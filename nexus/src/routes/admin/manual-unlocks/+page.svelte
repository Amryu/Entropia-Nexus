<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';

  let groups = $state([]);
  let activeKey = $state(null);
  let activeGroup = $state(null);
  let entries = $state([]);
  let loadingGroups = $state(true);
  let loadingEntries = $state(false);
  let filter = $state('');
  let unlocking = $state(new Set());

  onMount(async () => {
    await loadGroups();
    if (groups.length > 0) {
      await selectGroup(groups[0].key);
    }
  });

  async function loadGroups() {
    loadingGroups = true;
    try {
      const res = await fetch('/api/admin/manual-unlocks');
      if (!res.ok) throw new Error('Failed to load groups');
      const data = await res.json();
      groups = data.groups || [];
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      loadingGroups = false;
    }
  }

  async function selectGroup(key) {
    activeKey = key;
    loadingEntries = true;
    entries = [];
    try {
      const res = await fetch(`/api/admin/manual-unlocks?group=${encodeURIComponent(key)}`);
      if (!res.ok) throw new Error('Failed to load entries');
      const data = await res.json();
      activeGroup = data.group;
      entries = data.entries || [];
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      loadingEntries = false;
    }
  }

  async function unlock(entry) {
    if (unlocking.has(entry.id)) return;
    unlocking = new Set([...unlocking, entry.id]);
    try {
      const res = await fetch('/api/admin/manual-unlocks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ group: activeKey, id: entry.id }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.message || body.error || 'Unlock failed');
      }
      entries = entries.filter(e => e.id !== entry.id);
      addToast(`Unlocked ${entry.name}`, 'success');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      const next = new Set(unlocking);
      next.delete(entry.id);
      unlocking = next;
    }
  }

  let filtered = $derived.by(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(e =>
      (e.name || '').toLowerCase().includes(q) ||
      (e.subtitle || '').toLowerCase().includes(q)
    );
  });
</script>

<svelte:head>
  <title>Manual Unlocks | Admin | Entropia Nexus</title>
</svelte:head>

<div class="page">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Manual Unlocks</span>
  </div>

  <h1>Manual Unlocks</h1>
  <p class="subtitle">
    Manually unlock entries that are hidden from public listings while waiting on ingestion
    (e.g. fish without a confirmed discovery global).
  </p>

  {#if loadingGroups}
    <div class="state">Loading groups…</div>
  {:else if groups.length === 0}
    <div class="state">No manual-unlock groups configured.</div>
  {:else}
    <div class="tabs">
      {#each groups as g}
        <button
          class="tab"
          class:active={g.key === activeKey}
          onclick={() => selectGroup(g.key)}
        >
          {g.label}
        </button>
      {/each}
    </div>

    {#if activeGroup}
      <p class="group-desc">{activeGroup.description}</p>

      <div class="toolbar">
        <input
          class="filter"
          type="text"
          placeholder="Filter by name…"
          bind:value={filter}
        />
        <span class="count">
          {loadingEntries ? '…' : `${filtered.length} of ${entries.length}`} locked
        </span>
      </div>

      {#if loadingEntries}
        <div class="state">Loading entries…</div>
      {:else if entries.length === 0}
        <div class="state empty">No locked {activeGroup.entryLabel || 'entries'}.</div>
      {:else if filtered.length === 0}
        <div class="state empty">No matches for "{filter}".</div>
      {:else}
        <div class="list">
          {#each filtered as entry}
            <div class="row">
              <div class="info">
                <span class="name">{entry.name}</span>
                {#if entry.subtitle}
                  <span class="subtitle-tag">{entry.subtitle}</span>
                {/if}
              </div>
              <button
                class="btn-unlock"
                disabled={unlocking.has(entry.id)}
                onclick={() => unlock(entry)}
              >
                {unlocking.has(entry.id) ? 'Unlocking…' : 'Unlock'}
              </button>
            </div>
          {/each}
        </div>
      {/if}
    {/if}
  {/if}
</div>

<style>
  .page {
    max-width: 900px;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .breadcrumb span {
    color: var(--text-muted);
  }

  h1 {
    margin: 0 0 8px;
    font-size: 1.4rem;
    color: var(--text-color);
  }

  .subtitle {
    color: var(--text-muted);
    margin: 0 0 20px;
    font-size: 0.9rem;
  }

  .tabs {
    display: flex;
    gap: 4px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 16px;
  }

  .tab {
    padding: 8px 14px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 0.9rem;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
  }

  .tab:hover {
    color: var(--text-color);
  }

  .tab.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
  }

  .group-desc {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin: 0 0 16px;
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .filter {
    flex: 1;
    max-width: 320px;
    padding: 8px 10px;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.9rem;
  }

  .filter:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .count {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .list {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
  }

  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-color);
  }

  .row:last-child {
    border-bottom: none;
  }

  .info {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .name {
    color: var(--text-color);
    font-size: 0.9rem;
  }

  .subtitle-tag {
    font-size: 0.75rem;
    color: var(--text-muted);
    background: var(--hover-color);
    border-radius: 999px;
    padding: 2px 8px;
  }

  .btn-unlock {
    padding: 6px 12px;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .btn-unlock:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }

  .btn-unlock:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .state {
    padding: 24px;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .state.empty {
    background: var(--secondary-color);
    border: 1px dashed var(--border-color);
    border-radius: 6px;
  }
</style>
