<!--
  @component ConsentBanner
  GDPR-compliant cookie consent banner with three options:
  Essential Only, Allow All, or granular Settings toggle.
  Uses neutral class names to avoid adblocker filter lists.
-->
<script>
  import { hasDecision, grantAll, denyAll, saveConsent } from '$lib/stores/consent.svelte.js';
  import { browser } from '$app/environment';

  let showSettings = $state(false);
  let adsToggle = $state(false);
  let analyticsToggle = $state(false);

  let visible = $derived(browser && !hasDecision());

  function handleEssential() {
    denyAll();
  }

  function handleAllow() {
    grantAll();
  }

  function toggleSettings() {
    showSettings = !showSettings;
  }

  function handleSave() {
    saveConsent({ ads: adsToggle, analytics: analyticsToggle });
  }
</script>

{#if visible}
  <div class="site-notice" role="dialog" aria-label="Cookie preferences">
    <div class="site-notice-inner">
      <div class="site-notice-content">
        <p class="site-notice-text">
          <strong class="site-notice-highlight">Your privacy matters.</strong>
          We use cookies for analytics and personalized ads. Analytics help us improve the site,
          and ads keep Entropia Nexus free. You can accept all, decline non-essential cookies,
          or customize your preferences.
          <a href="/legal/privacy" class="site-notice-link">Privacy Policy</a>
        </p>

        {#if showSettings}
          <div class="site-notice-settings">
            <label class="site-notice-toggle">
              <span class="site-notice-toggle-info">
                <strong>Essential</strong>
                <span class="site-notice-toggle-desc">Required for the site to function - session authentication and viewport preference</span>
              </span>
              <input type="checkbox" checked disabled />
              <span class="site-notice-switch site-notice-switch-locked"></span>
            </label>
            <label class="site-notice-toggle">
              <span class="site-notice-toggle-info">
                <strong>Analytics</strong>
                <span class="site-notice-toggle-desc">Google Analytics - anonymous usage data to help us improve the site</span>
              </span>
              <input type="checkbox" bind:checked={analyticsToggle} />
              <span class="site-notice-switch" class:site-notice-switch-on={analyticsToggle}></span>
            </label>
            <label class="site-notice-toggle">
              <span class="site-notice-toggle-info">
                <strong>Advertising</strong>
                <span class="site-notice-toggle-desc">Google AdSense - personalized ads and tracking cookies</span>
              </span>
              <input type="checkbox" bind:checked={adsToggle} />
              <span class="site-notice-switch" class:site-notice-switch-on={adsToggle}></span>
            </label>
            <button class="site-notice-btn site-notice-btn-save" onclick={handleSave}>
              Save Preferences
            </button>
          </div>
        {:else}
          <div class="site-notice-actions">
            <button class="site-notice-btn site-notice-btn-allow" onclick={handleAllow}>
              Accept All
            </button>
            <button class="site-notice-btn site-notice-btn-essential" onclick={handleEssential}>
              Essential Only
            </button>
            <button class="site-notice-btn site-notice-btn-settings" onclick={toggleSettings}>
              Settings
            </button>
          </div>
        {/if}
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

  .site-notice-btn-settings {
    background: none;
    color: var(--text-muted);
    padding: 7px 12px;
  }

  .site-notice-btn-settings:hover {
    color: var(--text-color);
  }

  .site-notice-btn-save {
    background: var(--accent-color);
    color: #fff;
    align-self: flex-start;
  }

  /* Granular settings panel */
  .site-notice-settings {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .site-notice-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 12px;
    border-radius: 6px;
    background: var(--primary-color);
    cursor: pointer;
  }

  .site-notice-toggle-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 0.8125rem;
    color: var(--text-color);
  }

  .site-notice-toggle-desc {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .site-notice-toggle input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .site-notice-switch {
    position: relative;
    width: 36px;
    height: 20px;
    min-width: 36px;
    border-radius: 10px;
    background: var(--border-color);
    transition: background 0.2s;
  }

  .site-notice-switch::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--text-muted);
    transition: transform 0.2s, background 0.2s;
  }

  .site-notice-switch-on {
    background: var(--accent-color);
  }

  .site-notice-switch-on::after {
    transform: translateX(16px);
    background: #fff;
  }

  .site-notice-switch-locked {
    background: var(--accent-color);
    opacity: 0.5;
    cursor: not-allowed;
  }

  .site-notice-switch-locked::after {
    transform: translateX(16px);
    background: #fff;
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
