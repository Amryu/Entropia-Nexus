<script>
  
  /**
   * @typedef {Object} Props
   * @property {'active'|'stale'|'expired'|'terminated'|'closed'} [state]
   */

  /** @type {Props} */
  let { state = 'active' } = $props();
</script>

<span class="badge badge-subtle {state === 'active' ? 'badge-success' : state === 'stale' ? 'badge-warning' : state === 'expired' ? 'badge-error' : 'badge-muted'}">
  {state}
</span>

<style>
  .badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 500;
    border-radius: 4px;
    white-space: nowrap;
    text-transform: capitalize;
  }
  .badge-subtle { border: none; }
  .badge-success { background-color: rgba(16, 185, 129, 0.2); color: var(--success-color, #16a34a); }
  .badge-warning { background-color: rgba(245, 158, 11, 0.2); color: var(--warning-color, #fbbf24); }
  .badge-error { background-color: rgba(255, 107, 107, 0.2); color: var(--error-color, #ff6b6b); }
  .badge-muted { background-color: rgba(170, 170, 170, 0.15); color: var(--text-muted, #aaa); }
</style>
