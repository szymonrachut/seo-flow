$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== SEOFlow: starting local environment ==" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env"
}

if (-not (Test-Path ".\frontend\.env.local")) {
    Copy-Item ".\frontend\.env.example" ".\frontend\.env.local"
    Write-Host "Created frontend/.env.local"
}

function Invoke-DevCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command
    )

    powershell -ExecutionPolicy Bypass -File ".\scripts\dev.ps1" -Command $Command
    if ($LASTEXITCODE -ne 0) {
        throw "dev.ps1 failed for command '$Command'"
    }
}

function Show-DatabaseAuthHint {
    Write-Host ""
    Write-Host "PostgreSQL rejected the credentials from .env." -ForegroundColor Red
    Write-Host "Most likely cause: the Docker volume was initialized earlier with a different password." -ForegroundColor Yellow
    Write-Host "Normal startup keeps a trusted local password in .local/postgres/credentials.env and uses it as the source of truth." -ForegroundColor Yellow
    Write-Host "The stored password changes only when you run db-refresh-lock deliberately; startup may restore PostgreSQL back to that stored value if drift is detected." -ForegroundColor Yellow
    Write-Host "If you do not need existing local data, run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-reset" -ForegroundColor Yellow
    Write-Host "and then run start-local.cmd again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If you need to keep the data, update .env to the real password and run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-refresh-lock" -ForegroundColor Yellow
    Write-Host "Or deliberately align the running PostgreSQL role password to .env:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-align-password" -ForegroundColor Yellow
    Write-Host "Then run start-local.cmd again." -ForegroundColor Yellow
}

try {
    Invoke-DevCommand -Command "db-up"
    Invoke-DevCommand -Command "db-wait"
    Invoke-DevCommand -Command "migrate"
}
catch {
    if (
        $_.Exception.Message -match "password authentication failed for user" -or
        $_.Exception.Message -match "PostgreSQL rejected the configured password"
    ) {
        Show-DatabaseAuthHint
    }
    throw
}

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "Set-Location '$root'; powershell -ExecutionPolicy Bypass -File '.\scripts\dev.ps1' -Command api"
)

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "Set-Location '$root\frontend'; npm run dev"
)

Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"

Write-Host "Project started. Backend and frontend are running in separate windows." -ForegroundColor Green
