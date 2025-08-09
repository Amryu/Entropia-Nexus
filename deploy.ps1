# Deployment script for Entropia Nexus (PowerShell version)
# Usage: .\deploy.ps1 [nexus|api|bot|all|status]

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("nexus", "api", "bot", "all", "status")]
    [string]$Target
)

# Function to print colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

$SERVER_USER = "root"
$SERVER_HOST = "entropianexus.com"
$NEXUS_DEST = "/var/www/nexus"
$API_DEST = "/var/www/api"
$BOT_DEST = "/var/www/nexus-bot"

# Load configuration from external file
$configPath = Join-Path $env:USERPROFILE "deploy-config.json"
if (Test-Path $configPath) {
    $config = Get-Content $configPath | ConvertFrom-Json
    if ($config.password) {
        $SERVER_PASSWORD = $config.password
        Write-Status "Loaded password from config file"
    }
    if ($config.server_user) { $SERVER_USER = $config.server_user }
    if ($config.server_host) { $SERVER_HOST = $config.server_host }
} else {
    Write-Warning "Config file not found at $configPath"
    Write-Host "Create a file with: { `"password`": `"your-password`", `"server_user`": `"root`", `"server_host`": `"entropianexus.com`" }" -ForegroundColor Yellow
    exit 1
}

# Function to copy files using native PowerShell/SSH
function Copy-FilesToServer {
    param(
        [string]$SourcePath,
        [string]$DestPath,
        [string[]]$ExcludePatterns = @(),
        [switch]$DeleteExtra
    )
    
    Write-Status "Copying files from $SourcePath to $DestPath..."
    
    # Create a temporary directory for staging files
    $tempDir = Join-Path $env:TEMP "nexus-deploy-$(Get-Random)"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    try {
        # Copy files to temp directory with exclusions
        $sourceItems = Get-ChildItem -Path $SourcePath -Recurse
        
        foreach ($item in $sourceItems) {
            $relativePath = $item.FullName.Substring($SourcePath.Length).TrimStart('\', '/')
            $shouldExclude = $false
            
            # Check against exclusion patterns
            foreach ($pattern in $ExcludePatterns) {
                if ($relativePath -like $pattern -or $item.Name -like $pattern) {
                    $shouldExclude = $true
                    break
                }
            }
            
            if (-not $shouldExclude) {
                $destItem = Join-Path $tempDir $relativePath
                $destDir = Split-Path $destItem -Parent
                
                if (-not (Test-Path $destDir)) {
                    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                }
                
                if ($item.PSIsContainer -eq $false) {
                    Copy-Item $item.FullName $destItem -Force
                }
            }
        }
        
        # Create destination directory on server
        Invoke-SSH "mkdir -p '$DestPath'"
        
        # If DeleteExtra is specified, remove existing files first
        if ($DeleteExtra) {
            Write-Status "Cleaning destination directory..."
            Invoke-SSH "find '$DestPath' -mindepth 1 -delete 2>/dev/null || true"
        }
        
        # Use scp to copy the entire temp directory content
        Write-Status "Transferring files to server..."
        $scpDest = "${SERVER_USER}@${SERVER_HOST}:$DestPath/"
        
        # Use SCP with automated password
        $expectScript = @"
#!/usr/bin/expect -f
spawn scp -o StrictHostKeyChecking=no -r "$tempDir/*" "$scpDest"
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
"@
        
        $tempScript = [System.IO.Path]::GetTempFileName() + ".exp"
        $expectScript | Out-File -FilePath $tempScript -Encoding ASCII
        
        try {
            if (Get-Command wsl -ErrorAction SilentlyContinue) {
                # Use WSL if available
                wsl expect $tempScript
            } else {
                # Fallback to basic SCP (will prompt for password)
                Write-Warning "No automated password method available. You'll need to enter the password manually."
                & scp -o StrictHostKeyChecking=no -r "$tempDir/*" "$scpDest"
            }
        } finally {
            if (Test-Path $tempScript) {
                Remove-Item $tempScript -Force
            }
        }
        
        if ($LASTEXITCODE -ne 0) {
            throw "SCP failed with exit code: $LASTEXITCODE"
        }
        
        Write-Status "Files copied successfully"
    }
    finally {
        # Clean up temp directory
        if (Test-Path $tempDir) {
            Remove-Item $tempDir -Recurse -Force
        }
    }
}

# Function to copy individual files to server
function Copy-FileToServer {
    param(
        [string]$SourceFile,
        [string]$DestPath
    )
    
    Write-Status "Copying $SourceFile..."
    
    # Use SCP with automated password
    $expectScript = @"
#!/usr/bin/expect -f
spawn scp -o StrictHostKeyChecking=no "$SourceFile" "${SERVER_USER}@${SERVER_HOST}:$DestPath/"
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
"@
    
    $tempScript = [System.IO.Path]::GetTempFileName() + ".exp"
    $expectScript | Out-File -FilePath $tempScript -Encoding ASCII
    
    try {
        if (Get-Command wsl -ErrorAction SilentlyContinue) {
            # Use WSL if available
            wsl expect $tempScript
        } else {
            # Fallback to basic SCP (will prompt for password)
            Write-Warning "No automated password method available. You'll need to enter the password manually."
            & scp -o StrictHostKeyChecking=no "$SourceFile" "${SERVER_USER}@${SERVER_HOST}:$DestPath/"
        }
    } finally {
        if (Test-Path $tempScript) {
            Remove-Item $tempScript -Force
        }
    }
    
    if ($LASTEXITCODE -ne 0) {
        throw "SCP failed with exit code: $LASTEXITCODE"
    }
}

# Function to test SSH connection
function Test-SSHConnection {
    Write-Status "Testing SSH connection to $SERVER_HOST..."
    
    try {
        $result = Invoke-SSH "echo 'SSH connection successful'"
        Write-Success "SSH connection test passed"
        return $true
    }
    catch {
        Write-Error "SSH connection test failed: $_"
        return $false
    }
}

# Function to execute SSH command
function Invoke-SSH {
    param([string]$Command)
    
    Write-Status "Executing: $Command"
    
    # Create a temporary expect script for automated password entry
    $expectScript = @"
#!/usr/bin/expect -f
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_HOST "$Command"
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
"@
    
    $tempScript = [System.IO.Path]::GetTempFileName() + ".exp"
    $expectScript | Out-File -FilePath $tempScript -Encoding ASCII
    
    try {
        if (Get-Command wsl -ErrorAction SilentlyContinue) {
            # Use WSL if available
            $result = wsl expect $tempScript
        } else {
            # Fallback to basic SSH (will prompt for password)
            Write-Warning "No automated password method available. You'll need to enter the password manually."
            $result = ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_HOST $Command
        }
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "SSH command failed with exit code: $LASTEXITCODE"
            throw "SSH command failed"
        }
        return $result
    } finally {
        if (Test-Path $tempScript) {
            Remove-Item $tempScript -Force
        }
    }
}
function Stop-ScreenProcess {
    param([string]$SessionName)
    Write-Status "Checking for existing $SessionName process..."
    
    $stopCommand = @"
if screen -list | grep -q '$SessionName'; then
    echo 'Stopping existing $SessionName process...'
    screen -S $SessionName -X quit || true
    sleep 2
else
    echo 'No existing $SessionName process found'
fi
"@
    
    Invoke-SSH $stopCommand
}

# Function to start screen process
function Start-ScreenProcess {
    param([string]$SessionName, [string]$Command, [string]$WorkingDir)
    
    Write-Status "Starting $SessionName process..."
    
    $startCommand = @"
cd $WorkingDir
screen -dmS $SessionName bash -c '$Command'
sleep 2
if screen -list | grep -q '$SessionName'; then
    echo '$SessionName started successfully'
else
    echo 'Failed to start $SessionName'
    exit 1
fi
"@
    
    Invoke-SSH $startCommand
}

# Function to deploy nexus
function Deploy-Nexus {
    Write-Status "Deploying Nexus..."
    
    # Build the project
    Write-Status "Building Nexus..."
    Set-Location nexus
    npm run build
    Set-Location ..
    
    # Stop existing process
    Stop-ScreenProcess "nexus"
    
    # Create destination directory
    Invoke-SSH "mkdir -p $NEXUS_DEST"
    
    # Copy build folder
    Write-Status "Copying build files..."
    $excludePatterns = @('node_modules', '.git*', '.env*', '*.log')
    Copy-FilesToServer -SourcePath "nexus/build" -DestPath $NEXUS_DEST -ExcludePatterns $excludePatterns -DeleteExtra
    
    # Copy additional files
    Copy-FileToServer -SourceFile "nexus/start.js" -DestPath $NEXUS_DEST
    Copy-FileToServer -SourceFile "nexus/package.json" -DestPath $NEXUS_DEST
    
    # Install dependencies
    Write-Status "Installing dependencies on server..."
    Invoke-SSH "cd $NEXUS_DEST && npm install --production"
    
    # Start the process
    Start-ScreenProcess "nexus" "node start.js" $NEXUS_DEST
    
    Write-Success "Nexus deployed successfully!"
}

# Function to deploy API
function Deploy-Api {
    Write-Status "Deploying API..."
    
    # Stop existing process
    Stop-ScreenProcess "api"
    
    # Create destination directory
    Invoke-SSH "mkdir -p $API_DEST"
    
    # Copy API files
    Write-Status "Copying API files..."
    $excludePatterns = @('credentials.js', 'node_modules', '.git*', '*.log', 'test*', '*.test.js')
    Copy-FilesToServer -SourcePath "api" -DestPath $API_DEST -ExcludePatterns $excludePatterns -DeleteExtra
    
    # Update dependencies if needed
    Write-Status "Checking for package.json changes..."
    $updateCommand = @"
cd $API_DEST
if [ ! -f package-lock.json ] || [ package.json -nt package-lock.json ]; then
    echo 'Package.json changed, updating dependencies...'
    npm install --production
else
    echo 'No package changes detected'
fi
"@
    
    Invoke-SSH $updateCommand
    
    # Start the process
    Start-ScreenProcess "api" "HOST=127.0.0.1 PORT=3000 node app.js" $API_DEST
    
    Write-Success "API deployed successfully!"
}

# Function to deploy bot
function Deploy-Bot {
    Write-Status "Deploying Bot..."
    
    # Stop existing process
    Stop-ScreenProcess "bot"
    
    # Create destination directory
    Invoke-SSH "mkdir -p $BOT_DEST"
    
    # Copy Bot files
    Write-Status "Copying Bot files..."
    $excludePatterns = @('config.json', '.env', 'node_modules', '.git*', '*.log', 'test*', '*.test.js')
    Copy-FilesToServer -SourcePath "nexus-bot" -DestPath $BOT_DEST -ExcludePatterns $excludePatterns -DeleteExtra
    
    # Update dependencies if needed
    Write-Status "Checking for package.json changes..."
    $updateCommand = @"
cd $BOT_DEST
if [ ! -f package-lock.json ] || [ package.json -nt package-lock.json ]; then
    echo 'Package.json changed, updating dependencies...'
    npm install --production
else
    echo 'No package changes detected'
fi
"@
    
    Invoke-SSH $updateCommand
    
    # Start the process
    Start-ScreenProcess "bot" "node bot.js" $BOT_DEST
    
    Write-Success "Bot deployed successfully!"
}

# Function to show status
function Show-Status {
    Write-Status "Checking deployment status..."
    $statusCommand = @"
echo '=== Screen Sessions ==='
screen -list || echo 'No screen sessions running'
echo ''
echo '=== Process Status ==='
ps aux | grep -E '(node|npm)' | grep -v grep || echo 'No Node.js processes found'
"@
    
    Invoke-SSH $statusCommand
}

# Main deployment logic
Write-Status "Starting deployment process..."

# Test SSH connection first
if (-not (Test-SSHConnection)) {
    Write-Error "Cannot establish SSH connection. Please check:"
    Write-Host "1. SSH key is set up correctly" -ForegroundColor Yellow
    Write-Host "2. Server is accessible: ssh $SERVER_USER@$SERVER_HOST" -ForegroundColor Yellow
    Write-Host "3. Try manually: ssh $SERVER_USER@$SERVER_HOST 'echo test'" -ForegroundColor Yellow
    exit 1
}

switch ($Target) {
    "nexus" { Deploy-Nexus }
    "api" { Deploy-Api }
    "bot" { Deploy-Bot }
    "all" { 
        Write-Status "Deploying all components..."
        Deploy-Api
        Deploy-Bot
        Deploy-Nexus
    }
    "status" { Show-Status }
}

Write-Success "Deployment completed!"
