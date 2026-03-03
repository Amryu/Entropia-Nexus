# Client Release Process

Step-by-step guide for releasing a new version of the Entropia Nexus desktop client.

## Prerequisites

- Git tag for the version (e.g. `client-0.1.4`)
- WSL with Python venv at `~/entropia-nexus-venv` (for Linux builds)
- PyInstaller installed (`pip install pyinstaller`)
- 7z, zip, or PowerShell available (for Windows archive)

## 1. Prepare the Release

### Update version and changelog

1. **Edit `client/data/changelog.json`** — add a new entry at the top:
   ```json
   {
     "version": "X.Y.Z",
     "date": "YYYY-MM-DD",
     "changes": [
       {"type": "feat", "text": "Description of new feature"},
       {"type": "fix", "text": "Description of bug fix"}
     ]
   }
   ```
   Valid types: `feat`, `fix`.

2. **Update `client/VERSION`** — set to the new version string (e.g. `0.1.4`).

3. **Commit and tag:**
   ```bash
   git add client/VERSION client/data/changelog.json
   git commit -m "chore: bump client version to X.Y.Z"
   git tag client-X.Y.Z
   ```

### Version resolution

The build script (`client/build.sh`) resolves the version in this order:
1. Git tag matching `client-*` (preferred) — `git describe --tags --match 'client-*'`
2. Fallback: contents of `client/VERSION`

The tag and VERSION file should always agree.

## 2. Build

### Both platforms (from Windows with WSL)

```bash
./client/release.sh
```

### Single platform

```bash
./client/release.sh --windows-only
./client/release.sh --linux-only
```

### Skip rebuild (re-package existing dist)

```bash
./client/release.sh --skip-build
```

### What the build does

1. **`build.sh`** (per-platform):
   - Installs dependencies from `client/requirements.txt`
   - Runs PyInstaller `--onedir` with:
     - `--collect-all py_mini_racer` (V8 engine native binaries)
     - Bundled data: JS utils, assets, skill data, changelog, VERSION
     - Hidden imports: PyQt6.QtSvg, keyring backends
   - Strips unnecessary Qt/OpenCV/FFmpeg files (~100+ MB saved)
   - Writes resolved version into bundled VERSION
   - Generates `manifest.json` with SHA-256 hashes of all files

2. **`release.sh`** (packaging):
   - Builds Windows natively, Linux via WSL
   - Copies dist to `client/release/client/{windows,linux}/`
   - Creates archives: `.zip` (Windows), `.tar.gz` (Linux)
   - Copies `changelog.json` to `client/release/client/`

### Output structure

```
client/release/client/
  changelog.json
  windows/
    manifest.json
    entropia-nexus.exe
    _internal/...
    entropia-nexus-X.Y.Z-windows.zip
  linux/
    manifest.json
    entropia-nexus
    _internal/...
    entropia-nexus-X.Y.Z-linux.tar.gz
```

## 3. Upload to Server

The client updater fetches from `{nexus_base_url}/client/{platform}/manifest.json`.

### Full upload (both platforms + changelog)

```bash
rsync -avz --delete client/release/client/ server:/path/to/static/client/
```

### Per-platform upload

```bash
rsync -avz --delete client/release/client/windows/ server:/path/to/static/client/windows/
rsync -avz --delete client/release/client/linux/   server:/path/to/static/client/linux/
scp client/release/client/changelog.json server:/path/to/static/client/
```

The `changelog.json` must always be uploaded alongside platform files — the updater fetches it to show "What's new" in the update dialog.

## 4. How Updates Reach Users

The client's delta update system (`client/updater.py`):

1. Checks `{nexus_base_url}/client/{platform}/manifest.json` every hour (5s after startup, 5min retry on failure)
2. Compares SHA-256 hashes with the local `manifest.json`
3. Downloads only changed/new files to a staging directory
4. On user confirmation, applies the update by replacing files and restarting

Users can also download the full archive from the website for fresh installs.

## Checklist

- [ ] Changelog updated with all user-facing changes
- [ ] VERSION file matches the tag
- [ ] `git tag client-X.Y.Z` set on the release commit
- [ ] Build completes without errors on both platforms
- [ ] Quick smoke test: run the built executable, verify version in settings
- [ ] Upload release files to server
- [ ] Verify update is detected by an existing installation
