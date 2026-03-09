# Market Price Scanner Pipeline

The market price scanner reads in-game market price windows via OCR. It captures the game window, detects market price windows via template matching, reads item names and 10 data cells (5 periods x 2 metrics) using STPK-based glyph matching, resolves the item name against the known item database, and uploads results to the server for crowd-sourced aggregation.

## Architecture Overview

```
                    ┌──────────────────────────────────────────┐
                    │            Game Window                    │
                    │                                          │
                    │   ┌──────────────────────────────────┐   │
                    │   │     Market Price Window           │   │
                    │   │  ┌──────────────────────────┐    │   │
                    │   │  │  ITEM NAME (Row 1)        │    │   │
                    │   │  │  ITEM NAME (Row 2)        │    │   │
                    │   │  ├──────────┬───────────────┤    │   │
                    │   │  │ Markup % │ Sales Volume  │    │   │
                    │   │  ├──────────┼───────────────┤    │   │
                    │   │  │ 125%     │ 2.51 PED      │ 1d │   │
                    │   │  │ 110%     │ 15.3 kPED     │ 7d │   │
                    │   │  │ 105%     │ 120 kPED      │ 30d│   │
                    │   │  │ 102%     │ 1.2 MPED      │365d│   │
                    │   │  │ N/A      │ N/A           │3650d│   │
                    │   │  └──────────┴───────────────┘    │   │
                    │   │                          Tier: 5  │   │
                    │   └──────────────────────────────────┘   │
                    └──────────────────────────────────────────┘
                                         │
                          Window capture backend
                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Market Price Thread (daemon)                     │
│                                                                  │
│  Template Match ──→ ROI Extract ──→ STPK OCR ──→ Name Match     │
│  (find windows)    (name, cells)   (blob→glyph)  (Levenshtein)  │
│                                        │                         │
│                                 Confidence Aggregation           │
│                                 + Heuristic Validation           │
└─────────────────────────┬────────────────────────────────────────┘
                          │ EventBus
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Main Qt Thread                               │
│                                                                  │
│  AppSignals ──→ ScanHighlightOverlay (debug ROI boxes)           │
│             ──→ ScanSummaryOverlay   (results banner)            │
│                                                                  │
│  IngestionUploader ──→ Buffer ──→ POST /api/ingestion/market-prices
└─────────────────────────────────────────────────────────────────┘
```

**Threading model**: `MarketPriceDetector` runs in a daemon thread (`market-price`), polling at `market_price_poll_interval` (default 1.0s). `IngestionUploader` runs in the `ingestion-upload` thread, flushing every 30s. Events bridge to the main Qt thread via `AppSignals`.

## File Map

| File | Purpose |
|------|---------|
| `client/ocr/market_price_detector.py` | Core pipeline: template matching, ROI extraction, STPK OCR, cell parsing, confidence aggregation, heuristic validation |
| `client/ocr/stpk.py` | STPK v2 binary format reader/writer, 4-bit grid packing/unpacking |
| `client/ocr/font_matcher.py` | Shared OCR infrastructure: `DigitMatcher`, 4-bit soft-overlap scoring, grid normalization |
| `client/ocr/item_name_matcher.py` | Levenshtein-based item name matching, ambiguity detection, confidence adjustment |
| `client/ocr/market_disambiguation.py` | Character-pair disambiguation for confusable glyphs (0/O, 5/6, 3/8, etc.) |
| `client/ingestion/uploader.py` | Upload buffering, 1-hour dedup, confidence resend threshold, batch upload with rate limiting |
| `client/overlay/scan_highlight_overlay.py` | Qt debug overlay: ROI boxes, per-field confidence display, raw cell values |
| `client/core/constants.py` | Event type constants (`EVENT_MARKET_PRICE_*`) |
| `client/ui/signals.py` | EventBus to Qt signal bridge |
| `client/app.py` | Pipeline startup (`_start_ocr_pipeline`) |
| `client/core/config.py` | Market price config keys |
| `client/assets/stpk/` | STPK font template files (`market_digits.stpk`, `market_text.stpk`) |
| `scripts/capture_market_glyphs.py` | Interactive glyph capture tool (Tkinter) for building STPK templates |
| `scripts/gen_market_stpk.py` | STPK generation from Scaleform-rendered fonts |
| `scripts/debug_market_ocr.py` | Visual diagnostic tool comparing game blobs vs template grids |

## Pipeline Stages

### Stage 1: Window Detection

**File**: `market_price_detector.py` — `_tick()`

1. Captures the game window via `ScreenCapturer` (shared with skill scanner)
2. Template-matches the market price window header against the full game frame
3. Supports multiple simultaneous market price windows (non-maximum suppression)
4. Returns screen-absolute positions for each detected window

**Template Matching**:
- Uses `cv2.matchTemplate(TM_CCOEFF_NORMED)` with the market price header template
- Threshold: `market_price_match_threshold` config (default 0.9)
- Alpha mask applied to ignore transparent template regions

**Template Validation** (`_validate_match()`):
- Inside mask brightness must be >= `MIN_INSIDE_BRIGHTNESS` (180)
- Contrast (inside - outside) must be >= `MIN_CONTRAST` (30)
- Rejects false positives on uniform backgrounds

**Multi-Window Support**:
- After finding all matches above threshold, non-maximum suppression keeps only non-overlapping matches
- Overlap check: `|pos_x - kept_x| < template_w AND |pos_y - kept_y| < template_h`

### Stage 2: Pixel-Unchanged Optimization

**File**: `market_price_detector.py` — `_tick()`

Before expensive re-scanning, checks if tracked window positions have unchanged pixels:

1. Compares current pixel region against previously stored bytes (byte-identical check)
2. If unchanged AND all confidences >= `MIN_RESCAN_CONFIDENCE` (0.75): emit cached data, skip OCR
3. If changed OR any confidence below threshold: perform full re-read

This avoids re-scanning the same market price window ~60 times when the user is just looking at it. The semi-transparent background means pixel noise can cause byte differences even without content changes, so low-confidence results always force re-read.

### Stage 3: ROI Extraction

**File**: `market_price_detector.py` — `_read_market_price()`

Each market price window has these ROI regions, positioned relative to the template match location:

| ROI | Config Key | Default Offset | Size | Description |
|-----|-----------|----------------|------|-------------|
| Name Row 1 | `market_price_roi_name_row1` | dx=-80, dy=30 | 340x16 | First line of item name |
| Name Row 2 | `market_price_roi_name_row2` | dx=-80, dy=49 | 340x16 | Second line (long names) |
| Tier | `market_price_roi_tier` | dx=400, dy=112 | 30x14 | Item tier number |
| First Cell | `market_price_roi_first_cell` | dx=23, dy=112 | 100x14 | Top-left data cell |
| Cell Offset | `market_price_cell_offset` | x=107, y=25 | — | Grid spacing between cells |

**Data Cell Grid Layout**:

```
        Markup Column       Sales Column
        (col_idx=0)         (col_idx=1)
        ┌───────────┐       ┌───────────┐
  1d    │ +125.5%   │       │ 2.51 PED  │  row_idx=0
        ├───────────┤       ├───────────┤
  7d    │ +110.2%   │       │ 15.3 kPED │  row_idx=1
        ├───────────┤       ├───────────┤
  30d   │ +105.0%   │       │ 120 kPED  │  row_idx=2
        ├───────────┤       ├───────────┤
  365d  │ +102.1%   │       │ 1.2 MPED  │  row_idx=3
        ├───────────┤       ├───────────┤
  3650d │ N/A       │       │ N/A       │  row_idx=4
        └───────────┘       └───────────┘

Cell position:
  cell_dx = first_cell.dx + col_idx * cell_offset.x
  cell_dy = first_cell.dy + row_idx * cell_offset.y
```

### Stage 4: STPK-Based OCR

The market price scanner uses a different OCR approach from the skill scanner. Instead of rendering expected texts and template-matching, it uses **String Template Packs (STPK)** — pre-rendered glyph templates at 4-bit lightness resolution, matched against segmented character blobs.

#### 4.1 Text Intensity Extraction

**Method**: `_extract_text_intensity()`

The market price window has a semi-transparent dark background with bright white/cyan text. Extraction pipeline:

1. Convert BGR to grayscale
2. Zero pixels below `TEXT_BRIGHTNESS_THRESHOLD` (80) — suppress background bleed
3. Normalize to full 0-255 range — amplify faint text
4. Re-threshold to clean up residual noise

#### 4.2 4-Bit Quantization

```python
intensity_4bit = min(intensity / 16, 15).astype(uint8)
```

Maps 0-255 intensity to 0-15 (4-bit lightness levels). This soft quantization preserves gradient information for more robust matching than binary thresholding.

#### 4.3 Blob Detection

**Method**: `_match_stpk_blobs()`

Segments text into individual character blobs via column density analysis:

1. **Vertical bounds**: Find first/last row with content (reject if text height < 3px)
2. **Column density**: Count bright pixels per column: `col_density = sum(region > 0, axis=0)`
3. **Column filtering**: Only columns with >= `MARKET_MIN_COL_DENSITY` (2) bright pixels count as text. This filters out single anti-aliased bridge pixels between character gaps
4. **Blob segmentation**: Group consecutive qualifying columns into blobs `(x_start, x_end)`

#### 4.4 Blob Splitting & Merging

**Valley-Based Splitting** (`_split_blobs_at_valleys()`):

For blobs wider than `max_single_w` (8px for digits, 10px for text):

1. Compute column intensity profile: `col_sums = region.sum(axis=0)` in 4-bit space
2. Find split points where `col_sums[col] < MARKET_VALLEY_THRESHOLD` (23)
3. Group consecutive valley columns, split at boundaries
4. Reject splits producing too many fragments < `MARKET_MIN_SUB_BLOB_W` (3px)
5. Force-split pass: If blobs still > `max_single_w * 1.6`, find local minimum and split

**Narrow Pair Merging** (`_merge_narrow_pairs()`):

Merge adjacent blobs if both <= 2px wide and gap <= 2px. Handles characters like `"` rendered as two tick marks.

**Space Detection**:

- Compute median inter-blob gap
- Space threshold = `max(median_gap * 2, 4)` pixels
- Gaps >= threshold insert a space character into the result

#### 4.5 Grid Matching (4-Bit Soft Overlap)

**Method**: `_score_grid()`

Each blob is normalized to the STPK grid dimensions and scored against all template entries:

**Blob Normalization** (`_normalize_blob()`):
- Extract tight bounding box from 4-bit intensity
- Quantize to template grid size (grid_w x grid_h)
- Alignment: bottom-align for digits (right_align=True), top-align for text

**Scoring Formula**:
```
raw_score = 6 * sum(min(obs, tmpl)) - 2 * sum(tmpl) - sum(obs)
normalized = raw_score / (3 * sum(tmpl))
```

Properties:
- Rewards pixel overlap (first term)
- Penalizes missing template pixels (second term, heavier weight)
- Penalizes extra observation pixels (third term)
- Works with soft 4-bit values, not binary — handles anti-aliasing naturally

**Shift Tolerance**: Tries horizontal shifts (-1, 0, +1) and takes the maximum score to compensate for subpixel rendering differences.

**Minimum Score Threshold**: 0.4 (below this, the blob is treated as unrecognized)

#### 4.6 Multi-Character Matching

Before single-character scoring, wide blobs try multi-character STPK entries:

- Entries like `N/A`, `kPED`, `MPED`, `PED`, `PEC`, etc.
- Span consecutive blobs if content width is within 5px tolerance
- Multi-char entries require spanning >= 2 blobs
- Same 4-bit soft-overlap scoring

#### 4.7 Period (Dot) Auto-Detection

Narrow blobs (<= 2px wide) with content only in the bottom 3 rows are auto-classified as periods (`.`) with confidence 0.9. These are too small to score well against templates but are unambiguous from their position.

### Stage 5: Cell Value Parsing

**Method**: `_parse_cell_value()`

| Format | Examples | Result |
|--------|----------|--------|
| Markup (percent) | `+125.5%`, `125.5%` | 125.5 |
| Markup (absolute) | `+5.00`, `5.00` | 5.00 |
| Overflow | `>999999%` | -1 (sentinel) |
| Sales with unit | `2.51PED`, `15.3kPED`, `1.2MPED` | Value in PED |
| Sales (PEC) | `52.7PEC`, `0.3mPEC` | Value in PED (1 PEC = 0.01 PED) |
| Empty | `N/A`, `NA`, `N`, `-` | None |

**Unit Suffix Multipliers** (ordered longest-first for greedy matching):

| Suffix | Multiplier | Description |
|--------|-----------|-------------|
| `MPED` | 1,000,000 | Mega-PED |
| `kPED` | 1,000 | Kilo-PED |
| `PED` | 1 | PED |
| `mPEC` | 0.00001 | Milli-PEC |
| `uPEC` | 0.00000001 | Micro-PEC (game renders as u) |
| `PEC` | 0.01 | PEC |
| `M` | 1,000,000 | Bare Mega (absolute mode) |
| `k` | 1,000 | Bare kilo (absolute mode) |

**Markup Mode Detection**:
- First non-N/A markup raw text determines mode for the entire window
- If text ends with `%` -> percent mode
- Otherwise -> absolute mode

**Markup Format Validation**:
- Raw text must be N/A, start with `+`/`>`, or end with `%`
- Bare numbers are accepted (game sometimes drops the `+` prefix in absolute mode)
- Failed validation: value set to None, confidence zeroed

### Stage 6: Item Name Matching

**File**: `item_name_matcher.py` — `ItemNameMatcher`

#### 6.1 Name Normalization

- Uppercase to Title Case (game displays all-caps)
- Strip trailing `...` (text truncation)
- Normalize comma/period confusion (indistinguishable at small font sizes)
- Underscore to space (OCR artifact)
- Collapse multiple spaces

#### 6.2 Matching Strategy

1. **Exact match**: Direct lookup in normalized name dictionary
2. **Fuzzy search** (Levenshtein distance):

| Name Length | Max Edit Distance |
|-------------|-------------------|
| <= 8 chars | 1 |
| <= 16 chars | 2 |
| > 16 chars | 3 |

3. Quick length filter: skip candidates where `|len(item) - len(ocr)| > max_dist`
4. Collect all candidates at best distance

#### 6.3 Confidence Adjustment

```
confidence = (base_ocr_conf - PENALTY_PER_EDIT * edit_distance) * ambiguity_factor
```

- `PENALTY_PER_EDIT` = 0.15 per unit of edit distance
- `ambiguity_factor` = 0.50 if multiple candidates with low per-char OCR confidence at differentiating positions (< 0.80 threshold); otherwise 1.0

#### 6.4 Ambiguity Detection

Items in series with minimal character differences (e.g., "ArMatrix LR-10" vs "ArMatrix LR-15") trigger ambiguity detection:

- Multiple candidates at same edit distance
- Per-character OCR confidence at differentiating positions below `AMBIGUITY_CONFIDENCE_THRESHOLD` (0.80)
- Ambiguous matches get `AMBIGUITY_PENALTY` (0.50) multiplier and can trigger manual review via `EVENT_MARKET_PRICE_REVIEW`

**Data Source**: Item list loaded from DataClient on init, refreshed every 30 minutes.

### Stage 7: Confidence Aggregation

**Method**: `_aggregate_confidence()`

**Worst-field-dominated geometric mean**:

Given N cell confidences (sorted ascending):

```
worst = confidences[0]
rest = confidences[1:]
ocr_conf = worst^0.5 * product(rest)^(0.5 / (N-1))
```

The worst field gets 50% weight in the geometric mean. This means a single bad field drastically reduces overall confidence.

Examples with 10 fields:
- All at 0.93 -> ~0.93 overall
- One at 0.30, rest at 0.95 -> ~0.51 overall
- Two at 0.30 -> ~0.36 overall

**Important**: Only data cell confidences (10 cells) contribute. Item name confidence does NOT contribute to OCR confidence — it was previously included but caused misleadingly low scores because name matching uses a different confidence scale.

### Stage 8: Heuristic Validation

**Method**: `_heuristic_confidence_penalty()`

Applies a 0-1 penalty multiplier to OCR confidence based on data plausibility checks:

#### Sales Monotonicity

Longer periods should have equal or greater total sales volume than shorter periods:

| Violation | Penalty |
|-----------|---------|
| Shorter > Longer by 2x | *= 0.4 |
| Shorter > Longer by 1.1x | *= 0.6 |
| Rounding (1.0-1.1x) | *= 0.85 |

#### Markup Magnitude Stability

Large swings between adjacent periods suggest OCR errors:

| Period Transition | Suspect Ratio | Strong Ratio |
|------------------|---------------|--------------|
| 1d -> 7d | 20x | 100x |
| 7d -> 30d | 10x | 50x |
| 30d -> 365d | 5x | 20x |
| 365d -> 3650d | 5x | 20x |

Only applied when both periods have >= 0.1 PED sales volume. Volume factor caps penalty at 10 PED sales.

### Stage 9: Event Publishing

| Event | When | Consumer |
|-------|------|----------|
| `EVENT_MARKET_PRICE_DEBUG` | Every tick | Debug overlay (ROI boxes, confidence display) |
| `EVENT_MARKET_PRICE_SCAN` | Successful read | `IngestionUploader` (buffer for upload) |
| `EVENT_MARKET_PRICE_REVIEW` | Ambiguous/overflow | Review dialog for manual confirmation |
| `EVENT_MARKET_PRICE_LOST` | Window disappears | Overlay cleanup |
| `EVENT_MARKET_PRICE_ERROR` | ROI out of bounds | Error logging |

**Multi-window tracking**: A monotonic `tick_seq` counter groups events from the same tick. The overlay clears accumulated windows when `tick_seq` changes.

### Stage 10: Upload

**File**: `ingestion/uploader.py` — `IngestionUploader`

#### Submission Filtering

- Drop scans with confidence < `MIN_SUBMISSION_CONFIDENCE` (0.75)
- Exception: manually reviewed submissions bypass this threshold

#### Deduplication (1-hour window)

- Skip if same item name was submitted within the last hour
- Exception: resend if confidence improved by >= `CONFIDENCE_RESEND_THRESHOLD` (2%)
- Manually reviewed submissions always bypass dedup

#### Data Sanitization

- Convert overflow sentinel (`-1`) to `null`
- Strip transient debug keys (prefixed with `_`)
- Rename `ocr_confidence` to `confidence` for the server API

#### Batch Upload

- Buffer: `deque` of pending price scans
- Flush interval: every 30 seconds
- Chunk size: max `MAX_BATCH_SIZE` (500) items per request
- Rate limit: 20 requests per 60 seconds
- Endpoint: `POST /api/ingestion/market-prices` (OAuth required, allowlisted clients only)
- Persistence: SQLite database stores pending items for crash recovery

## STPK Binary Format (v2)

String Template Packs store pre-rendered glyph templates at 4-bit lightness resolution.

### File Structure

```
[HEADER: 32 bytes]
  0-3:    Magic "STPK" (4 bytes)
  4-5:    Version (u16, = 2)
  6-7:    Num entries (u16)
  8-9:    Grid width (u16)
  10-11:  Grid height (u16)
  12-13:  Font size (u16, in points)
  14-15:  Flags (u16: bits 0-7 = bpp, bit 8 = right-align)
  16-17:  X offset (s16, fixed-point / 10000)
  18-19:  Y offset (s16, fixed-point / 10000)
  20-23:  Font name length (u32)
  24-27:  String table size (u32)
  28-31:  Uncompressed payload size (u32, 0 = uncompressed)

[FONT NAME: font_name_length bytes, UTF-8]

[STRING TABLE: string_table_size bytes]
  Per string: u16 length + UTF-8 text

[ENTRY DIRECTORY: num_entries x 16 bytes]
  Per entry:
    0-3:   String offset in string table (u32)
    4-5:   Bitmap width (u16)
    6-7:   Bitmap height (u16)
    8-11:  Bitmap offset in bitmap section (u32)
    12-13: Content width (u16, rendered text width)
    14-15: Content height (u16, rendered text height)

[GRID DATA: num_entries x (grid_h x ceil(grid_w / 2)) bytes]
  4-bit nibble-packed (2 pixels per byte, high nibble first)
  Values 0-15 (lightness levels)

[BITMAP DATA: raw 8-bit pixel data]
  Each entry: bw x bh bytes
```

**Compression**: If `uncompressed_size > 0`, the payload after the font name is zlib-compressed.

### Current STPK Files

| File | Characters | Grid Size | Alignment | Font Size |
|------|-----------|-----------|-----------|-----------|
| `market_digits.stpk` | `0-9`, `.`, `%`, `/`, `A`, `M`, `P`, `E`, `D`, `k`, `u`, `+`, `>`, `N/A`, combo entries | 12px | Right | 12pt |
| `market_text.stpk` | `A-Z`, `0-9`, `().,'-!%$/ ` (item name characters) | 14px | Left | 14pt |

## Debug Overlay

**File**: `scan_highlight_overlay.py` — `_paint_market_price_rois()`

When `scan_overlay_debug` is enabled, the overlay draws:

- **ROI boxes**: Colored rectangles for each detected region
  - Cyan: Name rows
  - Yellow: Tier
  - Green: Data cells
- **Value text**: OCR'd value rendered at bottom-right of each box
  - Name text drawn in red (visible above game's white item name)
  - Data cells in white
- **Per-field confidence**: Percentage below each data cell box
  - Green (>= 90%), Yellow (>= 70%), Red (< 70%)
  - Shows worst-scoring character when confidence < 95% (e.g., `90% 'k'`)
- **Header info**: Aggregated confidence, OCR confidence, heuristic penalty, raw cell confidence array

The Skills template no-match box is suppressed when confidence < 50% to avoid visual clutter.

## Configuration

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `market_price_enabled` | bool | true | Enable market price detection |
| `market_price_match_threshold` | float | 0.9 | Template match threshold |
| `market_price_poll_interval` | float | 1.0 | Seconds between detection ticks |
| `market_price_text_threshold` | int | 80 | Brightness floor for text extraction |
| `market_price_digit_stpk` | str | `market_digits.stpk` | Digit STPK template file |
| `market_price_text_stpk` | str | `market_text.stpk` | Text STPK template file |
| `market_price_review_enabled` | bool | true | Enable manual review prompts |
| `market_price_roi_name_row1` | dict | `{dx:-80, dy:30, w:340, h:16}` | Name row 1 ROI |
| `market_price_roi_name_row2` | dict | `{dx:-80, dy:49, w:340, h:16}` | Name row 2 ROI |
| `market_price_roi_first_cell` | dict | `{dx:23, dy:112, w:100, h:14}` | First data cell ROI |
| `market_price_cell_offset` | dict | `{x:107, y:25}` | Cell grid spacing |
| `market_price_roi_tier` | dict | `{dx:400, dy:112, w:30, h:14}` | Tier ROI |
| `scan_overlay_debug` | bool | false | Show debug overlay with ROI boxes |

## Key Constants

### Detection & Validation

| Constant | Value | Purpose |
|----------|-------|---------|
| `BACKGROUND_SLEEP` | 1.0s | Sleep when game window not visible |
| `MIN_RESCAN_CONFIDENCE` | 0.75 | Force re-read when cached confidence below this |
| `MIN_INSIDE_BRIGHTNESS` | 180 | Template validation: min brightness inside mask |
| `MIN_CONTRAST` | 30 | Template validation: min brightness gap inside/outside |
| `EMPTY_CELL_BRIGHTNESS` | 40 | Below this, cell is empty (N/A) |

### OCR Processing

| Constant | Value | Purpose |
|----------|-------|---------|
| `TEXT_BRIGHTNESS_THRESHOLD` | 80 | Zero pixels below this before blob detection |
| `MARKET_MIN_COL_DENSITY` | 2 | Min bright pixels per column to count as text |
| `MARKET_VALLEY_THRESHOLD` | 23 | Column-sum threshold for character boundary detection |
| `MARKET_DIGIT_MAX_SINGLE_W` | 8 | Max single character width (digits) before splitting |
| `MARKET_TEXT_MAX_SINGLE_W` | 10 | Max single character width (text) before splitting |
| `MARKET_MIN_SUB_BLOB_W` | 3 | Min sub-blob width after splitting |

### Confidence & Upload

| Constant | Value | Purpose |
|----------|-------|---------|
| `MIN_SUBMISSION_CONFIDENCE` | 0.75 | Drop scans below this confidence |
| `CONFIDENCE_RESEND_THRESHOLD` | 0.02 | Resend if confidence improved by >= 2% |
| `MAX_BATCH_SIZE` | 500 | Max items per upload request |
| `INGEST_RATE_LIMIT_MAX_REQUESTS` | 20 | Rate limit: requests per window |
| `INGEST_RATE_LIMIT_WINDOW` | 60s | Rate limit window |

### Item Name Matching

| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_DIST_SHORT` | 1 | Max edit distance for names <= 8 chars |
| `MAX_DIST_MEDIUM` | 2 | Max edit distance for names <= 16 chars |
| `MAX_DIST_LONG` | 3 | Max edit distance for names > 16 chars |
| `PENALTY_PER_EDIT` | 0.15 | Confidence penalty per edit distance unit |
| `AMBIGUITY_CONFIDENCE_THRESHOLD` | 0.80 | Per-char confidence threshold for ambiguity detection |
| `AMBIGUITY_PENALTY` | 0.50 | Confidence multiplier for ambiguous matches |
| `REFRESH_INTERVAL` | 1800s | Item list refresh interval |

### Heuristic Validation

| Constant | Value | Purpose |
|----------|-------|---------|
| `_HEURISTIC_MIN_SALES` | 0.1 PED | Min sales volume to apply markup stability check |
| `_MARKUP_SUSPECT_RATIO` | [20, 10, 5, 5] | Suspect markup swing ratios per period transition |
| `_MARKUP_STRONG_RATIO` | [100, 50, 20, 20] | Strong markup swing ratios per period transition |

## Data Format

Market price scan data is passed as plain dicts through the event system:

```python
{
    # Item identification
    "item_name": str,            # Matched item name (from DB)
    "item_name_ocr": str,        # Raw OCR text (if different from matched)
    "item_name_conf": float,     # Item name matching confidence
    "item_name_edit_dist": int,  # Levenshtein distance (0 = exact match)
    "tier": int | None,          # Optional item tier

    # Per-period values (5 periods: 1d, 7d, 30d, 365d, 3650d)
    "markup_1d": float | None,   # Markup value (percent or absolute)
    "markup_1d_raw": str,        # Raw OCR text as read
    "markup_1d_conf": float,     # Per-field OCR confidence
    "markup_1d_worst_char": str, # Lowest-scoring character in this field
    # ... (analogous for markup_7d through markup_3650d)

    "sales_1d": float | None,   # Sales volume in PED
    "sales_1d_raw": str,
    "sales_1d_conf": float,
    "sales_1d_worst_char": str,
    # ... (analogous for sales_7d through sales_3650d)

    "markup_mode": str,          # "percent" or "absolute"

    # Confidence
    "ocr_confidence": float,     # Final OCR confidence (aggregate * heuristic)
    "confidence": float,         # Template match confidence
    "heuristic_penalty": float,  # Only present if != 1.0

    # Metadata
    "timestamp": str,            # ISO UTC timestamp
    "x": int, "y": int,         # Template match position
    "w": int, "h": int,         # Template dimensions

    # Debug (transient, stripped before upload)
    "_agg_raw": float,           # Raw aggregate before heuristic penalty
    "_hp_raw": float,            # Heuristic penalty value
    "_cell_confs": list[float],  # Per-cell confidence scores
}
```

## Server-Side Processing

After upload, the server aggregates submissions from multiple users:

1. Submissions stored in `market_price_submissions` bucketed by hour
2. After the hour elapses (+5 min grace), lazy finalization runs per-column confidence-weighted majority vote
3. Winner upserted into `market_price_snapshots` as authoritative record
4. Raw submissions auto-deleted after 3 days

See the [Market Price Snapshots](market.md#market-price-snapshots) section in market.md for database schema and API endpoints.

## Glyph Capture Tool

**File**: `scripts/capture_market_glyphs.py`

Interactive Tkinter UI for capturing glyph samples from game screenshots to improve STPK templates.

### Usage

```bash
# Live mode: capture from game window
python scripts/capture_market_glyphs.py

# Load a specific screenshot
python scripts/capture_market_glyphs.py  # then use "Load Image..." button

# Review all captured glyphs
python scripts/capture_market_glyphs.py --review

# Build new STPK from captured glyphs
python scripts/capture_market_glyphs.py --build
```

### Capture Workflow

1. Load a screenshot (live capture or file dialog)
2. Template matching locates market price windows
3. ROIs extracted for item name and data cells
4. Blob detection segments characters
5. Current STPK templates score each blob (shows best guess + confidence)
6. User confirms or corrects each glyph label
7. Confirmed glyphs saved to `scripts/captured_glyphs.json`

### Review Mode

Scrollable grid of all captured glyphs grouped by character. Click any glyph to inspect, relabel, or delete. Useful for auditing captured data before building new STPKs.

### Captured Glyphs Format

```json
{
  "<glyph_hash>": {
    "text": "5",
    "grid_w": 11,
    "grid_h": 14,
    "grid": [[4, 0, 0, 8, 15, 15, 12, 0, 0, 0, 0], ...],
    "count": 3,
    "source": "live_2/cell_markup_1d"
  }
}
```

### Important Notes

- The "Done" button only saves **confirmed** glyphs (not auto-guessed labels)
- `+` and `>` characters are in the expected digit character set but may need actual STPK glyph captures
- Unicode paths (e.g., with umlauts) are handled via `np.fromfile` + `cv2.imdecode` workaround
