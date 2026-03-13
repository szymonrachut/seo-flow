param(
    [ValidateSet("bootstrap", "db-up", "db-down", "db-logs", "migrate", "crawl", "test", "smoke-postgres", "api", "flow")]
    [string]$Command = "flow",
    [string]$StartUrl = "https://example.com",
    [int]$MaxUrls = 300,
    [int]$MaxDepth = 4,
    [double]$Delay = 0.5
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

function Wait-ForPostgres {
    param([int]$TimeoutSeconds = 90)
    $pythonExe = Get-PythonExe
    $env:POSTGRES_WAIT_TIMEOUT = [string]$TimeoutSeconds
    @'
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
    except Exception:
        if time.time() >= deadline:
            raise
        time.sleep(1)
'@ | & $pythonExe -
    if ($LASTEXITCODE -ne 0) {
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

function Db-Logs {
    Ensure-Docker
    Invoke-Checked -Exe "docker" -Args @("compose", "logs", "-f", "db")
}

function Migrate {
    Ensure-EnvFile
    Import-EnvFile
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @("-m", "alembic", "upgrade", "head")
}

function Crawl {
    Ensure-EnvFile
    Import-EnvFile
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @(
        "-m", "app.cli.run_crawl", $StartUrl,
        "--max-urls", "$MaxUrls",
        "--max-depth", "$MaxDepth",
        "--delay", "$Delay"
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
    "db-up" { Db-Up }
    "db-down" { Db-Down }
    "db-logs" { Db-Logs }
    "migrate" { Migrate }
    "crawl" { Crawl }
    "test" { Test-All }
    "smoke-postgres" { Smoke-Postgres }
    "api" { Api }
    "flow" { Flow }
}
