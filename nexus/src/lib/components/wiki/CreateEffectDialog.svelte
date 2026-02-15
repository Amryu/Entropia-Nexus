<!--
  @component CreateEffectDialog
  Modal dialog for creating a new effect inline from the EffectsEditor.
  Returns the effect data via 'create' event for embedding in the parent entity's change.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  let name = '';
  let canonicalName = '';
  let unit = '';
  let isPositive = true;
  let description = '';

  $: canSubmit = name.trim().length > 0;

  function handleSubmit() {
    if (!canSubmit) return;
    dispatch('create', {
      Name: name.trim(),
      _newEffect: {
        CanonicalName: canonicalName.trim() || null,
        Unit: unit.trim() || null,
        IsPositive: isPositive,
        Description: description.trim() || null
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
    <h3>Create New Effect</h3>

    <div class="form-group">
      <label for="effect-name">Name <span class="required">*</span></label>
      <input id="effect-name" type="text" bind:value={name} placeholder="e.g. Health Regeneration" autocomplete="off" maxlength="100" />
      <span class="hint">Unique identifier for this effect</span>
    </div>

    <div class="form-group">
      <label for="effect-canonical">In-Game Name</label>
      <input id="effect-canonical" type="text" bind:value={canonicalName} placeholder="e.g. Regeneration" autocomplete="off" maxlength="100" />
      <span class="hint">The name as it appears in-game (optional)</span>
    </div>

    <div class="form-group">
      <label for="effect-unit">Unit</label>
      <input id="effect-unit" type="text" bind:value={unit} placeholder="e.g. HP, %, HP/s" autocomplete="off" maxlength="20" />
    </div>

    <div class="form-group checkbox-group">
      <label>
        <input type="checkbox" bind:checked={isPositive} />
        Positive effect
      </label>
    </div>

    <div class="form-group">
      <label for="effect-desc">Description</label>
      <textarea id="effect-desc" bind:value={description} placeholder="Optional description..." rows="2" maxlength="500"></textarea>
    </div>

    <div class="actions">
      <button class="btn-cancel" on:click={handleCancel}>Cancel</button>
      <button class="btn-create" on:click={handleSubmit} disabled={!canSubmit}>Create</button>
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
  .form-group textarea {
    width: 100%;
    padding: 6px 8px;
    font-size: 13px;
    background-color: var(--input-bg, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  .form-group input[type="text"]:focus,
  .form-group textarea:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .form-group textarea {
    resize: vertical;
    font-family: inherit;
  }

  .form-group .hint {
    display: block;
    font-size: 10px;
    color: var(--text-muted, #999);
    margin-top: 2px;
  }

  .checkbox-group label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-color);
    cursor: pointer;
  }

  .checkbox-group input[type="checkbox"] {
    accent-color: var(--accent-color, #4a9eff);
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
