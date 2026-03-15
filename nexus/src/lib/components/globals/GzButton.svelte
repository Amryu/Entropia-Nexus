<script>
  // @ts-nocheck
  /**
   * GzButton — Inline "GZ" (congrats) toggle button for globals.
   * Shows count and allows logged-in users to toggle their GZ.
   */

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {number} globalId
   * @property {number} [count]
   * @property {boolean} [userGz]
   * @property {object|null} [user]
   * @property {boolean} [compact]
   */

  /** @type {Props} */
  let {
    globalId,
    count = $bindable(0),
    userGz = $bindable(false),
    user = null,
    compact = false
  } = $props();

  let toggling = $state(false);

  async function toggle() {
    if (!user || toggling) return;
    toggling = true;

    // Optimistic update
    const wasGz = userGz;
    userGz = !userGz;
    count += userGz ? 1 : -1;

    try {
      const res = await fetch(`/api/globals/${globalId}/gz`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        count = data.gz_count;
        userGz = data.user_gz;
      } else {
        // Revert
        userGz = wasGz;
        count += wasGz ? 1 : -1;
      }
    } catch {
      userGz = wasGz;
      count += wasGz ? 1 : -1;
    } finally {
      toggling = false;
    }
  }
</script>

<button
  class="gz-btn"
  class:gz-active={userGz}
  class:gz-compact={compact}
  class:gz-disabled={!user}
  title={user ? (userGz ? 'Remove GZ' : 'GZ! (Congrats)') : 'Log in to GZ'}
  onclick={(e) => { e.stopPropagation(); toggle(); }}
  disabled={!user || toggling}
>
  <span class="gz-label">GZ</span>
  {#if count > 0}
    <span class="gz-count">{count}</span>
  {/if}
</button>

<style>
  .gz-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.1);
    color: var(--text-muted);
    font-size: 0.6875rem;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
    letter-spacing: 0.3px;
  }

  .gz-btn:hover:not(:disabled) {
    border-color: var(--color-gold);
    color: var(--color-gold);
  }

  .gz-active {
    background: color-mix(in srgb, var(--color-gold) 15%, transparent);
    border-color: color-mix(in srgb, var(--color-gold) 40%, transparent);
    color: var(--color-gold);
  }

  .gz-compact {
    padding: 1px 5px;
    font-size: 0.625rem;
    gap: 3px;
  }

  .gz-disabled {
    cursor: default;
    opacity: 0.5;
  }

  .gz-count {
    font-variant-numeric: tabular-nums;
    display: none;
  }

  .gz-btn:hover .gz-count {
    display: inline;
  }
</style>
