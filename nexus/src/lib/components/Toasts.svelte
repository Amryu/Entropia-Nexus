<script>
  import { toasts, removeToast } from '$lib/stores/toasts.js';
  import { fly, fade } from 'svelte/transition';
</script>

{#if $toasts.length > 0}
  <div class="toast-container" aria-live="polite">
    {#each $toasts as toast (toast.id)}
      <div
        class="toast toast-{toast.type}"
        role="alert"
        in:fly={{ y: -30, duration: 200 }}
        out:fade={{ duration: 150 }}
      >
        <span class="toast-message">{toast.message}</span>
        <button class="toast-close" on:click={() => removeToast(toast.id)} aria-label="Dismiss">&times;</button>
      </div>
    {/each}
  </div>
{/if}

<style>
  .toast-container {
    position: fixed;
    top: 52px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 480px;
    width: calc(100% - 32px);
    pointer-events: none;
  }
  .toast {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 13px;
    line-height: 1.4;
    pointer-events: auto;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }
  .toast-error {
    background: var(--error-bg);
    color: var(--error-color);
    border: 1px solid var(--error-color);
  }
  .toast-warning {
    background: var(--warning-bg);
    color: var(--warning-color);
    border: 1px solid var(--warning-color);
  }
  .toast-success {
    background: var(--success-bg);
    color: var(--success-color);
    border: 1px solid var(--success-color);
  }
  .toast-info {
    background: var(--accent-color-bg);
    color: var(--accent-color);
    border: 1px solid var(--accent-color);
  }
  .toast-message {
    flex: 1;
  }
  .toast-close {
    background: none;
    border: none;
    color: inherit;
    font-size: 18px;
    cursor: pointer;
    padding: 0 2px;
    opacity: 0.7;
    line-height: 1;
    flex-shrink: 0;
  }
  .toast-close:hover {
    opacity: 1;
  }
</style>
