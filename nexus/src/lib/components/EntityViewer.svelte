<script>
  import { page } from '$app/stores';
  import { loading } from '../../stores';

  import NavList from './NavList.svelte';
  import Properties from './Properties.svelte';

  export let data;
  export let tableViewInfo;
  export let navButtonInfo = [];
  export let propertiesDataFunction;
  export let title;
  export let basePath;

  let expanded = false;

  function setExpansionState(event) {
    expanded = event.detail.expanded;
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
  <title>Entropia Nexus - {title}</title>
</svelte:head>
<div class="flex-container">
    <div class="{expanded ? 'nav-list-expanded' : 'nav-list'} centered">
      <NavList
        currentSelection={$page.params.slug}
        items={data.items}
        tableViewInfo={tableViewInfo}
        filterButtonInfo={navButtonInfo}
        title={title}
        basePath={basePath}
        on:expand={setExpansionState} />
    </div>
    <div class="flex-content {expanded ? 'hidden' : ''}">
      {#if $loading}
        <div class="loading">
          <div class="spinner"></div>
        </div>
      {/if}
      {#if $page.params.slug != null && data != null && data?.error == null && data.object != null}
        <slot object={data.object} additional={data.additional}></slot>
      {:else if data?.error != null}
        <div class="info error"><h2>{data?.error?.status}</h2><br />{data?.error?.message}</div>
      {:else}
        <div class="info">Select any item from the list on the left to show information!</div>
      {/if}
    </div>
    <div class="prop-list centered">
      <Properties imageUrl='' data={data.object != null ? propertiesDataFunction(data.object, data.additional) : {}} />
    </div>
</div>