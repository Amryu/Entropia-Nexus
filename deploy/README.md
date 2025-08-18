# Deployment

## Overview
This folder contains helper files to deploy the stack to a server using Docker Compose and images pushed to GHCR.

## Steps
1. On CI, images are built and pushed to GHCR with tag `${GITHUB_SHA}` and the `common` folder is uploaded as an artifact.
2. On the server, download/extract the repo (or just keep docker-compose files), copy the `deploy/` folder, and prepare an `.env` file based on `deploy/env.example`.
3. Provide `IMAGE_TAG` from the CI build you want to deploy. Optionally, provide `COMMON_SRC_DIR` or `COMMON_SRC_ARCHIVE` to update the `common` directory.
4. Run the deploy script:
   ```bash
   set -a
   source deploy/.env
   set +a
   bash deploy/deploy.sh
   ```

## Notes
- The override file `docker-compose.deploy.yml` switches services to pull from GHCR instead of building locally.
- Ensure the server has access to GHCR (log in with `docker login ghcr.io`).
- The script replaces the `common` directory if provided and restarts the stack.
