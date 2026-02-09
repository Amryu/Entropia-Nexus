<script>
  //@ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import FancyTable from '$lib/components/FancyTable.svelte';

  export let show = false;

  const dispatch = createEventDispatcher();

  let step = 'paste'; // 'paste' | 'preview' | 'done'
  let rawInput = '';
  let parseError = null;
  let parsedItems = [];
  let importing = false;
  let importResult = null;
  let importError = null;

  const previewColumns = [
    { key: 'item_name', header: 'Item', main: true, sortable: true, searchable: false },
    { key: 'item_id', header: 'ID', width: '70px', sortable: true, searchable: false },
    { key: 'quantity', header: 'Qty', width: '60px', sortable: true, searchable: false },
    {
      key: 'value', header: 'Value', width: '80px', sortable: true, searchable: false,
      formatter: (val) => val != null ? Number(val).toFixed(2) : '<span style="opacity:0.4">—</span>'
    },
    {
      key: 'container', header: 'Container', width: '140px', sortable: true, searchable: false,
      hideOnMobile: true,
      formatter: (val) => val || '<span style="opacity:0.4">—</span>'
    },
  ];

  function handleParse() {
    parseError = null;
    parsedItems = [];

    const text = rawInput.trim();
    if (!text) {
      parseError = 'Please paste some data.';
      return;
    }

    try {
      let data = JSON.parse(text);

      // Handle wrapped formats: { items: [...] } or { inventory: [...] }
      if (data && !Array.isArray(data)) {
        if (Array.isArray(data.items)) data = data.items;
        else if (Array.isArray(data.inventory)) data = data.inventory;
        else if (Array.isArray(data.Items)) data = data.Items;
        else if (Array.isArray(data.Inventory)) data = data.Inventory;
        else {
          parseError = 'JSON must be an array of items or an object with an "items" array.';
          return;
        }
      }

      if (!Array.isArray(data) || data.length === 0) {
        parseError = 'No items found in the pasted data.';
        return;
      }

      if (data.length > 500) {
        parseError = `Too many items (${data.length}). Maximum 500 items per import.`;
        return;
      }

      // Build a containerRefId → container name lookup for resolving references
      const containerLookup = new Map();
      for (const raw of data) {
        if (raw.id != null) {
          const name = raw.item_name ?? raw.ItemName ?? raw.Name ?? raw.name ?? '';
          if (name) containerLookup.set(raw.id, String(name).trim());
        }
      }

      // Normalize items from various formats
      parsedItems = data.map((raw, i) => {
        const itemId = raw.item_id ?? raw.ItemId ?? raw.Id ?? raw.id ?? null;
        const itemName = raw.item_name ?? raw.ItemName ?? raw.Name ?? raw.name ?? '';
        const quantity = raw.quantity ?? raw.Quantity ?? raw.qty ?? raw.Qty ?? 1;
        const instanceKey = raw.instance_key ?? raw.InstanceKey ?? raw.instanceKey ?? null;
        const details = raw.details ?? raw.Details ?? null;
        const value = raw.value ?? raw.Value ?? null;
        const container = raw.container ?? raw.Container ?? null;
        const containerRefId = raw.containerRefId ?? raw.container_ref_id ?? null;

        if (itemId == null || !Number.isFinite(Number(itemId))) {
          throw new Error(`Item ${i + 1}: missing or invalid item_id`);
        }
        if (!itemName) {
          throw new Error(`Item ${i + 1}: missing item_name`);
        }

        // Resolve container: prefer explicit string, fall back to containerRefId lookup
        let resolvedContainer = null;
        if (typeof container === 'string' && container.trim()) {
          resolvedContainer = container.trim();
        } else if (containerRefId != null && containerLookup.has(containerRefId)) {
          resolvedContainer = containerLookup.get(containerRefId);
        }

        return {
          item_id: Number(itemId),
          item_name: String(itemName).trim(),
          quantity: Math.max(0, Number(quantity) || 0),
          instance_key: instanceKey || null,
          details: details || null,
          value: value != null ? Number(value) : null,
          container: resolvedContainer,
        };
      });

      step = 'preview';
    } catch (e) {
      parseError = e.message;
    }
  }

  async function handleImport() {
    importing = true;
    importError = null;
    importResult = null;

    try {
      const res = await fetch('/api/users/inventory', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: parsedItems }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'Import failed');
      }
      importResult = data;
      step = 'done';
      dispatch('imported', data);
    } catch (e) {
      importError = e.message;
    } finally {
      importing = false;
    }
  }

  function handleClose() {
    // Reset state
    step = 'paste';
    rawInput = '';
    parseError = null;
    parsedItems = [];
    importResult = null;
    importError = null;
    dispatch('close');
  }

  function handleBack() {
    if (step === 'preview') {
      step = 'paste';
      parsedItems = [];
    } else if (step === 'done') {
      handleClose();
    }
  }
</script>

{#if show}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="modal-overlay"
    on:click={(e) => { if (e.target.classList.contains('modal-overlay')) handleClose(); }}
    on:keydown={(e) => { if (e.key === 'Escape') handleClose(); }}
  >
    <div class="modal">
      <h3 class="modal-title">
        {#if step === 'paste'}
          Import Inventory
        {:else if step === 'preview'}
          Preview Import ({parsedItems.length} item{parsedItems.length !== 1 ? 's' : ''})
        {:else}
          Import Complete
        {/if}
      </h3>

      {#if step === 'paste'}
        <p class="hint">Paste your inventory JSON data below. Accepts <code>{"{"}</code><code>items: [...]{"}"}</code> with <code>id</code>, <code>name</code>, <code>quantity</code>, <code>value</code>, and <code>container</code> fields.</p>
        <textarea
          class="json-input"
          bind:value={rawInput}
          placeholder={'{"items":[{"id":123,"name":"Weapon","quantity":5,"value":1.50,"container":"STORAGE (Calypso)"}]}'}
          rows="10"
        ></textarea>
        {#if parseError}
          <div class="error-msg">{parseError}</div>
        {/if}
        <div class="modal-actions">
          <button class="btn-secondary" on:click={handleClose}>Cancel</button>
          <button class="btn-primary" on:click={handleParse} disabled={!rawInput.trim()}>Parse</button>
        </div>

      {:else if step === 'preview'}
        <div class="preview-table">
          <FancyTable
            columns={previewColumns}
            data={parsedItems}
            rowHeight={36}
            sortable={true}
            searchable={false}
            emptyMessage="No items to import"
          />
        </div>
        {#if importError}
          <div class="error-msg">{importError}</div>
        {/if}
        <div class="modal-actions">
          <button class="btn-secondary" on:click={handleBack}>Back</button>
          <button class="btn-primary" on:click={handleImport} disabled={importing || parsedItems.length === 0}>
            {importing ? 'Importing...' : `Import ${parsedItems.length} item${parsedItems.length !== 1 ? 's' : ''}`}
          </button>
        </div>

      {:else}
        <div class="success-msg">
          Successfully imported {importResult?.imported ?? 0} item{(importResult?.imported ?? 0) !== 1 ? 's' : ''}.
        </div>
        <div class="modal-actions">
          <button class="btn-primary" on:click={handleClose}>Done</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
  }
  .modal {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
    width: 600px;
    max-width: calc(100% - 32px);
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  }
  .modal-title {
    margin: 0 0 12px 0;
    font-size: 18px;
  }
  .hint {
    margin: 0 0 8px 0;
    font-size: 13px;
    color: var(--text-muted);
  }
  .hint code {
    background: var(--hover-color);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
  }
  .json-input {
    width: 100%;
    padding: 10px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    font-family: monospace;
    font-size: 12px;
    resize: vertical;
    box-sizing: border-box;
  }
  .json-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }
  .preview-table {
    flex: 1;
    min-height: 200px;
    max-height: 400px;
    overflow: hidden;
    margin-bottom: 12px;
  }
  .error-msg {
    margin: 8px 0;
    padding: 0.75rem 1rem;
    background: var(--error-bg);
    border: 1px solid var(--error-color);
    border-radius: 4px;
    color: var(--error-color);
    font-size: 13px;
  }
  .success-msg {
    margin: 12px 0;
    padding: 0.75rem 1rem;
    background: var(--success-bg);
    border: 1px solid var(--success-color);
    border-radius: 4px;
    color: var(--success-color);
    font-size: 14px;
    text-align: center;
  }
  .modal-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 12px;
  }
  .btn-primary, .btn-secondary {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    border: 1px solid var(--border-color);
  }
  .btn-primary {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }
  .btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover);
  }
  .btn-primary:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
  .btn-secondary {
    background: transparent;
    color: var(--text-color);
  }
  .btn-secondary:hover {
    background: var(--hover-color);
  }
</style>
