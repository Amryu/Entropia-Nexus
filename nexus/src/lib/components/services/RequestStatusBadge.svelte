<script>
  export let status;
  export let size = 'normal'; // 'small', 'normal', 'large'

  const statusConfig = {
    pending: { label: 'Pending', color: '#f59e0b', bgColor: '#fef3c7' },
    negotiating: { label: 'In Conversation', color: '#8b5cf6', bgColor: '#ede9fe' },
    accepted: { label: 'Accepted', color: '#3b82f6', bgColor: '#dbeafe' },
    declined: { label: 'Declined', color: '#ef4444', bgColor: '#fee2e2' },
    in_progress: { label: 'In Progress', color: '#10b981', bgColor: '#d1fae5' },
    completed: { label: 'Completed', color: '#059669', bgColor: '#a7f3d0' },
    cancelled: { label: 'Cancelled', color: '#6b7280', bgColor: '#e5e7eb' },
    aborted: { label: 'Aborted', color: '#dc2626', bgColor: '#fecaca' }
  };

  $: config = statusConfig[status] || { label: status, color: '#6b7280', bgColor: '#e5e7eb' };
</script>

<span
  class="status-badge {size}"
  style="--badge-color: {config.color}; --badge-bg: {config.bgColor};"
>
  {config.label}
</span>

<style>
  .status-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-weight: 500;
    color: var(--badge-color);
    background-color: var(--badge-bg);
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
</style>
