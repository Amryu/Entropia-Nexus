<script>
  // @ts-nocheck
  let { show = $bindable(false) } = $props();

  function close() {
    show = false;
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) close();
  }

  function handleKeydown(e) {
    if (show && e.key === 'Escape') close();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<button class="mu-help-btn" onclick={() => show = true} title="What are markup sources?">
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="10" />
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
</button>

{#if show}
  <div class="modal-backdrop" role="presentation" onclick={handleBackdropClick}>
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header">
        <h3>Markup Sources</h3>
        <button type="button" class="modal-close" onclick={close}>&times;</button>
      </div>
      <div class="modal-body">
        <div class="help-section">
          <h4>Custom</h4>
          <p>
            Markup values specific to this calculator. When you haven't set a value
            for an item, the best available price is used automatically from your
            other sources in order: Inventory, In-Game, then Exchange.
          </p>
        </div>
        <div class="help-section">
          <h4>Inventory</h4>
          <p>
            Your account-wide markup settings, shared across all tools and your
            inventory valuation. You can edit values directly when this source
            is selected.
          </p>
        </div>
        <div class="help-section">
          <h4>In-Game</h4>
          <p>
            Market prices captured from in-game scans using the Entropia Nexus
            client. Updated automatically when new scans are performed.
          </p>
        </div>
        <div class="help-section">
          <h4>Exchange</h4>
          <p>
            Current weighted average prices (WAP) from the Entropia Nexus
            exchange.
          </p>
        </div>
        <div class="help-note">
          <p>
            When using Custom or Inventory, click any markup value to edit it.
            Values shown with a dashed underline are editable.
          </p>
        </div>
      </div>
      <div class="modal-footer">
        <button type="button" class="close-btn" onclick={close}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .mu-help-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    padding: 0;
    border: 1px solid var(--border-color, #555);
    border-radius: 50%;
    background: var(--bg-color);
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .mu-help-btn:hover {
    background: var(--accent-color, #4a9eff);
    color: white;
    border-color: var(--accent-color, #4a9eff);
  }

  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
  }

  .modal {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 100%;
    max-width: 460px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .modal-header h3 {
    margin: 0;
    font-size: 16px;
    color: var(--text-color);
  }

  .modal-close {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 24px;
    cursor: pointer;
    line-height: 1;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all 0.15s ease;
  }

  .modal-close:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .modal-body {
    padding: 20px;
    overflow-y: auto;
    flex: 1;
  }

  .help-section {
    margin-bottom: 16px;
  }

  .help-section:last-of-type {
    margin-bottom: 0;
  }

  .help-section h4 {
    margin: 0 0 4px;
    font-size: 14px;
    color: var(--accent-color, #4a9eff);
  }

  .help-section p {
    margin: 0;
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-color);
  }

  .help-note {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
  }

  .help-note p {
    margin: 0;
    font-size: 12px;
    line-height: 1.5;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    padding: 12px 20px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .close-btn {
    padding: 8px 16px;
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }
</style>
