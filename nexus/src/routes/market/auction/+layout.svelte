<script lang="ts">
  import { navigating } from '$app/stores';
  import { fade } from 'svelte/transition';
  interface Props {
    children?: import('svelte').Snippet;
  }

  let { children }: Props = $props();
</script>

{#if $navigating}
  <div class="loading-bar" transition:fade={{ duration: 150 }}>
    <div class="loading-progress"></div>
  </div>
{/if}

{@render children?.()}

<style>
  .loading-bar {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: color-mix(in srgb, var(--accent-color) 20%, transparent);
    z-index: 9999;
    overflow: hidden;
  }

  .loading-progress {
    height: 100%;
    width: 30%;
    background: var(--accent-color, #4a9eff);
    animation: loading 1s ease-in-out infinite;
  }

  @keyframes loading {
    0% { transform: translateX(-100%); }
    50% { transform: translateX(200%); }
    100% { transform: translateX(400%); }
  }
</style>
