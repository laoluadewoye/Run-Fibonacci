#!/bin/sh

# Sends a get request to the healthcheck API of the fibonacci server
set -e

# Print the destination socket
echo "https://$SELF_ADDRESS:$SELF_PORT/healthcheck"

# Send the information
curl \
    --cert "$SECRET_CERT_TARGET" \
    --key "$SECRET_KEY_TARGET" \
    --cacert "$SECRET_CA_CERT_TARGET" \
    --request GET \
    "https://$SELF_ADDRESS:$SELF_PORT/healthcheck"

set +e
