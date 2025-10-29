from server_init import *
from os import getpid, name
from platform import win32_ver, freedesktop_os_release
from flask import Flask, request as flask_request, jsonify
from requests import request as requests_request, Response
from sys import version
from threading import Thread
from time import sleep
from datastore_utils import APIType, DatastoreType, LogType, LogKind, report_log, save_log

# Create a server identifier
if name == 'nt':
    os_version: str = f'Windows {win32_ver()[0]}.{win32_ver()[1]}'
else:
    os_version: str = f'{freedesktop_os_release()['PRETTY_NAME']}'

SERVER_IDENTIFIER: dict = {
    'PYTHON_VERSION': version,
    'OS_VERSION': os_version,
    'WORKER_PID': getpid(),
    'API': API,
    'DATASTORE_TYPE': DATASTORE_TYPE,
    'STAGE_INDEX': STAGE_INDEX
}

# Create log from the server identifier
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'The server identifier is {SERVER_IDENTIFIER}')

# Create log from the datastore filepaths
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'The datastore default server log location is {DATASTORE_LOGS_DEFAULT_PATH}.')
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'The datastore operations log location is {DATASTORE_LOGS_OPERATION_PATH}.')
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'The datastore server log location is {DATASTORE_LOGS_SERVER_PATH}.')

# Create log from the server API
assert API in [member.value for member in APIType]
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER, f'The server API is {API}.')

# Get the server datastore
assert DATASTORE_TYPE in [member.value for member in DatastoreType]
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER, f'The server datastore is {DATASTORE_TYPE}.')

# Get the server count
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'Total amount of servers in the network is {STAGE_COUNT}.')

# Get the server index
assert 0 < STAGE_INDEX <= STAGE_COUNT
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'Server index validated. Index is {STAGE_INDEX}.')

# Get destination socket
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'Destination socket created. Socket is {NETWORK_DEST_ADDRESS} at port {NETWORK_DEST_PORT}.')

# Get throttle time
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'Throttle interval set to {THROTTLE_SECONDS} second(s).')

# Get the upper bound
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER, f'Upper bound of test set to {UPPER_BOUND}.')

# Start the log ID rotation
SNF_LOG_ID: str = 'N/A'
LAST_SNF_LOG_ID: str = 'N/A'

# Create app object
app = Flask(__name__)


# Define a sending thread
def trigger_send(new_fib_one: int, new_fib_two: int, snf_log_id: str) -> None:
    global SERVER_IDENTIFIER

    response: Response = requests_request(
        method='POST',
        url=f'https://{NETWORK_DEST_ADDRESS}:{NETWORK_DEST_PORT}',
        json={'fib_one': new_fib_one, 'fib_two': new_fib_two},
        cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
        verify=TLS_CA_CERT_PATH
    )
    report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.TRIGGERSEND], SERVER_IDENTIFIER,
               f'Return code for message ID {snf_log_id}: {response.status_code}')
    report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.TRIGGERSEND], SERVER_IDENTIFIER,
               f'Return info for message ID {snf_log_id}: {response.json()}')


# Create route processing logic
@app.route('/', methods=['POST'])
def process_fib_numbers() -> tuple[Response, int]:
    global SERVER_IDENTIFIER
    global SNF_LOG_ID

    # Get numbers
    fib_numbers: dict = flask_request.get_json(force=True, silent=True)
    if fib_numbers is None:
        msg: str = f'POST request failed. Unable to retrieve numbers.'
        report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.MAIN], SERVER_IDENTIFIER, msg)
        return jsonify({'status': 'Fail', 'message': msg, 'result': SNF_LOG_ID}), 422

    # Ingest numbers
    fib_one: int = int(fib_numbers['fib_one'])
    fib_two: int = int(fib_numbers['fib_two'])
    report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.MAIN], SERVER_IDENTIFIER,
               f'Retrieved numbers {fib_one} and {fib_two} in fibonacci sequence.')

    # Create new numbers
    if fib_two > 0:  # The sequence already started
        new_fib_one: int = fib_two
        new_fib_two: int = fib_one + fib_two
    else:  # The sequence just started
        new_fib_one: int = 0
        new_fib_two: int = 1

    report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.MAIN], SERVER_IDENTIFIER,
               f'Next fibonacci number determined to be {new_fib_two}.')
    report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.MAIN], SERVER_IDENTIFIER,
               f'Sending numbers {new_fib_one} and {new_fib_two} in fibonacci sequence.')

    # Artificial throttling
    sleep(THROTTLE_SECONDS)

    # Update the current log id
    SNF_LOG_ID = f'{STAGE_INDEX}-{new_fib_one}-{new_fib_two}'

    # Decide on a response to send back
    if new_fib_one < UPPER_BOUND:  # Run the bash script to forward the next server in line
        trigger_send_thread: Thread = Thread(target=trigger_send, args=(new_fib_one, new_fib_two, SNF_LOG_ID,))
        trigger_send_thread.start()
        msg: str = 'POST request succeeded. Sent off fibonacci numbers.'
        return_code: int = 202
    else:  # Return that the upper bound has been reached
        msg: str = f'POST request succeeded. Reached upper bound.'
        return_code: int = 200

    # Send the response back
    report_log(LogType.SEND, [LogKind.ONCALL, LogKind.MAIN], SERVER_IDENTIFIER, msg)
    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), return_code


# Create healthcheck logic
@app.route('/healthcheck', methods=['GET'])
def get_healthcheck() -> tuple[Response, int]:
    global SERVER_IDENTIFIER
    global SNF_LOG_ID
    global LAST_SNF_LOG_ID

    report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.HEALTHCHECK], SERVER_IDENTIFIER,
               'GET healthcheck request received.')

    # Compare IDs
    if LAST_SNF_LOG_ID != SNF_LOG_ID: 
        msg: str = 'GET healthcheck request succeeded. Server has processed a new step.'
    else:
        msg: str = 'GET healthcheck request succeeded. Server is waiting for some reason.'
    report_log(LogType.SEND, [LogKind.ONCALL, LogKind.HEALTHCHECK], SERVER_IDENTIFIER, msg)

    # Update Last ID for later healthcheck
    LAST_SNF_LOG_ID = SNF_LOG_ID

    # Send the response back
    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 200


# Create starting logic
@app.route('/start', methods=['GET'])
def start_fib() -> tuple[Response, int]:
    global SERVER_IDENTIFIER
    global SNF_LOG_ID

    report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.START], SERVER_IDENTIFIER, 'GET start request received.')

    # Set the log ID to the starting default
    SNF_LOG_ID = f'{STAGE_INDEX}-0-0'

    # Run the bash script to start the sequence at 0 0
    trigger_send_thread: Thread = Thread(target=trigger_send, args=(0, 0, SNF_LOG_ID,))
    trigger_send_thread.start()

    # Send the response back
    msg: str = f'GET start request succeeded. Started fibonacci sequence.'
    report_log(LogType.SEND, [LogKind.ONCALL, LogKind.START], SERVER_IDENTIFIER, msg)

    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 202


# Create datastore logic
@app.route('/datastore', methods=['POST'])
def process_log() -> tuple[Response, int]:
    global SERVER_IDENTIFIER
    global SNF_LOG_ID

    # Get log
    cur_log: dict = flask_request.get_json(force=True, silent=True)
    if cur_log is None:
        msg: str = f'POST datastore request failed. Unable to retrieve log.'
        report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.DATASTORE], SERVER_IDENTIFIER, msg)
        return jsonify({'status': 'Fail', 'message': msg, 'result': SNF_LOG_ID}), 422

    # Save log to file
    success, op_success = save_log(DATASTORE_LOGS_SERVER_PATH, cur_log, SERVER_IDENTIFIER)
    if success and op_success:
        status: str = 'Success'
        msg: str = f'POST datastore request succeeded. Saved log.'
        return_code: int = 200
    elif success and not op_success:
        status: str = 'Success'
        msg: str = f'POST datastore request succeeded. Saved log. Subsequent operation log saving failed.'
        return_code: int = 200
    else:
        status: str = 'Fail'
        msg: str = f'POST datastore request failed. Saving log to file failed.'
        return_code: int = 500

    report_log(LogType.SEND, [LogKind.ONCALL, LogKind.DATASTORE], SERVER_IDENTIFIER, msg)
    return jsonify({'status': status, 'message': msg, 'result': SNF_LOG_ID}), return_code
