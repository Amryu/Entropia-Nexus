<!--
  @component CraftingTreeNode
  Recursive tree node for the construction calculator tree view.
  Supports up to MAX_DEPTH levels of nesting.
-->
<script>
  import CraftingTreeNode from './CraftingTreeNode.svelte';
  // @ts-nocheck
  import { getMaxNonFailChance, isLimitedBlueprint } from '$lib/utils/constructionCalculator.js';

  const MAX_DEPTH = 10;

  

  

  

  // Callback functions passed from the parent page
  
  
  
  
  
  
  
  
  
  
  
  
  
  /**
   * @typedef {Object} Props
   * @property {object} node
   * @property {number} [depth]
   * @property {boolean} [isTarget]
   * @property {(bp: object) => string} getBlueprintLink
   * @property {(id: number) => boolean} isTargetBlueprint
   * @property {(id: number) => boolean} isOwned
   * @property {(id: number) => boolean} isBuying
   * @property {(id: number) => void} toggleBuyPreference
   * @property {(id: number) => void} toggleOwnership
   * @property {(id: number, value: string) => void} setNonFailChance
   * @property {(id: number) => number} getNonFailChance
   * @property {(materialName: string) => object[]|null} getMaterialBlueprintOptions
   * @property {(materialName: string) => number|null} getSelectedBlueprintId
   * @property {(materialName: string, blueprintId: number) => void} selectMaterialBlueprint
   * @property {(node: object) => number} getNodeTotalTime
   * @property {(seconds: number) => string} formatCraftTime
   */

  /** @type {Props} */
  let {
    node,
    depth = 0,
    isTarget = false,
    getBlueprintLink,
    isTargetBlueprint,
    isOwned,
    isBuying,
    toggleBuyPreference,
    toggleOwnership,
    setNonFailChance,
    getNonFailChance,
    getMaterialBlueprintOptions,
    getSelectedBlueprintId,
    selectMaterialBlueprint,
    getNodeTotalTime,
    formatCraftTime
  } = $props();

  let maxNonFail = $derived(getMaxNonFailChance(node.blueprint));
  let actuallyOwned = $derived(isOwned(node.blueprint.Id));
  let totalTime = $derived(getNodeTotalTime(node));
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
        <input
          type="number"
          class="nonfail-input"
          value={getNonFailChance(node.blueprint.Id)}
          min="0"
          max={maxNonFail}
          step="any"
          onchange={(e) => setNonFailChance(node.blueprint.Id, e.target.value)}
          onclick={(e) => e.stopPropagation()}
        />%
      </span>
    {/if}
    {#if !isTargetBlueprint(node.blueprint.Id)}
      {#if !node.owned}
        <span class="node-status buying">Buying</span>
      {/if}
      <button
        class="node-toggle"
        class:buying={isBuying(node.blueprint.Id)}
        onclick={() => toggleBuyPreference(node.blueprint.Id)}
        disabled={!actuallyOwned}
        title={!actuallyOwned ? 'Must own to craft' : (isBuying(node.blueprint.Id) ? 'Switch to crafting' : 'Switch to buying')}
      >
        {isBuying(node.blueprint.Id) ? 'Buy' : 'Craft'}
      </button>
      <button
        class="node-toggle ownership-toggle"
        class:not-owned={!actuallyOwned}
        onclick={() => toggleOwnership(node.blueprint.Id)}
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
          onchange={(e) => selectMaterialBlueprint(node.parentMaterialName, parseInt(e.target.value))}
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
        <CraftingTreeNode
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
