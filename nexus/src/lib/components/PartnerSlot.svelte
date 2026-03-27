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
  <div class="partner-promo-wrap">
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
    <a href="/account/settings/promos" class="partner-promo-cta">Place yours here</a>
  </div>
{:else}
  <a
    href="/account/settings/promos"
    class="partner-content"
    class:partner-content-vertical={variant === 'vertical'}
    class:partner-content-horizontal={variant === 'horizontal'}
  >
    <span class="partner-content-icon">EN</span>
    <div class="partner-content-text">
      <span class="partner-content-heading">Partner with Entropia Nexus</span>
      <span class="partner-content-sub">Reach the EU community with your placements</span>
      <span class="partner-cta">Learn More</span>
    </div>
  </a>
{/if}

<style>
  /* Active promo wrapper */
  .partner-promo-wrap {
    position: relative;
    width: 100%;
    height: 100%;
  }

  .partner-promo-cta {
    display: block;
    text-align: center;
    font-size: 0.6875rem;
    color: var(--text-muted);
    text-decoration: none;
    padding: 4px 0;
    opacity: 0.6;
    transition: opacity 0.15s, color 0.15s;
  }

  .partner-promo-cta:hover {
    opacity: 1;
    color: var(--accent-color);
  }

  @media (max-width: 899px) {
    .partner-promo-cta {
      display: none;
    }
  }

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
    gap: 16px;
  }

  .partner-content-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px;
    height: 40px;
    min-width: 40px;
    border-radius: 8px;
    background-color: var(--primary-color);
    color: var(--accent-color);
    font-size: 0.8125rem;
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .partner-content-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .partner-content-heading {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-color);
    line-height: 1.3;
  }

  .partner-content-sub {
    font-size: 0.8125rem;
    color: var(--text-muted);
    line-height: 1.3;
  }

  .partner-cta {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--accent-color);
    margin-top: 2px;
  }

  .partner-content:hover .partner-cta {
    text-decoration: underline;
  }

  /* Vertical: stack all items */
  .partner-content-vertical {
    flex-direction: column;
    text-align: center;
    gap: 12px;
  }

  .partner-content-vertical .partner-content-icon {
    width: 48px;
    height: 48px;
    min-width: 48px;
    font-size: 1rem;
  }

  .partner-content-vertical .partner-content-text {
    align-items: center;
    gap: 6px;
  }

  @media (max-width: 599px) {
    .partner-content-heading {
      font-size: 0.8125rem;
    }

    .partner-content-sub {
      display: none;
    }
  }
</style>
