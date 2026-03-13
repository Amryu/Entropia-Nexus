<!--
  @component WaypointCopyButton
  A reusable button that copies a waypoint to clipboard.
  Can be used standalone or in tables (FancyTable compatible).

  Usage standalone:
    <WaypointCopyButton waypoint="[Calypso, 123, 456, 100, Location]" />

  Usage in FancyTable (pass column.component):
    { key: 'waypoint', header: 'Location', component: WaypointCopyButton }
-->
<script>
  // @ts-nocheck
  import { copyToClipboard } from '$lib/util';

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string} [waypoint] - Waypoint string - used in standalone mode
   * @property {any} [row] - FancyTable compatibility: row data
   * @property {string} [value] - FancyTable compatibility: cell value (waypoint)
   * @property {boolean} [compact] - Whether to show the full waypoint text or just an icon
   * @property {string} [label] - Custom label when not showing waypoint text
   */

  /** @type {Props} */
  let {
    waypoint = '',
    row = null,
    value = '',
    compact = false,
    label = ''
  } = $props();

  let copied = $state(false);
  let timeout = null;

  // Use waypoint prop if provided, otherwise fall back to value (FancyTable mode)
  let actualWaypoint = $derived(waypoint || value || '');

  async function handleCopy() {
    const success = await copyToClipboard(`/wp ${actualWaypoint}`);
    if (success) {
      if (timeout) clearTimeout(timeout);
      copied = true;
      timeout = setTimeout(() => {
        copied = false;
      }, 2000);
    }
  }
</script>

<button
  class="waypoint-btn"
  class:copied
  class:compact
  onclick={handleCopy}
  title="Click to copy waypoint"
  disabled={!actualWaypoint}
>
  <!-- Copied overlay - positioned absolute so it doesn't affect layout -->
  <span class="copied-overlay" class:visible={copied}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polyline points="20 6 9 17 4 12"></polyline>
    </svg>
    <span class="overlay-text">Copied!</span>
  </span>

  <!-- Normal content - always rendered to maintain width -->
  <span class="normal-content" class:hidden={copied}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
    </svg>
    {#if compact && label}
      <span class="waypoint-text">{label}</span>
    {:else if !compact}
      <span class="waypoint-text">/wp {actualWaypoint}</span>
    {/if}
  </span>
</button>

<style>
  .waypoint-btn {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background-color: var(--bg-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    font-size: 12px;
    cursor: pointer;
    transition: background-color 0.15s, border-color 0.15s, color 0.15s;
    max-width: 100%;
    overflow: hidden;
  }

  .waypoint-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .waypoint-btn:not(:disabled):hover {
    background-color: var(--accent-color, #4a9eff) !important;
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .waypoint-btn.copied {
    background-color: var(--success-color, #28a745) !important;
    border-color: var(--success-color, #28a745);
    color: white;
  }

  .waypoint-btn.compact {
    padding: 4px 8px;
    font-size: 11px;
  }

  /* Normal content - maintains the button width */
  .normal-content {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    overflow: hidden;
  }

  .normal-content.hidden {
    visibility: hidden;
  }

  /* Copied overlay - positioned over normal content */
  .copied-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    opacity: 0;
    pointer-events: none;
  }

  .copied-overlay.visible {
    opacity: 1;
  }

  .overlay-text {
    font-family: monospace;
    font-size: 11px;
  }

  /* Hide "Copied!" text in compact mode - just show checkmark */
  .waypoint-btn.compact .overlay-text {
    display: none;
  }

  .waypoint-text {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    font-family: monospace;
    font-size: 11px;
  }

  .waypoint-btn svg,
  .normal-content svg,
  .copied-overlay svg {
    flex-shrink: 0;
  }
</style>
