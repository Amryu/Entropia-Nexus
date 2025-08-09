<script>
  //@ts-nocheck
  import { apiCall, apiPut } from "$lib/util";
  import EditFormControlGroup from "./EditFormControlGroup.svelte";

  export let object;
  export let user;
  export let canEdit = false;
 
  let disabled = false;
  let saving = false;
  let saveMessage = '';
 
  $: disabled = !canEdit || !user?.verified;

  // Only owners can manage managers, not regular managers
  $: isOwner = object && user && (object.OwnerId === user.id);
  $: canManageManagers = isOwner || (user && user.administrator);

  let isLoading = true;
  let dependencies = {};

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
            EuName: ''
          }),
          controls: [
            { 
              label: 'Entropia Name', 
              type: 'text', 
              '_get': x => x.EuName || x.User?.Name || '', 
              '_set': (x, v) => x.EuName = v
            }
          ]
        }, 
        itemNameFunc: j => `Manager ${j + 1}`, 
        '_get': x => x.Managers || [], 
        '_set': (x, v) => x.Managers = v
      }
    ]
  };

  function loadForm() {
    // No dependencies needed since we're using text input
    isLoading = false;
  }

  // Load form when component mounts
  loadForm();

  async function save() {
    if (disabled || saving || !canManageManagers) return;
    
    saving = true;
    saveMessage = 'Saving managers...';

    try {
      // Convert managers to PascalCase expected by the API
      let payload = {
        Managers: (object.Managers || []).map(manager => ({
          EuName: manager.EuName || manager.User?.Name || ''
        })).filter(manager => manager.EuName.trim())
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
</script>

<style>
  .manager-form-container {
    max-width: 800px;
    margin: 0 auto;
    padding: 1rem;
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

  .cancel-button {
    background-color: var(--color-secondary);
    color: var(--color-text-primary);
  }

  .cancel-button:hover {
    background-color: var(--color-secondary-hover);
  }
</style>

{#if !canManageManagers}
  <div class="disabled-message">
    You don't have permission to manage this shop's managers. Only the shop owner can manage managers.
  </div>
{:else if isLoading}
  <div>Loading manager editor...</div>
{:else}
  <div class="manager-form-container">
    <div class="form-header">
      <h3>Manage Shop Managers</h3>
      <div class="form-actions">
        {#if saveMessage}
          <div class="save-message" class:success={saveMessage.includes('successfully')} class:error={saveMessage.includes('Error')}>
            {saveMessage}
          </div>
        {/if}
        <button 
          class="save-button" 
          type="button" 
          on:click={save} 
          disabled={disabled || saving || !canManageManagers}>
          {saving ? 'Saving...' : 'Save Managers'}
        </button>
        <button class="cancel-button" type="button" on:click={cancel}>Cancel</button>
      </div>
    </div>

    <EditFormControlGroup 
      config={managerConfig} 
      dependencies={dependencies} 
      object={object} 
      disabled={disabled || !canManageManagers} />
  </div>
{/if}
