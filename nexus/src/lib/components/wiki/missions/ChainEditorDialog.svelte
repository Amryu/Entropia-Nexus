<!--
  @component ChainEditorDialog
  Dialog for creating/editing mission chains and managing chain dependencies.

  Features:
  - Create new chain or edit existing chain
  - View missions in the chain organized by dependency order
  - Edit prerequisites and unlocks (dependents) for the current mission
  - Highlight disconnected missions that need to be connected
  - Validate chain connectivity before saving
-->
<script>
  // @ts-nocheck
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  

  

  

  

  

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string|null} [chainName]
   * @property {string|null} [chainDescription]
   * @property {string|null} [chainPlanet]
   * @property {boolean} [isCreating]
   * @property {Array} [allChains]
   * @property {Array} [allMissions]
   * @property {Object|null} [currentMission]
   * @property {Object|null} Graph data for the chain { nodes, edges } [graphData]
   * @property {Array} [planetOptions]
   * @property {string} [currentPlanetName]
   * @property {(data: any) => void} [oncreate]
   * @property {(data: any) => void} [onupdateChain]
   * @property {(data: any) => void} [onselect]
   * @property {() => void} [onaddPrerequisite]
   * @property {(data: any) => void} [onupdatePrerequisite]
   * @property {(data: any) => void} [onremovePrerequisite]
   * @property {() => void} [onaddDependent]
   * @property {(data: any) => void} [onupdateDependent]
   * @property {(data: any) => void} [onremoveDependent]
   * @property {() => void} [onclose]
   */

  /** @type {Props} */
  let {
    chainName = null,
    chainDescription = null,
    chainPlanet = null,
    isCreating = false,
    allChains = [],
    allMissions = [],
    currentMission = null,
    graphData = null,
    planetOptions = [],
    currentPlanetName = 'Calypso',
    oncreate,
    onupdateChain,
    onselect,
    onaddPrerequisite,
    onupdatePrerequisite,
    onremovePrerequisite,
    onaddDependent,
    onupdateDependent,
    onremoveDependent,
    onclose
  } = $props();

  // Local state
  let newChainName = $state('');
  let newChainPlanet = $state('');
  let newChainDescription = $state('');

  // Sync default planet when prop changes
  $effect(() => {
    if (!newChainPlanet) {
      newChainPlanet = currentPlanetName;
    }
  });

  let nameError = $state('');

  // For editing existing chain
  let editChainName = $state('');
  let editChainDescription = $state('');
  let editChainPlanet = $state('');
  let editNameError = $state('');




  function buildAdjacencyLists(graph) {
    const next = new Map(); // missionId -> [missionIds that this unlocks]
    const prev = new Map(); // missionId -> [missionIds that are prerequisites]

    if (graph?.edges) {
      for (const edge of graph.edges) {
        const fromId = String(edge.FromId);
        const toId = String(edge.ToId);

        // FromId is prerequisite, ToId is the mission that requires it
        if (!next.has(fromId)) next.set(fromId, []);
        next.get(fromId).push(toId);

        if (!prev.has(toId)) prev.set(toId, []);
        prev.get(toId).push(fromId);
      }
    }

    return { adjacencyNext: next, adjacencyPrev: prev };
  }


  function organizeMissionsByDependencies(missions, prevMap) {
    if (!missions.length) return { layers: [], disconnected: [] };

    const missionIds = new Set(missions.map(m => String(m.Id)));
    const inDegree = new Map();
    const layers = [];
    const processed = new Set();

    // Initialize in-degree for all missions
    for (const m of missions) {
      const id = String(m.Id);
      const prereqs = (prevMap.get(id) || []).filter(p => missionIds.has(p));
      inDegree.set(id, prereqs.length);
    }

    // Process layers (topological sort by levels)
    while (processed.size < missions.length) {
      const layer = [];

      // Find all missions with in-degree 0 that haven't been processed
      for (const m of missions) {
        const id = String(m.Id);
        if (!processed.has(id) && inDegree.get(id) === 0) {
          layer.push(m);
          processed.add(id);
        }
      }

      if (layer.length === 0) {
        // Remaining missions have cycles or are disconnected
        break;
      }

      layers.push(layer);

      // Decrease in-degree for missions that depend on this layer
      for (const m of layer) {
        const id = String(m.Id);
        const unlocks = (adjacencyNext.get(id) || []).filter(u => missionIds.has(u));
        for (const unlockId of unlocks) {
          inDegree.set(unlockId, (inDegree.get(unlockId) || 1) - 1);
        }
      }
    }

    // Find disconnected missions (not yet processed)
    const disconnected = missions.filter(m => !processed.has(String(m.Id)));

    return { layers, disconnected };
  }


  function checkConnectivity(missions, nextMap, prevMap) {
    if (missions.length <= 1) return { isConnected: true, disconnectedIds: [] };

    const missionIds = new Set(missions.map(m => String(m.Id)));

    // Find roots (missions with no prerequisites)
    const roots = missions.filter(m => {
      const prereqs = (prevMap.get(String(m.Id)) || []).filter(p => missionIds.has(p));
      return prereqs.length === 0;
    });

    if (roots.length === 0) {
      // No roots means there's a cycle - all are disconnected in a sense
      return { isConnected: false, disconnectedIds: [...missionIds] };
    }

    // BFS from all roots
    const visited = new Set();
    const queue = roots.map(r => String(r.Id));
    queue.forEach(id => visited.add(id));

    while (queue.length > 0) {
      const current = queue.shift();
      const unlocks = (nextMap.get(current) || []).filter(u => missionIds.has(u));
      for (const unlockId of unlocks) {
        if (!visited.has(unlockId)) {
          visited.add(unlockId);
          queue.push(unlockId);
        }
      }
    }

    const disconnectedIds = [...missionIds].filter(id => !visited.has(id));
    return {
      isConnected: disconnectedIds.length === 0,
      disconnectedIds
    };
  }




  // Get label from options by value (for SearchInput display)
  function getOptionLabel(options, value) {
    if (!value) return '';
    const opt = options.find(o => o.value === String(value));
    return opt?.label || '';
  }

  function validateNewChainName(name) {
    if (!name || !name.trim()) {
      return 'Chain name is required';
    }
    const exists = allChains.some(c => c.Name.toLowerCase() === name.trim().toLowerCase());
    if (exists) {
      return 'A chain with this name already exists';
    }
    return '';
  }

  function validateEditChainName(name) {
    if (!name || !name.trim()) {
      return 'Chain name is required';
    }
    // Allow keeping the same name
    if (name.trim().toLowerCase() === (chainName || '').toLowerCase()) {
      return '';
    }
    const exists = allChains.some(c => c.Name.toLowerCase() === name.trim().toLowerCase());
    if (exists) {
      return 'A chain with this name already exists';
    }
    return '';
  }

  function handleCreateChain() {
    const error = validateNewChainName(newChainName);
    if (error) {
      nameError = error;
      return;
    }
    nameError = '';
    // Check if HTML content is effectively empty
    const isEmpty = !newChainDescription || newChainDescription === '<p></p>' ||
                    newChainDescription.replace(/<[^>]*>/g, '').trim() === '';
    oncreate?.({
      name: newChainName.trim(),
      planet: newChainPlanet,
      description: isEmpty ? null : newChainDescription
    });
  }

  function handleChainNameChange() {
    const error = validateEditChainName(editChainName);
    if (error) {
      editNameError = error;
      return;
    }
    editNameError = '';
    onupdateChain?.({ field: 'Name', value: editChainName.trim() });
  }

  function handleChainDescriptionChange() {
    // Check if HTML content is effectively empty (just empty tags or whitespace)
    const isEmpty = !editChainDescription || editChainDescription === '<p></p>' ||
                    editChainDescription.replace(/<[^>]*>/g, '').trim() === '';
    onupdateChain?.({ field: 'Description', value: isEmpty ? null : editChainDescription });
  }

  function handleChainPlanetChange() {
    onupdateChain?.({ field: 'Planet', value: editChainPlanet });
  }

  function handleSelectChain(name) {
    onselect?.({ name });
  }

  function handleAddPrerequisite() {
    onaddPrerequisite?.();
  }

  function handleUpdatePrerequisite(index, missionId) {
    const mission = allMissions.find(m => String(m.Id) === String(missionId));
    onupdatePrerequisite?.({ index, mission });
  }

  function handleRemovePrerequisite(index) {
    onremovePrerequisite?.({ index });
  }

  function handleAddDependent() {
    onaddDependent?.();
  }

  function handleUpdateDependent(index, missionId) {
    const mission = allMissions.find(m => String(m.Id) === String(missionId));
    onupdateDependent?.({ index, mission });
  }

  function handleRemoveDependent(index) {
    onremoveDependent?.({ index });
  }

  function handleClose() {
    onclose?.();
  }

  function getMissionName(id) {
    const mission = chainMissions.find(m => String(m.Id) === String(id));
    return mission?.Name || `Mission #${id}`;
  }

  function isCurrentMission(id) {
    return String(id) === String(currentMission?.Id);
  }

  function isDisconnected(id) {
    return connectivityStatus.disconnectedIds.includes(String(id));
  }
  // Initialize edit values when chain data changes
  $effect(() => {
    if (!isCreating && chainName) {
      editChainName = chainName || '';
      editChainDescription = chainDescription || '';
      editChainPlanet = chainPlanet || currentPlanetName;
    }
  });
  // Get missions in the current chain
  let chainMissions = $derived(graphData?.nodes || []);
  // Build adjacency lists for the chain graph
  let adjacencyLists = $derived(buildAdjacencyLists(graphData));
  let adjacencyNext = $derived(adjacencyLists.adjacencyNext);
  let adjacencyPrev = $derived(adjacencyLists.adjacencyPrev);
  // Organize missions into layers based on dependencies (topological sort)
  let organizedMissions = $derived(organizeMissionsByDependencies(chainMissions, adjacencyPrev));
  // Check if chain is fully connected (all missions reachable from at least one root)
  let connectivityStatus = $derived(checkConnectivity(chainMissions, adjacencyNext, adjacencyPrev));
  // Current mission's prerequisites and dependents
  let currentPrerequisites = $derived(currentMission?.Dependencies?.Prerequisites || []);
  let currentDependents = $derived(currentMission?.Dependencies?.Dependents || []);
  // Mission options for prerequisite/dependent selection (exclude current mission)
  let missionOptionsForDeps = $derived(allMissions
    .filter(m => m?.Id && m?.Name && String(m.Id) !== String(currentMission?.Id))
    .map(m => ({ value: String(m.Id), label: m.Name })));
  // Chain missions options (for quick adding from chain)
  let chainMissionOptions = $derived(chainMissions
    .filter(m => String(m.Id) !== String(currentMission?.Id))
    .map(m => ({ value: String(m.Id), label: m.Name })));
</script>

<div class="dialog-overlay" role="presentation" onclick={handleClose}>
  <div class="chain-dialog" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
    <div class="dialog-header">
      <h3>{isCreating ? 'Create New Chain' : 'Edit Chain'}</h3>
      <button class="dialog-close" onclick={handleClose}>Close</button>
    </div>

    <div class="dialog-body">
      {#if isCreating}
        <div class="create-chain-form">
          <div class="form-field">
            <label for="chain-name">Chain Name</label>
            <input
              id="chain-name"
              type="text"
              bind:value={newChainName}
              placeholder="Enter chain name..."
              class:error={nameError}
              oninput={() => nameError = ''}
            />
            {#if nameError}
              <span class="field-error">{nameError}</span>
            {/if}
          </div>
          <div class="form-field">
            <label for="chain-planet">Planet</label>
            <select id="chain-planet" bind:value={newChainPlanet}>
              {#each planetOptions as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
          </div>
          <div class="form-field">
            <span class="label">Description (optional)</span>
            <RichTextEditor
              content={newChainDescription}
              placeholder="Enter chain description..."
              onchange={(data) => newChainDescription = data}
              showWaypoints={true}
            />
          </div>
          <div class="form-actions">
            <button class="btn primary" onclick={handleCreateChain}>Create Chain</button>
            <button class="btn secondary" onclick={handleClose}>Cancel</button>
          </div>
        </div>
      {:else}
        <div class="chain-content">
          <!-- Chain Details Section (editable) -->
          <div class="section chain-details-section">
            <h4 class="section-title">Chain Details</h4>
            <div class="chain-details-form">
              <div class="form-row">
                <div class="form-field">
                  <label for="edit-chain-name">Name</label>
                  <input
                    id="edit-chain-name"
                    type="text"
                    bind:value={editChainName}
                    placeholder="Chain name..."
                    class:error={editNameError}
                    oninput={() => editNameError = ''}
                    onblur={handleChainNameChange}
                  />
                  {#if editNameError}
                    <span class="field-error">{editNameError}</span>
                  {/if}
                </div>
                <div class="form-field">
                  <label for="edit-chain-planet">Planet</label>
                  <select id="edit-chain-planet" bind:value={editChainPlanet} onchange={handleChainPlanetChange}>
                    {#each planetOptions as opt}
                      <option value={opt.value}>{opt.label}</option>
                    {/each}
                  </select>
                </div>
              </div>
              <div class="form-field">
                <span class="label">Description</span>
                <RichTextEditor
                  content={editChainDescription}
                  placeholder="Chain description (optional)..."
                  onchange={(data) => {
                    editChainDescription = data;
                    handleChainDescriptionChange();
                  }}
                  showWaypoints={true}
                />
              </div>
            </div>
          </div>

          <!-- Chain Overview Section -->
          <div class="section">
            <h4 class="section-title">Missions in Chain</h4>

            {#if !connectivityStatus.isConnected}
              <div class="warning-banner">
                <strong>Warning:</strong> Not all missions in this chain are connected.
                Disconnected missions are highlighted below. Please add dependencies to connect them.
              </div>
            {/if}

            {#if organizedMissions.layers.length > 0}
              <div class="mission-layers">
                {#each organizedMissions.layers as layer, layerIndex}
                  <div class="layer">
                    <div class="layer-label">
                      {layerIndex === 0 ? 'Start' : `Stage ${layerIndex + 1}`}
                    </div>
                    <div class="layer-missions">
                      {#each layer as mission}
                        <div
                          class="mission-chip"
                          class:current={isCurrentMission(mission.Id)}
                          class:disconnected={isDisconnected(mission.Id)}
                        >
                          {mission.Name}
                          {#if isCurrentMission(mission.Id)}
                            <span class="current-badge">current</span>
                          {/if}
                        </div>
                      {/each}
                    </div>
                  </div>
                  {#if layerIndex < organizedMissions.layers.length - 1}
                    <div class="layer-arrow">&#8595;</div>
                  {/if}
                {/each}
              </div>
            {:else if chainMissions.length === 0}
              <div class="empty-text">No missions in this chain yet.</div>
            {/if}

            {#if organizedMissions.disconnected.length > 0}
              <div class="disconnected-section">
                <div class="disconnected-label">Disconnected Missions</div>
                <div class="disconnected-missions">
                  {#each organizedMissions.disconnected as mission}
                    <div
                      class="mission-chip disconnected"
                      class:current={isCurrentMission(mission.Id)}
                    >
                      {mission.Name}
                      {#if isCurrentMission(mission.Id)}
                        <span class="current-badge">current</span>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>

          <!-- Dependencies Section -->
          <div class="section dependencies-section">
            <h4 class="section-title">Dependencies for: {currentMission?.Name || 'Current Mission'}</h4>

            <div class="dependencies-grid">
              <!-- Prerequisites Column -->
              <div class="dependency-column">
                <h5>Prerequisites</h5>
                <p class="column-hint">Missions that must be completed before this one</p>

                {#if currentPrerequisites.length > 0}
                  {#each currentPrerequisites as prereq, idx (idx)}
                    <div class="dependency-row">
                      <SearchInput
                        value={prereq?.Name || getOptionLabel(missionOptionsForDeps, prereq?.Id)}
                        options={missionOptionsForDeps}
                        placeholder="Select mission..."
                        onselect={(e) => handleUpdatePrerequisite(idx, e.value)}
                      />
                      <button type="button" class="btn-icon danger" onclick={() => handleRemovePrerequisite(idx)} title="Remove">
                        &times;
                      </button>
                    </div>
                  {/each}
                {:else}
                  <div class="empty-text">No prerequisites</div>
                {/if}
                <button type="button" class="btn-add" onclick={handleAddPrerequisite}>
                  <span>+</span> Add Prerequisite
                </button>
              </div>

              <!-- Unlocks Column -->
              <div class="dependency-column">
                <h5>Unlocks</h5>
                <p class="column-hint">Missions that this one unlocks</p>

                {#if currentDependents.length > 0}
                  {#each currentDependents as dep, idx (idx)}
                    <div class="dependency-row">
                      <SearchInput
                        value={dep?.Name || getOptionLabel(missionOptionsForDeps, dep?.Id)}
                        options={missionOptionsForDeps}
                        placeholder="Select mission..."
                        onselect={(e) => handleUpdateDependent(idx, e.value)}
                      />
                      <button type="button" class="btn-icon danger" onclick={() => handleRemoveDependent(idx)} title="Remove">
                        &times;
                      </button>
                    </div>
                  {/each}
                {:else}
                  <div class="empty-text">No unlocks</div>
                {/if}
                <button type="button" class="btn-add" onclick={handleAddDependent}>
                  <span>+</span> Add Unlock
                </button>
              </div>
            </div>
          </div>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .chain-dialog {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    width: min(700px, 95vw);
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px;
    border-bottom: 1px solid var(--border-color, #555);
    flex-shrink: 0;
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 18px;
  }

  .dialog-close {
    background: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-color);
    border-radius: 4px;
    padding: 6px 12px;
    cursor: pointer;
  }

  .dialog-body {
    padding: 16px;
    overflow-y: auto;
    flex: 1;
  }

  /* Create Chain Form */
  .create-chain-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-field label,
  .form-field .label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted, #999);
  }

  .form-field input,
  .form-field select {
    padding: 8px 12px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background: var(--input-bg, var(--bg-color));
    color: var(--text-color);
    font-size: 14px;
  }

  .form-field input.error {
    border-color: var(--error-color, #ef4444);
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  @media (max-width: 500px) {
    .form-row {
      grid-template-columns: 1fr;
    }
  }

  .chain-details-section {
    background: var(--secondary-color);
  }

  .chain-details-form {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .field-error {
    font-size: 12px;
    color: var(--error-color, #ef4444);
  }

  .form-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 8px;
  }

  .btn {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
    border: 1px solid var(--border-color, #555);
  }

  .btn.primary {
    background: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .btn.secondary {
    background: transparent;
    color: var(--text-color);
  }

  /* Chain Content */
  .chain-content {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .section {
    background: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    padding: 16px;
  }

  .section-title {
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 600;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .warning-banner {
    background: var(--warning-bg, rgba(245, 158, 11, 0.1));
    border: 1px solid var(--warning-border, #f59e0b);
    border-radius: 4px;
    padding: 10px 12px;
    margin-bottom: 12px;
    font-size: 13px;
    color: var(--warning-text, #f59e0b);
  }

  /* Mission Layers */
  .mission-layers {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .layer {
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }

  .layer-label {
    flex-shrink: 0;
    width: 70px;
    font-size: 11px;
    text-transform: uppercase;
    color: var(--text-muted, #999);
    padding-top: 6px;
  }

  .layer-missions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    flex: 1;
  }

  .layer-arrow {
    text-align: center;
    color: var(--text-muted, #999);
    padding-left: 82px;
    font-size: 14px;
  }

  .mission-chip {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 12px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .mission-chip.current {
    background: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
    font-weight: 500;
  }

  .mission-chip.disconnected:not(.current) {
    border-color: var(--warning-border, #f59e0b);
    background: var(--warning-bg, rgba(245, 158, 11, 0.1));
    color: var(--warning-text, #f59e0b);
  }

  .current-badge {
    font-size: 9px;
    text-transform: uppercase;
    opacity: 0.8;
  }

  .disconnected-section {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px dashed var(--border-color, #555);
  }

  .disconnected-label {
    font-size: 12px;
    color: var(--warning-text, #f59e0b);
    margin-bottom: 8px;
    font-weight: 500;
  }

  .disconnected-missions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  /* Dependencies Section */
  .dependencies-section {
    background: var(--bg-color, var(--primary-color));
  }

  .dependencies-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 20px;
  }

  .dependency-column {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .dependency-column h5 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
  }

  .column-hint {
    margin: 0 0 8px 0;
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .dependency-row {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 6px;
    align-items: center;
  }

  .dependency-row :global(.searchable-select),
  .dependency-row :global(.dep-select) {
    width: 100%;
  }

  .btn-icon {
    width: 28px;
    height: 28px;
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    line-height: 1;
  }

  .btn-icon.danger:hover {
    border-color: var(--error-color, #ef4444);
    color: var(--error-color, #ef4444);
  }

  .btn-add {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 10px;
    font-size: 12px;
    background: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 4px;
    cursor: pointer;
    margin-top: 4px;
  }

  .btn-add:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .empty-text {
    font-size: 12px;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  @media (max-width: 600px) {
    .chain-dialog {
      width: 100%;
      height: 100%;
      max-height: 100vh;
      border-radius: 0;
    }

    .layer {
      flex-direction: column;
      gap: 4px;
    }

    .layer-label {
      width: auto;
      padding-top: 0;
    }

    .layer-arrow {
      padding-left: 0;
    }
  }
</style>
