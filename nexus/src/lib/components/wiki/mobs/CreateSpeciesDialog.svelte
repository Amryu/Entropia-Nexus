<!--
  @component CreateSpeciesDialog
  Modal dialog for creating or editing a mob species inline from the Mob wiki page.
  Returns the species data via 'create' event for embedding in the parent entity's change.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  /** @type {{ Name: string, Properties?: { CodexBaseCost?: number, CodexType?: string }, _newSpecies?: { CodexBaseCost?: number, CodexType?: string } } | null} */
  export let species = null;

  $: isEdit = !!species;

  function getSpeciesValues() {
    return species?._newSpecies || species?.Properties || {};
  }

  let name = species?.Name || '';
  let codexBaseCost = getSpeciesValues().CodexBaseCost ?? '';
  let codexType = getSpeciesValues().CodexType || 'Mob';

  $: canSubmit = name.trim().length > 0;

  function handleSubmit() {
    if (!canSubmit) return;
    dispatch('create', {
      Name: name.trim(),
      _newSpecies: {
        CodexBaseCost: codexBaseCost !== '' ? Number(codexBaseCost) : null,
        CodexType: codexType
      }
    });
  }

  function handleCancel() {
    dispatch('cancel');
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

<div
  class="modal-overlay"
  role="button"
  tabindex="0"
  on:click={handleOverlayClick}
  on:keydown={handleKeydown}
>
  <div class="modal" role="dialog" aria-modal="true">
    <h3>{isEdit ? 'Edit Species' : 'Create New Species'}</h3>

    <div class="form-group">
      <label for="species-name">Name <span class="required">*</span></label>
      {#if isEdit}
        <input id="species-name" type="text" value={name} disabled />
      {:else}
        <input id="species-name" type="text" bind:value={name} placeholder="e.g. Calonite" autocomplete="off" maxlength="100" />
      {/if}
      <span class="hint">{isEdit ? 'Species name cannot be changed' : 'Unique species name'}</span>
    </div>

    <div class="form-group">
      <label for="species-codex-cost">Codex Base Cost (PED)</label>
      <input id="species-codex-cost" type="number" bind:value={codexBaseCost} placeholder="e.g. 50" min="0" step="0.01" />
      <span class="hint">PED cost per codex rank (optional)</span>
    </div>

    <div class="form-group">
      <label for="species-codex-type">Codex Type</label>
      <select id="species-codex-type" bind:value={codexType}>
        <option value="Mob">Mob</option>
        <option value="MobLooter">Mob (Looter)</option>
        <option value="Asteroid">Asteroid</option>
      </select>
    </div>

    <div class="actions">
      <button class="btn-cancel" on:click={handleCancel}>Cancel</button>
      <button class="btn-create" on:click={handleSubmit} disabled={!canSubmit}>{isEdit ? 'Save' : 'Create'}</button>
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
    z-index: 1001;
    padding: 16px;
    box-sizing: border-box;
  }

  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 400px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }

  .modal h3 {
    margin: 0 0 16px 0;
    font-size: 18px;
    font-weight: 600;
  }

  .form-group {
    margin-bottom: 12px;
  }

  .form-group label {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted, #999);
    margin-bottom: 4px;
  }

  .form-group .required {
    color: var(--error-color, #ef4444);
  }

  .form-group input[type="text"],
  .form-group input[type="number"],
  .form-group select {
    width: 100%;
    padding: 6px 8px;
    font-size: 13px;
    background-color: var(--input-bg, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  .form-group input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .form-group input:focus,
  .form-group select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .form-group .hint {
    display: block;
    font-size: 10px;
    color: var(--text-muted, #999);
    margin-top: 2px;
  }

  .actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 16px;
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

  .btn-create {
    padding: 8px 16px;
    font-size: 13px;
    background: var(--accent-color, #4a9eff);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
    font-weight: 500;
  }

  .btn-create:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-create:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
