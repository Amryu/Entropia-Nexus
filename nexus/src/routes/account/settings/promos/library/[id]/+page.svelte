<!--
  @component Promo Editor
  Create or edit a promo with type selector, name, images, and featured post fields.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { goto, invalidateAll } from '$app/navigation';
  import { addToast } from '$lib/stores/toasts';

  let { data } = $props();

  let isNew = $derived(data.isNew);
  let saving = $state(false);

  // Form fields
  let promoType = $state(data.promo?.promo_type ?? 'placement');
  let name = $state(data.promo?.name ?? '');
  let title = $state(data.promo?.title ?? '');
  let summary = $state(data.promo?.summary ?? '');
  let link = $state(data.promo?.link ?? '');

  // Images from server
  let serverImages = $derived(data.images ?? []);

  // Image upload states
  let uploadingSlot = $state(null);

  const PLACEMENT_VARIANTS = [
    { key: 'vertical', label: 'Vertical (160x600)', width: 160, height: 600 },
    { key: 'horizontal', label: 'Horizontal (728x90)', width: 728, height: 90 }
  ];

  function getImageUrl(variant) {
    const img = serverImages.find(i => i.slot_variant === variant);
    if (!img) return null;
    return img.image_path;
  }

  async function uploadImage(variant) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/webp';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;

      if (!data.promo?.id) {
        addToast('Save the promo first before uploading images', 'error');
        return;
      }

      uploadingSlot = variant;
      try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('entityType', 'promo-visual');
        formData.append('entityId', `${data.promo.id}-${variant}`);

        const res = await fetch('/api/uploads/entity-image', {
          method: 'POST',
          body: formData
        });

        if (!res.ok) {
          const err = await res.json().catch(() => null);
          addToast(err?.error || 'Image upload failed', 'error');
          return;
        }

        addToast('Image uploaded', 'success');
        await invalidateAll();
      } catch {
        addToast('Network error during upload', 'error');
      } finally {
        uploadingSlot = null;
      }
    };
    input.click();
  }

  async function savePromo() {
    if (!name.trim()) {
      addToast('Promo name is required', 'error');
      return;
    }

    saving = true;
    try {
      const body = {
        name: name.trim(),
        title: title.trim() || null,
        summary: summary.trim() || null,
        link: link.trim() || null
      };

      let res;
      if (isNew) {
        body.promo_type = promoType;
        res = await fetch('/api/promos', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      } else {
        res = await fetch(`/api/promos/${data.promo.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
      }

      const result = await res.json();
      if (!res.ok) {
        addToast(result?.error || 'Failed to save promo', 'error');
        return;
      }

      addToast(isNew ? 'Promo created' : 'Promo updated', 'success');

      if (isNew) {
        goto(`/account/settings/promos/library/${result.id}`);
      } else {
        await invalidateAll();
      }
    } catch {
      addToast('Network error', 'error');
    } finally {
      saving = false;
    }
  }
</script>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/account">Account</a>
      <span>/</span>
      <a href="/account/settings/promos">Promos</a>
      <span>/</span>
      <a href="/account/settings/promos/library">Library</a>
      <span>/</span>
      <span>{isNew ? 'New' : 'Edit'}</span>
    </div>

    <h1>{isNew ? 'Create Promo' : 'Edit Promo'}</h1>

    <div class="form-section">
      <label class="form-label">
        Promo Type
        {#if isNew}
          <select class="form-select" bind:value={promoType}>
            <option value="placement">Placement (banner ad)</option>
            <option value="featured_post">Featured Post</option>
          </select>
        {:else}
          <input class="form-input" value={promoType === 'placement' ? 'Placement' : 'Featured Post'} disabled />
        {/if}
      </label>

      <label class="form-label">
        Name <span class="required">*</span>
        <input class="form-input" type="text" bind:value={name} maxlength="100" placeholder="My Promo" />
      </label>

      {#if promoType === 'featured_post'}
        <label class="form-label">
          Title
          <input class="form-input" type="text" bind:value={title} maxlength="200" placeholder="Featured post title" />
        </label>

        <label class="form-label">
          Summary
          <textarea class="form-textarea" bind:value={summary} maxlength="500" rows="3" placeholder="Short description of the featured post"></textarea>
        </label>
      {/if}

      <label class="form-label">
        Link
        <input class="form-input" type="url" bind:value={link} maxlength="500" placeholder="https://example.com" />
      </label>
    </div>

    {#if !isNew && promoType === 'placement'}
      <div class="form-section">
        <h2>Ad Images</h2>
        <p class="section-hint">Upload banner images for each placement size. Save the promo first to enable uploads.</p>

        <div class="image-slots">
          {#each PLACEMENT_VARIANTS as variant}
            <div class="image-slot">
              <div class="slot-header">
                <span class="slot-label">{variant.label}</span>
              </div>
              <div class="slot-preview" style="aspect-ratio: {variant.width}/{variant.height}; max-width: {Math.min(variant.width, 400)}px;">
                {#if getImageUrl(variant.key)}
                  <img src={getImageUrl(variant.key)} alt="{variant.label} preview" />
                {:else}
                  <div class="slot-placeholder">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                    <span>{variant.width} x {variant.height}</span>
                  </div>
                {/if}
              </div>
              <button
                class="btn-secondary upload-btn"
                disabled={uploadingSlot === variant.key}
                onclick={() => uploadImage(variant.key)}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                {uploadingSlot === variant.key ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <div class="form-actions">
      <a href="/account/settings/promos/library" class="btn-secondary">Cancel</a>
      <button class="btn-primary" disabled={saving} onclick={savePromo}>
        {#if saving}
          Saving...
        {:else if isNew}
          Create Promo
        {:else}
          Save Changes
        {/if}
      </button>
    </div>
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 700px;
    margin: 0 auto;
    padding: 1.5rem;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  h1 {
    margin: 0 0 1.5rem;
    font-size: 1.75rem;
    color: var(--text-color);
  }

  h2 {
    margin: 0 0 0.5rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .form-section {
    margin-bottom: 2rem;
  }

  .form-label {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-color);
    margin-bottom: 1rem;
  }

  .required {
    color: #ef4444;
  }

  .form-input,
  .form-select,
  .form-textarea {
    padding: 0.5rem 0.75rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 0.875rem;
    font-family: inherit;
  }

  .form-input:focus,
  .form-select:focus,
  .form-textarea:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .form-input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .form-textarea {
    resize: vertical;
    min-height: 80px;
  }

  .section-hint {
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin: 0 0 1rem;
  }

  .image-slots {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .image-slot {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .slot-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .slot-label {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-color);
  }

  .slot-preview {
    background: var(--secondary-color);
    border: 1px dashed var(--border-color);
    border-radius: 6px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .slot-preview img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .slot-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.375rem;
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .upload-btn {
    align-self: flex-start;
  }

  .form-actions {
    display: flex;
    gap: 0.75rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .btn-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.5rem 1.25rem;
    background: var(--accent-color);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.5rem 1rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    font-size: 0.875rem;
    text-decoration: none;
    cursor: pointer;
    transition: border-color 0.15s;
  }

  .btn-secondary:hover {
    border-color: var(--accent-color);
  }

  .btn-secondary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 768px) {
    .form-actions {
      flex-direction: column;
    }
  }
</style>
