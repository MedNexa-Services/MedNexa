# MedNexa Database Automated Backup Script for Windows (Part 5 - Task 5.12)
param (
    [string]$BackupDir = ".\backups",
    [string]$ContainerName = "mednexa-db",
    [string]$DbUser = "mednexa",
    [string]$DbName = "mednexa",
    [int]$RetentionDays = 7
)

$ErrorActionPreference = "Stop"

if (!(Test-Path -Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $BackupDir "mednexa_backup_${Timestamp}.sql"

Write-Host "[INFO] Starting MedNexa database backup: $Timestamp..." -ForegroundColor Cyan

docker exec -t $ContainerName pg_dump -U $DbUser $DbName | Out-File -FilePath $BackupFile -Encoding utf8

$FileSize = (Get-Item $BackupFile).Length / 1MB
Write-Host ("[SUCCESS] Backup created successfully: {0} ({1:N2} MB)" -f $BackupFile, $FileSize) -ForegroundColor Green

# Retention policy: remove backups older than $RetentionDays
$CutoffDate = (Get-Date).AddDays(-$RetentionDays)
Get-ChildItem -Path $BackupDir -Filter "mednexa_backup_*.sql" | Where-Object { $_.LastWriteTime -lt $CutoffDate } | Remove-Item -Force
Write-Host "[INFO] Backup routine complete." -ForegroundColor Cyan
