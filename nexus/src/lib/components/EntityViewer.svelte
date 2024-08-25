<script>
  //@ts-nocheck
  import { loading, pageParams } from '../../stores';
  import { apiCall, encodeURIComponentSafe, getErrorMessage, getTypeName } from '$lib/util';

  import NavList from './NavList.svelte';
  import Properties from './Properties.svelte';
  import EntityTitleBar from './EntityTitleBar.svelte';
  import EditForm from './EditForm.svelte';
  import EntityHistory from './EntityHistory.svelte';

  export let data;
  export let tableViewInfo;
  export let navButtonInfo = [];
  export let editConfig;
  export let propertiesDataFunction;
  export let title;
  export let type;
  export let basePath;

  export let user;

  let mode = null;
  let change = null;
  
  $: if (typeof window !== 'undefined' && mode != new URLSearchParams(window.location.search).get('mode') && data != null) updateMode();

  function updateMode() {
    const urlParams = new URLSearchParams(window.location.search);

    if (mode === 'view' && !urlParams.get('mode')) {
      change = null;
      return;
    }

    mode = urlParams.get('mode') || 'view';

    if (mode === 'create' && data.session.user && data.session.user.verified) {
      let changeId = urlParams.get('change');

      if (!changeId) {
        // Create new change (draft)
        change = {
          data: (data?.additional?.type ? editConfig[data.additional.type] : editConfig).constructor(),
          author_id: data.session.user.id,
          entity: type,
          type: 'Create',
          state: 'Draft'
        };
      } else {
        // Load existing change
        apiCall(fetch, `/api/changes/${changeId}`, window.location.origin)
          .then(response => {
            change = response;
          })
          .catch(error => {
            console.error(error);
          });
      }

        return;
    }

    if (data.object == null) {
      return;
    }

    apiCall(fetch, `/api/changes?entityId=${data.object.Id}`, window.location.origin)
      .then(response => {
        change = response;
      })
      .catch(error => {
        console.error(error);
      });
  }

  let expanded = false;

  function getCurrentData(change, object) {
    if (mode === 'edit' || mode === 'preview') {
      return change || object;
    } else {
      return object;
    }
  }

  function setExpansionState(event) {
    expanded = event.detail.expanded;
  }

  function getCanonicalUrl(params) {
    if (params.type != null && params.slug != null)
      return `https://entropianexus.com${basePath}/${encodeURIComponentSafe(params.type)}/${encodeURIComponentSafe(params.slug)}`;
    else if (params.slug != null)
      return `https://entropianexus.com${basePath}/${encodeURIComponentSafe(params.slug)}`;
    else if (params.slug == null || params.slug == '')
      return `https://entropianexus.com${basePath}`;
  } 
</script>

<style>
  .info {
    width: 100%;
    text-align: center;
    margin-top: 50px;
  }
</style>

<svelte:head>
  <title>Entropia Nexus - {$pageParams.slug ?? title}</title>
  <meta name="description" content="Detailed information about {$pageParams.slug ?? title}.">
  <meta name="keywords" content="{$pageParams.slug != null ? $pageParams.slug + ', ' : ''}{basePath.split('/').slice(1).join(', ')}, Entropia Universe, Entropia, Entropia Nexus, EU, PE, Items, Mobs, Maps, Tools, MindArk, Wiki">
  <link rel="canonical" href="{getCanonicalUrl($pageParams)}" />
</svelte:head>
<div class="flex-container">
    <div class="{expanded ? 'nav-list-expanded' : 'nav-list'} centered">
      <NavList
        user={user}
        currentSelection={$pageParams.slug}
        items={data.items}
        tableViewInfo={tableViewInfo}
        filterButtonInfo={navButtonInfo}
        title={title}
        basePath={basePath}
        editable={editConfig != null}
        on:expand={setExpansionState} />
    </div>
    <div class="flex-content {expanded ? 'hidden' : ''}">
      {#if $loading}
        <div class="loading">
          <div class="spinner"></div>
        </div>
      {/if}
      {#if mode === 'create' || ($pageParams.slug != null && data != null && data?.error == null && data.object != null)}
        {#if mode == null || mode === 'view' || mode === 'preview'}
          <div class="flex-item flex-span-2">
            <EntityTitleBar title={getCurrentData(change?.data, data.object).Name} mode={mode} user={data.session.user} change={change} editable={editConfig != null} />
          </div>
          <slot object={getCurrentData(change?.data, data.object)} change={change} mode={mode} additional={data.additional} {user}></slot>
        {:else if mode === 'edit' || mode === 'create'}
          <div class="flex-item flex-span-2">
            <EntityTitleBar title={`${mode === 'edit' ? 'Edit' : 'Create'} ${getTypeName(type)}`} mode={mode} user={data.session.user} change={change}  editable={editConfig != null}/>
          </div>
          <div class="flex-item flex-span-2">
            <EditForm
              entity={type}
              user={user}
              object={getCurrentData(change?.data, data.object)}
              bind:change={change}
              config={data?.additional?.type ? editConfig[data.additional.type] : editConfig} />
          </div>
        {:else}
          <div class="flex-item flex-span-2">
            <EntityTitleBar title="History: {getCurrentData(change?.data, data.object).Name}" mode={mode} user={data.session.user} change={change} editable={editConfig != null} />
          </div>
          <div class="flex-item flex-span-2">
            <EntityHistory user={user} bind:change={change} versions={data.versions} />
          </div>
        {/if}
      {:else if data?.error != null}
        <div class="info error"><h1>Error {data?.error}</h1><br /><p>{getErrorMessage(data?.error)}</p></div>
      {:else}
        <div class="info"><h1>{title}</h1><br />Select any item from the list on the left to show information!</div>
      {/if}
    </div>
    <div class="right-sidebar">
      <div class="prop-list centered">
        <Properties imageUrl='' title={getCurrentData(change?.data, data.object)?.Name ?? '<No Name>'} data={getCurrentData(change?.data, data.object) != null ? propertiesDataFunction(getCurrentData(change?.data, data.object), data.additional) : {}} />
      </div>
      <div class="ad-wrapper">
        <a href="https://www.lootius.io/User/Register/1456" title="Earn PED by completing offers or playing minigames!" target="_blank">
          <img src="/lootius.png" alt="Lootius Banner" width="300px" height="80px" />
        </a>
      </div>
    </div>
</div>