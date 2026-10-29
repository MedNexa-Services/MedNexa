# MedNexa database backup for Windows (Part 5, task 5.12). Same behaviour as backup.sh:
# the dump is made inside the database container, checked, and only then moved into
# place; retention runs only after a good backup.
#
#   .\scripts\backup.ps1                      # backup into .\backups
#   .\scripts\backup.ps1 -BackupDir D:\backups
#
# Backups contain patient data: keep the folder readable by administrators only
# (icacls <folder> /inheritance:r /grant:r "$env:USERNAME:(OI)(CI)F") and encrypt copies
# before they leave the machine.
param (
    [string]$BackupDir = ".\backups",
    [string]$ContainerName = $(if ($env:DB_CONTAINER) { $env:DB_CONTAINER } else { "mednexa-db" }),
    [string]$DbUser = $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "mednexa" }),
    [string]$DbName = $(if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "mednexa" }),
    [int]$RetentionDays = 7
)

$ErrorActionPreference = "Stop"

function Assert-Success([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

$running = docker inspect -f '{{.State.Running}}' $ContainerName 2>$null
if ($running -ne "true") {
    throw "Container '$ContainerName' is not running (set -ContainerName or `$env:DB_CONTAINER)."
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Final = Join-Path $BackupDir "mednexa_backup_$Timestamp.sql.gz"
$Partial = "$Final.partial"
$RemoteSql = "/tmp/mednexa_backup_$Timestamp.sql"
$RemoteGz = "$RemoteSql.gz"

Write-Host "[INFO] Backing up database '$DbName' from container '$ContainerName'..." -ForegroundColor Cyan
try {
    # One shell script, run inside the container: no PowerShell pipeline touches the data
    # (PowerShell re-encodes piped text and would corrupt non-ASCII patient names).
    $script = "set -e; pg_dump -U '$DbUser' --clean --if-exists --no-owner --no-acl '$DbName' > '$RemoteSql'; gzip -f '$RemoteSql'; gzip -t '$RemoteGz'; gunzip -c '$RemoteGz' | tail -n 5 | grep -q 'PostgreSQL database dump complete'"
    docker exec $ContainerName sh -c $script
    Assert-Success "pg_dump"

    docker cp "${ContainerName}:$RemoteGz" $Partial
    Assert-Success "docker cp"
    if ((Get-Item $Partial).Length -eq 0) { throw "The backup file is empty." }
    Move-Item -Force $Partial $Final
}
finally {
    docker exec $ContainerName rm -f $RemoteSql $RemoteGz *> $null
    if (Test-Path $Partial) { Remove-Item -Force $Partial }
}

$SizeMb = (Get-Item $Final).Length / 1MB
Write-Host ("[SUCCESS] {0} ({1:N2} MB)" -f $Final, $SizeMb) -ForegroundColor Green

Write-Host "[INFO] Removing backups older than $RetentionDays days..." -ForegroundColor Cyan
$Cutoff = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -Filter "mednexa_backup_*.sql.gz" |
    Where-Object { $_.LastWriteTime -lt $Cutoff } |
    Remove-Item -Force
Write-Host "[INFO] Done." -ForegroundColor Cyan
