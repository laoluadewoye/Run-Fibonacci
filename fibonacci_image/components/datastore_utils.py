from server_init import *
from os import getpid
from os.path import exists
from enum import StrEnum, auto
from typing import Union
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.results import InsertOneResult
from pymongo.errors import OperationFailure
from psycopg2 import connect
from psycopg2.errors import OperationalError
from base64 import b64encode
from json import dumps
from hashlib import sha256
from requests import request, Response, RequestException
from datetime import datetime

# Set datastore log counts
DATASTORE_LOG_COUNT_SERVER: int = 0
DATASTORE_LOG_COUNT_DEFAULT: int = 0
DATASTORE_LOG_COUNT_OPERATION: int = 0


# Create datastore connection if needed
class DatastoreType(StrEnum):
    DSNONE = 'none'
    DSFILE = 'file'
    ELASTICSTACK = auto()
    MONGODB = auto()
    POSTGRESQL = auto()


if DATASTORE_TYPE == DatastoreType.MONGODB.value:
    DATASTORE_CONNECTION: Union[MongoClient, connect] = MongoClient(
        host=NETWORK_DATASTORE_ADDRESS, port=NETWORK_DATASTORE_PORT, username=DATASTORE_AUTH_USERNAME,
        password=DATASTORE_AUTH_PASSWORD
        # tls=True, tlsCAFile=SECRET_CA_CERT_TARGET, tlsCertificateKeyFile=SECRET_PEM_TARGET
    )
    DATASTORE_DATABASE: Database = DATASTORE_CONNECTION[DATASTORE_AUTH_USERNAME]
    if 'datastore' not in DATASTORE_DATABASE.list_collection_names():
        DATASTORE_DATABASE.create_collection(
            name='datastore',
            timeseries={
                'timeField': 'log_time',
                'metaField': 'log_server',
                'granularity': 'seconds'
            }
        )
elif DATASTORE_TYPE == DatastoreType.POSTGRESQL.value:
    DATASTORE_CONNECTION: Union[MongoClient, connect] = connect(
        dbname=DATASTORE_AUTH_USERNAME, user=DATASTORE_AUTH_USERNAME, password=DATASTORE_AUTH_PASSWORD,
        host=NETWORK_DATASTORE_ADDRESS, port=NETWORK_DATASTORE_PORT
        # sslmode='require', sslcert=SECRET_CERT_TARGET, sslkey=SECRET_KEY_TARGET,
        # sslcertmode='require', sslrootcert=SECRET_CA_CERT_TARGET
    )


# Specify valid API types
class APIType(StrEnum):
    REST = auto()
    GRPC = auto()
    SOAP = auto()
    GRAPHQL = auto()
    MQTT = auto()


# Specify valid log types
class LogType(StrEnum):
    SEND = auto()
    RECEIVE = auto()
    OPERATION = auto()


# Specify valid log kinds
class LogKind(StrEnum):
    # Events
    ONSTART = auto()
    ONCALL = auto()
    ONLOG = auto()

    # Methods
    TRIGGERSEND = auto()
    MAIN = auto()
    HEALTHCHECK = auto()
    START = auto()
    DATASTORE = auto()


def create_log(log_type: LogType, log_kinds: list[LogKind], server_id: dict, details: str) -> dict:
    # Create log
    new_log: dict[str, str] = {
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
        'server': b64encode(dumps(server_id).encode()).decode(),
        'type': log_type.value,
        'kinds': ';'.join([str(lk.value) for lk in log_kinds]),
        'details': details
    }

    # Hash the contents of the log and return
    new_log['hash'] = sha256(dumps(new_log).encode()).hexdigest()
    return new_log


def save_log(filepath: str, cur_log: dict, server_id: Union[dict, None] = None,
             is_operation: bool = False) -> Union[tuple[bool, bool], bool]:
    global DATASTORE_LOG_COUNT_SERVER
    global DATASTORE_LOG_COUNT_DEFAULT
    global DATASTORE_LOG_COUNT_OPERATION

    # Get log count
    if filepath == DATASTORE_LOGS_SERVER_PATH:
        DATASTORE_LOG_COUNT_SERVER += 1
        cur_log_count: int = DATASTORE_LOG_COUNT_SERVER
    elif filepath == DATASTORE_LOGS_DEFAULT_PATH:
        DATASTORE_LOG_COUNT_DEFAULT += 1
        cur_log_count: int = DATASTORE_LOG_COUNT_DEFAULT
    elif filepath == DATASTORE_LOGS_OPERATION_PATH:
        DATASTORE_LOG_COUNT_OPERATION += 1
        cur_log_count: int = DATASTORE_LOG_COUNT_OPERATION
    else:
        cur_log_count: int = -1
    assert cur_log_count > 0, 'File path should match one of the set paths.'

    # Write down everything
    try:
        if not exists(filepath):
            with open(filepath, 'w') as ds_file:
                ds_file.write('id,' + ','.join(cur_log.keys()) + '\n')
                ds_file.write(f'{cur_log_count},' + ','.join(cur_log.values()) + '\n')
        else:
            with open(filepath, 'a') as ds_file:
                ds_file.write(f'{cur_log_count},' + ','.join(cur_log.values()) + '\n')
        success: bool = True
        details: str ='Log saving event successful.'
    except FileNotFoundError:
        success: bool = False
        details: str = 'Log saving event unsuccessful. Local Datastore location not found.'

    if not is_operation:
        ds_log: dict = create_log(LogType.OPERATION, [LogKind.ONLOG], server_id, details)
        op_success: bool = save_log(DATASTORE_LOGS_OPERATION_PATH, ds_log, is_operation=True)
        return success, op_success
    else:
        return success


def send_log(cur_log: dict, server_id: dict):
    if DATASTORE_TYPE == DatastoreType.DSNONE.value: # Save to local temp CSV
        save_log(DATASTORE_LOGS_DEFAULT_PATH, cur_log, server_id)
    elif DATASTORE_TYPE == DatastoreType.DSFILE.value:  # Send to remote CSV
        try:
            response: Response = request(
                method='POST',
                url=f'https://{NETWORK_DATASTORE_ADDRESS}:{NETWORK_DATASTORE_PORT}/datastore',
                json=cur_log,
                cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
                verify=TLS_CA_CERT_PATH
            )
            ds_details: str = f'Return info for file datastore sending: {response.json()}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
        except RequestException as e:
            ds_details: str = f'Experienced Request Exception for file datastore. Details: {e}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
    elif DATASTORE_TYPE == DatastoreType.ELASTICSTACK.value:  # Send to remote Elasticstack
        try:
            cur_log['data_stream'] = {
                'type': 'logs',
                'dataset': f'fibonacci-{server_id['API']}-{server_id['STAGE_INDEX']}-{server_id['WORKER_PID']}',
                'namespace': 'datastore'
            }
            response: Response = request(
                method='POST',
                url=f'http://{NETWORK_DATASTORE_ADDRESS}:{NETWORK_DATASTORE_PORT}',
                auth=(DATASTORE_AUTH_USERNAME, DATASTORE_AUTH_PASSWORD),
                json=cur_log
                # cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
                # verify=SECRET_CA_CERT_TARGET
            )
            ds_details: str = f'Return info for ElasticStack datastore sending: {response.text}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
        except RequestException as e:
            ds_details: str = f'Experienced Request Exception for Elasticstack datastore. Details: {e}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
    elif DATASTORE_TYPE == DatastoreType.MONGODB.value:  # Send to remote MongoDB
        # Write to collection
        try:
            result: InsertOneResult = DATASTORE_CONNECTION[DATASTORE_AUTH_USERNAME]['datastore'].insert_one({
                'log_time': datetime.strptime(cur_log['time'], '%Y-%m-%d %H:%M:%S.%f'),
                'log_server': cur_log['server'],
                'log_type': cur_log['type'],
                'log_kinds': cur_log['kinds'],
                'log_details': cur_log['details'],
                'log_hash': cur_log['hash']
            })
            ds_details: str = f'Result ID for MongoDB datastore sending: {result.inserted_id}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
        except OperationFailure as e:
            ds_details: str = f'Experienced Operational Failure. Details: {e}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
    elif DATASTORE_TYPE == DatastoreType.POSTGRESQL.value:  # Send to remote PostgreSQL
        # Write to table
        try:
            with DATASTORE_CONNECTION:
                with DATASTORE_CONNECTION.cursor() as insert_cursor:
                    insert_cursor.execute("""
                        INSERT INTO datastore (log_time, log_server, log_type, log_kinds, log_details, log_hash) 
                        VALUES (%s, %s, %s, %s, %s, %s);
                        """,
                        (
                            datetime.strptime(cur_log['time'], '%Y-%m-%d %H:%M:%S.%f'), cur_log['server'],
                            cur_log['type'], cur_log['kinds'], cur_log['details'], cur_log['hash'],
                        )
                    )
            ds_details: str = f'Successfully log with hash {cur_log["hash"]} to datastore.'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
        except OperationalError as e:
            ds_details: str = f'Experienced Operational Error. Details: {e}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
    else:  # Error out
        ds_details: str = 'Could not match server datastore option to available constants.'
        report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)


def report_log(log_type: LogType, log_kinds: list[LogKind], server_id: dict, details: str,
               is_operation: bool = False) -> None:
    if is_operation:
        print(f'Gunicorn Worker {getpid()} Operation Log: {details}', flush=True)
        new_log: dict = create_log(log_type, log_kinds, server_id, details)
        save_log(DATASTORE_LOGS_OPERATION_PATH, new_log, is_operation=is_operation)
    else:
        print(f'Gunicorn Worker {getpid()} Server Log: {details}', flush=True)
        new_log: dict = create_log(log_type, log_kinds, server_id, details)
        send_log(new_log, server_id)


'''
Type of logs

1) Sends - Logs that are sent out by the server
2) Receives - Logs that are retrieved by the server
3) Operations - Logs that are generated by the server

Kinds of logs

1) OnStart - Logs that are created when the server is first started
2) OnCall - Logs that are created when the server API is called

Log fields

* ID - Incrementing number autogenerated by whatever datastore is used
* Time - The timestamp the log was recorded in UNIX epoch seconds
* Server - The configuration of the server in base 64
* Type - The type of log
* Kinds - The kind(s) of log
* Details - The details of the log in base 64
* Hash - The Hash of the log in SHA256
'''
