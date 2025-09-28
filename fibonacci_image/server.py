from flask import Flask, request, jsonify
from subprocess import run, CompletedProcess
from threading import Thread
from time import sleep
from os import environ


# Get the server count
assert 'SERVER_STAGE_COUNT' in environ
SERVER_STAGE_COUNT: int = int(environ.get('SERVER_STAGE_COUNT'))
print(f'Total amount of servers in the network is {SERVER_STAGE_COUNT}.', flush=True)

# Get the server index
assert 'SERVER_STAGE_INDEX' in environ
SERVER_STAGE_INDEX: int = int(environ.get('SERVER_STAGE_INDEX'))
assert 0 < SERVER_STAGE_INDEX < SERVER_STAGE_COUNT
print(f'Server index validated, index is {SERVER_STAGE_INDEX}.', flush=True)

# Get destination socket
assert 'DEST_ADDRESS' in environ
DEST_ADDRESS: str = environ.get('DEST_ADDRESS')

assert 'DEST_PORT' in environ
DEST_PORT: str = environ.get('DEST_PORT')
print(f'Destination socket created. Socket is {DEST_ADDRESS} at port {DEST_PORT}.', flush=True)

# Get throttle time
assert 'THROTTLE_INTERVAL' in environ
THROTTLE_INTERVAL: int = int(environ.get('THROTTLE_INTERVAL'))
print(f'Throttle interval set to {THROTTLE_INTERVAL} second(s).', flush=True)

# Get the upper bound
assert 'UPPER_BOUND' in environ
UPPER_BOUND: int = int(environ.get('UPPER_BOUND'))
print(f'Upper bound of test set to {UPPER_BOUND}.', flush=True)

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
    print(f'Return Code for Message ID {snf_log_id}: {snf_result.returncode}', flush=True)
    print(f'Standard Output for Message ID {snf_log_id}: {snf_result.stdout}', flush=True)
    print(f'Error for Message ID {snf_log_id}: {snf_result.stderr}', flush=True)


# Create route processing logic
@app.route('/', methods=['POST'])
def process_fib_numbers():
    global SNF_LOG_ID

    # Ingest numbers
    fib_one: int = int(request.form['fib_one'])
    fib_two: int = int(request.form['fib_two'])
    print(f'Retrieved numbers {fib_one} and {fib_two} in fibonacci sequence.', flush=True)

    # Create new numbers
    if fib_two > 0:  # The sequence already started
        new_fib_one: int = fib_two
        new_fib_two: int = fib_one + fib_two
    else:  # The sequence just started
        new_fib_one: int = 0
        new_fib_two: int = 1

    print(f'Next fibonacci number determined to be {new_fib_two}.', flush=True)
    print(f'Sending numbers {new_fib_one} and {new_fib_two} in fibonacci sequence.', flush=True)

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
        print(f'Reached Upper Bound. Stopping Sending.', flush=True)
        msg: str = f'POST request succeeded. Reached upper bound.'
        return_code: int = 200

    # Send the response back
    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), return_code


# Create route processing logic
@app.route('/healthcheck', methods=['GET'])
def get_healthcheck():
    global SNF_LOG_ID
    global LAST_SNF_LOG_ID

    # Compare IDs
    if LAST_SNF_LOG_ID != SNF_LOG_ID: 
        msg: str = 'GET healthcheck request succeeded. Server has processed a new step.'
    else:
        msg: str = 'GET healthcheck request succeeded. Server is waiting for some reason.'
    print(msg, flush=True)

    # Update Last ID for later healthcheck
    LAST_SNF_LOG_ID = SNF_LOG_ID

    # Send the response back
    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 200


# Create starting logic
@app.route('/start', methods=['GET'])
def start_fib():
    global SNF_LOG_ID

    # Set the log ID to the starting default
    SNF_LOG_ID = f'{SERVER_STAGE_INDEX}-0-0'

    # Run the bash script to start the sequence at 0 0
    trigger_send_thread: Thread = Thread(
        target=trigger_send, args=(0, 0, SNF_LOG_ID,)
    )
    trigger_send_thread.start()

    # Send the response back
    msg: str = f'GET start request succeeded. Started fibonacci sequence.'
    return jsonify({'status': 'Success', 'message': msg, 'result': SNF_LOG_ID}), 202
