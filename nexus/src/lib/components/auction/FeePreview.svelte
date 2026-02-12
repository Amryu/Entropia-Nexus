<!--
  @component FeePreview
  Real-time auction fee calculator display.
  Shows the tiered fee breakdown based on a given amount.
-->
<script>
  import { calculateAuctionFee } from '$lib/common/auctionUtils.js';

  /** @type {number} Amount to calculate fee for (PED) */
  export let amount = 0;

  $: fee = calculateAuctionFee(amount);
  $: netAmount = amount > 0 ? Math.max(0, amount - fee) : 0;
</script>

<div class="fee-preview">
  <div class="fee-row">
    <span class="fee-label">Estimated fee</span>
    <span class="fee-value" class:free={fee === 0}>
      {fee === 0 ? 'Free' : `${fee.toFixed(2)} PED`}
    </span>
  </div>
  {#if amount > 0 && fee > 0}
    <div class="fee-row net">
      <span class="fee-label">You receive</span>
      <span class="fee-value">{netAmount.toFixed(2)} PED</span>
    </div>
  {/if}
  <div class="fee-breakdown">
    <span class="fee-hint">First 100 PED free, 2% up to 1000, 1% above</span>
  </div>
</div>

<style>
  .fee-preview {
    padding: 0.75rem;
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .fee-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .fee-row.net {
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px solid var(--border-color);
  }

  .fee-label {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .fee-value {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .fee-value.free {
    color: var(--success-color);
  }

  .fee-breakdown {
    margin-top: 6px;
  }

  .fee-hint {
    font-size: 0.75rem;
    color: var(--text-muted);
  }
</style>
