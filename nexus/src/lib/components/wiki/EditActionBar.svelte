<!--
  @component EditActionBar
  Sticky action bar shown when in edit mode.
  Provides save draft and submit buttons with change status.
-->
<script>
  // @ts-nocheck
  import {
    editMode,
    hasChanges,
    hasErrors,
    changeMetadata,
    getChangeForSubmission,
    cancelEdit
  } from '$lib/stores/wikiEditState.js';
  import { apiCall } from '$lib/util';

  /** @type {Function|null} Custom save handler */
  export let onSave = null;

  /** @type {Function|null} Custom submit handler */
  export let onSubmit = null;

  let saving = false;
  let submitting = false;
  let statusMessage = '';
  let statusType = ''; // success, error

  async function handleSaveDraft() {
    if ($hasErrors) {
      statusMessage = 'Please fix validation errors before saving.';
      statusType = 'error';
      return;
    }

    saving = true;
    statusMessage = '';

    try {
      const change = getChangeForSubmission();

      if (onSave) {
        await onSave(change);
      } else {
        // Default save behavior
        let response;
        if ($changeMetadata.id) {
          // Update existing draft
          response = await apiCall(fetch, `/api/changes/${$changeMetadata.id}`, window.location.origin, {
            method: 'PUT',
            body: JSON.stringify({ ...change, state: 'Draft' })
          });
        } else {
          // Create new draft
          response = await apiCall(fetch, '/api/changes', window.location.origin, {
            method: 'POST',
            body: JSON.stringify({ ...change, state: 'Draft' })
          });
        }

        if (response.id) {
          changeMetadata.update(m => ({ ...m, id: response.id }));
        }
      }

      statusMessage = 'Draft saved successfully!';
      statusType = 'success';
    } catch (error) {
      console.error('Save error:', error);
      statusMessage = error.message || 'Failed to save draft.';
      statusType = 'error';
    } finally {
      saving = false;
    }
  }

  async function handleSubmit() {
    if ($hasErrors) {
      statusMessage = 'Please fix validation errors before submitting.';
      statusType = 'error';
      return;
    }

    if (!$hasChanges && !$changeMetadata.id) {
      statusMessage = 'No changes to submit.';
      statusType = 'error';
      return;
    }

    submitting = true;
    statusMessage = '';

    try {
      const change = getChangeForSubmission();

      if (onSubmit) {
        await onSubmit(change);
      } else {
        // Default submit behavior - save as Pending
        let response;
        if ($changeMetadata.id) {
          response = await apiCall(fetch, `/api/changes/${$changeMetadata.id}`, window.location.origin, {
            method: 'PUT',
            body: JSON.stringify({ ...change, state: 'Pending' })
          });
        } else {
          response = await apiCall(fetch, '/api/changes', window.location.origin, {
            method: 'POST',
            body: JSON.stringify({ ...change, state: 'Pending' })
          });
        }
      }

      statusMessage = 'Changes submitted for review!';
      statusType = 'success';

      // Exit edit mode after successful submit
      setTimeout(() => {
        cancelEdit();
      }, 1500);
    } catch (error) {
      console.error('Submit error:', error);
      statusMessage = error.message || 'Failed to submit changes.';
      statusType = 'error';
    } finally {
      submitting = false;
    }
  }

  function handleCancel() {
    if ($hasChanges) {
      if (confirm('You have unsaved changes. Are you sure you want to cancel?')) {
        cancelEdit();
      }
    } else {
      cancelEdit();
    }
  }
</script>

{#if $editMode}
  <div class="edit-action-bar">
    <div class="action-bar-content">
      <div class="status-area">
        {#if statusMessage}
          <span class="status-message" class:success={statusType === 'success'} class:error={statusType === 'error'}>
            {statusMessage}
          </span>
        {:else if $hasChanges}
          <span class="status-indicator unsaved">
            <span class="indicator-dot"></span>
            Unsaved changes
          </span>
        {:else if $changeMetadata.id}
          <span class="status-indicator saved">
            Draft saved
          </span>
        {:else}
          <span class="status-indicator">
            No changes
          </span>
        {/if}
      </div>

      <div class="action-buttons">
        <button class="btn btn-cancel" on:click={handleCancel} disabled={saving || submitting}>
          Cancel
        </button>

        <button
          class="btn btn-secondary"
          on:click={handleSaveDraft}
          disabled={saving || submitting || !$hasChanges}
        >
          {saving ? 'Saving...' : 'Save Draft'}
        </button>

        <button
          class="btn btn-primary"
          on:click={handleSubmit}
          disabled={saving || submitting || $hasErrors}
        >
          {submitting ? 'Submitting...' : 'Submit for Review'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .edit-action-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: var(--secondary-color);
    border-top: 1px solid var(--border-color, #555);
    padding: 12px 20px;
    z-index: 100;
    box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.2);
  }

  .action-bar-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
    gap: 16px;
  }

  .status-area {
    flex: 1;
    min-width: 0;
  }

  .status-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    color: var(--text-muted, #999);
  }

  .status-indicator.unsaved {
    color: var(--warning-color, #fbbf24);
  }

  .status-indicator.saved {
    color: var(--success-color, #4ade80);
  }

  .indicator-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: currentColor;
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .status-message {
    font-size: 14px;
    font-weight: 500;
  }

  .status-message.success {
    color: var(--success-color, #4ade80);
  }

  .status-message.error {
    color: var(--error-color, #ff6b6b);
  }

  .action-buttons {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }

  .btn {
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-cancel {
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .btn-cancel:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .btn-secondary {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .btn-secondary:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .btn-primary {
    background-color: var(--accent-color, #4a9eff);
    border: 1px solid var(--accent-color, #4a9eff);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef);
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .edit-action-bar {
      padding: 10px 12px;
    }

    .action-bar-content {
      flex-direction: column;
      gap: 10px;
    }

    .status-area {
      width: 100%;
      text-align: center;
    }

    .action-buttons {
      width: 100%;
      justify-content: stretch;
    }

    .action-buttons .btn {
      flex: 1;
      padding: 10px 12px;
    }

    .btn-cancel {
      flex: 0 0 auto;
    }
  }
</style>
