<script>
  //@ts-nocheck
  import { apiDelete, navigate } from "$lib/util";

  export let mode;
  export let user;
  export let title;
  export let change;
  export let editable = true;

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
      {#if mode !== 'edit' && mode !== 'history' && mode !== 'create'}
        <button on:click={() => navigate(window.location.pathname + '?mode=history')} title="View History">📄</button>
      {/if}
      {#if mode !== 'edit' && mode !== 'history' && mode !== 'create'}
        <button on:click={() => navigate(window.location.pathname + '?mode=edit')} title={user == null || !user.verified ? "Log in to edit" : 'Edit'} disabled={user == null || !user.verified}>✏️</button>
      {/if}
      {#if mode === 'preview' || mode ==='edit' || mode === 'history' || mode === 'create'}
        <button on:click={() => navigate(window.location.pathname)} title="Cancel">❌</button>
      {/if}
      {#if (mode === 'edit' || mode === 'create') && change?.id && user != null && user.verified}
        <button on:click={deleteChange} title="Delete this Change">🗑️</button>
      {/if}
    {/if}
  </div>
</div>