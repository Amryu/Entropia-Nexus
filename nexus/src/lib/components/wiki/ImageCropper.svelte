<!--
  @component ImageCropper
  Square cropping UI for entity icons using svelte-easy-crop.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { browser } from '$app/environment';
  import Cropper from 'svelte-easy-crop';

  const dispatch = createEventDispatcher();

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string} [image]
   * @property {number} [aspect]
   * @property {number} [minZoom]
   * @property {number} [maxZoom]
   */

  /** @type {Props} */
  let {
    image = '',
    aspect = 1,
    minZoom = 1,
    maxZoom = 3
  } = $props();

  let crop = $state({ x: 0, y: 0 });
  let zoom = $state(1);
  let croppedAreaPixels = null;

  function handleCropComplete(event) {
    croppedAreaPixels = event.detail.pixels;
  }

  /**
   * Get the cropped image as a blob
   * @returns {Promise<Blob>}
   */
  export async function getCroppedImage() {
    if (!croppedAreaPixels || !image) {
      return null;
    }

    return createCroppedImage(image, croppedAreaPixels);
  }

  /**
   * Create a cropped image from the source and crop area
   * @param {string} imageSrc
   * @param {object} pixelCrop
   * @returns {Promise<Blob>}
   */
  async function createCroppedImage(imageSrc, pixelCrop) {
    if (!browser) {
      return Promise.reject(new Error('Image cropping only available in browser'));
    }

    const img = await loadImage(imageSrc);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    // Set canvas size to the cropped area
    canvas.width = pixelCrop.width;
    canvas.height = pixelCrop.height;

    // Draw the cropped portion
    ctx.drawImage(
      img,
      pixelCrop.x,
      pixelCrop.y,
      pixelCrop.width,
      pixelCrop.height,
      0,
      0,
      pixelCrop.width,
      pixelCrop.height
    );

    // Return as blob
    return new Promise((resolve) => {
      canvas.toBlob((blob) => {
        resolve(blob);
      }, 'image/png', 1);
    });
  }

  /**
   * Load an image from a URL
   * @param {string} src
   * @returns {Promise<HTMLImageElement>}
   */
  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = src;
    });
  }

  function handleConfirm() {
    dispatch('confirm');
  }

  function handleCancel() {
    dispatch('cancel');
  }
</script>

<div class="image-cropper">
  <div class="cropper-container">
    {#if image}
      <Cropper
        {image}
        bind:crop
        bind:zoom
        {aspect}
        {minZoom}
        {maxZoom}
        on:cropcomplete={handleCropComplete}
      />
    {:else}
      <div class="no-image">No image selected</div>
    {/if}
  </div>

  <div class="controls">
    <div class="zoom-control">
      <label for="zoom-slider">Zoom</label>
      <input
        id="zoom-slider"
        type="range"
        min={minZoom}
        max={maxZoom}
        step="0.1"
        bind:value={zoom}
      />
      <span class="zoom-value">{zoom.toFixed(1)}x</span>
    </div>

    <div class="actions">
      <button type="button" class="btn-secondary" onclick={handleCancel}>
        Cancel
      </button>
      <button type="button" class="btn-primary" onclick={handleConfirm}>
        Crop Image
      </button>
    </div>
  </div>
</div>

<style>
  .image-cropper {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .cropper-container {
    position: relative;
    width: 100%;
    height: 300px;
    background-color: var(--primary-color, #1a1a1a);
    border-radius: 8px;
    overflow: hidden;
  }

  .no-image {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted, #999);
    font-size: 14px;
  }

  .controls {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .zoom-control {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .zoom-control label {
    font-size: 13px;
    color: var(--text-muted, #999);
    min-width: 40px;
  }

  .zoom-control input[type="range"] {
    flex: 1;
    height: 4px;
    appearance: none;
    background: var(--border-color, #555);
    border-radius: 2px;
    cursor: pointer;
  }

  .zoom-control input[type="range"]::-webkit-slider-thumb {
    appearance: none;
    width: 16px;
    height: 16px;
    background: var(--accent-color, #4a9eff);
    border-radius: 50%;
    cursor: pointer;
  }

  .zoom-control input[type="range"]::-moz-range-thumb {
    width: 16px;
    height: 16px;
    background: var(--accent-color, #4a9eff);
    border-radius: 50%;
    border: none;
    cursor: pointer;
  }

  .zoom-value {
    font-size: 13px;
    color: var(--text-color, #fff);
    min-width: 40px;
    text-align: right;
  }

  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .actions button {
    padding: 10px 20px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-primary {
    background-color: var(--accent-color, #4a9eff);
    border: none;
    color: white;
  }

  .btn-primary:hover {
    filter: brightness(1.1);
  }

  .btn-secondary {
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-color, #fff);
  }

  .btn-secondary:hover {
    background-color: var(--hover-color, #444);
  }

  /* Mobile - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .cropper-container {
      height: 250px;
    }

    .actions {
      flex-direction: column;
    }

    .actions button {
      width: 100%;
    }
  }
</style>
