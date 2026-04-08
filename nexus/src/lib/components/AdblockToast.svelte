<!--
  @component AdblockToast
  Small branded toast (bottom-right) shown when an adblocker is detected.
  Dismissible for 14 days via localStorage timestamp.
  Only appears after the consent banner has been dismissed.
-->
<script>
  import { browser } from '$app/environment';
  import { getRevenueBlocked, getRevenueChecked, runRevenueCheck } from '$lib/stores/revenue-state.svelte.js';
  import { hasDecision } from '$lib/stores/consent.svelte.js';
  import { fly } from 'svelte/transition';

  const STORAGE_KEY = 'nexus.adblock-toast.dismissed';
  const DISMISS_DURATION_MS = 14 * 24 * 60 * 60 * 1000; // 14 days

  let manuallyDismissed = $state(false);

  // Run adblock check once on mount
  $effect(() => {
    if (browser && !getRevenueChecked()) {
      runRevenueCheck();
    }
  });

  function isDismissedRecently() {
    if (!browser) return true;
    try {
      const ts = localStorage.getItem(STORAGE_KEY);
      if (!ts) return false;
      return Date.now() - Number(ts) < DISMISS_DURATION_MS;
    } catch {
      return false;
    }
  }

  function dismiss() {
    manuallyDismissed = true;
    if (!browser) return;
    try {
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch {}
  }

  let visible = $derived(
    browser &&
    getRevenueChecked() &&
    getRevenueBlocked() &&
    hasDecision() &&
    !manuallyDismissed &&
    !isDismissedRecently()
  );
</script>

{#if visible}
  <div class="site-support-toast" role="status" transition:fly={{ y: 20, duration: 250 }}>
    <span class="site-support-icon">EN</span>
    <div class="site-support-body">
      <p class="site-support-text">
        Entropia Nexus is supported by ads. Consider disabling your ad blocker to help keep this resource free.
      </p>
      <button class="site-support-dismiss" onclick={dismiss}>Dismiss</button>
    </div>
  </div>
{/if}

<style>
  .site-support-toast {
    position: fixed;
    bottom: 16px;
    right: 16px;
    z-index: 9999;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    max-width: 340px;
    padding: 12px 14px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  }

  .site-support-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    min-width: 32px;
    border-radius: 6px;
    background-color: var(--primary-color);
    color: var(--accent-color);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .site-support-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .site-support-text {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.45;
    color: var(--text-color);
  }

  .site-support-dismiss {
    align-self: flex-end;
    padding: 4px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--hover-color);
    color: var(--text-muted);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }

  .site-support-dismiss:hover {
    color: var(--text-color);
    border-color: var(--text-muted);
  }

  @media (max-width: 599px) {
    .site-support-toast {
      right: 8px;
      bottom: 8px;
      left: 8px;
      max-width: none;
    }
  }
</style>
