<!--
  @component RangeSlider
  Dual-knob range slider for filtering numeric ranges.
  Supports mouse, touch, and keyboard input.
-->
<script>
  import { createEventDispatcher } from 'svelte';

  export let min = 0;
  export let max = 100;
  export let step = 1;
  export let valueMin = 0;
  export let valueMax = 100;
  export let label = '';
  export let compact = false;

  const dispatch = createEventDispatcher();

  let trackEl;
  let dragging = null; // 'min' | 'max' | null

  $: range = max - min || 1;
  $: pctMin = ((valueMin - min) / range) * 100;
  $: pctMax = ((valueMax - min) / range) * 100;
  $: isFullRange = valueMin <= min && valueMax >= max;
  $: displayText = isFullRange ? 'All' : `${valueMin}–${valueMax}`;
  // Reserve width for the widest possible label to prevent layout shifts
  $: maxChars = `${max}`.length * 2 + 1; // e.g. "4000–4000" = 9ch
  $: labelWidth = `${Math.max(3, maxChars)}ch`; // minimum 3ch for "All"

  function clamp(v) {
    return Math.round(Math.min(max, Math.max(min, v)) / step) * step;
  }

  function pctToValue(pct) {
    return clamp(min + (pct / 100) * range);
  }

  function getTrackPct(clientX) {
    if (!trackEl) return 0;
    const rect = trackEl.getBoundingClientRect();
    return Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
  }

  function onPointerDown(e, thumb) {
    e.preventDefault();
    dragging = thumb;
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }

  function onPointerMove(e) {
    if (!dragging) return;
    const pct = getTrackPct(e.clientX);
    const val = pctToValue(pct);
    if (dragging === 'min') {
      valueMin = Math.min(val, valueMax);
    } else {
      valueMax = Math.max(val, valueMin);
    }
  }

  function onPointerUp() {
    dragging = null;
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    dispatch('change', { min: valueMin, max: valueMax });
  }

  function onTrackClick(e) {
    if (dragging) return;
    const pct = getTrackPct(e.clientX);
    const val = pctToValue(pct);
    // Move whichever thumb is closer
    const distMin = Math.abs(val - valueMin);
    const distMax = Math.abs(val - valueMax);
    if (distMin <= distMax) {
      valueMin = Math.min(val, valueMax);
    } else {
      valueMax = Math.max(val, valueMin);
    }
    dispatch('change', { min: valueMin, max: valueMax });
  }

  function onKeydown(e, thumb) {
    let delta = 0;
    if (e.key === 'ArrowRight' || e.key === 'ArrowUp') delta = step;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') delta = -step;
    else if (e.key === 'Home') { delta = -Infinity; }
    else if (e.key === 'End') { delta = Infinity; }
    else return;

    e.preventDefault();
    if (thumb === 'min') {
      valueMin = clamp(delta === -Infinity ? min : delta === Infinity ? valueMax : valueMin + delta);
      valueMin = Math.min(valueMin, valueMax);
    } else {
      valueMax = clamp(delta === -Infinity ? valueMin : delta === Infinity ? max : valueMax + delta);
      valueMax = Math.max(valueMax, valueMin);
    }
    dispatch('change', { min: valueMin, max: valueMax });
  }
</script>

<div class="range-slider" class:compact>
  {#if label}
    <span class="range-label">{label}: <strong style="display:inline-block;min-width:{labelWidth};text-align:right">{displayText}</strong></span>
  {/if}
  <div
    class="track"
    bind:this={trackEl}
    role="presentation"
    on:click={onTrackClick}
  >
    <div class="track-bg"></div>
    <div class="track-fill" style="left:{pctMin}%;right:{100-pctMax}%"></div>
    <div
      class="thumb"
      style="left:{pctMin}%"
      role="slider"
      tabindex="0"
      aria-label="{label} minimum"
      aria-valuemin={min}
      aria-valuemax={valueMax}
      aria-valuenow={valueMin}
      on:pointerdown={(e) => onPointerDown(e, 'min')}
      on:keydown={(e) => onKeydown(e, 'min')}
    ></div>
    <div
      class="thumb"
      style="left:{pctMax}%"
      role="slider"
      tabindex="0"
      aria-label="{label} maximum"
      aria-valuemin={valueMin}
      aria-valuemax={max}
      aria-valuenow={valueMax}
      on:pointerdown={(e) => onPointerDown(e, 'max')}
      on:keydown={(e) => onKeydown(e, 'max')}
    ></div>
  </div>
</div>

<style>
  .range-slider {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    user-select: none;
    touch-action: none;
  }

  .range-label {
    font-size: 0.8rem;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .range-label strong {
    color: var(--text-color);
  }

  .track {
    position: relative;
    width: 120px;
    height: 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    margin: 0 7px; /* half the thumb width so thumbs don't overlap neighbors */
  }

  .compact .track {
    width: 100px;
  }

  .track-bg {
    position: absolute;
    left: 0;
    right: 0;
    height: 4px;
    background: var(--border-color);
    border-radius: 2px;
  }

  .track-fill {
    position: absolute;
    height: 4px;
    background: var(--accent-color);
    border-radius: 2px;
  }

  .thumb {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent-color);
    border: 2px solid var(--bg-secondary, var(--secondary-color));
    transform: translateX(-50%);
    cursor: grab;
    z-index: 1;
    outline: none;
    transition: box-shadow 0.15s;
  }

  .thumb:hover, .thumb:focus-visible {
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent-color) 30%, transparent);
  }

  .thumb:active {
    cursor: grabbing;
  }

  @media (max-width: 600px) {
    .track {
      width: 80px;
    }
    .compact .track {
      width: 70px;
    }
  }
</style>
