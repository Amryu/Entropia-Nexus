<!--
  @component CraftingTreeNode
  Recursive tree node for the construction calculator tree view.
  Supports up to MAX_DEPTH levels of nesting.
-->
<script>
  // @ts-nocheck
  import { getMaxNonFailChance, isLimitedBlueprint } from '$lib/utils/constructionCalculator.js';

  const MAX_DEPTH = 10;

  /** @type {object} The crafting tree node */
  export let node;

  /** @type {number} Current nesting depth */
  export let depth = 0;

  /** @type {boolean} Whether this is a target blueprint (root) */
  export let isTarget = false;

  // Callback functions passed from the parent page
  /** @type {(bp: object) => string} */
  export let getBlueprintLink;
  /** @type {(id: number) => boolean} */
  export let isTargetBlueprint;
  /** @type {(id: number) => boolean} */
  export let isOwned;
  /** @type {(id: number) => boolean} */
  export let isBuying;
  /** @type {(id: number) => void} */
  export let toggleBuyPreference;
  /** @type {(id: number) => void} */
  export let toggleOwnership;
  /** @type {(id: number, value: string) => void} */
  export let setNonFailChance;
  /** @type {(id: number) => number} */
  export let getNonFailChance;
  /** @type {(materialName: string) => object[]|null} */
  export let getMaterialBlueprintOptions;
  /** @type {(materialName: string) => number|null} */
  export let getSelectedBlueprintId;
  /** @type {(materialName: string, blueprintId: number) => void} */
  export let selectMaterialBlueprint;
  /** @type {(node: object) => number} */
  export let getNodeTotalTime;
  /** @type {(seconds: number) => string} */
  export let formatCraftTime;

  $: maxNonFail = getMaxNonFailChance(node.blueprint);
  $: actuallyOwned = isOwned(node.blueprint.Id);
  $: totalTime = getNodeTotalTime(node);
</script>

<li class="tree-node" class:material-child={!isTarget} class:not-owned={!node.owned}>
  <div class="node-content">
    {#if !isTarget}
      <span class="node-type-badge material">Material</span>
    {/if}
    <a href={getBlueprintLink(node.blueprint)} class="node-name">
      {node.blueprint.Name}
    </a>
    <span class="node-quantity">&times;{node.quantityWanted}</span>
    {#if node.isLimited}<span class="limited-badge">(L)</span>{/if}
    {#if node.isSiB}<span class="sib-badge small">SiB</span>{/if}
    {#if totalTime > 0}<span class="node-time" title="Total crafting time (this + sub-materials)">{formatCraftTime(totalTime)}</span>{/if}
    {#if node.owned}
      <span class="node-nonfail" title="Non-fail chance (max {maxNonFail}% for {node.isSiB ? 'SiB' : 'non-SiB'})">
        {#if !isTargetBlueprint(node.blueprint.Id)}
          <input
            type="number"
            class="nonfail-input"
            value={getNonFailChance(node.blueprint.Id)}
            min="0"
            max={maxNonFail}
            on:change={(e) => setNonFailChance(node.blueprint.Id, e.target.value)}
            on:click|stopPropagation
          />%
        {:else}
          {node.nonFailChance}%
        {/if}
      </span>
    {/if}
    {#if !isTargetBlueprint(node.blueprint.Id)}
      {#if !node.owned}
        <span class="node-status buying">Buying</span>
      {/if}
      <button
        class="node-toggle"
        class:buying={isBuying(node.blueprint.Id)}
        on:click={() => toggleBuyPreference(node.blueprint.Id)}
        disabled={!actuallyOwned}
        title={!actuallyOwned ? 'Must own to craft' : (isBuying(node.blueprint.Id) ? 'Switch to crafting' : 'Switch to buying')}
      >
        {isBuying(node.blueprint.Id) ? 'Buy' : 'Craft'}
      </button>
      <button
        class="node-toggle ownership-toggle"
        class:not-owned={!actuallyOwned}
        on:click={() => toggleOwnership(node.blueprint.Id)}
        title={actuallyOwned ? 'Mark as not owned' : 'Mark as owned'}
      >
        {actuallyOwned ? 'Own' : "Don't Own"}
      </button>
    {:else}
      <span class="node-status target">Target</span>
    {/if}
  </div>

  <!-- Blueprint selection for material nodes with multiple options -->
  {#if !isTarget && node.parentMaterialName}
    {@const options = getMaterialBlueprintOptions(node.parentMaterialName)}
    {#if options && options.length > 1}
      <div class="bp-selector">
        <span class="bp-selector-label">BP:</span>
        <select
          class="bp-selector-select"
          value={node.blueprint.Id}
          on:change={(e) => selectMaterialBlueprint(node.parentMaterialName, parseInt(e.target.value))}
        >
          {#each options as bp}
            <option value={bp.Id}>
              {bp.Name}{isLimitedBlueprint(bp) ? ' (L)' : ''}
            </option>
          {/each}
        </select>
        {#if options.length > 1}
          <span class="bp-options-count" title="{options.length} blueprints available">{options.length} options</span>
        {/if}
      </div>
    {/if}
  {/if}

  {#if node.materialChildren?.length > 0 && depth < MAX_DEPTH}
    <ul class="tree-children">
      {#each node.materialChildren as child (child.blueprint.Id + '-' + child.parentMaterialName)}
        <svelte:self
          node={child}
          depth={depth + 1}
          isTarget={false}
          {getBlueprintLink}
          {isTargetBlueprint}
          {isOwned}
          {isBuying}
          {toggleBuyPreference}
          {toggleOwnership}
          {setNonFailChance}
          {getNonFailChance}
          {getMaterialBlueprintOptions}
          {getSelectedBlueprintId}
          {selectMaterialBlueprint}
          {getNodeTotalTime}
          {formatCraftTime}
        />
      {/each}
    </ul>
  {/if}
</li>
