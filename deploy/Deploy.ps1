param(
    [string]$ConfigPath = "deploy/env"
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[deploy] $msg" -ForegroundColor Cyan }

# Load env file if present (KEY=VALUE lines)
if (Test-Path $ConfigPath) {
    Write-Info "Loading config from $ConfigPath"
    Get-Content $ConfigPath | ForEach-Object {
        if ($_ -match '^(\s*#|\s*$)') { return }
        $kv = $_ -split '=', 2
        if ($kv.Count -eq 2) {
            $k = $kv[0].Trim()
            $v = $kv[1].Trim()
            [System.Environment]::SetEnvironmentVariable($k, $v)
        }
    }
} else {
    Write-Info "No config file provided. Using defaults and environment."
}

$PROJECT_DIR = $env:PROJECT_DIR
if (-not $PROJECT_DIR) { $PROJECT_DIR = (Get-Location).Path }
$BUILD_MODE = $env:BUILD_MODE; if (-not $BUILD_MODE) { $BUILD_MODE = 'production' }
$COMPOSE_ENV_FILE = $env:COMPOSE_ENV_FILE; if (-not $COMPOSE_ENV_FILE) { $COMPOSE_ENV_FILE = 'deploy/compose.env' }
$COMMON_HOST_PATH = $env:COMMON_HOST_PATH; if (-not $COMMON_HOST_PATH) { $COMMON_HOST_PATH = Join-Path $PROJECT_DIR 'common' }
$SYNC_COMMON_FROM_REPO = $env:SYNC_COMMON_FROM_REPO; if (-not $SYNC_COMMON_FROM_REPO) { $SYNC_COMMON_FROM_REPO = 'true' }
$API_ENV_PATH = $env:API_ENV_PATH; if (-not $API_ENV_PATH) { $API_ENV_PATH = (Join-Path $PROJECT_DIR 'api/.env') }
$NEXUS_ENV_PATH = $env:NEXUS_ENV_PATH; if (-not $NEXUS_ENV_PATH) { $NEXUS_ENV_PATH = (Join-Path $PROJECT_DIR 'nexus/.env') }
$BOT_ENV_PATH = $env:BOT_ENV_PATH; if (-not $BOT_ENV_PATH) { $BOT_ENV_PATH = (Join-Path $PROJECT_DIR 'nexus-bot/.env') }
$BOT_CONFIG_PATH = $env:BOT_CONFIG_PATH; if (-not $BOT_CONFIG_PATH) { $BOT_CONFIG_PATH = (Join-Path $PROJECT_DIR 'nexus-bot/config.json') }
$GIT_PULL = $env:GIT_PULL; if (-not $GIT_PULL) { $GIT_PULL = 'false' }
$GIT_REMOTE = $env:GIT_REMOTE; if (-not $GIT_REMOTE) { $GIT_REMOTE = 'origin' }
$GIT_BRANCH = $env:GIT_BRANCH

Write-Info "Project dir: $PROJECT_DIR"
Set-Location $PROJECT_DIR

if ($GIT_PULL -eq 'true') {
    Write-Info "Updating repo from $GIT_REMOTE $GIT_BRANCH"
    git fetch $GIT_REMOTE
    if ($GIT_BRANCH) { git checkout $GIT_BRANCH }
    git pull --ff-only $GIT_REMOTE $GIT_BRANCH
}

Write-Info "Building Nexus ($BUILD_MODE)"
Push-Location (Join-Path $PROJECT_DIR 'nexus')
 npm ci
 if ($BUILD_MODE -eq 'development') { npm run build:dev } else { npm run build:prod }
Pop-Location

if ($SYNC_COMMON_FROM_REPO -eq 'true') {
    Write-Info "Syncing common -> $COMMON_HOST_PATH"
    if (-not (Test-Path $COMMON_HOST_PATH)) { New-Item -ItemType Directory -Path $COMMON_HOST_PATH | Out-Null }
    # simple sync: remove and copy
    Get-ChildItem -Path $COMMON_HOST_PATH -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -Path (Join-Path $PROJECT_DIR 'common\*') -Destination $COMMON_HOST_PATH -Recurse -Force
}

Write-Info "Writing compose env file: $COMPOSE_ENV_FILE"
$composeDir = Split-Path -Path $COMPOSE_ENV_FILE -Parent
if ($composeDir -and -not (Test-Path $composeDir)) { New-Item -ItemType Directory -Path $composeDir | Out-Null }
@(
    "COMMON_HOST_PATH=$COMMON_HOST_PATH",
    "API_ENV_PATH=$API_ENV_PATH",
    "NEXUS_ENV_PATH=$NEXUS_ENV_PATH",
    "BOT_ENV_PATH=$BOT_ENV_PATH",
    "BOT_CONFIG_PATH=$BOT_CONFIG_PATH"
) | Set-Content -Path $COMPOSE_ENV_FILE -Encoding UTF8

$composeArgs = @('--env-file', $COMPOSE_ENV_FILE)

Write-Info "Bringing stack down"
 docker compose @composeArgs down 2>$null

Write-Info "Building images"
 docker compose @composeArgs build

Write-Info "Starting stack"
 docker compose @composeArgs up -d --remove-orphans

Write-Info "Done. Current services:"
 docker compose @composeArgs ps
