#!/bin/sh

set -e

echo "Generating test TLS materials..."
python TestGenTLS.py

fileContent="$(cat ../latest_image.adoc)"
echo "Creating container using image $fileContent..."

# Check if podman or docker are running
if podman info > /dev/null 2>&1; then
    echo "Podman engine is running. Using Podman to run container..."
    engineCommand="podman"
    engineRunning=1
elif docker info > /dev/null 2>&1; then
    echo "Docker engine is running. Using Docker to run container..."
    engineCommand="docker"
    engineRunning=1
else
    echo "No engine is running. Please start Docker or Podman to run test..."
    engineCommand=""
    engineRunning=0
fi

# Run if an engine is running...
if [ $engineRunning -eq 0 ]; then
    $engineCommand run --detach \
        --publish 8081:8081 \
        --mount type=bind,src=./test_self.key,dst=/run/secrets/self.key \
        --mount type=bind,src=./test_self.crt,dst=/run/secrets/self.crt \
        --mount type=bind,src=./test_ca.crt,dst=/run/secrets/ca.crt \
        --env SERVER_STAGE_COUNT=1 \
        --env SERVER_STAGE_INDEX=1 \
        --env SELF_LISTENING_ADDRESS=0.0.0.0 \
        --env SELF_HEALTHCHECK_ADDRESS=localhost \
        --env SELF_PORT=8081 \
        --env SECRET_KEY_TARGET=/run/secrets/self.key \
        --env SECRET_CERT_TARGET=/run/secrets/self.crt \
        --env SECRET_CA_CERT_TARGET=/run/secrets/ca.crt \
        --env DEST_ADDRESS=localhost \
        --env DEST_PORT=8081 \
        --env THROTTLE_INTERVAL=5 \
        --env UPPER_BOUND=4000000000 \
        --name test-fib-container \
        "$fileContent"

    for i in 5 4 3 2 1
    do
        echo "Waiting $i seconds for container to spin up..."
        sleep 1
    done

    echo "Sending test message to container..."
    curl -k \
        --cert "./test_self.key" \
        --key "./test_self.crt" \
        --cacert "./test_ca.crt" \
        --request GET \
        "https://localhost:8081/start"

    echo "Done. Use your container engine to stop and delete the container whenever you're done."
fi

set +e
