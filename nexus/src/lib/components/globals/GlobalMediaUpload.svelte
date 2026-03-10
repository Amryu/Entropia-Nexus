<script>
  // @ts-nocheck
  /**
   * GlobalMediaUpload - Small inline component for uploading media to a global.
   * Shows a camera/upload icon that opens a dropdown for screenshot upload or YouTube link.
   */
  import { createEventDispatcher } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';

  /** @type {number} */
  export let globalId;

  /** @type {string} Player name on the global (for ownership check) */
  export let playerName = '';

  /** @type {object|null} User session (null = not logged in) */
  export let user = null;

  /** Only show upload for the user's own globals (or admins) */
  $: isOwner = user && playerName && user.eu_name
    && user.eu_name.toLowerCase() === playerName.toLowerCase();
  $: isAdmin = user?.administrator || user?.grants?.includes('admin.panel');
  $: canUpload = isOwner || isAdmin;

  const dispatch = createEventDispatcher();
  let showMenu = false;
  let showVideoInput = false;
  let videoUrl = '';
  let uploading = false;
  let fileInput;
  let btnEl;
  let menuEl;
  let menuPos = { top: 0, right: 0 };

  function toggleMenu() {
    if (uploading) return;
    if (!showMenu && btnEl) {
      const rect = btnEl.getBoundingClientRect();
      menuPos = { top: rect.bottom + 4, right: window.innerWidth - rect.right };
    }
    showMenu = !showMenu;
    showVideoInput = false;
    videoUrl = '';
  }

  function closeMenu() {
    showMenu = false;
    showVideoInput = false;
    videoUrl = '';
  }

  function handleClickOutside(e) {
    if (!showMenu) return;
    if (btnEl && btnEl.contains(e.target)) return;
    if (menuEl && menuEl.contains(e.target)) return;
    closeMenu();
  }

  async function handleFileSelect(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      addToast('Image must be smaller than 5MB.', { type: 'error' });
      return;
    }

    uploading = true;
    closeMenu();

    try {
      const formData = new FormData();
      formData.append('image', file);

      const res = await fetch(`/api/globals/${globalId}/media`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        addToast('Screenshot uploaded successfully.', { type: 'success' });
        dispatch('uploaded', { type: 'image', globalId });
      } else {
        addToast(data.error || 'Upload failed.', { type: 'error' });
      }
    } catch (err) {
      addToast('Upload failed: ' + err.message, { type: 'error' });
    } finally {
      uploading = false;
      if (fileInput) fileInput.value = '';
    }
  }

  async function submitVideo() {
    if (!videoUrl.trim()) return;

    uploading = true;
    closeMenu();

    try {
      const res = await fetch(`/api/globals/${globalId}/media`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_url: videoUrl.trim() }),
      });

      const data = await res.json();
      if (res.ok) {
        addToast('Video link added successfully.', { type: 'success' });
        dispatch('uploaded', { type: 'video', globalId });
      } else {
        addToast(data.error || 'Failed to add video link.', { type: 'error' });
      }
    } catch (err) {
      addToast('Failed: ' + err.message, { type: 'error' });
    } finally {
      uploading = false;
      videoUrl = '';
    }
  }
</script>

<svelte:body on:mousedown={handleClickOutside} />

{#if canUpload}
  <div class="media-upload-wrapper">
    <button
      class="media-upload-btn"
      class:uploading
      title="Add media to this global"
      on:click={toggleMenu}
      disabled={uploading}
      bind:this={btnEl}
    >
      {#if uploading}
        <span class="spinner"></span>
      {:else}
        <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
          <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/>
        </svg>
      {/if}
    </button>

    {#if showMenu}
      <div class="upload-menu" bind:this={menuEl} style="top: {menuPos.top}px; right: {menuPos.right}px;">
        {#if !showVideoInput}
          <button class="menu-item" on:click={() => fileInput?.click()}>
            Upload Screenshot
          </button>
          <button class="menu-item" on:click={() => { showVideoInput = true; }}>
            Add Video Link
          </button>
        {:else}
          <div class="video-input-row">
            <input
              type="text"
              bind:value={videoUrl}
              placeholder="Video URL (YouTube, Twitch, Vimeo)"
              on:keydown={(e) => { if (e.key === 'Enter') submitVideo(); }}
            />
            <button class="submit-btn" on:click={submitVideo} disabled={!videoUrl.trim()}>
              Add
            </button>
          </div>
        {/if}
      </div>
    {/if}

    <input
      type="file"
      accept="image/png,image/jpeg,image/webp"
      style="display:none"
      bind:this={fileInput}
      on:change={handleFileSelect}
    />
  </div>
{/if}

<style>
  .media-upload-wrapper {
    position: relative;
    display: inline-flex;
  }

  .media-upload-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 2px;
    border-radius: 3px;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0.5;
    transition: opacity 0.15s;
  }

  .media-upload-btn:hover {
    opacity: 1;
    color: var(--accent-color);
  }

  .media-upload-btn.uploading {
    opacity: 1;
    cursor: wait;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid var(--text-muted);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .upload-menu {
    position: fixed;
    z-index: 100;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    min-width: 180px;
    padding: 4px;
  }

  .menu-item {
    display: block;
    width: 100%;
    text-align: left;
    padding: 8px 12px;
    background: none;
    border: none;
    color: var(--text-color);
    font-size: 13px;
    cursor: pointer;
    border-radius: 4px;
  }

  .menu-item:hover {
    background: var(--hover-color);
  }

  .video-input-row {
    display: flex;
    gap: 6px;
    padding: 6px;
  }

  .video-input-row input {
    flex: 1;
    padding: 6px 8px;
    font-size: 12px;
    background: var(--primary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    min-width: 180px;
  }

  .submit-btn {
    padding: 6px 12px;
    font-size: 12px;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    white-space: nowrap;
  }

  .submit-btn:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .submit-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
