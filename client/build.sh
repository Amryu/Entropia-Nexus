#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Entropia Nexus Client — Build Script
#
# Produces a standalone executable for the current platform using PyInstaller.
#
# Usage:  ./client/build.sh          (run from project root)
#
# Output: client/dist/entropia-nexus/
#   Windows: entropia-nexus.exe + _internal/
#   Linux:   entropia-nexus     + _internal/
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_NAME="entropia-nexus"

# Assets & data to bundle  (source → destination inside _internal/)
# Directories are included whole — adding files to them requires zero changes.
BUNDLE_DIRS=(
    "client/assets:client/assets"
    "nexus/src/lib/utils:nexus/src/lib/utils"
)
BUNDLE_FILES=(
    "client/data/skill_reference.json:client/data"
    "client/data/skill_ranks.json:client/data"
    "common/itemTypes.js:common"
    "client/VERSION:client"
)

# Hidden imports that PyInstaller may miss (conditional / lazy imports)
HIDDEN_IMPORTS=(
    PyQt6.QtSvg
    PyQt6.QtWebEngineWidgets
    PyQt6.QtWebEngineCore
    keyring.backends
    keyring.backends.Windows
    keyring.backends.SecretService
)

# ── Helpers ──────────────────────────────────────────────────────────────────

red()   { printf '\033[1;31m%s\033[0m\n' "$*"; }
green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
cyan()  { printf '\033[1;36m%s\033[0m\n' "$*"; }

die() { red "ERROR: $*" >&2; exit 1; }

# ── Validate environment ────────────────────────────────────────────────────

[[ -d "client" ]] || die "Run this script from the project root (could not find client/)."
[[ -d "nexus"  ]] || die "Run this script from the project root (could not find nexus/)."
[[ -f "client/run_client.py" ]] || die "Entry point not found: client/run_client.py"

# ── Detect platform ─────────────────────────────────────────────────────────

case "$OSTYPE" in
    msys*|cygwin*|mingw*|win*)
        PLATFORM="windows"
        SEP=";"
        ;;
    linux*)
        PLATFORM="linux"
        SEP=":"
        ;;
    darwin*)
        PLATFORM="macos"
        SEP=":"
        ;;
    *)
        die "Unsupported platform: $OSTYPE"
        ;;
esac

cyan "Platform: $PLATFORM"

# ── Resolve absolute project root ────────────────────────────────────────────
# PyInstaller resolves --add-data relative to the spec file, so we use
# absolute paths. On MSYS/Git Bash convert to native Windows paths.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
    ROOT="$(cygpath -w "$ROOT")"
fi

ENTRY_POINT="${ROOT}/client/run_client.py"
DIST_DIR="${ROOT}/client/dist"
BUILD_DIR="${ROOT}/client/build"

# ── Ensure PyInstaller is installed ──────────────────────────────────────────

if ! python -m PyInstaller --version &>/dev/null; then
    cyan "PyInstaller not found. Installing..."
    pip install pyinstaller || die "Failed to install PyInstaller."
fi

cyan "PyInstaller $(python -m PyInstaller --version)"

# ── Build --add-data arguments (absolute paths) ─────────────────────────────

DATA_ARGS=()

for entry in "${BUNDLE_DIRS[@]}"; do
    src="${ROOT}/${entry%%:*}"
    dst="${entry#*:}"
    # Existence check needs MSYS-compatible path
    if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
        check_path="$(cygpath -u "$src")"
    else
        check_path="$src"
    fi
    [[ -d "$check_path" ]] || die "Bundle directory not found: $src"
    DATA_ARGS+=( --add-data "${src}${SEP}${dst}" )
done

for entry in "${BUNDLE_FILES[@]}"; do
    src="${ROOT}/${entry%%:*}"
    dst="${entry#*:}"
    if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
        check_path="$(cygpath -u "$src")"
    else
        check_path="$src"
    fi
    [[ -f "$check_path" ]] || die "Bundle file not found: $src"
    DATA_ARGS+=( --add-data "${src}${SEP}${dst}" )
done

# ── Build --hidden-import arguments ──────────────────────────────────────────

IMPORT_ARGS=()
for mod in "${HIDDEN_IMPORTS[@]}"; do
    IMPORT_ARGS+=( --hidden-import "$mod" )
done

# ── Platform-specific flags ──────────────────────────────────────────────────

PLATFORM_ARGS=()
if [[ "$PLATFORM" == "windows" ]]; then
    PLATFORM_ARGS+=( --windowed )
    PLATFORM_ARGS+=( --icon "${ROOT}/client/assets/logo.png" )
elif [[ "$PLATFORM" == "linux" ]]; then
    PLATFORM_ARGS+=( --console --strip )
fi

# ── Clean previous build ─────────────────────────────────────────────────────

if [[ -d "$DIST_DIR/$APP_NAME" ]]; then
    cyan "Removing previous build..."
    rm -rf "$DIST_DIR/$APP_NAME"
fi

# ── Run PyInstaller ──────────────────────────────────────────────────────────

cyan "Building $APP_NAME..."

python -m PyInstaller \
    --name "$APP_NAME" \
    --onedir \
    --noconfirm \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR" \
    --specpath "${ROOT}/client" \
    --collect-all py_mini_racer \
    "${DATA_ARGS[@]}" \
    "${IMPORT_ARGS[@]}" \
    "${PLATFORM_ARGS[@]}" \
    "$ENTRY_POINT"

# ── Post-build: strip unnecessary bulk ─────────────────────────────────────

INTERNAL="$DIST_DIR/$APP_NAME/_internal"
if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
    INTERNAL_CHECK="$(cygpath -u "$INTERNAL")"
else
    INTERNAL_CHECK="$INTERNAL"
fi

if [[ -d "$INTERNAL_CHECK" ]]; then
    cyan "Stripping unnecessary files..."
    SAVED=0

    # 1. Debug .pak / .bin files (~83 MB)
    while IFS= read -r f; do
        sz=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
        SAVED=$((SAVED + sz))
        rm -f "$f"
    done < <(find "$INTERNAL_CHECK" \( -name '*.debug.pak' -o -name '*.debug.bin' \) -type f)

    # 2. DevTools resources (~11 MB)
    while IFS= read -r f; do
        sz=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
        SAVED=$((SAVED + sz))
        rm -f "$f"
    done < <(find "$INTERNAL_CHECK" -name 'qtwebengine_devtools_resources.pak' -type f)

    # 3. Non-en-US WebEngine locales (~40 MB)
    while IFS= read -r f; do
        base="$(basename "$f")"
        if [[ "$base" != "en-US.pak" ]]; then
            sz=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
            SAVED=$((SAVED + sz))
            rm -f "$f"
        fi
    done < <(find "$INTERNAL_CHECK" -path '*/qtwebengine_locales/*.pak' -type f)

    # 4. Qt Quick 3D DLLs — not used (~14 MB)
    while IFS= read -r f; do
        sz=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
        SAVED=$((SAVED + sz))
        rm -f "$f"
    done < <(find "$INTERNAL_CHECK" -name 'Qt6Quick3D*' -type f)

    SAVED_MB=$((SAVED / 1048576))
    cyan "  Stripped ~${SAVED_MB} MB of unnecessary files."
fi

# ── Post-build: generate manifest.json ──────────────────────────────────────

VERSION_FILE="${ROOT}/client/VERSION"
if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
    VERSION_CHECK="$(cygpath -u "$VERSION_FILE")"
else
    VERSION_CHECK="$VERSION_FILE"
fi
[[ -f "$VERSION_CHECK" ]] || die "Version file not found: $VERSION_FILE — create client/VERSION"

cyan "Generating manifest.json..."

MANIFEST_DIST="$DIST_DIR/$APP_NAME"
if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
    MANIFEST_DIST_CHECK="$(cygpath -u "$MANIFEST_DIST")"
else
    MANIFEST_DIST_CHECK="$MANIFEST_DIST"
fi

python -c "
import hashlib, json, os, sys
from datetime import datetime, timezone

dist_dir = sys.argv[1]
version_file = sys.argv[2]
platform = sys.argv[3]

with open(version_file) as f:
    version = f.read().strip()

files = {}
for root, dirs, filenames in os.walk(dist_dir):
    for fname in filenames:
        full = os.path.join(root, fname)
        rel = os.path.relpath(full, dist_dir).replace(os.sep, '/')
        if rel == 'manifest.json':
            continue
        h = hashlib.sha256()
        with open(full, 'rb') as fh:
            for chunk in iter(lambda: fh.read(65536), b''):
                h.update(chunk)
        files[rel] = {
            'sha256': h.hexdigest(),
            'size': os.path.getsize(full),
        }

manifest = {
    'version': version,
    'platform': platform,
    'build_date': datetime.now(timezone.utc).isoformat(),
    'files': files,
}

out = os.path.join(dist_dir, 'manifest.json')
with open(out, 'w') as f:
    json.dump(manifest, f, indent=2)

print(f'  Manifest: {len(files)} files, version {version}')
" "$MANIFEST_DIST_CHECK" "$VERSION_CHECK" "$PLATFORM"

# ── Post-build: copy config template ────────────────────────────────────────

CONFIG_SRC="${ROOT}/client/config.example.json"
if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
    CONFIG_SRC_CHECK="$(cygpath -u "$CONFIG_SRC")"
else
    CONFIG_SRC_CHECK="$CONFIG_SRC"
fi
if [[ -f "$CONFIG_SRC_CHECK" ]]; then
    cp "$CONFIG_SRC_CHECK" "$DIST_DIR/$APP_NAME/config.example.json"
    cyan "Copied config.example.json into output."
fi

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
green "Build complete!"
echo ""

OUT="$DIST_DIR/$APP_NAME"
if [[ "$PLATFORM" == "windows" ]]; then
    EXE="$OUT/$APP_NAME.exe"
else
    EXE="$OUT/$APP_NAME"
fi

# Use MSYS-compatible paths for file checks in summary
if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
    OUT_CHECK="$(cygpath -u "$OUT")"
    EXE_CHECK="$(cygpath -u "$EXE")"
else
    OUT_CHECK="$OUT"
    EXE_CHECK="$EXE"
fi

if [[ -f "$EXE_CHECK" ]]; then
    FILE_COUNT=$(find "$OUT_CHECK" -type f | wc -l)
    TOTAL_SIZE=$(du -sh "$OUT_CHECK" 2>/dev/null | cut -f1 || echo "unknown")
    cyan "  Output:  $OUT/"
    cyan "  Binary:  $EXE"
    cyan "  Files:   $FILE_COUNT"
    cyan "  Size:    $TOTAL_SIZE"
    echo ""
    cyan "Next steps:"
    echo "  1. cd $OUT"
    echo "  2. cp config.example.json config.json"
    echo "  3. Edit config.json with your settings"
    if [[ "$PLATFORM" == "windows" ]]; then
        echo "  4. ./$APP_NAME.exe"
    else
        echo "  4. ./$APP_NAME"
    fi
else
    red "Expected executable not found at $EXE"
    exit 1
fi
