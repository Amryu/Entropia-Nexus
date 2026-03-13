<script lang="ts">
  
  interface Props {
    /**
   * Skeleton table loading placeholder
   *
   * Props:
   * - rows: number - Number of skeleton rows to show
   * - columns: number - Number of columns
   * - rowHeight: number - Height of each row in px
   * - showHeader: boolean - Whether to show header skeleton
   */
    rows?: number;
    columns?: number;
    rowHeight?: number;
    showHeader?: boolean;
  }

  let {
    rows = 5,
    columns = 4,
    rowHeight = 48,
    showHeader = true
  }: Props = $props();
</script>

<div class="skeleton-table">
  {#if showHeader}
    <div class="skeleton-header">
      {#each Array(columns) as _, i}
        <div class="skeleton-cell header-cell" style="flex: {i === 0 ? 2 : 1};">
          <div class="skeleton-bar"></div>
        </div>
      {/each}
    </div>
  {/if}

  <div class="skeleton-body">
    {#each Array(rows) as _, rowIndex}
      <div class="skeleton-row" style="height: {rowHeight}px;">
        {#each Array(columns) as _, colIndex}
          <div class="skeleton-cell" style="flex: {colIndex === 0 ? 2 : 1};">
            <div
              class="skeleton-bar"
              style="width: {colIndex === 0 ? '70%' : `${60 + (rowIndex * 7 + colIndex * 13) % 30}%`};"
            ></div>
          </div>
        {/each}
      </div>
    {/each}
  </div>
</div>

<style>
  .skeleton-table {
    width: 100%;
    border: 1px solid var(--border-color, #333);
    border-radius: 6px;
    overflow: hidden;
    background: var(--secondary-color, #1a1a1a);
  }

  .skeleton-header {
    display: flex;
    background: var(--hover-color, #2a2a2a);
    border-bottom: 1px solid var(--border-color, #333);
    padding: 0.75rem 1rem;
  }

  .skeleton-body {
    display: flex;
    flex-direction: column;
  }

  .skeleton-row {
    display: flex;
    padding: 0 1rem;
    border-bottom: 1px solid var(--border-color, #333);
    align-items: center;
  }

  .skeleton-row:last-child {
    border-bottom: none;
  }

  .skeleton-cell {
    display: flex;
    align-items: center;
    padding: 0.5rem;
  }

  .header-cell .skeleton-bar {
    height: 0.9rem;
    background: var(--skeleton-header-bg, #3a3a3a);
  }

  .skeleton-bar {
    height: 0.85rem;
    background: var(--skeleton-bg, #2a2a2a);
    border-radius: 4px;
    position: relative;
    overflow: hidden;
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

  /* Light mode support */
  :global([data-theme="light"]) .skeleton-table {
    background: #fff;
    border-color: #e5e5e5;
  }

  :global([data-theme="light"]) .skeleton-header {
    background: #f5f5f5;
    border-color: #e5e5e5;
  }

  :global([data-theme="light"]) .skeleton-row {
    border-color: #e5e5e5;
  }

  :global([data-theme="light"]) .skeleton-bar {
    background: #e5e5e5;
  }

  :global([data-theme="light"]) .header-cell .skeleton-bar {
    background: #d5d5d5;
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
