<script>
  import { run } from 'svelte/legacy';

  import { onMount, onDestroy } from 'svelte';

  /**
   * @typedef {Object} Props
   * @property {any} [items]
   * @property {number} [minCardWidth]
   * @property {number} [cardHeight]
   * @property {number} [gap]
   * @property {number} [buffer]
   * @property {import('svelte').Snippet<[any]>} [children]
   * @property {import('svelte').Snippet} [empty]
   */

  /** @type {Props} */
  let {
    items = [],
    minCardWidth = 200,
    cardHeight = 160,
    gap = 12,
    buffer = 3,
    children,
    empty
  } = $props();

  let containerEl = $state();
  let containerWidth = $state(0);
  let scrollParent = $state(null);
  let offsetInParent = $state(0);
  let viewportHeight = $state(0);
  let scrollTop = $state(0);





  function findScrollParent(el) {
    let node = el.parentElement;
    while (node) {
      const style = getComputedStyle(node);
      if (style.overflowY === 'auto' || style.overflowY === 'scroll') return node;
      node = node.parentElement;
    }
    return document.documentElement;
  }

  function updateOffset() {
    if (!containerEl || !scrollParent) return;
    const containerRect = containerEl.getBoundingClientRect();
    const parentRect = scrollParent.getBoundingClientRect();
    offsetInParent = containerRect.top - parentRect.top + scrollParent.scrollTop;
  }

  function handleScroll() {
    if (!scrollParent) return;
    scrollTop = scrollParent.scrollTop;
  }

  let resizeObserver;
  let rafId = null;

  function scheduleScroll() {
    if (rafId) return;
    rafId = requestAnimationFrame(() => {
      rafId = null;
      handleScroll();
    });
  }

  onMount(() => {
    if (!containerEl) return;

    scrollParent = findScrollParent(containerEl);
    viewportHeight = scrollParent.clientHeight;
    containerWidth = containerEl.clientWidth;

    updateOffset();
    handleScroll();

    scrollParent.addEventListener('scroll', scheduleScroll, { passive: true });

    resizeObserver = new ResizeObserver(() => {
      containerWidth = containerEl.clientWidth;
      viewportHeight = scrollParent.clientHeight;
      updateOffset();
    });
    resizeObserver.observe(containerEl);
    if (scrollParent !== document.documentElement) {
      resizeObserver.observe(scrollParent);
    }
  });

  onDestroy(() => {
    scrollParent?.removeEventListener('scroll', scheduleScroll);
    resizeObserver?.disconnect();
    if (rafId) cancelAnimationFrame(rafId);
  });
  // Recompute offset when items change (layout may shift)
  run(() => {
    if (items && containerEl && scrollParent) updateOffset();
  });
  // Computed layout
  let columns = $derived(Math.max(1, Math.floor((containerWidth + gap) / (minCardWidth + gap))));
  let totalRows = $derived(Math.ceil(items.length / columns));
  let rowHeightWithGap = $derived(cardHeight + gap);
  let totalHeight = $derived(totalRows * rowHeightWithGap - (totalRows > 0 ? gap : 0));
  // Visible range based on parent scroll
  let relativeScroll = $derived(Math.max(0, scrollTop - offsetInParent));
  let startRow = $derived(Math.max(0, Math.floor(relativeScroll / rowHeightWithGap) - buffer));
  let endRow = $derived(Math.min(totalRows, Math.ceil((relativeScroll + viewportHeight) / rowHeightWithGap) + buffer));
  let visibleItems = $derived((() => {
    const result = [];
    for (let row = startRow; row < endRow; row++) {
      for (let col = 0; col < columns; col++) {
        const idx = row * columns + col;
        if (idx < items.length) {
          result.push({ item: items[idx], row, col, index: idx });
        }
      }
    }
    return result;
  })());
</script>

<div class="virtual-grid-container" bind:this={containerEl} style="height: {totalHeight}px;">
  {#each visibleItems as { item, row, col, index } (item.id ?? index)}
    <div
      class="virtual-grid-cell"
      style="
        position: absolute;
        top: {row * rowHeightWithGap}px;
        left: {col * ((containerWidth - (columns - 1) * gap) / columns + gap)}px;
        width: {(containerWidth - (columns - 1) * gap) / columns}px;
        height: {cardHeight}px;
      "
    >
      {@render children?.({ item, index, })}
    </div>
  {/each}
  {#if items.length === 0}
    {#if empty}{@render empty()}{:else}
      <p class="text-muted" style="text-align:center;padding:2rem;">No items</p>
    {/if}
  {/if}
</div>

<style>
  .virtual-grid-container {
    position: relative;
    width: 100%;
  }

  .virtual-grid-cell {
    box-sizing: border-box;
  }
</style>
