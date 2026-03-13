<script>
  // @ts-nocheck
  import { goto } from '$app/navigation';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { encodeURIComponentSafe } from '$lib/util';

  // Status filter (applied client-side after fetch)
  let statusFilter = $state('');

  // Column definitions for FancyTable
  const columns = [
    {
      key: 'global_name',
      header: 'Discord Name',
      sortable: true,
      searchable: true,
      width: '280px',
      formatter: (value, row) => {
        const avatarUrl = row.avatar
          ? `https://cdn.discordapp.com/avatars/${row.id}/${row.avatar}.png`
          : `https://cdn.discordapp.com/embed/avatars/${Number(BigInt(row.id) % 5n)}.png`;
        const displayName = row.global_name || row.username || '-';
        const username = row.username || '';
        return `
          <div style="display: flex; align-items: center; gap: 12px;">
            <img src="${avatarUrl}" alt="" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover;" />
            <div>
              <div style="font-weight: 500;">${escapeHtml(displayName)}</div>
              <div style="font-size: 12px; color: var(--text-muted);">@${escapeHtml(username)}</div>
            </div>
          </div>
        `;
      }
    },
    {
      key: 'eu_name',
      header: 'EU Name',
      sortable: true,
      searchable: true,
      formatter: (value) => value || '-'
    },
    {
      key: 'profile_link',
      header: 'Profile',
      sortable: false,
      searchable: false,
      width: '180px',
      formatter: (_, row) => {
        const label = row.eu_name || row.global_name || row.username || row.id || '-';
        const url = `/admin/users/${encodeURIComponentSafe(String(row.id))}`;
        return `<a class="profile-link" href="${url}" onclick="event.stopPropagation()">${escapeHtml(label)}</a>`;
      }
    },
    {
      key: 'society_name',
      header: 'Society',
      sortable: false,
      searchable: false,
      width: '200px',
      formatter: (_, row) => {
        if (!row?.society_name) return '-';
        const label = escapeHtml(`${row.society_name}${row.society_abbreviation ? ` (${row.society_abbreviation})` : ''}`);
        const url = `/societies/${encodeURIComponentSafe(row.society_name)}`;
        return `<a class="society-link" href="${url}">${label}</a>`;
      }
    },
    {
      key: 'status',
      header: 'Status',
      sortable: false,
      searchable: false,
      width: '120px',
      formatter: (_, row) => {
        const status = getUserStatus(row);
        return `<span class="status-badge ${status.class}">${status.label}</span>`;
      }
    },
    {
      key: 'verified',
      header: 'Verified',
      sortable: false,
      searchable: false,
      width: '100px',
      formatter: (value) => {
        if (value) {
          return `<span style="color: var(--success-color);">✓</span>`;
        }
        return `<span style="color: var(--text-muted);">-</span>`;
      }
    }
  ];

  // Escape HTML to prevent XSS
  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function getUserStatus(user) {
    if (user.banned) return { label: 'Banned', class: 'status-banned' };
    if (user.locked) return { label: 'Locked', class: 'status-locked' };
    if (user.administrator) return { label: 'Admin', class: 'status-admin' };
    if (user.verified) return { label: 'Verified', class: 'status-verified' };
    return { label: 'Unverified', class: 'status-unverified' };
  }

  // Lazy loading fetch function
  async function fetchUsers(offset, limit, sortBy, sortOrder, filters) {
    const page = Math.floor(offset / limit) + 1;
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('limit', String(limit));
    params.set('sortBy', sortBy || 'global_name');
    params.set('sortOrder', sortOrder || 'ASC');

    // Use global_name filter as search query if present
    if (filters.global_name) {
      params.set('q', filters.global_name);
    } else if (filters.eu_name) {
      params.set('q', filters.eu_name);
    }

    const response = await fetch(`/api/admin/users?${params}`);
    if (!response.ok) throw new Error('Failed to load users');

    const data = await response.json();

    let users = data.users || [];

    // Apply status filter client-side
    if (statusFilter) {
      users = users.filter(u => {
        if (statusFilter === 'banned') return u.banned;
        if (statusFilter === 'locked') return u.locked;
        if (statusFilter === 'admin') return u.administrator;
        if (statusFilter === 'verified') return u.verified && !u.locked && !u.banned;
        if (statusFilter === 'unverified') return !u.verified;
        return true;
      });
    }

    return {
      rows: users,
      total: data.total || users.length
    };
  }

  function handleRowClick(data) {
    const { row } = data;
    if (row?.id) {
      goto(`/admin/users/${row.id}`);
    }
  }

  // Reference to table for reloading when status filter changes
  let tableRef;
  let tableKey = $state(0);

  function handleStatusChange() {
    // Force table to reload by changing key
    tableKey++;
  }
</script>

<svelte:head>
  <title>Users | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .users-page {
    max-width: 1400px;
    height: calc(100vh - 140px);
    display: flex;
    flex-direction: column;
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

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }

  h1 {
    margin: 0;
    font-size: 24px;
    color: var(--text-color);
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .filter-group label {
    font-size: 13px;
    color: var(--text-muted);
  }

  .filter-group select {
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 14px;
    min-width: 150px;
  }

  .table-container {
    flex: 1;
    min-height: 400px;
  }

  /* Status badge styles for the table */
  :global(.status-badge) {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
  }

  :global(.status-banned) {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error-color);
  }

  :global(.status-locked) {
    background-color: rgba(245, 158, 11, 0.2);
    color: var(--warning-color);
  }

  :global(.status-admin) {
    background-color: rgba(139, 92, 246, 0.2);
    color: #8b5cf6;
  }

  :global(.status-verified) {
    background-color: rgba(16, 185, 129, 0.2);
    color: var(--success-color);
  }

  :global(.status-unverified) {
    background-color: var(--hover-color);
    color: var(--text-muted);
  }

  :global(.society-link) {
    color: var(--accent-color);
    text-decoration: none;
  }

  :global(.society-link:hover) {
    text-decoration: underline;
  }

  :global(.profile-link) {
    color: var(--accent-color);
    text-decoration: none;
  }

  :global(.profile-link:hover) {
    text-decoration: underline;
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .users-page {
      height: auto;
      min-height: calc(100vh - 140px);
    }

    .breadcrumb {
      font-size: 12px;
      flex-wrap: wrap;
    }

    h1 {
      font-size: 20px;
    }

    .page-header {
      flex-direction: column;
      align-items: stretch;
    }

    .filter-group {
      width: 100%;
    }

    .filter-group select {
      flex: 1;
      min-width: unset;
    }

    .table-container {
      min-height: 300px;
    }
  }
</style>

<div class="users-page">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Users</span>
  </div>

  <div class="page-header">
    <h1>User Management</h1>

    <div class="filter-group">
      <label for="status-filter">Status:</label>
      <select id="status-filter" bind:value={statusFilter} onchange={handleStatusChange}>
        <option value="">All Users</option>
        <option value="admin">Admins</option>
        <option value="verified">Verified</option>
        <option value="unverified">Unverified</option>
        <option value="locked">Locked</option>
        <option value="banned">Banned</option>
      </select>
    </div>
  </div>

  <div class="table-container">
    {#key tableKey}
      <FancyTable
        {columns}
        fetchData={fetchUsers}
        rowHeight={56}
        pageSize={50}
        sortable={true}
        searchable={true}
        emptyMessage="No users found"
        onrowClick={handleRowClick}
      />
    {/key}
  </div>
</div>
