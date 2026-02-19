<script>
  // @ts-nocheck
  import { enhance } from '$app/forms';
  import { encodeURIComponentSafe } from '$lib/util';

  export let data;
  export let form;

  $: pendingImages = data.pendingImages || [];
  $: approvedImages = data.approvedImages || [];

  // Tab state
  let activeTab = 'pending';

  function formatDate(isoString) {
    if (!isoString) return 'Unknown';
    const date = new Date(isoString);
    return date.toLocaleString();
  }

  // Map entity type to URL base path
  const ENTITY_TYPE_PATHS = {
    'weapon': '/items/weapons',
    'mob': '/information/mobs',
    'armorset': '/items/armorsets',
    'material': '/items/materials',
    'blueprint': '/items/blueprints',
    'skill': '/information/skills',
    'profession': '/information/professions',
    'vendor': '/information/vendors',
    'clothing': '/items/clothing',
    'consumable': '/items/consumables/stimulants',
    'capsule': '/items/consumables/capsules',
    'medicaltool': '/items/medicaltools/tools',
    'medicalchip': '/items/medicaltools/chips',
    'vehicle': '/items/vehicles',
    'pet': '/items/pets',
    'strongbox': '/items/strongboxes',
    'shop': '/market/shops',
    // Tools subtypes
    'refiner': '/items/tools/refiners',
    'scanner': '/items/tools/scanners',
    'finder': '/items/tools/finders',
    'excavator': '/items/tools/excavators',
    'teleportationchip': '/items/tools/teleportationchips',
    'effectchip': '/items/tools/effectchips',
    'misctool': '/items/tools/misctools',
    // Attachment subtypes
    'weaponamplifier': '/items/attachments/weaponamplifiers',
    'weaponvisionattachment': '/items/attachments/weaponvisionattachments',
    'absorber': '/items/attachments/absorbers',
    'armorplating': '/items/attachments/armorplatings',
    'finderamplifier': '/items/attachments/finderamplifiers',
    'enhancer': '/items/attachments/enhancers',
    'mindforceimplant': '/items/attachments/mindforceimplants',
    // Furnishing subtypes
    'furniture': '/items/furnishings/furniture',
    'decoration': '/items/furnishings/decorations',
    'storagecontainer': '/items/furnishings/storagecontainers',
    'sign': '/items/furnishings/signs'
  };

  function getEntityLink(entityType, entityName, isNameResolved) {
    if (!isNameResolved) return null;
    const basePath = ENTITY_TYPE_PATHS[entityType.toLowerCase()];
    if (!basePath) return null;
    return `${basePath}/${encodeURIComponentSafe(entityName)}`;
  }

  function confirmDelete(event, linkCount = 0) {
    let message = 'Are you sure you want to delete this image? This action cannot be undone.';
    if (linkCount > 0) {
      message = `Warning: ${linkCount} other ${linkCount === 1 ? 'entity relies' : 'entities rely'} on this image via linking. Deleting it will break ${linkCount === 1 ? 'that image' : 'those images'} too.\n\n${message}`;
    }
    if (!confirm(message)) {
      event.preventDefault();
    }
  }
</script>

<svelte:head>
  <title>Images | Admin</title>
</svelte:head>

<div class="images-page">
  <nav class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Images</span>
  </nav>

  <header class="page-header">
    <h1>Image Management</h1>
    <p class="subtitle">Review pending uploads and manage approved images</p>
  </header>

  {#if form?.error}
    <div class="alert alert-error">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="8" x2="12" y2="12"/>
        <circle cx="12" cy="16" r="1" fill="currentColor"/>
      </svg>
      {form.error}
    </div>
  {/if}

  {#if form?.success}
    <div class="alert alert-success">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>
      Image {form.action} successfully
    </div>
  {/if}

  <!-- Tabs -->
  <div class="tabs">
    <button
      class="tab"
      class:active={activeTab === 'pending'}
      on:click={() => activeTab = 'pending'}
    >
      Pending
      {#if pendingImages.length > 0}
        <span class="badge pending">{pendingImages.length}</span>
      {/if}
    </button>
    <button
      class="tab"
      class:active={activeTab === 'approved'}
      on:click={() => activeTab = 'approved'}
    >
      Approved
      {#if approvedImages.length > 0}
        <span class="badge">{approvedImages.length}</span>
      {/if}
    </button>
  </div>

  <!-- Pending Images Tab -->
  {#if activeTab === 'pending'}
    {#if pendingImages.length === 0}
      <div class="empty-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <circle cx="8.5" cy="8.5" r="1.5"/>
          <polyline points="21 15 16 10 5 21"/>
        </svg>
        <h3>No Pending Images</h3>
        <p>All uploaded images have been reviewed.</p>
      </div>
    {:else}
      <div class="images-grid">
        {#each pendingImages as image}
          <div class="image-card">
            <div class="image-preview">
              <img src={image.previewUrl} alt="Pending upload" />
            </div>

            <div class="image-info">
              <div class="info-row">
                <span class="label">Entity:</span>
                {#if getEntityLink(image.entityType, image.entityName, image.isNameResolved)}
                  <a href={getEntityLink(image.entityType, image.entityName, image.isNameResolved)} class="value link entity-link">
                    {image.entityName}
                  </a>
                {:else}
                  <span class="value entity-link">{image.entityName}</span>
                {/if}
              </div>
              <div class="info-row">
                <span class="label">Type:</span>
                <span class="value type-value">{image.entityType}</span>
              </div>
              <div class="info-row">
                <span class="label">Uploaded by:</span>
                {#if image.uploaderProfile}
                  <a class="value link" href={`/admin/users/${encodeURIComponentSafe(image.uploaderProfile)}`}>
                    {image.uploaderName}
                  </a>
                {:else}
                  <span class="value">{image.uploaderName}</span>
                {/if}
              </div>
              <div class="info-row">
                <span class="label">Uploaded:</span>
                <span class="value">{formatDate(image.uploadedAt)}</span>
              </div>
            </div>

            <div class="image-actions">
              <form method="POST" action="?/approve" use:enhance>
                <input type="hidden" name="entityType" value={image.entityType} />
                <input type="hidden" name="entityId" value={image.entityId} />
                <button type="submit" class="btn btn-approve">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                  Approve
                </button>
              </form>

              <form method="POST" action="?/deny" use:enhance>
                <input type="hidden" name="entityType" value={image.entityType} />
                <input type="hidden" name="entityId" value={image.entityId} />
                <button type="submit" class="btn btn-deny">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                  Deny
                </button>
              </form>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}

  <!-- Approved Images Tab -->
  {#if activeTab === 'approved'}
    {#if approvedImages.length === 0}
      <div class="empty-state">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
          <circle cx="8.5" cy="8.5" r="1.5"/>
          <polyline points="21 15 16 10 5 21"/>
        </svg>
        <h3>No Approved Images</h3>
        <p>No images have been approved yet.</p>
      </div>
    {:else}
      <div class="images-grid">
        {#each approvedImages as image}
          <div class="image-card approved">
            <div class="image-preview">
              <img src={image.imageUrl} alt="Approved image" />
            </div>

            <div class="image-info">
              <div class="info-row">
                <span class="label">Entity:</span>
                {#if getEntityLink(image.entityType, image.entityName, image.isNameResolved)}
                  <a href={getEntityLink(image.entityType, image.entityName, image.isNameResolved)} class="value link entity-link">
                    {image.entityName}
                  </a>
                {:else}
                  <span class="value entity-link">{image.entityName}</span>
                {/if}
              </div>
              <div class="info-row">
                <span class="label">Type:</span>
                <span class="value type-value">{image.entityType}</span>
              </div>
              {#if image.linkedFrom}
                <div class="info-row">
                  <span class="label">Linked from:</span>
                  <span class="value">{image.linkedFrom.entityType}/{image.linkedFrom.entityId}</span>
                </div>
              {/if}
              {#if image.linkCount > 0}
                <div class="info-row">
                  <span class="label">Used by:</span>
                  <span class="value link-count">{image.linkCount} other {image.linkCount === 1 ? 'entity' : 'entities'}</span>
                </div>
              {/if}
              {#if image.approvedAt}
                <div class="info-row">
                  <span class="label">Approved:</span>
                  <span class="value">{formatDate(image.approvedAt)}</span>
                </div>
              {/if}
            </div>

            <div class="image-actions single">
              <form method="POST" action="?/delete" use:enhance on:submit={(e) => confirmDelete(e, image.linkCount)}>
                <input type="hidden" name="entityType" value={image.entityType} />
                <input type="hidden" name="entityId" value={image.entityId} />
                <button type="submit" class="btn btn-delete">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    <line x1="10" y1="11" x2="10" y2="17"/>
                    <line x1="14" y1="11" x2="14" y2="17"/>
                  </svg>
                  Delete
                </button>
              </form>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .images-page {
    max-width: 1200px;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .breadcrumb span {
    color: var(--text-muted);
  }

  .page-header {
    margin-bottom: 24px;
  }

  .page-header h1 {
    margin: 0 0 8px 0;
    font-size: 24px;
    font-weight: 600;
    color: var(--text-color);
  }

  .subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 14px;
  }

  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 24px;
    border-bottom: 1px solid var(--border-color);
  }

  .tab {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 20px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    margin-bottom: -1px;
  }

  .tab:hover {
    color: var(--text-color);
  }

  .tab.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
  }

  .badge {
    padding: 2px 8px;
    background-color: var(--hover-color);
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
  }

  .badge.pending {
    background-color: rgba(245, 158, 11, 0.2);
    color: var(--warning-color, #f59e0b);
  }

  .alert {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 20px;
    font-size: 14px;
  }

  .alert-error {
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error-color, #ef4444);
    color: var(--error-color, #ef4444);
  }

  .alert-success {
    background-color: rgba(74, 222, 128, 0.1);
    border: 1px solid var(--success-color, #4ade80);
    color: var(--success-color, #4ade80);
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;
    color: var(--text-muted);
  }

  .empty-state svg {
    margin-bottom: 16px;
    opacity: 0.5;
  }

  .empty-state h3 {
    margin: 0 0 8px 0;
    font-size: 18px;
    color: var(--text-color);
  }

  .empty-state p {
    margin: 0;
    font-size: 14px;
  }

  .images-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 20px;
  }

  .image-card {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .image-card.approved {
    border-color: rgba(74, 222, 128, 0.3);
  }

  .image-preview {
    aspect-ratio: 1;
    background-color: var(--primary-color);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .image-preview img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .image-info {
    padding: 12px 16px;
    border-top: 1px solid var(--border-color);
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    font-size: 13px;
  }

  .info-row:not(:last-child) {
    border-bottom: 1px solid var(--border-color);
  }

  .label {
    color: var(--text-muted);
  }

  .value {
    color: var(--text-color);
    font-weight: 500;
  }

  .value.link {
    color: var(--accent-color);
    text-decoration: none;
  }

  .value.link:hover {
    text-decoration: underline;
  }

  .value.entity-link {
    font-weight: 600;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .value.type-value {
    text-transform: capitalize;
  }

  .value.link-count {
    color: var(--accent-color);
  }

  .image-actions {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--border-color);
  }

  .image-actions.single {
    justify-content: center;
  }

  .image-actions form {
    flex: 1;
  }

  .image-actions.single form {
    flex: none;
    width: 50%;
  }

  .btn {
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 16px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-approve {
    background-color: var(--success-color, #4ade80);
    color: white;
  }

  .btn-approve:hover {
    filter: brightness(1.1);
  }

  .btn-deny {
    background-color: var(--error-color, #ef4444);
    color: white;
  }

  .btn-deny:hover {
    filter: brightness(1.1);
  }

  .btn-delete {
    background-color: transparent;
    border: 1px solid var(--error-color, #ef4444);
    color: var(--error-color, #ef4444);
  }

  .btn-delete:hover {
    background-color: var(--error-color, #ef4444);
    color: white;
  }

  @media (max-width: 767px) {
    .tabs {
      overflow-x: auto;
    }

    .tab {
      padding: 10px 16px;
      white-space: nowrap;
    }

    .images-grid {
      grid-template-columns: 1fr;
    }

    .image-actions {
      flex-direction: column;
    }

    .image-actions.single form {
      width: 100%;
    }

    .breadcrumb {
      font-size: 12px;
    }
  }
</style>
