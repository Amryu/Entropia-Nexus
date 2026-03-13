<!--
  @component ImageUploader
  Entity icon upload with client-side cropping and upload to server.
  Shows current image, allows selection and cropping of new image.
-->
<script>
  // @ts-nocheck
  import ImageCropper from './ImageCropper.svelte';

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string|null} [currentImage]
   * @property {string} [entityType]
   * @property {number|string} [entityId]
   * @property {boolean} [editable]
   * @property {number} [maxSizeMB]
   * @property {(data: any) => void} [onupload]
   */

  /** @type {Props} */
  let {
    currentImage = null,
    entityType = '',
    entityId = '',
    editable = false,
    maxSizeMB = 2,
    onupload
  } = $props();

  // Component state
  let fileInput = $state();
  let selectedImage = $state(null);
  let isCropping = $state(false);
  let isUploading = $state(false);
  let uploadError = $state(null);
  let cropperRef = $state();

  // Computed max size in bytes
  let maxSizeBytes = $derived(maxSizeMB * 1024 * 1024);

  function handleFileSelect(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      uploadError = 'Please select an image file';
      return;
    }

    // Validate file size
    if (file.size > maxSizeBytes) {
      uploadError = `Image must be smaller than ${maxSizeMB}MB`;
      return;
    }

    uploadError = null;

    // Read the file as data URL
    const reader = new FileReader();
    reader.onload = (e) => {
      selectedImage = e.target.result;
      isCropping = true;
    };
    reader.readAsDataURL(file);

    // Reset input so same file can be selected again
    event.target.value = '';
  }

  function handleDrop(event) {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (file && file.type.startsWith('image/')) {
      // Create a synthetic event object
      handleFileSelect({ target: { files: [file] } });
    }
  }

  function handleDragOver(event) {
    event.preventDefault();
  }

  async function handleCropConfirm() {
    if (!cropperRef) return;

    try {
      isUploading = true;
      uploadError = null;

      // Get the cropped image blob
      const blob = await cropperRef.getCroppedImage();
      if (!blob) {
        throw new Error('Failed to crop image');
      }

      // Create form data
      const formData = new FormData();
      formData.append('image', blob, 'icon.png');
      formData.append('entityType', entityType);
      formData.append('entityId', String(entityId));

      // Upload to server
      const response = await fetch('/api/uploads/entity-image', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || 'Upload failed');
      }

      const result = await response.json();

      // Notify parent of successful upload
      onupload?.({
        tempPath: result.tempPath,
        previewUrl: result.previewUrl
      });

      // Reset state
      isCropping = false;
      selectedImage = null;
    } catch (error) {
      uploadError = error.message || 'Upload failed';
    } finally {
      isUploading = false;
    }
  }

  function handleCropCancel() {
    isCropping = false;
    selectedImage = null;
    uploadError = null;
  }

  function openFileDialog() {
    fileInput?.click();
  }
</script>

<div class="image-uploader">
  {#if isCropping}
    <div class="cropper-wrapper">
      <ImageCropper
        bind:this={cropperRef}
        image={selectedImage}
        onconfirm={handleCropConfirm}
        oncancel={handleCropCancel}
      />
      {#if isUploading}
        <div class="upload-overlay">
          <div class="spinner"></div>
          <span>Uploading...</span>
        </div>
      {/if}
    </div>
  {:else}
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -- tabindex is conditional: set to 0 when editable (role=button), -1 otherwise (role=img) -->
    <div
      class="image-preview"
      class:editable
      onclick={editable ? openFileDialog : null}
      onkeydown={editable ? (e) => e.key === 'Enter' && openFileDialog() : null}
      ondrop={editable ? handleDrop : null}
      ondragover={editable ? handleDragOver : null}
      role={editable ? 'button' : 'img'}
      tabindex={editable ? 0 : -1}
    >
      {#if currentImage}
        <img src={currentImage} alt="Entity icon" />
      {:else}
        <div class="placeholder">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
            <circle cx="8.5" cy="8.5" r="1.5"/>
            <polyline points="21 15 16 10 5 21"/>
          </svg>
          {#if editable}
            <span>Click or drag to upload</span>
          {:else}
            <span>No image</span>
          {/if}
        </div>
      {/if}

      {#if editable && currentImage}
        <div class="edit-overlay">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <span>Change</span>
        </div>
      {/if}
    </div>
  {/if}

  {#if uploadError}
    <div class="error-message">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <line x1="12" y1="16" x2="12.01" y2="16"/>
      </svg>
      {uploadError}
    </div>
  {/if}

  <input
    bind:this={fileInput}
    type="file"
    accept="image/*"
    onchange={handleFileSelect}
    class="hidden-input"
  />
</div>

<style>
  .image-uploader {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .hidden-input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }

  .image-preview {
    position: relative;
    width: 128px;
    height: 128px;
    border-radius: 8px;
    overflow: hidden;
    background-color: var(--secondary-color, #2a2a2a);
    border: 2px solid var(--border-color, #555);
  }

  .image-preview.editable {
    cursor: pointer;
    border-style: dashed;
  }

  .image-preview.editable:hover {
    border-color: var(--accent-color, #4a9eff);
  }

  .image-preview.editable:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
    box-shadow: 0 0 0 3px rgba(74, 158, 255, 0.2);
  }

  .image-preview img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: 12px;
    color: var(--text-muted, #999);
    text-align: center;
  }

  .placeholder svg {
    margin-bottom: 8px;
    opacity: 0.5;
  }

  .placeholder span {
    font-size: 11px;
    line-height: 1.3;
  }

  .edit-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background-color: rgba(0, 0, 0, 0.7);
    color: white;
    opacity: 0;
    transition: opacity 0.15s;
  }

  .image-preview.editable:hover .edit-overlay,
  .image-preview.editable:focus .edit-overlay {
    opacity: 1;
  }

  .edit-overlay svg {
    margin-bottom: 4px;
  }

  .edit-overlay span {
    font-size: 12px;
    font-weight: 500;
  }

  .cropper-wrapper {
    position: relative;
  }

  .upload-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    background-color: rgba(0, 0, 0, 0.7);
    color: white;
    border-radius: 8px;
    z-index: 10;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .error-message {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error-color, #ef4444);
    border-radius: 6px;
    color: var(--error-color, #ef4444);
    font-size: 13px;
  }

  /* Mobile - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .image-preview {
      width: 100px;
      height: 100px;
    }
  }
</style>
