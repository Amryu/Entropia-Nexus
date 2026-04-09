<!--
  @component EditActionBar
  Sticky action bar shown when in edit mode.
  Provides save draft and submit buttons with change status.
-->
<script>
  // @ts-nocheck
  import { goto, invalidateAll } from '$app/navigation';
  import { browser } from '$app/environment';
  import { onDestroy } from 'svelte';
  import {
    editMode,
    isCreateMode,
    hasChanges,
    hasErrors,
    hasWarnings,
    changeMetadata,
    currentEntity,
    originalEntity,
    existingPendingChange,
    fieldWarnings,
    getChangeForSubmission,
    cancelEdit,
    markSaved,
    setFieldError,
    setFieldWarning,
    setViewingPendingChange,
    suppressNextNavGuard
  } from '$lib/stores/wikiEditState.js';
  import { apiPost, apiPut, encodeURIComponentSafe } from '$lib/util';

  // In create mode, Name must be filled in before save/submit
  let nameIsEmpty = $derived($isCreateMode && (!$currentEntity?.Name || $currentEntity.Name.trim() === ''));
  let hasValidationIssues = $derived($hasErrors || nameIsEmpty);

  // Determine current change state - Pending means already submitted for review
  let isPending = $derived($existingPendingChange?.state === 'Pending' || $changeMetadata.state === 'Pending');

  // DirectApply/ApplyFailed: change was submitted for direct application
  let isDirectApplyState = $derived($changeMetadata.state === 'DirectApply' || $changeMetadata.state === 'ApplyFailed'
    || $existingPendingChange?.state === 'DirectApply' || $existingPendingChange?.state === 'ApplyFailed');

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {Function|null} [onSave]
   * @property {Function|null} [onSubmit]
   * @property {string} [basePath]
   * @property {object|null} [user]
   * @property {string} [entityName]
   * @property {() => void} [onexitedit]
   */

  /** @type {Props} */
  let {
    onSave = null,
    onSubmit = null,
    basePath = '',
    user = null,
    entityName = '',
    onexitedit
  } = $props();

  let saving = $state(false);
  let submitting = $state(false);
  let directApplying = $state(false);
  let deleting = $state(false);
  let statusMessage = $state('');
  let statusType = $state(''); // success, error
  let pollTimer = null;
  let similarCheckTimer = null;
  // Track the name the user already confirmed so we don't re-prompt
  let confirmedSimilarName = $state('');

  // Ref + ResizeObserver so --edit-bar-height stays in sync with the actual rendered height.
  // WikiPage uses this var to pad content so the bar never obscures page content.
  let barEl = $state();
  let resizeObserver = null;
  $effect(() => {
    if (!browser || !barEl) return;
    resizeObserver = new ResizeObserver((entries) => {
      for (const e of entries) {
        const h = Math.ceil(e.borderBoxSize?.[0]?.blockSize ?? e.contentRect.height);
        document.documentElement.style.setProperty('--edit-bar-height', `${h}px`);
      }
    });
    resizeObserver.observe(barEl);
    return () => {
      resizeObserver?.disconnect();
      resizeObserver = null;
      document.documentElement.style.removeProperty('--edit-bar-height');
    };
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
    if (similarCheckTimer) clearTimeout(similarCheckTimer);
    if (browser) document.documentElement.style.removeProperty('--edit-bar-height');
  });

  // Derived so the similarity effect only re-runs when Name actually changes,
  // not on every $currentEntity emission (e.g. when editing Description)
  let currentName = $derived(($currentEntity?.Name ?? '').trim());
  let originalName = $derived(($originalEntity?.Name ?? '').trim());

  // Debounced similarity check when the Name field changes
  $effect(() => {
    const name = currentName;
    const entity = $changeMetadata?.entity;
    const origName = originalName;

    if (!name || name.length < 3 || !entity) {
      setFieldWarning('Name', null);
      return;
    }

    // Skip check when name is unchanged from the original (update mode, just entered edit)
    if (origName && name === origName) {
      setFieldWarning('Name', null);
      return;
    }

    if (similarCheckTimer) clearTimeout(similarCheckTimer);
    similarCheckTimer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ name, entity });
        // Exclude original name for updates so the entity doesn't match itself
        if (origName) params.set('exclude', origName);

        const res = await fetch(`/api/changes/check-similar?${params}`);
        if (!res.ok) { setFieldWarning('Name', null); return; }
        const data = await res.json();

        if (data.similar?.length > 0) {
          setFieldWarning('Name', `Similar: ${data.similar.join(', ')}`);
        } else {
          setFieldWarning('Name', null);
        }
      } catch {
        setFieldWarning('Name', null);
      }
    }, 600);
  });

  /**
   * If the Name field has a similarity warning the user hasn't confirmed yet,
   * show a confirmation dialog.  Returns true to proceed, false to abort.
   */
  function confirmSimilarIfNeeded() {
    const name = $currentEntity?.Name?.trim();
    const warning = $fieldWarnings['Name'];
    if (!warning || name === confirmedSimilarName) return true;

    const ok = confirm(
      `Entities with a similar name already exist:\n\n${warning.replace('Similar: ', '').split(', ').map(n => `  \u2022 ${n}`).join('\n')}\n\nAre you sure this is not a duplicate?`
    );
    if (ok) confirmedSimilarName = name;
    return ok;
  }

  // Admin-only: allow Direct Apply (pass-through without review)
  let isUserAdmin = $derived(user?.grants?.includes('admin.panel') || user?.administrator);

  // Check if user can delete the change (author or admin)
  let canDelete = $derived(user && $changeMetadata.id && (
    ($existingPendingChange && ($existingPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))) ||
    (!$existingPendingChange && user.verified)
  ));

  function buildPutUrl(changeId, state) {
    let url = `/api/changes/${changeId}?state=${state}`;
    if ($changeMetadata.content_updated_at) {
      url += `&content_updated_at=${encodeURIComponent($changeMetadata.content_updated_at)}`;
    }
    return url;
  }

  async function handleSaveDraft() {
    // Check for Name in create mode
    if (nameIsEmpty) {
      setFieldError('Name', 'Name is required');
      statusMessage = 'Name is required to save.';
      statusType = 'error';
      return;
    }

    if ($hasErrors) {
      statusMessage = 'Please fix validation errors before saving.';
      statusType = 'error';
      return;
    }

    if (!confirmSimilarIfNeeded()) return;

    saving = true;
    statusMessage = '';

    try {
      const change = getChangeForSubmission();
      // Preserve current state - don't change Pending/DirectApply back to Draft
      // ApplyFailed → re-submit as DirectApply so the bot retries
      const rawState = $changeMetadata.state || $existingPendingChange?.state;
      const currentState = isPending ? 'Pending'
        : rawState === 'DirectApply' || rawState === 'ApplyFailed' ? 'DirectApply'
        : 'Draft';

      if (onSave) {
        await onSave(change);
      } else {
        // Default save behavior
        // API expects: raw entity object in body, params in URL query string
        let response;
        if ($changeMetadata.id) {
          // Update existing change, preserving its state
          response = await apiPut(fetch, buildPutUrl($changeMetadata.id, currentState), change.data);
          if (response?.error) {
            throw new Error(response.error);
          }
        } else {
          // Create new draft: POST /api/changes?type={type}&entity={entity}&state=Draft
          const type = change.data.Id ? 'Update' : 'Create';
          response = await apiPost(fetch, `/api/changes?type=${type}&entity=${change.entity}&state=Draft`, change.data);
          if (response?.error) {
            throw new Error(response.error);
          }
        }

        const changeId = response?.id || $changeMetadata.id;
        if (changeId) {
          changeMetadata.update(m => ({
            ...m,
            id: changeId,
            content_updated_at: response?.content_updated_at || m.content_updated_at
          }));
          markSaved();
          if (browser) {
            await invalidateAll();
            if ($isCreateMode && response?.id) {
              suppressNextNavGuard();
              await goto(`${window.location.pathname}?mode=create&changeId=${response.id}`, {
                replaceState: true,
                noScroll: true
              });
            }
          }
        }
      }

      statusMessage = 'Saved successfully!';
      statusType = 'success';
    } catch (error) {
      console.error('Save error:', error);
      statusMessage = error.message || 'Failed to save.';
      statusType = 'error';
    } finally {
      saving = false;
    }
  }

  async function handleSubmit() {
    // Check for Name in create mode
    if (nameIsEmpty) {
      setFieldError('Name', 'Name is required');
      statusMessage = 'Name is required to submit.';
      statusType = 'error';
      return;
    }

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

    if (!confirmSimilarIfNeeded()) return;

    submitting = true;
    statusMessage = '';

    try {
      const change = getChangeForSubmission();

      if (onSubmit) {
        await onSubmit(change);
      } else {
        // Default submit behavior - save as Pending
        // API expects: raw entity object in body, params in URL query string
        let response;
        if ($changeMetadata.id) {
          // Update to Pending: PUT /api/changes/{id}?state=Pending
          response = await apiPut(fetch, buildPutUrl($changeMetadata.id, 'Pending'), change.data);
          if (response?.error) {
            throw new Error(response.error);
          }
        } else {
          // Create as Pending: POST /api/changes?type={type}&entity={entity}&state=Pending
          const type = change.data.Id ? 'Update' : 'Create';
          response = await apiPost(fetch, `/api/changes?type=${type}&entity=${change.entity}&state=Pending`, change.data);
          if (response?.error) {
            throw new Error(response.error);
          }
        }

        const changeId = response?.id || $changeMetadata.id;
        if (changeId) {
          changeMetadata.update(m => ({
            ...m,
            id: changeId,
            state: 'Pending',
            content_updated_at: response?.content_updated_at || m.content_updated_at
          }));
          markSaved();
          if (browser) {
            await invalidateAll();
            if ($isCreateMode && response?.id) {
              suppressNextNavGuard();
              await goto(`${window.location.pathname}?mode=create&changeId=${response.id}`, {
                replaceState: true,
                noScroll: true
              });
            }
          }
        }
      }

      statusMessage = 'Changes submitted for review!';
      statusType = 'success';

      // Exit edit mode but keep viewing the submitted changes
      if (!$isCreateMode) {
        setTimeout(() => {
          cancelEdit();
          onexitedit?.();
          setViewingPendingChange(true);
        }, 1500);
      }
    } catch (error) {
      console.error('Submit error:', error);
      statusMessage = error.message || 'Failed to submit changes.';
      statusType = 'error';
    } finally {
      submitting = false;
    }
  }

  async function handleDirectApply() {
    if (nameIsEmpty) {
      setFieldError('Name', 'Name is required');
      statusMessage = 'Name is required.';
      statusType = 'error';
      return;
    }

    if ($hasErrors) {
      statusMessage = 'Please fix validation errors before applying.';
      statusType = 'error';
      return;
    }

    if (!$hasChanges && !$changeMetadata.id) {
      statusMessage = 'No changes to apply.';
      statusType = 'error';
      return;
    }

    if (!confirmSimilarIfNeeded()) return;

    directApplying = true;
    statusMessage = '';

    try {
      const change = getChangeForSubmission();

      let response;
      if ($changeMetadata.id) {
        response = await apiPut(fetch, buildPutUrl($changeMetadata.id, 'DirectApply'), change.data);
        if (response?.error) {
          throw new Error(response.error);
        }
      } else {
        const type = change.data.Id ? 'Update' : 'Create';
        response = await apiPost(fetch, `/api/changes?type=${type}&entity=${change.entity}&state=DirectApply`, change.data);
        if (response?.error) {
          throw new Error(response.error);
        }
      }

      const changeId = response?.id || $changeMetadata.id;
      if (changeId) {
        changeMetadata.update(m => ({
          ...m,
          id: changeId,
          state: 'DirectApply',
          content_updated_at: response?.content_updated_at || m.content_updated_at
        }));
        markSaved();

        statusMessage = 'Applying changes...';
        statusType = 'success';

        await pollForApply(changeId);
      }
    } catch (error) {
      console.error('Direct apply error:', error);
      statusMessage = error.message || 'Failed to submit for direct application.';
      statusType = 'error';
      directApplying = false;
    }
  }

  const POLL_INTERVAL = 2000;
  const POLL_TIMEOUT = 30000;

  async function pollForApply(changeId) {
    const start = Date.now();

    return new Promise((resolve) => {
      pollTimer = setInterval(async () => {
        if (Date.now() - start > POLL_TIMEOUT) {
          clearInterval(pollTimer);
          pollTimer = null;
          statusMessage = 'Taking longer than expected. Check Discord for confirmation.';
          statusType = 'success';
          directApplying = false;
          resolve();
          return;
        }

        try {
          const res = await fetch(`/api/changes/${changeId}`);
          if (!res.ok) return;
          const change = await res.json();

          if (change?.state === 'Approved') {
            clearInterval(pollTimer);
            pollTimer = null;
            statusMessage = 'Changes applied successfully!';
            statusType = 'success';
            if (browser) await invalidateAll();
            if ($isCreateMode) {
              // Newly created entity now exists — navigate to its page so the URL
              // bar reflects the real route instead of the ?mode=create draft URL.
              const createdName = change?.data?.Name || $currentEntity?.Name;
              setTimeout(() => {
                cancelEdit();
                if (createdName && basePath && browser) {
                  suppressNextNavGuard();
                  goto(`${basePath}/${encodeURIComponentSafe(createdName)}`);
                } else if (basePath && browser) {
                  suppressNextNavGuard();
                  goto(basePath);
                }
              }, 1500);
            } else {
              setTimeout(() => { cancelEdit(); onexitedit?.(); }, 1500);
            }
            directApplying = false;
            resolve();
          } else if (change?.state === 'ApplyFailed') {
            clearInterval(pollTimer);
            pollTimer = null;
            changeMetadata.update(m => ({ ...m, state: 'ApplyFailed' }));
            statusMessage = 'Failed to apply changes. You can retry or check Discord.';
            statusType = 'error';
            directApplying = false;
            resolve();
          }
        } catch {
          // Network error — retry on next tick
        }
      }, POLL_INTERVAL);
    });
  }

  function handleCancel() {
    const doCancel = () => {
      // Capture before cancelEdit() resets isCreateMode
      const wasCreate = $isCreateMode;
      cancelEdit();
      // In create mode, navigate back to the base path
      if (wasCreate && basePath) {
        suppressNextNavGuard();
        goto(basePath);
      } else {
        onexitedit?.();
      }
    };

    if ($hasChanges) {
      if (confirm('You have unsaved changes. Are you sure you want to cancel?')) {
        doCancel();
      }
    } else {
      doCancel();
    }
  }

  async function handleDelete() {
    if (!$changeMetadata.id) {
      return;
    }

    const changeType = $existingPendingChange?.type || ($isCreateMode ? 'Create' : 'Update');
    const confirmMessage = changeType === 'Create'
      ? 'Are you sure you want to delete this pending creation? This cannot be undone.'
      : 'Are you sure you want to delete this pending change? This cannot be undone.';

    if (!confirm(confirmMessage)) {
      return;
    }

    deleting = true;
    statusMessage = '';

    try {
      const response = await fetch(`/api/changes/${$changeMetadata.id}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'Failed to delete change');
      }

      statusMessage = 'Change deleted successfully!';
      statusType = 'success';

      // Invalidate data to refresh sidebar
      await invalidateAll();

      // Navigate based on change type
      setTimeout(() => {
        if (changeType === 'Create') {
          // For creates, go back to base path
          suppressNextNavGuard();
          goto(basePath);
        } else {
          // For updates, go to the entity view (remove edit mode)
          cancelEdit();
          if (entityName) {
            suppressNextNavGuard();
            goto(`${basePath}/${encodeURIComponentSafe(entityName)}`);
          }
        }
      }, 500);
    } catch (error) {
      console.error('Delete error:', error);
      statusMessage = error.message || 'Failed to delete change.';
      statusType = 'error';
      deleting = false;
    }
  }
</script>

{#if $editMode}
  <div class="edit-action-bar" bind:this={barEl}>
    <div class="action-bar-content">
      <div class="status-area">
        {#if statusMessage}
          <span class="status-message" class:success={statusType === 'success'} class:error={statusType === 'error'}>
            {statusMessage}
          </span>
        {:else if nameIsEmpty}
          <span class="status-indicator validation-hint">
            Enter a name to save
          </span>
        {:else if $hasChanges}
          <span class="status-indicator unsaved">
            <span class="indicator-dot"></span>
            Unsaved changes
          </span>
        {:else if $changeMetadata.id}
          {#if $changeMetadata.state === 'ApplyFailed'}
            <span class="status-indicator apply-failed">Apply failed</span>
          {:else}
            <span class="status-indicator saved">
              {isPending ? 'Pending review' : $changeMetadata.state === 'DirectApply' ? 'Awaiting direct apply' : 'Saved'}
            </span>
          {/if}
        {:else}
          <span class="status-indicator">
            No changes
          </span>
        {/if}
      </div>

      <div class="action-buttons">
        <button class="btn btn-cancel" onclick={handleCancel} disabled={saving || submitting || directApplying || deleting}>
          Cancel
        </button>

        {#if canDelete}
          <button
            class="btn btn-danger"
            onclick={handleDelete}
            disabled={saving || submitting || directApplying || deleting}
            title="Delete this pending change"
          >
            {deleting ? 'Deleting...' : 'Delete Change'}
          </button>
        {/if}

        <button
          class="btn"
          class:btn-secondary={!isPending}
          class:btn-primary={isPending}
          onclick={handleSaveDraft}
          disabled={saving || submitting || directApplying || deleting || !$hasChanges || hasValidationIssues}
          title={nameIsEmpty ? 'Name is required' : ''}
        >
          {saving ? 'Saving...' : 'Save'}
        </button>

        {#if !isPending}
          <button
            class="btn btn-primary"
            onclick={handleSubmit}
            disabled={saving || submitting || directApplying || deleting || hasValidationIssues}
            title={nameIsEmpty ? 'Name is required' : ''}
          >
            {submitting ? 'Submitting...' : 'Submit for Review'}
          </button>
        {/if}

        {#if isUserAdmin}
          <button
            class="btn btn-accent"
            onclick={handleDirectApply}
            disabled={saving || submitting || directApplying || deleting || hasValidationIssues}
            title="Apply changes immediately without review (admin only)"
          >
            {directApplying ? 'Applying...' : 'Direct Apply'}
          </button>
        {/if}
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

  .status-indicator.apply-failed {
    color: var(--error-color, #ff6b6b);
  }

  .status-indicator.validation-hint {
    color: var(--text-muted, #999);
    font-style: italic;
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

  .btn-danger {
    background-color: var(--error-color, #ff6b6b);
    border: 1px solid var(--error-color, #ff6b6b);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background-color: var(--error-color-hover, #ff5252);
  }

  .btn-accent {
    background-color: var(--success-color, #16a34a);
    border: 1px solid var(--success-color, #16a34a);
    color: white;
  }

  .btn-accent:hover:not(:disabled) {
    background-color: var(--button-success-hover, #047857);
  }

  /* Mobile adjustments - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
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
