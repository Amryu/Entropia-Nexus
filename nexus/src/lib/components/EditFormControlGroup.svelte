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
  let tempValues = {};

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
      // Initialize temporary buffer for input-validator so user can type freely
      if (control.type === 'input-validator' && tempValues[i] === undefined) {
        try {
          tempValues[i] = stores[i].value;
        } catch {}
      }
    });
  }

  function commitInputValidator(i, control) {
    const val = tempValues[i];
    try {
      if (val !== undefined && (!control.validator || control.validator(val, dependencies, root))) {
        stores[i].value = val;
      }
    } catch {}
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

  /* Visual separation for list/array item content only */
  .efcg-item {
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 8px;
    margin: 6px 0;
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
    {:else if control.type === 'date'}
      <input type="date" id={control.key} bind:value={stores[i].value} disabled={disabled} />
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
      <select id={control.key} bind:value={stores[i].value} disabled={disabled} on:change={() => dispatch('change')}>
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
      <input
        type="text"
        id={control.key}
        class={(tempValues[i] ?? stores[i].value) && control.validator((tempValues[i] ?? stores[i].value), dependencies, root) ? '' : 'invalid'}
        bind:value={tempValues[i]}
        disabled={disabled}
        on:keydown={(e) => { if (e.key === 'Enter') { commitInputValidator(i, control); e.currentTarget.blur(); } }}
        on:blur={() => commitInputValidator(i, control)}
      />
    {:else if control.type === 'waypoint'}
      <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px;">
        <input type="number" placeholder="Longitude" step="0.0001"
          value={Array.isArray(stores[i].value) ? stores[i].value[0] || '' : ''}
          on:paste={(event) => {
            event.preventDefault();
            let paste = (event.clipboardData || window.clipboardData).getData('text');
            try {
              let parsed = JSON.parse(paste);
              if (Array.isArray(parsed) && parsed.length >= 4) {
                let coords = [parsed[1], parsed[2], parsed[3]]; // Skip planet name, take coords
                stores[i].value = coords.map(v => parseFloat(v) || 0);
                return;
              }
            } catch (e) {
              // Try comma-separated format
              let parts = paste.split(',').map(s => s.trim());
              if (parts.length >= 3) {
                let coords = parts.slice(1, 4); // Skip first item (planet), take next 3
                if (coords.every(v => !isNaN(parseFloat(v)))) {
                  stores[i].value = coords.map(v => parseFloat(v) || 0);
                  return;
                }
              }
            }
          }}
          on:input={(event) => {
            let input = event.target.value.trim();
            // Check if it looks like a waypoint paste
            if (input.includes('[') || input.includes(',')) {
              try {
                let parsed = JSON.parse(input);
                if (Array.isArray(parsed) && parsed.length >= 3) {
                  let coords = parsed.length >= 5 ? [parsed[1], parsed[2], parsed[3]] : parsed.slice(0, 3);
                  stores[i].value = coords.map(v => parseFloat(v) || 0);
                  return;
                }
              } catch (e) {
                let parts = input.split(',').map(s => s.trim());
                if (parts.length >= 3) {
                  let coords = parts.slice(0, 3).map(v => parseFloat(v) || 0);
                  if (coords.some(v => !isNaN(v))) {
                    stores[i].value = coords;
                    return;
                  }
                }
              }
            }
            // Single value update
            let newValue = [...(stores[i].value || [0, 0, 0])];
            newValue[0] = parseFloat(event.target.value) || 0;
            stores[i].value = newValue;
          }} 
          disabled={disabled} />
        <input type="number" placeholder="Latitude" step="0.0001"
          value={Array.isArray(stores[i].value) ? stores[i].value[1] || '' : ''}
          on:paste={(event) => {
            event.preventDefault();
            let paste = (event.clipboardData || window.clipboardData).getData('text');
            // Handle waypoint paste format: [ARIS, 34498, 21428, 194, Waypoint]
            try {
              let parsed = JSON.parse(paste);
              if (Array.isArray(parsed) && parsed.length >= 4) {
                let coords = [parsed[1], parsed[2], parsed[3]]; // Skip planet name, take coords
                stores[i].value = coords.map(v => parseFloat(v) || 0);
                return;
              }
            } catch (e) {
              // Try comma-separated format
              let parts = paste.split(',').map(s => s.trim());
              if (parts.length >= 3) {
                let coords = parts.slice(1, 4); // Skip first item (planet), take next 3
                if (coords.every(v => !isNaN(parseFloat(v)))) {
                  stores[i].value = coords.map(v => parseFloat(v) || 0);
                  return;
                }
              }
            }
          }}
          on:input={(event) => {
            let input = event.target.value.trim();
            // Check if it looks like a waypoint paste
            if (input.includes('[') || input.includes(',')) {
              try {
                let parsed = JSON.parse(input);
                if (Array.isArray(parsed) && parsed.length >= 3) {
                  let coords = parsed.length >= 5 ? [parsed[1], parsed[2], parsed[3]] : parsed.slice(0, 3);
                  stores[i].value = coords.map(v => parseFloat(v) || 0);
                  return;
                }
              } catch (e) {
                let parts = input.split(',').map(s => s.trim());
                if (parts.length >= 3) {
                  let coords = parts.slice(0, 3).map(v => parseFloat(v) || 0);
                  if (coords.some(v => !isNaN(v))) {
                    stores[i].value = coords;
                    return;
                  }
                }
              }
            }
            // Single value update
            let newValue = [...(stores[i].value || [0, 0, 0])];
            newValue[1] = parseFloat(event.target.value) || 0;
            stores[i].value = newValue;
          }} 
          disabled={disabled} />
        <input type="number" placeholder="Altitude" step="0.01"
          value={Array.isArray(stores[i].value) ? stores[i].value[2] || '' : ''}
          on:paste={(event) => {
            event.preventDefault();
            let paste = (event.clipboardData || window.clipboardData).getData('text');
            // Handle waypoint paste format: [ARIS, 34498, 21428, 194, Waypoint]
            try {
              let parsed = JSON.parse(paste);
              if (Array.isArray(parsed) && parsed.length >= 4) {
                let coords = [parsed[1], parsed[2], parsed[3]]; // Skip planet name, take coords
                stores[i].value = coords.map(v => parseFloat(v) || 0);
                return;
              }
            } catch (e) {
              // Try comma-separated format
              let parts = paste.split(',').map(s => s.trim());
              if (parts.length >= 3) {
                let coords = parts.slice(1, 4); // Skip first item (planet), take next 3
                if (coords.every(v => !isNaN(parseFloat(v)))) {
                  stores[i].value = coords.map(v => parseFloat(v) || 0);
                  return;
                }
              }
            }
          }}
          on:input={(event) => {
            let input = event.target.value.trim();
            // Check if it looks like a waypoint paste
            if (input.includes('[') || input.includes(',')) {
              try {
                let parsed = JSON.parse(input);
                if (Array.isArray(parsed) && parsed.length >= 3) {
                  let coords = parsed.length >= 5 ? [parsed[1], parsed[2], parsed[3]] : parsed.slice(0, 3);
                  stores[i].value = coords.map(v => parseFloat(v) || 0);
                  return;
                }
              } catch (e) {
                let parts = input.split(',').map(s => s.trim());
                if (parts.length >= 3) {
                  let coords = parts.slice(0, 3).map(v => parseFloat(v) || 0);
                  if (coords.some(v => !isNaN(v))) {
                    stores[i].value = coords;
                    return;
                  }
                }
              }
            }
            // Single value update
            let newValue = [...(stores[i].value || [0, 0, 0])];
            newValue[2] = parseFloat(event.target.value) || 0;
            stores[i].value = newValue;
          }} 
          disabled={disabled} />
      </div>
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
          {#if control.allowInsert !== false}
            <input type="button" value="Insert" on:click={() => { 
              let newItem = control.config.constructor(); 
              if (control.config.initialize) {
                const currentIndex = j;
                const parentArray = stores[i].value || [];
                control.config.initialize(newItem, dependencies, root, currentIndex, parentArray, object);
              }
              stores[i].value = [...stores[i].value.slice(0, j), newItem, ...stores[i].value.slice(j)]; 
              dispatch('change'); 
            }} disabled={disabled} />
          {/if}
        </span>
        <div class="efcg-item">
          <svelte:self root={root} bind:object={item} controls={control.config.controls} dependencies={dependencies} disabled={disabled} on:change={() => dispatch('change')} />
        </div>
      {/each}
      {control.itemNameFunc ? control.itemNameFunc(stores[i].value?.length) : `#${(stores[i].value?.length ?? 0) + 1}`}
      <input type="button" value="Add" on:click={() => { 
        let newItem = control.config.constructor(); 
        if (control.config.initialize) {
          const currentIndex = stores[i].value?.length || 0;
          const parentArray = stores[i].value || [];
          control.config.initialize(newItem, dependencies, root, currentIndex, parentArray, object);
        }
        stores[i].value = [...stores[i].value, newItem]; 
        dispatch('change'); 
      }} disabled={disabled} />
    {:else if control.type === 'array'}
      {#each Array.from({ length: typeof control.size === 'function' ? control.size(object, dependencies, root) : control.size }, (_, k) => stores[i].value?.find(x => control.indexFunc(x, k)) ?? undefined) as value, j}
        <span>
          {control.itemNameFunc(j)} &nbsp; 
          {#if value !== undefined}
            <input type="button" value="Remove" on:click={() => { stores[i].value = stores[i].value.filter(x => !control.indexFunc(x, j)); dispatch('change'); }} disabled={disabled} />
          {/if}
        </span>
        {#if value !== undefined}
          <div class="efcg-item">
            <svelte:self root={root} bind:object={value} controls={control.config.controls} dependencies={dependencies} disabled={disabled} on:change={() => dispatch('change')} />
          </div>
        {:else}
          <input type="button" value="Add" on:click={() => { 
            const newItem = control.config.constructor(j);
            if (control.config.initialize) {
              const currentIndex = j;
              const parentArray = stores[i].value || [];
              control.config.initialize(newItem, dependencies, root, currentIndex, parentArray, object);
            }
            stores[i].value.push(newItem); 
            dispatch('change'); 
          }} disabled={disabled} />
        {/if}
      {/each}
    {/if}
  {/if}
{/each}
</div>