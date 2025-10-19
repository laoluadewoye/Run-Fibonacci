from flask import Flask, request as flask_request, jsonify
from requests import request as requests_request, Response
from sys import version
from threading import Thread
from time import sleep
from os import environ, getpid
from datastore_utils import APIType, DatastoreType, LogType, LogKind, report_log, save_log

# Create a server identifier
SERVER_IDENTIFIER = {
    'PYTHON_INFO': version,
    'WORKER_ID': getpid(),
    'SERVER_API': environ.get('SERVER_API', 'N/A'),
    'SERVER_DATASTORE': environ.get('SERVER_DATASTORE', 'N/A'),
    'SERVER_STAGE_INDEX': environ.get('SERVER_STAGE_INDEX', 'N/A'),
    'SELF_LISTENING_ADDRESS': environ.get('SELF_LISTENING_ADDRESS', 'N/A'),
    'SELF_PORT': environ.get('SELF_PORT', 'N/A'),
}

# Create log from version
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER, version)

# Get the TLS materials
assert 'SECRET_KEY_TARGET' in environ
SECRET_KEY_TARGET: str = environ.get('SECRET_KEY_TARGET')
assert 'SECRET_CERT_TARGET' in environ
SECRET_CERT_TARGET: str = environ.get('SECRET_CERT_TARGET')
assert 'SECRET_PEM_TARGET' in environ
assert 'SECRET_CA_CERT_TARGET' in environ
SECRET_CA_CERT_TARGET: str = environ.get('SECRET_CA_CERT_TARGET')

# Get the datastore filepaths
assert 'DATASTORE_DEFAULT_FILEPATH' in environ
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'The datastore default log location is {environ.get('DATASTORE_DEFAULT_FILEPATH')}.')
assert 'DATASTORE_OPERATIONS_FILEPATH' in environ
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'The datastore operations log location is {environ.get('DATASTORE_OPERATIONS_FILEPATH')}.')
assert 'DATASTORE_FILEPATH' in environ
DATASTORE_FILEPATH: str = environ.get('DATASTORE_FILEPATH')
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'The datastore log location is {DATASTORE_FILEPATH}.')

# Get the server API
assert 'SERVER_API' in environ
SERVER_API: str = environ.get('SERVER_API')
assert SERVER_API in [member.value for member in APIType]
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER, f'The server API is {SERVER_API}.')

# Get the server datastore
assert 'SERVER_DATASTORE' in environ
SERVER_DATASTORE: str = environ.get('SERVER_DATASTORE')
assert SERVER_DATASTORE in [member.value for member in DatastoreType]
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER, f'The server datastore is {SERVER_DATASTORE}.')

# Get the server count
assert 'SERVER_STAGE_COUNT' in environ
SERVER_STAGE_COUNT: int = int(environ.get('SERVER_STAGE_COUNT'))
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'Total amount of servers in the network is {SERVER_STAGE_COUNT}.')

# Get the server index
assert 'SERVER_STAGE_INDEX' in environ
SERVER_STAGE_INDEX: int = int(environ.get('SERVER_STAGE_INDEX'))
assert 0 < SERVER_STAGE_INDEX <= SERVER_STAGE_COUNT
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'Server index validated. Index is {SERVER_STAGE_INDEX}.')

# Get destination socket
assert 'DEST_ADDRESS' in environ
DEST_ADDRESS: str = environ.get('DEST_ADDRESS')

assert 'DEST_PORT' in environ
DEST_PORT: str = environ.get('DEST_PORT')
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'Destination socket created. Socket is {DEST_ADDRESS} at port {DEST_PORT}.')

# Get throttle time
assert 'THROTTLE_INTERVAL' in environ
THROTTLE_INTERVAL: int = int(environ.get('THROTTLE_INTERVAL'))
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER,
           f'Throttle interval set to {THROTTLE_INTERVAL} second(s).')

# Get the upper bound
assert 'UPPER_BOUND' in environ
UPPER_BOUND: int = int(environ.get('UPPER_BOUND'))
report_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_IDENTIFIER, f'Upper bound of test set to {UPPER_BOUND}.')

# Start the log ID rotation
SNF_LOG_ID: str = 'N/A'
LAST_SNF_LOG_ID: str = 'N/A'

# Create app object
app = Flask(__name__)


# Define a sending thread
def trigger_send(new_fib_one, new_fib_two, snf_log_id):
    global SERVER_IDENTIFIER

    response: Response = requests_request(
        method='POST',
        url=f'https://{DEST_ADDRESS}:{DEST_PORT}',
        json={'fib_one': new_fib_one, 'fib_two': new_fib_two},
        cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
        verify=SECRET_CA_CERT_TARGET
    )
    report_log(LogType.SEND, [LogKind.ONCALL, LogKind.TRIGGERSEND], SERVER_IDENTIFIER,
               f'Return code for message ID {snf_log_id}: {response.status_code}')
    report_log(LogType.SEND, [LogKind.ONCALL, LogKind.TRIGGERSEND], SERVER_IDENTIFIER,
               f'Return info for message ID {snf_log_id}: {response.json()}')


# Create route processing logic
@app.route('/', methods=['POST'])
def process_fib_numbers():
    global SERVER_IDENTIFIER
    global SNF_LOG_ID

    # Get numbers
    fib_numbers = flask_request.get_json(force=True, silent=True)
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
    sleep(THROTTLE_INTERVAL)

    # Update the current log id
    SNF_LOG_ID = f'{SERVER_STAGE_INDEX}-{new_fib_one}-{new_fib_two}'

    # Decide on a response to send back
    if new_fib_one < UPPER_BOUND:  # Run the bash script to forward the next server in line
        trigger_send_thread: Thread = Thread(
            target=trigger_send, args=(new_fib_one, new_fib_two, SNF_LOG_ID,)
        )
        trigger_send_thread.start()
        msg: str = f'POST request succeeded. Sent off fibonacci numbers.'
        return_code: int = 202
    else:  # Return that the upper bound has been reached
        report_log(LogType.SEND, [LogKind.ONCALL, LogKind.MAIN], SERVER_IDENTIFIER,
                   'Reached upper bound. Stopping sending.')

        msg: str = f'POST request succeeded. Reached upper bound.'
        return_code: int = 200

    # Send the response back
    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), return_code


# Create healthcheck logic
@app.route('/healthcheck', methods=['GET'])
def get_healthcheck():
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
def start_fib():
    global SERVER_IDENTIFIER
    global SNF_LOG_ID

    report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.START], SERVER_IDENTIFIER, 'GET start request received.')

    # Set the log ID to the starting default
    SNF_LOG_ID = f'{SERVER_STAGE_INDEX}-0-0'

    # Run the bash script to start the sequence at 0 0
    trigger_send_thread: Thread = Thread(
        target=trigger_send, args=(0, 0, SNF_LOG_ID,)
    )
    trigger_send_thread.start()

    # Send the response back
    msg: str = f'GET start request succeeded. Started fibonacci sequence.'
    report_log(LogType.SEND, [LogKind.ONCALL, LogKind.START], SERVER_IDENTIFIER, msg)

    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 202


# Create datastore logic
@app.route('/datastore', methods=['POST'])
def process_log():
    global SERVER_IDENTIFIER
    global SNF_LOG_ID
    global DATASTORE_FILEPATH

    # Get log
    cur_log = flask_request.get_json(force=True, silent=True)
    if cur_log is None:
        msg: str = f'POST datastore request failed. Unable to retrieve log.'
        report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.DATASTORE], SERVER_IDENTIFIER, msg)
        return jsonify({'status': 'Fail', 'message': msg, 'result': SNF_LOG_ID}), 422

    # Save log to file
    success, op_success = save_log(DATASTORE_FILEPATH, cur_log, SERVER_IDENTIFIER)
    if success and op_success:
        msg: str = f'POST datastore request succeeded. Saved log.'
        report_log(LogType.SEND, [LogKind.ONCALL, LogKind.DATASTORE], SERVER_IDENTIFIER, msg)
        return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 200
    if success and not op_success:
        msg: str = f'POST datastore request succeeded. Saved log. Subsequent operation log saving failed.'
        report_log(LogType.SEND, [LogKind.ONCALL, LogKind.DATASTORE], SERVER_IDENTIFIER, msg)
        return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 200
    else:
        msg: str = f'POST datastore request failed. Saving log to file failed.'
        report_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.DATASTORE], SERVER_IDENTIFIER, msg)
        return jsonify({'status': 'Fail', 'message': msg, 'result': SNF_LOG_ID}), 500
