$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "== SEOFlow: starting local environment ==" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Utworzono .env"
}

if (-not (Test-Path ".\frontend\.env.local")) {
    Copy-Item ".\frontend\.env.example" ".\frontend\.env.local"
    Write-Host "Utworzono frontend/.env.local"
}

# 1. Baza
powershell -ExecutionPolicy Bypass -File ".\scripts\dev.ps1" -Command db-up

# 2. Krótkie czekanie aż kontener bazy wstanie
Start-Sleep -Seconds 5

# 3. Migracje
powershell -ExecutionPolicy Bypass -File ".\scripts\dev.ps1" -Command migrate

# 4. API w osobnym oknie
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "Set-Location '$root'; powershell -ExecutionPolicy Bypass -File '.\scripts\dev.ps1' -Command api"
)

# 5. Frontend w osobnym oknie
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "Set-Location '$root\frontend'; npm run dev"
)

# 6. Opcjonalnie otwarcie przeglądarki
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"

Write-Host "Projekt uruchomiony. Backend i frontend startują w osobnych oknach." -ForegroundColor Green