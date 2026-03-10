<script>
  // @ts-nocheck
  /**
   * GlobalMediaDialog - Modal for viewing global media (screenshot or video).
   */
  import { createEventDispatcher } from 'svelte';
  import { parseVideoUrl } from '$lib/utils/videoEmbed.js';

  /** @type {boolean} */
  export let show = false;

  /** @type {object|null} Global entry with media_image/media_video */
  export let global = null;

  const dispatch = createEventDispatcher();

  $: videoInfo = global?.media_video
    ? parseVideoUrl(global.media_video, typeof window !== 'undefined' ? window.location.hostname : 'entropianexus.com')
    : null;

  function close() {
    dispatch('close');
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) close();
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') close();
  }

  function formatValue(val, unit) {
    if (!val) return '';
    if (unit === 'PEC') return `${(val / 100).toFixed(2)} PED`;
    return `${Number(val).toFixed(2)} PED`;
  }
</script>

<svelte:window on:keydown={handleKeydown} />

{#if show && global}
  <div class="modal-backdrop" role="presentation" on:click={handleBackdropClick}>
    <div class="modal" class:modal-wide={global.media_image}>
      <div class="modal-header">
        <div class="header-info">
          <h3>
            {global.target || 'Global'}
            {#if global.ath}
              <span class="badge-ath">ATH</span>
            {:else if global.hof}
              <span class="badge-hof">HoF</span>
            {/if}
          </h3>
          <span class="header-meta">
            {global.player || ''}
            {#if global.value}
              — {formatValue(global.value, global.unit)}
            {/if}
          </span>
        </div>
        <button type="button" class="modal-close" on:click={close}>&times;</button>
      </div>

      <div class="modal-body">
        {#if global.media_image}
          <div class="media-image-container">
            <img
              src="/api/img/global/{global.id}"
              alt="Screenshot of {global.target || 'global event'}"
              loading="lazy"
            />
          </div>
        {:else if global.media_video && videoInfo}
          <div class="media-video-container">
            <iframe
              src="{videoInfo.embedUrl}"
              title="Video of {global.target || 'global event'}"
              frameborder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowfullscreen
            ></iframe>
          </div>
        {/if}
      </div>

      <div class="modal-footer">
        <button type="button" class="close-btn" on:click={close}>Close</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.75);
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
    max-width: 600px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
  }

  .modal-wide {
    max-width: 900px;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .header-info h3 {
    margin: 0;
    font-size: 15px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .header-meta {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .badge-hof, .badge-ath {
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .badge-hof {
    background-color: rgba(234, 179, 8, 0.2);
    color: #eab308;
  }

  .badge-ath {
    background-color: rgba(239, 68, 68, 0.2);
    color: #ef4444;
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
    flex-shrink: 0;
  }

  .modal-close:hover {
    color: var(--text-color);
    background-color: var(--hover-color);
  }

  .modal-body {
    padding: 0;
    overflow: auto;
    flex: 1;
  }

  .media-image-container {
    display: flex;
    justify-content: center;
    background: #000;
  }

  .media-image-container img {
    max-width: 100%;
    max-height: 70vh;
    object-fit: contain;
  }

  .media-video-container {
    position: relative;
    width: 100%;
    padding-bottom: 56.25%; /* 16:9 aspect ratio */
  }

  .media-video-container iframe {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    padding: 10px 18px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .close-btn {
    padding: 6px 14px;
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
  }

  .close-btn:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }
</style>
