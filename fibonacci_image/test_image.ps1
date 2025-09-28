py -3.13 TestGenTLS.py

$fileContent = Get-Content "./latest_image.txt"
Write-Output $fileContent

docker run --detach `
    --publish 8081:8081 `
    --mount type=bind,src=./test_self.key,dst=/run/secrets/self.key `
    --mount type=bind,src=./test_self.crt,dst=/run/secrets/self.crt `
    --mount type=bind,src=./test_ca.crt,dst=/run/secrets/ca.crt `
    --env SERVER_STAGE_COUNT=2 `
    --env SERVER_STAGE_INDEX=1 `
    --env SELF_ADDRESS=0.0.0.0 `
    --env SELF_PORT=8081 `
    --env SECRET_KEY_TARGET=/run/secrets/self.key `
    --env SECRET_CERT_TARGET=/run/secrets/self.crt `
    --env SECRET_CA_CERT_TARGET=/run/secrets/ca.crt `
    --env DEST_ADDRESS=0.0.0.0 `
    --env DEST_PORT=8081 `
    --env THROTTLE_INTERVAL=5 `
    --env UPPER_BOUND=4000000000 `
    --name test_fib_container `
    $fileContent

Start-Sleep -Seconds 5

curl.exe `
    --cert ./test_self.crt `
    --key ./test_self.key `
    --cacert ./test_ca.crt `
    --request GET `
    https://localhost:8081/start

# curl --cert ./test_self.crt --key ./test_self.key --cacert ./test_ca.crt --request GET https://localhost:8081/start
