<script>
  //@ts-nocheck
  import { apiDelete, navigate } from "$lib/util";

  /**
   * @typedef {Object} Props
   * @property {any} mode
   * @property {any} user
   * @property {any} title
   * @property {any} description
   * @property {any} change
   * @property {boolean} [editable]
   * @property {boolean} [ownershipBasedEditing]
   * @property {boolean} [canEdit]
   * @property {any} [entityType] - New prop to identify entity type
   * @property {any} [object] - Current object for permission checks
   */

  /** @type {Props} */
  let {
    mode,
    user,
    title,
    description,
    change,
    editable = true,
    ownershipBasedEditing = false,
    canEdit = true,
    entityType = null,
    object = null
  } = $props();

  function deleteChange() {
    if (confirm('Are you sure you want to delete this change?')) {
      apiDelete(fetch, '/api/changes/' + change.id, window.location.origin)
        .then(() => {
          navigate(window.location.pathname);
        })
        .catch(error => {
          console.error(error);
        });
    }
  }
</script>

<style>
  .title-wrapper {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 10px;
    align-items: center;
  }

  .title-buttons > button {
    width: 64px;
    height: 64px;
    margin-left: 12px;
    font-size: 24px;
  }
</style>

<div class="title-wrapper">
  <h1 style={mode === 'preview' ? 'color: yellow; text-decoration: underline dashed;' : null} title={mode === 'preview' ? 'Watching preview of change.' : null}>{title}</h1>
  <div class="title-buttons">
    {#if editable}
      {#if mode !== 'edit' && mode !== 'history' && mode !== 'create' && mode !== 'edit-inventory' && mode !== 'edit-managers'}
        <button onclick={() => navigate(window.location.pathname + '?mode=edit')} 
                title={user == null ? "Log in to edit" : !user.verified ? "Verify to edit" : ownershipBasedEditing && !canEdit ? "Only owner/managers can edit" : 'Edit'} 
                disabled={user == null || !user.verified || (ownershipBasedEditing && !canEdit)}>✏️</button>
      {/if}
      
      {#if entityType === 'Shop' && mode !== 'edit' && mode !== 'history' && mode !== 'create' && mode !== 'edit-inventory' && mode !== 'edit-managers'}
        {#if object && user && (object.OwnerId === user.id || user.grants?.includes('admin.panel'))}
          <button onclick={() => navigate(window.location.pathname + '?mode=edit-managers')} 
                  title={user == null ? "Log in to edit" : !user.verified ? "Verify to edit" : "Edit Managers"} 
                  disabled={user == null || !user.verified}>👥</button>
        {/if}
        <button onclick={() => navigate(window.location.pathname + '?mode=edit-inventory')} 
                title={user == null ? "Log in to edit" : !user.verified ? "Verify to edit" : ownershipBasedEditing && !canEdit ? "Only owner/managers can edit" : 'Edit Inventory'} 
                disabled={user == null || !user.verified || (ownershipBasedEditing && !canEdit)}>📦</button>
      {/if}
      
      {#if mode === 'edit-inventory' || mode === 'edit-managers'}
        <button onclick={() => navigate(window.location.pathname)} title="Return">↩</button>
      {:else if mode === 'preview' || mode === 'edit' || mode === 'history' || mode === 'create'}
        <button onclick={() => navigate(window.location.pathname)} title="Cancel">❌</button>
      {/if}
      {#if (mode === 'edit' || mode === 'create') && change?.id && user != null && user.verified}
        <button onclick={deleteChange} title="Delete this Change">🗑️</button>
      {/if}
    {/if}
  </div>
</div>
{#if description}
  <br />
  <p>{description}</p>
{/if}
