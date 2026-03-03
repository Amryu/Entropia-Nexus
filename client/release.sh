#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Entropia Nexus Client — Release Script
#
# Builds the client for Windows (native) and Linux (via WSL), then packages
# everything into a release directory matching the server's /static/client/
# layout. Upload the output directory to the server to publish.
#
# Usage:
#   ./client/release.sh                    Build both platforms
#   ./client/release.sh --windows-only     Build Windows only
#   ./client/release.sh --linux-only       Build Linux only
#   ./client/release.sh --skip-build       Package existing dist (no rebuild)
#
# Output:  client/release/client/
#   changelog.json
#   windows/
#     manifest.json
#     entropia-nexus.exe
#     _internal/...
#     entropia-nexus-<version>-windows.zip
#   linux/
#     manifest.json
#     entropia-nexus
#     _internal/...
#     entropia-nexus-<version>-linux.tar.gz
#
# Upload:
#   rsync -avz --delete client/release/client/ server:/path/to/static/client/
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Parse arguments ──────────────────────────────────────────────────────────

BUILD_WINDOWS=true
BUILD_LINUX=true
SKIP_BUILD=false

for arg in "$@"; do
    case "$arg" in
        --windows-only) BUILD_LINUX=false ;;
        --linux-only)   BUILD_WINDOWS=false ;;
        --skip-build)   SKIP_BUILD=true ;;
        --help|-h)
            sed -n '2,/^# ──/{ /^# ──/d; s/^# \?//p; }' "$0"
            exit 0
            ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ── Helpers ──────────────────────────────────────────────────────────────────

red()   { printf '\033[1;31m%s\033[0m\n' "$*"; }
green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
cyan()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
die()   { red "ERROR: $*" >&2; exit 1; }

# ── Validate environment ────────────────────────────────────────────────────

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if command -v cygpath &>/dev/null; then
    ROOT_U="$(cygpath -u "$ROOT")"
    ROOT_W="$(cygpath -w "$ROOT")"
else
    ROOT_U="$ROOT"
    ROOT_W="$ROOT"
fi

[[ -d "$ROOT_U/client" ]] || die "Run from the project root (could not find client/)."
[[ -f "$ROOT_U/client/build.sh" ]] || die "build.sh not found."

# ── Read version ─────────────────────────────────────────────────────────────

VERSION_FILE="$ROOT_U/client/VERSION"
[[ -f "$VERSION_FILE" ]] || die "client/VERSION not found."
VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
[[ -n "$VERSION" ]] || die "client/VERSION is empty."

APP_NAME="entropia-nexus"
DIST_DIR="$ROOT_U/client/dist"
RELEASE_DIR="$ROOT_U/client/release/client"

bold "═══════════════════════════════════════════════"
bold "  Entropia Nexus Client — Release v$VERSION"
bold "═══════════════════════════════════════════════"
echo ""

# ── WSL detection ────────────────────────────────────────────────────────────

WSL_ROOT=""
if $BUILD_LINUX; then
    if command -v wsl.exe &>/dev/null || command -v wsl &>/dev/null; then
        # Convert Windows path to WSL mount path
        # C:\Users\Foo\Project -> /mnt/c/Users/Foo/Project
        DRIVE=$(echo "$ROOT_W" | head -c1 | tr '[:upper:]' '[:lower:]')
        TAIL=$(echo "$ROOT_W" | sed 's|^.:\\||; s|\\|/|g')
        WSL_ROOT="/mnt/$DRIVE/$TAIL"
        cyan "WSL project path: $WSL_ROOT"
    else
        red "WSL not found — cannot build Linux version."
        if $BUILD_WINDOWS; then
            cyan "Continuing with Windows only."
            BUILD_LINUX=false
        else
            die "WSL is required for Linux builds."
        fi
    fi
fi

# ── Prepare release directory ────────────────────────────────────────────────

mkdir -p "$RELEASE_DIR"

# Only clear the platform directories we're actually building
$BUILD_WINDOWS && rm -rf "$RELEASE_DIR/windows"
$BUILD_LINUX   && rm -rf "$RELEASE_DIR/linux"

# Copy changelog to platform-independent location
CHANGELOG_SRC="$ROOT_U/client/data/changelog.json"
if [[ -f "$CHANGELOG_SRC" ]]; then
    cp "$CHANGELOG_SRC" "$RELEASE_DIR/changelog.json"
    cyan "Copied changelog.json"
else
    red "Warning: changelog.json not found"
fi

# ── Helper: package a platform build into the release dir ────────────────────

package_platform() {
    local PLATFORM="$1"   # "windows" or "linux"
    local BINARY="$2"     # "entropia-nexus.exe" or "entropia-nexus"
    local ARCHIVE_EXT="$3" # "zip" or "tar.gz"

    local SRC="$DIST_DIR/$APP_NAME"
    local DEST="$RELEASE_DIR/$PLATFORM"

    [[ -f "$SRC/$BINARY" ]] || die "$PLATFORM build not found: $SRC/$BINARY"

    cyan "Packaging $PLATFORM..."
    mkdir -p "$DEST"

    # Copy all dist files (for delta updates)
    cp -r "$SRC/"* "$DEST/"

    # Create archive (for fresh downloads)
    local ARCHIVE_NAME="${APP_NAME}-${VERSION}-${PLATFORM}.${ARCHIVE_EXT}"

    (
        cd "$DIST_DIR"
        if [[ "$ARCHIVE_EXT" == "zip" ]]; then
            if command -v 7z &>/dev/null; then
                7z a -tzip -mx=7 "$DEST/$ARCHIVE_NAME" "$APP_NAME/" \
                    -x!"$APP_NAME/manifest.json" > /dev/null
            elif command -v zip &>/dev/null; then
                zip -r -9 "$DEST/$ARCHIVE_NAME" "$APP_NAME/" \
                    -x "$APP_NAME/manifest.json" > /dev/null
            elif command -v powershell &>/dev/null; then
                local SRC_WIN DEST_WIN
                SRC_WIN="$(cygpath -w "$SRC" 2>/dev/null || echo "$SRC")"
                DEST_WIN="$(cygpath -w "$DEST/$ARCHIVE_NAME" 2>/dev/null || echo "$DEST/$ARCHIVE_NAME")"
                powershell -NoProfile -Command \
                    "Compress-Archive -Path '$SRC_WIN' -DestinationPath '$DEST_WIN' -Force"
            else
                die "No zip tool found (tried 7z, zip, powershell)."
            fi
        else
            tar czf "$DEST/$ARCHIVE_NAME" --exclude="manifest.json" "$APP_NAME/"
        fi
    )

    local SIZE
    SIZE=$(du -sh "$DEST/$ARCHIVE_NAME" 2>/dev/null | cut -f1 || echo "?")
    green "  $ARCHIVE_NAME ($SIZE)"
}

# ── Build & package Windows ──────────────────────────────────────────────────
# Build order matters: both platforms share client/dist/entropia-nexus/, so we
# build + package each platform before starting the next build.

if $BUILD_WINDOWS; then
    if ! $SKIP_BUILD; then
        echo ""
        bold "──── Building Windows ────"
        echo ""
        bash "$ROOT_U/client/build.sh"
    fi
    echo ""
    package_platform "windows" "$APP_NAME.exe" "zip"
fi

# ── Build & package Linux (via WSL) ─────────────────────────────────────────

if $BUILD_LINUX; then
    if ! $SKIP_BUILD; then
        echo ""
        bold "──── Building Linux (WSL) ────"
        echo ""
        # Build on the native Linux filesystem to avoid NTFS chmod issues,
        # then copy the result back to client/dist/ for packaging.
        # Uses a temp script file to avoid nested quoting issues (Git Bash → WSL).
        WSL_DEST="$WSL_ROOT/client/dist"
        WSL_SCRIPT="$ROOT_U/client/.wsl-build-tmp.sh"
        cat > "$WSL_SCRIPT" << WSLEOF
#!/usr/bin/env bash
set -euo pipefail
source ~/entropia-nexus-venv/bin/activate
python -m pip install --quiet -r "$WSL_ROOT/client/requirements.txt"

LINUX_BUILD=~/entropia-nexus-build
export NEXUS_DIST_DIR="\$LINUX_BUILD/dist"
export NEXUS_BUILD_DIR="\$LINUX_BUILD/build"
rm -rf "\$LINUX_BUILD"
mkdir -p "\$NEXUS_DIST_DIR" "\$NEXUS_BUILD_DIR"

cd "$WSL_ROOT" && bash client/build.sh

# Replace symlinks with hardlinks — NTFS cannot store Linux symlinks
find "\$NEXUS_DIST_DIR/$APP_NAME" -type l | while IFS= read -r link; do
    target=\$(readlink -f "\$link")
    rm "\$link"
    ln "\$target" "\$link"
done

# Copy result back to the Windows filesystem
rm -rf "$WSL_DEST/$APP_NAME"
mkdir -p "$WSL_DEST"
cp -r "\$NEXUS_DIST_DIR/$APP_NAME" "$WSL_DEST/$APP_NAME"

echo "Copied \$(find "$WSL_DEST/$APP_NAME" -type f | wc -l) files to Windows filesystem"
WSLEOF
        MSYS_NO_PATHCONV=1 wsl bash "$WSL_ROOT/client/.wsl-build-tmp.sh"
        rm -f "$WSL_SCRIPT"
    fi
    echo ""
    package_platform "linux" "$APP_NAME" "tar.gz"
fi

# ── Verify release ──────────────────────────────────────────────────────────

echo ""
bold "──── Release Contents ────"
echo ""
cyan "client/release/client/"

[[ -f "$RELEASE_DIR/changelog.json" ]] && echo "  changelog.json"

if $BUILD_WINDOWS && [[ -d "$RELEASE_DIR/windows" ]]; then
    local_count=$(find "$RELEASE_DIR/windows" -type f | wc -l)
    local_size=$(du -sh "$RELEASE_DIR/windows" 2>/dev/null | cut -f1)
    echo "  windows/  ($local_count files, $local_size)"
fi

if $BUILD_LINUX && [[ -d "$RELEASE_DIR/linux" ]]; then
    local_count=$(find "$RELEASE_DIR/linux" -type f | wc -l)
    local_size=$(du -sh "$RELEASE_DIR/linux" 2>/dev/null | cut -f1)
    echo "  linux/    ($local_count files, $local_size)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
TOTAL_SIZE=$(du -sh "$RELEASE_DIR" 2>/dev/null | cut -f1 || echo "?")
green "═══════════════════════════════════════════════"
green "  Release v$VERSION ready! ($TOTAL_SIZE)"
green "═══════════════════════════════════════════════"
echo ""
cyan "Upload to server:"
echo "  rsync -avz --delete client/release/client/ yourserver:/path/to/static/client/"
echo ""
cyan "Or upload platforms individually:"
$BUILD_WINDOWS && echo "  rsync -avz --delete client/release/client/windows/ yourserver:/path/to/static/client/windows/"
$BUILD_LINUX   && echo "  rsync -avz --delete client/release/client/linux/   yourserver:/path/to/static/client/linux/"
echo "  scp client/release/client/changelog.json yourserver:/path/to/static/client/"
echo ""
