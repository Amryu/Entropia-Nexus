<!--
  @component Admin Roles & Grants Management
  Displays all roles, their grants, and provides CRUD for roles.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';

  let roles = $state([]);
  let allGrants = $state([]);
  let loading = $state(true);
  let error = $state(null);

  // Dialog state
  let showDialog = $state(false);
  let dialogMode = $state('create'); // 'create' | 'edit'
  let editingRole = $state(null);
  let formName = $state('');
  let formDescription = $state('');
  let formParentId = $state(null);
  let formGrants = $state({}); // { grantKey: boolean }
  let saving = $state(false);

  // Expanded row state
  let expandedRoleId = $state(null);

  onMount(async () => {
    await loadData();
  });

  async function loadData() {
    loading = true;
    error = null;
    try {
      const [rolesRes, grantsRes] = await Promise.all([
        fetch('/api/admin/roles'),
        fetch('/api/admin/grants')
      ]);
      if (!rolesRes.ok || !grantsRes.ok) throw new Error('Failed to load data');
      roles = await rolesRes.json();
      allGrants = await grantsRes.json();
    } catch (e) {
      error = e.message;
    }
    loading = false;
  }

  function openCreateDialog() {
    dialogMode = 'create';
    editingRole = null;
    formName = '';
    formDescription = '';
    formParentId = null;
    formGrants = {};
    showDialog = true;
  }

  async function openEditDialog(role) {
    dialogMode = 'edit';
    editingRole = role;
    formName = role.name;
    formDescription = role.description || '';
    formParentId = role.parent_id;

    // Load role grants
    const res = await fetch(`/api/admin/roles/${role.id}/grants`);
    if (res.ok) {
      const roleGrants = await res.json();
      formGrants = {};
      for (const g of roleGrants) {
        formGrants[g.key] = g.granted;
      }
    }
    showDialog = true;
  }

  async function handleSave() {
    saving = true;
    try {
      const url = dialogMode === 'create' ? '/api/admin/roles' : `/api/admin/roles/${editingRole.id}`;
      const method = dialogMode === 'create' ? 'POST' : 'PUT';

      const roleRes = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formName,
          description: formDescription || null,
          parent_id: formParentId || null
        })
      });

      if (!roleRes.ok) {
        const data = await roleRes.json();
        throw new Error(data.error || 'Failed to save role');
      }

      const savedRole = await roleRes.json();

      // Save grants — only send checked (true) entries; unchecked means unset (not denied)
      const grantEntries = Object.entries(formGrants)
        .filter(([_, granted]) => granted === true)
        .map(([key]) => ({ key, granted: true }));

      if (grantEntries.length > 0 || dialogMode === 'edit') {
        await fetch(`/api/admin/roles/${savedRole.id}/grants`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ grants: grantEntries })
        });
      }

      showDialog = false;
      await loadData();
    } catch (e) {
      error = e.message;
    }
    saving = false;
  }

  async function handleDelete(role) {
    if (!confirm(`Delete role "${role.name}"? Users with this role will lose its permissions.`)) return;

    const res = await fetch(`/api/admin/roles/${role.id}`, { method: 'DELETE' });
    if (res.ok) {
      await loadData();
    } else {
      const data = await res.json();
      error = data.error || 'Failed to delete role';
    }
  }

  function toggleExpand(roleId) {
    expandedRoleId = expandedRoleId === roleId ? null : roleId;
  }
</script>

<svelte:head>
  <title>Roles & Grants - Admin - Entropia Nexus</title>
</svelte:head>

<div class="roles-page">
  <div class="page-header">
    <h1>Roles & Grants</h1>
    <button class="btn-primary" onclick={openCreateDialog}>Create Role</button>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if loading}
    <div class="loading">Loading...</div>
  {:else}
    <div class="roles-table">
      <div class="table-header">
        <span class="col-name">Name</span>
        <span class="col-desc">Description</span>
        <span class="col-parent">Parent</span>
        <span class="col-grants">Grants</span>
        <span class="col-users">Users</span>
        <span class="col-actions">Actions</span>
      </div>

      {#each roles as role}
        <div class="table-row" class:expanded={expandedRoleId === role.id}>
          <span class="col-name">
            <button class="expand-btn" onclick={() => toggleExpand(role.id)}>
              <svg class="chevron" class:open={expandedRoleId === role.id} width="12" height="12" viewBox="0 0 12 12">
                <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" />
              </svg>
            </button>
            <strong>{role.name}</strong>
          </span>
          <span class="col-desc">{role.description || '-'}</span>
          <span class="col-parent">{role.parent_name || '-'}</span>
          <span class="col-grants">{role.grant_count}</span>
          <span class="col-users">{role.user_count}</span>
          <span class="col-actions">
            <button class="btn-small" onclick={() => openEditDialog(role)}>Edit</button>
            {#if role.name !== 'admin'}
              <button class="btn-small btn-danger" onclick={() => handleDelete(role)}>Delete</button>
            {/if}
          </span>
        </div>

        {#if expandedRoleId === role.id}
          <div class="row-details">
            {#await fetch(`/api/admin/roles/${role.id}/grants`).then(r => r.json())}
              <span class="loading-small">Loading grants...</span>
            {:then roleGrants}
              {#if roleGrants.length === 0}
                <span class="no-grants">No grants assigned</span>
              {:else}
                <div class="grant-badges">
                  {#each roleGrants as g}
                    <span class="grant-badge" class:denied={!g.granted}>
                      {g.key}
                      {#if !g.granted}<span class="denied-label">denied</span>{/if}
                    </span>
                  {/each}
                </div>
              {/if}
            {:catch}
              <span class="error-text">Failed to load grants</span>
            {/await}
          </div>
        {/if}
      {/each}

      {#if roles.length === 0}
        <div class="empty-row">No roles defined.</div>
      {/if}
    </div>

    <div class="grants-section">
      <h2>Available Grants</h2>
      <div class="grants-list">
        {#each allGrants as grant}
          <div class="grant-item">
            <code>{grant.key}</code>
            <span class="grant-desc">{grant.description || ''}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

<!-- Create/Edit Dialog -->
{#if showDialog}
  <div class="dialog-overlay" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) showDialog = false; }}>
    <div class="dialog">
      <h2>{dialogMode === 'create' ? 'Create Role' : `Edit: ${editingRole.name}`}</h2>

      <div class="form-field">
        <label for="role-name">Name</label>
        <input id="role-name" type="text" bind:value={formName} placeholder="e.g. editor" />
      </div>

      <div class="form-field">
        <label for="role-desc">Description</label>
        <input id="role-desc" type="text" bind:value={formDescription} placeholder="Optional description" />
      </div>

      <div class="form-field">
        <label for="role-parent">Parent Role</label>
        <select id="role-parent" bind:value={formParentId}>
          <option value={null}>None</option>
          {#each roles.filter(r => r.id !== editingRole?.id) as r}
            <option value={r.id}>{r.name}</option>
          {/each}
        </select>
      </div>

      <div class="form-field">
        <label>Grants</label>
        <div class="grant-checkboxes">
          {#each allGrants as grant}
            <label class="grant-checkbox">
              <input type="checkbox" bind:checked={formGrants[grant.key]} />
              <span class="grant-key">{grant.key}</span>
              {#if grant.description}
                <span class="grant-hint">{grant.description}</span>
              {/if}
            </label>
          {/each}
        </div>
      </div>

      <div class="dialog-actions">
        <button class="btn-secondary" onclick={() => showDialog = false} disabled={saving}>Cancel</button>
        <button class="btn-primary" onclick={handleSave} disabled={saving || !formName.trim()}>
          {saving ? 'Saving...' : (dialogMode === 'create' ? 'Create' : 'Save')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .roles-page {
    padding: 24px;
    max-width: 1100px;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.5rem;
    color: var(--text-color);
  }

  .error-banner {
    background-color: var(--error-bg, #fee);
    color: var(--error-text, #c33);
    padding: 10px 16px;
    border-radius: 6px;
    margin-bottom: 16px;
    font-size: 0.875rem;
  }

  .loading {
    text-align: center;
    padding: 48px;
    color: var(--text-muted);
  }

  /* Table */
  .roles-table {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 32px;
  }

  .table-header, .table-row {
    display: grid;
    grid-template-columns: 180px 1fr 100px 70px 60px 130px;
    align-items: center;
    padding: 10px 16px;
    gap: 8px;
    font-size: 0.875rem;
  }

  .table-header {
    background-color: var(--primary-color);
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .table-row {
    border-top: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .table-row:hover {
    background-color: var(--hover-color);
  }

  .col-name {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .col-desc {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-muted);
  }

  .expand-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px;
    display: flex;
    color: var(--text-muted);
  }

  .chevron {
    transition: transform 0.15s ease;
  }

  .chevron.open {
    transform: rotate(90deg);
  }

  .row-details {
    padding: 8px 16px 12px 42px;
    border-top: 1px solid var(--border-color);
    background-color: var(--primary-color);
  }

  .grant-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .grant-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.75rem;
    font-family: monospace;
    color: var(--text-color);
  }

  .grant-badge.denied {
    border-color: var(--error-text, #c33);
    color: var(--error-text, #c33);
  }

  .denied-label {
    font-size: 0.625rem;
    text-transform: uppercase;
    font-weight: 600;
  }

  .empty-row, .loading-small, .no-grants, .error-text {
    padding: 16px;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.875rem;
  }

  .error-text {
    color: var(--error-text, #c33);
  }

  /* Grants section */
  .grants-section h2 {
    font-size: 1.1rem;
    margin: 0 0 12px 0;
    color: var(--text-color);
  }

  .grants-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .grant-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .grant-item code {
    font-weight: 600;
    color: var(--accent-color);
    min-width: 140px;
  }

  .grant-desc {
    color: var(--text-muted);
  }

  /* Buttons */
  .btn-primary {
    padding: 8px 16px;
    background-color: var(--accent-color);
    color: var(--primary-color);
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    padding: 8px 16px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
  }

  .btn-small {
    padding: 4px 10px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.75rem;
  }

  .btn-small:hover {
    background-color: var(--hover-color);
  }

  .btn-danger {
    color: var(--error-text, #c33);
    border-color: var(--error-text, #c33);
  }

  .btn-danger:hover {
    background-color: var(--error-bg, #fee);
  }

  .col-actions {
    display: flex;
    gap: 6px;
  }

  /* Dialog */
  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .dialog {
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 24px;
    width: 520px;
    max-width: 90vw;
    max-height: 80vh;
    overflow-y: auto;
    overflow-x: hidden;
  }

  .dialog h2 {
    margin: 0 0 20px 0;
    font-size: 1.2rem;
    color: var(--text-color);
  }

  .form-field {
    margin-bottom: 16px;
  }

  .form-field label {
    display: block;
    margin-bottom: 4px;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--text-muted);
  }

  .form-field input[type="text"],
  .form-field select {
    width: 100%;
    padding: 8px 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    font-size: 0.875rem;
    box-sizing: border-box;
  }

  .grant-checkboxes {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 8px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    max-height: 250px;
    overflow-y: auto;
  }

  .grant-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.8125rem;
    cursor: pointer;
  }

  .grant-key {
    font-family: monospace;
    font-weight: 500;
    color: var(--text-color);
  }

  .grant-hint {
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 20px;
  }

  @media (max-width: 900px) {
    .roles-page {
      padding: 16px;
    }

    .table-header, .table-row {
      grid-template-columns: 1fr 1fr 80px;
    }

    .col-desc, .col-parent, .col-users {
      display: none;
    }
  }
</style>
