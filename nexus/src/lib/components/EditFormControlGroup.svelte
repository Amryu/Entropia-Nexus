<script>
  //@ts-nocheck
  import { createEventDispatcher } from "svelte";

  import { writable } from "svelte/store";

  export let root;
  export let object;
  export let dependencies = {};
  export let controls = [];
  export let title = null;
  export let disabled = false;

  let stores = {};
  let dispatch = createEventDispatcher();

  function createStore(object, _get, _set, dependencies) {
    const { subscribe, set, update } = writable('');

    return {
      subscribe,
      set,
      update,
      get value() {
        return _get(object, dependencies);
      },
      set value(newValue) {
        _set(object, newValue, dependencies);
        set(newValue);
        dispatch('change');
      }
    };
  }

  $: if(controls) {
    stores = {};
    controls.forEach((control, i) => {
      stores[i] = createStore(object, control._get, control._set, dependencies);
    });
  }
</script>

<style>
  .grid {
    display: grid;
    gap: 10px;
    grid-template-columns: minmax(120px, max-content) 1fr;
    align-items: stretch;
    justify-content: start;
    margin-bottom: 0.83em;
  }

  .grid:last-child {
    margin-bottom: 0;
  }

  h3 {
    margin-top: 0;
  }

  input, select {
    background-color: var(--primary-color);
    color: var(--text-color);
  }

  .select-editable {
    position:relative;
    border: 1px solid gray;
  }
  .select-editable select {
    position:absolute;
    top:0px;
    left:0px;
    width:100%;
    margin:0;
    border:none;
  }
  .select-editable input {
    position:absolute;
    top:0px;
    left:0px;
    width:calc(100% - 20px);
    padding:1px;
    border:none;
  }
  .select-editable select:focus, .select-editable input:focus {
    outline:none;
  }

  .invalid {
    background-color: #660000 !important;
  }
</style>

{#if title}
  <h3>{title}</h3>
{/if}

<div class="grid">
{#each controls as control, i}
  {#if control._if === undefined || control._if(object, dependencies)}
    {#if control.type !== 'list' && control.type !== 'array'}
      <label for={control.key}>{typeof control.label === 'function' ? control.label(object) : control.label}</label>
    {/if}

    {#if control.type === 'text'}
      <input type="text" id={control.key} bind:value={stores[i].value} disabled={disabled} />
    {:else if control.type === 'number'}
      <input type="number" id={control.key} step={control.step} min={control.min} max={control.max} bind:value={stores[i].value} disabled={disabled} />
    {:else if control.type === 'multi'}
      <div style="display: grid; grid-template-columns: repeat({control.fields.length}, 1fr); text-align: center;">
        {#each control.fields as field}
          <span>{field}</span>
        {/each}
        {#each Array.from({ length: control.fields.length }) as _, j}
          <input type="number" style="width: calc(100% - 8px);" id={control.key} value={stores[i].value[j]} disabled={disabled} on:input={(event) => stores[i].value = stores[i].value.map((x, k) => k === j ? Number(event.target.value) : x)} />
        {/each}
      </div>
    {:else if control.type === 'checkbox'}
      <span style="text-align: left;">
        <input type="checkbox" id={control.key} bind:checked={stores[i].value} disabled={disabled} />
      </span>
    {:else if control.type === 'textarea'}
      <textarea id={control.key} bind:value={stores[i].value} disabled={disabled}></textarea>
    {:else if control.type === 'select'}
      <select id={control.key} bind:value={stores[i].value} disabled={disabled}>
        {#each control.options(object, dependencies, root) as option}
          <option value={option ?? ''}>{option ?? 'None'}</option>
        {/each}
      </select>
    {:else if control.type === 'input-select' }
      <div class="select-editable">
        <select on:change={e => stores[i].value = e.target.value} disabled={disabled}>
          <option value="" selected></option>
          {#each control.options(object, dependencies, root) as option}
            <option value={option ?? ''}>{option ?? 'None'}</option>
          {/each}
        </select>
        <input type="text" name="format" bind:value={stores[i].value} disabled={disabled}/>
      </div>
    {:else if control.type === 'input-validator'}
      <input type="text" class={stores[i].value && control.validator(stores[i].value, dependencies, root) ? '' : 'invalid'} id={control.key} bind:value={stores[i].value} disabled={disabled} />
    {:else if control.type === 'range'}
      <span>
        <input type="number" id={control.key} value={stores[i].value[0]} step={control.step} min={control.min} max={control.max} on:input={(event) => stores[i].value = [Number(event.target.value), stores[i].value[1]]} disabled={disabled} />
        -
        <input type="number" id={control.key} value={stores[i].value[1]} step={control.step} min={control.min} max={control.max} on:input={(event) => stores[i].value = [stores[i].value[0], Number(event.target.value)]} disabled={disabled} />
      </span>
    {:else if control.type === 'group'}
      <svelte:self root={root} bind:object={object} controls={control.controls} dependencies={dependencies} disabled={disabled} on:change={() => dispatch('change')} />
    {:else if control.type === 'list'}
      {#each (stores[i].value ?? []).sort((a, b) => control.sort ? control.sort(a, b) : 0) as item, j}
        <span>
          {control.itemNameFunc ? control.itemNameFunc(j) : `#${j + 1}`} &nbsp; 
          <input type="button" value="Remove" on:click={() => { stores[i].value = stores[i].value.filter((_, k) => k !== j); dispatch('change'); }} disabled={disabled} />
        </span>
        <svelte:self root={root} bind:object={item} controls={control.config.controls} dependencies={dependencies} disabled={disabled} on:change={() => dispatch('change')} />
      {/each}
      {control.itemNameFunc ? control.itemNameFunc(stores[i].value?.length) : `#${(stores[i].value?.length ?? 0) + 1}`}
      <input type="button" value="Add" on:click={() => { stores[i].value = [...stores[i].value, control.config.constructor()]; dispatch('change'); }} disabled={disabled} />
    {:else if control.type === 'array'}
      {#each Array.from({ length: control.size }, (_, k) => stores[i].value?.find(x => control.indexFunc(x, k)) ?? undefined) as value, j}
        <span>
          {control.itemNameFunc(j)} &nbsp; 
          {#if value !== undefined}
            <input type="button" value="Remove" on:click={() => { stores[i].value = stores[i].value.filter(x => !control.indexFunc(x, j)); dispatch('change'); }} disabled={disabled} />
          {/if}
        </span>
        {#if value !== undefined}
          <svelte:self root={root} bind:object={value} controls={control.config.controls} dependencies={dependencies} disabled={disabled} on:change={() => dispatch('change')} />
        {:else}
          <input type="button" value="Add" on:click={() => { stores[i].value.push(control.config.constructor(j)); dispatch('change'); }} disabled={disabled} />
        {/if}
      {/each}
    {/if}
  {/if}
{/each}
</div>