#!/bin/bash

# Server Setup Script for Entropia Nexus
# Run this on your server to set up the initial directory structure and dependencies

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root. Run as your regular user."
    exit 1
fi

print_status "Setting up Entropia Nexus server environment..."

# Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required packages
print_status "Installing required packages..."
sudo apt install -y curl wget git screen nginx

# Install Node.js (using NodeSource repository for latest LTS)
print_status "Installing Node.js..."
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
    sudo apt install -y nodejs
fi

# Verify installations
print_status "Verifying installations..."
echo "Node.js version: $(node --version)"
echo "npm version: $(npm --version)"
echo "Screen version: $(screen --version | head -n1)"

# Create directory structure
print_status "Creating directory structure..."
sudo mkdir -p /var/www/nexus
sudo mkdir -p /var/www/api
sudo mkdir -p /var/www/nexus-bot

# Set ownership
print_status "Setting directory ownership..."
sudo chown -R $USER:$USER /var/www/

# Set permissions
print_status "Setting directory permissions..."
chmod 755 /var/www/nexus
chmod 755 /var/www/api
chmod 755 /var/www/nexus-bot

# Create nginx configuration for nexus (optional)
print_status "Creating nginx configuration template..."
sudo tee /etc/nginx/sites-available/nexus > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;  # Change this to your domain
    
    # Frontend (Nexus)
    location / {
        proxy_pass http://127.0.0.1:3001;  # Adjust port if different
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://127.0.0.1:3000/;  # API server
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

print_warning "Nginx configuration created at /etc/nginx/sites-available/nexus"
print_warning "Remember to:"
print_warning "1. Edit the server_name in the nginx config"
print_warning "2. Enable the site: sudo ln -s /etc/nginx/sites-available/nexus /etc/nginx/sites-enabled/"
print_warning "3. Test nginx config: sudo nginx -t"
print_warning "4. Reload nginx: sudo systemctl reload nginx"

# Create example configuration files
print_status "Creating example configuration files..."

# API credentials example
cat > /var/www/api/credentials.js.example << 'EOF'
// Copy this file to credentials.js and fill in your actual credentials

module.exports = {
  // Database connection
  connectionString: 'postgresql://username:password@localhost:5432/nexus',
  
  // API configuration
  port: 3000,
  host: '127.0.0.1',
  
  // Add other credentials as needed
};
EOF

# Bot config example
cat > /var/www/nexus-bot/config.json.example << 'EOF'
{
  "prefix": "!",
  "guildId": "your-guild-id",
  "clientId": "your-client-id",
  "channels": {
    "general": "channel-id"
  }
}
EOF

# Bot .env example
cat > /var/www/nexus-bot/.env.example << 'EOF'
CLIENT_TOKEN=your-bot-token
CLIENT_ID=your-client-id
GUILD_ID=your-guild-id
API_URL=http://localhost:3000
POSTGRES_USERS_CONNECTION_STRING=postgresql://username:password@localhost:5432/nexus-users
POSTGRES_NEXUS_CONNECTION_STRING=postgresql://username:password@localhost:5432/nexus
EOF

# Create systemd service files (alternative to screen)
print_status "Creating systemd service templates..."

sudo tee /etc/systemd/system/nexus-api.service > /dev/null <<EOF
[Unit]
Description=Entropia Nexus API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/var/www/api
Environment=HOST=127.0.0.1
Environment=PORT=3000
ExecStart=/usr/bin/node app.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/nexus-bot.service > /dev/null <<EOF
[Unit]
Description=Entropia Nexus Discord Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/var/www/nexus-bot
ExecStart=/usr/bin/node bot.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/nexus-frontend.service > /dev/null <<EOF
[Unit]
Description=Entropia Nexus Frontend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/var/www/nexus
ExecStart=/usr/bin/node start.js
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

print_success "Server setup completed!"
print_status "Directory structure created:"
echo "  /var/www/nexus/     - Frontend application"
echo "  /var/www/api/       - API server"
echo "  /var/www/nexus-bot/ - Discord bot"
echo ""
print_status "Next steps:"
echo "1. Copy your configuration files:"
echo "   - /var/www/api/credentials.js (from credentials.js.example)"
echo "   - /var/www/nexus-bot/config.json (from config.json.example)"
echo "   - /var/www/nexus-bot/.env (from .env.example)"
echo ""
echo "2. Set up your database and configure connection strings"
echo ""
echo "3. Configure nginx if you want to use it:"
echo "   - Edit /etc/nginx/sites-available/nexus"
echo "   - Enable: sudo ln -s /etc/nginx/sites-available/nexus /etc/nginx/sites-enabled/"
echo "   - Test: sudo nginx -t"
echo "   - Reload: sudo systemctl reload nginx"
echo ""
echo "4. Use screen sessions (recommended) or systemd services:"
echo "   Screen: Use the deployment script"
echo "   Systemd: sudo systemctl enable/start nexus-api nexus-bot nexus-frontend"
echo ""
echo "5. Run your deployment script from your local machine"
