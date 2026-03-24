param(
    [ValidateSet("bootstrap", "playwright-install", "db-up", "db-down", "db-reset", "db-logs", "db-wait", "migrate", "crawl", "test", "smoke-postgres", "api", "flow")]
    [string]$Command = "flow",
    [string]$StartUrl = "https://example.com",
    [int]$MaxUrls = 300,
    [int]$MaxDepth = 4,
    [double]$Delay = 0.5,
    [ValidateSet("never", "auto", "always")]
    [string]$RenderMode = "auto",
    [int]$RenderTimeoutMs = 8000,
    [int]$MaxRenderedPages = 25
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PythonExe {
    $venvPython = Join-Path ".venv" "Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    return "python"
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Exe,
        [Parameter(Mandatory = $true)][string[]]$Args
    )
    & $Exe @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Exe $($Args -join ' ')"
    }
}

function Import-EnvFile {
    param([string]$Path = ".env")
    if (-not (Test-Path $Path)) {
        return
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed)) {
            continue
        }
        if ($trimmed.StartsWith("#")) {
            continue
        }
        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }
        $name = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1)
        Set-Item -Path "Env:$name" -Value $value
    }
}

function Ensure-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker is not available in PATH."
    }
}

function Ensure-EnvFile {
    if (-not (Test-Path ".env")) {
        if (-not (Test-Path ".env.example")) {
            throw ".env and .env.example are both missing."
        }
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example"
    }
}

function Show-DatabaseAuthHint {
    Write-Host ""
    Write-Host "PostgreSQL rejected the credentials from .env / DATABASE_URL." -ForegroundColor Red
    Write-Host "Most likely cause: the Docker volume was initialized earlier with a different password." -ForegroundColor Yellow
    Write-Host "This repo does not rotate the postgres role password during tests, migrations or startup." -ForegroundColor Yellow
    Write-Host "" 
    Write-Host "If you do not need the current local DB data, run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-reset" -ForegroundColor Yellow
    Write-Host "Then run migrate (or your normal startup flow) again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If you need to keep the data, do not reset the volume." -ForegroundColor Yellow
    Write-Host "Instead align .env / DATABASE_URL with the real password already stored in PostgreSQL" -ForegroundColor Yellow
    Write-Host "or change the postgres role password inside the container deliberately." -ForegroundColor Yellow
    Write-Host ""
}

function Test-DatabaseAuthFailureText {
    param([string]$Text)
    return $Text -match "password authentication failed for user" -or
        $Text -match "PostgreSQL rejected the configured password"
}

function Wait-ForPostgres {
    param([int]$TimeoutSeconds = 90)
    $pythonExe = Get-PythonExe
    $env:POSTGRES_WAIT_TIMEOUT = [string]$TimeoutSeconds
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @'
import os
import time
import psycopg
from sqlalchemy.engine import make_url

database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise SystemExit("DATABASE_URL is not set")

sa_url = make_url(database_url)
psycopg_url = sa_url.set(drivername="postgresql").render_as_string(hide_password=False)

deadline = time.time() + int(os.environ.get("POSTGRES_WAIT_TIMEOUT", "90"))
while True:
    try:
        with psycopg.connect(psycopg_url, connect_timeout=3):
            print("postgres-ready")
            break
    except Exception as exc:
        message = str(exc).lower()
        if "password authentication failed" in message:
            raise SystemExit(
                "PostgreSQL rejected the configured password. "
                "This usually means the Docker volume was initialized earlier with a different password."
            ) from exc
        if time.time() >= deadline:
            raise
        time.sleep(1)
'@ | & $pythonExe - 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($output) {
        $output | ForEach-Object { Write-Host $_.ToString() }
    }
    if ($exitCode -ne 0) {
        $outputText = ($output | ForEach-Object { $_.ToString() }) -join "`n"
        if (Test-DatabaseAuthFailureText -Text $outputText) {
            Show-DatabaseAuthHint
        }
        throw "PostgreSQL health check failed."
    }
}

function Bootstrap {
    Ensure-EnvFile
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Invoke-Checked -Exe "python" -Args @("-m", "venv", ".venv")
    }
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-Checked -Exe $pythonExe -Args @("-m", "pip", "install", "-e", ".[dev]")
}

function Playwright-Install {
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @("-m", "playwright", "install", "chromium")
}

function Db-Up {
    Ensure-Docker
    Ensure-EnvFile
    Import-EnvFile
    Invoke-Checked -Exe "docker" -Args @("compose", "up", "-d", "db")
}

function Db-Down {
    Ensure-Docker
    Invoke-Checked -Exe "docker" -Args @("compose", "down")
}

function Db-Reset {
    Ensure-Docker
    Ensure-EnvFile
    Import-EnvFile
    Write-Host "Resetting the local PostgreSQL Docker volume. This removes local DB data." -ForegroundColor Yellow
    Invoke-Checked -Exe "docker" -Args @("compose", "down", "-v", "--remove-orphans")
    Invoke-Checked -Exe "docker" -Args @("compose", "up", "-d", "db")
    Wait-ForPostgres
    Write-Host "PostgreSQL volume recreated. Run migrate next." -ForegroundColor Green
}

function Db-Logs {
    Ensure-Docker
    Invoke-Checked -Exe "docker" -Args @("compose", "logs", "-f", "db")
}

function Migrate {
    Ensure-EnvFile
    Import-EnvFile
    $pythonExe = Get-PythonExe
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & $pythonExe -m alembic upgrade head 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($output) {
        $output | ForEach-Object { Write-Host $_.ToString() }
    }
    if ($exitCode -ne 0) {
        $outputText = ($output | ForEach-Object { $_.ToString() }) -join "`n"
        if (Test-DatabaseAuthFailureText -Text $outputText) {
            Show-DatabaseAuthHint
        }
        throw "Command failed: $pythonExe -m alembic upgrade head"
    }
}

function Crawl {
    Ensure-EnvFile
    Import-EnvFile
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @(
        "-m", "app.cli.run_crawl", $StartUrl,
        "--max-urls", "$MaxUrls",
        "--max-depth", "$MaxDepth",
        "--delay", "$Delay",
        "--render-mode", "$RenderMode",
        "--render-timeout-ms", "$RenderTimeoutMs",
        "--max-rendered-pages", "$MaxRenderedPages"
    )
}

function Test-All {
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @("-m", "pytest")
}

function Smoke-Postgres {
    Db-Up
    Wait-ForPostgres
    Migrate
    Ensure-EnvFile
    Import-EnvFile
    if (-not $env:POSTGRES_SMOKE_DATABASE_URL) {
        $env:POSTGRES_SMOKE_DATABASE_URL = $env:DATABASE_URL
    }
    $env:RUN_POSTGRES_SMOKE = "1"
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @("-m", "pytest", "-m", "postgres_smoke", "-q")
}

function Api {
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @("-m", "uvicorn", "app.api.main:app", "--reload")
}

function Flow {
    Bootstrap
    Db-Up
    Wait-ForPostgres
    Migrate
    Crawl
    Test-All
}

switch ($Command) {
    "bootstrap" { Bootstrap }
    "playwright-install" { Playwright-Install }
    "db-up" { Db-Up }
    "db-down" { Db-Down }
    "db-reset" { Db-Reset }
    "db-logs" { Db-Logs }
    "db-wait" {
        Ensure-EnvFile
        Import-EnvFile
        Wait-ForPostgres
    }
    "migrate" { Migrate }
    "crawl" { Crawl }
    "test" { Test-All }
    "smoke-postgres" { Smoke-Postgres }
    "api" { Api }
    "flow" { Flow }
}
