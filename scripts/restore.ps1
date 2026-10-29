# MedNexa Database Restore Script for Windows (Part 5 - Task 5.12)
param (
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [string]$ContainerName = "mednexa-db",
    [string]$DbUser = "mednexa",
    [string]$DbName = "mednexa"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -Path $BackupFile)) {
    Write-Error "Backup file not found: $BackupFile"
    exit 1
}

Write-Host "[WARNING] This will overwrite current database '$DbName'." -ForegroundColor Yellow
$Confirmation = Read-Host "Type 'YES' to proceed with restore"
if ($Confirmation -ne "YES") {
    Write-Host "[INFO] Restore aborted."
    exit 0
}

Write-Host "[INFO] Restoring database from $BackupFile..." -ForegroundColor Cyan
Get-Content -Path $BackupFile -Raw | docker exec -i $ContainerName psql -U $DbUser -d $DbName

Write-Host "[SUCCESS] Database restore complete." -ForegroundColor Green
