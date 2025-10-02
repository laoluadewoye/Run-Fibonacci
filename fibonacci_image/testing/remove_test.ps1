$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

# Check if docker or podman are running
docker info | Out-Null
$dockerRunning = ($LASTEXITCODE -eq 0)
podman info | Out-Null
$podmanRunning = ($LASTEXITCODE -eq 0)

$engineRunning = 0
$engineCommand = ""
if ($dockerRunning) {
    Write-Host "Docker engine is running. Using Docker to remove container..."
    $engineRunning = 1
    $engineCommand = "docker"
} elseif ($podmanRunning) {
    Write-Host "Podman engine is running. Using Podman to remove container..."
    $engineRunning = 1
    $engineCommand = "podman"
}

if ($engineRunning -eq 1) {
    & $engineCommand stop test-fib-container
    & $engineCommand rm test-fib-container
} else {
    Write-Host "No engine is running. Please start Docker or Podman to run removal..."
}

Write-Host "Removing TLS materials..."
Get-ChildItem *.key | foreach { Remove-Item -Path $_.FullName }
Get-ChildItem *.crt | foreach { Remove-Item -Path $_.FullName }
Get-ChildItem *.p12 | foreach { Remove-Item -Path $_.FullName }
