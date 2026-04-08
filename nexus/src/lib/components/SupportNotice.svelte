<!--
  @component SupportNotice
  Small branded notice (bottom-right) shown when content delivery is blocked.
  Dismissible for 14 days via localStorage timestamp.
  Only appears after the consent banner has been dismissed.
-->
<script>
  import { browser } from '$app/environment';
  import { getContentBlocked, getContentChecked, runContentCheck } from '$lib/stores/feature-state.svelte.js';
  import { hasDecision } from '$lib/stores/consent.svelte.js';
  import { fly } from 'svelte/transition';

  const STORAGE_KEY = 'nexus.notice.ts';
  const DISMISS_DURATION_MS = 14 * 24 * 60 * 60 * 1000; // 14 days

  let manuallyDismissed = $state(false);

  // Run check once on mount
  $effect(() => {
    if (browser && !getContentChecked()) {
      runContentCheck();
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
    getContentChecked() &&
    getContentBlocked() &&
    hasDecision() &&
    !manuallyDismissed &&
    !isDismissedRecently()
  );
</script>

{#if visible}
  <div class="inline-notice" role="status" transition:fly={{ y: 20, duration: 250 }}>
    <span class="notice-icon">EN</span>
    <div class="notice-body">
      <p class="notice-text">
        Entropia Nexus is supported by ads. Consider disabling your ad blocker to help keep this resource free.
      </p>
      <button class="notice-action" onclick={dismiss}>Dismiss</button>
    </div>
  </div>
{/if}

<style>
  .inline-notice {
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

  .notice-icon {
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

  .notice-body {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .notice-text {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.45;
    color: var(--text-color);
  }

  .notice-action {
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

  .notice-action:hover {
    color: var(--text-color);
    border-color: var(--text-muted);
  }

  @media (max-width: 599px) {
    .inline-notice {
      right: 8px;
      bottom: 8px;
      left: 8px;
      max-width: none;
    }
  }
</style>
