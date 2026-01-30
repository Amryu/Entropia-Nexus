<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import JsonTreeNode from './JsonTreeNode.svelte';

  export let show = false;
  export let title = 'Compare JSON';
  export let oldData = null;
  export let newData = null;
  export let oldLabel = 'Previous';
  export let newLabel = 'Current';

  const dispatch = createEventDispatcher();

  let leftPane;
  let rightPane;
  let syncingScroll = false;

  // Shared collapse state between both panes (by JSON path)
  let collapsedPaths = new Set();

  function close() {
    dispatch('close');
  }

  function handleKeydown(e) {
    if (e.key === 'Escape' && show) {
      close();
    }
  }

  // Line-based scroll sync
  function syncScroll(source, target) {
    if (syncingScroll) return;
    syncingScroll = true;
    target.scrollTop = source.scrollTop;
    requestAnimationFrame(() => {
      syncingScroll = false;
    });
  }

  function handleLeftScroll() {
    if (leftPane && rightPane) {
      syncScroll(leftPane, rightPane);
    }
  }

  function handleRightScroll() {
    if (leftPane && rightPane) {
      syncScroll(rightPane, leftPane);
    }
  }

  // Toggle collapse state for a path
  function toggleCollapse(path) {
    if (collapsedPaths.has(path)) {
      collapsedPaths.delete(path);
    } else {
      collapsedPaths.add(path);
    }
    collapsedPaths = new Set(collapsedPaths); // Trigger reactivity with new Set
  }

  // Keys to strip from comparison (API-only fields)
  const stripKeys = ['Links', '$Url', 'ItemId'];

  // Priority keys for sorting
  const priorityKeys = ['Id', 'Name', 'Properties'];

  // Recursively strip API-only fields and sort keys
  function cleanAndSort(obj) {
    if (obj === null || obj === undefined) return obj;
    if (typeof obj !== 'object') return obj;

    if (Array.isArray(obj)) {
      return obj.map(cleanAndSort);
    }

    const result = {};
    const keys = Object.keys(obj).filter(k => !stripKeys.includes(k));

    keys.sort((a, b) => {
      const aIdx = priorityKeys.indexOf(a);
      const bIdx = priorityKeys.indexOf(b);
      if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
      if (aIdx !== -1) return -1;
      if (bIdx !== -1) return 1;

      const aVal = obj[a];
      const bVal = obj[b];
      const aCat = Array.isArray(aVal) ? 3 : (aVal && typeof aVal === 'object') ? 2 : 1;
      const bCat = Array.isArray(bVal) ? 3 : (bVal && typeof bVal === 'object') ? 2 : 1;
      if (aCat !== bCat) return aCat - bCat;

      return a.localeCompare(b);
    });

    for (const key of keys) {
      result[key] = cleanAndSort(obj[key]);
    }
    return result;
  }

  $: cleanedOld = oldData ? cleanAndSort(oldData) : null;
  $: cleanedNew = newData ? cleanAndSort(newData) : null;

  // Reset collapsed state when dialog opens
  $: if (show) {
    collapsedPaths = new Set();
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if show}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="dialog-overlay" on:click={close}>
    <div class="dialog" on:click|stopPropagation>
      <div class="dialog-header">
        <h3>{title}</h3>
        <button type="button" class="close-btn" on:click={close}>×</button>
      </div>
      <div class="dialog-body">
        <div class="compare-container">
          <div class="compare-pane">
            <div class="pane-header">{oldLabel}</div>
            <div
              class="pane-content"
              bind:this={leftPane}
              on:scroll={handleLeftScroll}
            >
              {#if cleanedOld}
                <JsonTreeNode
                  data={cleanedOld}
                  path=""
                  {collapsedPaths}
                  {toggleCollapse}
                />
              {:else}
                <span class="null-value">No data</span>
              {/if}
            </div>
          </div>
          <div class="compare-pane">
            <div class="pane-header">{newLabel}</div>
            <div
              class="pane-content"
              bind:this={rightPane}
              on:scroll={handleRightScroll}
            >
              {#if cleanedNew}
                <JsonTreeNode
                  data={cleanedNew}
                  path=""
                  {collapsedPaths}
                  {toggleCollapse}
                />
              {:else}
                <span class="null-value">No data</span>
              {/if}
            </div>
          </div>
        </div>
      </div>
      <div class="dialog-footer">
        <button type="button" class="btn" on:click={close}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 95%;
    max-width: 1400px;
    height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
    overflow: hidden;
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
    background-color: var(--hover-color);
    flex-shrink: 0;
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 16px;
    color: var(--text-color);
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 24px;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0;
    line-height: 1;
  }

  .close-btn:hover {
    color: var(--text-color);
  }

  .dialog-body {
    flex: 1;
    overflow: hidden;
    padding: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .compare-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .compare-pane {
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--border-color);
    overflow: hidden;
    min-height: 0;
  }

  .compare-pane:last-child {
    border-right: none;
  }

  .pane-header {
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-muted);
    background-color: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    flex-shrink: 0;
  }

  .pane-content {
    flex: 1;
    margin: 0;
    padding: 16px;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.6;
    background-color: var(--primary-color);
    color: var(--text-color);
    overflow: auto;
    min-height: 0;
  }

  .dialog-footer {
    padding: 12px 20px;
    border-top: 1px solid var(--border-color);
    display: flex;
    justify-content: flex-end;
    background-color: var(--hover-color);
    flex-shrink: 0;
  }

  .btn {
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .null-value {
    color: #569cd6;
    font-style: italic;
  }

  @media (max-width: 768px) {
    .compare-container {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr 1fr;
    }

    .compare-pane {
      border-right: none;
      border-bottom: 1px solid var(--border-color);
    }

    .compare-pane:last-child {
      border-bottom: none;
    }
  }
</style>
