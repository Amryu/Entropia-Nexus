# Entropia Nexus

A comprehensive web-based database and information platform for Entropia Universe, featuring interactive maps, item databases, market tracking, and community tools.

## About

Entropia Nexus is a community-driven platform that provides:

- **Interactive Maps**: Explore planets (Calypso, Setesh, etc.) with detailed location data
- **Item Database**: Comprehensive information on weapons, armor, vehicles, pets, blueprints, tools, and more
- **Game Information**: Mobs, skills, professions, vendors, and missions
- **Market Tools**: Shop tracking, exchange browser, and price monitoring
- **Player Tools**: Loadout builder and character management
- **Discord Integration**: Community engagement through Discord bot integration

## Architecture

The project consists of three main components:

### 1. Frontend ([nexus/](nexus/))
- **Framework**: SvelteKit
- **Port**: 3001
- **Purpose**: Web interface for browsing and managing game data
- **Features**:
  - Interactive SVG maps with markers
  - Item browser with filtering and search
  - Real-time market data visualization
  - User loadout management

### 2. Backend API ([api/](api/))
- **Framework**: Express.js
- **Port**: 3000
- **Purpose**: REST API serving data from PostgreSQL databases
- **Features**:
  - Swagger/OpenAPI documentation
  - Request metrics tracking
  - Compression and CORS support
  - Automatic error handling

### 3. Discord Bot ([nexus-bot/](nexus-bot/))
- **Framework**: Discord.js
- **Purpose**: Discord integration for community management
- **Features**:
  - User access control
  - Change tracking and approval workflows
  - Discord slash commands
  - Database update notifications

### 4. Desktop Client ([client/](client/))
- **Framework**: PyQt6
- **Purpose**: Desktop companion app for OCR skill scanning, chat log parsing, and hunting/mining tracking
- **Build**: PyInstaller via `client/build.sh`
- **Key Dependencies**: PyQt6, OpenCV, py-mini-racer, watchdog, keyboard

## Database Structure

The project uses two PostgreSQL databases:

- **nexus**: Wiki/static game data (items, maps, mobs, NPCs, etc.)
- **nexus_users**: User-related data (accounts, shops, inventories, change tracking, etc.)

## Prerequisites

Before you begin, ensure you have:

- **Node.js** 24 LTS and npm
- **Python** 3.9+ and pip (for the desktop client)
- **PostgreSQL** 14+ installed and running
- **Git** for version control
- **Bash shell** for client scripts (`client/build.sh`, `client/release.sh`)
  - Windows: install **Git Bash** (Git for Windows) or **MSYS2**
- **Docker** and Docker Compose (optional, for containerized deployment)
- **WSL** on Windows (optional, only needed for cross-platform client releases)

## Quick Start for New Developers

### 1. Clone the Repository

```bash
git clone <repository-url>
cd "Entropia Nexus"
```

### 2. Configure Environment Variables

The project uses `.env` files for configuration. Start by copying the example files:

```bash
# API configuration
cp api/.env.example api/.env

# Frontend configuration
cp nexus/.env.example nexus/.env

# Discord bot configuration (if using)
cp nexus-bot/.env.example nexus-bot/.env
```

### 3. Edit Configuration Files

Edit `api/.env` with your database credentials:

```env
# Primary Database (nexus)
NEXUS_DB_USER=nexus
NEXUS_DB_PASS=your_secure_password
NEXUS_DB_HOST=localhost
NEXUS_DB_NAME=nexus
NEXUS_DB_PORT=5432

# Users Database (nexus_users)
NEXUS_USERS_DB_USER=nexus
NEXUS_USERS_DB_PASS=your_secure_password
NEXUS_USERS_DB_HOST=localhost
NEXUS_USERS_DB_NAME=nexus_users
NEXUS_USERS_DB_PORT=5432
```

Edit `nexus/.env` with your frontend configuration:

```env
VITE_API_URL=http://localhost:3000
PUBLIC_URL=http://localhost:3001
```

### 4. Set Up Databases

Create the PostgreSQL databases and users manually, or use your preferred database management tool.

```sql
-- Create databases
CREATE DATABASE nexus;
CREATE DATABASE "nexus_users";

-- Create user and grant permissions
CREATE USER nexus WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE nexus TO nexus;
GRANT ALL PRIVILEGES ON DATABASE "nexus_users" TO nexus;
```

### 5. Install Dependencies

```bash
# Install API dependencies
cd api
npm install

# Install frontend dependencies
cd ../nexus
npm install

# Install Discord bot dependencies (if using)
cd ../nexus-bot
npm install

cd ..
```

If you plan to run or build the desktop client, use a Python virtual environment:

```bash
cd client
python -m venv .venv

# Activate the venv
# PowerShell:
.\.venv\Scripts\Activate.ps1
# Git Bash / MSYS2:
source .venv/Scripts/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
cd ..
```

### 6. Start the Development Environment

#### Option A: Using Docker Compose (Recommended)

```bash
docker-compose up
```

This starts all three services:
- Frontend: http://localhost:3001
- API: http://localhost:3000
- API Documentation: http://localhost:3000/api-docs
- Discord Bot: Running in background

#### Option B: Running Services Manually

```bash
# Terminal 1: Start API
cd api && npm start

# Terminal 2: Start Frontend
cd nexus && npm run dev

# Terminal 3: Start Discord Bot (optional)
cd nexus-bot && npm start
```

### 7. Access the Application

- **Frontend**: http://localhost:3001
- **API**: http://localhost:3000
- **Swagger API Docs**: http://localhost:3000/api-docs

## Environment Variables Reference

### API (.env)

```env
# Nexus Database (static/wiki data)
NEXUS_DB_USER=nexus
NEXUS_DB_PASS=your_password
NEXUS_DB_HOST=localhost
NEXUS_DB_NAME=nexus
NEXUS_DB_PORT=5432
NEXUS_DB_MAX=10
NEXUS_DB_IDLE_MS=30000
NEXUS_DB_KEEPALIVE=true

# Nexus-Users Database (user data)
NEXUS_USERS_DB_USER=nexus
NEXUS_USERS_DB_PASS=your_password
NEXUS_USERS_DB_HOST=localhost
NEXUS_USERS_DB_NAME=nexus_users
NEXUS_USERS_DB_PORT=5432
NEXUS_USERS_DB_MAX=10
NEXUS_USERS_DB_IDLE_MS=30000
NEXUS_USERS_DB_KEEPALIVE=true
```

### Frontend (.env)

```env
# API URL (frontend needs to connect to backend)
VITE_API_URL=http://localhost:3000

# Public URL (for production deployments)
PUBLIC_URL=http://localhost:3001

# Canonical redirect config for short domain
SHORT_REDIRECT_ENABLED=true
SHORT_REDIRECT_HOSTS=eunex.us,www.eunex.us
CANONICAL_PUBLIC_URL=https://entropianexus.com
```

### Discord Bot (.env)

```env
CLIENT_TOKEN=your_discord_bot_token
CLIENT_ID=your_discord_client_id
GUILD_ID=your_discord_guild_id
API_URL=http://localhost:3000
POSTGRES_USERS_CONNECTION_STRING=postgresql://nexus:password@localhost:5432/nexus_users
POSTGRES_NEXUS_CONNECTION_STRING=postgresql://nexus:password@localhost:5432/nexus
```

## Database Management

### Migrations

Database schema changes are managed through numbered migration files:

- **Nexus DB**: `sql/nexus/migrations/` (001–050+)
- **Nexus Users DB**: `sql/nexus_users/migrations/` (001–084+)

Apply migrations in numbered order:

```bash
psql -U nexus -d nexus -f sql/nexus/migrations/001_bot_permissions_nexus.sql
psql -U nexus -d nexus_users -f sql/nexus_users/migrations/001_service_tables.sql
# ... continue in order
```

Migrations are the source of truth for schema. Each file is wrapped in a transaction (`BEGIN`/`COMMIT`).

## Project Structure

```
Entropia Nexus/
├── api/                          # Backend API (Express.js)
│   ├── endpoints/                # API endpoint modules
│   ├── app.js                    # Express application entry
│   ├── package.json
│   └── .env                      # API configuration
├── nexus/                        # Frontend (SvelteKit)
│   ├── src/
│   │   ├── routes/               # SvelteKit routes
│   │   └── lib/
│   │       └── components/       # Svelte components
│   ├── package.json
│   └── .env                      # Frontend configuration
├── nexus-bot/                    # Discord Bot
│   ├── commands/                 # Discord slash commands
│   ├── bot.js                    # Bot entry point
│   ├── package.json
│   └── .env                      # Bot configuration
├── client/                       # Desktop Client (PyQt6)
│   ├── ui/                       # UI pages and components
│   ├── core/                     # Database, config, networking
│   ├── chat_parser/              # Chat log parsing and handlers
│   ├── skills/                   # Skill lookup utilities
│   ├── assets/                   # Icons and images
│   ├── data/                     # Reference data (skills, changelog)
│   ├── build.sh                  # PyInstaller build script
│   ├── release.sh                # Cross-platform release packaging
│   ├── requirements.txt          # Python dependencies
│   └── VERSION                   # Client version
├── sql/                          # Database migrations
│   ├── nexus/
│   │   └── migrations/           # Nexus DB migrations (numbered)
│   └── nexus_users/
│       └── migrations/           # Nexus Users DB migrations (numbered)
├── common/                       # Shared code/data between services
├── deploy/                       # Deployment scripts and config
│   ├── deploy.sh                 # Docker deployment orchestration
│   └── env.example               # Deployment env template
├── docs/                         # Documentation
├── docker-compose.yml            # Docker composition
├── LICENSE                       # Source-available license
└── README.md                     # This file
```

## Useful Scripts

| Script | Description |
|--------|-------------|
| `Build.ps1` | Build all services for production |
| `ReplicateToLocal.ps1` | Replicate production data to local environment |
| `client/build.sh` | Build client executable for current platform |
| `client/release.sh` | Cross-platform client release packaging |
| `deploy/deploy.sh` | Docker deployment orchestration |

## Building for Production

### Web Services

```bash
# Build all services
./Build.ps1

# Or build individually
cd nexus && npm run build:prod
cd api && npm ci --omit=dev
```

### Desktop Client

```bash
# Create and activate a virtual environment (recommended)
cd client
python -m venv .venv

# PowerShell:
.\.venv\Scripts\Activate.ps1
# Git Bash / MSYS2:
source .venv/Scripts/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
cd ..

# Build for current platform (run from a Bash shell)
bash client/build.sh
# Output: client/dist/entropia-nexus/

# Release (both platforms — Linux builds via WSL on Windows)
bash client/release.sh
bash client/release.sh --windows-only
bash client/release.sh --linux-only
```

Note: `client/build.sh` and `client/release.sh` must be run from Bash (Git Bash/MSYS2/WSL), not CMD/PowerShell.

The build script auto-detects the platform, bundles assets and data files, runs PyInstaller, and strips unnecessary Qt modules (~200 MB savings). Version is read from `client/VERSION` or git tags matching `client-*`.

## Docker Deployment

```bash
# Development: build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Deployment

Use the deployment script with a configured environment file:

```bash
cp deploy/env.example deploy/env
# Edit deploy/env with production paths and credentials
bash deploy/deploy.sh deploy/env
```

See [deploy/](deploy/) for details.

## API Documentation

When the API is running, access interactive API documentation at:

- Swagger UI: http://localhost:3000/api-docs

## Short URL Domain (eunex.us)

`eunex.us` is configured as a redirect-only short domain.

- Requests to `eunex.us` are resolved to canonical long-form URLs on `CANONICAL_PUBLIC_URL`.
- Redirects are permanent (`301`) and preserve query strings.
- Unknown short codes are still redirected to the canonical host with the original path/query unchanged.
- Short codes are only active on hosts listed in `SHORT_REDIRECT_HOSTS`.

Operational requirements:

1. Point DNS for `eunex.us` and `www.eunex.us` to the frontend entrypoint.
2. Ensure TLS certificates include both short hosts.
3. Preserve the incoming `Host` header at the reverse proxy/load balancer.
4. Set `CANONICAL_PUBLIC_URL` to the correct long-form site origin per environment.

## Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make your changes**
4. **Test thoroughly**
5. **Commit your changes**: `git commit -m "Add your feature"`
6. **Push to branch**: `git push origin feature/your-feature`
7. **Create a Pull Request**

By submitting a contribution, you agree to the terms in [Section 5 of the LICENSE](LICENSE) (perpetual license grant to the copyright holder).

### Coding Standards

- Use meaningful variable and function names
- Add comments for complex logic
- Follow existing code style
- Test changes before committing

## Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running: `pg_isready`
- Check credentials in `api/.env`
- Ensure databases exist: `psql -l`
- Check user permissions

### Port Already in Use

- Check what's using the port: `netstat -ano | findstr :3000`
- Change port in `.env` files
- Kill the process using the port

### Dependencies Not Found

- Delete `node_modules` and reinstall: `rm -r node_modules && npm install`
- Clear npm cache: `npm cache clean --force`
- Ensure you're using Node.js 24 LTS

### Windows Path Length Errors

- Symptoms: `Filename too long`, `ENAMETOOLONG`, checkout/build failures in deep paths.
- Enable long paths in Git:
  - `git config --global core.longpaths true`
- Enable long paths in Windows (Administrator PowerShell), then reboot:
  - `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force`
- Keep clone paths short (example: `C:\dev\entropia-nexus`) if issues persist.

## License

This project is licensed under the Entropia Nexus Source-Available License. See [LICENSE](LICENSE) for details.

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Contact the development team
- Check the [documentation](docs/)

## Acknowledgments

- Entropia Universe community
- All contributors and testers
