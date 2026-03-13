<script>
  import JsonTreeNode from './JsonTreeNode.svelte';
  
  /**
   * @typedef {Object} Props
   * @property {any} data
   * @property {string} [path]
   * @property {any} collapsedPaths
   * @property {any} toggleCollapse
   */

  /** @type {Props} */
  let {
    data,
    path = '',
    collapsedPaths,
    toggleCollapse
  } = $props();

  let isArray = $derived(Array.isArray(data));
  let isObject = $derived(data !== null && typeof data === 'object' && !isArray);
  let isCollapsed = $derived(collapsedPaths.has(path));
</script>

{#if isArray}
  <span class="bracket">[</span>
  {#if data.length > 0}
    <button class="collapse-btn" onclick={() => toggleCollapse(path)}>
      {isCollapsed ? '+' : '-'}
    </button>
  {/if}
  {#if isCollapsed}
    <span class="collapsed-hint">{data.length} items</span>
    <span class="bracket">]</span>
  {:else}
    <div class="json-children">
      {#each data as item, i}
        {@const itemPath = `${path}[${i}]`}
        <div class="json-line">
          <span class="json-index">{i}:</span>
          <JsonTreeNode
            data={item}
            path={itemPath}
            {collapsedPaths}
            {toggleCollapse}
          />
          {#if i < data.length - 1}<span class="comma">,</span>{/if}
        </div>
      {/each}
    </div>
    <span class="bracket">]</span>
  {/if}
{:else if isObject}
  {@const keys = Object.keys(data)}
  <span class="bracket">{'{'}</span>
  {#if keys.length > 0}
    <button class="collapse-btn" onclick={() => toggleCollapse(path)}>
      {isCollapsed ? '+' : '-'}
    </button>
  {/if}
  {#if isCollapsed}
    <span class="collapsed-hint">{keys.length} properties</span>
    <span class="bracket">{'}'}</span>
  {:else}
    <div class="json-children">
      {#each keys as key, i}
        {@const keyPath = path ? `${path}.${key}` : key}
        <div class="json-line">
          <span class="json-key">"{key}"</span>
          <span class="colon">:</span>
          <JsonTreeNode
            data={data[key]}
            path={keyPath}
            {collapsedPaths}
            {toggleCollapse}
          />
          {#if i < keys.length - 1}<span class="comma">,</span>{/if}
        </div>
      {/each}
    </div>
    <span class="bracket">{'}'}</span>
  {/if}
{:else if data === null}
  <span class="null-value">null</span>
{:else if typeof data === 'string'}
  <span class="string-value">"{data}"</span>
{:else if typeof data === 'number'}
  <span class="number-value">{data}</span>
{:else if typeof data === 'boolean'}
  <span class="boolean-value">{data}</span>
{:else}
  <span class="unknown-value">{String(data)}</span>
{/if}

<style>
  .json-children {
    padding-left: 20px;
    border-left: 1px solid var(--border-color);
    margin-left: 4px;
  }

  .json-line {
    line-height: 1.6;
    white-space: nowrap;
  }

  .json-key {
    color: #9cdcfe;
  }

  .json-index {
    color: var(--text-muted);
    margin-right: 4px;
  }

  .colon {
    color: var(--text-muted);
    margin-right: 6px;
  }

  .comma {
    color: var(--text-muted);
  }

  .bracket {
    color: var(--text-muted);
  }

  .string-value {
    color: #ce9178;
  }

  .number-value {
    color: #b5cea8;
  }

  .boolean-value {
    color: #569cd6;
  }

  .null-value {
    color: #569cd6;
    font-style: italic;
  }

  .unknown-value {
    color: var(--text-muted);
  }

  .collapse-btn {
    background: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 3px;
    color: var(--text-muted);
    font-family: monospace;
    font-size: 10px;
    width: 16px;
    height: 16px;
    line-height: 1;
    cursor: pointer;
    margin-left: 4px;
    padding: 0;
    vertical-align: middle;
  }

  .collapse-btn:hover {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .collapsed-hint {
    color: var(--text-muted);
    font-style: italic;
    margin: 0 4px;
  }
</style>
