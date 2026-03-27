<!--
  @component Promo Bookings
  Table of user's bookings with status badges and metrics.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto } from '$app/navigation';

  let { data } = $props();

  let bookings = $derived(data.bookings ?? []);

  function formatDate(d) {
    if (!d) return '';
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function ctr(views, clicks) {
    if (!views || views === 0) return '0.00%';
    return ((clicks / views) * 100).toFixed(2) + '%';
  }

  const STATUS_COLORS = {
    pending: 'warning',
    approved: 'info',
    active: 'success',
    expired: 'muted',
    cancelled: 'error'
  };
</script>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/account">Account</a>
      <span>/</span>
      <a href="/account/settings/promos">Promos</a>
      <span>/</span>
      <span>Bookings</span>
    </div>

    <div class="page-header">
      <h1>My Bookings</h1>
      <a href="/account/settings/promos/bookings/new" class="btn-primary">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        New Booking
      </a>
    </div>

    {#if bookings.length === 0}
      <div class="empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        <p>No bookings yet. Book a slot to start running your promo.</p>
        <a href="/account/settings/promos/bookings/new" class="btn-primary">New Booking</a>
      </div>
    {:else}
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Promo</th>
              <th>Slot</th>
              <th>Dates</th>
              <th>Views</th>
              <th>Clicks</th>
              <th>CTR</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {#each bookings as b}
              <tr class="clickable-row" onclick={() => goto(`/account/settings/promos/bookings/${b.id}`)}>
                <td class="promo-cell">{b.promo_name}</td>
                <td class="slot-cell">{b.slot_type}</td>
                <td class="date-cell">{formatDate(b.start_date)} – {formatDate(b.end_date)}</td>
                <td>{b.total_views.toLocaleString()}</td>
                <td>{b.total_clicks.toLocaleString()}</td>
                <td>{ctr(b.total_views, b.total_clicks)}</td>
                <td><span class="status-badge {STATUS_COLORS[b.status]}">{b.status}</span></td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 1.5rem;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.75rem;
    color: var(--text-color);
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    background: var(--accent-color);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    text-decoration: none;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 3rem 1rem;
    gap: 1rem;
    color: var(--text-muted);
  }

  .empty-state p {
    margin: 0;
    max-width: 300px;
    font-size: 0.9rem;
  }

  .table-wrap {
    overflow-x: auto;
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
    white-space: nowrap;
  }

  .data-table td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .clickable-row {
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .clickable-row:hover {
    background-color: var(--hover-color);
  }

  .promo-cell {
    font-weight: 500;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .slot-cell {
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

  @media (max-width: 768px) {
    .data-table {
      font-size: 0.8125rem;
    }

    .data-table th,
    .data-table td {
      padding: 8px;
    }
  }
</style>
