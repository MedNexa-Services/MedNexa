# MedNexa database restore for Windows (Part 5, task 5.12). Same behaviour as restore.sh:
# replaces the database contents with the backup in ONE transaction (all or nothing).
#
#   .\scripts\restore.ps1 -BackupFile .\backups\mednexa_backup_<timestamp>.sql.gz [-Yes]
#
# Stop the services that use the database first (docker compose stop api telephony dashboard)
# and start them again afterwards.
param (
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [string]$ContainerName = $(if ($env:DB_CONTAINER) { $env:DB_CONTAINER } else { "mednexa-db" }),
    [string]$DbUser = $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "mednexa" }),
    [string]$DbName = $(if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "mednexa" }),
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

function Assert-Success([string]$What) {
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)" }
}

if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) { throw "Backup file not found: $BackupFile" }
$running = docker inspect -f '{{.State.Running}}' $ContainerName 2>$null
if ($running -ne "true") {
    throw "Container '$ContainerName' is not running (set -ContainerName or `$env:DB_CONTAINER)."
}

Write-Host "[WARNING] This replaces ALL data in database '$DbName' with $BackupFile." -ForegroundColor Yellow
if (-not $Yes) {
    $answer = Read-Host "Continue? (y/N)"
    if ($answer -notin @("y", "Y")) { Write-Host "[INFO] Restore aborted."; exit 0 }
}

$Remote = "/tmp/mednexa_restore.sql.gz"
try {
    docker cp (Resolve-Path -LiteralPath $BackupFile).Path "${ContainerName}:$Remote"
    Assert-Success "docker cp"
    docker exec $ContainerName gzip -t $Remote
    Assert-Success "Checking the backup (is it a valid gzip file?)"

    $script = "set -e; gunzip -c '$Remote' | psql -v ON_ERROR_STOP=1 --single-transaction -q -o /dev/null -U '$DbUser' -d '$DbName'"
    docker exec $ContainerName sh -c $script
    Assert-Success "psql restore"
}
finally {
    docker exec $ContainerName rm -f $Remote *> $null
}
Write-Host "[SUCCESS] Database '$DbName' restored from $BackupFile." -ForegroundColor Green
