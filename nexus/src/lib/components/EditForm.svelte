<script>
  //@ts-nocheck
  import { apiCall, apiPost, apiPut, navigate } from "$lib/util";
  import EditFormControlGroup from "./EditFormControlGroup.svelte";

  export let entity;
  export let change;
  export let object;
  export let config;
  export let user;
 
  let disabled = false;
 
  $: disabled = change != null && user?.id !== change.author_id && !user?.administrator;

  $: if (config) loadForm(config);
  $: if ((object == null || Object.keys(object).length === 0) && change?.data) object = change.data;

  let isLoading = true;
  let dependencies = {};

  function loadForm(config) {
    if (!config) return;

    let dependencyNames = getControlDependencies(config);

    if (dependencyNames.length > 0) {
      Promise.all(dependencyNames.filter(x => dependencies[x] == null).map(x =>
        apiCall(fetch, `/${x}`).then(response => [ x, response.sort((a, b) => a.Name.localeCompare(b.Name))])
      )).then(results => {
        dependencies = { ...dependencies, ...Object.fromEntries(results) };
        isLoading = false;
      })
      .catch(error => {
        console.error(error);
        isLoading = false;
      })
    }
    else {
      isLoading = false;
    }
  }

  function getControlDependencies(config) {
    let childDependencies = getControls(config.controls).filter(x => x?.config?.dependencies != null).flatMap(x => x.config.dependencies);

    if (config.dependencies != null) {
      return [...new Set([...config.dependencies, ...childDependencies])];
    }
    else {
      return childDependencies;
    }
  }

  function getControls(controlCollection) {
    return [
      ...controlCollection,
      ...controlCollection.filter(x => x.type === 'list' && x.config != null).flatMap(x => getControls(x.config.controls)),
      ...controlCollection.filter(x => x.type === 'group' && x.controls != null).flatMap(x => getControls(x.controls))];
  }

  function cancel() {
    navigate(window.location.pathname);
  }

  async function save() {
    let urlParams = new URLSearchParams(window.location.search);

    let mode = urlParams.get('mode');
    let changeId = urlParams.get('change');
    
    if (!mode) {
      alert('There was an error saving the entity. You are neither in edit nor in create mode!');
    }

    if (change?.id) {
      apiPut(fetch, `/api/changes/${change.id}`, object, window.location.origin)
        .then(_ => {
          alert('Change saved successfully!');
        })
        .catch(error => {
          alert(error);
        });
    } else {
      let type = object.Id ? 'Update' : 'Create';

      apiPost(fetch, `/api/changes?type=${type}&entity=${entity}`, object, window.location.origin)
        .then(async res => {
          if (res.error) {
            alert(res.error);
            return;
          }

          change = res;
          object = res.data;

          if (mode === 'create' && !changeId) {
            navigate(`${window.location.pathname}?mode=create&change=${res.id}`);
          }

          alert('Change created successfully!');
        })
        .catch(error => {
          alert(error);
        });
    }
  }

  async function submit() {
    let urlParams = new URLSearchParams(window.location.search);

    let mode = urlParams.get('mode');
    let changeId = urlParams.get('change');

    if (!mode) {
      alert('There was an error saving the entity. You are neither in edit nor in create mode!');
      return;
    }

    if (change?.id) {
      apiPut(fetch, `/api/changes/${change.id}?state=Pending`, object, window.location.origin)
        .then(_ => {
          alert('Change submitted successfully!');
        })
        .catch(error => {
          alert(error);
        });
    } else {
      let type = object.Id ? 'Update' : 'Create';

      apiPost(fetch, `/api/changes?type=${type}&entity=${entity}&state=Pending`, object, window.location.origin)
        .then(async res => {
          if (res.error) {
            alert(res.error);
            return;
          }

          change = res;
          object = res.data;

          if (mode === 'create' && !changeId) {
            navigate(`${window.location.pathname}?mode=create&change=${res.id}`);
          }
          
          alert('Change submitted successfully!');
        })
        .catch(error => {
          alert(error);
        });
    }
  }
</script>

<style>
  button {
    margin-left: 5px;
  }

  button:hover {
    cursor: pointer;
    background-color: var(--hover-color);
  }
</style>

{#if isLoading || object == null}
  <div class="info">Loading...</div>
{:else}
  {#if change?.id && (change.state === 'Pending' || change.state === 'Draft')}
    <div class="info" style="text-align: center;">This entity is currently being edited by someone and in the "{change.state}" state.</div>
  {/if}
  {#if change?.id && change.author_id !== user?.id && !user?.administrator}
    <div class="info" style="text-align: center;">You are not the author of this change. You can only view it.</div>
  {/if}
  <form>
    {#each config.controls.filter(x => x._if === undefined || x._if(object, dependencies)) as control}
      <EditFormControlGroup on:change={() => { config = config; object = object; }} root={object} bind:object={object} controls={control.controls || [control]} dependencies={dependencies} title={control.label} disabled={disabled} />
    {/each}
    <br />
    <div style="text-align: right;">
      <button type="button" on:click={cancel} disabled={disabled}>Cancel</button>
      <button type="button" on:click={save} disabled={disabled}>Save</button>
      <button type="button" on:click={submit} disabled={disabled || (change && change?.state !== 'Draft')} title={change && change?.state !== 'Draft' ? 'This change was already submitted. Use the Save button to make further changes!' : null}>Submit</button>
    </div>
  </form>
{/if}