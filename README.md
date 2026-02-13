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

## Database Structure

The project uses two PostgreSQL databases:

- **nexus**: Wiki/static game data (items, maps, mobs, NPCs, etc.)
- **nexus-users**: User-related data (accounts, shops, inventories, change tracking, etc.)

## Prerequisites

Before you begin, ensure you have:

- **Node.js** 18+ and npm
- **PostgreSQL** 12+ installed and running
- **Docker** and Docker Compose (optional, for containerized deployment)
- **Git** for version control

## Quick Start for New Developers

### 1. Clone the Repository

```bash
git clone <repository-url>
cd "Entropia Nexus"
```

### 2. Configure Environment Variables

The project uses `.env` files for configuration. Start by copying the example files:

```powershell
# API configuration
cp api\.env.example api\.env

# Frontend configuration
cp nexus\.env.example nexus\.env

# Discord bot configuration (if using)
cp nexus-bot\.env.example nexus-bot\.env
```

### 3. Edit Configuration Files

Edit `api\.env` with your database credentials:

```env
# Primary Database (nexus)
NEXUS_DB_USER=nexus
NEXUS_DB_PASS=your_secure_password
NEXUS_DB_HOST=localhost
NEXUS_DB_NAME=nexus
NEXUS_DB_PORT=5432

# Users Database (nexus-users)
NEXUS_USERS_DB_USER=nexus
NEXUS_USERS_DB_PASS=your_secure_password
NEXUS_USERS_DB_HOST=localhost
NEXUS_USERS_DB_NAME=nexus-users
NEXUS_USERS_DB_PORT=5432
```

Edit `nexus\.env` with your frontend configuration:

```env
VITE_API_URL=http://localhost:3000
PUBLIC_URL=http://localhost:3001
```

### 4. Set Up Databases

Create the PostgreSQL databases and users manually, or use your preferred database management tool.

```sql
-- Create databases
CREATE DATABASE nexus;
CREATE DATABASE "nexus-users";

-- Create user and grant permissions
CREATE USER nexus WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE nexus TO nexus;
GRANT ALL PRIVILEGES ON DATABASE "nexus-users" TO nexus;
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

```powershell
# Terminal 1: Start API
cd api
npm start

# Terminal 2: Start Frontend
cd nexus
npm run dev

# Terminal 3: Start Discord Bot (optional)
cd nexus-bot
npm start
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
NEXUS_USERS_DB_NAME=nexus-users
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
POSTGRES_USERS_CONNECTION_STRING=postgresql://nexus:password@localhost:5432/nexus-users
POSTGRES_NEXUS_CONNECTION_STRING=postgresql://nexus:password@localhost:5432/nexus
```

## Database Management

### Exporting Database Schemas

To export the current database schemas for backup or sharing:

```powershell
.\ExportDatabases-Simple.ps1 -Password "your_postgres_password"
```

This creates schema exports in [sql/migrations/](sql/migrations/).

See [sql/migrations/README.md](sql/migrations/README.md) for more details.

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
│   │   ├── lib/
│   │   │   └── components/       # Svelte components
│   │   └── app.html
│   ├── package.json
│   └── .env                      # Frontend configuration
├── nexus-bot/                    # Discord Bot
│   ├── commands/                 # Discord slash commands
│   ├── bot.js                    # Bot entry point
│   ├── package.json
│   └── .env                      # Bot configuration
├── sql/                          # SQL scripts and utilities
│   ├── migrations/               # Database schema exports
│   │   ├── nexus/
│   │   │   └── schema_latest.sql
│   │   └── nexus-users/
│   │       └── schema_latest.sql
│   └── *.sql                     # Utility SQL scripts
├── common/                       # Shared code/data between services
├── docs/                         # Documentation
├── tools/                        # Development tools
├── docker-compose.yml            # Docker composition
├── Build.ps1                     # Build script
├── ReplicateToLocal.ps1          # Data replication script
├── ExportDatabases-Simple.ps1    # Export database schemas
└── README.md                     # This file
```

## Useful Scripts

| Script | Description |
|--------|-------------|
| `ExportDatabases-Simple.ps1` | Export current database schemas |
| `Build.ps1` | Build all services for production |
| `ReplicateToLocal.ps1` | Replicate production data to local environment |

## Building for Production

```powershell
# Build all services
.\Build.ps1

# Or build individually
cd nexus && npm run build:prod
cd ../api && npm install --production
```

## Docker Deployment

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

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

### Coding Standards

- Use meaningful variable and function names
- Add comments for complex logic
- Follow existing code style
- Test changes before committing

## Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running: `pg_isready`
- Check credentials in `api\.env`
- Ensure databases exist: `psql -l`
- Check user permissions

### Port Already in Use

- Check what's using the port: `netstat -ano | findstr :3000`
- Change port in `.env` files
- Kill the process using the port

### Dependencies Not Found

- Delete `node_modules` and reinstall: `rm -r node_modules && npm install`
- Clear npm cache: `npm cache clean --force`
- Ensure you're using Node.js 18+

## License

[Add your license information here]

## Support

For issues, questions, or contributions:
- Open an issue on GitHub
- Contact the development team
- Check the [documentation](docs/)

## Acknowledgments

- Entropia Universe community
- All contributors and testers
