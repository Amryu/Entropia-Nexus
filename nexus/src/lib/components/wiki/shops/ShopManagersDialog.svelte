<!--
  @component ShopManagersDialog
  Dialog for managing shop managers. Only shop owner can access this.
  Managers are added by their verified Entropia name.
-->
<script>
  // @ts-nocheck
  import { apiCall } from '$lib/util';

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string} [shopName] - Shop name/identifier for API calls
   * @property {boolean} [open] - Whether the dialog is open
   * @property {any} [managers] - Current managers list
   * @property {() => void} [onclose]
   * @property {(data: any) => void} [onsaved]
   */

  /** @type {Props} */
  let { shopName = '', open = $bindable(false), managers = [], onclose, onsaved } = $props();

  // Local state
  let localManagers = $state([]);
  let newManagerName = $state('');
  let loading = false;
  let saving = $state(false);
  let error = $state(null);
  let success = $state(null);

  // Sync with prop
  $effect(() => {
    if (open) {
      localManagers = [...(managers || []).map(m => ({ Name: m.Name || m.name || m }))];
      error = null;
      success = null;
      newManagerName = '';
    }
  });

  function close() {
    open = false;
    onclose?.();
  }

  function addManager() {
    const name = newManagerName.trim();
    if (!name) return;

    // Check for duplicates
    if (localManagers.some(m => m.Name.toLowerCase() === name.toLowerCase())) {
      error = `"${name}" is already in the managers list.`;
      return;
    }

    localManagers = [...localManagers, { Name: name }];
    newManagerName = '';
    error = null;
  }

  function removeManager(index) {
    localManagers = localManagers.filter((_, i) => i !== index);
  }

  function handleKeydown(event) {
    if (event.key === 'Enter') {
      event.preventDefault();
      addManager();
    }
  }

  // Explicit input handler to ensure value is captured (workaround for binding issues)
  function handleInput(event) {
    newManagerName = event.target.value;
  }

  async function save() {
    if (saving) return;

    saving = true;
    error = null;
    success = null;

    try {
      const response = await fetch(`/api/shops/${encodeURIComponent(shopName)}/managers`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ Managers: localManagers })
      });

      const result = await response.json();

      if (!response.ok) {
        error = result.error || 'Failed to update managers';
      } else {
        success = 'Managers updated successfully';
        onsaved?.({ managers: localManagers });
        setTimeout(() => {
          close();
        }, 1000);
      }
    } catch (e) {
      error = 'Network error. Please try again.';
    } finally {
      saving = false;
    }
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) {
      close();
    }
  }
</script>

{#if open}
  <div class="dialog-backdrop" role="presentation" onclick={handleBackdropClick}>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="managers-dialog-title">
      <div class="dialog-header">
        <h3 id="managers-dialog-title">Manage Shop Managers</h3>
        <button class="close-btn" onclick={close} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="dialog-body">
        <p class="description">
          Managers can edit the shop's inventory. Enter the <strong>Entropia Universe name</strong> of verified users to add them as managers.
        </p>

        <!-- Add Manager Input -->
        <div class="add-manager-row">
          <input
            type="text"
            bind:value={newManagerName}
            oninput={handleInput}
            onkeydown={handleKeydown}
            placeholder="Enter Entropia name..."
            class="manager-input"
            disabled={saving}
          />
          <button class="add-btn" onclick={addManager} disabled={!newManagerName.trim() || saving}>
            Add
          </button>
        </div>

        <!-- Current Managers List -->
        <div class="managers-list">
          {#if localManagers.length === 0}
            <div class="no-managers">No managers assigned.</div>
          {:else}
            {#each localManagers as manager, index}
              <div class="manager-item">
                <span class="manager-name">{manager.Name}</span>
                <button
                  class="remove-btn"
                  onclick={() => removeManager(index)}
                  disabled={saving}
                  aria-label="Remove {manager.Name}"
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
            {/each}
          {/if}
        </div>

        <!-- Status Messages -->
        {#if error}
          <div class="message error">{error}</div>
        {/if}
        {#if success}
          <div class="message success">{success}</div>
        {/if}
      </div>

      <div class="dialog-footer">
        <button class="cancel-btn" onclick={close} disabled={saving}>
          Cancel
        </button>
        <button class="save-btn" onclick={save} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    width: 100%;
    max-width: 480px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .close-btn {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--text-muted, #999);
    border-radius: 4px;
  }

  .close-btn:hover {
    color: var(--text-color);
    background-color: var(--hover-color) !important;
  }

  .dialog-body {
    padding: 20px;
    overflow-y: auto;
    flex: 1;
  }

  .description {
    font-size: 13px;
    color: var(--text-muted, #999);
    margin: 0 0 16px 0;
    line-height: 1.5;
  }

  .add-manager-row {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }

  .manager-input {
    flex: 1;
    padding: 10px 12px;
    font-size: 14px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .manager-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .add-btn {
    padding: 10px 16px;
    font-size: 14px;
    font-weight: 500;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  .add-btn:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef) !important;
  }

  .add-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .managers-list {
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    max-height: 200px;
    overflow-y: auto;
  }

  .no-managers {
    padding: 20px;
    text-align: center;
    color: var(--text-muted, #999);
    font-style: italic;
    font-size: 13px;
  }

  .manager-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .manager-item:last-child {
    border-bottom: none;
  }

  .manager-name {
    font-size: 14px;
    color: var(--text-color);
  }

  .remove-btn {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--text-muted, #999);
    border-radius: 4px;
  }

  .remove-btn:hover:not(:disabled) {
    color: var(--error-color, #ff6b6b);
    background-color: var(--error-bg, rgba(255, 107, 107, 0.15)) !important;
  }

  .message {
    margin-top: 12px;
    padding: 10px 12px;
    border-radius: 4px;
    font-size: 13px;
  }

  .message.error {
    background-color: var(--error-bg, rgba(255, 107, 107, 0.15));
    color: var(--error-color, #ff6b6b);
    border: 1px solid var(--error-color, #ff6b6b);
  }

  .message.success {
    background-color: var(--success-bg, rgba(74, 222, 128, 0.15));
    color: var(--success-color, #4ade80);
    border: 1px solid var(--success-color, #4ade80);
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 16px 20px;
    border-top: 1px solid var(--border-color, #555);
  }

  .cancel-btn,
  .save-btn {
    padding: 10px 20px;
    font-size: 14px;
    font-weight: 500;
    border-radius: 4px;
    cursor: pointer;
  }

  .cancel-btn {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .cancel-btn:hover:not(:disabled) {
    background-color: var(--hover-color) !important;
  }

  .save-btn {
    background-color: var(--accent-color, #4a9eff);
    border: none;
    color: white;
  }

  .save-btn:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef) !important;
  }

  .save-btn:disabled,
  .cancel-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Mobile - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .dialog-backdrop {
      padding: 10px;
    }

    .dialog {
      max-height: 95vh;
    }

    .dialog-header,
    .dialog-footer {
      padding: 12px 16px;
    }

    .dialog-body {
      padding: 16px;
    }

    .add-manager-row {
      flex-direction: column;
    }

    .add-btn {
      width: 100%;
    }
  }
</style>
