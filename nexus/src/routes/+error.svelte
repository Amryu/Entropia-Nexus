<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';


  function getDefaultMessage(status: number): string {
    switch (status) {
      case 400:
        return 'Bad Request';
      case 401:
        return 'You must be logged in to access this page.';
      case 403:
        return 'You do not have permission to access this page.';
      case 404:
        return 'The page you are looking for does not exist.';
      case 500:
        return 'Something went wrong on our end. Please try again later.';
      default:
        return 'An unexpected error occurred.';
    }
  }

  function getTitle(status: number): string {
    switch (status) {
      case 400:
        return 'Bad Request';
      case 401:
        return 'Unauthorized';
      case 403:
        return 'Access Denied';
      case 404:
        return 'Page Not Found';
      case 500:
        return 'Server Error';
      default:
        return 'Error';
    }
  }

  function getIcon(status: number): string {
    switch (status) {
      case 401:
      case 403:
        return '🔒';
      case 404:
        return '🔍';
      case 500:
        return '⚠';
      default:
        return '❌';
    }
  }

  function goBack() {
    if (typeof window !== 'undefined' && window.history.length > 1) {
      window.history.back();
    } else {
      goto('/');
    }
  }

  function goHome() {
    goto('/');
  }
  let status = $derived($page.status);
  let message = $derived($page.error?.message || getDefaultMessage(status));
</script>

<svelte:head>
  <title>{status} - {getTitle(status)} | Entropia Nexus</title>
</svelte:head>

<div class="error-page">
  <div class="error-container">
    <div class="error-icon">{getIcon(status)}</div>
    <h1 class="error-status">{status}</h1>
    <h2 class="error-title">{getTitle(status)}</h2>
    <p class="error-message">{message}</p>

    <div class="error-actions">
      <button class="btn btn-primary" onclick={goBack}>
        Go Back
      </button>
      <button class="btn btn-secondary" onclick={goHome}>
        Go to Homepage
      </button>
    </div>

    {#if status === 401}
      <div class="login-hint">
        <p>Please <a href="/discord">log in with Discord</a> to continue.</p>
      </div>
    {/if}

    {#if status === 403}
      <div class="verify-hint">
        <p class="verify-main">This area requires a verified account.</p>
        <p class="verify-explanation">
          Verification confirms your Entropia Universe character and unlocks all site features including the marketplace, service listings, and more.
        </p>
        <a href="/account/setup" class="btn btn-verify">
          Verify Your Account
        </a>
        <p class="verify-discord">
          Need help? Join our <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener">Discord server</a> for assistance.
        </p>
      </div>
    {/if}
  </div>
</div>

<style>
  .error-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: 20px;
    box-sizing: border-box;
    background-color: var(--primary-color);
  }

  .error-container {
    text-align: center;
    max-width: 500px;
    padding: 40px;
    background-color: var(--secondary-color);
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  }

  .error-icon {
    font-size: 64px;
    margin-bottom: 16px;
  }

  .error-status {
    font-size: 72px;
    font-weight: bold;
    color: var(--accent-color);
    margin: 0;
    line-height: 1;
  }

  .error-title {
    font-size: 24px;
    color: var(--text-color);
    margin: 16px 0;
  }

  .error-message {
    font-size: 16px;
    color: var(--text-muted);
    margin-bottom: 32px;
    line-height: 1.5;
  }

  .error-actions {
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
  }

  .btn {
    padding: 12px 24px;
    border-radius: 6px;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    transition: all 0.2s ease;
  }

  .btn-primary {
    background-color: var(--accent-color);
    color: white;
  }

  .btn-primary:hover {
    background-color: var(--accent-color-hover);
    transform: translateY(-1px);
  }

  .btn-secondary {
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }

  .btn-secondary:hover {
    background-color: var(--disabled-color);
    transform: translateY(-1px);
  }

  .login-hint, .verify-hint {
    margin-top: 24px;
    padding-top: 24px;
    border-top: 1px solid var(--border-color);
  }

  .login-hint p {
    color: var(--text-muted);
    font-size: 14px;
    margin: 0;
  }

  .verify-hint {
    text-align: center;
  }

  .verify-main {
    color: var(--text-color);
    font-size: 16px;
    font-weight: 500;
    margin: 0 0 8px 0;
  }

  .verify-explanation {
    color: var(--text-muted);
    font-size: 14px;
    margin: 0 0 20px 0;
    line-height: 1.5;
  }

  .btn-verify {
    display: inline-block;
    background-color: var(--success-color);
    color: white;
    text-decoration: none;
    margin-bottom: 16px;
  }

  .btn-verify:hover {
    filter: brightness(1.1);
    transform: translateY(-1px);
  }

  .verify-discord {
    color: var(--text-muted);
    font-size: 13px;
    margin: 0;
  }

  .verify-discord a {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .verify-discord a:hover {
    color: var(--accent-color-hover);
  }

  .login-hint a {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .login-hint a:hover {
    color: var(--accent-color-hover);
  }
</style>
