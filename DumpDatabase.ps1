# PostgreSQL Database Dump Script
# Dumps the nexus database in cleartext SQL format
# Usage: .\DumpDatabase.ps1 -Password "your_password" [-DbHost "localhost"] [-Port 5432] [-User "postgres"] [-Database "nexus"]

param(
    [Parameter(Mandatory=$true)]
    [string]$Password,

    [Parameter(Mandatory=$false)]
    [string]$DbHost = "localhost",

    [Parameter(Mandatory=$false)]
    [int]$Port = 5432,

    [Parameter(Mandatory=$false)]
    [string]$User = "postgres",

    [Parameter(Mandatory=$false)]
    [string]$Database = "nexus"
)

# Create timestamp for the output file
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

# Create output directory if it doesn't exist
$outputDir = "sql\dumps"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

# Set the output file path
$outputFile = "$outputDir\${Database}_dump_$timestamp.sql"

# Set password in environment variable for pg_dump
$env:PGPASSWORD = $Password

Write-Host "Starting database dump..." -ForegroundColor Cyan
Write-Host "  Host: $DbHost" -ForegroundColor Gray
Write-Host "  Port: $Port" -ForegroundColor Gray
Write-Host "  User: $User" -ForegroundColor Gray
Write-Host "  Database: $Database" -ForegroundColor Gray
Write-Host "  Output: $outputFile" -ForegroundColor Gray
Write-Host ""

# Run pg_dump with plain SQL format (--format=plain or -Fp)
# --verbose: Show progress
# --no-owner: Don't output commands to set ownership
# --no-privileges: Don't output commands to set privileges (GRANT/REVOKE)
# --clean: Include DROP commands before CREATE
# --if-exists: Use IF EXISTS when dropping objects
pg_dump -h $DbHost -p $Port -U $User -d $Database `
    --format=plain `
    --verbose `
    --no-owner `
    --no-privileges `
    --clean `
    --if-exists `
    -f $outputFile

# Check if the dump was successful
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Success! Database dumped to: $outputFile" -ForegroundColor Green

    # Create a latest.sql symlink/copy for convenience
    $latestFile = "$outputDir\${Database}_dump_latest.sql"
    Copy-Item $outputFile $latestFile -Force
    Write-Host "Latest dump also saved to: $latestFile" -ForegroundColor Green

    # Show file size
    $fileSize = (Get-Item $outputFile).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    Write-Host ""
    Write-Host "Dump file size: $fileSizeMB MB" -ForegroundColor Yellow
} else {
    Write-Error "Failed to dump database. Exit code: $LASTEXITCODE"

    # Clear password and exit
    $env:PGPASSWORD = $null
    exit 1
}

# Clear password from environment
$env:PGPASSWORD = $null

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
