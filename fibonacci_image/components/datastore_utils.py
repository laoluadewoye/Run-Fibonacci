from os import environ, getpid
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

# Specify desired API and datastore
SERVER_API: str = environ.get('SERVER_API')
SERVER_DATASTORE: str = environ.get('SERVER_DATASTORE')

# Specify TLS materials
SECRET_KEY_TARGET: str = environ.get('SECRET_KEY_TARGET')
SECRET_CERT_TARGET: str = environ.get('SECRET_CERT_TARGET')
SECRET_PEM_TARGET: str = environ.get('SECRET_PEM_TARGET')
SECRET_CA_CERT_TARGET: str = environ.get('SECRET_CA_CERT_TARGET')

# Specify default datastore log location and log counts
DATASTORE_FILEPATH: str = environ.get('DATASTORE_FILEPATH')
DATASTORE_DEFAULT_FILEPATH: str = environ.get('DATASTORE_DEFAULT_FILEPATH')
DATASTORE_OPERATIONS_FILEPATH: str = environ.get('DATASTORE_OPERATIONS_FILEPATH')
DATASTORE_LOG_COUNT: int = 0
DATASTORE_DEFAULT_LOG_COUNT: int = 0
DATASTORE_OPERATIONS_LOG_COUNT: int = 0

# Specify datastore network socket
DATASTORE_ADDRESS: str = environ.get('DATASTORE_ADDRESS')
DATASTORE_PORT: int = int(environ.get('DATASTORE_PORT'))


# Create datastore connection if needed
class DatastoreType(StrEnum):
    DSNONE = 'none'
    DSFILE = 'file'
    ELASTICSTACK = auto()
    MONGODB = auto()
    POSTGRESQL = auto()


DATASTORE_USER: str = environ.get('DATASTORE_USER', 'N/A')
DATASTORE_PASSWORD: str = environ.get('DATASTORE_PASSWORD', 'N/A')

if SERVER_DATASTORE == DatastoreType.MONGODB.value:
    DATASTORE_CONNECTION: Union[MongoClient, connect] = MongoClient(
        host=DATASTORE_ADDRESS, port=DATASTORE_PORT, username=DATASTORE_USER, password=DATASTORE_PASSWORD
        # tls=True, tlsCAFile=SECRET_CA_CERT_TARGET, tlsCertificateKeyFile=SECRET_PEM_TARGET
    )
    DATASTORE_DATABASE: Database = DATASTORE_CONNECTION[DATASTORE_USER]
    if 'datastore' not in DATASTORE_DATABASE.list_collection_names():
        DATASTORE_DATABASE.create_collection(
            name='datastore',
            timeseries={
                'timeField': 'log_time',
                'metaField': 'log_server',
                'granularity': 'seconds'
            }
        )
elif SERVER_DATASTORE == DatastoreType.POSTGRESQL.value:
    DATASTORE_CONNECTION: Union[MongoClient, connect] = connect(
        dbname=DATASTORE_USER, user=DATASTORE_USER, password=DATASTORE_PASSWORD, host=DATASTORE_ADDRESS,
        port=DATASTORE_PORT
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
    global DATASTORE_FILEPATH
    global DATASTORE_DEFAULT_FILEPATH
    global DATASTORE_OPERATIONS_FILEPATH
    global DATASTORE_LOG_COUNT
    global DATASTORE_DEFAULT_LOG_COUNT
    global DATASTORE_OPERATIONS_LOG_COUNT

    # Get log count
    if filepath == DATASTORE_FILEPATH:
        DATASTORE_LOG_COUNT += 1
        cur_log_count: int = DATASTORE_LOG_COUNT
    elif filepath == DATASTORE_DEFAULT_FILEPATH:
        DATASTORE_DEFAULT_LOG_COUNT += 1
        cur_log_count: int = DATASTORE_DEFAULT_LOG_COUNT
    elif filepath == DATASTORE_OPERATIONS_FILEPATH:
        DATASTORE_OPERATIONS_LOG_COUNT += 1
        cur_log_count: int = DATASTORE_OPERATIONS_LOG_COUNT
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
        op_success: bool = save_log(DATASTORE_OPERATIONS_FILEPATH, ds_log, is_operation=True)
        return success, op_success
    else:
        return success


def send_log(cur_log: dict, server_id: dict):
    global SERVER_DATASTORE
    global DATASTORE_DEFAULT_FILEPATH
    global DATASTORE_OPERATIONS_FILEPATH
    global DATASTORE_ADDRESS
    global DATASTORE_PORT
    global DATASTORE_USER
    global DATASTORE_PASSWORD
    global DATASTORE_CONNECTION
    global SECRET_KEY_TARGET
    global SECRET_CERT_TARGET
    global SECRET_CA_CERT_TARGET

    if SERVER_DATASTORE == DatastoreType.DSNONE.value: # Save to local temp CSV
        save_log(DATASTORE_DEFAULT_FILEPATH, cur_log, server_id)
    elif SERVER_DATASTORE == DatastoreType.DSFILE.value:  # Send to remote CSV
        try:
            response: Response = request(
                method='POST',
                url=f'https://{DATASTORE_ADDRESS}:{DATASTORE_PORT}/datastore',
                json=cur_log,
                cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
                verify=SECRET_CA_CERT_TARGET
            )
            ds_details: str = f'Return info for file datastore sending: {response.json()}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
        except RequestException as e:
            ds_details: str = f'Experienced Request Exception for file datastore. Details: {e}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
    elif SERVER_DATASTORE == DatastoreType.ELASTICSTACK.value:  # Send to remote elasticstack
        try:
            response: Response = request(
                method='POST',
                url=f'https://{DATASTORE_ADDRESS}:{DATASTORE_PORT}',
                auth=(DATASTORE_USER, DATASTORE_PASSWORD),
                json=cur_log,
                cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
                verify=SECRET_CA_CERT_TARGET
            )
            ds_details: str = f'Return info for ElasticStack datastore sending: {response.json()}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
        except RequestException as e:
            ds_details: str = f'Experienced Request Exception for Elasticstack datastore. Details: {e}'
            report_log(LogType.OPERATION, [LogKind.ONLOG], server_id, ds_details, is_operation=True)
    elif SERVER_DATASTORE == DatastoreType.MONGODB.value:  # Send to remote MongoDB
        # Write to collection
        try:
            result: InsertOneResult = DATASTORE_CONNECTION[DATASTORE_USER]['datastore'].insert_one({
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
    elif SERVER_DATASTORE == DatastoreType.POSTGRESQL.value:  # Send to remote PostgreSQL
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
    global DATASTORE_OPERATIONS_FILEPATH

    if is_operation:
        print(f'Gunicorn Worker {getpid()} Operation Log: {details}', flush=True)
        new_log: dict = create_log(log_type, log_kinds, server_id, details)
        save_log(DATASTORE_OPERATIONS_FILEPATH, new_log, is_operation=is_operation)
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
