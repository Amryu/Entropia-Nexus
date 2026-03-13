<script>
  // @ts-nocheck
  import { addToast } from '$lib/stores/toasts.js';

  let { data } = $props();
  let reports = $state(data.reports || []);
  let filter = $state('pending'); // 'pending' | 'resolved' | 'all'

  let filtered = $derived(filter === 'all' ? reports
    : filter === 'pending' ? reports.filter(r => !r.resolved_at)
    : reports.filter(r => r.resolved_at));

  async function deleteMedia(report) {
    if (!confirm(`Delete media on global #${report.global_id}? This cannot be undone.`)) return;

    try {
      const res = await fetch(`/api/globals/${report.global_id}/media`, { method: 'DELETE' });
      if (res.ok) {
        addToast('Media deleted.', { type: 'success' });
        await resolveReport(report, true);
      } else {
        const d = await res.json().catch(() => ({}));
        addToast(d.error || 'Failed to delete media.', { type: 'error' });
      }
    } catch {
      addToast('Failed to delete media.', { type: 'error' });
    }
  }

  async function resolveReport(report, skipToast = false) {
    try {
      const res = await fetch(`/api/admin/globals/reports/${report.id}/resolve`, { method: 'POST' });
      if (res.ok) {
        report.resolved_at = new Date().toISOString();
        reports = [...reports];
        if (!skipToast) addToast('Report dismissed.', { type: 'success' });
      }
    } catch {
      addToast('Failed to resolve report.', { type: 'error' });
    }
  }

  function formatDate(d) {
    return new Date(d).toLocaleString();
  }
</script>

<svelte:head>
  <title>Media Reports | Admin</title>
</svelte:head>

<div class="page">
  <div class="page-header">
    <h1>Globals Media Reports</h1>
    <div class="filter-btns">
      <button class:active={filter === 'pending'} onclick={() => filter = 'pending'}>
        Pending ({reports.filter(r => !r.resolved_at).length})
      </button>
      <button class:active={filter === 'resolved'} onclick={() => filter = 'resolved'}>Resolved</button>
      <button class:active={filter === 'all'} onclick={() => filter = 'all'}>All</button>
    </div>
  </div>

  {#if filtered.length === 0}
    <p class="empty">No reports to show.</p>
  {:else}
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Global</th>
            <th>Player</th>
            <th>Media</th>
            <th>Reporter</th>
            <th>Reason</th>
            <th>Date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as report}
            <tr class:resolved={report.resolved_at}>
              <td>
                <a href="/globals/target/{encodeURIComponent(report.target_name)}" target="_blank">
                  #{report.global_id}
                </a>
                <span class="text-muted"> — {report.target_name}</span>
              </td>
              <td>{report.player_name}</td>
              <td>
                {#if report.has_image}
                  <a href="/api/img/global/{report.global_id}" target="_blank">Image</a>
                {:else if report.has_video}
                  Video
                {:else}
                  <span class="text-muted">Removed</span>
                {/if}
              </td>
              <td>{report.reporter_name}</td>
              <td class="reason-cell">{report.reason}</td>
              <td class="text-muted">{formatDate(report.created_at)}</td>
              <td class="actions-cell">
                {#if !report.resolved_at}
                  <button class="btn-delete" onclick={() => deleteMedia(report)}>Delete Media</button>
                  <button class="btn-dismiss" onclick={() => resolveReport(report)}>Dismiss</button>
                {:else}
                  <span class="text-muted">Resolved{report.resolved_by_name ? ` by ${report.resolved_by_name}` : ''}</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px 20px;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.25rem;
  }

  .filter-btns {
    display: flex;
    gap: 4px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .filter-btns button {
    padding: 4px 12px;
    font-size: 0.75rem;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }

  .filter-btns button.active {
    background: var(--accent-color);
    color: #fff;
  }

  .empty {
    text-align: center;
    color: var(--text-muted);
    padding: 40px;
  }

  .table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: var(--secondary-color);
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
  }

  th {
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    white-space: nowrap;
  }

  td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-color);
    vertical-align: top;
  }

  tr.resolved {
    opacity: 0.5;
  }

  .reason-cell {
    max-width: 300px;
    word-break: break-word;
  }

  .actions-cell {
    white-space: nowrap;
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .btn-delete {
    padding: 4px 10px;
    font-size: 12px;
    background: transparent;
    color: var(--color-danger);
    border: 1px solid color-mix(in srgb, var(--color-danger) 30%, transparent);
    border-radius: 4px;
    cursor: pointer;
  }

  .btn-delete:hover {
    background: color-mix(in srgb, var(--color-danger) 15%, transparent);
  }

  .btn-dismiss {
    padding: 4px 10px;
    font-size: 12px;
    background: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
  }

  .btn-dismiss:hover {
    color: var(--text-color);
  }

  .text-muted {
    color: var(--text-muted);
  }
</style>
