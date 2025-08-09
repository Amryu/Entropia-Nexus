# Deployment Guide

This repository includes deployment scripts to easily deploy the Entropia Nexus components to your server.

## Prerequisites

1. **SSH Access**: Set up SSH key authentication to your server
2. **rsync**: Required for file synchronization
   - Linux/macOS: Usually pre-installed
   - Windows: Install via WSL, Git Bash, or Cygwin
3. **Screen**: Must be installed on your server for process management

## Setup

1. **Configure the deployment script**:
   ```bash
   cp deploy.config.example deploy.config
   # Edit deploy.config with your server details
   ```

2. **Update script variables** (if not using config file):
   - Edit `deploy.sh` or `deploy.ps1`
   - Change `SERVER_USER` and `SERVER_HOST` variables

3. **Make the bash script executable**:
   ```bash
   chmod +x deploy.sh
   ```

## Usage

### Bash (Linux/macOS/WSL)
```bash
# Deploy individual components
./deploy.sh nexus    # Deploy frontend only
./deploy.sh api      # Deploy API only  
./deploy.sh bot      # Deploy bot only
./deploy.sh all      # Deploy all components

# Check status
./deploy.sh status
```

### PowerShell (Windows)
```powershell
# Deploy individual components
.\deploy.ps1 nexus   # Deploy frontend only
.\deploy.ps1 api     # Deploy API only
.\deploy.ps1 bot     # Deploy bot only
.\deploy.ps1 all     # Deploy all components

# Check status
.\deploy.ps1 status
```

## What Each Deployment Does

### Nexus (Frontend)
- Builds the SvelteKit application
- Copies `build/` folder to `/var/www/nexus`
- Copies `start.js` and `package.json`
- Installs production dependencies
- Restarts in screen session named "nexus"

### API
- Copies all files except `credentials.js` to `/var/www/api`
- Updates npm packages if `package.json` changed
- Restarts in screen session named "api"
- Starts with: `HOST=127.0.0.1 PORT=3000 node app.js`

### Bot
- Copies all files except `config.json` and `.env` to `/var/www/nexus-bot`
- Installs/updates npm packages
- Restarts in screen session named "bot"
- Starts with: `node bot.js`

## Server Requirements

### Directory Structure
```
/var/www/
├── nexus/          # Frontend build files
├── api/            # API server files
└── nexus-bot/      # Discord bot files
```

### Screen Sessions
The deployment script manages these screen sessions:
- `nexus` - Frontend application
- `api` - API server
- `bot` - Discord bot

### Managing Screen Sessions Manually
```bash
# List all screen sessions
screen -list

# Attach to a session
screen -r nexus
screen -r api
screen -r bot

# Detach from session (while inside)
Ctrl+A, then D

# Kill a session
screen -S nexus -X quit
```

## Troubleshooting

### SSH Connection Issues
- Ensure SSH key authentication is set up
- Test connection: `ssh your-username@your-server.com`
- Check SSH key permissions: `chmod 600 ~/.ssh/id_rsa`

### Rsync Not Found (Windows)
- Install Git Bash or WSL
- Or install rsync via Chocolatey: `choco install rsync`

### Screen Session Issues
- Install screen on server: `sudo apt install screen` (Ubuntu/Debian)
- Check if sessions are running: `screen -list`

### Permission Issues
- Ensure your user has write access to `/var/www/`
- May need to run: `sudo chown -R your-username:your-username /var/www/`

### Port Already in Use
- Check what's using the port: `sudo lsof -i :3000`
- Kill process if needed: `sudo kill -9 <PID>`

## Configuration Files Excluded

The following files are **NOT** copied during deployment to preserve server-specific settings:

### API
- `credentials.js` - Database credentials and API keys

### Bot  
- `config.json` - Bot configuration
- `.env` - Environment variables and tokens

### General
- `node_modules/` - Dependencies (reinstalled fresh)
- `.git/` - Git repository data
- `*.log` - Log files
- Development and test files

Make sure these files exist on your server before first deployment!
