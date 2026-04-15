<!--
  @component ContributeDialog
  Shared auth-aware dialog shown when a visitor clicks a ContributeCTA or
  MissingFieldCTA. Branches on the viewer's auth state:
    - not logged in  -> Discord login steps + bounty pitch
    - unverified     -> verification steps + bounty pitch
    - verified       -> "Start editing" primary that calls onContribute
-->
<script>
  // @ts-nocheck
  import { page } from '$app/stores';
  import { categoryLabel } from './contributeCategories.js';

  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {string} [field] - specific missing field name (optional)
   * @property {string} [category] - contribution category
   * @property {() => void} [onclose]
   * @property {() => void} [onContribute] - called for verified users when they click "Start editing"
   */

  /** @type {Props} */
  let {
    show = false,
    field = '',
    category = 'general',
    onclose,
    onContribute,
  } = $props();

  let user = $derived($page.data?.session?.user);
  let isLoggedIn = $derived(!!user);
  let isVerified = $derived(!!user?.verified);

  let loginUrl = $derived(
    `/discord/login?redirect=${encodeURIComponent(($page.url.pathname || '/') + ($page.url.search || ''))}`
  );

  let thing = $derived(field ? `**${field}**` : categoryLabel(category));

  function close() {
    onclose?.();
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) close();
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') close();
  }

  function handleStartEditing() {
    close();
    onContribute?.();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if show}
  <div
    class="contribute-dialog-overlay"
    role="presentation"
    onclick={handleBackdropClick}
  >
    <div
      class="contribute-dialog-content"
      role="dialog"
      tabindex="-1"
      aria-modal="true"
      aria-labelledby="contribute-dialog-title"
      onclick={(e) => e.stopPropagation()}
      onkeydown={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        class="contribute-dialog-close"
        onclick={close}
        aria-label="Close"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>

      {#if !isLoggedIn}
        <h3 id="contribute-dialog-title" class="contribute-dialog-title">Help build the wiki</h3>
        <div class="contribute-dialog-body">
          <p>
            {#if field}
              You noticed <strong>{field}</strong> is missing. You can fill it in and earn PED through our bounty program.
            {:else}
              You spotted missing {categoryLabel(category)}. You can help fill it in and earn PED through our bounty program.
            {/if}
          </p>
          <p class="bounty-note">
            Approved wiki contributions earn PED through our bounty program - the more data you add, the more you earn.
          </p>

          <div class="auth-steps">
            <div class="auth-step">
              <span class="step-number">1</span>
              <div class="step-content">
                <strong>Login with Discord</strong>
                <p>Click the button below to log in using your Discord account.</p>
              </div>
            </div>
            <div class="auth-step">
              <span class="step-number">2</span>
              <div class="step-content">
                <strong>Join our Discord Server</strong>
                <p>After logging in, join the Entropia Nexus Discord server if you haven't already.</p>
              </div>
            </div>
            <div class="auth-step">
              <span class="step-number">3</span>
              <div class="step-content">
                <strong>Complete Verification</strong>
                <p>A verification thread will automatically open (may take up to 5 minutes). Follow the instructions to verify your Entropia Universe character.</p>
              </div>
            </div>
          </div>

          <div class="dialog-actions">
            <a href={loginUrl} class="contribute-btn primary">Login with Discord</a>
            <a href="/bounties" class="contribute-btn secondary" onclick={close}>Learn about bounties</a>
          </div>
        </div>
      {:else if !isVerified}
        <h3 id="contribute-dialog-title" class="contribute-dialog-title">Verify to contribute</h3>
        <div class="contribute-dialog-body">
          <p>
            {#if field}
              Your account needs verification before you can add <strong>{field}</strong> (or any other wiki data).
            {:else}
              Your account needs verification before you can edit wiki entries.
            {/if}
          </p>
          <p class="bounty-note">
            Once verified, approved contributions earn PED through our bounty program.
          </p>

          <div class="auth-steps">
            <div class="auth-step">
              <span class="step-number">1</span>
              <div class="step-content">
                <strong>Join our Discord Server</strong>
                <p>Make sure you've joined the Entropia Nexus Discord server.</p>
              </div>
            </div>
            <div class="auth-step">
              <span class="step-number">2</span>
              <div class="step-content">
                <strong>Wait for Verification Thread</strong>
                <p>A verification thread will automatically open in your Discord DMs or in a private channel. This may take up to 5 minutes after joining.</p>
              </div>
            </div>
            <div class="auth-step">
              <span class="step-number">3</span>
              <div class="step-content">
                <strong>Follow Verification Instructions</strong>
                <p>Respond to the verification thread with the requested information about your Entropia Universe character.</p>
              </div>
            </div>
          </div>

          <div class="dialog-actions">
            <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="contribute-btn primary">Join Discord Server</a>
            <a href="/bounties" class="contribute-btn secondary" onclick={close}>Learn about bounties</a>
          </div>
        </div>
      {:else}
        <h3 id="contribute-dialog-title" class="contribute-dialog-title">Contribute missing data</h3>
        <div class="contribute-dialog-body">
          <p>
            {#if field}
              Click <strong>Start editing</strong> to add <strong>{field}</strong> to this page.
            {:else}
              Click <strong>Start editing</strong> to fill in the missing {categoryLabel(category)}.
            {/if}
          </p>
          <p class="bounty-note">
            Approved contributions count toward the bounty program - your submissions earn PED once reviewed.
          </p>

          <div class="dialog-actions">
            {#if onContribute}
              <button type="button" class="contribute-btn primary" onclick={handleStartEditing}>Start editing</button>
            {:else}
              <p class="edit-hint">Use the <strong>Edit</strong> button at the top of the page to start editing.</p>
            {/if}
            <a href="/bounties" class="contribute-btn secondary" onclick={close}>View bounty program</a>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .contribute-dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
    box-sizing: border-box;
  }

  .contribute-dialog-content {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 12px;
    max-width: 520px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    position: relative;
    padding: 24px;
    box-sizing: border-box;
    color: var(--text-color);
  }

  .contribute-dialog-close {
    position: absolute;
    top: 12px;
    right: 12px;
    background: transparent;
    border: none;
    color: var(--text-muted, #999);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    transition: all 0.15s;
  }

  .contribute-dialog-close:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .contribute-dialog-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0 0 16px 0;
    padding-right: 32px;
  }

  .contribute-dialog-body > p {
    margin: 0 0 12px 0;
    color: var(--text-muted, #999);
    line-height: 1.5;
  }

  .contribute-dialog-body > p.bounty-note {
    margin-bottom: 20px;
    font-size: 13px;
    padding: 10px 12px;
    background-color: var(--hover-color);
    border-left: 3px solid var(--accent-color, #4a9eff);
    border-radius: 4px;
    color: var(--text-color);
  }

  .auth-steps {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 24px;
  }

  .auth-step {
    display: flex;
    gap: 12px;
    align-items: flex-start;
  }

  .step-number {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 50%;
    font-size: 14px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .step-content {
    flex: 1;
    min-width: 0;
  }

  .step-content strong {
    display: block;
    color: var(--text-color);
    margin-bottom: 4px;
  }

  .step-content p {
    margin: 0;
    font-size: 13px;
    color: var(--text-muted, #999);
    line-height: 1.4;
  }

  .dialog-actions {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: center;
  }

  .contribute-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s;
    border: none;
    font-family: inherit;
  }

  .contribute-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .contribute-btn.primary:hover {
    filter: brightness(1.1);
  }

  .contribute-btn.secondary {
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .contribute-btn.secondary:hover {
    background-color: var(--hover-color);
  }

  .edit-hint {
    margin: 0;
    font-size: 13px;
    color: var(--text-muted, #999);
  }
</style>
