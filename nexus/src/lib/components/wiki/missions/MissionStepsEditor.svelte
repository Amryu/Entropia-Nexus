<!--
  @component MissionStepsEditor
  Editor for mission steps + objective payloads.
-->
<script>
  // @ts-nocheck
  import { updateField } from '$lib/stores/wikiEditState.js';
  import { hasCondition } from '$lib/shopUtils.js';
  import { hasItemTag } from '$lib/util.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import WaypointInput from '$lib/components/wiki/WaypointInput.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  export let steps = [];
  export let fieldPath = 'Steps';
  export let mobMaturities = [];
  export let npcOptions = [];
  export let locationOptions = [];
  export let itemsIndex = {};
  /** Full item info map { id: { Name, Type } } for type checking */
  export let itemsMap = {};

  /** Mission's planet info for Explore objectives */
  export let missionPlanet = null; // { Id: number, Name: string }

  const objectiveTypeOptions = [
    { value: 'Dialog', label: 'Dialog' },
    { value: 'KillCount', label: 'Kill Count' },
    { value: 'KillCycle', label: 'Kill Cycle' },
    { value: 'Explore', label: 'Explore' },
    { value: 'Interact', label: 'Interact' },
    { value: 'HandIn', label: 'Hand In' },
    { value: 'CraftSuccess', label: 'Craft (Success)' },
    { value: 'CraftAttempt', label: 'Craft (Attempt)' },
    { value: 'CraftCycle', label: 'Craft (Cycle)' },
    { value: 'MiningCycle', label: 'Mining (Cycle)' },
    { value: 'MiningClaim', label: 'Mining (Claim)' },
    { value: 'MiningPoints', label: 'Mining (Points)' }
  ];

  const objectiveDefaults = {
    Dialog: { targetLocationId: null, dialogText: '' },
    KillCount: { useKillPoints: false, mobs: [], totalCountRequired: null },
    KillCycle: { useKillPoints: false, mobs: [], pedToCycle: null },
    Explore: { planetId: null, longitude: null, latitude: null, altitude: null },
    Interact: { targetLocationId: null },
    HandIn: { npcLocationId: null, items: [] },
    CraftSuccess: { totalCountRequired: null },
    CraftAttempt: { totalCountRequired: null },
    CraftCycle: { pedToCycle: null },
    MiningCycle: { totalCountRequired: null },
    MiningClaim: { totalCountRequired: null, minClaimValue: null },
    MiningPoints: { totalCountRequired: null }
  };

  let itemNameDrafts = {};

  // Single dialog state - null when closed, object when open
  let openMaturityDialog = null; // { stepIndex, objIndex, mobIndex }

  // Build unique mob options from maturities (using MobId as value)
  $: mobOptions = (() => {
    const mobMap = new Map();
    for (const maturity of mobMaturities) {
      const mobId = maturity?.MobId;
      const mobName = maturity?.Mob?.Name;
      if (mobId && mobName && !mobMap.has(mobId)) {
        mobMap.set(mobId, { label: mobName, value: mobId });
      }
    }
    return Array.from(mobMap.values()).sort((a, b) => a.label.localeCompare(b.label));
  })();

  // Build mob ID to name lookup
  $: mobIdToName = (() => {
    const map = new Map();
    for (const maturity of mobMaturities) {
      const mobId = maturity?.MobId;
      const mobName = maturity?.Mob?.Name;
      if (mobId && mobName) {
        map.set(mobId, mobName);
      }
    }
    return map;
  })();

  // Get mob name from ID
  function getMobName(mobId) {
    return mobIdToName.get(mobId) || `Mob #${mobId}`;
  }

  // Get maturities for a specific mob by MobId, sorted by level*HP ascending, bosses after non-bosses
  function getMaturitiesForMob(mobId) {
    if (!mobId) return [];
    const maturities = mobMaturities.filter(m => m?.MobId === mobId);
    return maturities.sort((a, b) => {
      const aIsBoss = a.Properties?.Boss === true;
      const bIsBoss = b.Properties?.Boss === true;
      if (aIsBoss !== bIsBoss) return aIsBoss ? 1 : -1;
      const aScore = (a.Properties?.Level || 0) * (a.Properties?.Health || 0);
      const bScore = (b.Properties?.Level || 0) * (b.Properties?.Health || 0);
      return aScore - bScore;
    });
  }

  function ensureArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function toNumber(value) {
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
  }

  function createStep() {
    return {
      Id: null,
      Index: steps.length + 1,
      Title: '',
      Description: '',
      Objectives: []
    };
  }

  function normalizeStepIndexes(list) {
    return list.map((step, index) => ({ ...step, Index: index + 1 }));
  }

  function updateSteps(newSteps) {
    updateField(fieldPath, newSteps);
  }

  function addStep() {
    updateSteps([...steps, createStep()]);
  }

  function removeStep(index) {
    const next = steps.filter((_, i) => i !== index);
    updateSteps(normalizeStepIndexes(next));
  }

  function updateStepField(index, key, value) {
    const next = steps.map((step, i) => {
      if (i !== index) return step;
      return { ...step, [key]: value };
    });
    updateSteps(next);
  }

  function addObjective(stepIndex) {
    const next = steps.map((step, i) => {
      if (i !== stepIndex) return step;
      const objectives = ensureArray(step.Objectives);
      return {
        ...step,
        Objectives: [
          ...objectives,
          { Id: null, Type: 'Dialog', Payload: { ...objectiveDefaults.Dialog } }
        ]
      };
    });
    updateSteps(next);
  }

  function removeObjective(stepIndex, objIndex) {
    const next = steps.map((step, i) => {
      if (i !== stepIndex) return step;
      const objectives = ensureArray(step.Objectives);
      return {
        ...step,
        Objectives: objectives.filter((_, idx) => idx !== objIndex)
      };
    });
    updateSteps(next);
    // Close dialog if it was for this objective
    if (openMaturityDialog?.stepIndex === stepIndex && openMaturityDialog?.objIndex === objIndex) {
      openMaturityDialog = null;
    }
  }

  function updateObjectivePayload(stepIndex, objIndex, patch) {
    const next = steps.map((step, i) => {
      if (i !== stepIndex) return step;
      const objectives = ensureArray(step.Objectives);
      const updated = objectives.map((obj, idx) => {
        if (idx !== objIndex) return obj;
        const payload = { ...(obj.Payload || {}), ...(patch || {}) };
        return { ...obj, Payload: payload };
      });
      return { ...step, Objectives: updated };
    });
    updateSteps(next);
  }

  function setObjectiveType(stepIndex, objIndex, type) {
    const defaults = objectiveDefaults[type] ? { ...objectiveDefaults[type] } : {};
    const next = steps.map((step, i) => {
      if (i !== stepIndex) return step;
      const objectives = ensureArray(step.Objectives);
      const updated = objectives.map((obj, idx) => {
        if (idx !== objIndex) return obj;
        return { ...obj, Type: type, Payload: defaults };
      });
      return { ...step, Objectives: updated };
    });
    updateSteps(next);
    openMaturityDialog = null;
  }

  function getObjectivePayload(stepIndex, objIndex) {
    return steps?.[stepIndex]?.Objectives?.[objIndex]?.Payload || {};
  }

  // ===== Kill Objective Functions =====

  function addMobEntry(stepIndex, objIndex) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const mobs = ensureArray(payload.mobs);
    updateObjectivePayload(stepIndex, objIndex, {
      mobs: [...mobs, { mobId: null, targets: [], countsPerTarget: null }]
    });
  }

  function removeMobEntry(stepIndex, objIndex, mobIndex) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const mobs = ensureArray(payload.mobs);
    updateObjectivePayload(stepIndex, objIndex, {
      mobs: mobs.filter((_, i) => i !== mobIndex)
    });
    // Close dialog if it was for this mob
    if (openMaturityDialog?.stepIndex === stepIndex &&
        openMaturityDialog?.objIndex === objIndex &&
        openMaturityDialog?.mobIndex === mobIndex) {
      openMaturityDialog = null;
    }
  }

  function handleMobSelect(stepIndex, objIndex, mobIndex, mobId) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const mobs = ensureArray(payload.mobs);

    if (!mobId) {
      const newMobs = mobs.map((m, i) => i === mobIndex ? { mobId: null, targets: [], countsPerTarget: null } : m);
      updateObjectivePayload(stepIndex, objIndex, { mobs: newMobs });
      return;
    }

    // Enable all maturities by default when selecting a mob
    const maturities = getMaturitiesForMob(mobId);
    const allTargets = maturities.map(m => m.Id);

    const newMobs = mobs.map((m, i) => {
      if (i !== mobIndex) return m;
      return { mobId, targets: allTargets, countsPerTarget: null };
    });

    updateObjectivePayload(stepIndex, objIndex, { mobs: newMobs });
  }

  function toggleKillPointsMode(stepIndex, objIndex) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const newUseKillPoints = !payload.useKillPoints;

    // Clear or initialize countsPerTarget for all mobs
    const mobs = ensureArray(payload.mobs).map(mob => ({
      ...mob,
      countsPerTarget: newUseKillPoints ? {} : null
    }));

    updateObjectivePayload(stepIndex, objIndex, {
      useKillPoints: newUseKillPoints,
      mobs
    });
  }

  function openDialog(stepIndex, objIndex, mobIndex) {
    openMaturityDialog = { stepIndex, objIndex, mobIndex };
  }

  function closeDialog() {
    openMaturityDialog = null;
  }

  function toggleMaturityEnabled(stepIndex, objIndex, mobIndex, maturityId, enabled) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const mobs = ensureArray(payload.mobs);
    const mob = mobs[mobIndex];
    if (!mob) return;

    const targets = ensureArray(mob.targets);
    let newTargets;
    if (enabled) {
      newTargets = targets.includes(maturityId) ? targets : [...targets, maturityId];
    } else {
      newTargets = targets.filter(id => id !== maturityId);
    }

    let newCountsPerTarget = { ...(mob.countsPerTarget || {}) };
    if (!enabled && newCountsPerTarget[maturityId] != null) {
      delete newCountsPerTarget[maturityId];
    }

    const newMobs = mobs.map((m, i) => {
      if (i !== mobIndex) return m;
      return {
        ...m,
        targets: newTargets,
        countsPerTarget: Object.keys(newCountsPerTarget).length > 0 ? newCountsPerTarget : null
      };
    });

    updateObjectivePayload(stepIndex, objIndex, { mobs: newMobs });
  }

  function updateMaturityCount(stepIndex, objIndex, mobIndex, maturityId, count) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const mobs = ensureArray(payload.mobs);
    const mob = mobs[mobIndex];
    if (!mob) return;

    const counts = { ...(mob.countsPerTarget || {}) };
    if (count == null || count === '') {
      delete counts[maturityId];
    } else {
      counts[maturityId] = count;
    }

    const newMobs = mobs.map((m, i) => {
      if (i !== mobIndex) return m;
      return {
        ...m,
        countsPerTarget: Object.keys(counts).length > 0 ? counts : null
      };
    });

    updateObjectivePayload(stepIndex, objIndex, { mobs: newMobs });
  }

  function getMaturityConfigSummary(mob) {
    if (!mob?.mobId) return 'Select mob first';
    const maturities = getMaturitiesForMob(mob.mobId);
    const targets = ensureArray(mob.targets);
    const enabledCount = targets.length;
    const totalCount = maturities.length;
    if (enabledCount === totalCount) {
      return `All ${totalCount}`;
    }
    return `${enabledCount}/${totalCount}`;
  }

  // ===== HandIn Functions =====

  function addHandInItem(stepIndex, objIndex) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const items = ensureArray(payload.items);
    updateObjectivePayload(stepIndex, objIndex, {
      items: [...items, { itemId: null, quantity: null, minPedValue: null, pedValue: null }]
    });
  }

  function updateHandInItem(stepIndex, objIndex, itemIndex, key, value) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const items = ensureArray(payload.items);
    const next = items.map((item, idx) => {
      if (idx !== itemIndex) return item;
      return { ...item, [key]: value };
    });
    updateObjectivePayload(stepIndex, objIndex, { items: next });
  }

  function removeHandInItem(stepIndex, objIndex, itemIndex) {
    const payload = getObjectivePayload(stepIndex, objIndex);
    const items = ensureArray(payload.items);
    updateObjectivePayload(stepIndex, objIndex, { items: items.filter((_, idx) => idx !== itemIndex) });
  }

  function getItemDraftKey(stepIndex, objIndex, itemIndex) {
    return `${stepIndex}-${objIndex}-${itemIndex}`;
  }

  function getItemDisplayName(itemId, key) {
    if (Object.prototype.hasOwnProperty.call(itemNameDrafts, key)) {
      return itemNameDrafts[key];
    }
    if (itemId != null && itemsIndex && itemsIndex[itemId]) {
      return itemsIndex[itemId];
    }
    return itemId != null ? `#${itemId}` : '';
  }

  function setItemDraft(key, value) {
    itemNameDrafts = { ...itemNameDrafts, [key]: value };
  }

  function handleHandInItemChange(stepIndex, objIndex, itemIndex, value) {
    const key = getItemDraftKey(stepIndex, objIndex, itemIndex);
    setItemDraft(key, value);
    if (value.trim().length === 0) {
      updateHandInItem(stepIndex, objIndex, itemIndex, 'itemId', null);
    }
  }

  function handleHandInItemSelect(stepIndex, objIndex, itemIndex, item) {
    const key = getItemDraftKey(stepIndex, objIndex, itemIndex);
    setItemDraft(key, item?.Name || '');
    updateHandInItem(stepIndex, objIndex, itemIndex, 'itemId', item?.Id ?? null);
  }

  // ===== Explore Functions =====

  function getExploreWaypointValue(payload) {
    return {
      planet: missionPlanet?.Name || null,
      planetId: missionPlanet?.Id || payload?.planetId || null,
      x: payload?.longitude ?? null,
      y: payload?.latitude ?? null,
      z: payload?.altitude ?? null,
      name: null
    };
  }

  function handleExploreWaypointChange(stepIndex, objIndex, detail) {
    updateObjectivePayload(stepIndex, objIndex, {
      planetId: missionPlanet?.Id || detail.planetId || null,
      longitude: detail.x,
      latitude: detail.y,
      altitude: detail.z
    });
  }

  function isItemDamageable(itemId) {
    if (!itemId) return false;
    const itemInfo = itemsMap[itemId];
    if (!itemInfo) return false;
    const pseudoItem = { Properties: { Type: itemInfo.Type } };
    if (!hasCondition(pseudoItem)) return false;
    if (hasItemTag(itemInfo.Name, 'L')) return false;
    return true;
  }

  // Helper to get display label from options by value
  function getOptionLabel(options, value) {
    if (!value) return '';
    const opt = options.find(o => o.value === String(value));
    return opt?.label || '';
  }

  // Helper to find option value by label (for select events)
  function getOptionValue(options, label) {
    if (!label) return null;
    const opt = options.find(o => o.label === label);
    return opt?.value || null;
  }
</script>

<div class="mission-steps-editor">
  {#if !steps || steps.length === 0}
    <div class="editor-empty">No steps yet.</div>
  {:else}
    {#each steps as step, stepIndex (step.Id || stepIndex)}
      <div class="step-card">
        <div class="step-header">
          <div class="step-title">
            <span class="step-index">Step {step.Index ?? stepIndex + 1}</span>
            <input
              class="step-input"
              type="text"
              value={step.Title ?? ''}
              placeholder="Step title"
              on:input={(e) => updateStepField(stepIndex, 'Title', e.target.value)}
            />
          </div>
          <button type="button" class="btn-icon danger" on:click={() => removeStep(stepIndex)} title="Remove step">×</button>
        </div>

        <div class="step-description-editor">
          <RichTextEditor
            content={step.Description ?? ''}
            placeholder="Step description"
            on:change={(e) => updateStepField(stepIndex, 'Description', e.detail.content)}
          />
        </div>

        <div class="objective-section">
          <div class="objective-header">
            <span>Objectives</span>
          </div>

          {#if !step.Objectives || step.Objectives.length === 0}
            <div class="editor-empty">No objectives yet.</div>
          {:else}
            {#each step.Objectives as objective, objIndex (objective.Id || objIndex)}
              {@const payload = objective.Payload || {}}
              <div class="objective-row">
                <div class="objective-controls">
                  <select
                    class="objective-select"
                    value={objective.Type || 'Dialog'}
                    on:change={(e) => setObjectiveType(stepIndex, objIndex, e.target.value)}
                  >
                    {#each objectiveTypeOptions as option}
                      <option value={option.value}>{option.label}</option>
                    {/each}
                  </select>
                  <button type="button" class="btn-icon danger" on:click={() => removeObjective(stepIndex, objIndex)} title="Remove objective">×</button>
                </div>

                <div class="objective-editor">
                  {#if objective.Type === 'Dialog'}
                    <div class="objective-grid">
                      <div class="objective-field full">
                        <label>NPC</label>
                        <SearchInput
                          value={getOptionLabel(npcOptions, payload.targetLocationId)}
                          options={npcOptions}
                          placeholder="Search NPC..."
                          on:select={(e) => updateObjectivePayload(stepIndex, objIndex, { targetLocationId: toNumber(e.detail.value) })}
                        />
                      </div>
                      <div class="objective-field full">
                        <label>Dialog Text</label>
                        <div class="dialog-text-editor">
                          <RichTextEditor
                            content={payload.dialogText ?? ''}
                            placeholder="Dialog cue"
                            on:change={(e) => updateObjectivePayload(stepIndex, objIndex, { dialogText: e.detail.content })}
                          />
                        </div>
                      </div>
                    </div>
                  {:else if objective.Type === 'Interact'}
                    <div class="objective-grid">
                      <div class="objective-field full">
                        <label>Target</label>
                        <SearchInput
                          value={getOptionLabel(locationOptions, payload.targetLocationId)}
                          options={locationOptions}
                          placeholder="Search location..."
                          on:select={(e) => updateObjectivePayload(stepIndex, objIndex, { targetLocationId: toNumber(e.detail.value) })}
                        />
                      </div>
                    </div>
                  {:else if objective.Type === 'Explore'}
                    <div class="objective-field full">
                      <WaypointInput
                        value={getExploreWaypointValue(payload)}
                        hidePlanet={!!missionPlanet}
                        planetLocked={!!missionPlanet}
                        hideName={true}
                        nameLocked={true}
                        on:change={(e) => handleExploreWaypointChange(stepIndex, objIndex, e.detail)}
                      />
                    </div>
                  {:else if objective.Type === 'KillCount' || objective.Type === 'KillCycle'}
                    {@const useKillPoints = payload.useKillPoints === true}
                    {@const mobs = ensureArray(payload.mobs)}
                    <div class="kill-objective">
                      <div class="kill-header">
                        <span class="kill-label">Targets</span>
                        <button
                          type="button"
                          class="kill-points-toggle"
                          class:active={useKillPoints}
                          on:click={() => toggleKillPointsMode(stepIndex, objIndex)}
                          title={useKillPoints ? 'Switch to simple kill count' : 'Switch to kill points mode'}
                        >
                          {useKillPoints ? 'Kill Points' : 'Simple'}
                        </button>
                      </div>

                      <div class="mob-list">
                        {#each mobs as mob, mobIndex (mobIndex)}
                          {@const maturitiesForMob = getMaturitiesForMob(mob.mobId)}
                          <div class="mob-row">
                            <div class="mob-search">
                              <SearchInput
                                value={mob.mobId || ''}
                                placeholder="Search mob..."
                                options={mobOptions}
                                on:select={(e) => handleMobSelect(stepIndex, objIndex, mobIndex, e.detail.value)}
                              />
                            </div>
                            <button
                              type="button"
                              class="configure-btn"
                              disabled={!mob.mobId}
                              on:click={() => openDialog(stepIndex, objIndex, mobIndex)}
                            >
                              {getMaturityConfigSummary(mob)}
                            </button>
                            <button
                              type="button"
                              class="btn-icon danger"
                              on:click={() => removeMobEntry(stepIndex, objIndex, mobIndex)}
                              title="Remove mob"
                            >×</button>
                          </div>
                        {/each}
                        <button type="button" class="btn-add" on:click={() => addMobEntry(stepIndex, objIndex)}>
                          <span>+</span> Add Mob
                        </button>
                      </div>

                      <div class="kill-options">
                        {#if objective.Type === 'KillCount'}
                          <div class="objective-field">
                            <label>{useKillPoints ? 'Total Points' : 'Total Count'}</label>
                            <input
                              type="number"
                              min="0"
                              placeholder="0"
                              value={payload.totalCountRequired ?? ''}
                              on:input={(e) => updateObjectivePayload(stepIndex, objIndex, { totalCountRequired: toNumber(e.target.value) })}
                            />
                          </div>
                        {:else if objective.Type === 'KillCycle'}
                          <div class="objective-field">
                            <label>PED to Cycle</label>
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              placeholder="0"
                              value={payload.pedToCycle ?? ''}
                              on:input={(e) => updateObjectivePayload(stepIndex, objIndex, { pedToCycle: toNumber(e.target.value) })}
                            />
                          </div>
                        {/if}
                      </div>
                    </div>
                  {:else if objective.Type === 'HandIn'}
                    <div class="objective-grid">
                      <div class="objective-field full">
                        <label>NPC</label>
                        <SearchInput
                          value={getOptionLabel(npcOptions, payload.npcLocationId)}
                          options={npcOptions}
                          placeholder="Search NPC..."
                          on:select={(e) => updateObjectivePayload(stepIndex, objIndex, { npcLocationId: toNumber(e.detail.value) })}
                        />
                      </div>
                      <div class="objective-field full">
                        <label>Items</label>
                        <div class="handin-list">
                          {#each ensureArray(payload.items) as item, itemIndex}
                            {@const itemKey = getItemDraftKey(stepIndex, objIndex, itemIndex)}
                            {@const damageable = isItemDamageable(item.itemId)}
                            <div class="handin-row" class:has-min-tt={damageable}>
                              <SearchInput
                                value={getItemDisplayName(item.itemId, itemKey)}
                                placeholder="Search item..."
                                apiEndpoint="/search/items"
                                displayFn={(item) => item?.Name || ''}
                                on:change={(e) => handleHandInItemChange(stepIndex, objIndex, itemIndex, e.detail.value)}
                                on:select={(e) => handleHandInItemSelect(stepIndex, objIndex, itemIndex, e.detail.data)}
                              />
                              <input
                                type="number"
                                min="0"
                                step="1"
                                placeholder="Quantity"
                                value={item.quantity ?? ''}
                                on:input={(e) => updateHandInItem(stepIndex, objIndex, itemIndex, 'quantity', toNumber(e.target.value))}
                              />
                              {#if damageable}
                                <input
                                  type="number"
                                  min="0"
                                  step="0.01"
                                  placeholder="Min TT required"
                                  title="Minimum TT required (optional - full TT required if not specified)"
                                  value={item.minPedValue ?? ''}
                                  on:input={(e) => updateHandInItem(stepIndex, objIndex, itemIndex, 'minPedValue', toNumber(e.target.value))}
                                />
                              {/if}
                              <input
                                type="number"
                                min="0"
                                step="0.01"
                                placeholder="PED"
                                value={item.pedValue ?? ''}
                                on:input={(e) => updateHandInItem(stepIndex, objIndex, itemIndex, 'pedValue', toNumber(e.target.value))}
                              />
                              <button type="button" class="btn-icon danger" on:click={() => removeHandInItem(stepIndex, objIndex, itemIndex)} title="Remove item">×</button>
                            </div>
                          {/each}
                          <button type="button" class="btn-add" on:click={() => addHandInItem(stepIndex, objIndex)}><span>+</span> Add Item</button>
                        </div>
                      </div>
                    </div>
                  {:else if objective.Type === 'CraftSuccess' || objective.Type === 'CraftAttempt'}
                    <div class="objective-grid">
                      <div class="objective-field">
                        <label>{objective.Type === 'CraftSuccess' ? 'Successful Crafts' : 'Craft Attempts'}</label>
                        <input
                          type="number"
                          min="0"
                          placeholder="0"
                          value={payload.totalCountRequired ?? ''}
                          on:input={(e) => updateObjectivePayload(stepIndex, objIndex, { totalCountRequired: toNumber(e.target.value) })}
                        />
                      </div>
                    </div>
                  {:else if objective.Type === 'CraftCycle'}
                    <div class="objective-grid">
                      <div class="objective-field">
                        <label>PED to Cycle</label>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          placeholder="0"
                          value={payload.pedToCycle ?? ''}
                          on:input={(e) => updateObjectivePayload(stepIndex, objIndex, { pedToCycle: toNumber(e.target.value) })}
                        />
                      </div>
                    </div>
                  {:else if objective.Type === 'MiningCycle' || objective.Type === 'MiningPoints'}
                    <div class="objective-grid">
                      <div class="objective-field">
                        <label>{objective.Type === 'MiningCycle' ? 'Mining Drops' : 'Mining Points'}</label>
                        <input
                          type="number"
                          min="0"
                          placeholder="0"
                          value={payload.totalCountRequired ?? ''}
                          on:input={(e) => updateObjectivePayload(stepIndex, objIndex, { totalCountRequired: toNumber(e.target.value) })}
                        />
                      </div>
                    </div>
                  {:else if objective.Type === 'MiningClaim'}
                    <div class="objective-grid">
                      <div class="objective-field">
                        <label>Claims Required</label>
                        <input
                          type="number"
                          min="0"
                          placeholder="0"
                          value={payload.totalCountRequired ?? ''}
                          on:input={(e) => updateObjectivePayload(stepIndex, objIndex, { totalCountRequired: toNumber(e.target.value) })}
                        />
                      </div>
                      <div class="objective-field">
                        <label>Min Claim Value (PED)</label>
                        <input
                          type="number"
                          min="0"
                          step="0.01"
                          placeholder="Any"
                          value={payload.minClaimValue ?? ''}
                          on:input={(e) => updateObjectivePayload(stepIndex, objIndex, { minClaimValue: toNumber(e.target.value) })}
                        />
                      </div>
                    </div>
                  {/if}
                </div>
              </div>
            {/each}
          {/if}
          <button type="button" class="btn-add" on:click={() => addObjective(stepIndex)}><span>+</span> Add Objective</button>
        </div>
      </div>
    {/each}
  {/if}
  <button type="button" class="btn-add" on:click={addStep}><span>+</span> Add Step</button>
</div>

<!-- Maturity Configuration Dialog (rendered once, outside the loop) -->
{#if openMaturityDialog}
  {@const { stepIndex, objIndex, mobIndex } = openMaturityDialog}
  {@const dialogMobId = ensureArray(getObjectivePayload(stepIndex, objIndex).mobs)[mobIndex]?.mobId}
  {@const maturitiesForMob = getMaturitiesForMob(dialogMobId)}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="dialog-overlay" on:click={closeDialog}>
    <div class="maturity-dialog" on:click|stopPropagation>
      <div class="dialog-header">
        <h3>Configure Maturities: {getMobName(dialogMobId)}</h3>
        <button type="button" class="btn-icon" on:click={closeDialog}>×</button>
      </div>
      <div class="dialog-content">
        {#if !dialogMobId || maturitiesForMob.length === 0}
          <div class="dialog-empty">No maturities found for this mob.</div>
        {:else}
          {@const payload = getObjectivePayload(stepIndex, objIndex)}
          {@const useKillPoints = payload.useKillPoints === true}
          <div class="maturity-list" class:has-count-column={useKillPoints}>
            <div class="maturity-list-header">
              <span class="maturity-col-enabled">Enabled</span>
              <span class="maturity-col-name">Maturity</span>
              <span class="maturity-col-stats">Level / HP</span>
              {#if useKillPoints}
                <span class="maturity-col-count">Count</span>
              {/if}
            </div>
            {#each maturitiesForMob as maturity (maturity.Id)}
              {@const mob = ensureArray(getObjectivePayload(stepIndex, objIndex).mobs)[mobIndex]}
              {@const isEnabled = ensureArray(mob?.targets).includes(maturity.Id)}
              {@const isBoss = maturity.Properties?.Boss === true}
              <div class="maturity-row" class:disabled={!isEnabled} class:boss={isBoss}>
                <label class="maturity-col-enabled">
                  <input
                    type="checkbox"
                    checked={isEnabled}
                    on:change={(e) => toggleMaturityEnabled(stepIndex, objIndex, mobIndex, maturity.Id, e.target.checked)}
                  />
                </label>
                <span class="maturity-col-name">
                  {maturity.Name}
                  {#if isBoss}
                    <span class="boss-badge">Boss</span>
                  {/if}
                </span>
                <span class="maturity-col-stats">
                  {maturity.Properties?.Level ?? '?'} / {maturity.Properties?.Health ?? '?'}
                </span>
                {#if useKillPoints}
                  <div class="maturity-col-count">
                    <input
                      type="number"
                      min="0"
                      placeholder="0"
                      disabled={!isEnabled}
                      value={ensureArray(getObjectivePayload(stepIndex, objIndex).mobs)[mobIndex]?.countsPerTarget?.[maturity.Id] ?? ''}
                      on:input={(e) => updateMaturityCount(stepIndex, objIndex, mobIndex, maturity.Id, toNumber(e.target.value))}
                    />
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
      <div class="dialog-footer">
        <button type="button" class="btn-primary" on:click={closeDialog}>Done</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .mission-steps-editor {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .btn-add {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 4px;
    width: 100%;
  }

  .btn-add:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  .editor-empty {
    font-size: 13px;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .step-card {
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 12px;
    background: var(--secondary-color);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .step-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .step-title {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: 1;
  }

  .step-index {
    font-size: 12px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .step-input {
    flex: 1;
    background: var(--input-bg, var(--bg-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    padding: 4px 6px;
    color: var(--text-color);
    font-size: 13px;
  }

  .step-description-editor,
  .dialog-text-editor {
    font-size: 12px;
  }

  .step-description-editor :global(.rich-text-editor),
  .dialog-text-editor :global(.rich-text-editor) {
    min-height: 60px;
  }

  .objective-section {
    border-top: 1px solid var(--border-color, #555);
    padding-top: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .objective-header {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-bottom: 4px;
  }

  .objective-row {
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 8px;
    background: var(--bg-color, #1b1b1b);
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .objective-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .objective-select {
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    padding: 4px 6px;
    color: var(--text-color);
    font-size: 12px;
  }

  .objective-editor {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .objective-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 8px;
  }

  .objective-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted, #999);
  }

  .objective-field.full {
    grid-column: 1 / -1;
  }

  .objective-field label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .objective-field input {
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    padding: 4px 6px;
    color: var(--text-color);
    font-size: 12px;
    height: 28px;
    box-sizing: border-box;
  }

  /* Kill objective styles */
  .kill-objective {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .kill-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .kill-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--text-muted, #999);
  }

  .kill-points-toggle {
    height: 24px;
    padding: 0 10px;
    font-size: 11px;
    font-weight: 500;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .kill-points-toggle:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--text-color);
  }

  .kill-points-toggle.active {
    background: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .mob-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .mob-row {
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: 6px;
    align-items: center;
  }

  .mob-search {
    min-width: 0;
  }

  .configure-btn {
    height: 28px;
    padding: 0 10px;
    font-size: 11px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .configure-btn:hover:not(:disabled) {
    border-color: var(--accent-color, #4a9eff);
  }

  .configure-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .kill-options {
    display: flex;
    gap: 12px;
  }

  .kill-options .objective-field {
    flex: 1;
    max-width: 200px;
  }

  /* Dialog styles */
  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .maturity-dialog {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    width: 90%;
    max-width: 500px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .dialog-content {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }

  .dialog-empty {
    padding: 24px;
    text-align: center;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .dialog-footer {
    padding: 12px 16px;
    border-top: 1px solid var(--border-color, #555);
    display: flex;
    justify-content: flex-end;
  }

  .btn-primary {
    padding: 6px 16px;
    font-size: 12px;
    background: var(--accent-color, #4a9eff);
    border: none;
    border-radius: 4px;
    color: white;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-primary:hover {
    opacity: 0.9;
  }

  /* Maturity list styles */
  .maturity-list {
    display: flex;
    flex-direction: column;
  }

  .maturity-list-header {
    display: grid;
    grid-template-columns: 60px 1fr 100px;
    gap: 8px;
    padding: 8px 16px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--text-muted, #999);
    background: var(--bg-color);
    border-bottom: 1px solid var(--border-color, #555);
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .has-count-column .maturity-list-header {
    grid-template-columns: 60px 1fr 100px 80px;
  }

  .maturity-row {
    display: grid;
    grid-template-columns: 60px 1fr 100px;
    gap: 8px;
    padding: 8px 16px;
    align-items: center;
    border-bottom: 1px solid var(--border-color, #555);
    transition: background-color 0.15s;
  }

  .has-count-column .maturity-row {
    grid-template-columns: 60px 1fr 100px 80px;
  }

  .maturity-row:last-child {
    border-bottom: none;
  }

  .maturity-row:hover {
    background: var(--hover-color);
  }

  .maturity-row.disabled {
    opacity: 0.5;
  }

  .maturity-row.boss {
    background: rgba(255, 193, 7, 0.1);
  }

  .maturity-row.boss:hover {
    background: rgba(255, 193, 7, 0.15);
  }

  .maturity-col-enabled {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .maturity-col-enabled input[type="checkbox"] {
    width: 16px;
    height: 16px;
    cursor: pointer;
  }

  .maturity-col-name {
    font-size: 13px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .boss-badge {
    font-size: 10px;
    padding: 1px 4px;
    background: var(--warning-color, #ffc107);
    color: #000;
    border-radius: 3px;
    font-weight: 600;
  }

  .maturity-col-stats {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .maturity-col-count input {
    width: 100%;
    height: 26px;
    padding: 0 6px;
    font-size: 12px;
    background: var(--input-bg, var(--bg-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  .maturity-col-count input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* HandIn list styles */
  .handin-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .handin-row {
    display: grid;
    gap: 6px;
    align-items: center;
    grid-template-columns: minmax(180px, 2fr) minmax(80px, 1fr) minmax(80px, 1fr) auto;
  }

  .handin-row.has-min-tt {
    grid-template-columns: minmax(180px, 2fr) repeat(3, minmax(80px, 1fr)) auto;
  }

  .handin-row :global(.item-search),
  .objective-field :global(.searchable-select) {
    width: 100%;
  }

  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-icon:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .btn-icon.danger:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  @media (max-width: 700px) {
    .objective-grid {
      grid-template-columns: 1fr;
    }

    .mob-row {
      grid-template-columns: 1fr auto;
      gap: 6px;
    }

    .mob-row .mob-search {
      grid-column: 1 / -1;
    }

    .kill-options {
      flex-direction: column;
    }

    .kill-options .objective-field {
      max-width: none;
    }

    .handin-row {
      grid-template-columns: 1fr;
    }

    .handin-row .btn-icon {
      justify-self: flex-end;
    }

    .maturity-dialog {
      width: 95%;
      max-height: 90vh;
    }

    .maturity-list-header,
    .maturity-row {
      grid-template-columns: 50px 1fr 70px;
    }

    .has-count-column .maturity-list-header,
    .has-count-column .maturity-row {
      grid-template-columns: 50px 1fr 70px 60px;
    }
  }
</style>
