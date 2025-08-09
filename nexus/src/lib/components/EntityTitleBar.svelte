<script>
  //@ts-nocheck
  import { apiDelete, navigate } from "$lib/util";

  export let mode;
  export let user;
  export let title;
  export let description;
  export let change;
  export let editable = true;
  export let ownershipBasedEditing = false;
  export let canEdit = true;
  export let entityType = null; // New prop to identify entity type
  export let object = null; // Current object for permission checks

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
      {#if mode !== 'edit' && mode !== 'history' && mode !== 'create' && mode !== 'manage-inventory' && mode !== 'manage-managers'}
        <button on:click={() => navigate(window.location.pathname + '?mode=history')} title="View History">📄</button>
      {/if}
      {#if mode !== 'edit' && mode !== 'history' && mode !== 'create' && mode !== 'manage-inventory' && mode !== 'manage-managers'}
        <button on:click={() => navigate(window.location.pathname + '?mode=edit')} 
                title={user == null ? "Log in to edit" : !user.verified ? "Verify to edit" : ownershipBasedEditing && !canEdit ? "Only owner/managers can edit" : 'Edit'} 
                disabled={user == null || !user.verified || (ownershipBasedEditing && !canEdit)}>✏️</button>
      {/if}
      
      {#if entityType === 'Shop' && mode !== 'edit' && mode !== 'history' && mode !== 'create' && mode !== 'manage-inventory' && mode !== 'manage-managers'}
        {#if object && user && (object.OwnerId === user.id || user.administrator)}
          <button on:click={() => navigate(window.location.pathname + '?mode=manage-managers')} 
                  title={user == null ? "Log in to manage" : !user.verified ? "Verify to manage" : "Manage Managers"} 
                  disabled={user == null || !user.verified}>👥</button>
        {/if}
        <button on:click={() => navigate(window.location.pathname + '?mode=manage-inventory')} 
                title={user == null ? "Log in to manage" : !user.verified ? "Verify to manage" : ownershipBasedEditing && !canEdit ? "Only owner/managers can manage" : 'Manage Inventory'} 
                disabled={user == null || !user.verified || (ownershipBasedEditing && !canEdit)}>📦</button>
      {/if}
      
      {#if mode === 'preview' || mode ==='edit' || mode === 'history' || mode === 'create' || mode === 'manage-inventory' || mode === 'manage-managers'}
        <button on:click={() => navigate(window.location.pathname)} title="Cancel">❌</button>
      {/if}
      {#if (mode === 'edit' || mode === 'create') && change?.id && user != null && user.verified}
        <button on:click={deleteChange} title="Delete this Change">🗑️</button>
      {/if}
    {/if}
  </div>
</div>
{#if description}
  <br />
  <p>{description}</p>
{/if}