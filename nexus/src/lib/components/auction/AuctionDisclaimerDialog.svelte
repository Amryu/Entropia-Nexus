<!--
  @component AuctionDisclaimerDialog
  Modal dialog for first-time bidder/seller disclaimer acceptance.
-->
<script>
  import { addToast } from '$lib/stores/toasts.js';




  /**
   * @typedef {Object} Props
   * @property {boolean} [open]
   * @property {'bidder'|'seller'} [role]
   * @property {(data: {role: string}) => void} [onaccepted]
   * @property {() => void} [onclose]
   */

  /** @type {Props} */
  let { open = $bindable(false), role = 'bidder', onaccepted, onclose } = $props();

  let accepted = $state(false);
  let submitting = $state(false);

  const disclaimerText = {
    bidder: {
      title: 'Bidder Agreement',
      points: [
        'By placing a bid, you commit to completing the transaction if you win.',
        'Bids cannot be retracted once placed.',
        'If you win an auction, you are obligated to pay the winning amount in-game.',
        'Failure to complete transactions may result in account restrictions.',
        'If any issues arise or mistakes need to be corrected, you must inform moderators as soon as possible to avoid account penalties.',
        'The platform facilitates connections between buyers and sellers but does not guarantee trades.'
      ]
    },
    seller: {
      title: 'Seller Agreement',
      points: [
        'Listing an auction commits you to selling the item(s) if a valid bid is received.',
        'A fee will be deducted from the final sale price (first 100 PED free, 2% up to 1000 PED, 1% above).',
        'Items in your item set should match their description. Misrepresentation may result in account restrictions.',
        'You are responsible for completing the in-game trade with the winning bidder.',
        'Auctions with bids cannot be cancelled by the seller.',
        'If any issues arise or mistakes need to be corrected, you must inform moderators as soon as possible to avoid account penalties.',
        'The platform facilitates connections between buyers and sellers but does not guarantee trades.'
      ]
    }
  };

  let config = $derived(disclaimerText[role] || disclaimerText.bidder);

  async function handleAccept() {
    if (!accepted) return;
    submitting = true;

    try {
      const res = await fetch('/api/auction/disclaimer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role })
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || 'Failed to accept disclaimer');
      }

      onaccepted?.({ role });
      open = false;
    } catch (err) {
      addToast(err.message, { type: 'error' });
    } finally {
      submitting = false;
    }
  }

  function handleClose() {
    accepted = false;
    open = false;
    onclose?.();
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) handleClose();
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') handleClose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
  <div class="dialog-backdrop" role="presentation" onclick={handleBackdropClick}>
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="disclaimer-title">
      <div class="dialog-header">
        <h2 id="disclaimer-title">{config.title}</h2>
      </div>

      <div class="dialog-content">
        <ul class="disclaimer-points">
          {#each config.points as point}
            <li>{point}</li>
          {/each}
        </ul>

        <label class="checkbox-label">
          <input type="checkbox" bind:checked={accepted} />
          <span>I have read and agree to the above terms</span>
        </label>
      </div>

      <div class="dialog-footer">
        <button class="btn btn-secondary" onclick={handleClose}>Cancel</button>
        <button class="btn btn-primary" onclick={handleAccept} disabled={!accepted || submitting}>
          {submitting ? 'Accepting...' : 'Accept & Continue'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .dialog-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 20px;
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    width: 100%;
    max-width: 520px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dialog-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .dialog-content {
    padding: 20px;
    flex: 1;
    overflow-y: auto;
  }

  .disclaimer-points {
    margin: 0 0 1.25rem 0;
    padding-left: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .disclaimer-points li {
    font-size: 0.9rem;
    color: var(--text-color);
    line-height: 1.5;
  }

  .checkbox-label {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    cursor: pointer;
    padding: 0.75rem;
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
  }

  .checkbox-label input {
    margin-top: 2px;
    flex-shrink: 0;
  }

  .checkbox-label span {
    font-size: 0.9rem;
    color: var(--text-color);
    font-weight: 500;
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 16px 20px;
    border-top: 1px solid var(--border-color);
  }

  .btn {
    padding: 8px 16px;
    font-size: 14px;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background-color: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-secondary:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .btn-primary {
    background-color: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover, #3a8eef);
  }
</style>
