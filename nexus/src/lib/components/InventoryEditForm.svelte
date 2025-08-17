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

  // Work on a normalized copy so controls match PascalCase fields
  let formObject = null;

  $: formObject = normalizeObject(object);

  function normalizeObject(src) {
    if (!src) return null;
    const clone = JSON.parse(JSON.stringify(src));
    // Normalize groups
    clone.InventoryGroups = (clone.InventoryGroups || []).map(g => ({
      Id: g.Id ?? g.id ?? null,
      Name: g.Name ?? g.name ?? '',
      SortOrder: g.SortOrder ?? g.sort_order ?? 0,
      Items: (g.Items || []).map(it => ({
        ItemId: it.ItemId ?? it.item_id ?? null,
        StackSize: it.StackSize ?? it.stack_size ?? 1,
        Markup: it.Markup ?? it.markup ?? 100,
        SortOrder: it.SortOrder ?? it.item_sort_order ?? it.sort_order ?? 0,
        Item: it.Item ?? null
      }))
    }));
    return clone;
  }

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
          initialize: (group, _d, _root, currentIndex) => {
            // Preserve order by defaulting SortOrder to index
            group.SortOrder = currentIndex ?? 0;
          },
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
              // Keep items ordered by SortOrder
              sort: (a, b) => (a?.SortOrder ?? 0) - (b?.SortOrder ?? 0),
              config: {
                constructor: () => ({
                  ItemId: null,
                  StackSize: 1,
                  Markup: 100.00,
                  SortOrder: 0
                }),
                dependencies: ['items'],
                initialize: (item, _d, _root, currentIndex) => {
                  // Initialize default sort/index
                  item.SortOrder = currentIndex ?? 0;
                  item.StackSize = item.StackSize ?? 1;
                  item.Markup = item.Markup ?? 100.0;
                },
                controls: [
                  {
                    label: 'Item',
                    type: 'input-validator',
                    validator: (val, d) => !!val && d.items?.some(i => i.Name === val),
                    '_get': (x, d) => {
                      if (x.Item?.Name) return x.Item.Name;
                      if (x.ItemId) {
                        const found = d.items?.find(i => i.Id === x.ItemId);
                        return found?.Name ?? '';
                      }
                      return '';
                    },
                    '_set': (x, v, d) => {
                      const item = d.items?.find(i => i.Name === v);
                      x.ItemId = item?.Id || null;
                      // Keep a light reference for UI friendliness
                      x.Item = item ? { Id: item.Id, Name: item.Name } : null;
                    }
                  },
                  {
                    label: 'Qty | Markup %',
                    type: 'multi',
                    fields: ['Stack Size', 'Markup %'],
                    '_get': x => [x.StackSize ?? 1, x.Markup ?? 100.0],
                    '_set': (x, v) => {
                      const [ss, mu] = Array.isArray(v) ? v : [x.StackSize ?? 1, x.Markup ?? 100.0];
                      // Sanitize values
                      const stack = Math.max(1, Math.floor(Number(ss) || 1));
                      const markup = Math.max(0, Number(mu) || 0);
                      x.StackSize = stack;
                      x.Markup = Number(markup.toFixed(2));
                    }
                  }
                ]
              }, 
              itemNameFunc: j => `#${j + 1}`, 
              '_get': x => x.Items || [], 
              '_set': (x, v) => x.Items = v
            }
          ]
        }, 
        itemNameFunc: j => `Group ${j + 1}`, 
        // Keep groups ordered by SortOrder
        sort: (a, b) => (a?.SortOrder ?? 0) - (b?.SortOrder ?? 0),
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
      // Convert InventoryGroups to PascalCase API format from normalized object
      const groups = (formObject.InventoryGroups || []).map((group, gi) => {
        const items = (group.Items || []).map((item, ii) => ({
          ItemId: item.ItemId ?? item.item_id ?? null,
          StackSize: Math.max(1, parseInt(item.StackSize ?? item.stack_size ?? 1) || 1),
          Markup: Math.max(0, parseFloat(item.Markup ?? item.markup ?? 100) || 0),
          SortOrder: ii
        }));
        return {
          Name: group.Name,
          SortOrder: gi,
          Items: items
        };
      });

      let payload = {
        Id: formObject.Id,
        InventoryGroups: groups
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
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 1rem;
  box-sizing: border-box;
  overflow-x: hidden;
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

  /* Match ManagerEditForm button styles */
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
        <button class="save-button" type="button" on:click={save} disabled={disabled || saving}>
          {saving ? 'Saving...' : 'Save Inventory'}
        </button>
      </div>
    </div>

    <EditFormControlGroup 
      title="Inventory"
      root={formObject}
      controls={inventoryConfig.controls}
      dependencies={dependencies} 
      object={formObject} 
      disabled={disabled} />
  </div>
{/if}
