<!--
  @component WeaponConfigPanel
  Compact weapon configuration card for the (L) Weapon Profitability tool.
  Supports weapon selection, all attachment slots, enhancers, and markup source toggles.
-->
<script>
  // @ts-nocheck
  import { hasItemTag } from '$lib/util.js';
  import EntityPicker from './EntityPicker.svelte';
  import { computeWeaponStats, formatNumber, getCompatibleAmplifiers, weaponUsesExplosiveAmmo } from './weaponProfitability.js';

  let {
    config = $bindable({}),
    entities = {},
    markupData = {},
    limitedOnly = false,
    removable = false,
    compact = false,
    dropUp = false,
    onremove = () => {},
    label = ''
  } = $props();

  const isLimited = (name) => !!name && hasItemTag(name, 'L');
  const clampEnh = (v) => Math.max(0, Math.min(10, Math.round(Number(v) || 0)));

  // Resolve selected entities
  let weapon = $derived(config.weaponName ? entities.weapons?.find(w => w.Name === config.weaponName) : null);
  let weaponClass = $derived(weapon?.Properties?.Class || null);
  let isMining = $derived(weapon?.Properties?.Type?.startsWith('Mining Laser') ?? false);
  let isRanged = $derived(weaponClass === 'Ranged');
  let isMelee = $derived(weaponClass === 'Melee');
  let isMindforce = $derived(weaponClass === 'Mindforce');
  let isExplosive = $derived(weaponUsesExplosiveAmmo(weapon));

  // Filter weapon list
  let weaponList = $derived.by(() => {
    let list = entities.weapons || [];
    if (limitedOnly) list = list.filter(w => isLimited(w.Name));
    return list;
  });

  // Compatible amplifiers for this weapon
  let compatibleAmplifiers = $derived(weapon ? getCompatibleAmplifiers(weapon, entities.amplifiers || []) : []);
  // Compatible matrices (Melee only, already filtered in entities.matrices)
  let compatibleMatrices = $derived(isMelee ? (entities.matrices || []) : []);

  let showAttachments = $state(false);

  // Auto-expand attachments if any are set
  $effect(() => {
    if (config.amplifierName || config.absorberName || config.scopeName ||
        config.sightName || config.matrixName || config.implantName) {
      showAttachments = true;
    }
  });

  // Computed stats
  let stats = $derived.by(() => {
    if (!config.weaponName) return null;
    return computeWeaponStats(config, entities);
  });

  function resolveMarkup(itemName, source, customValue) {
    if (source === 'custom' || !itemName) return customValue ?? 100;
    if (source === 'inventory' && markupData.inventoryMap) {
      const id = markupData.nameToId?.get(itemName);
      if (id != null && markupData.inventoryMap.has(id)) return markupData.inventoryMap.get(id);
    }
    if (source === 'ingame' && markupData.ingameMap?.has(itemName)) return markupData.ingameMap.get(itemName);
    if (source === 'exchange' && markupData.wapByName?.has(itemName)) return markupData.wapByName.get(itemName);
    return customValue ?? 100;
  }

  $effect(() => {
    const src = config.markupSource;
    if (src !== 'custom' && config.weaponName) {
      const resolved = resolveMarkup(config.weaponName, src, config.markupPercent);
      if (resolved !== config.markupPercent) config.markupPercent = resolved;
    }
  });

  function handleWeaponSelect(item) {
    config.weaponName = item?.Name ?? null;
    if (!isLimited(item?.Name)) config.markupPercent = 100;
    const cls = item?.Properties?.Class;
    if (cls !== 'Ranged') { config.scopeName = null; config.scopeSightName = null; config.sightName = null; }
    if (cls !== 'Melee') config.matrixName = null;
    if (cls !== 'Mindforce') config.implantName = null;
    if (item?.Properties?.Type?.startsWith('Mining Laser')) config.absorberName = null;
    // Clear incompatible amplifier
    if (item && config.amplifierName) {
      const compat = getCompatibleAmplifiers(item, entities.amplifiers || []);
      if (!compat.some(a => a.Name === config.amplifierName)) config.amplifierName = null;
    }
  }

  function handleWeaponClear() {
    config.weaponName = null;
    config.markupPercent = 100;
    config.amplifierName = null;
    config.absorberName = null;
    config.scopeName = null;
    config.scopeSightName = null;
    config.sightName = null;
    config.matrixName = null;
    config.implantName = null;
  }
</script>

<div class="wcp" class:compact>
  {#if label}
    <span class="wcp-label">{label}</span>
  {/if}

  <!-- Row 1: remove btn + weapon picker -->
  <div class="wcp-picker-row">
    {#if removable}
      <button type="button" class="wcp-remove" onclick={onremove} title="Remove">×</button>
    {/if}
    <div class="wcp-picker">
      <EntityPicker
        entities={weaponList}
        selected={weapon}
        placeholder={limitedOnly ? 'Select (L) weapon...' : 'Select weapon...'}
        {dropUp}
        onselect={handleWeaponSelect}
        onclear={handleWeaponClear}
      />
    </div>
  </div>

  {#if weapon}
    <!-- Row 2: enhancers + markup -->
    <div class="wcp-controls-row">
      <label class="wcp-field" title="Damage enhancers">
        <span>Dmg</span>
        <input type="number" min="0" max="10" class="wcp-num sm"
          value={config.damageEnhancers}
          oninput={(e) => { config.damageEnhancers = clampEnh(e.target.value); }} />
      </label>
      <label class="wcp-field" title="Economy enhancers">
        <span>Eco</span>
        <input type="number" min="0" max="10" class="wcp-num sm"
          value={config.economyEnhancers}
          oninput={(e) => { config.economyEnhancers = clampEnh(e.target.value); }} />
      </label>
      {#if isLimited(config.weaponName)}
        <label class="wcp-field" title="Weapon markup">
          <span>MU%</span>
          <input type="number" min="0" step="0.01" class="wcp-num"
            bind:value={config.markupPercent} />
        </label>
        <div class="wcp-src-btns">
          {#each ['custom', 'inventory', 'ingame', 'exchange'] as src}
            <button type="button" class="src-btn" class:active={config.markupSource === src}
              onclick={() => { config.markupSource = src; }}>
              {src === 'custom' ? 'Cust' : src === 'inventory' ? 'Inv' : src === 'ingame' ? 'IG' : 'Exch'}
            </button>
          {/each}
        </div>
      {:else}
        <span class="wcp-ul-badge">UL</span>
      {/if}
    </div>

    <!-- Attachments -->
    <button type="button" class="wcp-att-toggle"
      onclick={() => { showAttachments = !showAttachments; }}>
      {showAttachments ? '▾' : '▸'} Attachments
      {#if config.amplifierName || config.absorberName || config.scopeName || config.sightName || config.matrixName || config.implantName}
        <span class="wcp-att-count">({[config.amplifierName, config.absorberName, config.scopeName, config.sightName, config.matrixName, config.implantName].filter(Boolean).length})</span>
      {/if}
    </button>

    {#if showAttachments}
      <div class="wcp-att-section">
        <!-- Amplifier (filtered by weapon type) -->
        <div class="wcp-att">
          <span class="wcp-att-label">Amplifier</span>
          <div class="wcp-att-row">
            <EntityPicker
              entities={compatibleAmplifiers}
              selected={config.amplifierName ? compatibleAmplifiers.find(a => a.Name === config.amplifierName) : null}
              placeholder="Select amplifier..." {dropUp}
              onselect={(item) => { config.amplifierName = item?.Name ?? null; if (!isLimited(item?.Name)) config.amplifierMarkup = 100; }}
              onclear={() => { config.amplifierName = null; config.amplifierMarkup = 100; }}
            />
            {#if isLimited(config.amplifierName)}
              <input type="number" min="0" step="0.01" class="wcp-num sm" title="Amp MU%"
                bind:value={config.amplifierMarkup} />
            {/if}
          </div>
        </div>

        <!-- Absorber (not for mining) -->
        {#if !isMining}
          <div class="wcp-att">
            <span class="wcp-att-label">Absorber</span>
            <div class="wcp-att-row">
              <EntityPicker
                entities={entities.absorbers || []}
                selected={config.absorberName ? entities.absorbers?.find(a => a.Name === config.absorberName) : null}
                placeholder="Select absorber..." {dropUp}
                onselect={(item) => { config.absorberName = item?.Name ?? null; if (!isLimited(item?.Name)) config.absorberMarkup = 100; }}
                onclear={() => { config.absorberName = null; config.absorberMarkup = 100; }}
              />
              {#if isLimited(config.absorberName)}
                <input type="number" min="0" step="0.01" class="wcp-num sm" title="Absorber MU%"
                  bind:value={config.absorberMarkup} />
              {/if}
            </div>
          </div>
        {/if}

        <!-- Scope + Scope Sight + Sight (Ranged only) -->
        {#if isRanged}
          <div class="wcp-att">
            <span class="wcp-att-label">Scope</span>
            <div class="wcp-att-row">
              <EntityPicker
                entities={entities.scopes || []}
                selected={config.scopeName ? entities.scopes?.find(s => s.Name === config.scopeName) : null}
                placeholder="Select scope..." {dropUp}
                onselect={(item) => { config.scopeName = item?.Name ?? null; if (!isLimited(item?.Name)) config.scopeMarkup = 100; if (!item) config.scopeSightName = null; }}
                onclear={() => { config.scopeName = null; config.scopeMarkup = 100; config.scopeSightName = null; }}
              />
              {#if isLimited(config.scopeName)}
                <input type="number" min="0" step="0.01" class="wcp-num sm" title="Scope MU%"
                  bind:value={config.scopeMarkup} />
              {/if}
            </div>
          </div>
          {#if config.scopeName}
            <div class="wcp-att nested">
              <span class="wcp-att-label">Scope Sight</span>
              <EntityPicker
                entities={entities.sights || []}
                selected={config.scopeSightName ? entities.sights?.find(s => s.Name === config.scopeSightName) : null}
                placeholder="Select scope sight..." {dropUp}
                onselect={(item) => { config.scopeSightName = item?.Name ?? null; }}
                onclear={() => { config.scopeSightName = null; }}
              />
            </div>
          {/if}
          <div class="wcp-att">
            <span class="wcp-att-label">Sight</span>
            <EntityPicker
              entities={entities.sights || []}
              selected={config.sightName ? entities.sights?.find(s => s.Name === config.sightName) : null}
              placeholder="Select sight..." {dropUp}
              onselect={(item) => { config.sightName = item?.Name ?? null; }}
              onclear={() => { config.sightName = null; }}
            />
          </div>
        {/if}

        <!-- Matrix (Melee only) -->
        {#if isMelee}
          <div class="wcp-att">
            <span class="wcp-att-label">Matrix</span>
            <EntityPicker
              entities={compatibleMatrices}
              selected={config.matrixName ? compatibleMatrices.find(m => m.Name === config.matrixName) : null}
              placeholder="Select matrix..." {dropUp}
              onselect={(item) => { config.matrixName = item?.Name ?? null; if (!isLimited(item?.Name)) config.matrixMarkup = 100; }}
              onclear={() => { config.matrixName = null; config.matrixMarkup = 100; }}
            />
          </div>
        {/if}

        <!-- Implant (Mindforce only) -->
        {#if isMindforce}
          <div class="wcp-att">
            <span class="wcp-att-label">Implant</span>
            <EntityPicker
              entities={entities.implants || []}
              selected={config.implantName ? entities.implants?.find(i => i.Name === config.implantName) : null}
              placeholder="Select implant..." {dropUp}
              onselect={(item) => { config.implantName = item?.Name ?? null; if (!isLimited(item?.Name)) config.implantMarkup = 100; }}
              onclear={() => { config.implantName = null; config.implantMarkup = 100; }}
            />
          </div>
        {/if}
      </div>
    {/if}

    <!-- Stats -->
    {#if stats}
      <div class="wcp-stats">
        <span class="wcp-stat" title="Efficiency">Eff: {stats.efficiency != null ? stats.efficiency.toFixed(1) + '%' : 'N/A'}</span>
        <span class="wcp-stat" title="Damage per PED">DPP: {stats.dpp != null ? stats.dpp.toFixed(2) : 'N/A'}</span>
        <span class="wcp-stat" title="Damage per second">DPS: {stats.dps != null ? stats.dps.toFixed(1) : 'N/A'}</span>
        <span class="wcp-stat" title="TT cost per use (PEC)">TT: {stats.ttCostPerUse != null ? stats.ttCostPerUse.toFixed(2) : 'N/A'}</span>
        <span class="wcp-stat" title="Total uses">Uses: {formatNumber(stats.totalUses)}</span>
        {#if stats.totalCyclePED != null}
          <span class="wcp-stat" title="Total cycle (PED)">Cycle: {stats.totalCyclePED.toFixed(2)}</span>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .wcp {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .wcp.compact { padding: 8px 10px; gap: 4px; }

  .wcp-label { font-weight: 600; font-size: 13px; color: var(--text-color); }

  .wcp-remove {
    background: transparent; border: none; color: var(--text-muted);
    font-size: 16px; cursor: pointer; padding: 2px 4px; line-height: 1; border-radius: 4px;
    flex-shrink: 0; align-self: center;
  }
  .wcp-remove:hover { color: var(--danger-color, #e74c3c); background: var(--hover-color); }

  /* Row 1: remove + picker */
  .wcp-picker-row {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .wcp-picker { flex: 1; min-width: 0; }

  /* Row 2: enhancers + markup */
  .wcp-controls-row {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }

  .wcp-field {
    display: flex;
    align-items: center;
    gap: 3px;
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .wcp-num {
    width: 64px;
    padding: 4px 5px;
    font-size: 12px;
    background: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    text-align: right;
  }
  .wcp-num.sm { width: 44px; text-align: center; }
  .wcp-num:focus { border-color: var(--accent-color); outline: none; }

  .wcp-src-btns { display: flex; gap: 1px; }

  .src-btn {
    padding: 3px 5px; font-size: 10px;
    border: 1px solid var(--border-color); background: var(--bg-color);
    color: var(--text-muted); cursor: pointer; border-radius: 3px;
  }
  .src-btn.active { background: var(--accent-color); border-color: var(--accent-color); color: white; }
  .src-btn:hover:not(.active) { background: var(--hover-color); }

  .wcp-ul-badge {
    font-size: 10px; color: var(--text-muted);
    padding: 3px 6px; background: var(--bg-color);
    border-radius: 3px; border: 1px solid var(--border-color);
  }

  /* Attachments */
  .wcp-att-toggle {
    background: transparent; border: none; color: var(--text-muted);
    font-size: 13px; cursor: pointer; padding: 2px 0; text-align: left;
    display: flex; align-items: center; gap: 4px;
  }
  .wcp-att-toggle:hover { color: var(--text-color); }
  .wcp-att-count { color: var(--accent-color); }

  .wcp-att-section {
    display: flex; flex-direction: column; gap: 6px;
    padding-left: 8px; border-left: 2px solid var(--border-color);
  }

  .wcp-att { display: flex; flex-direction: column; gap: 3px; }
  .wcp-att.nested { padding-left: 12px; }
  .wcp-att-label { font-size: 10px; color: var(--text-muted); font-weight: 500; }

  .wcp-att-row {
    display: flex; gap: 4px; align-items: center;
  }
  .wcp-att-row :global(.entity-picker) { flex: 1; }

  /* Stats */
  .wcp-stats {
    display: flex; gap: 10px; flex-wrap: wrap;
    padding-top: 4px; border-top: 1px solid var(--border-color);
  }

  .wcp-stat {
    font-size: 11px; color: var(--text-muted);
    white-space: nowrap; font-variant-numeric: tabular-nums;
  }

  @media (max-width: 600px) {
    .wcp-controls-row { width: 100%; }
  }
</style>
