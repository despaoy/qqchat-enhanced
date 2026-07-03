param(
    [int]$Port = 8000,
    [string]$HostName = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Backend = Join-Path $Root "backend"

function Find-Python {
    try {
        & py -3.12 -V *> $null
        if ($LASTEXITCODE -eq 0) { return @{ Command = "py"; Args = @("-3.12") } }
    } catch {}

    try {
        & python -V *> $null
        if ($LASTEXITCODE -eq 0) { return @{ Command = "python"; Args = @() } }
    } catch {}

    throw "Python was not found. Install Python 3.12 or make py/python available in PATH."
}

$env:ENVIRONMENT = "development"
$env:MODEL_PROVIDER = "mock"
$env:VLLM_ENABLED = "false"
$env:VLLM_BASE_URLS = ""
$env:BACKEND_URL = "http://${HostName}:$Port"
if (-not $env:SECURITY_MIDDLEWARE_ENABLED) { $env:SECURITY_MIDDLEWARE_ENABLED = "true" }

$Python = Find-Python
$Args = @($Python.Args) + @("run.py", "--host", $HostName, "--port", "$Port", "--reload", "--workers", "1")

Write-Host "Starting backend in mock mode: $($env:BACKEND_URL)" -ForegroundColor Cyan
Write-Host "vLLM and local large model loading are disabled." -ForegroundColor DarkGray
Push-Location $Backend
try {
    & $Python.Command @Args
} finally {
    Pop-Location
}
