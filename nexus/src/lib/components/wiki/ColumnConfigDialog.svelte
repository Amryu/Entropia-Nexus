<!--
  @component ColumnConfigDialog
  Modal dialog for configuring which columns are visible and their order.
  Supports drag-and-drop reordering (desktop + touch).
-->
<script>
  // @ts-nocheck
  import { untrack } from 'svelte';

  /**
   * @typedef {Object} Props
   * @property {Array} [visibleColumns]
   * @property {Array} [allColumns]
   * @property {Function} [onapply]
   * @property {Function} [oncancel]
   */

  /** @type {Props} */
  let { visibleColumns = [], allColumns = [], onapply, oncancel } = $props();

  // Internal state: working copy of visible column keys (in order)
  let selectedKeys = $state(untrack(() => visibleColumns.map(c => c.key)));

  // Drag state
  let dragIndex = $state(null);
  let dragOverIndex = $state(null);
  let touchDragElement = null;
  let touchStartY = 0;
  let touchCurrentY = 0;
  let touchStarted = false;

  // Build lookup map for all columns
  let columnMap = $derived(Object.fromEntries(allColumns.map(c => [c.key, c])));

  // Available columns = all columns not currently selected
  let availableColumns = $derived(allColumns.filter(c => !selectedKeys.includes(c.key)));

  // Resolved visible columns from selected keys
  let resolvedVisible = $derived(selectedKeys.map(k => columnMap[k]).filter(Boolean));

  function addColumn(key) {
    selectedKeys = [...selectedKeys, key];
  }

  function removeColumn(key) {
    selectedKeys = selectedKeys.filter(k => k !== key);
  }

  function moveColumn(fromIndex, toIndex) {
    if (fromIndex === toIndex) return;
    const updated = [...selectedKeys];
    const [moved] = updated.splice(fromIndex, 1);
    updated.splice(toIndex, 0, moved);
    selectedKeys = updated;
  }

  // Desktop drag-and-drop
  function handleDragStart(e, index) {
    dragIndex = index;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
  }

  function handleDragOver(e, index) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    dragOverIndex = index;
  }

  function handleDragLeave() {
    dragOverIndex = null;
  }

  function handleDrop(e, index) {
    e.preventDefault();
    if (dragIndex !== null && dragIndex !== index) {
      moveColumn(dragIndex, index);
    }
    dragIndex = null;
    dragOverIndex = null;
  }

  function handleDragEnd() {
    dragIndex = null;
    dragOverIndex = null;
  }

  // Touch drag-and-drop
  function handleTouchStart(e, index) {
    const touch = e.touches[0];
    touchStartY = touch.clientY;
    touchCurrentY = touch.clientY;
    dragIndex = index;
    touchStarted = false;
  }

  function handleTouchMove(e, index) {
    if (dragIndex === null) return;
    const touch = e.touches[0];
    touchCurrentY = touch.clientY;

    if (!touchStarted && Math.abs(touchCurrentY - touchStartY) > 10) {
      touchStarted = true;
    }

    if (!touchStarted) return;
    e.preventDefault();

    // Find which item we're over
    const items = document.querySelectorAll('.visible-item');
    for (let i = 0; i < items.length; i++) {
      const rect = items[i].getBoundingClientRect();
      if (touchCurrentY >= rect.top && touchCurrentY <= rect.bottom) {
        dragOverIndex = i;
        break;
      }
    }
  }

  function handleTouchEnd() {
    if (dragIndex !== null && dragOverIndex !== null && dragIndex !== dragOverIndex && touchStarted) {
      moveColumn(dragIndex, dragOverIndex);
    }
    dragIndex = null;
    dragOverIndex = null;
    touchStarted = false;
  }

  function handleApply() {
    onapply?.({ columnKeys: selectedKeys });
  }

  function handleCancel() {
    oncancel?.();
  }

  function handleOverlayClick(e) {
    if (e.target.classList.contains('modal-overlay')) {
      handleCancel();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      handleCancel();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />
<div
  class="modal-overlay"
  role="presentation"
  onclick={handleOverlayClick}
>
  <div class="modal" role="dialog" aria-modal="true">
    <h3>Configure Columns</h3>

    <div class="hint">First 5 columns are shown in expanded view. All shown in full-width.</div>

    <div class="section-label">Visible Columns ({resolvedVisible.length})</div>
    <div class="visible-list">
      {#each resolvedVisible as column, i (column.key)}
        <div
          class="visible-item"
          class:drag-over={dragOverIndex === i && dragIndex !== i}
          class:dragging={dragIndex === i}
          draggable="true"
          ondragstart={(e) => handleDragStart(e, i)}
          ondragover={(e) => handleDragOver(e, i)}
          ondragleave={handleDragLeave}
          ondrop={(e) => handleDrop(e, i)}
          ondragend={handleDragEnd}
          ontouchstart={(e) => handleTouchStart(e, i)}
          ontouchmove={(e) => handleTouchMove(e, i)}
          ontouchend={handleTouchEnd}
        >
          <span class="drag-handle" title="Drag to reorder">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="8" cy="4" r="2"/><circle cx="16" cy="4" r="2"/>
              <circle cx="8" cy="12" r="2"/><circle cx="16" cy="12" r="2"/>
              <circle cx="8" cy="20" r="2"/><circle cx="16" cy="20" r="2"/>
            </svg>
          </span>
          <span class="col-index">{i + 1}</span>
          <span class="col-name">{column.header}</span>
          {#if i < 5}
            <span class="col-badge expanded">E</span>
          {/if}
          <button class="remove-btn" onclick={() => removeColumn(column.key)} title="Remove column">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 6L6 18M6 6l12 12"/>
            </svg>
          </button>
        </div>
      {/each}
      {#if resolvedVisible.length === 0}
        <div class="empty-msg">No columns selected</div>
      {/if}
    </div>

    {#if availableColumns.length > 0}
      <div class="section-label">Available Columns ({availableColumns.length})</div>
      <div class="available-list">
        {#each availableColumns as column (column.key)}
          <button class="available-item" onclick={() => addColumn(column.key)}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            <span>{column.header}</span>
          </button>
        {/each}
      </div>
    {/if}

    <div class="actions">
      <button class="btn-cancel" onclick={handleCancel}>Cancel</button>
      <button class="btn-apply" onclick={handleApply}>Apply</button>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
    padding: 16px;
    box-sizing: border-box;
  }

  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 420px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  .modal h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
    font-weight: 600;
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted, #999);
    margin-bottom: 16px;
  }

  .section-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }

  .visible-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: 16px;
    min-height: 36px;
  }

  .visible-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    cursor: grab;
    user-select: none;
    transition: border-color 0.15s;
  }

  .visible-item:hover {
    border-color: var(--accent-color, #4a9eff);
  }

  .visible-item.dragging {
    opacity: 0.4;
  }

  .visible-item.drag-over {
    border-color: var(--accent-color, #4a9eff);
    border-top: 2px solid var(--accent-color, #4a9eff);
  }

  .drag-handle {
    color: var(--text-muted, #999);
    display: flex;
    align-items: center;
    flex-shrink: 0;
    cursor: grab;
  }

  .col-index {
    font-size: 10px;
    color: var(--text-muted, #999);
    min-width: 16px;
    text-align: center;
    flex-shrink: 0;
  }

  .col-name {
    flex: 1;
    font-size: 13px;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .col-badge {
    font-size: 9px;
    font-weight: 600;
    padding: 1px 4px;
    border-radius: 3px;
    flex-shrink: 0;
  }

  .col-badge.expanded {
    background: var(--accent-color, #4a9eff);
    color: white;
  }

  .remove-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s;
  }

  .remove-btn:hover {
    background: var(--error-color, #ef4444);
    color: white;
    border-color: var(--error-color, #ef4444);
  }

  .available-list {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 20px;
  }

  .available-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    font-size: 12px;
    background: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
  }

  .available-item:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .empty-msg {
    font-size: 12px;
    color: var(--text-muted, #999);
    font-style: italic;
    padding: 8px;
    text-align: center;
  }

  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  .btn-cancel {
    padding: 8px 16px;
    font-size: 13px;
    background: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    cursor: pointer;
  }

  .btn-cancel:hover {
    background: var(--hover-color);
  }

  .btn-apply {
    padding: 8px 16px;
    font-size: 13px;
    background: var(--accent-color, #4a9eff);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
    font-weight: 500;
  }

  .btn-apply:hover {
    filter: brightness(1.1);
  }
</style>
