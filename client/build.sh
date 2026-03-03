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
    "client/data/changelog.json:client/data"
    "common/itemTypes.js:common"
    "client/VERSION:client"
)

# Hidden imports that PyInstaller may miss (conditional / lazy imports)
HIDDEN_IMPORTS=(
    PyQt6.QtSvg
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
DIST_DIR="${NEXUS_DIST_DIR:-${ROOT}/client/dist}"
BUILD_DIR="${NEXUS_BUILD_DIR:-${ROOT}/client/build}"

# ── Install dependencies ──────────────────────────────────────────────────────

cyan "Installing dependencies..."
python -m pip install --quiet -r "${ROOT}/client/requirements.txt" \
    || die "Failed to install requirements."

if ! python -m PyInstaller --version &>/dev/null; then
    cyan "PyInstaller not found. Installing..."
    python -m pip install pyinstaller || die "Failed to install PyInstaller."
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
    rm -rf "$DIST_DIR/$APP_NAME" 2>/dev/null || true
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

    # Helper: delete matching files and tally saved bytes
    strip_files() {
        while IFS= read -r f; do
            sz=$(stat -c%s "$f" 2>/dev/null || stat -f%z "$f" 2>/dev/null || echo 0)
            SAVED=$((SAVED + sz))
            rm -f "$f"
        done
    }

    # Helper: delete matching directories and tally saved bytes
    strip_dirs() {
        while IFS= read -r d; do
            sz=$(du -sb "$d" 2>/dev/null | cut -f1 || echo 0)
            SAVED=$((SAVED + sz))
            rm -rf "$d"
        done
    }

    # 1. Unused Qt6 module libraries (.dll on Windows, .so* on Linux)
    #    Keep: QtWidgets, QtCore, QtGui, QtSvg, QtMultimedia, QtNetwork
    #    Patterns cover both Windows (Qt6Quick.dll) and Linux (libQt6Quick.so.6)
    STRIP_QT6_MODULES=(
        Quick Qml QmlModels QmlMeta QmlWorkerScript Positioning WebChannel
        OpenGL Quick3D RemoteObjects PrintSupport Pdf ShaderTools Sensors
        TextToSpeech WebSockets SpatialAudio XcbQpa EglFSDeviceIntegration
        WaylandClient WlShellIntegration Concurrent DBus
    )
    FIND_QT6_ARGS=()
    for mod in "${STRIP_QT6_MODULES[@]}"; do
        [[ ${#FIND_QT6_ARGS[@]} -gt 0 ]] && FIND_QT6_ARGS+=( -o )
        FIND_QT6_ARGS+=( -name "Qt6${mod}*" -o -name "libQt6${mod}*" )
    done
    find "$INTERNAL_CHECK" \( -type f -o -type l \) \( "${FIND_QT6_ARGS[@]}" \) | strip_files

    # 2. Unused PyQt6 Python bindings (.pyd on Windows, .abi3.so on Linux)
    STRIP_PYQT_MODULES=(
        'QtPrintSupport*' 'QtRemoteObjects*' 'QtQuick*'
        'QtQml*' 'QtPositioning*' 'QtOpenGL*' 'QtDBus*'
    )
    FIND_PYQT_ARGS=()
    for pat in "${STRIP_PYQT_MODULES[@]}"; do
        [[ ${#FIND_PYQT_ARGS[@]} -gt 0 ]] && FIND_PYQT_ARGS+=( -o )
        FIND_PYQT_ARGS+=( -name "$pat" )
    done
    find "$INTERNAL_CHECK" -path '*/PyQt6*' \( -type f -o -type l \) \( "${FIND_PYQT_ARGS[@]}" \) | strip_files

    # 3. Qt5 from OpenCV — OCR uses image ops only, not cv2.imshow()
    find "$INTERNAL_CHECK" \( -type f -o -type l \) \( -name 'Qt5*' -o -name 'libQt5*' \) | strip_files

    # 4. Software OpenGL fallback (Windows only)
    find "$INTERNAL_CHECK" -name 'opengl32sw.dll' \( -type f -o -type l \) | strip_files

    # 5. FFmpeg / video codecs — QSoundEffect plays WAV natively, no FFmpeg needed
    find "$INTERNAL_CHECK" \( -type f -o -type l \) \( \
        -name 'avcodec-*.dll' -o -name 'avformat-*.dll' \
        -o -name 'avutil-*.dll' -o -name 'swresample-*.dll' \
        -o -name 'libavcodec*.so*' -o -name 'libavformat*.so*' \
        -o -name 'libavutil*.so*' -o -name 'libswresample*.so*' \
        -o -name 'libswscale*.so*' -o -name 'libavfilter*.so*' \
        -o -name 'libavdevice*.so*' \
        -o -name 'libaom*.so*' -o -name 'libvpx*.so*' \
        -o -name 'libavif*.so*' \
        \) | strip_files

    # 6. OpenCV video I/O FFmpeg — OCR uses image ops only
    find "$INTERNAL_CHECK" -name 'opencv_videoio_ffmpeg*' \( -type f -o -type l \) | strip_files

    # 7. Qt translations — English-only app
    find "$INTERNAL_CHECK" -path '*/Qt6/translations' -type d | strip_dirs

    # 8. QML directory — pure QWidgets app, no QML files used
    find "$INTERNAL_CHECK" -path '*/Qt6/qml' -type d | strip_dirs

    # 9. Qt positioning plugin
    find "$INTERNAL_CHECK" -path '*/plugins/position' -type d | strip_dirs

    # 10. Qt xcb GL integrations — not needed for overlay/headless use
    find "$INTERNAL_CHECK" -path '*/plugins/xcbglintegrations' -type d | strip_dirs

    # 11. Qt FFmpeg multimedia plugin (Linux .so)
    find "$INTERNAL_CHECK" -name 'libffmpegmediaplugin*' \( -type f -o -type l \) | strip_files
    find "$INTERNAL_CHECK" -name 'libQt6FFmpegStub*' \( -type f -o -type l \) | strip_files

    # 12. Font files — not licensed for distribution; STPK templates provide OCR matching
    find "$INTERNAL_CHECK" -name '*.ttf' \( -type f -o -type l \) | strip_files

    # 13. Qt6 platform plugins not needed on desktop
    find "$INTERNAL_CHECK" -path '*/plugins/platforms*' \( -type f -o -type l \) \( \
        -name 'libqlinuxfb*' -o -name 'libqvkkhrdisplay*' \
        -o -name 'libqvnc*' -o -name 'libqoffscreen*' \
        \) | strip_files
    find "$INTERNAL_CHECK" -path '*/plugins/generic*' -name 'libqtuiotouchplugin*' \
        \( -type f -o -type l \) | strip_files

    # 14. OpenCV Qt platform plugins — not using cv2.imshow()
    find "$INTERNAL_CHECK" -path '*/cv2/qt*' -type d | strip_dirs

    SAVED_MB=$((SAVED / 1048576))
    cyan "  Stripped ~${SAVED_MB} MB of unnecessary files."
fi

# ── Post-build: resolve version ─────────────────────────────────────────────
# Prefer git tag (e.g. "client-1.2.0"), fall back to client/VERSION file.
# Tags must match: client-<semver>  (the "client-" prefix is stripped).

VERSION=""
if command -v git &>/dev/null && git rev-parse --git-dir &>/dev/null 2>&1; then
    GIT_DESC="$(git describe --tags --match 'client-*' --abbrev=0 2>/dev/null || true)"
    if [[ -n "$GIT_DESC" ]]; then
        VERSION="${GIT_DESC#client-}"   # strip "client-" prefix
    fi
fi

if [[ -z "$VERSION" ]]; then
    VERSION_FILE="${ROOT}/client/VERSION"
    if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
        VERSION_CHECK="$(cygpath -u "$VERSION_FILE")"
    else
        VERSION_CHECK="$VERSION_FILE"
    fi
    if [[ -f "$VERSION_CHECK" ]]; then
        VERSION="$(cat "$VERSION_CHECK" | tr -d '[:space:]')"
    fi
fi

[[ -n "$VERSION" ]] || die "No version found — tag with 'git tag client-X.Y.Z' or create client/VERSION"
cyan "Version: $VERSION"

# Write resolved version into the bundled VERSION file so the client reads it
BUNDLED_VERSION="$DIST_DIR/$APP_NAME/_internal/client/VERSION"
if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
    BUNDLED_CHECK="$(cygpath -u "$BUNDLED_VERSION")"
else
    BUNDLED_CHECK="$BUNDLED_VERSION"
fi
if [[ -f "$BUNDLED_CHECK" ]]; then
    echo "$VERSION" > "$BUNDLED_CHECK"
fi

# ── Post-build: generate manifest.json ──────────────────────────────────────

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
version = sys.argv[2]
platform = sys.argv[3]

files = {}
for root, dirs, filenames in os.walk(dist_dir):
    for fname in filenames:
        full = os.path.join(root, fname)
        if not os.path.isfile(full):
            continue  # skip broken symlinks
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
" "$MANIFEST_DIST_CHECK" "$VERSION" "$PLATFORM"

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
