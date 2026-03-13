<script>
  import { page } from '$app/stores';

  

  

  
  /**
   * @typedef {Object} Props
   * @property {{ verified?: boolean } | null} [user]
   * @property {string} [label] - Button label text (e.g. "Login to create service")
   * @property {string} [createUrl] - URL to redirect to after login (e.g. "/market/services/create")
   */

  /** @type {Props} */
  let { user = null, label = 'Login to create', createUrl = '' } = $props();

  let showDialog = $state(false);

  let needsAuth = $derived(!user);
  let needsVerification = $derived(user && !user.verified);
  let visible = $derived(needsAuth || needsVerification);

  let loginUrl = $derived(`/discord/login?redirect=${encodeURIComponent(createUrl || $page.url.pathname)}`);

  function openDialog() {
    showDialog = true;
  }

  function closeDialog() {
    showDialog = false;
  }
</script>

{#if visible}
  <button class="auth-hint-btn" onclick={openDialog} title={needsAuth ? 'Login required' : 'Verification required'}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
    <span>{needsAuth ? label : label.replace(/^Login/, 'Verify')}</span>
  </button>
{/if}

{#if showDialog}
  <div class="dialog-overlay" role="presentation" onclick={closeDialog} onkeydown={(e) => e.key === 'Escape' && closeDialog()}>
    <div class="dialog-content" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-modal="true" aria-labelledby="auth-dialog-title">
      <button class="dialog-close" onclick={closeDialog} aria-label="Close">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>

      <h2 id="auth-dialog-title" class="dialog-title">
        {needsAuth ? 'Login Required' : 'Verification Required'}
      </h2>

      {#if needsAuth}
        <div class="dialog-body">
          <p>To create marketplace listings, you need to log in and verify your account.</p>

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
            <a href={loginUrl} class="dialog-btn primary">Login with Discord</a>
            <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="dialog-btn secondary">Join Discord Server</a>
          </div>
        </div>
      {:else}
        <div class="dialog-body">
          <p>Your account needs to be verified before you can create marketplace listings.</p>

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
            <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="dialog-btn primary">Join Discord Server</a>
            <button class="dialog-btn secondary" onclick={closeDialog}>Close</button>
          </div>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .auth-hint-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    transition: all 0.15s;
    max-height: 32px;
    box-sizing: border-box;
  }

  .auth-hint-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  .dialog-overlay {
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

  .dialog-content {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 12px;
    max-width: 500px;
    width: 100%;
    max-height: 90vh;
    overflow-y: auto;
    position: relative;
    padding: 24px;
    box-sizing: border-box;
  }

  .dialog-close {
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

  .dialog-close:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .dialog-title {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-color);
    margin: 0 0 16px 0;
    padding-right: 32px;
  }

  .dialog-body {
    color: var(--text-color);
  }

  .dialog-body > p {
    margin: 0 0 20px 0;
    color: var(--text-muted, #999);
    line-height: 1.5;
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
  }

  .dialog-btn {
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
  }

  .dialog-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .dialog-btn.primary:hover {
    filter: brightness(1.1);
  }

  .dialog-btn.secondary {
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
  }

  .dialog-btn.secondary:hover {
    background-color: var(--hover-color);
  }
</style>
