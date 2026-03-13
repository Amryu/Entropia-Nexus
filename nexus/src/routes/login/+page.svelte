<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { dev } from '$app/environment';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';

  let { data } = $props();

  // Get redirect URL from query params
  let redirectUrl = $derived($page.url.searchParams.get('redirect') || '/');
  let allowTestPicker = ($derived(dev || data.isTestMode));

  // Test users available in dev/test mode
  const testUsers = [
    { id: 'verified1', name: 'Test User One', type: 'Verified', icon: '✓' },
    { id: 'verified2', name: 'Test User Two', type: 'Verified', icon: '✓' },
    { id: 'verified3', name: 'Test User Three', type: 'Verified', icon: '✓' },
    { id: 'unverified1', name: 'Unverified User One', type: 'Unverified', icon: '○' },
    { id: 'unverified2', name: 'Unverified User Two', type: 'Unverified', icon: '○' },
    { id: 'unverified3', name: 'Unverified User Three', type: 'Unverified', icon: '○' },
    { id: 'admin', name: 'Admin User', type: 'Admin', icon: '★' }
  ];

  let isLoggingIn = $state(false);
  let errorMessage = $state('');

  async function loginAsTestUser(userId: string) {
    if (isLoggingIn) return;
    isLoggingIn = true;
    errorMessage = '';

    try {
      const response = await fetch('/api/test/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Login failed');
      }

      // Redirect to the intended page
      window.location.href = redirectUrl;
    } catch (err) {
      errorMessage = err.message;
      isLoggingIn = false;
    }
  }

  function loginWithDiscord() {
    const discordUrl = `/discord/login${redirectUrl !== '/' ? `?redirect=${encodeURIComponent(redirectUrl)}` : ''}`;
    window.location.href = discordUrl;
  }

  onMount(() => {
    if (!allowTestPicker) {
      loginWithDiscord();
    }
  });
</script>

<svelte:head>
  <title>Login | Entropia Nexus</title>
</svelte:head>

<div class="login-page">
  <div class="login-container">
    <h1 class="login-title">Login to Entropia Nexus</h1>

    {#if errorMessage}
      <div class="error-banner">
        {errorMessage}
      </div>
    {/if}

    <div class="login-section">
      <button class="discord-btn" onclick={loginWithDiscord} disabled={isLoggingIn}>
        <svg class="discord-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
        </svg>
        Continue with Discord
      </button>
    </div>

    {#if allowTestPicker}
      <div class="divider">
        <span>Development Mode</span>
      </div>

      <div class="test-users-section">
        <h2>Login as Test User</h2>
        <p class="test-users-note">These accounts are only available in development/test mode.</p>

        <div class="test-users-grid">
          {#each testUsers as user}
            <button
              class="test-user-btn"
              class:verified={user.type === 'Verified'}
              class:unverified={user.type === 'Unverified'}
              class:admin={user.type === 'Admin'}
              onclick={() => loginAsTestUser(user.id)}
              disabled={isLoggingIn}
            >
              <span class="user-icon">{user.icon}</span>
              <span class="user-name">{user.name}</span>
              <span class="user-type">{user.type}</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .login-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100%;
    padding: 20px;
    box-sizing: border-box;
    background-color: var(--primary-color);
  }

  .login-container {
    width: 100%;
    max-width: 500px;
    padding: 40px;
    background-color: var(--secondary-color);
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  }

  .login-title {
    font-size: 24px;
    text-align: center;
    margin: 0 0 24px 0;
    color: var(--text-color);
  }

  .error-banner {
    background-color: var(--error-bg);
    color: var(--error-color);
    padding: 12px 16px;
    border-radius: 6px;
    margin-bottom: 20px;
    text-align: center;
  }

  .login-section {
    margin-bottom: 20px;
  }

  .discord-btn {
    width: 100%;
    padding: 14px 20px;
    background-color: #5865F2;
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    transition: background-color 0.2s;
  }

  .discord-btn:hover:not(:disabled) {
    background-color: #4752C4;
  }

  .discord-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .discord-icon {
    width: 24px;
    height: 24px;
  }

  .divider {
    display: flex;
    align-items: center;
    margin: 24px 0;
    color: var(--text-muted);
    font-size: 12px;
    text-transform: uppercase;
  }

  .divider::before,
  .divider::after {
    content: '';
    flex: 1;
    border-bottom: 1px solid var(--border-color);
  }

  .divider span {
    padding: 0 12px;
  }

  .test-users-section h2 {
    font-size: 16px;
    margin: 0 0 8px 0;
    color: var(--text-color);
  }

  .test-users-note {
    font-size: 12px;
    color: var(--text-muted);
    margin: 0 0 16px 0;
  }

  .test-users-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .test-user-btn {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background-color: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.2s;
    text-align: left;
  }

  .test-user-btn:hover:not(:disabled) {
    background-color: var(--disabled-color);
    border-color: var(--border-hover);
  }

  .test-user-btn:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }

  .test-user-btn.verified .user-icon {
    color: var(--success-color);
  }

  .test-user-btn.unverified .user-icon {
    color: var(--warning-color);
  }

  .test-user-btn.admin .user-icon {
    color: #fbbf24;
  }

  .user-icon {
    font-size: 18px;
    width: 24px;
    text-align: center;
  }

  .user-name {
    flex: 1;
    font-weight: 500;
  }

  .user-type {
    font-size: 12px;
    color: var(--text-muted);
    padding: 2px 8px;
    background-color: var(--secondary-color);
    border-radius: 4px;
  }

  .test-user-btn.admin .user-type {
    background-color: rgba(251, 191, 36, 0.2);
    color: #fbbf24;
  }
</style>
