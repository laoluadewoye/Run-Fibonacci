#!/bin/sh

set -e

# Check if podman or docker are running
if podman info > /dev/null 2>&1; then
    echo "Podman engine is running. Using Podman to remove container..."
    engineCommand="podman"
    engineRunning=1
elif docker info > /dev/null 2>&1; then
    echo "Docker engine is running. Using Docker to remove container..."
    engineCommand="docker"
    engineRunning=1
else
    echo "No engine is running. Please start Docker or Podman to run removal..."
    engineCommand=""
    engineRunning=0
fi

if [ $engineRunning -eq 0 ]; then
    $engineCommand stop test-fib-container
    $engineCommand rm test-fib-container
fi

echo "Removing TLS materials..."
rm "*.key"
rm "*.crt"
rm "*.p12"

set +e
