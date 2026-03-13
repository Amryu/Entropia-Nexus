<script>
  //@ts-nocheck
  import { apiCall, apiPut } from "$lib/util";
  import EditFormControlGroup from "./EditFormControlGroup.svelte";

 
  let disabled = $state(false);
  let saving = $state(false);
  let saveMessage = $state('');
 



  import { onMount } from 'svelte';
  /**
   * @typedef {Object} Props
   * @property {any} object
   * @property {any} user
   * @property {boolean} [canEdit]
   */

  /** @type {Props} */
  let { object, user, canEdit = false } = $props();
  let isLoading = $state(true);
  let dependencies = {};
  let managers = $state([]);

  // Manager configuration
  const managerConfig = {
    constructor: () => ({
      Managers: []
    }),
    dependencies: [],
    controls: [
      {
        label: 'Shop Managers',
        type: 'list',
        config: {
          constructor: () => ({
            Name: ''
          }),
          controls: [
            { 
              label: 'Entropia Name', 
              type: 'text', 
              '_get': x => x.Name || x.User?.Name || '', 
              '_set': (x, v) => x.Name = v
            }
          ]
        }, 
        itemNameFunc: j => `Manager ${j + 1}`, 
        '_get': x => x.Managers || [], 
        '_set': (x, v) => x.Managers = v
      }
    ]
  };

  // Fetch managers from API on mount
  onMount(async () => {
    isLoading = true;
    try {
      const res = await apiCall(fetch, `/api/shops/${object.Id}/managers`);
      managers = Array.isArray(res?.Managers) ? res.Managers : [];
    } catch (e) {
      managers = [];
    }
    isLoading = false;
  });

  async function save() {
    if (disabled || saving || !canManageManagers) return;
    
    saving = true;
    saveMessage = 'Saving managers...';

    try {
      // Convert managers to PascalCase expected by the API
      let payload = {
        Managers: (managers || []).map(manager => ({
          Name: manager.Name || manager.User?.Name || ''
        })).filter(manager => manager.Name && manager.Name.trim())
      };
      
      const response = await apiPut(fetch, `/api/shops/${object.Id}/managers`, payload);
      
      if (response?.success) {
        saveMessage = 'Managers saved successfully!';
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      } else {
        saveMessage = 'Error: ' + (response?.error || 'Unknown error');
      }
    } catch (error) {
      console.error('Save error:', error);
      saveMessage = 'Error: ' + error.message;
    }
    
    setTimeout(() => {
      saving = false;
      saveMessage = '';
    }, 3000);
  }

  function cancel() {
    window.location.reload();
  }
  $effect(() => {
    disabled = !canEdit || !user?.verified;
  });
  // Only owners can manage managers, not regular managers
  let isOwner = $derived(object && user && (object.OwnerId === user.id));
  let canManageManagers = $derived(isOwner || (user && user.grants?.includes('admin.panel')));
</script>

<style>
  .manager-form-container {
  width: 100%;
    max-width: none;
    margin: 0;
    padding: 1rem;
  box-sizing: border-box;
  }

  .form-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--color-border);
  }

  .form-actions {
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  .save-message {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-weight: bold;
  }

  .save-message.success {
    background-color: var(--color-success);
    color: white;
  }

  .save-message.error {
    background-color: var(--color-error);
    color: white;
  }

  .disabled-message {
    color: var(--color-text-muted);
    font-style: italic;
    margin-top: 1rem;
  }

  button {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .save-button {
    background-color: var(--color-primary);
    color: white;
  }

  .save-button:hover:not(:disabled) {
    background-color: var(--color-primary-hover);
  }
</style>

{#if !canManageManagers}
  <div class="disabled-message">
    You don't have permission to manage this shop's managers. Only the shop owner can manage managers.
  </div>
{:else if isLoading}
  <div>Loading managers...</div>
{:else}
  <div class="manager-form-container">
    <div class="form-header">
      <h3>Edit Managers</h3>
      <div class="form-actions">
        {#if saveMessage}
          <div class="save-message" class:success={saveMessage.includes('successfully')} class:error={saveMessage.includes('Error')}>
            {saveMessage}
          </div>
        {/if}
        <button 
          class="save-button" 
          type="button" 
          onclick={save} 
          disabled={disabled || saving || !canManageManagers}>
          {saving ? 'Saving...' : 'Save Managers'}
        </button>
      </div>
    </div>

    <EditFormControlGroup 
      title="Managers"
      root={{ Managers: managers }}
      controls={managerConfig.controls}
      dependencies={dependencies} 
      object={{ Managers: managers }}
      disabled={disabled || !canManageManagers} />
  </div>
{/if}
