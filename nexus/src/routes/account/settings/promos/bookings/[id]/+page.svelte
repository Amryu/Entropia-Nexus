<!--
  @component Booking Detail
  Shows booking info, metrics chart, images, and cancel button.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto, invalidateAll } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';

  let { data } = $props();

  let booking = $derived(data.booking);
  let metrics = $derived(data.metrics ?? []);
  let images = $derived(data.images ?? []);
  let cancelling = $state(false);

  let totalViews = $derived(metrics.reduce((sum, m) => sum + m.views, 0));
  let totalClicks = $derived(metrics.reduce((sum, m) => sum + m.clicks, 0));
  let ctr = $derived(totalViews > 0 ? ((totalClicks / totalViews) * 100).toFixed(2) : '0.00');

  // Find max value for chart scaling
  let maxViews = $derived(Math.max(1, ...metrics.map(m => m.views)));

  const STATUS_COLORS = {
    pending: 'warning',
    approved: 'info',
    active: 'success',
    expired: 'muted',
    cancelled: 'error'
  };

  const CANCELLABLE_STATUSES = ['pending', 'approved'];

  function formatDate(d) {
    if (!d) return '';
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function formatShortDate(d) {
    if (!d) return '';
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  async function cancelBooking() {
    if (!confirm('Are you sure you want to cancel this booking? This cannot be undone.')) return;
    cancelling = true;
    try {
      const res = await fetch(`/api/promos/bookings/${booking.id}`, { method: 'DELETE' });
      const result = await res.json();
      if (!res.ok) {
        addToast(result?.error || 'Failed to cancel booking', 'error');
        return;
      }
      addToast('Booking cancelled', 'success');
      await invalidateAll();
    } catch {
      addToast('Network error', 'error');
    } finally {
      cancelling = false;
    }
  }
</script>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/account">Account</a>
      <span>/</span>
      <a href="/account/settings/promos">Promos</a>
      <span>/</span>
      <a href="/account/settings/promos/bookings">Bookings</a>
      <span>/</span>
      <span>#{booking.id}</span>
    </div>

    <div class="page-header">
      <div>
        <h1>Booking #{booking.id}</h1>
        <span class="status-badge {STATUS_COLORS[booking.status]}">{booking.status}</span>
      </div>
      {#if CANCELLABLE_STATUSES.includes(booking.status)}
        <button class="btn-danger" disabled={cancelling} onclick={cancelBooking}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>
          {cancelling ? 'Cancelling...' : 'Cancel Booking'}
        </button>
      {/if}
    </div>

    <div class="detail-grid">
      <div class="detail-section">
        <h2>Details</h2>
        <dl class="detail-list">
          <div class="detail-row">
            <dt>Promo</dt>
            <dd><a href="/account/settings/promos/library/{booking.promo_id}">{booking.promo_name}</a></dd>
          </div>
          <div class="detail-row">
            <dt>Type</dt>
            <dd>{booking.promo_type === 'placement' ? 'Placement' : 'Featured Post'}</dd>
          </div>
          <div class="detail-row">
            <dt>Slot</dt>
            <dd>{booking.slot_type}</dd>
          </div>
          <div class="detail-row">
            <dt>Period</dt>
            <dd>{formatDate(booking.start_date)} - {formatDate(booking.end_date)}</dd>
          </div>
          <div class="detail-row">
            <dt>Duration</dt>
            <dd>{booking.weeks} week{booking.weeks === 1 ? '' : 's'}</dd>
          </div>
          {#if booking.price != null}
            <div class="detail-row">
              <dt>Price</dt>
              <dd>{Number(booking.price).toFixed(2)} {booking.currency || 'PED'}</dd>
            </div>
          {/if}
          {#if booking.admin_note}
            <div class="detail-row">
              <dt>Note</dt>
              <dd>{booking.admin_note}</dd>
            </div>
          {/if}
        </dl>
      </div>

      <div class="detail-section">
        <h2>Performance</h2>
        <div class="metrics-summary">
          <div class="metric">
            <span class="metric-value">{totalViews.toLocaleString()}</span>
            <span class="metric-label">Views</span>
          </div>
          <div class="metric">
            <span class="metric-value">{totalClicks.toLocaleString()}</span>
            <span class="metric-label">Clicks</span>
          </div>
          <div class="metric">
            <span class="metric-value">{ctr}%</span>
            <span class="metric-label">CTR</span>
          </div>
        </div>

        {#if metrics.length > 0}
          <div class="chart-container">
            <div class="chart-bars">
              {#each metrics as m}
                <div class="chart-col" title="{formatShortDate(m.event_date)}: {m.views} views, {m.clicks} clicks">
                  <div class="bar-wrap">
                    <div class="bar bar-views" style="height: {(m.views / maxViews) * 100}%"></div>
                  </div>
                  <span class="chart-label">{formatShortDate(m.event_date)}</span>
                </div>
              {/each}
            </div>
            <div class="chart-legend">
              <span class="legend-item"><span class="legend-swatch views"></span> Views</span>
            </div>
          </div>
        {:else}
          <p class="no-data">No metrics data yet.</p>
        {/if}
      </div>
    </div>

    {#if images.length > 0}
      <div class="detail-section">
        <h2>Images</h2>
        <div class="image-gallery">
          {#each images as img}
            <div class="gallery-item">
              <img src={img.image_path} alt="{img.slot_variant}" />
              <span class="gallery-label">{img.slot_variant} ({img.width}x{img.height})</span>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <div class="back-row">
      <a href="/account/settings/promos/bookings" class="btn-secondary">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
        Back to Bookings
      </a>
    </div>
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
    align-items: flex-start;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .page-header h1 {
    margin: 0;
    font-size: 1.75rem;
    color: var(--text-color);
    display: inline;
    margin-right: 0.75rem;
  }

  h2 {
    margin: 0 0 0.75rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .detail-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .detail-section {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
  }

  .detail-grid .detail-section {
    margin-bottom: 0;
  }

  .detail-list {
    margin: 0;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border-color);
    gap: 0.75rem;
  }

  .detail-row:last-child {
    border-bottom: none;
  }

  .detail-row dt {
    font-size: 0.8125rem;
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .detail-row dd {
    margin: 0;
    font-size: 0.875rem;
    color: var(--text-color);
    text-align: right;
  }

  .detail-row dd a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .detail-row dd a:hover {
    text-decoration: underline;
  }

  .metrics-summary {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.25rem;
  }

  .metric {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 0.75rem 0.5rem;
    background: var(--primary-color);
    border-radius: 6px;
  }

  .metric-value {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .metric-label {
    font-size: 0.6875rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-top: 0.125rem;
  }

  .chart-container {
    margin-top: 0.5rem;
  }

  .chart-bars {
    display: flex;
    gap: 2px;
    align-items: flex-end;
    height: 120px;
    overflow-x: auto;
    padding-bottom: 1.5rem;
    position: relative;
  }

  .chart-col {
    flex: 1;
    min-width: 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
    cursor: default;
  }

  .bar-wrap {
    flex: 1;
    width: 100%;
    display: flex;
    align-items: flex-end;
    justify-content: center;
  }

  .bar {
    width: 80%;
    max-width: 24px;
    border-radius: 2px 2px 0 0;
    min-height: 2px;
    transition: height 0.2s;
  }

  .bar-views {
    background: var(--accent-color);
  }

  .chart-label {
    font-size: 0.5625rem;
    color: var(--text-muted);
    white-space: nowrap;
    position: absolute;
    bottom: 0;
    transform: rotate(-45deg);
    transform-origin: top left;
  }

  .chart-legend {
    display: flex;
    gap: 1rem;
    justify-content: center;
    margin-top: 0.5rem;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .legend-swatch {
    width: 10px;
    height: 10px;
    border-radius: 2px;
  }

  .legend-swatch.views {
    background: var(--accent-color);
  }

  .no-data {
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin: 0;
  }

  .image-gallery {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .gallery-item {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
  }

  .gallery-item img {
    max-width: 200px;
    max-height: 200px;
    object-fit: contain;
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .gallery-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-align: center;
  }

  .back-row {
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 0.875rem;
    text-decoration: none;
    cursor: pointer;
    transition: border-color 0.15s;
  }

  .btn-secondary:hover {
    border-color: var(--accent-color);
  }

  .btn-danger {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1rem;
    background: transparent;
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 6px;
    font-size: 0.875rem;
    cursor: pointer;
    transition: background 0.15s;
  }

  .btn-danger:hover {
    background: rgba(239, 68, 68, 0.1);
  }

  .btn-danger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    vertical-align: middle;
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
    .detail-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
