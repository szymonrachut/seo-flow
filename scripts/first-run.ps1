$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== SEOFlow: first run setup ==" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Utworzono .env z .env.example"
} else {
    Write-Host ".env już istnieje"
}

if (-not (Test-Path ".\frontend\.env.local")) {
    Copy-Item ".\frontend\.env.example" ".\frontend\.env.local"
    Write-Host "Utworzono frontend/.env.local z frontend/.env.example"
} else {
    Write-Host "frontend/.env.local już istnieje"
}

powershell -ExecutionPolicy Bypass -File ".\scripts\dev.ps1" -Command bootstrap

if (-not (Test-Path ".\frontend\node_modules")) {
    Set-Location ".\frontend"
    npm install
    Set-Location $root
} else {
    Write-Host "frontend/node_modules już istnieje, pomijam npm install"
}

Write-Host "First run completed." -ForegroundColor Green