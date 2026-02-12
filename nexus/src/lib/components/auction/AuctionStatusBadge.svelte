<!--
  @component AuctionStatusBadge
  Color-coded status badge for auction states.
-->
<script>
  /** @type {'draft'|'active'|'ended'|'settled'|'cancelled'|'frozen'} */
  export let status;
  export let size = 'normal';

  const config = {
    draft: { label: 'Draft', semantic: 'muted' },
    active: { label: 'Active', semantic: 'success' },
    ended: { label: 'Ended', semantic: 'warning' },
    settled: { label: 'Settled', semantic: 'info' },
    cancelled: { label: 'Cancelled', semantic: 'error' },
    frozen: { label: 'Frozen', semantic: 'error' }
  };

  $: cfg = config[status] || { label: status, semantic: 'muted' };
</script>

<span class="status-badge {size} {cfg.semantic}">
  {cfg.label}
</span>

<style>
  .status-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-weight: 500;
    white-space: nowrap;
  }

  .status-badge.small {
    padding: 0.125rem 0.5rem;
    font-size: 0.75rem;
  }

  .status-badge.normal {
    padding: 0.25rem 0.75rem;
    font-size: 0.875rem;
  }

  .status-badge.success {
    color: var(--success-color);
    background-color: var(--success-bg);
  }

  .status-badge.warning {
    color: var(--warning-color);
    background-color: var(--warning-bg);
  }

  .status-badge.error {
    color: var(--error-color);
    background-color: var(--error-bg);
  }

  .status-badge.info {
    color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .status-badge.muted {
    color: var(--text-muted);
    background-color: var(--hover-color);
  }
</style>
