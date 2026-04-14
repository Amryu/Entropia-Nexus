<!--
  @component ConsentBanner
  Cookie consent banner. Essential cookies are always on; analytics
  (Google Analytics) is opt-in. Uses neutral class names to avoid adblocker filter lists.
-->
<script>
  import { hasDecision, grantAll, denyAll } from '$lib/stores/consent.svelte.js';
  import { browser } from '$app/environment';

  let visible = $derived(browser && !hasDecision());

  function handleEssential() {
    denyAll();
  }

  function handleAllow() {
    grantAll();
  }
</script>

{#if visible}
  <div class="site-notice" role="dialog" aria-label="Cookie preferences">
    <div class="site-notice-inner">
      <div class="site-notice-content">
        <p class="site-notice-text">
          <strong class="site-notice-highlight">Your privacy matters.</strong>
          Entropia Nexus uses Google Analytics to collect anonymous usage data that helps us
          improve the site. No personalized advertising or tracking cookies are used.
          You can accept analytics or stick with essential cookies only.
          <a href="/legal/privacy" class="site-notice-link">Privacy Policy</a>
        </p>

        <div class="site-notice-actions">
          <button class="site-notice-btn site-notice-btn-allow" onclick={handleAllow}>
            Accept Analytics
          </button>
          <button class="site-notice-btn site-notice-btn-essential" onclick={handleEssential}>
            Essential Only
          </button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .site-notice {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 10001;
    background: var(--secondary-color);
    border-top: 1px solid var(--border-color);
    box-shadow: 0 -2px 12px rgba(0, 0, 0, 0.2);
    animation: site-notice-slide-up 0.3s ease;
  }

  @keyframes site-notice-slide-up {
    from { transform: translateY(100%); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  .site-notice-inner {
    max-width: 960px;
    margin: 0 auto;
    padding: 14px 20px;
  }

  .site-notice-content {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .site-notice-text {
    margin: 0;
    font-size: 0.8125rem;
    line-height: 1.5;
    color: var(--text-color);
  }

  .site-notice-highlight {
    color: var(--accent-color);
  }

  .site-notice-link {
    color: var(--accent-color) !important;
    text-decoration: underline !important;
  }

  .site-notice-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .site-notice-btn {
    padding: 7px 16px;
    border-radius: 6px;
    font-size: 0.8125rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: opacity 0.15s, background 0.15s;
    white-space: nowrap;
  }

  .site-notice-btn:hover {
    opacity: 0.9;
  }

  .site-notice-btn-essential,
  .site-notice-btn-allow {
    background: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }

  .site-notice-btn-essential:hover,
  .site-notice-btn-allow:hover {
    background: var(--border-color);
  }

  @media (max-width: 599px) {
    .site-notice-inner {
      padding: 12px 14px;
    }

    .site-notice-actions {
      flex-direction: column;
    }

    .site-notice-btn {
      text-align: center;
    }
  }
</style>
