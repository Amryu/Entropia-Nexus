# Capture System

Screenshots, video clips, and continuous recording for the desktop client.

## Architecture

```
 ┌──────────────────┐     ┌──────────────┐     ┌──────────────┐
 │ FrameDistributor │────>│ FrameBuffer  │     │ AudioBuffer  │
 │ (WGC / BitBlt)   │     │ JPEG deque   │     │ WASAPI PCM   │
 └──────────────────┘     └──────┬───────┘     └──────┬───────┘
         │                       │                     │
         │ (live frame)          │ snapshot()           │ snapshot()
         ▼                       ▼                     ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                      CaptureManager                          │
 │  - _on_capture_frame()   push to buffer + live recording     │
 │  - _do_save_clip()       snapshot buffer → encode thread     │
 │  - _take_screenshot()    grab frame → save PNG               │
 │  - _start/_stop_recording()   live FFmpeg pipe               │
 └────────┬─────────────────────────────┬───────────────────────┘
          │                             │
          ▼                             ▼
 ┌─────────────────┐          ┌──────────────────┐
 │  clip_writer.py │          │  screenshot.py   │
 │  write_clip()   │          │  save_screenshot()│
 │  (FFmpeg encode) │          │  (PNG via cv2)   │
 └─────────────────┘          └──────────────────┘
```

### Components

| File | Purpose |
|------|---------|
| `capture/capture_manager.py` | Central orchestrator — buffer lifecycle, hotkeys, global detection, encoding dispatch |
| `capture/frame_buffer.py` | Rolling JPEG-compressed frame deque with webcam snapshots |
| `capture/clip_writer.py` | FFmpeg-based clip encoder with parallel frame processing |
| `capture/screenshot.py` | Screenshot saving, background compositing, blur regions |
| `capture/audio_buffer.py` | WASAPI loopback (game audio) and input (mic) capture |
| `capture/webcam_capture.py` | Background webcam thread with device discovery |
| `capture/ffmpeg.py` | FFmpeg binary discovery, download, RNNoise model management |
| `capture/constants.py` | All defaults, resolution presets, bitrate tables, scaling algorithms |
| `overlay/recording_bar_overlay.py` | Compact overlay bar — screenshot/clip/record buttons, timer, encoding progress |

## Frame Buffer

The `FrameBuffer` stores a rolling window of JPEG-compressed frames in a bounded `deque`. Each entry is a tuple:

```
(timestamp: float, jpeg_bytes: bytes, webcam_jpeg: bytes | None)
```

- **Encoding**: JPEG quality 80 via `cv2.imencode` (~2-5ms at 1080p)
- **Memory**: ~45MB for 15s at 1080p 30fps; webcam adds ~5-10MB
- **Thread safety**: All access gated by `threading.Lock`
- **Auto-discard**: `deque(maxlen=buffer_seconds * fps)` drops oldest frames automatically

### Push (capture thread)

Called by `CaptureManager._on_capture_frame()` on every frame from the distributor:

```python
frame_buffer.push(frame_bgr, timestamp, webcam_bgr)
```

The webcam frame (if any) is captured at the same instant and stored alongside the main frame for perfect sync.

### Snapshot (clip save)

Returns a list of all buffered frames within a time range:

```python
frames = frame_buffer.snapshot()             # all frames
frames = frame_buffer.snapshot(t_start, t_end)  # time-windowed
```

This is the input to `write_clip()`.

## Audio Capture

Two independent `AudioBuffer` instances capture audio via WASAPI:

| Buffer | Mode | Source |
|--------|------|--------|
| Game audio | Loopback | System output device (captures what you hear) |
| Microphone | Input | Selected input device |

Both store rolling float32 PCM at 48kHz stereo, up to 65 seconds (~24MB each).

### Channel negotiation

WASAPI shared-mode loopback uses the Windows audio engine's mix format. The buffer tries channels in order:
- **Loopback**: stereo (2) → device reported → mono (1)
- **Microphone**: device reported (capped) → mono (1)

### Snapshot

```python
audio_pcm = audio_buffer.snapshot(start_time, end_time)
# Returns: np.ndarray float32, shape (samples, channels) or None
```

Time range matches the frame buffer's timestamps for A/V sync.

## Clip Encoding

### Trigger → Encode Flow

```
Hotkey / Global detected
  └─ CaptureManager._do_save_clip()
       ├─ frame_buffer.snapshot() → frames list
       ├─ audio_buffer.snapshot() → game PCM
       ├─ mic_buffer.snapshot()   → mic PCM
       ├─ Build output path
       ├─ Publish EVENT_CLIP_ENCODING_STARTED {path, frames}
       └─ Spawn daemon thread: _encode_clip()
            └─ write_clip(frames, audio, ...)
                 ├─ Parallel frame processing (ThreadPoolExecutor)
                 ├─ Write raw BGR24 to FFmpeg stdin
                 ├─ on_progress callback → EVENT_CLIP_ENCODING_PROGRESS
                 └─ FFmpeg muxes to MP4
            └─ Publish EVENT_CLIP_SAVED {path, duration, frames}
```

### Parallel Frame Processing

Frame decoding and compositing runs in a `ThreadPoolExecutor` with a sliding window:

```python
workers = min(4, os.cpu_count())
ahead = workers * 2  # max frames in flight

# Sliding window prevents 450 decoded frames in RAM at once
# (~6MB each at 1080p = 2.7GB without windowing)
while pending:
    frame_bgr = future.result()     # blocks until next frame ready
    proc.stdin.write(frame_bgr.tobytes())
    submit_next()                   # refill window
```

OpenCV's `imdecode`, `resize`, `GaussianBlur` all release the GIL, so threads achieve near-linear speedup on the C side.

### Per-Frame Processing Pipeline

For each frame in the buffer:

1. **JPEG decode** — `cv2.imdecode(jpeg_bytes)` → BGR numpy array
2. **Background compositing** (optional) — scale game frame + center on background canvas
3. **Blur regions** (optional) — `cv2.GaussianBlur` on normalized regions, in-place
4. **Webcam composite** (optional) — decode webcam JPEG, crop, resize, chroma key blend, overlay on frame in-place
5. **Resolution resize** — ensure frame matches FFmpeg's expected dimensions
6. **Pipe** — `proc.stdin.write(frame_bgr.tobytes())` raw BGR24

### FFmpeg Command

```
ffmpeg -y
  -f rawvideo -pix_fmt bgr24 -s {W}x{H} -r {effective_fps} -i pipe:0
  [-i game_audio.wav]
  [-i mic_audio.wav]
  [-vf "scale=...:flags=lanczos,pad=..."]       # only when no background composite
  -c:v libx264 -preset fast -b:v {bitrate} -pix_fmt yuv420p
  [-filter_complex "[2:a]{mic_filters}[mic_f]"]  # RNNoise + gate + compressor
  [-map 0:v -map 1:a -map [mic_f]]
  -c:a aac -b:a 128k
  [-metadata:s:a:0 "title=System Audio"]
  [-metadata:s:a:1 "title=Microphone"]
  .{stem}.encoding.mp4
```

- **Effective FPS**: Computed from actual frame timestamps (`(count-1) / duration`) rather than configured FPS, ensuring proper A/V sync
- **Temp output**: Written to `.{stem}.encoding.mp4` first, atomically renamed on success. Gallery scanner skips dotfiles, so incomplete clips are never shown.
- **Dual audio tracks**: Game and mic are separate tracks with metadata labels, allowing post-editing in video editors
- **Mic filters only**: Noise suppression (RNNoise/arnndn), noise gate, and compressor are applied only to the mic track

### Audio Filters (Mic Only)

Applied via FFmpeg's `-filter_complex` or `-af`:

| Filter | FFmpeg | Default |
|--------|--------|---------|
| Noise suppression | `arnndn=m=bd.rnnn:mix=1.0` | Mix 1.0 (fully denoised) |
| Noise gate | `agate=threshold=0.01:ratio=10:attack=5:release=200` | -40dB threshold |
| Compressor | `acompressor=threshold=-20dB:ratio=4:attack=5:release=100` | Moderate compression |

### Bitrate Calculation

Reference bitrates at 1080p (2,073,600 pixels):

| Quality | 1080p | Formula |
|---------|-------|---------|
| Low | 3 Mbps | `ref * (pixels / 2073600) ^ 0.75` |
| Medium | 6 Mbps | Power-law tracks diminishing returns |
| High | 12 Mbps | at higher resolutions |
| Ultra | 20 Mbps | |

### Thumbnail

A `.thumb.jpg` is saved alongside each clip for instant gallery loading:
- Frame closest to `thumb_time` (1s after global for auto-clips, first frame for manual)
- Scaled to fit 320x200, JPEG quality 80
- Gallery loads these instead of decoding the first video frame

### Progress Reporting

Progress events are published per whole-percent change (throttled):

```
EVENT_CLIP_ENCODING_STARTED  {path: str, frames: int}
EVENT_CLIP_ENCODING_PROGRESS {path: str, written: int, total: int}
EVENT_CLIP_SAVED             {path: str, duration: float, frames: int}
```

**Gallery**: An `EncodingThumbnailWidget` placeholder appears at the top of the gallery with a progress bar and percentage. Removed when `clip_saved` fires.

**Recording bar overlay**: Shows `• Clip 42%` appended to the timer label during encoding.

## Continuous Recording

Unlike clip saving (which snapshots the buffer), recording pipes live frames directly to FFmpeg:

```
Start recording
  └─ Open FFmpeg subprocess (stdin=PIPE)
  └─ _on_capture_frame() → _write_recording_frame(frame.copy())
       ├─ Background composite (optional)
       ├─ Blur regions (in-place)
       ├─ Webcam composite (in-place, from live webcam)
       └─ proc.stdin.write(frame_bgr.tobytes())

Stop recording
  └─ proc.stdin.close()
  └─ Wait for FFmpeg to finish
  └─ Finalize audio (drain remaining chunks)
  └─ Publish EVENT_RECORDING_STOPPED {path, duration}
```

Key differences from clip encoding:
- **Live**: Frames are written as they arrive, not from a buffer snapshot
- **frame.copy()**: The shared frame from the distributor is copied before in-place modifications (blur, webcam) to avoid corrupting it for other subscribers (OCR)
- **Audio drain**: A background thread snapshots audio every 5 seconds during recording to prevent buffer overflow
- **No parallel processing**: Single-threaded, as frames must be written in real-time order

### Error Handling

The recording pipe catches `BrokenPipeError`, `OSError`, and `ValueError` (closed file). On pipe failure, recording stops cleanly and logs the error.

## Screenshots

```
Hotkey / Global detected
  └─ CaptureManager._take_screenshot()
       ├─ _grab_frame() → BGR numpy array (live frame from distributor)
       ├─ build_screenshot_path() → Path with timestamp, target, amount
       └─ save_screenshot()
            ├─ compose_on_background() (optional)
            ├─ Scale to size_pct (25/50/75/100%)
            ├─ apply_blur_regions() (in-place GaussianBlur)
            └─ cv2.imwrite(path, frame, PNG)
```

### File Naming

```
{base_dir}/[YYYY-MM-DD/]{YYYY-MM-DD_HH-MM-SS}[_{target}][_{amount}].png
```

- Daily subfolder is optional (`screenshot_daily_subfolder` config)
- Target name and amount are included for global-triggered screenshots
- Unsafe filename characters (`<>:"/\|?*`) are replaced with `-`

## Webcam

### Architecture

A single `WebcamCapture` instance runs a background thread reading from the camera:

```python
while running:
    ret, frame = cap.read()
    with lock:
        latest_frame = frame      # single-frame buffer
    stop_event.wait(timeout=interval)
```

The latest frame is read by both the preview dialog and the frame buffer (via `get_latest_frame()`).

### Backend Fallback

On Windows, tries backends in order: MSMF → DirectShow. Each backend is tested with 5 stability reads before acceptance. If a backend fails 10 consecutive reads during capture, it switches to the next.

### Device Discovery

```python
WebcamCapture.discover_devices_async()   # background thread probe
WebcamCapture.get_cached_devices(timeout) # return cached results
WebcamCapture.list_devices(max_test=3)   # blocking probe
```

Probes device indices 0..2, stops after 2 consecutive failures. Redirects stderr at the OS level to suppress OpenCV's C++ warnings.

### Compositing

The webcam overlay is composited per-frame during encoding:

1. **Crop** — normalized `{x, y, w, h}` region within webcam frame
2. **Resize** — scale to `webcam_scale` fraction of main frame width
3. **Position** — normalized center `(position_x, position_y)` → pixel coords, clamped to bounds
4. **Chroma key** (optional) — HSV color distance → alpha mask → float32 blend

Chroma key compositing in the preview dialog resizes BGR *before* applying chroma to avoid premultiplied-alpha interpolation artifacts on transparency edges.

## Scaling Algorithms

Configurable via `clip_scaling` config field:

| Key | cv2 Constant | Performance (1080p) | Notes |
|-----|-------------|---------------------|-------|
| `lanczos` | `INTER_LANCZOS4` | ~7ms | 8x8, sharpest |
| `cubic` | `INTER_CUBIC` | ~2ms | 4x4, default, balanced |
| `linear` | `INTER_LINEAR` | ~1ms | 2x2, fast, slightly soft |
| `area` | `INTER_AREA` | ~2.3ms | Best for downscaling |
| `nearest` | `INTER_NEAREST` | ~1ms | Pixelated, fastest |

Default is `cubic` (bicubic). Preview widgets use `cubic` to save CPU.

## Resolution Presets

Grouped by aspect ratio:

| Group | Presets |
|-------|---------|
| 16:9 | 4K, 1440p, 1080p, 900p, 720p, 480p |
| 21:9 | UW-4K, UW-QHD, UW-FHD |
| 16:10 | WQXGA, WUXGA, WSXGA+, WXGA+, WXGA |
| 4:3 | UXGA, SXGA, XGA, SVGA |

`"source"` means no scaling — output matches capture resolution.

## Constants

```python
DEFAULT_BUFFER_SECONDS = 15
DEFAULT_POST_GLOBAL_SECONDS = 5
DEFAULT_SCREENSHOT_DELAY_S = 1.0
DEFAULT_CAPTURE_FPS = 30
JPEG_QUALITY = 80
AUDIO_SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
WEBCAM_OVERLAY_SCALE = 0.2      # 20% of frame width
WEBCAM_DEFAULT_POS_X = 0.88     # bottom-right area
WEBCAM_DEFAULT_POS_Y = 0.85
DEFAULT_SCALING_ALGORITHM = "cubic"
FILENAME_TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"
```

## Events

| Event | Data | When |
|-------|------|------|
| `EVENT_SCREENSHOT_SAVED` | `{path, timestamp, global_event?}` | Screenshot written to disk |
| `EVENT_CLIP_ENCODING_STARTED` | `{path, frames}` | Clip encoding begins |
| `EVENT_CLIP_ENCODING_PROGRESS` | `{path, written, total}` | Each 1% of frames encoded |
| `EVENT_CLIP_SAVED` | `{path, timestamp, duration, frames}` | Clip MP4 finalized |
| `EVENT_RECORDING_STARTED` | `{start_time}` | Continuous recording begins |
| `EVENT_RECORDING_STOPPED` | `{path, duration}` | Recording finalized |
| `EVENT_CAPTURE_ERROR` | `{error: str}` | Any capture failure |
| `EVENT_OWN_GLOBAL` | GlobalEvent dict | Own player's global detected |

## FFmpeg Discovery

Searched in order:
1. Explicit config path (`ffmpeg_path`)
2. System PATH (`shutil.which("ffmpeg")`)
3. User bin (`~/.entropia-nexus/bin/ffmpeg`)
4. Bundled (`client/bin/ffmpeg`)

Auto-download available on Windows from BtbN/FFmpeg-Builds.

## Recording Bar Overlay

Compact horizontal bar with:

| Element | Function |
|---------|----------|
| Screenshot button | Triggers `EVENT_HOTKEY_TRIGGERED "screenshot"` |
| Clip button | Triggers `EVENT_HOTKEY_TRIGGERED "save_clip"` (opens settings if clips disabled) |
| Record button | Toggles recording; pulsing red when active |
| Time label | `00:00 / ~remaining` idle; `HH:MM:SS / ~remaining` recording; `• Clip 42%` during encoding |
| Gallery button | Opens gallery page |

Disk space remaining is estimated from `free_bytes / (bitrate / 8)`, updated every 5 seconds.

## OBS Studio Integration

When OBS mode is enabled (`obs_enabled = True`), the client delegates all video capture, audio, webcam, and encoding to OBS Studio via obs-websocket (v5, built into OBS 28+). Screenshots remain handled by the client.

### What Changes

| Feature | Internal Mode | OBS Mode |
|---------|--------------|----------|
| Frame buffering | FrameBuffer JPEG deque | OBS Replay Buffer |
| Audio capture | WASAPI loopback | OBS audio sources |
| Webcam | WebcamCapture thread | OBS webcam source |
| Clip encoding | FFmpeg via clip_writer | OBS encoding |
| Recording | FFmpeg pipe | OBS recording |
| Screenshots | Client (unchanged) | Client (unchanged) |
| Auto-global triggers | Client conditions | Client conditions → OBS |

### Architecture

```
Client CaptureManager                    OBS Studio
  │                                        │
  ├─ own-global detected                   │
  │    └─ check conditions                 │
  │         └─ Timer(post_global_seconds)  │
  │              └─ OBSClient ────────────►│ SaveReplayBuffer
  │                                        │
  │              ◄─────────────────────────│ ReplayBufferSaved event
  │    └─ GetLastReplayBufferReplay ──────►│
  │    └─ Publish EVENT_CLIP_SAVED         │
  │                                        │
  ├─ hotkey: save_clip                     │
  │    └─ OBSClient.save_replay_buffer() ─►│
  │                                        │
  ├─ hotkey: toggle_recording              │
  │    └─ OBSClient.start/stop_record() ──►│
```

### Config Fields

| Field | Default | Description |
|-------|---------|-------------|
| `obs_enabled` | `false` | Enable OBS integration mode |
| `obs_host` | `"localhost"` | obs-websocket host |
| `obs_port` | `4455` | obs-websocket port |
| `obs_manage_replay_buffer` | `false` | Auto start/stop replay buffer with EU client |
| Password | (keyring) | Stored in system keyring, not config file |

### Events

| Event | Data | When |
|-------|------|------|
| `EVENT_OBS_CONNECTED` | `{host, port}` | WebSocket connection established |
| `EVENT_OBS_DISCONNECTED` | `{reason}` | Connection lost or closed |
| `EVENT_OBS_ERROR` | `{error}` | Command failure (replay buffer not active, etc.) |

### Connection Lifecycle

- Connects on startup if `obs_enabled`
- Automatic reconnection with exponential backoff (2s → 30s max)
- Disconnects on mode change or app shutdown
- Connection status shown in Settings and Recording Bar overlay (● connected, ○ disconnected)
- State synced on connect: queries current recording and replay buffer status

### Replay Buffer Management

When `obs_manage_replay_buffer` is enabled, the client automatically manages the OBS Replay Buffer:

- **Game opens** (EU client window detected): starts the replay buffer
- **Game closes** (EU client window lost): stops the replay buffer
- **Client exits**: stops the replay buffer
- **OBS reconnects**: starts the replay buffer if the game is already running

Detection uses a 3-second polling timer that checks the FrameDistributor's cached game window handle. The user is prompted to enable this when first activating OBS mode.

### Components

| File | Purpose |
|------|---------|
| `capture/obs_client.py` | OBS WebSocket wrapper — connection lifecycle, reconnection, request dispatch |

Uses the `obsws-python` library (synchronous `ReqClient` + `EventClient`).
