<!--
  @component FishingAdvisor
  Simplified fishing rig builder. Select a rod and one attachment per category,
  view individual stats and an aggregated summary.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { createPreference } from '$lib/preferences.js';
  import EntityPicker from './EntityPicker.svelte';
  import FishingPickerDialog from './FishingPickerDialog.svelte';

  let {
    fishingRods = [],
    fishingReels = [],
    fishingBlanks = [],
    fishingLines = [],
    fishingLures = []
  } = $props();

  const alpha = (a, b) => (a?.Name || '').localeCompare(b?.Name || '', undefined, { numeric: true });

  let rods = $derived(fishingRods.filter(r => r.Properties?.RodType !== 'Baitfishing').sort(alpha));
  let reels = $derived([...fishingReels].sort(alpha));
  let blanks = $derived([...fishingBlanks].sort(alpha));
  let lines = $derived([...fishingLines].sort(alpha));
  let lures = $derived([...fishingLures].sort(alpha));

  // ===== State =====
  let rod = $state(null);
  let reel = $state(null);
  let blank = $state(null);
  let line = $state(null);
  let lure = $state(null);

  let savedRigs = $state([]);
  let activeRigId = $state(null);

  // ===== Persistence =====
  let prefLoaded = $state(false);
  const pref = createPreference('gear-advisor.fishing-advisor', null, { debounceMs: 600 });

  onMount(async () => {
    const userId = $page.data?.user?.id ?? null;
    await pref.load(userId);
    let stored;
    pref.subscribe(v => stored = v)();
    if (stored) {
      rod = stored.rod ?? null;
      reel = stored.reel ?? null;
      blank = stored.blank ?? null;
      line = stored.line ?? null;
      lure = stored.lure ?? null;
      savedRigs = stored.savedRigs || [];
      activeRigId = stored.activeRigId ?? null;
    }
    prefLoaded = true;
  });

  $effect(() => {
    const _r = rod; const _re = reel; const _b = blank; const _li = line; const _lu = lure;
    const _sr = savedRigs; const _id = activeRigId;
    if (!prefLoaded) return;
    pref.set({ rod: _r, reel: _re, blank: _b, line: _li, lure: _lu, savedRigs: _sr, activeRigId: _id });
  });

  // ===== Resolved entities =====
  let rodEntity = $derived(rod ? rods.find(e => e.Name === rod) || fishingRods.find(e => e.Name === rod) : null);
  let reelEntity = $derived(reel ? reels.find(e => e.Name === reel) : null);
  let blankEntity = $derived(blank ? blanks.find(e => e.Name === blank) : null);
  let lineEntity = $derived(line ? lines.find(e => e.Name === line) : null);
  let lureEntity = $derived(lure ? lures.find(e => e.Name === lure) : null);

  const SLOTS = [
    { key: 'reel', label: 'Reel', stats: ['Strength', 'Speed'] },
    { key: 'blank', label: 'Blank', stats: ['Strength', 'Flexibility'] },
    { key: 'line', label: 'Line', stats: ['Strength', 'Flexibility', 'Length'] },
    { key: 'lure', label: 'Lure', stats: ['Depth', 'Quality'] }
  ];

  const ROD_COLUMNS = [
    { key: 'Name', label: 'Name' },
    { key: 'Properties.RodType', label: 'Type' },
    { key: 'Properties.Strength', label: 'Str', align: 'right' },
    { key: 'Properties.Flexibility', label: 'Flex', align: 'right' },
    { key: 'Profession.Name', label: 'Profession' },
    { key: 'Properties.Skill.LearningIntervalStart', label: 'Min Lvl', align: 'right' },
    { key: 'Properties.Skill.LearningIntervalEnd', label: 'Max Lvl', align: 'right' },
    { key: 'Properties.Economy.MaxTT', label: 'MaxTT', align: 'right', suffix: 'PED' },
    { key: 'Properties.Economy.Decay', label: 'Decay', align: 'right', suffix: 'PEC' },
    { key: 'Properties.Economy.AmmoBurn', label: 'Ammo Burn', align: 'right' },
  ];

  const SLOT_COLUMNS = {
    reel: [
      { key: 'Name', label: 'Name' },
      { key: 'Properties.Strength', label: 'Strength', align: 'right' },
      { key: 'Properties.Speed', label: 'Speed', align: 'right' },
      { key: 'Properties.Economy.MaxTT', label: 'MaxTT', align: 'right', suffix: 'PED' },
      { key: 'Properties.Economy.Decay', label: 'Decay', align: 'right', suffix: 'PEC' },
      { key: 'Properties.Weight', label: 'Weight', align: 'right', suffix: 'kg' },
    ],
    blank: [
      { key: 'Name', label: 'Name' },
      { key: 'Properties.Strength', label: 'Strength', align: 'right' },
      { key: 'Properties.Flexibility', label: 'Flexibility', align: 'right' },
      { key: 'Properties.Economy.MaxTT', label: 'MaxTT', align: 'right', suffix: 'PED' },
      { key: 'Properties.Economy.Decay', label: 'Decay', align: 'right', suffix: 'PEC' },
      { key: 'Properties.Weight', label: 'Weight', align: 'right', suffix: 'kg' },
    ],
    line: [
      { key: 'Name', label: 'Name' },
      { key: 'Properties.Strength', label: 'Strength', align: 'right' },
      { key: 'Properties.Flexibility', label: 'Flexibility', align: 'right' },
      { key: 'Properties.Length', label: 'Length', align: 'right' },
      { key: 'Properties.Economy.MaxTT', label: 'MaxTT', align: 'right', suffix: 'PED' },
      { key: 'Properties.Economy.Decay', label: 'Decay', align: 'right', suffix: 'PEC' },
      { key: 'Properties.Weight', label: 'Weight', align: 'right', suffix: 'kg' },
    ],
    lure: [
      { key: 'Name', label: 'Name' },
      { key: 'Properties.Depth', label: 'Depth', align: 'right' },
      { key: 'Properties.Quality', label: 'Quality', align: 'right' },
      { key: 'Properties.Economy.MaxTT', label: 'MaxTT', align: 'right', suffix: 'PED' },
      { key: 'Properties.Economy.Decay', label: 'Decay', align: 'right', suffix: 'PEC' },
      { key: 'Properties.Weight', label: 'Weight', align: 'right', suffix: 'kg' },
    ]
  };

  // Dialog state
  let dialogOpen = $state(false);
  let dialogSlot = $state(null);

  let dialogTitle = $derived(
    dialogSlot === 'rod' ? 'Select Fishing Rod'
    : dialogSlot ? `Select ${SLOTS.find(s => s.key === dialogSlot)?.label ?? ''}`
    : ''
  );

  let dialogEntities = $derived(
    dialogSlot === 'rod' ? rods
    : dialogSlot ? entitiesFor(dialogSlot)
    : []
  );

  let dialogColumns = $derived(
    dialogSlot === 'rod' ? ROD_COLUMNS
    : dialogSlot ? (SLOT_COLUMNS[dialogSlot] || [])
    : []
  );

  let dialogSelected = $derived(
    dialogSlot === 'rod' ? rod
    : dialogSlot === 'reel' ? reel
    : dialogSlot === 'blank' ? blank
    : dialogSlot === 'line' ? line
    : dialogSlot === 'lure' ? lure
    : null
  );

  function openDialog(slotKey) {
    dialogSlot = slotKey;
    dialogOpen = true;
  }

  function handleDialogSelect(entity) {
    if (dialogSlot === 'rod') rod = entity?.Name ?? null;
    else handleSelect(dialogSlot, entity);
  }

  function entitiesFor(key) {
    if (key === 'reel') return reels;
    if (key === 'blank') return blanks;
    if (key === 'line') return lines;
    if (key === 'lure') return lures;
    return [];
  }

  function entityFor(key) {
    if (key === 'reel') return reelEntity;
    if (key === 'blank') return blankEntity;
    if (key === 'line') return lineEntity;
    if (key === 'lure') return lureEntity;
    return null;
  }

  function handleSelect(key, item) {
    if (key === 'reel') reel = item?.Name ?? null;
    else if (key === 'blank') blank = item?.Name ?? null;
    else if (key === 'line') line = item?.Name ?? null;
    else if (key === 'lure') lure = item?.Name ?? null;
  }

  function handleClear(key) {
    if (key === 'reel') reel = null;
    else if (key === 'blank') blank = null;
    else if (key === 'line') line = null;
    else if (key === 'lure') lure = null;
  }

  // ===== Summary =====
  const SUMMARY_STATS = ['Strength', 'Flexibility', 'Speed', 'Length', 'Depth', 'Quality'];

  let summary = $derived.by(() => {
    const all = [rodEntity, reelEntity, blankEntity, lineEntity, lureEntity];
    const result = {};
    for (const stat of SUMMARY_STATS) {
      let total = 0;
      let found = false;
      for (const e of all) {
        const v = e?.Properties?.[stat];
        if (v != null) { total += v; found = true; }
      }
      if (found) result[stat] = total;
    }
    return result;
  });

  let economySummary = $derived.by(() => {
    const all = [rodEntity, reelEntity, blankEntity, lineEntity, lureEntity];
    let weight = 0, maxTT = 0, decay = 0, ammoBurn = 0;
    let hasAny = false;
    for (const e of all) {
      if (!e) continue;
      hasAny = true;
      const p = e.Properties;
      if (p.Weight != null) weight += p.Weight;
      if (p.Economy?.MaxTT != null) maxTT += p.Economy.MaxTT;
      if (p.Economy?.Decay != null) decay += p.Economy.Decay;
      if (p.Economy?.AmmoBurn != null) ammoBurn += p.Economy.AmmoBurn;
    }
    const cost = decay != null && ammoBurn != null ? decay + ammoBurn / 100 : null;
    return hasAny ? { weight, maxTT, decay, ammoBurn, cost } : null;
  });

  let itemCount = $derived(
    [rodEntity, reelEntity, blankEntity, lineEntity, lureEntity].filter(Boolean).length
  );

  // ===== Saved rigs =====
  let editingName = $state(null);
  let editValue = $state('');

  function buildRigName() {
    if (rodEntity) return rodEntity.Name;
    return 'Untitled Rig';
  }

  function createRig() {
    const newRig = {
      id: Date.now().toString(36),
      name: buildRigName(),
      rod, reel, blank, line, lure,
      savedAt: new Date().toISOString()
    };
    savedRigs = [...savedRigs, newRig];
    activeRigId = newRig.id;
  }

  function cloneRig() {
    if (!activeRigId) return;
    const source = savedRigs.find(s => s.id === activeRigId);
    if (!source) return;
    const clone = {
      ...JSON.parse(JSON.stringify(source)),
      id: Date.now().toString(36),
      name: source.name + ' (copy)',
      savedAt: new Date().toISOString()
    };
    savedRigs = [...savedRigs, clone];
    activeRigId = clone.id;
  }

  function deleteRig() {
    if (!activeRigId) return;
    const idx = savedRigs.findIndex(s => s.id === activeRigId);
    savedRigs = savedRigs.filter(s => s.id !== activeRigId);
    if (savedRigs.length > 0) {
      const next = savedRigs[Math.min(idx, savedRigs.length - 1)];
      activeRigId = next.id;
      loadRig(next);
    } else {
      activeRigId = null;
    }
  }

  function loadRig(rig) {
    rod = rig.rod ?? null;
    reel = rig.reel ?? null;
    blank = rig.blank ?? null;
    line = rig.line ?? null;
    lure = rig.lure ?? null;
  }

  function selectRig(rig) {
    activeRigId = rig.id;
    loadRig(rig);
  }

  function renameActiveRig() {
    if (!activeRigId) return;
    const rig = savedRigs.find(s => s.id === activeRigId);
    if (rig) { editingName = rig.id; editValue = rig.name; }
  }

  function finishRename(id) {
    if (editValue.trim()) {
      savedRigs = savedRigs.map(s => s.id === id ? { ...s, name: editValue.trim() } : s);
    }
    editingName = null;
    editValue = '';
  }

  function exportRigs() {
    const data = JSON.stringify(savedRigs, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fishing-rigs.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  function importRigs() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = e.target?.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const imported = JSON.parse(text);
        if (!Array.isArray(imported)) return;
        const newRigs = imported.map(s => ({
          ...s,
          id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
          savedAt: new Date().toISOString()
        }));
        savedRigs = [...savedRigs, ...newRigs];
      } catch { /* ignore invalid files */ }
    };
    input.click();
  }

  // Auto-save active rig
  let autoSaveTimer = null;
  $effect(() => {
    const _rod = rod; const _reel = reel; const _blank = blank; const _line = line; const _lure = lure;
    const _id = activeRigId;
    if (!_id) return;
    if (autoSaveTimer) clearTimeout(autoSaveTimer);
    autoSaveTimer = setTimeout(() => {
      savedRigs = savedRigs.map(s => s.id === _id ? {
        ...s, rod: _rod, reel: _reel, blank: _blank, line: _line, lure: _lure,
        savedAt: new Date().toISOString()
      } : s);
    }, 2000);
  });

  function fmtStat(v) {
    if (v == null) return '-';
    return Number.isInteger(v) ? v.toString() : v.toFixed(1);
  }
</script>

<div class="fishing-advisor">
  <!-- Left sidebar: saved rigs -->
  <aside class="fa-left">
    <div class="set-sidebar">
      <div class="set-toolbar">
        <button type="button" class="toolbar-btn btn-create" onclick={createRig} title="Save current rig">Create</button>
        <button type="button" class="toolbar-btn" onclick={cloneRig} disabled={!activeRigId} title="Clone selected rig">Clone</button>
        <button type="button" class="toolbar-btn" onclick={renameActiveRig} disabled={!activeRigId} title="Rename selected rig">Rename</button>
        <button type="button" class="toolbar-btn btn-delete" onclick={deleteRig} disabled={!activeRigId} title="Delete selected rig">Delete</button>
        <button type="button" class="toolbar-btn" onclick={importRigs} title="Import rigs from file">Import</button>
        <button type="button" class="toolbar-btn" onclick={exportRigs} disabled={savedRigs.length === 0} title="Export all rigs">Export</button>
      </div>

      <div class="set-list">
        {#if savedRigs.length === 0}
          <div class="set-empty">No saved rigs</div>
        {:else}
          {#each savedRigs as rig (rig.id)}
            <button
              type="button"
              class="set-item"
              class:active={rig.id === activeRigId}
              onclick={() => selectRig(rig)}
              ondblclick={() => { editingName = rig.id; editValue = rig.name; }}
            >
              {#if editingName === rig.id}
                <!-- svelte-ignore a11y_autofocus -->
                <input
                  class="rename-input"
                  type="text"
                  bind:value={editValue}
                  onkeydown={(e) => { if (e.key === 'Enter') finishRename(rig.id); if (e.key === 'Escape') editingName = null; }}
                  onblur={() => finishRename(rig.id)}
                  onclick={(e) => e.stopPropagation()}
                  autofocus
                />
              {:else}
                <span class="set-name">{rig.name}</span>
                <span class="set-meta">{[rig.rod, rig.reel, rig.blank, rig.line, rig.lure].filter(Boolean).length} items</span>
              {/if}
            </button>
          {/each}
        {/if}
      </div>
    </div>
  </aside>

  <!-- Main content -->
  <div class="fa-main">
    <!-- Rod panel -->
    <section class="fa-section">
      <h3 class="fa-section-title">Fishing Rod</h3>
      <div class="slot-card slot-rod">
        <div class="picker-row">
          <EntityPicker
            entities={rods}
            selected={rodEntity}
            placeholder="Search rods..."
            onselect={(item) => { rod = item?.Name ?? null; }}
            onclear={() => { rod = null; }}
          />
          <button type="button" class="browse-btn" onclick={() => openDialog('rod')} title="Browse all rods">Browse</button>
        </div>
        {#if rodEntity}
          <div class="slot-stats">
            <div class="rod-info">
              {#if rodEntity.Properties.RodType}
                <span class="rod-type-badge">{rodEntity.Properties.RodType}</span>
              {/if}
              {#if rodEntity.Profession?.Name}
                <span class="rod-profession">
                  {rodEntity.Profession.Name}
                  {#if rodEntity.Properties.Skill?.LearningIntervalStart != null || rodEntity.Properties.Skill?.LearningIntervalEnd != null}
                    <span class="rod-levels">
                      ({rodEntity.Properties.Skill.LearningIntervalStart ?? '?'} - {rodEntity.Properties.Skill.LearningIntervalEnd ?? '?'})
                    </span>
                  {/if}
                </span>
              {/if}
              {#if rodEntity.Properties.Skill?.IsSiB}
                <span class="rod-sib">SiB</span>
              {/if}
            </div>
            <div class="stat-rows">
              {#if rodEntity.Properties.Strength != null}
                <div class="stat-row"><span class="stat-label">Strength</span><span class="stat-value">{fmtStat(rodEntity.Properties.Strength)}</span></div>
              {/if}
              {#if rodEntity.Properties.Flexibility != null}
                <div class="stat-row"><span class="stat-label">Flexibility</span><span class="stat-value">{fmtStat(rodEntity.Properties.Flexibility)}</span></div>
              {/if}
              {#if rodEntity.Properties.Economy?.MaxTT != null}
                <div class="stat-row"><span class="stat-label">Max TT</span><span class="stat-value">{fmtStat(rodEntity.Properties.Economy.MaxTT)} PED</span></div>
              {/if}
              {#if rodEntity.Properties.Economy?.Decay != null}
                <div class="stat-row"><span class="stat-label">Decay</span><span class="stat-value">{fmtStat(rodEntity.Properties.Economy.Decay)} PEC</span></div>
              {/if}
              {#if rodEntity.Properties.Economy?.AmmoBurn != null}
                <div class="stat-row"><span class="stat-label">Ammo Burn</span><span class="stat-value">{rodEntity.Properties.Economy.AmmoBurn}</span></div>
              {/if}
              {#if rodEntity.Properties.Weight != null}
                <div class="stat-row"><span class="stat-label">Weight</span><span class="stat-value">{fmtStat(rodEntity.Properties.Weight)} kg</span></div>
              {/if}
            </div>
          </div>
        {/if}
      </div>
    </section>

    <!-- Attachment panels -->
    <section class="fa-section">
      <h3 class="fa-section-title">Attachments</h3>
      <div class="slots-grid">
        {#each SLOTS as slot (slot.key)}
          {@const entity = entityFor(slot.key)}
          <div class="slot-card">
            <div class="slot-label">{slot.label}</div>
            <div class="picker-row">
              <EntityPicker
                entities={entitiesFor(slot.key)}
                selected={entity}
                placeholder="Search {slot.label.toLowerCase()}s..."
                onselect={(item) => handleSelect(slot.key, item)}
                onclear={() => handleClear(slot.key)}
              />
              <button type="button" class="browse-btn" onclick={() => openDialog(slot.key)} title="Browse all {slot.label.toLowerCase()}s">Browse</button>
            </div>
            {#if entity}
              <div class="stat-rows">
                {#each slot.stats as statKey}
                  {#if entity.Properties[statKey] != null}
                    <div class="stat-row">
                      <span class="stat-label">{statKey}</span>
                      <span class="stat-value">{fmtStat(entity.Properties[statKey])}</span>
                    </div>
                  {/if}
                {/each}
                {#if entity.Properties.Economy?.MaxTT != null}
                  <div class="stat-row"><span class="stat-label">Max TT</span><span class="stat-value">{fmtStat(entity.Properties.Economy.MaxTT)} PED</span></div>
                {/if}
                {#if entity.Properties.Economy?.Decay != null}
                  <div class="stat-row"><span class="stat-label">Decay</span><span class="stat-value">{fmtStat(entity.Properties.Economy.Decay)} PEC</span></div>
                {/if}
                {#if entity.Properties.Weight != null}
                  <div class="stat-row"><span class="stat-label">Weight</span><span class="stat-value">{fmtStat(entity.Properties.Weight)} kg</span></div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    </section>
  </div>

  <!-- Right column: Summary info box -->
  <aside class="fa-right">
    <div class="summary-box">
      <h3 class="summary-title">Rig Summary</h3>

      {#if itemCount === 0}
        <div class="summary-empty">Select equipment to see aggregated stats</div>
      {:else}
        <!-- Rod info -->
        {#if rodEntity}
          <div class="summary-section">
            <div class="summary-section-title">Rod Info</div>
            {#if rodEntity.Properties.RodType}
              <div class="stat-row">
                <span class="stat-label">Type</span>
                <span class="stat-value">{rodEntity.Properties.RodType}</span>
              </div>
            {/if}
            {#if rodEntity.Profession?.Name}
              <div class="stat-row">
                <span class="stat-label">Profession</span>
                <span class="stat-value">{rodEntity.Profession.Name}</span>
              </div>
            {/if}
            {#if rodEntity.Properties.Skill?.LearningIntervalStart != null}
              <div class="stat-row">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">{rodEntity.Properties.Skill.LearningIntervalStart} - {rodEntity.Properties.Skill.LearningIntervalEnd ?? '?'}</span>
              </div>
            {/if}
            {#if rodEntity.Properties.Skill?.IsSiB}
              <div class="stat-row">
                <span class="stat-label">SiB</span>
                <span class="stat-value sib-yes">Yes</span>
              </div>
            {/if}
          </div>
        {/if}

        <!-- Aggregated stats -->
        {#if Object.keys(summary).length > 0}
          <div class="summary-section">
            <div class="summary-section-title">Combined Stats</div>
            {#each Object.entries(summary) as [name, value]}
              <div class="stat-row">
                <span class="stat-label">{name}</span>
                <span class="stat-value">{fmtStat(value)}</span>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Economy -->
        {#if economySummary}
          <div class="summary-section">
            <div class="summary-section-title">Economy</div>
            <div class="stat-row">
              <span class="stat-label">Total Weight</span>
              <span class="stat-value">{fmtStat(economySummary.weight)} kg</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Total Max TT</span>
              <span class="stat-value">{fmtStat(economySummary.maxTT)} PED</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Total Decay</span>
              <span class="stat-value">{fmtStat(economySummary.decay)} PEC</span>
            </div>
            {#if economySummary.ammoBurn > 0}
              <div class="stat-row">
                <span class="stat-label">Total Ammo Burn</span>
                <span class="stat-value">{economySummary.ammoBurn}</span>
              </div>
            {/if}
            {#if economySummary.cost != null}
              <div class="stat-row stat-row-highlight">
                <span class="stat-label">Cost</span>
                <span class="stat-value">{fmtStat(economySummary.cost)} PEC</span>
              </div>
            {/if}
          </div>
        {/if}
      {/if}
    </div>
  </aside>
</div>

<FishingPickerDialog
  bind:open={dialogOpen}
  title={dialogTitle}
  entities={dialogEntities}
  columns={dialogColumns}
  selected={dialogSelected}
  onselect={handleDialogSelect}
/>

<style>
  .fishing-advisor {
    display: flex;
    gap: 16px;
  }

  /* ===== Left sidebar ===== */
  .fa-left {
    width: 260px;
    min-width: 260px;
    max-width: 260px;
    position: sticky;
    top: 0;
    align-self: flex-start;
    max-height: calc(100vh - 138px);
    max-height: calc(100dvh - 138px);
  }

  .set-sidebar {
    display: flex;
    flex-direction: column;
    gap: 6px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
    padding: 10px;
    max-height: 100%;
    overflow: hidden;
  }

  .set-toolbar {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
  }

  .toolbar-btn {
    padding: 7px 6px;
    font-size: 13px;
    border: 1px solid var(--border-color);
    border-radius: 5px;
    background-color: var(--bg-color);
    color: var(--text-color);
    cursor: pointer;
    text-align: center;
    transition: all 0.1s ease;
  }

  .toolbar-btn:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .toolbar-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-create {
    border-color: var(--success-color);
    color: var(--success-color);
  }

  .btn-create:hover:not(:disabled) {
    background-color: var(--success-color);
    color: white;
  }

  .btn-delete {
    border-color: var(--color-danger, #ef4444);
    color: var(--color-danger, #ef4444);
  }

  .btn-delete:hover:not(:disabled) {
    background-color: var(--color-danger, #ef4444);
    color: white;
  }

  .set-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .set-empty {
    font-size: 11px;
    color: var(--text-muted);
    text-align: center;
    padding: 8px 0;
  }

  .set-item {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 8px 10px;
    border: 1px solid transparent;
    border-radius: 6px;
    background-color: transparent;
    color: var(--text-color);
    cursor: pointer;
    text-align: left;
    width: 100%;
    transition: all 0.1s ease;
  }

  .set-item:hover {
    background-color: var(--hover-color);
  }

  .set-item.active {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .set-name {
    font-size: 13px;
    font-weight: 500;
    word-break: break-word;
    width: 100%;
  }

  .set-meta {
    font-size: 11px;
    opacity: 0.7;
  }

  .rename-input {
    padding: 2px 4px;
    font-size: 12px;
    background-color: var(--bg-color);
    border: 1px solid var(--accent-color);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
  }

  /* ===== Main content ===== */
  .fa-main {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .fa-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .fa-section-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .slots-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
  }

  .slot-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
  }

  .slot-rod {
    max-width: 400px;
  }

  .slot-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .picker-row {
    display: flex;
    gap: 6px;
    align-items: flex-start;
  }

  .picker-row :global(.entity-picker) {
    flex: 1;
    min-width: 0;
  }

  .browse-btn {
    padding: 8px 10px;
    font-size: 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--bg-color);
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.1s ease;
    flex-shrink: 0;
  }

  .browse-btn:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .slot-stats {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .rod-info {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }

  .rod-type-badge {
    font-size: 12px;
    padding: 2px 8px;
    border-radius: 4px;
    background-color: var(--accent-color);
    color: white;
    font-weight: 500;
  }

  .rod-profession {
    font-size: 12px;
    color: var(--text-muted);
  }

  .rod-levels {
    font-variant-numeric: tabular-nums;
  }

  .rod-sib {
    font-size: 11px;
    padding: 1px 6px;
    border-radius: 3px;
    background-color: var(--success-color);
    color: white;
    font-weight: 500;
  }

  .stat-rows {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 12px;
    padding: 1px 0;
  }

  .stat-label {
    color: var(--text-muted);
  }

  .stat-value {
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    color: var(--text-color);
  }

  .stat-row-highlight {
    border-top: 1px solid var(--border-color);
    margin-top: 2px;
    padding-top: 4px;
    font-weight: 600;
  }

  .stat-row-highlight .stat-label {
    color: var(--text-color);
  }

  /* ===== Right info box ===== */
  .fa-right {
    width: 260px;
    min-width: 260px;
    max-width: 260px;
    position: sticky;
    top: 0;
    align-self: flex-start;
  }

  .summary-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
  }

  .summary-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .summary-empty {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 8px 0;
  }

  .summary-section {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding-top: 6px;
    border-top: 1px solid var(--border-color);
  }

  .summary-section:first-of-type {
    border-top: none;
    padding-top: 0;
  }

  .summary-section-title {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 2px;
  }

  .sib-yes {
    color: var(--success-color);
  }

  /* ===== Responsive ===== */
  @media (max-width: 1200px) {
    .fa-right {
      width: 220px;
      min-width: 220px;
      max-width: 220px;
    }
  }

  @media (max-width: 1000px) {
    .fa-left {
      width: 220px;
      min-width: 220px;
      max-width: 220px;
    }
  }

  @media (max-width: 900px) {
    .fishing-advisor {
      flex-direction: column;
    }

    .fa-left {
      position: static;
      width: 100%;
      min-width: 0;
      max-width: none;
      height: auto;
    }

    .set-sidebar {
      height: auto;
      max-height: 200px;
    }

    .fa-right {
      position: static;
      width: 100%;
      min-width: 0;
      max-width: none;
      order: -1;
    }
  }

  @media (max-width: 600px) {
    .slots-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
