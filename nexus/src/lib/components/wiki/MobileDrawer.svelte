<!--
  @component MobileDrawer
  Slide-in drawer for mobile navigation.
  Includes backdrop overlay and swipe-to-close support.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { fly, fade } from 'svelte/transition';

  const dispatch = createEventDispatcher();

  /** @type {boolean} Whether drawer is open */
  export let open = false;

  /** @type {string} Side to slide from */
  export let side = 'left';

  function close() {
    open = false;
    dispatch('close');
  }

  function handleBackdropClick() {
    close();
  }

  function handleKeydown(event) {
    if (event.key === 'Escape') {
      close();
    }
  }

  // Swipe to close support
  let touchStartX = 0;
  let touchCurrentX = 0;
  let swiping = false;

  function handleTouchStart(event) {
    touchStartX = event.touches[0].clientX;
    touchCurrentX = event.touches[0].clientX; // Initialize to same position so taps don't trigger swipe
    swiping = true;
  }

  function handleTouchMove(event) {
    if (!swiping) return;
    touchCurrentX = event.touches[0].clientX;
  }

  function handleTouchEnd() {
    if (!swiping) return;

    const diff = touchStartX - touchCurrentX;
    const threshold = 50;

    if (side === 'left' && diff > threshold) {
      close();
    } else if (side === 'right' && diff < -threshold) {
      close();
    }

    swiping = false;
    touchStartX = 0;
    touchCurrentX = 0;
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
  <div class="drawer-overlay" transition:fade={{ duration: 200 }}>
    <button
      class="backdrop"
      on:click={handleBackdropClick}
      aria-label="Close navigation"
    />

    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
    <aside
      class="drawer drawer-{side}"
      transition:fly={{ x: side === 'left' ? -300 : 300, duration: 250 }}
      on:touchstart={handleTouchStart}
      on:touchmove={handleTouchMove}
      on:touchend={handleTouchEnd}
      on:click|stopPropagation
      role="dialog"
      aria-modal="true"
      aria-label="Navigation"
    >
      <div class="drawer-header">
        <button class="close-btn" on:click={close} aria-label="Close">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="drawer-content">
        <slot />
      </div>
    </aside>
  </div>
{/if}

<style>
  .drawer-overlay {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
  }

  .backdrop {
    position: absolute;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.5);
    border: none;
    cursor: pointer;
    z-index: 0;
  }

  .drawer {
    position: relative;
    z-index: 1;
    width: 85%;
    max-width: 320px;
    height: 100%;
    background-color: var(--secondary-color);
    display: flex;
    flex-direction: column;
    box-shadow: 2px 0 10px rgba(0, 0, 0, 0.3);
  }

  .drawer-left {
    /* Default - left side */
  }

  .drawer-right {
    margin-left: auto;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.3);
  }

  .drawer-header {
    display: flex;
    justify-content: flex-end;
    padding: 8px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .close-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    padding: 0;
    background: transparent;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    border-radius: 4px;
  }

  .close-btn:hover {
    background-color: var(--hover-color);
  }

  .drawer-content {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
  }
</style>
