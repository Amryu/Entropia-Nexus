<script>
  //@ts-nocheck
  import { apiCall, apiPost, apiPut, navigate } from "$lib/util";
  import EditFormControlGroup from "./EditFormControlGroup.svelte";

  export let entity;
  export let object;
  export let config;
  export let user;
  export let endpoint; // API endpoint for direct updates
  export let canEdit = false; // Whether user can edit this object
 
  let disabled = false;
  let saving = false;
  let saveMessage = '';
 
  $: disabled = !canEdit || !user?.verified;

  $: if (config) loadForm(config);

  let isLoading = true;
  let dependencies = {};

  function loadForm(config) {
    if (!config) return;

    let dependencyNames = getControlDependencies(config);

    if (dependencyNames.length > 0) {
      Promise.all(dependencyNames.filter(x => dependencies[x] == null).map(x =>
        apiCall(fetch, `/${x}`).then(response => [ x, response.sort((a, b) => a.Name.localeCompare(b.Name))])
      )).then(results => {
        dependencies = { ...dependencies, ...Object.fromEntries(results) };
        isLoading = false;
      })
      .catch(error => {
        console.error(error);
        isLoading = false;
      })
    }
    else {
      isLoading = false;
    }
  }

  function getControlDependencies(config) {
    let childDependencies = getControls(config.controls).filter(x => x?.config?.dependencies != null).flatMap(x => x.config.dependencies);

    if (config.dependencies != null) {
      return [...new Set([...config.dependencies, ...childDependencies])];
    }
    else {
      return childDependencies;
    }
  }

  function getControls(controls) {
    let result = controls.filter(x => x != null);

    for (let i = 0; i < controls.length; i++) {
      if (controls[i]?.controls) {
        result = [...result, ...getControls(controls[i].controls)];
      }
    }

    return result;
  }

  async function save() {
    if (disabled || saving) return;
    
    saving = true;
    saveMessage = 'Saving...';

    try {
      // Make a deep copy to avoid modifying the original object
      let payload = JSON.parse(JSON.stringify(object));
      
      // Remove any client-side only properties that shouldn't be sent to the server
      delete payload.Owner;
      delete payload.Planet;
      delete payload.Managers;
      delete payload.InventoryGroups;
      
      const response = await apiPut(fetch, endpoint, payload);
      
      if (response.success) {
        saveMessage = 'Saved successfully!';
        // Refresh the page to show updated data
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      } else {
        saveMessage = 'Error: ' + (response.error || 'Unknown error');
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
    navigate(window.location.pathname);
  }
</script>

<style>
  .form-container {
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
    padding: 1rem;
    background-color: var(--color-warning);
    color: var(--color-text-primary);
    border-radius: 4px;
    margin-bottom: 1rem;
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

<div class="form-container">
  <div class="form-header">
    <h2>Edit {entity}</h2>
    <div class="form-actions">
      {#if saveMessage}
        <div class="save-message {saveMessage.includes('Error') ? 'error' : 'success'}">
          {saveMessage}
        </div>
      {/if}
      <button 
        class="save-button" 
        on:click={save} 
        disabled={disabled || saving}>
        {saving ? 'Saving...' : 'Save'}
      </button>
      <button class="cancel-button" on:click={cancel}>Cancel</button>
    </div>
  </div>

  {#if !canEdit}
    <div class="disabled-message">
      You don't have permission to edit this {entity.toLowerCase()}. Only the owner and managers can make changes.
    </div>
  {/if}

  {#if isLoading}
    <p>Loading form...</p>
  {:else}
    <EditFormControlGroup 
      config={config} 
      object={object} 
      dependencies={dependencies} 
      disabled={disabled} />
  {/if}
</div>
