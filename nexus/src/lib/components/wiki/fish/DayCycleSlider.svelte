<!--
  @component DayCycleSlider
  Horizontal bar representing the 0..1 day cycle. In view mode it paints
  only the range [start, end] (wrapping through 1.0 -> 0.0 when start>end)
  as a dark-to-bright blue gradient with the rest dimmed. In edit mode it
  shows two draggable thumbs (start, end) so users can set a range by
  direct manipulation; swapping the thumbs' relative position wraps the
  range through midnight.

  Values are on a 0.05 grid (21 discrete positions, 1.0 wraps to 0.0).
  Both null -> "Unknown" (we haven't figured out the window for this fish
  yet, distinct from "confirmed all-day"). When editing starts from null,
  both are seeded to a sensible default so the user can drag from there.
-->
<script>
  // @ts-nocheck

  const STEP = 0.05;
  const STEPS = 20; // 0.00..1.00 inclusive = 21 grid points; 20 intervals

  /**
   * @typedef {Object} Props
   * @property {number|null} [start]   Start of the window, 0..1 on the 0.05 grid, or null for "Unknown"
   * @property {number|null} [end]     End of the window, 0..1 on the 0.05 grid, or null for "Unknown"
   * @property {boolean} [editable]    True to show draggable thumbs
   * @property {(range: {start: number|null, end: number|null}) => void} [onchange]
   */
  let {
    start = null,
    end = null,
    editable = false,
    onchange
  } = $props();

  let trackEl = $state(null);
  let dragging = $state(null); // 'start' | 'end' | null

  // Both null = unknown window; otherwise both expected to be set.
  let isUnknown = $derived(start == null && end == null);

  // Snap a continuous 0..1 value to the 0.05 grid.
  function snap(v) {
    return Math.round(v * STEPS) / STEPS;
  }

  function clamp01(v) {
    return Math.max(0, Math.min(1, v));
  }

  function pctToValue(pct) {
    return snap(clamp01(pct / 100));
  }

  function getTrackPct(clientX) {
    if (!trackEl) return 0;
    const rect = trackEl.getBoundingClientRect();
    return Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
  }

  function fmtLabel(v) {
    if (v == null) return '—';
    // Display as HH:MM on a 24h clock so the cycle is readable.
    const total = v * 24;
    const h = Math.floor(total);
    const m = Math.round((total - h) * 60);
    const hh = h >= 24 ? '00' : String(h).padStart(2, '0');
    const mm = String(m).padStart(2, '0');
    return `${hh}:${mm}`;
  }

  let rangeLabel = $derived.by(() => {
    if (isUnknown) return 'Unknown';
    return `${fmtLabel(start)} – ${fmtLabel(end)}${start > end ? ' (wraps)' : ''}`;
  });

  // Active painted segments (as [leftPct, rightPct] pairs). Wrap -> two
  // segments. Equal start/end -> full cycle (cyclic interpretation).
  let segments = $derived.by(() => {
    if (isUnknown) return [[0, 100]];
    const s = start * 100, e = end * 100;
    if (s === e) return [[0, 100]];
    if (s < e) return [[s, e]];
    return [[0, e], [s, 100]];
  });

  function emit(nextStart, nextEnd) {
    onchange?.({ start: nextStart, end: nextEnd });
  }

  function setUnknown() {
    emit(null, null);
  }

  function setDefault() {
    // Daylight hours as a reasonable starting point.
    emit(0.25, 0.75);
  }

  function onPointerDown(e, thumb) {
    if (!editable) return;
    e.preventDefault();
    dragging = thumb;
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }

  function onPointerMove(e) {
    if (!dragging) return;
    const val = pctToValue(getTrackPct(e.clientX));
    if (dragging === 'start') emit(val, end);
    else emit(start, val);
  }

  function onPointerUp() {
    dragging = null;
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
  }

  function onTrackClick(e) {
    if (!editable || dragging) return;
    if (isUnknown) { setDefault(); return; }
    const val = pctToValue(getTrackPct(e.clientX));
    // Move whichever thumb is closer along the non-wrapped distance.
    const dStart = Math.abs(val - start);
    const dEnd = Math.abs(val - end);
    if (dStart <= dEnd) emit(val, end);
    else emit(start, val);
  }

  function onKeydown(e, thumb) {
    if (!editable) return;
    let delta = 0;
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') delta = STEP;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') delta = -STEP;
    else if (e.key === 'Home') { delta = -Infinity; }
    else if (e.key === 'End') { delta = Infinity; }
    else return;
    e.preventDefault();

    const cur = thumb === 'start' ? start : end;
    let next;
    if (delta === -Infinity) next = 0;
    else if (delta === Infinity) next = 1;
    else next = snap(clamp01(cur + delta));

    if (thumb === 'start') emit(next, end);
    else emit(start, next);
  }

  let startPct = $derived(start != null ? start * 100 : 0);
  let endPct = $derived(end != null ? end * 100 : 100);
</script>

<div class="day-cycle">
  <div class="day-cycle-header">
    <span class="range-label">{rangeLabel}</span>
    {#if editable}
      {#if isUnknown}
        <button type="button" class="mini-btn" onclick={setDefault}>Set range</button>
      {:else}
        <button type="button" class="mini-btn" onclick={setUnknown}>Mark unknown</button>
      {/if}
    {/if}
  </div>

  <div
    class="track"
    class:editable
    bind:this={trackEl}
    role="presentation"
    onclick={onTrackClick}
  >
    <!-- Full day/night gradient, dimmed. Midnight at both ends, noon in the middle. -->
    <div class="track-base"></div>

    <!-- Active segments repaint the gradient at full brightness. Each
         segment uses a background-size + background-position trick so the
         gradient stays aligned with the underlying track, preserving the
         day/night cue. -->
    {#each segments as [l, r]}
      {#if r > l}
        <div
          class="track-active"
          style="left:{l}%; width:{r - l}%; background-size:{100 / ((r - l) / 100)}% 100%; background-position:-{l / ((r - l) / 100)}% 0;"
        ></div>
      {/if}
    {/each}

    <!-- Tick marks every 6h (0.25 intervals) as subtle guides. -->
    <div class="tick" style="left:25%"></div>
    <div class="tick" style="left:50%"></div>
    <div class="tick" style="left:75%"></div>

    {#if editable && !isUnknown}
      <div
        class="thumb"
        style="left:{startPct}%"
        role="slider"
        tabindex="0"
        aria-label="Start of window"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={start}
        aria-valuetext={fmtLabel(start)}
        onpointerdown={(e) => onPointerDown(e, 'start')}
        onkeydown={(e) => onKeydown(e, 'start')}
      >
        <span class="thumb-label">{fmtLabel(start)}</span>
      </div>
      <div
        class="thumb"
        style="left:{endPct}%"
        role="slider"
        tabindex="0"
        aria-label="End of window"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={end}
        aria-valuetext={fmtLabel(end)}
        onpointerdown={(e) => onPointerDown(e, 'end')}
        onkeydown={(e) => onKeydown(e, 'end')}
      >
        <span class="thumb-label">{fmtLabel(end)}</span>
      </div>
    {/if}
  </div>

  <div class="day-cycle-axis">
    <span>00:00</span>
    <span>06:00</span>
    <span>12:00</span>
    <span>18:00</span>
    <span>24:00</span>
  </div>
</div>

<style>
  .day-cycle {
    display: flex;
    flex-direction: column;
    gap: 4px;
    user-select: none;
    touch-action: none;
    width: 100%;
  }

  .day-cycle-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    font-size: 12px;
    color: var(--text-color);
  }

  .range-label {
    font-weight: 500;
  }

  .mini-btn {
    padding: 2px 8px;
    background: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
  }

  .mini-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .track {
    position: relative;
    width: 100%;
    height: 22px;
    border-radius: 4px;
    overflow: visible;
    cursor: default;
  }

  .track.editable {
    cursor: pointer;
  }

  .track-base,
  .track-active {
    position: absolute;
    top: 0;
    bottom: 0;
    border-radius: 3px;
    /* Day/night gradient across 0..1:
       midnight (dark navy) -> dawn (twilight) -> noon (bright sky) ->
       dusk (twilight) -> midnight (dark navy). */
    background-image: linear-gradient(
      to right,
      #050a1a 0%,
      #0e1a3a 12%,
      #2a4a85 25%,
      #6fa8dc 40%,
      #bcd9f2 50%,
      #6fa8dc 60%,
      #2a4a85 75%,
      #0e1a3a 88%,
      #050a1a 100%
    );
  }

  .track-base {
    left: 0;
    right: 0;
    opacity: 0.25;
    border: 1px solid var(--border-color, #555);
  }

  .track-active {
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.12);
  }

  .tick {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1px;
    background: rgba(255, 255, 255, 0.15);
    pointer-events: none;
  }

  .thumb {
    position: absolute;
    top: 50%;
    width: 14px;
    height: 28px;
    background: var(--accent-color, #4a9eff);
    border: 2px solid var(--bg-secondary, var(--secondary-color, #1a1a1a));
    border-radius: 4px;
    transform: translate(-50%, -50%);
    cursor: grab;
    z-index: 2;
    outline: none;
    transition: box-shadow 0.15s;
  }

  .thumb:hover,
  .thumb:focus-visible {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent-color) 30%, transparent);
  }

  .thumb:active {
    cursor: grabbing;
  }

  .thumb-label {
    position: absolute;
    left: 50%;
    bottom: calc(100% + 4px);
    transform: translateX(-50%);
    font-size: 10px;
    padding: 1px 5px;
    background: var(--bg-color, var(--primary-color, #1a1a1a));
    color: var(--text-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    white-space: nowrap;
    pointer-events: none;
  }

  .day-cycle-axis {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: var(--text-muted, #999);
  }
</style>
