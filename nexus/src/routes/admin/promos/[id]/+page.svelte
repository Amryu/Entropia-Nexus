<script>
  // @ts-nocheck
  import { addToast } from '$lib/stores/toasts';
  import { goto } from '$app/navigation';

  let { data } = $props();

  let bookingOverride = $state(null);
  let booking = $derived(bookingOverride ?? data.booking);
  let images = $derived(data.images);
  let metrics = $derived(data.metrics);

  let price = $state('');
  let adminNote = $state('');
  let saving = $state(false);
  let actionPending = $state(false);

  // Sync form fields when page data loads/changes
  $effect.pre(() => {
    const b = data.booking;
    price = b?.price ?? '';
    adminNote = b?.admin_note ?? '';
    bookingOverride = null;
  });

  const statusColors = {
    pending: 'warning', approved: 'info', active: 'success',
    expired: 'muted', cancelled: 'error'
  };

  function formatDate(d) {
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  let totalViews = $derived(metrics.reduce((s, m) => s + m.views, 0));
  let totalClicks = $derived(metrics.reduce((s, m) => s + m.clicks, 0));
  let ctr = $derived(totalViews > 0 ? ((totalClicks / totalViews) * 100).toFixed(2) : '0.00');

  async function saveDetails() {
    saving = true;
    try {
      const res = await fetch(`/api/admin/promos/bookings/${booking.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          price: price !== '' ? parseFloat(price) : null,
          admin_note: adminNote || null
        })
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.error || 'Save failed'); }
      const updated = await res.json();
      bookingOverride = { ...booking, ...updated };
      addToast('Booking updated', 'success');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      saving = false;
    }
  }

  async function performAction(action) {
    if (action === 'approve' && !booking.price && !price) {
      addToast('Set a price before approving', 'error');
      return;
    }
    actionPending = true;
    try {
      // Save price first if changed
      if (price !== '' && parseFloat(price) !== parseFloat(booking.price)) {
        await fetch(`/api/admin/promos/bookings/${booking.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ price: parseFloat(price), admin_note: adminNote || null })
        });
      }
      const res = await fetch(`/api/admin/promos/bookings/${booking.id}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_note: adminNote || null })
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.error || 'Action failed'); }
      const updated = await res.json();
      bookingOverride = { ...booking, ...updated };
      addToast(`Booking ${action === 'reject' ? 'rejected' : action + 'd'}`, 'success');
    } catch (err) {
      addToast(err.message, 'error');
    } finally {
      actionPending = false;
    }
  }
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <a href="/admin/promos">Promos</a>
    <span class="separator">/</span>
    <span>Booking #{booking.id}</span>
  </nav>

  <div class="page-header">
    <h1>Booking #{booking.id} — {booking.promo_name}</h1>
    <span class="status-badge {statusColors[booking.status]}">{booking.status}</span>
  </div>

  <div class="detail-grid">
    <!-- Booking Info -->
    <section class="detail-card">
      <h2>Booking Details</h2>
      <dl class="detail-list">
        <dt>User</dt>
        <dd>{booking.user_eu_name || booking.user_name}</dd>
        <dt>Promo Type</dt>
        <dd>{booking.promo_type === 'placement' ? 'Placement' : 'Featured Post'}</dd>
        <dt>Slot</dt>
        <dd>{booking.slot_type}</dd>
        <dt>Period</dt>
        <dd>{formatDate(booking.start_date)} – {formatDate(booking.end_date)} ({booking.weeks} week{booking.weeks > 1 ? 's' : ''})</dd>
        <dt>Created</dt>
        <dd>{formatDate(booking.created_at)}</dd>
      </dl>
    </section>

    <!-- Promo Preview -->
    <section class="detail-card">
      <h2>Creative Preview</h2>
      {#if booking.promo_type === 'placement'}
        {#if images.length > 0}
          <div class="image-previews">
            {#each images as img}
              <div class="image-preview">
                <img src="/api/img/promo-visual/{booking.promo_id}-{img.slot_variant}" alt="{img.slot_variant}" />
                <span class="variant-label">{img.slot_variant} ({img.width}x{img.height})</span>
              </div>
            {/each}
          </div>
        {:else}
          <p class="empty">No images uploaded yet</p>
        {/if}
      {:else}
        <div class="featured-preview">
          {#if booking.promo_title}<h3>{booking.promo_title}</h3>{/if}
          {#if booking.promo_summary}<p>{booking.promo_summary}</p>{/if}
          {#if booking.promo_link}<a href={booking.promo_link} target="_blank" rel="noopener">{booking.promo_link}</a>{/if}
        </div>
      {/if}
    </section>

    <!-- Admin Controls -->
    <section class="detail-card">
      <h2>Admin Controls</h2>
      <div class="form-group">
        <label for="price">Price (PED)</label>
        <input id="price" type="number" step="0.01" min="0" bind:value={price} placeholder="Set negotiated price" />
      </div>
      <div class="form-group">
        <label for="note">Admin Note</label>
        <textarea id="note" rows="3" bind:value={adminNote} placeholder="Internal notes..."></textarea>
      </div>
      <div class="action-buttons">
        <button class="btn save" onclick={saveDetails} disabled={saving}>
          {saving ? 'Saving...' : 'Save'}
        </button>
        {#if booking.status === 'pending'}
          <button class="btn approve" onclick={() => performAction('approve')} disabled={actionPending}>Approve</button>
          <button class="btn reject" onclick={() => performAction('reject')} disabled={actionPending}>Reject</button>
        {/if}
        {#if booking.status === 'approved'}
          <button class="btn activate" onclick={() => performAction('activate')} disabled={actionPending}>Activate Now</button>
        {/if}
      </div>
    </section>

    <!-- Metrics -->
    {#if metrics.length > 0}
      <section class="detail-card">
        <h2>Metrics</h2>
        <div class="metrics-summary">
          <div class="metric"><span class="metric-value">{totalViews.toLocaleString()}</span><span class="metric-label">Views</span></div>
          <div class="metric"><span class="metric-value">{totalClicks.toLocaleString()}</span><span class="metric-label">Clicks</span></div>
          <div class="metric"><span class="metric-value">{ctr}%</span><span class="metric-label">CTR</span></div>
        </div>
        <div class="metrics-chart">
          {#each metrics as m}
            <div class="chart-bar" title="{formatDate(m.event_date)}: {m.views} views, {m.clicks} clicks">
              <div class="bar-fill" style="height: {Math.min(100, (m.views / Math.max(...metrics.map(x => x.views), 1)) * 100)}%"></div>
              <span class="bar-label">{new Date(m.event_date).getDate()}</span>
            </div>
          {/each}
        </div>
      </section>
    {/if}
  </div>
</div>

<style>
  .page-container { padding: 0; }

  .breadcrumb { margin-bottom: 16px; font-size: 0.8125rem; color: var(--text-muted); }
  .breadcrumb a { color: var(--accent-color); text-decoration: none; }
  .breadcrumb .separator { margin: 0 6px; }

  .page-header { display: flex; align-items: center; gap: 12px; margin-bottom: 24px; }
  .page-header h1 { margin: 0; font-size: 1.375rem; color: var(--text-color); }

  .status-badge {
    display: inline-block; padding: 3px 10px; border-radius: 4px;
    font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.3px;
  }
  .status-badge.warning { background: rgba(234,179,8,0.15); color: #eab308; }
  .status-badge.info { background: rgba(59,130,246,0.15); color: #3b82f6; }
  .status-badge.success { background: rgba(34,197,94,0.15); color: #22c55e; }
  .status-badge.muted { background: rgba(107,114,128,0.15); color: var(--text-muted); }
  .status-badge.error { background: rgba(239,68,68,0.15); color: #ef4444; }

  .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

  .detail-card {
    background-color: var(--secondary-color); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 20px;
  }

  .detail-card h2 { margin: 0 0 16px; font-size: 1rem; color: var(--text-color); }

  .detail-list { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 8px 16px; font-size: 0.875rem; }
  .detail-list dt { color: var(--text-muted); font-weight: 500; }
  .detail-list dd { margin: 0; color: var(--text-color); }

  .image-previews { display: flex; flex-direction: column; gap: 12px; }
  .image-preview img { max-width: 100%; max-height: 200px; object-fit: contain; border-radius: 4px; background: var(--primary-color); }
  .variant-label { font-size: 0.75rem; color: var(--text-muted); margin-top: 4px; display: block; }

  .featured-preview h3 { margin: 0 0 8px; font-size: 1rem; color: var(--text-color); }
  .featured-preview p { margin: 0 0 8px; font-size: 0.875rem; color: var(--text-muted); }
  .featured-preview a { color: var(--accent-color); font-size: 0.8125rem; }

  .form-group { margin-bottom: 14px; }
  .form-group label { display: block; margin-bottom: 4px; font-size: 0.8125rem; color: var(--text-muted); }
  .form-group input, .form-group textarea {
    width: 100%; padding: 8px 10px; background: var(--primary-color); color: var(--text-color);
    border: 1px solid var(--border-color); border-radius: 4px; font-size: 0.875rem; box-sizing: border-box;
  }
  .form-group input:focus, .form-group textarea:focus { border-color: var(--accent-color); outline: none; }

  .action-buttons { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
  .btn {
    padding: 8px 16px; border: none; border-radius: 4px; font-size: 0.8125rem;
    font-weight: 500; cursor: pointer; transition: opacity 0.15s;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn.save { background: var(--accent-color); color: white; }
  .btn.approve { background: #22c55e; color: white; }
  .btn.reject { background: #ef4444; color: white; }
  .btn.activate { background: #3b82f6; color: white; }

  .metrics-summary { display: flex; gap: 24px; margin-bottom: 16px; }
  .metric { display: flex; flex-direction: column; align-items: center; }
  .metric-value { font-size: 1.25rem; font-weight: 700; color: var(--text-color); }
  .metric-label { font-size: 0.75rem; color: var(--text-muted); }

  .metrics-chart { display: flex; gap: 2px; align-items: flex-end; height: 80px; }
  .chart-bar { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; }
  .bar-fill { width: 100%; min-height: 2px; background: var(--accent-color); border-radius: 2px 2px 0 0; transition: height 0.3s; }
  .bar-label { font-size: 0.625rem; color: var(--text-muted); margin-top: 2px; }

  .empty { color: var(--text-muted); font-size: 0.875rem; }

  @media (max-width: 899px) {
    .detail-grid { grid-template-columns: 1fr; }
  }
</style>
