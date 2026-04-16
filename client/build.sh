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
    "client/loadout/generated:client/loadout/generated"
)
BUNDLE_FILES=(
    "client/data/skill_reference.json:client/data"
    "client/data/skill_ranks.json:client/data"
    "client/data/changelog.json:client/data"
    "client/VERSION:client"
)

# Hidden imports that PyInstaller may miss (conditional / lazy imports)
HIDDEN_IMPORTS=(
    PyQt6.QtSvg
    PyQt6.QtMultimedia
    PyQt6.QtMultimediaWidgets
    keyring.backends
    keyring.backends.Windows
    keyring.backends.SecretService
    win32ctypes.pywin32.win32cred
    win32ctypes.pywin32.pywintypes
    sounddevice
    _sounddevice_data
    obsws_python
    mpv
    streamlink
    streamlink.plugins
    trio
    trio._core
    websockets
    websockets.sync
    websockets.sync.client
    client.overlay.custom_grid.builtin._common
    client.overlay.custom_grid.builtin.button_widget
    client.overlay.custom_grid.builtin.clock_widget
    client.overlay.custom_grid.builtin.event_log
    client.overlay.custom_grid.builtin.exchange_price
    client.overlay.custom_grid.builtin.graph_widget
    client.overlay.custom_grid.builtin.hunt_stats
    client.overlay.custom_grid.builtin.label_widget
    client.overlay.custom_grid.builtin.loot_list
    client.overlay.custom_grid.builtin.mob_info
    client.overlay.custom_grid.builtin.player_status
    client.overlay.custom_grid.builtin.skill_gain
    client.overlay.custom_grid.builtin.stat_label
    client.overlay.custom_grid.builtin.timer_widget
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

# ── Regenerate transpiled loadout modules ────────────────────────────────────
# Parses the shared JS files via acorn (Node) and writes idiomatic Python
# into client/loadout/generated/. Required before PyInstaller picks up the
# client package, otherwise release builds ship a stale port.
command -v node &>/dev/null || die "node not found — required by the loadout transpiler"
cyan "Regenerating client/loadout/generated/ from JS sources..."
( cd "${ROOT}" && python -m client.loadout.transpile --force ) \
    || die "Transpile step failed — aborting build."

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
    # Generate version info so Task Manager shows "Entropia Nexus Client"
    VERSION_INFO="${BUILD_DIR}/version_info.txt"
    python "${ROOT}/client/version_info.py" > "$VERSION_INFO"
    PLATFORM_ARGS+=( --version-file "$VERSION_INFO" )
elif [[ "$PLATFORM" == "linux" ]]; then
    PLATFORM_ARGS+=( --console --strip )
    # Bundle desktop entry file for Linux
    BUNDLE_FILES+=( "client/assets/entropia-nexus.desktop:client/assets" )
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
    --collect-all sounddevice \
    --collect-all onnxruntime \
    --collect-all numpy \
    --collect-all streamlink \
    --exclude-module onnxruntime.transformers \
    --exclude-module onnxruntime.quantization \
    --exclude-module onnxruntime.tools \
    --exclude-module onnxruntime.datasets \
    --exclude-module sympy \
    --exclude-module mpmath \
    --exclude-module onnxtr \
    --exclude-module scipy \
    --exclude-module pyautogui \
    --exclude-module 'numpy._core._multiarray_tests' \
    --exclude-module 'numpy._core._umath_tests' \
    --exclude-module 'numpy._core._struct_ufunc_tests' \
    --exclude-module 'numpy._core._rational_tests' \
    --exclude-module 'numpy._core._operand_flag_tests' \
    --exclude-module 'numpy._core._simd' \
    --exclude-module 'numpy.random' \
    --exclude-module 'numpy.fft' \
    --exclude-module 'PIL.ImageMath' \
    --exclude-module '_multiprocessing' \
    --exclude-module '_decimal' \
    --exclude-module '_yaml' \
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
        WaylandClient WlShellIntegration Concurrent
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
        'QtQml*' 'QtPositioning*' 'QtOpenGL*'
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

    # 5. FFmpeg / video codecs — kept for QMediaPlayer (gallery) and cv2.VideoCapture (backgrounds)

    # 6. OpenCV video I/O FFmpeg — kept for cv2.VideoCapture (background video loading)

    # 7. Qt translations — English-only app
    find "$INTERNAL_CHECK" -path '*/Qt6/translations' -type d | strip_dirs

    # 8. QML directory — pure QWidgets app, no QML files used
    find "$INTERNAL_CHECK" -path '*/Qt6/qml' -type d | strip_dirs

    # 9. Qt positioning plugin
    find "$INTERNAL_CHECK" -path '*/plugins/position' -type d | strip_dirs

    # 10. Qt xcb GL integrations — not needed for overlay/headless use
    find "$INTERNAL_CHECK" -path '*/plugins/xcbglintegrations' -type d | strip_dirs

    # 11. Qt FFmpeg multimedia plugin — kept for QMediaPlayer (gallery video playback)

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

    # 15. onnxruntime offline tools — only inference (capi) is used
    find "$INTERNAL_CHECK" -path '*/onnxruntime/transformers' -type d | strip_dirs
    find "$INTERNAL_CHECK" -path '*/onnxruntime/quantization' -type d | strip_dirs
    find "$INTERNAL_CHECK" -path '*/onnxruntime/tools' -type d | strip_dirs
    find "$INTERNAL_CHECK" -path '*/onnxruntime/datasets' -type d | strip_dirs

    # 16. sympy/mpmath — transitive onnxruntime deps, only for symbolic shape inference
    find "$INTERNAL_CHECK" -path '*/sympy' -type d | strip_dirs
    find "$INTERNAL_CHECK" -path '*/mpmath' -type d | strip_dirs

    SAVED_MB=$((SAVED / 1048576))
    cyan "  Stripped ~${SAVED_MB} MB of unnecessary files."
fi

# ── Post-build: resolve version ─────────────────────────────────────────────
# Read version from client/VERSION file (single source of truth).

VERSION=""
VERSION_FILE="${ROOT}/client/VERSION"
if [[ "$PLATFORM" == "windows" ]] && command -v cygpath &>/dev/null; then
    VERSION_CHECK="$(cygpath -u "$VERSION_FILE")"
else
    VERSION_CHECK="$VERSION_FILE"
fi
if [[ -f "$VERSION_CHECK" ]]; then
    VERSION="$(cat "$VERSION_CHECK" | tr -d '[:space:]')"
fi

[[ -n "$VERSION" ]] || die "No version found — create client/VERSION with the version number"
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

# Filename substrings that identify the 'video' optional group.
# These provide video capture, audio recording, and gallery playback.
# NOTE: QtMultimedia (without 'Widgets') is NOT included — needed for QSoundEffect (core).
VIDEO_KEYWORDS = [
    'avcodec', 'avformat', 'avutil', 'swresample', 'swscale',
    'avfilter', 'avdevice',
    'opencv_videoio_ffmpeg',
    'ffmpegmediaplugin', 'Qt6FFmpegStub',
    'sounddevice', '_sounddevice_data', 'portaudio',
    'MultimediaWidgets',
]

def get_file_group(rel_path):
    low = rel_path.lower()
    for kw in VIDEO_KEYWORDS:
        if kw.lower() in low:
            return 'video'
    return None

files = {}
group_sizes = {}
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
        size = os.path.getsize(full)
        entry = {
            'sha256': h.hexdigest(),
            'size': size,
        }
        group = get_file_group(rel)
        if group:
            entry['group'] = group
            group_sizes[group] = group_sizes.get(group, 0) + size
        files[rel] = entry

manifest = {
    'version': version,
    'platform': platform,
    'build_date': datetime.now(timezone.utc).isoformat(),
    'groups': {
        name: {'description': 'Video capture, audio recording, and gallery playback', 'size': total}
        for name, total in group_sizes.items()
    },
    'files': files,
}

out = os.path.join(dist_dir, 'manifest.json')
with open(out, 'w') as f:
    json.dump(manifest, f, indent=2)

core_count = sum(1 for f in files.values() if 'group' not in f)
for name, total in group_sizes.items():
    count = sum(1 for f in files.values() if f.get('group') == name)
    print(f'  Group \"{name}\": {count} files, {total / 1048576:.1f} MB')
print(f'  Manifest: {len(files)} files ({core_count} core), version {version}')
" "$MANIFEST_DIST_CHECK" "$VERSION" "$PLATFORM"

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
