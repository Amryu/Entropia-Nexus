<script>
  /** @type {'draft'|'available'|'rented'|'unlisted'|'deleted'|'open'|'accepted'|'rejected'|'in_progress'|'completed'|'cancelled'} */
  export let status;
  /** @type {'offer'|'request'} */
  export let type = 'offer';
  export let size = 'normal';

  const offerConfig = {
    draft: { label: 'Draft', semantic: 'muted' },
    available: { label: 'Available', semantic: 'success' },
    rented: { label: 'Rented Out', semantic: 'info' },
    unlisted: { label: 'Unlisted', semantic: 'warning' },
    deleted: { label: 'Deleted', semantic: 'error' }
  };

  const requestConfig = {
    open: { label: 'Open', semantic: 'warning' },
    accepted: { label: 'Accepted', semantic: 'info' },
    rejected: { label: 'Rejected', semantic: 'error' },
    in_progress: { label: 'In Progress', semantic: 'success' },
    completed: { label: 'Completed', semantic: 'success' },
    cancelled: { label: 'Cancelled', semantic: 'muted' }
  };

  $: configs = type === 'offer' ? offerConfig : requestConfig;
  $: config = configs[status] || { label: status, semantic: 'muted' };
</script>

<span class="status-badge {size} {config.semantic}">
  {config.label}
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

  .status-badge.large {
    padding: 0.375rem 1rem;
    font-size: 1rem;
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
