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

  let isLoading = true;
  let dependencies = {};

  // Inventory configuration
  const inventoryConfig = {
    constructor: () => ({
      InventoryGroups: []
    }),
    dependencies: ['items'],
    controls: [
      {
        label: 'Inventory Groups',
        type: 'list',
        config: {
          constructor: () => ({
            Name: '',
            SortOrder: 0,
            Items: []
          }),
          controls: [
            { 
              label: 'Group Name', 
              type: 'text', 
              '_get': x => x.Name, 
              '_set': (x, v) => x.Name = v 
            },
            {
              label: 'Items',
              type: 'list',
              config: {
                constructor: () => ({
                  ItemId: null,
                  StackSize: 1,
                  Markup: 100.00,
                  SortOrder: 0
                }),
                dependencies: ['items'],
                controls: [
                  { 
                    label: 'Item', 
                    type: 'select', 
                    options: (_, d) => d.items.map(x => x.Name).sort((a,b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })), 
                    '_get': x => x.Item?.Name, 
                    '_set': (x, v, d) => {
                      const item = d.items.find(i => i.Name === v);
                      x.ItemId = item?.Id || null;
                    }
                  },
                  { 
                    label: 'Stack Size', 
                    type: 'number', 
                    step: 1, 
                    min: 1, 
                    '_get': x => x.StackSize, 
                    '_set': (x, v) => x.StackSize = Math.max(1, parseInt(v) || 1) 
                  },
                  { 
                    label: 'Markup %', 
                    type: 'number', 
                    step: 0.01, 
                    min: 0, 
                    '_get': x => x.Markup, 
                    '_set': (x, v) => x.Markup = Math.max(0, parseFloat(v) || 100) 
                  }
                ]
              }, 
              itemNameFunc: j => `Item ${j + 1}`, 
              '_get': x => x.Items || [], 
              '_set': (x, v) => x.Items = v
            }
          ]
        }, 
        itemNameFunc: j => `Group ${j + 1}`, 
        '_get': x => x.InventoryGroups || [], 
        '_set': (x, v) => x.InventoryGroups = v
      }
    ]
  };

  function loadForm() {
    let dependencyNames = ['items'];

    Promise.all(dependencyNames.map(x =>
      apiCall(fetch, `/${x}`).then(response => [ x, response.sort((a, b) => a.Name.localeCompare(b.Name))])
    )).then(results => {
      dependencies = { ...dependencies, ...Object.fromEntries(results) };
      isLoading = false;
    })
    .catch(error => {
      console.error(error);
      isLoading = false;
    });
  }

  // Load form when component mounts
  loadForm();

  async function save() {
    if (disabled || saving) return;
    
    saving = true;
    saveMessage = 'Saving inventory...';

    try {
      // Convert InventoryGroups to PascalCase API format
      let payload = {
        Id: object.Id,
        InventoryGroups: (object.InventoryGroups || []).map(group => ({
          Name: group.Name,
          Items: (group.Items || []).map(item => ({
            ItemId: item.ItemId,
            StackSize: item.StackSize,
            Markup: item.Markup,
            SortOrder: item.SortOrder || 0
          }))
        }))
      };
      
      const response = await apiPut(fetch, `/api/shops/${object.Id}/inventory`, payload);
      
      if (response?.success) {
        saveMessage = 'Inventory saved successfully!';
        setTimeout(() => { window.location.reload(); }, 1000);
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
  .inventory-form-container {
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
</style>

{#if disabled}
  <div class="disabled-message">
    You don't have permission to edit this shop's inventory.
  </div>
{:else if isLoading}
  <div>Loading inventory editor...</div>
{:else}
  <div class="inventory-form-container">
    <div class="form-header">
      <h3>Edit Inventory</h3>
      <div class="form-actions">
        {#if saveMessage}
          <div class="save-message" class:success={saveMessage.includes('successfully')} class:error={saveMessage.includes('Error')}>
            {saveMessage}
          </div>
        {/if}
        <button type="button" on:click={save} disabled={disabled || saving}>
          {saving ? 'Saving...' : 'Save Inventory'}
        </button>
        <button type="button" on:click={cancel}>Cancel</button>
      </div>
    </div>

    <EditFormControlGroup 
      config={inventoryConfig} 
      dependencies={dependencies} 
      object={object} 
      disabled={disabled} />
  </div>
{/if}
