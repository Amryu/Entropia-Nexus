<script>
  // @ts-nocheck
  /**
   * GlobalMediaDialog - Modal for viewing global media (screenshot or video).
   * Supports GZ (congrats), delete (uploader/admin), and report (other users).
   */
  import { createEventDispatcher } from 'svelte';
  import { parseVideoUrl } from '$lib/utils/videoEmbed.js';
  import { addToast } from '$lib/stores/toasts.js';
  import GzButton from '$lib/components/globals/GzButton.svelte';

  /** @type {boolean} */
  export let show = false;

  /** @type {object|null} Global entry with media_image/media_video */
  export let global = null;

  /** @type {object|null} User session */
  export let user = null;

  const dispatch = createEventDispatcher();

  $: videoInfo = global?.media_video
    ? parseVideoUrl(global.media_video, typeof window !== 'undefined' ? window.location.hostname : 'entropianexus.com')
    : null;

  $: userId = user ? String(user.Id || user.id) : null;
  $: isUploader = userId && global?.media_uploaded_by && String(global.media_uploaded_by) === userId;
  $: isAdmin = user?.administrator || user?.grants?.includes('admin.panel');
  $: canDelete = isUploader || isAdmin;
  $: canReport = user && !isUploader && (global?.media_image || global?.media_video);

  let deleting = false;
  let showReportForm = false;
  let reportReason = '';
  let reporting = false;
  let reported = false;

  function close() {
    showReportForm = false;
    reportReason = '';
    reported = false;
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

  async function deleteMedia() {
    if (!global || deleting) return;
    if (!confirm('Delete this media? This cannot be undone.')) return;

    deleting = true;
    try {
      const res = await fetch(`/api/globals/${global.id}/media`, { method: 'DELETE' });
      if (res.ok) {
        addToast('Media deleted.', { type: 'success' });
        dispatch('deleted', { globalId: global.id });
      } else {
        const data = await res.json().catch(() => ({}));
        addToast(data.error || 'Failed to delete media.', { type: 'error' });
      }
    } catch (err) {
      addToast('Failed to delete media.', { type: 'error' });
    } finally {
      deleting = false;
    }
  }

  async function submitReport() {
    if (!reportReason.trim() || reporting) return;

    reporting = true;
    try {
      const res = await fetch(`/api/globals/${global.id}/media/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: reportReason.trim() }),
      });
      if (res.ok) {
        addToast('Report submitted. Thank you.', { type: 'success' });
        reported = true;
        showReportForm = false;
        reportReason = '';
      } else {
        const data = await res.json().catch(() => ({}));
        addToast(data.error || 'Failed to submit report.', { type: 'error' });
      }
    } catch {
      addToast('Failed to submit report.', { type: 'error' });
    } finally {
      reporting = false;
    }
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
        <div class="footer-left">
          <GzButton globalId={global.id} count={global.gz_count || 0} {user} />
          {#if canReport && !reported}
            {#if !showReportForm}
              <button type="button" class="report-btn" on:click={() => { showReportForm = true; }}>
                Report
              </button>
            {:else}
              <div class="report-form">
                <input
                  type="text"
                  bind:value={reportReason}
                  placeholder="Reason for report..."
                  maxlength="500"
                  on:keydown={(e) => { if (e.key === 'Enter') submitReport(); }}
                />
                <button type="button" class="report-submit" on:click={submitReport} disabled={!reportReason.trim() || reporting}>
                  Submit
                </button>
                <button type="button" class="report-cancel" on:click={() => { showReportForm = false; reportReason = ''; }}>
                  Cancel
                </button>
              </div>
            {/if}
          {:else if reported}
            <span class="report-done">Reported</span>
          {/if}
        </div>
        <div class="footer-right">
          {#if canDelete}
            <button type="button" class="delete-btn" on:click={deleteMedia} disabled={deleting}>
              {deleting ? 'Deleting...' : 'Delete'}
            </button>
          {/if}
          <button type="button" class="close-btn" on:click={close}>Close</button>
        </div>
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
    background-color: color-mix(in srgb, var(--color-gold) 20%, transparent);
    color: var(--color-gold);
  }

  .badge-ath {
    background-color: color-mix(in srgb, var(--color-danger) 20%, transparent);
    color: var(--color-danger);
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
    justify-content: space-between;
    align-items: center;
    padding: 10px 18px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
    gap: 10px;
  }

  .footer-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .footer-right {
    display: flex;
    align-items: center;
    gap: 8px;
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

  .delete-btn {
    padding: 6px 14px;
    background-color: transparent;
    color: var(--color-danger);
    border: 1px solid color-mix(in srgb, var(--color-danger) 30%, transparent);
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
  }

  .delete-btn:hover:not(:disabled) {
    background-color: color-mix(in srgb, var(--color-danger) 15%, transparent);
  }

  .delete-btn:disabled {
    opacity: 0.5;
    cursor: wait;
  }

  .report-btn {
    padding: 4px 10px;
    background: none;
    border: 1px solid var(--border-color);
    color: var(--text-muted);
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
  }

  .report-btn:hover {
    color: var(--text-color);
    border-color: var(--text-muted);
  }

  .report-form {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .report-form input {
    padding: 4px 8px;
    font-size: 12px;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    min-width: 160px;
  }

  .report-submit {
    padding: 4px 10px;
    font-size: 12px;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  .report-submit:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .report-cancel {
    padding: 4px 10px;
    font-size: 12px;
    background: none;
    border: 1px solid var(--border-color);
    color: var(--text-muted);
    border-radius: 4px;
    cursor: pointer;
  }

  .report-done {
    font-size: 12px;
    color: var(--text-muted);
    font-style: italic;
  }
</style>
