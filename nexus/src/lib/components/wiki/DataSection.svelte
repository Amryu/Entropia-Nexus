<!--
  @component DataSection
  Collapsible content section for organizing wiki page data.
  Supports expand/collapse with smooth animation.
-->
<script>
  // @ts-nocheck
  import { slide } from 'svelte/transition';












  /**
   * @typedef {Object} Props
   * @property {string} [title]
   * @property {string} [icon]
   * @property {boolean} [expanded]
   * @property {boolean} [collapsible]
   * @property {string} [subtitle]
   * @property {boolean} [allowOverflow]
   * @property {import('svelte').Snippet} [actions]
   * @property {import('svelte').Snippet} [children]
   * @property {Function} [ontoggle]
   */

  /** @type {Props} */
  let {
    title = '',
    icon = '',
    expanded = $bindable(true),
    collapsible = true,
    subtitle = '',
    allowOverflow = false,
    actions,
    children,
    ontoggle
  } = $props();

  function toggle() {
    if (collapsible) {
      expanded = !expanded;
      ontoggle?.({ expanded });
    }
  }

  function handleKeydown(event) {
    if (collapsible && (event.key === 'Enter' || event.key === ' ')) {
      event.preventDefault();
      toggle();
    }
  }
</script>

<section class="data-section" class:expanded class:collapsible class:allow-overflow={allowOverflow}>
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -- tabindex is conditional: only set when collapsible makes header a button -->
  <header
    class="section-header"
    role={collapsible ? 'button' : undefined}
    tabindex={collapsible ? 0 : undefined}
    aria-expanded={collapsible ? expanded : undefined}
    onclick={toggle}
    onkeydown={handleKeydown}
  >
    <div class="section-title-group">
      {#if icon}
        <span class="section-icon">{icon}</span>
      {/if}
      <h2 class="section-title">{title}</h2>
      {#if subtitle && !expanded}
        <span class="section-subtitle">{subtitle}</span>
      {/if}
    </div>

    <div class="section-actions" role="presentation" onclick={(e) => e.stopPropagation()}>
      {@render actions?.()}
    </div>

    {#if collapsible}
      <span class="expand-icon" class:rotated={expanded}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </span>
    {/if}
  </header>

  {#if expanded}
    <div class="section-content" transition:slide={{ duration: 200 }}>
      {@render children?.()}
    </div>
  {/if}
</section>

<style>
  .data-section {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    margin-bottom: 16px;
    overflow: hidden;
  }

  .data-section.allow-overflow {
    overflow: visible;
  }

  .data-section:last-child {
    margin-bottom: 0;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background-color: var(--bg-secondary, var(--secondary-color));
    border-bottom: 1px solid transparent;
    user-select: none;
  }

  .data-section.expanded .section-header {
    border-bottom-color: var(--border-color, #555);
  }

  .data-section.collapsible .section-header {
    cursor: pointer;
  }

  .data-section.collapsible .section-header:hover {
    background-color: var(--hover-color);
  }

  .data-section.collapsible .section-header:focus {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
  }

  .section-title-group {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    flex: 1;
  }

  .section-icon {
    font-size: 18px;
    flex-shrink: 0;
  }

  .section-title {
    font-size: 16px;
    font-weight: 600;
    margin: 0;
    color: var(--text-color);
  }

  .section-subtitle {
    font-size: 13px;
    color: var(--text-muted, #999);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .section-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
    margin-right: 8px;
  }

  .section-actions:empty {
    display: none;
  }

  .expand-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted, #999);
    transition: transform 0.2s ease;
    flex-shrink: 0;
  }

  .expand-icon.rotated {
    transform: rotate(180deg);
  }

  .section-content {
    padding: 16px;
  }

  /* Mobile adjustments - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .data-section {
      border-radius: 6px;
      margin-bottom: 12px;
    }

    .section-header {
      padding: 10px 12px;
    }

    .section-title {
      font-size: 15px;
    }

    .section-content {
      padding: 12px;
    }
  }
</style>
