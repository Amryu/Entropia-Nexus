<script>
  //@ts-nocheck
  import { onMount } from 'svelte';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { addToast } from '$lib/stores/toasts.js';

  let items = [];
  let loading = true;
  let showResolved = false;

  const columns = [
    { key: 'item_name', header: 'Item Name', main: true, sortable: true, searchable: true },
    {
      key: 'value', header: 'Per-Unit TT', sortable: true, width: '100px',
      formatter: (v) => v != null ? Number(v).toFixed(2) + ' PED' : '-',
    },
    {
      key: 'user_count', header: 'Users', sortable: true, width: '70px',
      formatter: (v) => v?.toLocaleString() ?? '0',
    },
    {
      key: 'first_seen_at', header: 'First Seen', sortable: true, width: '140px', hideOnMobile: true,
      formatter: (v) => v ? new Date(v).toLocaleDateString() : '-',
      sortValue: (row) => row.first_seen_at ? new Date(row.first_seen_at).getTime() : 0,
    },
    {
      key: 'last_seen_at', header: 'Last Seen', sortable: true, width: '140px', hideOnMobile: true,
      formatter: (v) => v ? new Date(v).toLocaleDateString() : '-',
      sortValue: (row) => row.last_seen_at ? new Date(row.last_seen_at).getTime() : 0,
    },
    {
      key: '_actions', header: '', width: '100px',
      formatter: () => '',
      rawValue: true,
    },
  ];

  onMount(() => {
    loadItems();
  });

  async function loadItems() {
    loading = true;
    try {
      const res = await fetch(`/api/admin/unknown-items?resolved=${showResolved}&limit=200`);
      if (res.ok) {
        items = await res.json();
      }
    } catch (err) {
      console.error('Error loading unknown items:', err);
    } finally {
      loading = false;
    }
  }

  async function markResolved(item) {
    try {
      const res = await fetch(`/api/admin/unknown-items/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        items = items.filter(i => i.id !== item.id);
        addToast(`Marked "${item.item_name}" as resolved`, 'success');
      }
    } catch (err) {
      addToast('Failed to resolve item', 'error');
    }
  }

  function toggleResolved() {
    showResolved = !showResolved;
    loadItems();
  }
</script>

<div class="unknown-items-page">
  <div class="page-header">
    <h1>Unknown Items</h1>
    <div class="header-actions">
      <label class="toggle-label">
        <input type="checkbox" bind:checked={showResolved} on:change={toggleResolved} />
        Show resolved
      </label>
    </div>
  </div>

  <p class="description">
    Items that couldn't be matched during inventory imports. Sorted by number of unique users who have them.
  </p>

  <FancyTable
    {columns}
    data={items}
    {loading}
    rowHeight={44}
    emptyMessage={showResolved ? 'No resolved items' : 'No unknown items found'}
    defaultSort={{ column: 'user_count', order: 'DESC' }}
  >
    <svelte:fragment slot="cell" let:column let:row>
      {#if column.key === '_actions'}
        {#if !row.resolved}
          <button class="btn btn-sm btn-resolve" on:click|stopPropagation={() => markResolved(row)}>
            Resolve
          </button>
        {:else}
          <span class="badge badge-subtle badge-success">Resolved</span>
        {/if}
      {/if}
    </svelte:fragment>
  </FancyTable>
</div>

<style>
  .unknown-items-page {
    padding: 0;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.4rem;
  }

  .description {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin: 0 0 1rem;
  }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.85rem;
    color: var(--text-muted);
    cursor: pointer;
  }

  .btn {
    padding: 0.3rem 0.6rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
  }

  .btn-sm {
    padding: 0.25rem 0.5rem;
  }

  .btn-resolve {
    background: var(--accent-color);
    color: #fff;
  }

  .btn-resolve:hover {
    background: var(--accent-color-hover);
  }
</style>
