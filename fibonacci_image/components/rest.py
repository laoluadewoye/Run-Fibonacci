from flask import Flask, request, jsonify
from sys import version
from subprocess import run, CompletedProcess
from threading import Thread
from time import sleep
from os import environ
from datastore_utils import APIType, DatastoreType, LogType, LogKind, save_log

# Create a server configuration
SERVER_CONFIG = {
    'PYTHON_INFO': version,
    'SERVER_API': environ.get('SERVER_API', 'N/A'),
    'SERVER_DATASTORE': environ.get('SERVER_DATASTORE', 'N/A'),
    'SERVER_STAGE_COUNT': environ.get('SERVER_STAGE_COUNT', 'N/A'),
    'SERVER_STAGE_INDEX': environ.get('SERVER_STAGE_INDEX', 'N/A'),
    'SELF_LISTENING_ADDRESS': environ.get('SELF_LISTENING_ADDRESS', 'N/A'),
    'SELF_HEALTHCHECK_ADDRESS': environ.get('SELF_HEALTHCHECK_ADDRESS', 'N/A'),
    'SELF_PORT': environ.get('SELF_PORT', 'N/A'),
    'SECRET_KEY_TARGET': environ.get('SECRET_KEY_TARGET', 'N/A'),
    'SECRET_CERT_TARGET': environ.get('SECRET_CERT_TARGET', 'N/A'),
    'SECRET_CA_CERT_TARGET': environ.get('SECRET_CA_CERT_TARGET', 'N/A'),
    'DEST_ADDRESS': environ.get('DEST_ADDRESS', 'N/A'),
    'DEST_PORT': environ.get('DEST_PORT', 'N/A'),
    'DATASTORE_ADDRESS': environ.get('DATASTORE_ADDRESS', 'N/A'),
    'DATASTORE_PORT': environ.get('DATASTORE_PORT', 'N/A'),
    'THROTTLE_INTERVAL': environ.get('THROTTLE_INTERVAL', 'N/A'),
    'UPPER_BOUND': environ.get('UPPER_BOUND', 'N/A'),
}

# Create log from version
save_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_CONFIG, version)

# Get the server API
assert 'SERVER_API' in environ
SERVER_API: str = environ.get('SERVER_API')
assert SERVER_API in [member.value for member in APIType]
save_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_CONFIG, f'The server API is {SERVER_API}.')

# Get the server datastore
assert 'SERVER_DATASTORE' in environ
SERVER_DATASTORE: str = environ.get('SERVER_DATASTORE')
assert SERVER_DATASTORE in [member.value for member in DatastoreType]
save_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_CONFIG, f'The server datastore is {SERVER_DATASTORE}.')

# Get the server count
assert 'SERVER_STAGE_COUNT' in environ
SERVER_STAGE_COUNT: int = int(environ.get('SERVER_STAGE_COUNT'))
save_log(
    LogType.OPERATION, [LogKind.ONSTART], SERVER_CONFIG,
    f'Total amount of servers in the network is {SERVER_STAGE_COUNT}.'
)

# Get the server index
assert 'SERVER_STAGE_INDEX' in environ
SERVER_STAGE_INDEX: int = int(environ.get('SERVER_STAGE_INDEX'))
assert 0 < SERVER_STAGE_INDEX <= SERVER_STAGE_COUNT
save_log(
    LogType.OPERATION, [LogKind.ONSTART], SERVER_CONFIG,
    f'Server index validated. Index is {SERVER_STAGE_INDEX}.'
)

# Get destination socket
assert 'DEST_ADDRESS' in environ
DEST_ADDRESS: str = environ.get('DEST_ADDRESS')

assert 'DEST_PORT' in environ
DEST_PORT: str = environ.get('DEST_PORT')
save_log(
    LogType.OPERATION, [LogKind.ONSTART], SERVER_CONFIG,
    f'Destination socket created. Socket is {DEST_ADDRESS} at port {DEST_PORT}.'
)

# Get throttle time
assert 'THROTTLE_INTERVAL' in environ
THROTTLE_INTERVAL: int = int(environ.get('THROTTLE_INTERVAL'))
save_log(
    LogType.OPERATION, [LogKind.ONSTART], SERVER_CONFIG,
    f'Throttle interval set to {THROTTLE_INTERVAL} second(s).'
)

# Get the upper bound
assert 'UPPER_BOUND' in environ
UPPER_BOUND: int = int(environ.get('UPPER_BOUND'))
save_log(LogType.OPERATION, [LogKind.ONSTART], SERVER_CONFIG, f'Upper bound of test set to {UPPER_BOUND}.')

# Start the log ID rotation
SNF_LOG_ID: str = 'N/A'
LAST_SNF_LOG_ID: str = 'N/A'

# Create app object
app = Flask(__name__)


# Define a sending thread
def trigger_send(new_fib_one, new_fib_two, snf_log_id):
    snf_result: CompletedProcess = run(
        ['./send_next_fib.sh', str(new_fib_one), str(new_fib_two), DEST_ADDRESS, DEST_PORT],
        capture_output=True, 
        text=True
    )
    save_log(
        LogType.SEND, [LogKind.ONCALL, LogKind.TRIGGERSEND], SERVER_CONFIG,
        f'Return Code for Message ID {snf_log_id}: {snf_result.returncode}'
    )
    save_log(
        LogType.SEND, [LogKind.ONCALL, LogKind.TRIGGERSEND], SERVER_CONFIG,
        f'Standard Output for Message ID {snf_log_id}: {snf_result.stdout}'
    )
    save_log(
        LogType.SEND, [LogKind.ONCALL, LogKind.TRIGGERSEND], SERVER_CONFIG,
        f'Error for Message ID {snf_log_id}: {snf_result.stderr}'
    )


# Create route processing logic
@app.route('/', methods=['POST'])
def process_fib_numbers():
    global SNF_LOG_ID

    # Ingest numbers
    fib_one: int = int(request.form['fib_one'])
    fib_two: int = int(request.form['fib_two'])
    save_log(
        LogType.RECEIVE, [LogKind.ONCALL, LogKind.PROCESS], SERVER_CONFIG,
        f'Retrieved numbers {fib_one} and {fib_two} in fibonacci sequence.'
    )

    # Create new numbers
    if fib_two > 0:  # The sequence already started
        new_fib_one: int = fib_two
        new_fib_two: int = fib_one + fib_two
    else:  # The sequence just started
        new_fib_one: int = 0
        new_fib_two: int = 1

    save_log(
        LogType.RECEIVE, [LogKind.ONCALL, LogKind.PROCESS], SERVER_CONFIG,
        f'Next fibonacci number determined to be {new_fib_two}.'
    )
    save_log(
        LogType.RECEIVE, [LogKind.ONCALL, LogKind.PROCESS], SERVER_CONFIG,
        f'Sending numbers {new_fib_one} and {new_fib_two} in fibonacci sequence.'
    )

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
        save_log(
            LogType.SEND, [LogKind.ONCALL, LogKind.PROCESS], SERVER_CONFIG,
            'Reached Upper Bound. Stopping Sending.'
        )

        msg: str = f'POST request succeeded. Reached upper bound.'
        return_code: int = 200

    # Send the response back
    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), return_code


# Create route processing logic
@app.route('/healthcheck', methods=['GET'])
def get_healthcheck():
    global SNF_LOG_ID
    global LAST_SNF_LOG_ID

    save_log(
        LogType.RECEIVE, [LogKind.ONCALL, LogKind.HEALTHCHECK], SERVER_CONFIG,
        'GET healthcheck request received.'
    )

    # Compare IDs
    if LAST_SNF_LOG_ID != SNF_LOG_ID: 
        msg: str = 'GET healthcheck request succeeded. Server has processed a new step.'
    else:
        msg: str = 'GET healthcheck request succeeded. Server is waiting for some reason.'
    save_log(LogType.SEND, [LogKind.ONCALL, LogKind.HEALTHCHECK], SERVER_CONFIG, msg)

    # Update Last ID for later healthcheck
    LAST_SNF_LOG_ID = SNF_LOG_ID

    # Send the response back
    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 200


# Create starting logic
@app.route('/start', methods=['GET'])
def start_fib():
    global SNF_LOG_ID

    save_log(LogType.RECEIVE, [LogKind.ONCALL, LogKind.START], SERVER_CONFIG, 'GET start request received.')

    # Set the log ID to the starting default
    SNF_LOG_ID = f'{SERVER_STAGE_INDEX}-0-0'

    # Run the bash script to start the sequence at 0 0
    trigger_send_thread: Thread = Thread(
        target=trigger_send, args=(0, 0, SNF_LOG_ID,)
    )
    trigger_send_thread.start()

    # Send the response back
    msg: str = f'GET start request succeeded. Started fibonacci sequence.'
    save_log(LogType.SEND, [LogKind.ONCALL, LogKind.START], SERVER_CONFIG, msg)

    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 202

@app.route('/datastore', methods=['POST'])
def save_log():
    ...
