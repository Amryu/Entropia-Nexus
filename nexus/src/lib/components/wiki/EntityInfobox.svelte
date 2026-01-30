<!--
  @component EntityInfobox
  Compact infobox displaying entity icon and key stats.
  Adapts layout for mobile (horizontal) and desktop (vertical/floating).
-->
<script>
  // @ts-nocheck

  /** @type {object|null} Entity object */
  export let entity = null;

  /** @type {string} Entity name (fallback if entity is null) */
  export let name = '';

  /** @type {string} Entity type label (e.g., "Melee Weapon") */
  export let type = '';

  /** @type {string} Entity subtype/class (e.g., "Sword") */
  export let subtype = '';

  /** @type {string|null} Image URL */
  export let imageUrl = null;

  /** @type {Array} Key stats to display [{label, value, suffix?}] */
  export let stats = [];

  /** @type {boolean} Whether to show in compact/horizontal mode */
  export let compact = false;

  /** @type {string} Layout variant: 'default', 'floating', 'card' */
  export let variant = 'default';

  $: displayName = entity?.Name || name;
  $: displayType = entity?.Properties?.Type || type;
  $: displaySubtype = entity?.Properties?.Class || subtype;
</script>

<div class="entity-infobox" class:compact class:floating={variant === 'floating'} class:card={variant === 'card'}>
  <div class="infobox-icon">
    {#if imageUrl}
      <img src={imageUrl} alt={displayName} class="entity-image" />
    {:else}
      <div class="icon-placeholder">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path d="M21 15l-5-5L5 21" />
        </svg>
      </div>
    {/if}
  </div>

  <div class="infobox-content">
    <h2 class="entity-name">{displayName}</h2>

    {#if displayType || displaySubtype}
      <div class="entity-type">
        {#if displayType}
          <span class="type-badge">{displayType}</span>
        {/if}
        {#if displaySubtype}
          <span class="subtype">{displaySubtype}</span>
        {/if}
      </div>
    {/if}

    {#if stats.length > 0}
      <div class="quick-stats">
        {#each stats as stat}
          <div class="stat-item">
            <span class="stat-label">{stat.label}</span>
            <span class="stat-value">
              {stat.value}{#if stat.suffix}<span class="stat-suffix">{stat.suffix}</span>{/if}
            </span>
          </div>
        {/each}
      </div>
    {/if}

    <slot name="extra" />
  </div>
</div>

<style>
  .entity-infobox {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
  }

  /* Compact/horizontal layout (for mobile or inline use) */
  .entity-infobox.compact {
    flex-direction: row;
    align-items: flex-start;
    padding: 12px;
    gap: 12px;
  }

  .entity-infobox.compact .infobox-icon {
    flex-shrink: 0;
  }

  .entity-infobox.compact .entity-name {
    font-size: 18px;
  }

  .entity-infobox.compact .quick-stats {
    flex-direction: row;
    flex-wrap: wrap;
    gap: 8px 16px;
  }

  /* Floating variant (Wikipedia-style right sidebar) */
  .entity-infobox.floating {
    float: right;
    width: 280px;
    margin: 0 0 16px 20px;
  }

  /* Card variant (full width, centered content) */
  .entity-infobox.card {
    align-items: center;
    text-align: center;
  }

  .entity-infobox.card .quick-stats {
    justify-content: center;
  }

  .infobox-icon {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .entity-image {
    width: 100px;
    height: 100px;
    object-fit: contain;
    border-radius: 6px;
    background-color: var(--bg-color, var(--primary-color));
  }

  .entity-infobox.compact .entity-image {
    width: 80px;
    height: 80px;
  }

  .icon-placeholder {
    width: 100px;
    height: 100px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-color, var(--primary-color));
    border: 2px dashed var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-muted, #999);
  }

  .entity-infobox.compact .icon-placeholder {
    width: 80px;
    height: 80px;
  }

  .entity-infobox.compact .icon-placeholder svg {
    width: 36px;
    height: 36px;
  }

  .infobox-content {
    flex: 1;
    min-width: 0;
  }

  .entity-name {
    font-size: 22px;
    font-weight: 600;
    margin: 0 0 6px 0;
    color: var(--text-color);
    line-height: 1.2;
  }

  .entity-type {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .type-badge {
    display: inline-block;
    padding: 2px 8px;
    font-size: 12px;
    font-weight: 500;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .subtype {
    font-size: 14px;
    color: var(--text-muted, #999);
  }

  .quick-stats {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
    font-size: 14px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
  }

  .stat-suffix {
    font-weight: 400;
    color: var(--text-muted, #999);
    margin-left: 2px;
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .entity-infobox {
      padding: 12px;
    }

    .entity-infobox.floating {
      float: none;
      width: 100%;
      margin: 0 0 12px 0;
    }

    .entity-name {
      font-size: 20px;
    }

    .entity-image,
    .icon-placeholder {
      width: 80px;
      height: 80px;
    }
  }
</style>
