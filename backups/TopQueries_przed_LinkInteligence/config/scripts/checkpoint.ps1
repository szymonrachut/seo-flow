[CmdletBinding()]
param(
    [string]$Name = $(Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'),
    [string]$DbContainer = 'seo-crawler-db',
    [string]$DbName = 'seo_crawler',
    [string]$DbUser = 'postgres',
    [switch]$Zip,
    [switch]$NoGit,
    [switch]$NoDb
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Copy-IfExists {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (Test-Path -LiteralPath $Source) {
        $parent = Split-Path -Parent $Destination
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
    }
}

function Test-CommandExists {
    param([Parameter(Mandatory = $true)][string]$Command)
    return $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}


function Get-RelativeUnixPath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Path
    )

    $rootUri = [System.Uri]((Resolve-Path -LiteralPath $Root).Path.TrimEnd('\') + '\')
    $pathUri = [System.Uri]((Resolve-Path -LiteralPath $Path).Path)
    return [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString())
}

function New-RepoZip {
    param(
        [Parameter(Mandatory = $true)][string]$SourceRoot,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }

    $excludeDirs = @(
        '.git',
        '.venv',
        'node_modules',
        '__pycache__',
        '.pytest_cache',
        '.mypy_cache',
        '.ruff_cache',
        'dist',
        'build',
        'coverage',
        'htmlcov',
        'backups'
    )

    $excludeFiles = @(
        '*.pyc', '*.pyo', '*.log', '*.sqlite', '*.db', '*.tmp', '*.cache'
    )

    $sourceRootResolved = (Resolve-Path -LiteralPath $SourceRoot).Path

    $files = Get-ChildItem -LiteralPath $sourceRootResolved -Recurse -File -Force | Where-Object {
        $fullName = $_.FullName
        $relative = Get-RelativeUnixPath -Root $sourceRootResolved -Path $fullName

        foreach ($dir in $excludeDirs) {
            if ($relative -like "$dir/*" -or $relative -like "$dir\\*" -or $relative -eq $dir) {
                return $false
            }
        }

        foreach ($pattern in $excludeFiles) {
            if ($_.Name -like $pattern) {
                return $false
            }
        }

        return $true
    }

    $zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in $files) {
            $relative = Get-RelativeUnixPath -Root $sourceRootResolved -Path $file.FullName
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $relative, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
        }
    }
    finally {
        $zip.Dispose()
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRootCandidate = Resolve-Path -LiteralPath (Join-Path $scriptDir '..') -ErrorAction SilentlyContinue
$repoRoot = if ($repoRootCandidate -and (Test-Path -LiteralPath (Join-Path $repoRootCandidate '.git'))) {
    $repoRootCandidate.Path
} else {
    (Get-Location).Path
}

Set-Location -LiteralPath $repoRoot

$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$checkpointName = ($Name -replace '[^a-zA-Z0-9._-]', '_').Trim('_')
if ([string]::IsNullOrWhiteSpace($checkpointName)) {
    $checkpointName = $timestamp
}

$backupRoot = Join-Path $repoRoot 'backups'
$checkpointRoot = Join-Path $backupRoot $checkpointName
$dbRoot = Join-Path $checkpointRoot 'db'
$configRoot = Join-Path $checkpointRoot 'config'
$repoBackupRoot = Join-Path $checkpointRoot 'repo'

New-Item -ItemType Directory -Path $dbRoot -Force | Out-Null
New-Item -ItemType Directory -Path $configRoot -Force | Out-Null
New-Item -ItemType Directory -Path $repoBackupRoot -Force | Out-Null

$gitCommitHash = ''
$gitTagName = ''
$gitBranch = ''

if (-not $NoGit) {
    if (Test-CommandExists -Command 'git') {
        try {
            $gitTopLevel = (& git rev-parse --show-toplevel 2>$null).Trim()
            if ($LASTEXITCODE -eq 0 -and $gitTopLevel) {
                Set-Location -LiteralPath $gitTopLevel
                $repoRoot = $gitTopLevel
                $gitBranch = (& git branch --show-current 2>$null).Trim()

                Write-Step "Git checkpoint for $checkpointName"
                $statusOutput = (& git status --porcelain=v1 2>$null)
                if ($LASTEXITCODE -eq 0 -and $statusOutput) {
                    & git add -A
                    & git commit -m "Checkpoint: $checkpointName"
                } else {
                    Write-Host 'Brak zmian do commita. Pomijam commit.' -ForegroundColor Yellow
                }

                $existingTag = (& git rev-parse -q --verify "refs/tags/$checkpointName" 2>$null)
                if ($LASTEXITCODE -eq 0 -and $existingTag) {
                    $gitTagName = "$checkpointName-$timestamp"
                } else {
                    $gitTagName = $checkpointName
                }

                & git tag $gitTagName
                $gitCommitHash = (& git rev-parse HEAD 2>$null).Trim()
                Write-Host "Utworzono tag: $gitTagName" -ForegroundColor Green
            } else {
                Write-Host 'Nie wykryto repo Git. Pomijam commit i tag.' -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "Git checkpoint nie powiódł się: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host 'Git nie jest dostępny w PATH. Pomijam commit i tag.' -ForegroundColor Yellow
    }
}

# Paths may have changed after resolving real git root.
$backupRoot = Join-Path $repoRoot 'backups'
$checkpointRoot = Join-Path $backupRoot $checkpointName
$dbRoot = Join-Path $checkpointRoot 'db'
$configRoot = Join-Path $checkpointRoot 'config'
$repoBackupRoot = Join-Path $checkpointRoot 'repo'
New-Item -ItemType Directory -Path $dbRoot -Force | Out-Null
New-Item -ItemType Directory -Path $configRoot -Force | Out-Null
New-Item -ItemType Directory -Path $repoBackupRoot -Force | Out-Null

if (-not $NoDb) {
    if (Test-CommandExists -Command 'docker') {
        try {
            $containerExists = (& docker ps -a --format '{{.Names}}' | Where-Object { $_ -eq $DbContainer })
            if ($containerExists) {
                Write-Step "Dump bazy danych z kontenera $DbContainer"
                $dbDumpFile = Join-Path $dbRoot ("{0}_{1}.sql" -f $DbName, $checkpointName)
                & docker exec $DbContainer pg_dump -U $DbUser -d $DbName | Out-File -FilePath $dbDumpFile -Encoding utf8
                if ($LASTEXITCODE -ne 0) {
                    throw "pg_dump zwrócił kod $LASTEXITCODE"
                }

                $globalsDumpFile = Join-Path $dbRoot ("globals_{0}.sql" -f $checkpointName)
                & docker exec $DbContainer pg_dumpall -U $DbUser --globals-only | Out-File -FilePath $globalsDumpFile -Encoding utf8
                if ($LASTEXITCODE -ne 0) {
                    throw "pg_dumpall zwrócił kod $LASTEXITCODE"
                }

                Write-Host "Zapisano dump bazy: $dbDumpFile" -ForegroundColor Green
            } else {
                Write-Host "Nie znaleziono kontenera Docker: $DbContainer. Pomijam dump DB." -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "Backup bazy nie powiódł się: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host 'Docker nie jest dostępny w PATH. Pomijam dump DB.' -ForegroundColor Yellow
    }
}

Write-Step 'Kopia plików konfiguracyjnych'
Copy-IfExists -Source (Join-Path $repoRoot '.env') -Destination (Join-Path $configRoot '.env')
Copy-IfExists -Source (Join-Path $repoRoot '.env.example') -Destination (Join-Path $configRoot '.env.example')
Copy-IfExists -Source (Join-Path $repoRoot 'docker-compose.yml') -Destination (Join-Path $configRoot 'docker-compose.yml')
Copy-IfExists -Source (Join-Path $repoRoot 'docker-compose.yaml') -Destination (Join-Path $configRoot 'docker-compose.yaml')
Copy-IfExists -Source (Join-Path $repoRoot 'compose.yml') -Destination (Join-Path $configRoot 'compose.yml')
Copy-IfExists -Source (Join-Path $repoRoot 'alembic.ini') -Destination (Join-Path $configRoot 'alembic.ini')
Copy-IfExists -Source (Join-Path $repoRoot 'pyproject.toml') -Destination (Join-Path $configRoot 'pyproject.toml')
Copy-IfExists -Source (Join-Path $repoRoot 'package.json') -Destination (Join-Path $configRoot 'package.json')
Copy-IfExists -Source (Join-Path $repoRoot 'package-lock.json') -Destination (Join-Path $configRoot 'package-lock.json')
Copy-IfExists -Source (Join-Path $repoRoot 'frontend/.env') -Destination (Join-Path $configRoot 'frontend/.env')
Copy-IfExists -Source (Join-Path $repoRoot 'frontend/.env.example') -Destination (Join-Path $configRoot 'frontend/.env.example')
Copy-IfExists -Source (Join-Path $repoRoot 'scripts') -Destination (Join-Path $configRoot 'scripts')

if ($Zip) {
    try {
        Write-Step 'Tworzenie ZIP repozytorium'
        $zipPath = Join-Path $repoBackupRoot ("repo_{0}.zip" -f $checkpointName)
        New-RepoZip -SourceRoot $repoRoot -ZipPath $zipPath
        Write-Host "Zapisano ZIP repo: $zipPath" -ForegroundColor Green
    }
    catch {
        Write-Host "Tworzenie ZIP nie powiodło się: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

$manifestPath = Join-Path $checkpointRoot 'manifest.txt'
$manifest = @(
    "checkpoint_name=$checkpointName",
    "timestamp=$timestamp",
    "repo_root=$repoRoot",
    "git_branch=$gitBranch",
    "git_commit=$gitCommitHash",
    "git_tag=$gitTagName",
    "db_container=$DbContainer",
    "db_name=$DbName",
    "db_user=$DbUser",
    "zip_enabled=$($Zip.IsPresent)",
    "backup_root=$checkpointRoot"
)
$manifest | Set-Content -Path $manifestPath -Encoding utf8

Write-Host ''
Write-Host 'Gotowe.' -ForegroundColor Green
Write-Host "Checkpoint: $checkpointName"
Write-Host "Folder backupu: $checkpointRoot"
