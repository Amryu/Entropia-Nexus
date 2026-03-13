<!--
  @component EntityViewer
  @deprecated This component is deprecated and will be replaced by the new WikiPage system.
  New wiki pages should use components from $lib/components/wiki/ instead.

  Migration guide:
  - WikiPage.svelte: Main responsive container
  - WikiHeader.svelte: Breadcrumbs, title, mode toggle
  - WikiNavigation.svelte: Sidebar navigation with search
  - DataSection.svelte: Collapsible content sections
  - InlineEdit.svelte: WYSIWYG inline editing
  - EntityInfobox.svelte: Icon + key stats display
  - WikiSEO.svelte: SEO meta tags + JSON-LD

  See plan file for full migration details.
-->
<script>
  import { run } from 'svelte/legacy';

  //@ts-nocheck
  /**
   * @deprecated Use WikiPage and related components from $lib/components/wiki/ instead.
   */
  import { loading, pageParams } from '../../stores';
  import { apiCall, encodeURIComponentSafe, getErrorMessage, getTypeName } from '$lib/util';

  import NavList from './NavList.svelte';
  import Properties from './Properties.svelte';
  import EntityTitleBar from './EntityTitleBar.svelte';
  import EditForm from './EditForm.svelte';
  import InventoryEditForm from './InventoryEditForm.svelte';
  import ManagerEditForm from './ManagerEditForm.svelte';
  import EntityHistory from './EntityHistory.svelte';


  /**
   * @typedef {Object} Props
   * @property {any} data
   * @property {any} tableViewInfo
   * @property {any} [navButtonInfo]
   * @property {any} editConfig
   * @property {any} propertiesDataFunction
   * @property {any} title
   * @property {any} type
   * @property {any} basePath
   * @property {boolean} [ownershipBasedEditing] - New parameter for shops
   * @property {any} [getOwnershipInfo] - Function to check ownership
   * @property {any} user
   * @property {import('svelte').Snippet<[any]>} [children]
   */

  /** @type {Props} */
  let {
    data,
    tableViewInfo,
    navButtonInfo = [],
    editConfig,
    propertiesDataFunction,
    title,
    type,
    basePath,
    ownershipBasedEditing = false,
    getOwnershipInfo = null,
    user,
    children
  } = $props();

  let mode = $state(null);
  let change = $state(null);
  

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
            console.log('No existing change found, creating a new one.');
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
        console.log('No existing change found, creating a new one.');
      });
  }

  let expanded = $state(false);

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

  run(() => {
    if (typeof window !== 'undefined' && mode != new URLSearchParams(window.location.search).get('mode') && data != null) updateMode();
  });
</script>

<style>
  .info {
    width: 100%;
    text-align: center;
    margin-top: 50px;
  }

  /* Support block below Properties, no outer margins to keep a continuous sidebar */
  .support-wrapper {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;    padding: 12px 0;
    border-top: 1px solid #ccc;
    background-color: var(--secondary-color);
  }
  .support-inner {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
  }
  .kofi-button {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: 6px;
    background: #29abe0;
    color: #fff;
    text-decoration: none;
    font-weight: 600;
    box-shadow: 0 1px 2px rgba(0,0,0,0.2);
  }
  .kofi-button:hover { filter: brightness(1.05); }
  .kofi-logo { height: 18px; width: 18px; }
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
            <EntityTitleBar 
              title={getCurrentData(change?.data, data.object).Name} 
              description={getCurrentData(change?.data, data.object)?.Properties?.Description} 
              mode={mode} 
              user={data.session.user} 
              change={change} 
              editable={editConfig != null}
              ownershipBasedEditing={ownershipBasedEditing}
              canEdit={ownershipBasedEditing && getOwnershipInfo ? getOwnershipInfo(data.object, user) : true}
              entityType={type}
              object={data.object} />
          </div>
          {@render children?.({ object: getCurrentData(change?.data, data.object), change, mode, additional: data.additional, user, })}
        {:else if mode === 'edit' || mode === 'create'}
          <div class="flex-item flex-span-2">
            <EntityTitleBar 
              title={`${mode === 'edit' ? 'Edit' : 'Create'} ${getTypeName(type)}`} 
              mode={mode} 
              user={data.session.user} 
              change={change}  
              editable={editConfig != null}
              ownershipBasedEditing={ownershipBasedEditing}
              canEdit={ownershipBasedEditing && getOwnershipInfo ? getOwnershipInfo(data.object, user) : true}
              entityType={type}
              object={data.object} />
          </div>
          <div class="flex-item flex-span-2">
            <EditForm
              entity={type}
              user={user}
              object={getCurrentData(change?.data, data.object)}
              bind:change={change}
              config={data?.additional?.type ? editConfig[data.additional.type] : editConfig} />
          </div>
    {:else if mode === 'edit-inventory'}
          <div class="flex-item flex-span-2">
            <EntityTitleBar 
      title={`Edit Inventory - ${getCurrentData(change?.data, data.object).Name}`} 
              mode={mode} 
              user={data.session.user} 
              change={change}  
              editable={editConfig != null}
              ownershipBasedEditing={ownershipBasedEditing}
              canEdit={ownershipBasedEditing && getOwnershipInfo ? getOwnershipInfo(data.object, user) : true}
              entityType={type}
              object={data.object} />
          </div>
          <div class="flex-item flex-span-2">
            <InventoryEditForm
              user={user}
              object={getCurrentData(change?.data, data.object)}
              canEdit={getOwnershipInfo ? getOwnershipInfo(data.object, user) : false} />
          </div>
    {:else if mode === 'edit-managers'}
          <div class="flex-item flex-span-2">
            <EntityTitleBar 
      title={`Edit Managers - ${getCurrentData(change?.data, data.object).Name}`} 
              mode={mode} 
              user={data.session.user} 
              change={change}  
              editable={editConfig != null}
              ownershipBasedEditing={ownershipBasedEditing}
              canEdit={ownershipBasedEditing && getOwnershipInfo ? getOwnershipInfo(data.object, user) : true}
              entityType={type}
              object={data.object} />
          </div>
          <div class="flex-item flex-span-2">
            <ManagerEditForm
              user={user}
              object={getCurrentData(change?.data, data.object)}
              canEdit={getOwnershipInfo ? getOwnershipInfo(data.object, user) : false} />
          </div>
        {:else}
          <div class="flex-item flex-span-2">
            <EntityTitleBar 
              title="History: {getCurrentData(change?.data, data.object).Name}" 
              mode={mode} 
              user={data.session.user} 
              change={change} 
              editable={editConfig != null}
              entityType={type}
              object={data.object} />
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
        {#if getCurrentData(change?.data, data.object)}
          <Properties imageUrl='' title={getCurrentData(change?.data, data.object)?.Name ?? '<No Name>'} data={propertiesDataFunction(getCurrentData(change?.data, data.object), data.additional)} />
        {:else}
          <Properties imageUrl='' title={'<No Name>'} data={{}} />
        {/if}
      </div>
      <!-- Support section directly below Properties, no gap -->
      <div class="support-wrapper">
        <div class="support-inner">
          <a
            class="kofi-button"
            href="https://ko-fi.com/C0C21JO3B1"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Support on Ko-fi"
          >
            <img class="kofi-logo" alt="Ko-fi" src="https://storage.ko-fi.com/cdn/cup-border.png" />
            Support on Ko-fi
          </a>
        </div>
      </div>
    </div>
</div>