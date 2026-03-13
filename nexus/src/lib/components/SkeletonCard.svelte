<script lang="ts">
  
  interface Props {
    /**
   * Skeleton card for service/request cards
   */
    count?: number;
  }

  let { count = 3 }: Props = $props();
</script>

<div class="skeleton-cards">
  {#each Array(count) as _}
    <div class="skeleton-card">
      <div class="skeleton-card-header">
        <div class="skeleton-bar title"></div>
        <div class="skeleton-bar badge"></div>
      </div>
      <div class="skeleton-card-body">
        <div class="skeleton-bar subtitle"></div>
        <div class="skeleton-card-meta">
          <div class="skeleton-bar meta"></div>
          <div class="skeleton-bar meta"></div>
        </div>
      </div>
    </div>
  {/each}
</div>

<style>
  .skeleton-cards {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .skeleton-card {
    border: 1px solid var(--border-color, #333);
    border-radius: 8px;
    padding: 1rem;
    background: var(--secondary-color, #1a1a1a);
  }

  .skeleton-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }

  .skeleton-card-body {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .skeleton-card-meta {
    display: flex;
    gap: 1rem;
  }

  .skeleton-bar {
    border-radius: 4px;
    position: relative;
    overflow: hidden;
    background: var(--skeleton-bg, #2a2a2a);
  }

  .skeleton-bar::after {
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

  .skeleton-bar.title {
    width: 40%;
    height: 1.25rem;
  }

  .skeleton-bar.badge {
    width: 60px;
    height: 1.5rem;
    border-radius: 9999px;
  }

  .skeleton-bar.subtitle {
    width: 60%;
    height: 0.9rem;
  }

  .skeleton-bar.meta {
    width: 80px;
    height: 0.85rem;
  }

  /* Light mode support */
  :global([data-theme="light"]) .skeleton-card {
    background: #fff;
    border-color: #e5e5e5;
  }

  :global([data-theme="light"]) .skeleton-bar {
    background: #e5e5e5;
  }

  :global([data-theme="light"]) .skeleton-bar::after {
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.5),
      transparent
    );
  }
</style>
