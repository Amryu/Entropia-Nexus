<script lang="ts">
  /**
   * Skeleton loading placeholder component
   *
   * Props:
   * - variant: 'text' | 'circle' | 'rect' | 'card' - Shape of the skeleton
   * - width: string - CSS width (default: '100%')
   * - height: string - CSS height (default varies by variant)
   * - lines: number - Number of text lines (only for variant='text')
   * - animate: boolean - Whether to animate (default: true)
   */
  export let variant: 'text' | 'circle' | 'rect' | 'card' = 'text';
  export let width: string = '100%';
  export let height: string | null = null;
  export let lines: number = 1;
  export let animate: boolean = true;

  // Default heights based on variant
  $: defaultHeight = {
    text: '1rem',
    circle: '40px',
    rect: '100px',
    card: '120px'
  }[variant];

  $: actualHeight = height || defaultHeight;
</script>

{#if variant === 'text' && lines > 1}
  <div class="skeleton-lines" style="width: {width};">
    {#each Array(lines) as _, i}
      <div
        class="skeleton skeleton-text"
        class:animate
        style="width: {i === lines - 1 ? '70%' : '100%'}; height: {actualHeight};"
      ></div>
    {/each}
  </div>
{:else if variant === 'circle'}
  <div
    class="skeleton skeleton-circle"
    class:animate
    style="width: {width}; height: {width};"
  ></div>
{:else if variant === 'card'}
  <div
    class="skeleton skeleton-card"
    class:animate
    style="width: {width}; height: {actualHeight};"
  >
    <div class="skeleton-card-content">
      <div class="skeleton skeleton-text" style="width: 60%; height: 1.2rem;"></div>
      <div class="skeleton skeleton-text" style="width: 80%; height: 0.9rem;"></div>
      <div class="skeleton skeleton-text" style="width: 40%; height: 0.9rem;"></div>
    </div>
  </div>
{:else}
  <div
    class="skeleton skeleton-{variant}"
    class:animate
    style="width: {width}; height: {actualHeight};"
  ></div>
{/if}

<style>
  .skeleton {
    background: var(--skeleton-bg, #2a2a2a);
    border-radius: 4px;
    position: relative;
    overflow: hidden;
  }

  .skeleton.animate::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.08),
      transparent
    );
    animation: shimmer 1.5s infinite;
  }

  @keyframes shimmer {
    0% {
      transform: translateX(-100%);
    }
    100% {
      transform: translateX(100%);
    }
  }

  .skeleton-lines {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .skeleton-text {
    border-radius: 4px;
  }

  .skeleton-circle {
    border-radius: 50%;
  }

  .skeleton-rect {
    border-radius: 6px;
  }

  .skeleton-card {
    border-radius: 8px;
    padding: 1rem;
    border: 1px solid var(--border-color, #333);
  }

  .skeleton-card-content {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .skeleton-card .skeleton-text {
    background: var(--skeleton-inner-bg, #333);
  }

  /* Light mode support */
  :global([data-theme="light"]) .skeleton {
    background: #e5e5e5;
  }

  :global([data-theme="light"]) .skeleton.animate::after {
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.5),
      transparent
    );
  }

  :global([data-theme="light"]) .skeleton-card .skeleton-text {
    background: #d5d5d5;
  }
</style>
