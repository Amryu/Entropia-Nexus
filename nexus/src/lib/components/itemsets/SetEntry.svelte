<!--
  @component SetEntry
  Armor/clothing set entry in an item set.
  Shows the set name with a gender selector and expandable pieces list.
  Each piece can have individual currentTT metadata.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { slide } from 'svelte/transition';

  const dispatch = createEventDispatcher();

  /** @type {object} Set entry: { setType, setId, setName, gender?, pieces[] } */
  export let entry;

  /** @type {boolean} Whether pieces are shown expanded */
  export let expanded = false;

  $: pieces = entry?.pieces || [];
  $: hasPieces = pieces.length > 0;

  function toggleExpanded() {
    expanded = !expanded;
  }

  function updateGender(gender) {
    dispatch('update', { ...entry, gender: gender || undefined });
  }

  function updatePieceMeta(index, field, value) {
    const newPieces = [...pieces];
    const piece = { ...newPieces[index] };
    piece.meta = { ...(piece.meta || {}), [field]: value };
    newPieces[index] = piece;
    dispatch('update', { ...entry, pieces: newPieces });
  }

  function remove() {
    dispatch('remove');
  }
</script>

<div class="set-entry">
  <div class="set-header">
    <button class="btn-remove" on:click={remove} title="Remove set">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    </button>
    <div class="set-info" on:click={toggleExpanded} role="button" tabindex="0" on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleExpanded()}>
      <span class="set-type-badge">{entry.setType === 'ArmorSet' ? 'Armor' : 'Clothing'}</span>
      <span class="set-name">{entry.setName}</span>
      <span class="set-piece-count">{pieces.length}pc</span>
      {#if hasPieces}
        <span class="expand-icon" class:rotated={expanded}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </span>
      {/if}
    </div>
    <select
      class="gender-select"
      value={entry.gender || ''}
      on:change={(e) => updateGender(e.target.value)}
    >
      <option value="">Gender...</option>
      <option value="Male">Male</option>
      <option value="Female">Female</option>
    </select>
  </div>

  {#if expanded && hasPieces}
    <div class="set-pieces" transition:slide={{ duration: 150 }}>
      {#each pieces as piece, idx}
        <div class="piece-row">
          <span class="piece-connector"></span>
          <span class="piece-slot">{piece.slot || ''}</span>
          <span class="piece-name">{piece.name}</span>
          <div class="piece-tt">
            <label class="piece-tt-label">TT</label>
            <input
              type="number"
              class="piece-tt-input"
              value={piece.meta?.currentTT ?? ''}
              min="0"
              step="0.01"
              placeholder="0.00"
              on:change={(e) => updatePieceMeta(idx, 'currentTT', e.target.value === '' ? null : Number(e.target.value))}
            />
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .set-entry {
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }

  .set-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
  }

  .set-info {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    min-width: 0;
    cursor: pointer;
  }

  .set-info:focus {
    outline: none;
  }

  .set-type-badge {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 3px;
    background-color: var(--accent-color);
    color: white;
    flex-shrink: 0;
  }

  .set-name {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-color);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .set-piece-count {
    font-size: 11px;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .expand-icon {
    display: flex;
    align-items: center;
    color: var(--text-muted);
    transition: transform 0.15s;
    flex-shrink: 0;
  }

  .expand-icon.rotated {
    transform: rotate(180deg);
  }

  .gender-select {
    padding: 3px 6px;
    font-size: 11px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    flex-shrink: 0;
  }

  .gender-select:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .btn-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 3px;
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--error-color);
    cursor: pointer;
    flex-shrink: 0;
    transition: all 0.15s;
  }

  .btn-remove:hover {
    background-color: var(--error-color);
    color: white;
    border-color: var(--error-color);
  }

  .set-pieces {
    border-top: 1px solid var(--border-color);
    padding: 6px 10px 6px 32px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .piece-row {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
  }

  .piece-connector {
    width: 8px;
    height: 1px;
    background-color: var(--border-color);
    flex-shrink: 0;
  }

  .piece-slot {
    font-size: 10px;
    color: var(--text-muted);
    width: 40px;
    flex-shrink: 0;
  }

  .piece-name {
    color: var(--text-color);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .piece-tt {
    display: flex;
    align-items: center;
    gap: 3px;
    flex-shrink: 0;
  }

  .piece-tt-label {
    font-size: 10px;
    color: var(--text-muted);
  }

  .piece-tt-input {
    width: 60px;
    padding: 2px 4px;
    font-size: 11px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 3px;
    color: var(--text-color);
  }

  .piece-tt-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  /* Remove spinner arrows */
  .piece-tt-input::-webkit-outer-spin-button,
  .piece-tt-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  .piece-tt-input[type=number] {
    -moz-appearance: textfield;
  }

  @media (max-width: 899px) {
    .set-pieces {
      padding-left: 20px;
    }
    .piece-slot {
      display: none;
    }
  }
</style>
