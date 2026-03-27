<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let bookings = $state([]);
  let statusFilter = $state('');
  let isLoading = $state(true);
  let loadError = $state(null);

  onMount(() => loadBookings());

  async function loadBookings() {
    isLoading = true;
    loadError = null;
    try {
      let url = '/api/admin/promos/bookings?limit=100';
      if (statusFilter) url += `&status=${statusFilter}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error('Failed to load bookings');
      bookings = await res.json();
    } catch (err) {
      loadError = err.message;
    } finally {
      isLoading = false;
    }
  }

  function handleFilterChange() {
    loadBookings();
  }

  function formatDate(d) {
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function formatPrice(p) {
    if (p == null) return '—';
    return `${Number(p).toFixed(2)} PED`;
  }

  const statusColors = {
    pending: 'warning',
    approved: 'info',
    active: 'success',
    expired: 'muted',
    cancelled: 'error'
  };
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <span>Promos</span>
  </nav>

  <div class="page-header">
    <h1>Promo Bookings</h1>
    <div class="header-actions">
      <select class="state-filter" bind:value={statusFilter} onchange={handleFilterChange}>
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="approved">Approved</option>
        <option value="active">Active</option>
        <option value="expired">Expired</option>
        <option value="cancelled">Cancelled</option>
      </select>
    </div>
  </div>

  {#if loadError}
    <p class="error-msg">{loadError}</p>
  {:else if isLoading}
    <p class="loading">Loading bookings...</p>
  {:else if bookings.length === 0}
    <p class="empty">No bookings found.</p>
  {:else}
    <table class="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>User</th>
          <th>Promo</th>
          <th>Type</th>
          <th>Slot</th>
          <th>Dates</th>
          <th>Price</th>
          <th>Views</th>
          <th>Clicks</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {#each bookings as b}
          <tr class="clickable-row" onclick={() => goto(`/admin/promos/${b.id}`)}>
            <td>#{b.id}</td>
            <td>{b.user_eu_name || b.user_name}</td>
            <td>{b.promo_name}</td>
            <td class="type-cell">{b.promo_type === 'placement' ? 'Placement' : 'Featured Post'}</td>
            <td>{b.slot_type}</td>
            <td class="date-cell">{formatDate(b.start_date)} – {formatDate(b.end_date)}</td>
            <td>{formatPrice(b.price)}</td>
            <td>{b.total_views ?? 0}</td>
            <td>{b.total_clicks ?? 0}</td>
            <td><span class="status-badge {statusColors[b.status]}">{b.status}</span></td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .page-container {
    padding: 0;
  }

  .breadcrumb {
    margin-bottom: 16px;
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb .separator {
    margin: 0 6px;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.5rem;
    color: var(--text-color);
  }

  .state-filter {
    padding: 6px 12px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }

  .data-table th {
    text-align: left;
    padding: 10px 12px;
    border-bottom: 2px solid var(--border-color);
    color: var(--text-muted);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .data-table td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .clickable-row {
    cursor: pointer;
    transition: background-color 0.15s ease;
  }

  .clickable-row:hover {
    background-color: var(--hover-color);
  }

  .type-cell {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    color: var(--text-muted);
  }

  .date-cell {
    white-space: nowrap;
    font-size: 0.8125rem;
  }

  .status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .status-badge.warning {
    background-color: rgba(234, 179, 8, 0.15);
    color: #eab308;
  }

  .status-badge.info {
    background-color: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
  }

  .status-badge.success {
    background-color: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }

  .status-badge.muted {
    background-color: rgba(107, 114, 128, 0.15);
    color: var(--text-muted);
  }

  .status-badge.error {
    background-color: rgba(239, 68, 68, 0.15);
    color: #ef4444;
  }

  .loading, .empty {
    color: var(--text-muted);
    padding: 24px 0;
  }

  .error-msg {
    color: #ef4444;
    padding: 12px;
    background-color: rgba(239, 68, 68, 0.1);
    border-radius: 4px;
  }
</style>
