# Skill Scanner Pipeline

The skill scanner reads skill data from the in-game SKILLS panel via OCR. It captures the game window, detects the skills panel, reads skill names/ranks/progress using font-based template matching, and displays results in the client UI and as an in-game overlay.

## Architecture Overview

```
                        ┌──────────────────────────────┐
                        │       Game Window             │
                        │  ┌────────────────────────┐   │
                        │  │    SKILLS Panel         │   │
                        │  │  ┌──────┬────┬───────┐  │   │
                        │  │  │ Name │Rank│Points │  │   │
                        │  │  ├──────┼────┼───────┤  │   │
                        │  │  │ Aim  │ II │  1234 │  │   │
                        │  │  │ ...  │... │  ...  │  │   │
                        │  │  └──────┴────┴───────┘  │   │
                        │  └────────────────────────┘   │
                        └──────────────────────────────┘
                                     │
                            PrintWindow capture
                                     ▼
┌──────────────────────────────────────────────────────────┐
│                    OCR Thread (daemon)                     │
│                                                           │
│  Detector ──→ Preprocessor ──→ FontMatcher ──→ Results    │
│  (find panel)  (threshold)     (template match) (package) │
│                                                           │
└───────────────────────┬──────────────────────────────────┘
                        │ EventBus
                        ▼
┌──────────────────────────────────────────────────────────┐
│                   Main Qt Thread                          │
│                                                           │
│  AppSignals ──→ SkillsPage (results table, skill cards)   │
│             ──→ ScanHighlightOverlay (green row markers)  │
└──────────────────────────────────────────────────────────┘
```

**Threading model**: The OCR pipeline runs in a dedicated daemon thread (`ocr-scan`). It publishes events via `EventBus` (thread-safe). The `AppSignals` class bridges these to Qt signals for main-thread UI updates.

## File Map

| File | Purpose |
|------|---------|
| `client/ocr/orchestrator.py` | Core pipeline coordinator — `ScanOrchestrator` class |
| `client/ocr/detector.py` | Skills panel detection via template matching, ROI management |
| `client/ocr/font_matcher.py` | Font-based template rendering + matching (PIL → OpenCV) |
| `client/ocr/capturer.py` | Win32 `PrintWindow` screen capture (ignores overlays) |
| `client/ocr/preprocessor.py` | Image preprocessing: grayscale, threshold, row/column extraction |
| `client/ocr/skill_parser.py` | `SkillMatcher` (fuzzy name matching) + `RankVerifier` (rank validation) |
| `client/ocr/progress_bar.py` | HSV-based progress bar fill reading with sub-pixel precision |
| `client/ocr/navigator.py` | Pagination text parsing, skill category list |
| `client/ocr/models.py` | Data models: `SkillReading`, `SkillScanResult`, `ScanProgress` |
| `client/overlay/scan_highlight_overlay.py` | Qt overlay — green row highlights + checkmarks |
| `client/overlay/scan_overlay.py` | Tkinter debug overlay (legacy/fallback) |
| `client/ui/pages/skills_page.py` | Skills page UI — scan trigger, results display |
| `client/ui/dialogs/scan_roi_dialog.py` | ROI calibration dialog with live preview |
| `client/core/constants.py` | Event type constants (`EVENT_OCR_*`, `EVENT_DEBUG_*`) |
| `client/ui/signals.py` | EventBus → Qt signal bridge (`AppSignals`) |
| `client/app.py` | Pipeline startup (`_start_ocr_pipeline`) + overlay creation |
| `client/core/config.py` | Scan-related config keys |

## Pipeline Stages

### Stage 1: Trigger

Three ways to start scanning:

| Trigger | Entry Point | Notes |
|---------|-------------|-------|
| **Automatic** | `app.py:_start_ocr_pipeline()` | Daemon thread launched on startup, calls `ScanOrchestrator.run_continuous()` |
| **Manual** | Skills page "Run Manual Scan" button | Emits `trigger_ocr_scan` signal |
| **Hotkey** | F7 (config: `hotkey_ocr_scan`) | Currently disabled in hotkey manager |

### Stage 2: Window Detection

**File**: `detector.py` — `SkillsWindowDetector.detect()`

1. Finds the game window by title prefix (`"Entropia Universe Client"`)
2. Captures the full game window via `PrintWindow`
3. Template-matches the "SKILLS" title band within the capture
4. Returns screen-absolute window bounds `(x, y, w, h)`

Polling: every `DETECT_POLL_INTERVAL` (1.0s), timeout after `DETECT_TIMEOUT` (120s). Skips expensive capture when game is not the foreground window (`is_game_foreground()` check, <0.1ms vs ~100ms).

### Stage 3: Stability Check

**File**: `orchestrator.py` — `_wait_for_stable_window()`

Waits for `STABILITY_TICKS` (3) consecutive matching positions at `STABILITY_POLL_INTERVAL` (0.1s) intervals. Uses `quick_verify()` to confirm the panel header is still at the expected location. Prevents scanning a panel that's being dragged.

### Stage 4: Layout Computation

**File**: `orchestrator.py` — `_compute_layout()`

Resolves all derived coordinates needed for cropping and scanning:

- **ROIs**: From `DEFAULT_ROI_PIXELS` (pixel positions measured from a 557×668px reference) + user overrides from `scan_roi_overrides` config
- **Column ranges**: Template-matches column headers (SKILL NAME, RANK, POINTS) for precise column X boundaries
- **Derived regions**: table, total row, pagination, sidebar indicator positions
- **Caching**: Local coordinates are cached since the skills panel is fixed-size; only the screen position changes

Publishes `EVENT_DEBUG_REGIONS` with all bounds for overlay visualization.

### Stage 5: Screen Capture

**File**: `capturer.py` — `ScreenCapturer.capture_window()`

| Platform | Method | Notes |
|----------|--------|-------|
| **Windows** | `PrintWindow()` with `PW_RENDERFULLCONTENT` | Captures window content directly, ignores overlays on top |
| **Windows fallback** | `BitBlt` (GDI) | Works for standard windows, not DX/GL |
| **Linux** | `mss` region capture | Captures screen region (includes overlays) |

Output: numpy array in BGR format. GDI resources (DC, bitmap) are properly cleaned up.

### Stage 6: Table Extraction

**File**: `preprocessor.py` — `ImagePreprocessor`

1. **Crop**: Table region extracted from full game capture using layout coordinates
2. **Threshold**: Binary threshold at 120 grayscale (light text on dark background)
3. **Row split**: `extract_rows()` divides table into row strips by computed row height
4. **Column split**: `extract_columns()` extracts name/rank/points cells per row
5. **Empty check**: Rows with fewer than `MIN_BRIGHT_PIXELS` (50) bright pixels are skipped — prevents rejecting short names like "Aim" that occupy few pixels

Right-edge trimming: `NAME_COL_RIGHT_TRIM` (30px) and `POINTS_COL_RIGHT_TRIM` (30px) remove empty gap between columns.

### Stage 7: Font Template Matching

**File**: `font_matcher.py` — `FontMatcher`

The primary OCR method. Instead of traditional OCR, renders expected text as templates and matches against captured cells.

**Initialization**:
- Loads all known skill names (from `SkillMatcher`) and rank names (from `RankVerifier`)
- Renders template images for each using PIL + Arial Unicode Bold (`client/assets/arial-unicode-bold.ttf`)
- Templates rendered at `MATCH_SCALE` (4x) resolution for accuracy
- Inter-glyph spacing: `GLYPH_GAP` = 1px (matches game's tight text rendering)

**Matching process**:
1. Captured cell image → binary threshold (same as preprocessor: 120)
2. Upscale to 4x resolution
3. `cv2.matchTemplate(TM_CCOEFF_NORMED)` against pre-rendered templates
4. Best match above threshold is accepted

**Thresholds** (TM_CCOEFF_NORMED):
| Target | Threshold | Notes |
|--------|-----------|-------|
| Skill names | 0.65 | Accommodates ClearType (game) vs FreeType (PIL) differences |
| Rank names | 0.65 | |
| Digits | 0.65 | |

**Auto-calibration**: After the first page scan, tests multiple font sizes and rendering modes against captured cells to find optimal settings. Calibration data saved to `./data/font_calibration.json`.

**Disk cache**: Captured templates saved to `./data/captured_templates/` when match score exceeds `CAPTURE_MIN_SCORE` (0.95).

### Stage 8: Skill & Rank Matching

**File**: `skill_parser.py`

**SkillMatcher** — fuzzy name matching fallback:
- Fetches skill list from `api.entropianexus.com/skills` (cached 24h at `client/data/skill_reference.json`)
- Exact match first, then `SequenceMatcher` fuzzy match (threshold: 0.80)

**RankVerifier** — rank validation and cross-verification:
- Fetches rank thresholds from `api.entropianexus.com/enumerations/Skill%20Ranks` (cached 24h at `client/data/skill_ranks.json`)
- `expected_rank(points)`: determines what rank a skill should be at given points
- `verify(rank, points, bar_pct)`: cross-checks OCR'd rank against expected rank for the point total, computes expected bar fill percentage

### Stage 9: Progress Bar Reading

**File**: `progress_bar.py` — `ProgressBarReader`

Reads the teal/cyan fill percentage of skill progress bars:

1. Convert to HSV color space
2. Create mask for fill region: hue 140–190° (mapped to OpenCV's 0–180 scale), saturation ≥ 50, value ≥ 80
3. Average mask across rows → 1D column fill profile
4. Find fill boundary with sub-pixel interpolation (threshold: 30% column density)
5. Returns 0.00–100.00, rounded to 2 decimals

### Stage 10: Result Packaging

Each matched row produces a `SkillReading`:

```python
@dataclass
class SkillReading:
    skill_name: str          # e.g., "Laser Weaponry Technology"
    rank: str                # e.g., "Apprentice"
    current_points: float    # e.g., 1234.56
    progress_percent: float  # 0.00-100.00 (rank progress bar)
    rank_bar_percent: float  # 0.00-100.00 (rank bar)
    category: str            # e.g., "Combat"
    scan_timestamp: datetime
```

**Events published per row**:
- `EVENT_SKILL_SCANNED`: the `SkillReading` object (consumed by Skills page)
- `EVENT_DEBUG_ROW`: detailed row data including match scores, raw text, verification (consumed by overlay)

**Events published per page**:
- `EVENT_OCR_PROGRESS`: `ScanProgress` with found/expected counts, current category

**On completion**:
- `EVENT_OCR_COMPLETE`: final `SkillScanResult` with all skills, missing list, timing

### Stage 11: Continuous Monitoring & Page Detection

**File**: `orchestrator.py` — main loop in `run_continuous()`

After the initial scan, the orchestrator monitors for page changes:

1. **Anchor-based fast detection**: Stores first row's binary image hash as anchor
2. **Fast poll** (every `MONITOR_INTERVAL` = 0.1s): Extracts first row, compares hash — if same, page unchanged, skip
3. **On page change**: Publishes `EVENT_OCR_PAGE_CHANGED`, clears overlay checkmarks, performs full page scan
4. **On window move**: Attempts `quick_relocate()` first, falls back to full detection loop
5. **On window close**: Exits monitoring, publishes `EVENT_OCR_COMPLETE`

**Safety**: If ≥ `MAX_MISS_FRACTION` (50%) of content rows fail to match, the page is discarded (window likely moved mid-capture).

## Event Flow

```
OCR Thread                              Main Qt Thread
──────────                              ───────────────

EVENT_DEBUG_REGIONS ───EventBus──→  ScanHighlightOverlay._on_regions()
                                    (show overlay, store layout bounds)

EVENT_DEBUG_ROW ───────EventBus──→  ScanHighlightOverlay._on_row()
                                    (add green highlight + checkmark)

EVENT_SKILL_SCANNED ───EventBus──→  AppSignals.skill_scanned
                                    → SkillsPage._on_skill_scanned()
                                    (add row to results table, update skill values)

EVENT_OCR_PROGRESS ────EventBus──→  AppSignals.ocr_progress
                                    → SkillsPage._on_ocr_progress()
                                    (update "45/165 skills" status)

EVENT_OCR_PAGE_CHANGED ─EventBus─→  ScanHighlightOverlay._on_page_changed()
                                    (clear row highlights)
                                    AppSignals.ocr_page_changed
                                    → SkillsPage._on_ocr_page_changed()
                                    (clear results table)

EVENT_OCR_COMPLETE ────EventBus──→  ScanHighlightOverlay._on_complete()
                                    (auto-hide after 3000ms)
                                    AppSignals.ocr_complete
                                    → SkillsPage._on_ocr_complete()
                                    (final results, refresh all tabs)

EVENT_OCR_OVERLAYS_HIDE EventBus─→  ScanHighlightOverlay._on_hide()
                                    (immediate hide — panel closed/moved)
```

**Thread safety**: `ScanHighlightOverlay` bridges EventBus callbacks to Qt signals internally, ensuring all painting happens on the main thread.

## Overlay Visualization

### ScanHighlightOverlay (Qt — production)

**File**: `client/overlay/scan_highlight_overlay.py`

- Full-screen frameless click-through window (Win32 `WS_EX_LAYERED | WS_EX_TRANSPARENT`)
- Qt attribute `WA_TranslucentBackground` for full transparency
- **Row highlights**: `rgba(0, 221, 102, 40)` fill with `rgba(0, 221, 102, 120)` border
- **Checkmarks**: ✓ in Consolas 10pt bold, `#00dd66`, positioned 14px left of table
- **Auto-hide**: 3000ms after `EVENT_OCR_COMPLETE`
- **Focus polling**: Only visible when game window is foreground (checked by title prefix)
- **Debug mode** (`scan_overlay_debug` config): Draws colored region boxes — red (window), green (sidebar), yellow (table), magenta (pagination), gold (total), orange/blue/teal (columns)

### ScanOverlay (Tkinter — debug/legacy)

**File**: `client/overlay/scan_overlay.py`

- Runs in a separate daemon thread
- Click-through via Win32 `WS_EX_LAYERED | WS_EX_TRANSPARENT`
- Shows OCR'd values to the right of the game window
- Template match scores displayed in magenta
- Row highlights with match status colors (green/red/gray)

## ROI Calibration

**Default ROIs** (`detector.py:DEFAULT_ROI_PIXELS`): Pixel positions measured from a fixed 557×668px skills panel reference.

| ROI | Position (x, y, w, h) | Description |
|-----|----------------------|-------------|
| `table` | (10, 84, 575, 317) | Main data table |
| `total` | (10, 401, 575, 27) | "Total: XXXXX" row |
| `pagination` | (10, 460, 575, 28) | Page indicator "1/3" |
| `indicator` | (0, 75, 70, 25) | Sidebar category indicator |

**User overrides**: The `ScanRoiDialog` provides spinboxes for x/y/w/h offsets per region. Changes publish `EVENT_ROI_CONFIG_CHANGED` immediately for live preview. Saved to `config.json` as `scan_roi_overrides`.

## Configuration

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `ocr_confidence_threshold` | float | 0.7 | Minimum confidence for skill name matches |
| `scan_overlay_debug` | bool | false | Show debug region boxes on the overlay |
| `scan_roi_overrides` | dict | {} | `{roi_name: [x, y, w, h]}` pixel offset overrides |
| `hotkey_ocr_scan` | str | "F7" | Scan hotkey combo (currently disabled in hotkey manager) |

## Key Constants

### Timing (orchestrator.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `DETECT_POLL_INTERVAL` | 1.0s | How often to poll for skills window |
| `DETECT_TIMEOUT` | 120s | Give up if window not found |
| `MONITOR_INTERVAL` | 0.1s | Poll for page changes during continuous monitoring |
| `STABILITY_TICKS` | 3 | Consecutive matching positions required |
| `STABILITY_POLL_INTERVAL` | 0.1s | Interval between stability checks |

### OCR Tuning (orchestrator.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `MIN_BRIGHT_PIXELS` | 50 | Minimum bright pixels to consider a row non-empty |
| `NAME_COL_RIGHT_TRIM` | 30px | Trim empty space from right edge of name column |
| `POINTS_COL_RIGHT_TRIM` | 30px | Trim empty space from right edge of points column |
| `MAX_MISS_FRACTION` | 0.5 | Discard page if >50% of rows fail to match |

### Template Matching (font_matcher.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `SKILL_THRESHOLD` | 0.65 | TM_CCOEFF_NORMED threshold for skill names |
| `RANK_THRESHOLD` | 0.65 | TM_CCOEFF_NORMED threshold for rank names |
| `DIGIT_THRESHOLD` | 0.65 | TM_CCOEFF_NORMED threshold for digit strings |
| `GLYPH_GAP` | 1px | Inter-glyph spacing in rendered templates |
| `BINARY_THRESHOLD` | 115 | Grayscale threshold for binary conversion |
| `CAPTURE_MIN_SCORE` | 0.95 | Minimum score to save a new captured template |
| `MATCH_SCALE` | 4x | Template rendering upscale factor |

## Data Models

**File**: `client/ocr/models.py`

```python
@dataclass
class SkillReading:
    """A single skill as read from the game UI."""
    skill_name: str
    rank: str
    current_points: float
    progress_percent: float  # 0.00-100.00
    rank_bar_percent: float  # 0.00-100.00
    category: str
    scan_timestamp: datetime

@dataclass
class SkillScanResult:
    """Complete result of a full skills scan."""
    skills: list[SkillReading]
    missing_skills: list[str]
    scan_start: datetime
    scan_end: datetime
    total_expected: int
    total_found: int

@dataclass
class ScanProgress:
    """Progress state for the overlay."""
    total_skills_expected: int
    skills_found: int
    current_category: str
    current_page: int
    total_pages: int
    missing_names: list[str]
```

## Reference Data

The scanner fetches and caches reference data from the Nexus API:

| Data | API Endpoint | Cache File | TTL |
|------|-------------|------------|-----|
| Skill names | `api.entropianexus.com/skills` | `client/data/skill_reference.json` | 24h |
| Rank thresholds | `api.entropianexus.com/enumerations/Skill%20Ranks` | `client/data/skill_ranks.json` | 24h |

Falls back to cached files if the API is unreachable.

## Skill Categories

The 13 skill categories in sidebar order (defined in `navigator.py`):

Attributes, Design, Combat, Construction, Defense, General, Information, Medical, Mining, Science, Mindforce, Beauty, Social
