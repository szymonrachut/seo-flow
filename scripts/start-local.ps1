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

function Read-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$DefaultValue = ""
    )
    if (-not (Test-Path $Path)) {
        return $DefaultValue
    }
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }
        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }
        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        if ($key -eq $Name) {
            return $trimmed.Substring($separatorIndex + 1)
        }
    }
    return $DefaultValue
}

function Ensure-FrontendDependencies {
    $frontendNodeModulesPath = Join-Path $root "frontend\node_modules"
    if (Test-Path $frontendNodeModulesPath) {
        return
    }

    Write-Host "frontend/node_modules is missing. Running npm install before startup..." -ForegroundColor Yellow
    Push-Location ".\frontend"
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed."
        }
    }
    finally {
        Pop-Location
    }
}

function Wait-ForHttpEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Label,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
            return $true
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    Write-Host "$Label did not become ready at $Url within $TimeoutSeconds seconds." -ForegroundColor Yellow
    return $false
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

$frontendUrl = Read-EnvValue -Path ".env" -Name "FRONTEND_APP_URL" -DefaultValue "http://127.0.0.1:5173"
$apiPort = Read-EnvValue -Path ".env" -Name "API_PORT" -DefaultValue "8000"
$apiHealthUrl = "http://127.0.0.1:$apiPort/health"

Ensure-FrontendDependencies

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "Set-Location '$root'; powershell -ExecutionPolicy Bypass -File '.\scripts\dev.ps1' -Command api"
)

Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-Command", "& {
        Set-Location '$root\frontend'
        `$frontendUrl = '$([string](Read-EnvValue -Path '.env' -Name 'FRONTEND_APP_URL' -DefaultValue 'http://127.0.0.1:5173'))'
        if (`$frontendUrl -match ':(\d+)$') {
            npm run dev -- --host=127.0.0.1 --port=`$Matches[1] --strictPort
        }
        else {
            npm run dev
        }
    }"
)

$frontendApiUrl = Read-EnvValue -Path ".\frontend\.env.local" -Name "VITE_API_BASE_URL"
if ($frontendApiUrl -match "http://127\.0\.0\.1:(\d+)") {
    $apiPort = $Matches[1]
    Write-Host "Frontend is configured to use API port $apiPort" -ForegroundColor DarkGray
    $apiHealthUrl = "http://127.0.0.1:$apiPort/health"
}

$apiReady = Wait-ForHttpEndpoint -Url $apiHealthUrl -Label "API"
$frontendReady = Wait-ForHttpEndpoint -Url $frontendUrl -Label "Frontend" -TimeoutSeconds 60

if ($frontendReady) {
    Start-Process $frontendUrl
}
else {
    Write-Host "Skipping browser auto-open because the frontend is still unavailable. Check the frontend PowerShell window for npm/Vite errors." -ForegroundColor Yellow
}

if ($apiReady -and $frontendReady) {
    Write-Host "Project started. Backend and frontend are running in separate windows." -ForegroundColor Green
}
else {
    Write-Host "Startup finished with warnings. Backend and frontend windows are open; check the warnings above if the app is still unavailable." -ForegroundColor Yellow
}
