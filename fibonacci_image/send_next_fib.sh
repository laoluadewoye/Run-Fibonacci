#!/bin/sh

# Sends the next two numbers in the fibonacci sequence to the next server
set -e

# Take in fibonacci numbers and socket combination
fib_one=$1
fib_two=$2
dest_ip=$3
dest_port=$4

# Print the destination socket
echo "https://$dest_ip:$dest_port"

# Send the information
curl \
    --cert "$SECRET_CERT_TARGET" \
    --key "$SECRET_KEY_TARGET" \
    --cacert "$SECRET_CA_CERT_TARGET" \
    --data "fib_one=$fib_one&fib_two=$fib_two" \
    --header "Content-Type: application/x-www-form-urlencoded" \
    --request POST \
    "https://$dest_ip:$dest_port"

set +e
