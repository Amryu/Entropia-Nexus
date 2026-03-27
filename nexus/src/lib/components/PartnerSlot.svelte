<!--
  @component PartnerSlot
  Renders an active promo image or a self-promo placeholder.

  Props:
  - promos: array of active promos for this slot (may be empty)
  - variant: 'vertical' | 'horizontal' — determines which image to show
  - rotationIndex: number for picking which promo from the array
-->
<script>
  let { promos = [], variant = 'horizontal', rotationIndex = 0 } = $props();

  let promo = $derived(
    promos.length > 0 ? promos[rotationIndex % promos.length] : null
  );
</script>

{#if promo}
  <a
    href="/api/promos/click/{promo.booking_id}"
    class="partner-promo"
    class:partner-promo-vertical={variant === 'vertical'}
    class:partner-promo-horizontal={variant === 'horizontal'}
    rel="noopener"
    target="_blank"
  >
    <img
      src="/api/img/promo-visual/{promo.promo_id}-{variant}"
      alt={promo.name || 'Partner'}
      class="partner-promo-img"
      loading="lazy"
    />
  </a>
{:else}
  <a
    href="/account/settings/promos"
    class="partner-content"
    class:partner-content-vertical={variant === 'vertical'}
    class:partner-content-horizontal={variant === 'horizontal'}
  >
    <span class="partner-content-icon">EN</span>
    <span class="partner-content-heading">Partner with Entropia Nexus</span>
    <span class="partner-content-sub">Reach the EU community</span>
    <span class="partner-cta">Learn More</span>
  </a>
{/if}

<style>
  /* Active promo */
  .partner-promo {
    display: block;
    width: 100%;
    height: 100%;
    border-radius: 8px;
    overflow: hidden;
    transition: opacity 0.2s ease;
  }

  .partner-promo:hover {
    opacity: 0.92;
  }

  .partner-promo-img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  /* Self-promo placeholder */
  .partner-content {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-muted);
    background: linear-gradient(
      135deg,
      var(--secondary-color) 0%,
      color-mix(in srgb, var(--secondary-color) 85%, var(--accent-color)) 100%
    );
    border: 1px dashed var(--border-color);
    box-sizing: border-box;
    transition: border-color 0.2s ease, background 0.2s ease;
    gap: 8px;
    padding: 16px;
  }

  .partner-content:hover {
    border-color: var(--accent-color);
  }

  /* Vertical layout (160x600 side rails) */
  .partner-content-vertical {
    flex-direction: column;
    text-align: center;
    gap: 12px;
  }

  /* Horizontal layout (inline slots) */
  .partner-content-horizontal {
    flex-direction: row;
    text-align: left;
    gap: 12px;
  }

  .partner-content-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    min-width: 36px;
    border-radius: 8px;
    background-color: var(--primary-color);
    color: var(--accent-color);
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .partner-content-heading {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--text-color);
    line-height: 1.3;
  }

  .partner-content-sub {
    font-size: 0.75rem;
    color: var(--text-muted);
    line-height: 1.3;
  }

  .partner-cta {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--accent-color);
    transition: text-decoration 0.15s ease;
  }

  .partner-content:hover .partner-cta {
    text-decoration: underline;
  }

  /* Vertical: stack all items */
  .partner-content-vertical .partner-content-icon {
    width: 44px;
    height: 44px;
    min-width: 44px;
    font-size: 0.875rem;
  }

  .partner-content-vertical .partner-content-heading {
    font-size: 0.875rem;
  }

  /* Horizontal: keep text items together */
  .partner-content-horizontal .partner-content-sub {
    display: none;
  }

  @media (max-width: 599px) {
    .partner-content-horizontal .partner-content-sub {
      display: none;
    }

    .partner-content-heading {
      font-size: 0.75rem;
    }
  }
</style>
