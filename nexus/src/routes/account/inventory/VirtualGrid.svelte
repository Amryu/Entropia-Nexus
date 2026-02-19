<script>
  import { onMount, onDestroy } from 'svelte';

  export let items = [];
  export let minCardWidth = 200;
  export let cardHeight = 160;
  export let gap = 12;
  export let buffer = 3;

  let containerEl;
  let containerWidth = 0;
  let scrollParent = null;
  let offsetInParent = 0;
  let viewportHeight = 0;
  let scrollTop = 0;

  // Recompute offset when items change (layout may shift)
  $: if (items && containerEl && scrollParent) updateOffset();

  // Computed layout
  $: columns = Math.max(1, Math.floor((containerWidth + gap) / (minCardWidth + gap)));
  $: totalRows = Math.ceil(items.length / columns);
  $: rowHeightWithGap = cardHeight + gap;
  $: totalHeight = totalRows * rowHeightWithGap - (totalRows > 0 ? gap : 0);

  // Visible range based on parent scroll
  $: relativeScroll = Math.max(0, scrollTop - offsetInParent);
  $: startRow = Math.max(0, Math.floor(relativeScroll / rowHeightWithGap) - buffer);
  $: endRow = Math.min(totalRows, Math.ceil((relativeScroll + viewportHeight) / rowHeightWithGap) + buffer);

  $: visibleItems = (() => {
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
  })();

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
      <slot {item} {index} />
    </div>
  {/each}
  {#if items.length === 0}
    <slot name="empty">
      <p class="text-muted" style="text-align:center;padding:2rem;">No items</p>
    </slot>
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
