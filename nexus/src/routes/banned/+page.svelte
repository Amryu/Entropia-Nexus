<script>
  // @ts-nocheck
</script>

<svelte:head>
  <title>Account Banned | Entropia Nexus</title>
</svelte:head>

<style>
  .banned-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: 20px;
    box-sizing: border-box;
  }

  .banned-container {
    background-color: var(--secondary-color);
    border: 1px solid var(--error-color);
    border-radius: 12px;
    padding: 40px;
    max-width: 500px;
    text-align: center;
  }

  .banned-icon {
    font-size: 64px;
    margin-bottom: 16px;
  }

  .banned-title {
    font-size: 28px;
    font-weight: bold;
    color: var(--error-color);
    margin: 0 0 16px 0;
  }

  .banned-message {
    color: var(--text-color);
    font-size: 16px;
    line-height: 1.6;
    margin: 0 0 24px 0;
  }

  .banned-contact {
    color: var(--text-muted);
    font-size: 14px;
    margin: 0;
  }

  .banned-contact a {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .banned-contact a:hover {
    color: var(--accent-color-hover);
  }
</style>

<div class="banned-page">
  <div class="banned-container">
    <div class="banned-icon">🚫</div>
    <h1 class="banned-title">Account Banned</h1>
    <p class="banned-message">
      Your account has been suspended from Entropia Nexus.
      You are no longer able to access the platform.
    </p>
    <p class="banned-contact">
      If you believe this is a mistake, please contact us on
      <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener">Discord</a>.
    </p>
  </div>
</div>
