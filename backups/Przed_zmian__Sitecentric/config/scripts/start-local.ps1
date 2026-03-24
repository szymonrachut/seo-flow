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
}

function Show-DatabaseAuthHint {
    Write-Host ""
    Write-Host "PostgreSQL rejected the credentials from .env." -ForegroundColor Red
    Write-Host "Most likely cause: the Docker volume was initialized earlier with a different password." -ForegroundColor Yellow
    Write-Host "If you do not need existing local data, run:" -ForegroundColor Yellow
    Write-Host "  docker compose down -v" -ForegroundColor Yellow
    Write-Host "and then run start-local.cmd again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If you need to keep the data, update DATABASE_URL to the real password" -ForegroundColor Yellow
    Write-Host "or change the postgres role password inside the container." -ForegroundColor Yellow
}

Invoke-DevCommand -Command "db-up"
Invoke-DevCommand -Command "db-wait"

try {
    Invoke-DevCommand -Command "migrate"
}
catch {
    if ($_.Exception.Message -match "password authentication failed for user") {
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
