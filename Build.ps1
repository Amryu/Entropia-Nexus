param(
    [switch]$NoCache,
    [switch]$PruneAll,
    [switch]$Pull,
    [string]$ComposeFile = "docker-compose.yml"
)

$ErrorActionPreference = 'Stop'

Set-Location -LiteralPath $PSScriptRoot/nexus

npm run build:dev

# Move to repo root (script directory)
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath $ComposeFile)) {
    throw "Compose file not found: $ComposeFile"
}

Write-Host "[1/4] Discovering images for this compose project..." -ForegroundColor Cyan
$composeImages = @()
try {
    # Merge stderr to stdout to avoid NativeCommandError on warnings, then filter to image IDs (12+ hex chars)
    $raw = & docker compose -f $ComposeFile images --quiet 2>&1
    if ($raw) {
        $composeImages = $raw | Where-Object { $_ -match '^[0-9a-f]{12,}$' } | Sort-Object -Unique
    }
} catch {
    Write-Host "Warning: failed to list compose images (continuing): $($_.Exception.Message)" -ForegroundColor DarkYellow
}

Write-Host "[2/4] Bringing down compose stack (containers/networks/volumes/orphans)..." -ForegroundColor Cyan
& docker compose -f $ComposeFile down --volumes --remove-orphans

# Stop and remove any non-compose containers using these images, then remove the images
if ($composeImages.Count -gt 0) {
    Write-Host "[3/4] Stopping/removing containers using compose images (outside of this project) ..." -ForegroundColor Cyan
    foreach ($img in $composeImages) {
        if (-not $img) { continue }
        $cons = & docker ps -a --filter "ancestor=$img" -q 2>$null | Sort-Object -Unique
        if ($cons) {
            Write-Host " - Killing containers for image ${img}: $($cons -join ', ')" -ForegroundColor DarkYellow
            foreach ($c in $cons) { & docker rm -f $c | Out-Null }
        }
    }

    Write-Host "Removing compose images ..." -ForegroundColor Cyan
    foreach ($img in $composeImages) {
        if (-not $img) { continue }
        & docker rmi -f $img 2>$null | Out-Null
    }
} else {
    Write-Host "[3/4] No compose images found to clean." -ForegroundColor DarkGray
}

if ($PruneAll) {
    Write-Host "[3/4] Pruning unused images/volumes/build cache (global) ..." -ForegroundColor Cyan
    # Remove unused images not referenced by any container
    & docker image prune -a -f
    # Remove dangling build cache
    & docker builder prune -a -f
    # Remove unused volumes (no containers attached)
    & docker volume prune -f
} else {
    Write-Host "[3/4] Skipping global prune (use -PruneAll to enable)." -ForegroundColor DarkGray
}

Write-Host "[4/4] Building compose images..." -ForegroundColor Cyan
$buildArgs = @('compose','-f', $ComposeFile, 'build')
if ($NoCache) { $buildArgs += '--no-cache' }
if ($Pull)    { $buildArgs += '--pull' }

& docker @buildArgs

Write-Host "Done. You can start the stack with: docker compose -f $ComposeFile up -d" -ForegroundColor Green
