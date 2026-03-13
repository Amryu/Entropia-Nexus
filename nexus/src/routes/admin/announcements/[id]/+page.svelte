<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';
  import ImageUploadDialog from '$lib/components/wiki/ImageUploadDialog.svelte';

  const id = $page.params.id;
  const isNew = id === 'new';

  let title = $state('');
  let summary = $state('');
  let link = $state('');
  let image_url = $state('');
  let content_html = $state('');
  let pinned = $state(false);
  let published = $state(false);

  let isLoading = $state(!isNew);
  let saving = $state(false);
  let deleting = $state(false);
  let error = $state(null);
  let showImageDialog = $state(false);
  let savedId = $state(isNew ? null : id);

  onMount(async () => {
    if (!isNew) {
      try {
        const response = await fetch(`/api/admin/announcements/${id}`);
        if (!response.ok) throw new Error('Announcement not found');
        const data = await response.json();
        title = data.title || '';
        summary = data.summary || '';
        link = data.link || '';
        image_url = data.image_url || '';
        content_html = data.content_html || '';
        pinned = data.pinned || false;
        published = data.published || false;
      } catch (err) {
        error = err.message;
      } finally {
        isLoading = false;
      }
    }
  });

  async function handleSave() {
    if (!title.trim()) {
      error = 'Title is required';
      return;
    }

    saving = true;
    error = null;

    try {
      const body = {
        title: title.trim(),
        summary: summary.trim() || null,
        link: link.trim() || null,
        image_url: image_url || null,
        content_html: content_html || null,
        pinned,
        published
      };

      let response;
      if (isNew && !savedId) {
        response = await fetch('/api/admin/announcements', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      } else {
        response = await fetch(`/api/admin/announcements/${savedId || id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      }

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Failed to save');

      addToast(isNew && !savedId ? 'Announcement created' : 'Announcement updated', 'success');

      if (isNew && !savedId && data.id) {
        savedId = data.id;
        goto(`/admin/announcements/${data.id}`, { replaceState: true });
      }
    } catch (err) {
      error = err.message;
    } finally {
      saving = false;
    }
  }

  async function handleDelete() {
    if (!confirm('Are you sure you want to delete this announcement?')) return;

    deleting = true;
    error = null;

    try {
      const response = await fetch(`/api/admin/announcements/${savedId || id}`, { method: 'DELETE' });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Failed to delete');
      }
      addToast('Announcement deleted', 'success');
      goto('/admin/announcements');
    } catch (err) {
      error = err.message;
      deleting = false;
    }
  }

  function handleEditorChange(e) {
    content_html = e.detail;
  }

  function handleImageUploaded(event) {
    if (event.detail?.imageUrl) {
      image_url = event.detail.imageUrl;
      addToast('Image uploaded', 'success');
    }
    showImageDialog = false;
  }

  function removeImage() {
    image_url = '';
  }
</script>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span class="separator">/</span>
    <a href="/admin/announcements">Announcements</a>
    <span class="separator">/</span>
    <span>{isNew ? 'New' : 'Edit'}</span>
  </nav>

  <div class="page-header">
    <h1>{isNew && !savedId ? 'New Announcement' : 'Edit Announcement'}</h1>
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  {#if isLoading}
    <div class="loading">Loading...</div>
  {:else}
    <div class="form-card">
      <div class="form-group">
        <label for="title">Title <span class="required">*</span></label>
        <input id="title" type="text" bind:value={title} maxlength="200" placeholder="Announcement title" />
      </div>

      <div class="form-group">
        <label for="summary">Summary</label>
        <textarea id="summary" bind:value={summary} maxlength="500" rows="3" placeholder="Short teaser shown on the landing page news card"></textarea>
        <span class="hint">{summary.length}/500</span>
      </div>

      <div class="form-group">
        <label>Content</label>
        <span class="hint" style="margin-bottom: 0.375rem;">Full article body. Supports rich text formatting. Paste markdown and it will be auto-converted.</span>
        {#await import('$lib/components/wiki/RichTextEditor.svelte') then module}
          <module.default
            content={content_html}
            placeholder="Write announcement content..."
            showHeadings={true}
            showCodeBlock={false}
            showVideo={true}
            showImages={true}
            handleMarkdownPaste={true}
            on:change={handleEditorChange}
          />
        {/await}
      </div>

      <div class="form-group">
        <label>Image</label>
        {#if image_url}
          <div class="image-preview">
            <img src={image_url} alt="Announcement banner" />
            <div class="image-actions">
              <button type="button" class="btn btn-sm" onclick={() => (showImageDialog = true)}>Change</button>
              <button type="button" class="btn btn-sm btn-danger" onclick={removeImage}>Remove</button>
            </div>
          </div>
        {:else if savedId}
          <button type="button" class="btn btn-upload" onclick={() => (showImageDialog = true)}>
            Upload Banner Image
          </button>
          <span class="hint">Recommended: wide banner image (e.g. 1200x630)</span>
        {:else}
          <span class="hint">Save the announcement first to upload an image.</span>
        {/if}
      </div>

      <div class="form-group">
        <label for="link">External Link</label>
        <input id="link" type="url" bind:value={link} placeholder="https://..." />
        <span class="hint">Optional link to an external source. If content is provided, readers can view the article on-site.</span>
      </div>

      <div class="form-row-toggles">
        <label class="toggle-label">
          <input type="checkbox" bind:checked={pinned} />
          <span>Pinned</span>
          <span class="hint-inline">Stays at the top of the news feed</span>
        </label>

        <label class="toggle-label">
          <input type="checkbox" bind:checked={published} />
          <span>Published</span>
          <span class="hint-inline">Visible on the landing page</span>
        </label>
      </div>

      <div class="form-actions">
        <button class="btn btn-cancel" onclick={() => goto('/admin/announcements')}>
          Cancel
        </button>

        {#if !isNew}
          <button class="btn btn-danger" onclick={handleDelete} disabled={deleting}>
            {deleting ? 'Deleting...' : 'Delete'}
          </button>
        {/if}

        <button class="btn btn-primary" onclick={handleSave} disabled={saving || !title.trim()}>
          {saving ? 'Saving...' : isNew && !savedId ? 'Create' : 'Save'}
        </button>
      </div>
    </div>
  {/if}
</div>

{#if savedId}
  <ImageUploadDialog
    open={showImageDialog}
    entityType="announcement"
    entityId={savedId}
    entityName={title || 'Announcement'}
    showDelete={!!image_url}
    hasImage={!!image_url}
    aspect={1.9}
    maxWidth={1200}
    maxHeight={630}
    on:close={() => (showImageDialog = false)}
    on:uploaded={handleImageUploaded}
    on:deleted={() => {
      image_url = '';
      showImageDialog = false;
      addToast('Image removed', 'success');
    }}
  />
{/if}

<style>
  .page-container {
    max-width: 900px;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .separator {
    color: var(--text-muted);
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    margin: 0;
  }

  .error-banner {
    background: var(--error-bg);
    color: var(--error-color);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    border: 1px solid var(--error-color);
    margin-bottom: 1rem;
  }

  .loading {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .form-card {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
  }

  .form-group {
    margin-bottom: 1.25rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.375rem;
    font-weight: 500;
    font-size: 0.875rem;
  }

  .required {
    color: var(--error-color);
  }

  .form-group input,
  .form-group textarea {
    width: 100%;
    padding: 0.5rem;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.875rem;
    box-sizing: border-box;
  }

  .form-group input:focus,
  .form-group textarea:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .hint {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
  }

  .image-preview {
    margin-top: 0.5rem;
    border-radius: 6px;
    overflow: hidden;
    max-width: 600px;
    border: 1px solid var(--border-color);
  }

  .image-preview img {
    width: 100%;
    display: block;
  }

  .image-actions {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem;
    background-color: var(--tertiary-color);
  }

  .btn-upload {
    padding: 0.5rem 1rem;
    background-color: var(--secondary-color);
    border: 1px dashed var(--border-color);
    color: var(--text-color);
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.875rem;
    transition: all 0.15s;
  }

  .btn-upload:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .form-row-toggles {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }

  .toggle-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    font-size: 0.875rem;
  }

  .toggle-label input[type="checkbox"] {
    width: 1rem;
    height: 1rem;
    accent-color: var(--accent-color);
  }

  .hint-inline {
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .btn {
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn.btn-sm {
    padding: 0.25rem 0.75rem;
    font-size: 0.8125rem;
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-cancel {
    background-color: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-cancel:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .btn-primary {
    background-color: var(--accent-color);
    border: 1px solid var(--accent-color);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover);
  }

  .btn-danger {
    background-color: var(--error-color);
    border: 1px solid var(--error-color);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    filter: brightness(0.9);
  }

  @media (max-width: 899px) {
    .form-actions {
      flex-direction: column;
    }

    .form-actions .btn {
      width: 100%;
      text-align: center;
    }
  }
</style>
