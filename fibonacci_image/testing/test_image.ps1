$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

Write-Host "Generating test TLS materials..."
py -3.13 TestGenTLS.py

Write-Host "Converting PEM materials to PKCS12 materials for Windows..."
openssl pkcs12 -export -in test_ca.crt -inkey test_ca.key -out test_ca.p12
openssl pkcs12 -export -in test_self.crt -inkey test_self.key -out test_self.p12

$fileContent = Get-Content "../latest_image.adoc"
Write-Host "Creating container using image $fileContent..."

# Check if docker or podman are running
docker info | Out-Null
$dockerRunning = ($LASTEXITCODE -eq 0)
podman info | Out-Null
$podmanRunning = ($LASTEXITCODE -eq 0)

$engineRunning = 0
$engineCommand = ""
if ($dockerRunning) {
    Write-Host "Docker engine is running. Using Docker to run container..."
    $engineRunning = 1
    $engineCommand = "docker"
} elseif ($podmanRunning) {
    Write-Host "Podman engine is running. Using Podman to run container..."
    $engineRunning = 1
    $engineCommand = "podman"
}

# Run if an engine is running...
if ($engineRunning -eq 1) {
    & $engineCommand run --detach `
        --publish 8081:8081 `
        --mount type=bind,src=./test_self.key,dst=/run/secrets/self.key `
        --mount type=bind,src=./test_self.crt,dst=/run/secrets/self.crt `
        --mount type=bind,src=./test_ca.crt,dst=/run/secrets/ca.crt `
        --env SERVER_STAGE_COUNT=1 `
        --env SERVER_STAGE_INDEX=1 `
        --env SELF_LISTENING_ADDRESS=0.0.0.0 `
        --env SELF_HEALTHCHECK_ADDRESS=localhost `
        --env SELF_PORT=8081 `
        --env SECRET_KEY_TARGET=/run/secrets/self.key `
        --env SECRET_CERT_TARGET=/run/secrets/self.crt `
        --env SECRET_CA_CERT_TARGET=/run/secrets/ca.crt `
        --env DEST_ADDRESS=localhost `
        --env DEST_PORT=8081 `
        --env THROTTLE_INTERVAL=5 `
        --env UPPER_BOUND=4000000000 `
        --name test-fib-container `
        $fileContent

    for ($i = 5; $i -ge 1; $i--) {
        Write-Host "Waiting $i seconds for container to spin up..."
        Start-Sleep -Seconds 1
    }

    Write-Host "Sending test message to container..."
    curl.exe -k `
        --cert ./test_self.p12 `
        --cacert ./test_ca.p12 `
        --request GET `
        https://localhost:8081/start

    Write-Host "Done. Use your container engine to stop and delete the container whenever you're done."
} else {
    Write-Host "No engine is running. Please start Docker or Podman to run test..."
}
