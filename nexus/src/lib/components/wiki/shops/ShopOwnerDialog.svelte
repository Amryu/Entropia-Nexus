<!--
  @component ShopOwnerDialog
  Dialog for admins to assign a new owner to a shop.
  When a new owner is set, all managers are cleared automatically.
-->
<script>
  import { run } from 'svelte/legacy';

  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string} [shopName] - Shop name/identifier for API calls
   * @property {boolean} [open] - Whether the dialog is open
   * @property {string} [currentOwner] - Current owner name (for display)
   */

  /** @type {Props} */
  let { shopName = '', open = $bindable(false), currentOwner = '' } = $props();

  // Local state
  let newOwnerName = $state('');
  let saving = $state(false);
  let error = $state(null);
  let success = $state(null);
  let confirmClear = $state(false);

  // Reset state when dialog opens
  run(() => {
    if (open) {
      newOwnerName = '';
      error = null;
      success = null;
      confirmClear = false;
    }
  });

  function close() {
    open = false;
    dispatch('close');
  }

  function handleBackdropClick(event) {
    if (event.target === event.currentTarget) {
      close();
    }
  }

  function handleKeydown(event) {
    if (event.key === 'Enter' && newOwnerName.trim() && !saving) {
      event.preventDefault();
      if (!confirmClear) {
        confirmClear = true;
      } else {
        save();
      }
    }
    if (event.key === 'Escape') {
      close();
    }
  }

  function proceedToConfirm() {
    const name = newOwnerName.trim();
    if (!name) {
      error = 'Please enter an Entropia name.';
      return;
    }
    error = null;
    confirmClear = true;
  }

  async function save() {
    if (saving) return;

    const name = newOwnerName.trim();
    if (!name) {
      error = 'Please enter an Entropia name.';
      return;
    }

    saving = true;
    error = null;
    success = null;

    try {
      const response = await fetch(`/api/shops/${encodeURIComponent(shopName)}/owner`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ OwnerName: name })
      });

      const result = await response.json();

      if (!response.ok) {
        error = result.error || 'Failed to update owner';
        confirmClear = false;
      } else {
        success = 'Owner updated successfully. Managers have been cleared.';
        dispatch('saved', { ownerName: name });
        setTimeout(() => {
          close();
          // Reload the page to get fresh data
          window.location.reload();
        }, 1500);
      }
    } catch (e) {
      error = 'Network error. Please try again.';
      confirmClear = false;
    } finally {
      saving = false;
    }
  }
</script>

{#if open}
  <div class="dialog-backdrop" role="presentation" onclick={handleBackdropClick} onkeydown={handleKeydown}>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="owner-dialog-title">
      <div class="dialog-header">
        <h3 id="owner-dialog-title">Assign Shop Owner</h3>
        <button class="close-btn" onclick={close} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div class="dialog-body">
        {#if !confirmClear}
          <!-- Step 1: Enter new owner name -->
          <p class="description">
            Enter the <strong>Entropia Universe name</strong> of the verified user to assign as the new owner.
          </p>

          {#if currentOwner}
            <div class="current-owner">
              <span class="label">Current Owner:</span>
              <span class="value">{currentOwner}</span>
            </div>
          {/if}

          <div class="input-row">
            <label for="owner-input" class="input-label">New Owner</label>
            <input
              id="owner-input"
              type="text"
              bind:value={newOwnerName}
              placeholder="Enter Entropia name..."
              class="owner-input"
              disabled={saving}
            />
          </div>

          <div class="warning-notice">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
            <span>Changing the owner will <strong>remove all managers</strong> from this shop.</span>
          </div>
        {:else}
          <!-- Step 2: Confirm the change -->
          <div class="confirm-panel">
            <div class="confirm-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
            </div>
            <h4>Confirm Owner Change</h4>
            <p>You are about to:</p>
            <ul class="confirm-list">
              <li>Set <strong>{newOwnerName}</strong> as the new owner</li>
              <li>Remove all current managers from this shop</li>
            </ul>
            <p class="confirm-warning">This action cannot be undone.</p>
          </div>
        {/if}

        <!-- Status Messages -->
        {#if error}
          <div class="message error">{error}</div>
        {/if}
        {#if success}
          <div class="message success">{success}</div>
        {/if}
      </div>

      <div class="dialog-footer">
        {#if !confirmClear}
          <button class="cancel-btn" onclick={close} disabled={saving}>
            Cancel
          </button>
          <button
            class="next-btn"
            onclick={proceedToConfirm}
            disabled={!newOwnerName.trim() || saving}
          >
            Continue
          </button>
        {:else}
          <button class="cancel-btn" onclick={() => confirmClear = false} disabled={saving}>
            Back
          </button>
          <button class="save-btn danger" onclick={save} disabled={saving}>
            {saving ? 'Updating...' : 'Confirm Change'}
          </button>
        {/if}
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
    max-width: 440px;
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

  .current-owner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    margin-bottom: 16px;
    font-size: 13px;
  }

  .current-owner .label {
    color: var(--text-muted, #999);
  }

  .current-owner .value {
    font-weight: 500;
    color: var(--text-color);
  }

  .input-row {
    margin-bottom: 16px;
  }

  .input-label {
    display: block;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted, #999);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .owner-input {
    width: 100%;
    padding: 10px 12px;
    font-size: 14px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  .owner-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .warning-notice {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    background-color: var(--warning-bg, rgba(251, 191, 36, 0.15));
    border: 1px solid var(--warning-color, #fbbf24);
    border-radius: 6px;
    font-size: 13px;
    color: var(--warning-color, #fbbf24);
    line-height: 1.4;
  }

  .warning-notice svg {
    flex-shrink: 0;
    margin-top: 1px;
  }

  .confirm-panel {
    text-align: center;
    padding: 16px 0;
  }

  .confirm-icon {
    color: var(--warning-color, #fbbf24);
    margin-bottom: 12px;
  }

  .confirm-panel h4 {
    font-size: 18px;
    font-weight: 600;
    margin: 0 0 12px 0;
    color: var(--text-color);
  }

  .confirm-panel p {
    font-size: 14px;
    color: var(--text-muted, #999);
    margin: 0 0 12px 0;
  }

  .confirm-list {
    text-align: left;
    margin: 0 0 16px 0;
    padding-left: 24px;
    font-size: 14px;
    color: var(--text-color);
  }

  .confirm-list li {
    margin-bottom: 6px;
  }

  .confirm-warning {
    font-size: 13px;
    color: var(--error-color, #ff6b6b);
    font-weight: 500;
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
  .next-btn,
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

  .next-btn {
    background-color: var(--accent-color, #4a9eff);
    border: none;
    color: white;
  }

  .next-btn:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef) !important;
  }

  .save-btn {
    background-color: var(--accent-color, #4a9eff);
    border: none;
    color: white;
  }

  .save-btn.danger {
    background-color: var(--error-color, #ff6b6b);
  }

  .save-btn.danger:hover:not(:disabled) {
    background-color: #e55c5c !important;
  }

  .save-btn:disabled,
  .next-btn:disabled,
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
  }
</style>
