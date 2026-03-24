param(
    [ValidateSet("bootstrap", "playwright-install", "db-up", "db-down", "db-reset", "db-logs", "db-wait", "db-sync-env", "db-refresh-lock", "db-align-password", "migrate", "crawl", "test", "test-quick", "test-backend-full", "test-crawler", "smoke-postgres", "api", "flow")]
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
    $values = Read-EnvFileValues -Path $Path
    foreach ($name in $values.Keys) {
        Set-Item -Path "Env:$name" -Value $values[$name]
    }
}

function Read-EnvFileValues {
    param([string]$Path = ".env")
    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
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
        $values[$name] = $value
    }

    return $values
}

function Get-EnvValueOrDefault {
    param(
        [hashtable]$Values,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$DefaultValue
    )
    if ($null -ne $Values -and $Values.ContainsKey($Name)) {
        $value = [string]$Values[$Name]
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            return $value
        }
    }
    return $DefaultValue
}

function Build-PostgresDatabaseUrl {
    param(
        [Parameter(Mandatory = $true)][string]$User,
        [Parameter(Mandatory = $true)][string]$Password,
        [Parameter(Mandatory = $true)][string]$DbHost,
        [Parameter(Mandatory = $true)][string]$Port,
        [Parameter(Mandatory = $true)][string]$Database
    )
    $encodedUser = [System.Uri]::EscapeDataString($User)
    $encodedPassword = [System.Uri]::EscapeDataString($Password)
    $encodedDatabase = [System.Uri]::EscapeDataString($Database)
    return "postgresql+psycopg://$($encodedUser):$($encodedPassword)@$($DbHost):$($Port)/$($encodedDatabase)"
}

function Get-PostgresCredentialValues {
    param([hashtable]$Values)
    return @{
        "POSTGRES_USER" = Get-EnvValueOrDefault -Values $Values -Name "POSTGRES_USER" -DefaultValue "postgres"
        "POSTGRES_PASSWORD" = Get-EnvValueOrDefault -Values $Values -Name "POSTGRES_PASSWORD" -DefaultValue "postgres"
        "POSTGRES_DB" = Get-EnvValueOrDefault -Values $Values -Name "POSTGRES_DB" -DefaultValue "seo_crawler"
    }
}

function Get-EffectivePostgresEnvValues {
    param(
        [hashtable]$SourceValues,
        [hashtable]$CredentialValues
    )
    $dbHost = Get-EnvValueOrDefault -Values $SourceValues -Name "POSTGRES_HOST" -DefaultValue "localhost"
    $port = Get-EnvValueOrDefault -Values $SourceValues -Name "POSTGRES_PORT" -DefaultValue "5432"
    return @{
        "POSTGRES_USER" = $CredentialValues["POSTGRES_USER"]
        "POSTGRES_PASSWORD" = $CredentialValues["POSTGRES_PASSWORD"]
        "POSTGRES_DB" = $CredentialValues["POSTGRES_DB"]
        "POSTGRES_HOST" = $dbHost
        "POSTGRES_PORT" = $port
        "DATABASE_URL" = Build-PostgresDatabaseUrl `
            -User $CredentialValues["POSTGRES_USER"] `
            -Password $CredentialValues["POSTGRES_PASSWORD"] `
            -DbHost $dbHost `
            -Port $port `
            -Database $CredentialValues["POSTGRES_DB"]
    }
}

function Test-EnvValueSetMatches {
    param(
        [hashtable]$Left,
        [hashtable]$Right,
        [Parameter(Mandatory = $true)][string[]]$Keys
    )
    foreach ($key in $Keys) {
        $leftValue = ""
        $rightValue = ""
        if ($null -ne $Left -and $Left.ContainsKey($key)) {
            $leftValue = [string]$Left[$key]
        }
        if ($null -ne $Right -and $Right.ContainsKey($key)) {
            $rightValue = [string]$Right[$key]
        }
        if ($leftValue -ne $rightValue) {
            return $false
        }
    }
    return $true
}

function Update-EnvFileValues {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][hashtable]$Values,
        [Parameter(Mandatory = $true)][string[]]$Keys
    )
    $originalLines = @()
    if (Test-Path $Path) {
        $originalLines = [string[]](Get-Content $Path)
    }

    $updatedLines = New-Object System.Collections.Generic.List[string]
    foreach ($line in $originalLines) {
        $updatedLines.Add($line)
    }

    $seenKeys = @{}
    for ($index = 0; $index -lt $updatedLines.Count; $index++) {
        $line = $updatedLines[$index]
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }
        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }
        $name = $trimmed.Substring(0, $separatorIndex).Trim()
        if ($Keys -contains $name) {
            $updatedLines[$index] = "$name=$($Values[$name])"
            $seenKeys[$name] = $true
        }
    }

    foreach ($key in $Keys) {
        if (-not $seenKeys.ContainsKey($key)) {
            $updatedLines.Add("$key=$($Values[$key])")
        }
    }

    $originalText = [string]::Join("`n", $originalLines)
    $updatedText = [string]::Join("`n", $updatedLines)
    if ($originalText -eq $updatedText) {
        return $false
    }

    $directory = Split-Path -Parent $Path
    if ($directory -and -not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    Set-Content -Path $Path -Value $updatedLines -Encoding ascii
    return $true
}

function Get-PostgresCredentialLockPath {
    $postgresStateDir = Join-Path ".local" "postgres"
    if (-not (Test-Path $postgresStateDir)) {
        New-Item -ItemType Directory -Path $postgresStateDir -Force | Out-Null
    }
    return Join-Path $postgresStateDir "credentials.env"
}

function Write-PostgresCredentialLock {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][hashtable]$CredentialValues
    )
    $directory = Split-Path -Parent $Path
    if ($directory -and -not (Test-Path $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    $lines = @(
        "# Local PostgreSQL credential lock for the Docker volume.",
        "# Normal startup commands sync .env back to these values.",
        "LOCK_TRUSTED=1",
        "POSTGRES_USER=$($CredentialValues["POSTGRES_USER"])",
        "POSTGRES_PASSWORD=$($CredentialValues["POSTGRES_PASSWORD"])",
        "POSTGRES_DB=$($CredentialValues["POSTGRES_DB"])"
    )
    Set-Content -Path $Path -Value $lines -Encoding ascii
}

function Get-PostgresCredentialLockInfo {
    $path = Get-PostgresCredentialLockPath
    if (-not (Test-Path $path)) {
        return @{
            "Exists" = $false
            "IsTrusted" = $false
            "Path" = $path
            "Values" = @{}
        }
    }

    $values = Read-EnvFileValues -Path $path
    $trustedFlag = Get-EnvValueOrDefault -Values $values -Name "LOCK_TRUSTED" -DefaultValue "0"
    return @{
        "Exists" = $true
        "IsTrusted" = ($trustedFlag -eq "1")
        "Path" = $path
        "Values" = $values
    }
}

function Persist-TrustedPostgresCredentialLockFromEnv {
    param([switch]$Quiet)
    Ensure-EnvFile

    $credentialKeys = @("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB")
    $effectiveEnvKeys = @("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORT", "DATABASE_URL")
    $lockInfo = Get-PostgresCredentialLockInfo
    $envValues = Read-EnvFileValues -Path ".env"
    $currentCredentials = Get-PostgresCredentialValues -Values $envValues
    $effectiveEnvValues = Get-EffectivePostgresEnvValues -SourceValues $envValues -CredentialValues $currentCredentials
    $existingTrustedCredentials = @{}
    if ($lockInfo["IsTrusted"]) {
        $existingTrustedCredentials = Get-PostgresCredentialValues -Values $lockInfo["Values"]
    }
    $credentialsChanged = -not (
        $lockInfo["IsTrusted"] -and (
            Test-EnvValueSetMatches -Left $currentCredentials -Right $existingTrustedCredentials -Keys $credentialKeys
        )
    )

    Update-EnvFileValues -Path ".env" -Values $effectiveEnvValues -Keys $effectiveEnvKeys | Out-Null

    if ($credentialsChanged) {
        Write-PostgresCredentialLock -Path $lockInfo["Path"] -CredentialValues $currentCredentials
        if (-not $Quiet) {
            Write-Host "Locked local PostgreSQL credentials in $($lockInfo["Path"])" -ForegroundColor DarkGray
        }
    }
}

function Sync-EnvFromTrustedPostgresCredentialLock {
    Ensure-EnvFile

    $effectiveEnvKeys = @("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORT", "DATABASE_URL")
    $lockInfo = Get-PostgresCredentialLockInfo
    if (-not $lockInfo["Exists"]) {
        return $false
    }
    if (-not $lockInfo["IsTrusted"]) {
        return $false
    }

    $envValues = Read-EnvFileValues -Path ".env"
    $lockedCredentials = Get-PostgresCredentialValues -Values $lockInfo["Values"]
    $effectiveEnvValues = Get-EffectivePostgresEnvValues -SourceValues $envValues -CredentialValues $lockedCredentials
    $envUpdated = Update-EnvFileValues -Path ".env" -Values $effectiveEnvValues -Keys $effectiveEnvKeys
    if ($envUpdated) {
        Write-Host "Detected PostgreSQL credential drift in .env." -ForegroundColor Yellow
        Write-Host "Re-synced .env from $($lockInfo["Path"]) so the existing Docker volume keeps working." -ForegroundColor Yellow
    }
    return $envUpdated
}

function Test-DatabaseConnectionUrl {
    param(
        [Parameter(Mandatory = $true)][string]$DatabaseUrl,
        [int]$ConnectTimeoutSeconds = 3
    )
    $pythonExe = Get-PythonExe
    $env:POSTGRES_TEST_DATABASE_URL = $DatabaseUrl
    $env:POSTGRES_TEST_CONNECT_TIMEOUT = [string]$ConnectTimeoutSeconds
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @'
import os
import psycopg

database_url = os.environ["POSTGRES_TEST_DATABASE_URL"]
connect_timeout = int(os.environ.get("POSTGRES_TEST_CONNECT_TIMEOUT", "3"))

with psycopg.connect(database_url, connect_timeout=connect_timeout):
    print("postgres-ready")
'@ | & $pythonExe - 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        Remove-Item Env:POSTGRES_TEST_DATABASE_URL -ErrorAction SilentlyContinue
        Remove-Item Env:POSTGRES_TEST_CONNECT_TIMEOUT -ErrorAction SilentlyContinue
    }

    return @{
        "ExitCode" = $exitCode
        "OutputText" = (($output | ForEach-Object { $_.ToString() }) -join "`n").Trim()
    }
}

function Try-RecoverFromLegacyCredentialLock {
    Ensure-EnvFile

    $effectiveEnvKeys = @("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORT", "DATABASE_URL")
    $lockInfo = Get-PostgresCredentialLockInfo
    if (-not $lockInfo["Exists"]) {
        return $false
    }
    if ($lockInfo["IsTrusted"]) {
        return $false
    }

    $envValues = Read-EnvFileValues -Path ".env"
    $legacyCredentials = Get-PostgresCredentialValues -Values $lockInfo["Values"]
    $effectiveEnvValues = Get-EffectivePostgresEnvValues -SourceValues $envValues -CredentialValues $legacyCredentials
    $probeResult = Test-DatabaseConnectionUrl -DatabaseUrl $effectiveEnvValues["DATABASE_URL"]
    if ($probeResult["ExitCode"] -ne 0) {
        return $false
    }

    Update-EnvFileValues -Path ".env" -Values $effectiveEnvValues -Keys $effectiveEnvKeys | Out-Null
    Write-PostgresCredentialLock -Path $lockInfo["Path"] -CredentialValues $legacyCredentials
    Write-Host "Recovered PostgreSQL credentials from legacy lock at $($lockInfo["Path"])." -ForegroundColor Yellow
    return $true
}

function Ensure-PostgresCredentialLock {
    param(
        [switch]$RefreshFromEnv,
        [switch]$PersistIfMissing
    )
    if ($RefreshFromEnv) {
        Persist-TrustedPostgresCredentialLockFromEnv
        Write-Host "Refreshed .local PostgreSQL credential lock from .env." -ForegroundColor Yellow
        Write-Host "db-reset will recreate the volume with these credentials." -ForegroundColor Yellow
        return
    }

    if ($PersistIfMissing) {
        $lockInfo = Get-PostgresCredentialLockInfo
        if (-not $lockInfo["Exists"]) {
            Persist-TrustedPostgresCredentialLockFromEnv
            return
        }
    }

    Sync-EnvFromTrustedPostgresCredentialLock | Out-Null
}

function Get-ComposeDbContainerId {
    Ensure-Docker
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & docker compose ps -q db 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        return $null
    }

    $containerId = (($output | ForEach-Object { $_.ToString() }) -join "`n").Trim()
    if ([string]::IsNullOrWhiteSpace($containerId)) {
        return $null
    }
    return $containerId
}

function Invoke-DbContainerSql {
    param(
        [Parameter(Mandatory = $true)][string]$Sql,
        [string]$Database = "postgres"
    )
    $containerId = Get-ComposeDbContainerId
    if (-not $containerId) {
        return @{
            "ExitCode" = 1
            "OutputText" = "PostgreSQL container is not running."
        }
    }

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = & docker exec -u postgres $containerId psql -v ON_ERROR_STOP=1 -d $Database -c $Sql 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    return @{
        "ExitCode" = $exitCode
        "OutputText" = (($output | ForEach-Object { $_.ToString() }) -join "`n").Trim()
    }
}

function Test-DbContainerLocalAccess {
    $result = Invoke-DbContainerSql -Sql "select 1;" -Database "postgres"
    return $result["ExitCode"] -eq 0
}

function ConvertTo-SqlIdentifier {
    param([Parameter(Mandatory = $true)][string]$Value)
    return '"' + $Value.Replace('"', '""') + '"'
}

function ConvertTo-SqlLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Set-PostgresRolePassword {
    param(
        [Parameter(Mandatory = $true)][string]$User,
        [Parameter(Mandatory = $true)][string]$Password
    )
    if (-not (Test-DbContainerLocalAccess)) {
        throw "Cannot access PostgreSQL locally inside the container, so the postgres role password cannot be updated."
    }

    $sql = "ALTER ROLE $(ConvertTo-SqlIdentifier -Value $User) WITH PASSWORD $(ConvertTo-SqlLiteral -Value $Password);"
    $result = Invoke-DbContainerSql -Sql $sql -Database "postgres"
    if ($result["ExitCode"] -ne 0) {
        if ($result["OutputText"]) {
            Write-Host $result["OutputText"]
        }
        throw "Failed to update the PostgreSQL role password inside the container."
    }
}

function Try-RestoreTrustedPostgresPassword {
    Ensure-Docker
    Ensure-EnvFile

    $lockInfo = Get-PostgresCredentialLockInfo
    if (-not $lockInfo["IsTrusted"]) {
        return $false
    }
    if (-not (Test-DbContainerLocalAccess)) {
        return $false
    }

    $envValues = Read-EnvFileValues -Path ".env"
    $trustedCredentials = Get-PostgresCredentialValues -Values $lockInfo["Values"]
    $effectiveEnvValues = Get-EffectivePostgresEnvValues -SourceValues $envValues -CredentialValues $trustedCredentials
    Update-EnvFileValues -Path ".env" -Values $effectiveEnvValues -Keys @("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST", "POSTGRES_PORT", "DATABASE_URL") | Out-Null
    Import-EnvFile
    Set-PostgresRolePassword -User $trustedCredentials["POSTGRES_USER"] -Password $trustedCredentials["POSTGRES_PASSWORD"]
    Persist-TrustedPostgresCredentialLockFromEnv -Quiet
    Write-Host "Detected PostgreSQL password drift. Restored the trusted local password from $($lockInfo["Path"])." -ForegroundColor Yellow
    return $true
}

function Align-PostgresPasswordToEnv {
    Ensure-Docker
    Ensure-EnvFile
    Ensure-PostgresCredentialLock
    Import-EnvFile

    Db-Up

    $targetUser = [string]$env:POSTGRES_USER
    $targetPassword = [string]$env:POSTGRES_PASSWORD
    Set-PostgresRolePassword -User $targetUser -Password $targetPassword

    Persist-TrustedPostgresCredentialLockFromEnv
    Import-EnvFile
    Wait-ForPostgres
    Write-Host "Aligned PostgreSQL role password inside the container to the credentials from .env." -ForegroundColor Green
}

function Get-DatabaseAuthDiagnostics {
    $lockInfo = Get-PostgresCredentialLockInfo
    return @{
        "HasTrustedLock" = [bool]$lockInfo["IsTrusted"]
        "HasLegacyLock" = [bool]($lockInfo["Exists"] -and -not $lockInfo["IsTrusted"])
        "LockPath" = [string]$lockInfo["Path"]
        "ContainerLocalAccess" = [bool](Test-DbContainerLocalAccess)
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
    $diagnostics = Get-DatabaseAuthDiagnostics
    Write-Host ""
    Write-Host "PostgreSQL rejected the credentials from .env / DATABASE_URL." -ForegroundColor Red
    Write-Host "Most likely cause: the Docker volume was initialized earlier with a different password." -ForegroundColor Yellow
    Write-Host "This repo does not rotate the postgres role password during tests, migrations or startup." -ForegroundColor Yellow
    if ($diagnostics["HasLegacyLock"]) {
        Write-Host "A legacy credential lock exists at $($diagnostics["LockPath"]) but it could not be verified against the running DB." -ForegroundColor Yellow
    }
    Write-Host "" 
    Write-Host "If you do not need the current local DB data, run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-reset" -ForegroundColor Yellow
    Write-Host "Then run migrate (or your normal startup flow) again." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "If you need to keep the data, do not reset the volume." -ForegroundColor Yellow
    Write-Host "If you already know the real password, update .env and run:" -ForegroundColor Yellow
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-refresh-lock" -ForegroundColor Yellow
    if ($diagnostics["ContainerLocalAccess"]) {
        Write-Host "" 
        Write-Host "If you want to keep the data and deliberately align PostgreSQL to the password from .env, run:" -ForegroundColor Yellow
        Write-Host "  powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -Command db-align-password" -ForegroundColor Yellow
    }
    Write-Host "Retry your original command afterwards." -ForegroundColor Yellow
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
    if ($exitCode -ne 0) {
        $outputText = ($output | ForEach-Object { $_.ToString() }) -join "`n"
        if (Test-DatabaseAuthFailureText -Text $outputText) {
            if (Try-RecoverFromLegacyCredentialLock) {
                Import-EnvFile
                Wait-ForPostgres -TimeoutSeconds $TimeoutSeconds
                return
            }
            if (Try-RestoreTrustedPostgresPassword) {
                Wait-ForPostgres -TimeoutSeconds $TimeoutSeconds
                return
            }
            Show-DatabaseAuthHint
        }
        if ($output) {
            $output | ForEach-Object { Write-Host $_.ToString() }
        }
        throw "PostgreSQL health check failed."
    }
    if ($output) {
        $output | ForEach-Object { Write-Host $_.ToString() }
    }
    Persist-TrustedPostgresCredentialLockFromEnv -Quiet
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
    Ensure-PostgresCredentialLock
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
    Ensure-PostgresCredentialLock -RefreshFromEnv
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
    Ensure-PostgresCredentialLock
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
    Ensure-PostgresCredentialLock
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

function Test-Quick {
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @(
        "-m", "pytest",
        "-q",
        "-m", "not slow and not integration and not e2e and not postgres_smoke"
    )
}

function Test-Backend-Full {
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @(
        "-m", "pytest",
        "-q",
        "--durations=20",
        "-m", "not postgres_smoke"
    )
}

function Test-Crawler {
    $pythonExe = Get-PythonExe
    $crawlerTests = @(
        "tests/test_api_stage5.py",
        "tests/test_links_extraction.py",
        "tests/test_meta_extraction_stage2.py",
        "tests/test_pipeline_and_stats.py",
        "tests/test_rendering_stage5.py",
        "tests/test_url_normalization.py"
    )
    Invoke-Checked -Exe $pythonExe -Args (@("-m", "pytest", "-q", "--durations=10") + $crawlerTests)
}

function Test-All {
    Test-Backend-Full
}

function Smoke-Postgres {
    Db-Up
    Wait-ForPostgres
    Migrate
    Ensure-EnvFile
    Ensure-PostgresCredentialLock
    Import-EnvFile
    if (-not $env:POSTGRES_SMOKE_DATABASE_URL) {
        $env:POSTGRES_SMOKE_DATABASE_URL = $env:DATABASE_URL
    }
    $env:RUN_POSTGRES_SMOKE = "1"
    $pythonExe = Get-PythonExe
    Invoke-Checked -Exe $pythonExe -Args @("-m", "pytest", "-m", "postgres_smoke", "-q")
}

function Api {
    Ensure-EnvFile
    Ensure-PostgresCredentialLock
    Import-EnvFile
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
        Ensure-PostgresCredentialLock
        Import-EnvFile
        Wait-ForPostgres
    }
    "db-sync-env" {
        if (-not (Sync-EnvFromTrustedPostgresCredentialLock)) {
            Write-Host "No trusted PostgreSQL credential lock was found. Run db-refresh-lock after verifying .env, or let db-wait create the lock after a successful connection." -ForegroundColor Yellow
        }
        Import-EnvFile
    }
    "db-refresh-lock" {
        Persist-TrustedPostgresCredentialLockFromEnv
        Import-EnvFile
    }
    "db-align-password" { Align-PostgresPasswordToEnv }
    "migrate" { Migrate }
    "crawl" { Crawl }
    "test" { Test-All }
    "test-quick" { Test-Quick }
    "test-backend-full" { Test-Backend-Full }
    "test-crawler" { Test-Crawler }
    "smoke-postgres" { Smoke-Postgres }
    "api" { Api }
    "flow" { Flow }
}
