param(
    [switch]$Frontend
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

function Invoke-Step {
    param(
        [string]$Name,
        [string]$WorkDir,
        [string]$Command,
        [string[]]$Arguments = @()
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location $WorkDir
    try {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}

$Python = Find-Python
$PyArgs = @($Python.Args)

$CompileTargets = @(
    "app/main.py",
    "api/generate.py",
    "api/loras.py",
    "api/stats.py",
    "api/integrations.py",
    "bot/async_inference.py",
    "db/database.py",
    "db/pg_database.py",
    "inference/vllm_client.py",
    "inference/model_manager.py",
    "infra/circuit_breaker.py",
    "infra/deployment.py",
    "scripts/local_smoke.py"
)

Invoke-Step "Python syntax check" $Backend $Python.Command ($PyArgs + @("-m", "py_compile") + $CompileTargets)
Invoke-Step "Backend core tests" $Backend $Python.Command ($PyArgs + @("-m", "pytest", "tests/test_core.py", "-q"))
Invoke-Step "API smoke test and mock AstrBot event" $Backend $Python.Command ($PyArgs + @("-m", "scripts.local_smoke"))
Invoke-Step "Git whitespace check" $Root "git" @("diff", "--check")

if ($Frontend) {
    Invoke-Step "Frontend TypeScript check" $Root "pnpm" @("ts-check")
} else {
    Write-Host ""
    Write-Host "Skipped frontend TypeScript check. Run: pnpm verify:local:frontend" -ForegroundColor DarkGray
}

Write-Host ""

$TestTmp = Join-Path $Backend ".test_tmp"
$ResolvedTmp = Resolve-Path -LiteralPath $TestTmp -ErrorAction SilentlyContinue
if ($ResolvedTmp) {
    $BackendResolved = (Resolve-Path -LiteralPath $Backend).Path
    $TmpPath = $ResolvedTmp.Path
    if (-not ($TmpPath.StartsWith($BackendResolved, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "Refusing to remove test temp outside backend: $TmpPath"
    }
    Remove-Item -LiteralPath $TmpPath -Recurse -Force
}

Write-Host "Local baseline verification completed." -ForegroundColor Green
