<!--
  @component Attachments Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Handles 7 subtypes: weaponamplifiers, weaponvisionattachments, absorbers,
  finderamplifiers, armorplatings, enhancers, mindforceimplants

  Legacy editConfig preserved in attachments-legacy/+page.svelte
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { clampDecimals, encodeURIComponentSafe, getTypeLink } from '$lib/util';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';

  // Legacy components for data display
  import Acquisition from '$lib/components/Acquisition.svelte';

  export let data;

  $: attachment = data.object;
  $: user = data.session?.user;
  $: additional = data.additional || {};

  // For multi-type pages, data.items is an object keyed by type
  $: allItems = (() => {
    if (!data.items) return [];
    if (additional.type && data.items[additional.type]) {
      return data.items[additional.type];
    }
    // No type selected - combine all items from all types
    const combined = [];
    for (const [type, items] of Object.entries(data.items)) {
      for (const item of items) {
        combined.push({ ...item, _type: type });
      }
    }
    return combined;
  })();

  // Type navigation buttons
  const typeButtons = [
    { label: 'Amplifiers', title: 'Weapon Amplifiers', type: 'weaponamplifiers' },
    { label: 'Scopes', title: 'Sights/Scopes', type: 'weaponvisionattachments' },
    { label: 'Absorbers', title: 'Deterioration Absorbers', type: 'absorbers' },
    { label: 'Finder Amp', title: 'Finder Amplifiers', type: 'finderamplifiers' },
    { label: 'Platings', title: 'Armor Platings', type: 'armorplatings' },
    { label: 'Enhancers', title: 'Enhancers', type: 'enhancers' },
    { label: 'Implants', title: 'Mindforce Implants', type: 'mindforceimplants' }
  ];

  // Type name mapping
  function getTypeName(type) {
    switch (type) {
      case 'weaponamplifiers': return 'Weapon Amplifier';
      case 'weaponvisionattachments': return 'Sight/Scope';
      case 'absorbers': return 'Deterioration Absorber';
      case 'finderamplifiers': return 'Finder Amplifier';
      case 'armorplatings': return 'Armor Plating';
      case 'enhancers': return 'Enhancer';
      case 'mindforceimplants': return 'Mindforce Implant';
      default: return 'Attachment';
    }
  }

  // Entity type for editing
  function getEntityType(type) {
    switch (type) {
      case 'weaponamplifiers': return 'WeaponAmplifier';
      case 'weaponvisionattachments': return 'WeaponVisionAttachment';
      case 'absorbers': return 'Absorber';
      case 'finderamplifiers': return 'FinderAmplifier';
      case 'armorplatings': return 'ArmorPlating';
      case 'enhancers': return 'Enhancer';
      case 'mindforceimplants': return 'MindforceImplant';
      default: return null;
    }
  }

  // Build navigation items
  $: navItems = allItems;

  // Navigation filters - type buttons with deselection support
  $: navFilters = typeButtons.map(btn => ({
    label: btn.label,
    title: btn.title,
    type: btn.type,
    active: additional.type === btn.type,
    href: additional.type === btn.type ? '/items/attachments' : `/items/attachments/${btn.type}`
  }));

  // Type-specific sidebar table columns
  function getNavTableColumns(type) {
    switch (type) {
      case 'weaponamplifiers':
        return [
          { key: 'type', header: 'Type', width: '55px', filterPlaceholder: 'BLP', getValue: (item) => item.Properties?.Type, format: (v) => v || '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'weaponvisionattachments':
        return [
          { key: 'zoom', header: 'Zoom', width: '55px', filterPlaceholder: '>2', getValue: (item) => item.Properties?.Zoom, format: (v) => v != null ? `${v.toFixed(1)}x` : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'absorbers':
        return [
          { key: 'abs', header: 'Abs', width: '55px', filterPlaceholder: '>5', getValue: (item) => item.Properties?.Economy?.Absorption, format: (v) => v != null ? `${(v * 100).toFixed(0)}%` : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'finderamplifiers':
        return [
          { key: 'decay', header: 'Decay', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.Decay, format: (v) => v != null ? v.toFixed(2) : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'armorplatings':
        return [
          { key: 'def', header: 'Def', width: '55px', filterPlaceholder: '>10', getValue: (item) => getTotalDefense(item), format: (v) => v != null ? v.toFixed(1) : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      case 'enhancers':
        return [
          { key: 'tool', header: 'Tool', width: '55px', filterPlaceholder: 'Weapon', getValue: (item) => item.Properties?.Tool, format: (v) => v ? v.slice(0, 6) : '-' },
          { key: 'type', header: 'Type', width: '55px', filterPlaceholder: 'Damage', getValue: (item) => item.Properties?.Type, format: (v) => v ? v.slice(0, 6) : '-' }
        ];
      case 'mindforceimplants':
        return [
          { key: 'abs', header: 'Abs', width: '55px', filterPlaceholder: '>5', getValue: (item) => item.Properties?.Economy?.Absorption, format: (v) => v != null ? `${(v * 100).toFixed(0)}%` : '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
      default:
        return [
          { key: 'cat', header: 'Cat', width: '70px', filterPlaceholder: 'Amp', getValue: (item) => getTypeName(item._type || additional.type).slice(0, 8), format: (v) => v || '-' },
          { key: 'tt', header: 'TT', width: '55px', filterPlaceholder: '>1', getValue: (item) => item.Properties?.Economy?.MaxTT, format: (v) => v != null ? clampDecimals(v, 1, 2) : '-' }
        ];
    }
  }

  $: navTableColumns = getNavTableColumns(additional.type);

  // Custom href generator for items
  function getItemHref(item, basePath) {
    const type = item._type || additional.type;
    if (type) {
      return `/items/attachments/${type}/${encodeURIComponentSafe(item.Name)}`;
    }
    return `${basePath}/${encodeURIComponentSafe(item.Name)}`;
  }

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Attachments', href: '/items/attachments' },
    ...(additional.type ? [{ label: getTypeName(additional.type) + 's', href: `/items/attachments/${additional.type}` }] : []),
    ...(attachment ? [{ label: attachment.Name }] : [])
  ];

  // SEO
  $: seoDescription = attachment?.Properties?.Description ||
    `${attachment?.Name || 'Attachment'} - ${getTypeName(additional.type)} in Entropia Universe.`;

  $: canonicalUrl = attachment
    ? `https://entropianexus.com/items/attachments/${additional.type}/${encodeURIComponentSafe(attachment.Name)}`
    : additional.type
    ? `https://entropianexus.com/items/attachments/${additional.type}`
    : 'https://entropianexus.com/items/attachments';

  // ========== CALCULATION FUNCTIONS ==========
  function getCost(item) {
    if (!item?.Properties?.Economy) return null;
    const decay = item.Properties.Economy.Decay ?? 0;
    const ammoBurn = item.Properties.Economy.AmmoBurn ?? 0;
    if (additional.type === 'weaponamplifiers') {
      return decay != null && ammoBurn != null ? decay + ammoBurn / 100 : null;
    }
    return decay;
  }

  function getTotalUses(item) {
    if (!item?.Properties?.Economy?.MaxTT || !item?.Properties?.Economy?.Decay) return null;
    const maxTT = item.Properties.Economy.MaxTT;
    const minTT = item.Properties.Economy.MinTT ?? 0;
    const decay = item.Properties.Economy.Decay;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  function getTotalDamage(item) {
    if (!item?.Properties?.Damage) return 0;
    const d = item.Properties.Damage;
    return (d.Impact ?? 0) + (d.Cut ?? 0) + (d.Stab ?? 0) + (d.Penetration ?? 0) +
           (d.Shrapnel ?? 0) + (d.Burn ?? 0) + (d.Cold ?? 0) + (d.Acid ?? 0) + (d.Electric ?? 0);
  }

  function getEffectiveDamage(item) {
    const totalDamage = getTotalDamage(item);
    return totalDamage != null ? totalDamage * (0.88 * 0.75 + 0.02 * 1.75) : null;
  }

  function getDPP(item) {
    const cost = getCost(item);
    const effectiveDamage = getEffectiveDamage(item);
    if (cost && effectiveDamage) return effectiveDamage / cost;
    return null;
  }

  function getTotalDefense(item) {
    if (!item?.Properties?.Defense) return 0;
    const d = item.Properties.Defense;
    return (d.Impact ?? 0) + (d.Cut ?? 0) + (d.Stab ?? 0) + (d.Penetration ?? 0) +
           (d.Shrapnel ?? 0) + (d.Burn ?? 0) + (d.Cold ?? 0) + (d.Acid ?? 0) + (d.Electric ?? 0);
  }

  function getMaxArmorDecay(item) {
    if (!item?.Properties?.Economy?.Durability || !getTotalDefense(item)) return null;
    return getTotalDefense(item) * ((100000 - item.Properties.Economy.Durability) / 100000) * 0.05;
  }

  function getTotalAbsorption(item) {
    if (!item?.Properties?.Economy?.MaxTT) return null;
    const maxArmorDecay = getMaxArmorDecay(item);
    if (!maxArmorDecay) return null;
    const minTT = item.Properties.Economy.MinTT ?? 0;
    return getTotalDefense(item) * ((item.Properties.Economy.MaxTT - minTT) / (maxArmorDecay / 100));
  }

  function getEnhancerEffect(item) {
    const key = `${item?.Properties?.Tool} ${item?.Properties?.Type}`;
    const effects = {
      'Weapon Damage': 'Increases damage, decay and ammo burn by 10%',
      'Weapon Range': 'Increases range by 5%',
      'Weapon Skill Modification': 'Increases your profession levels for the weapon by 0.5',
      'Weapon Economy': 'Reduces the decay and ammo burn by approximately 1-1.1%',
      'Weapon Accuracy': 'Increases the chance for a critical hit by 0.2% (at max skill)',
      'Armor Defense': 'Increases all protection by 5%',
      'Armor Durability': 'Increases durability by 10%',
      'Medical Tool Economy': 'Reduces the decay by 10%',
      'Medical Tool Heal': 'Increases the decay and the amount healed by 5%',
      'Medical Tool Skill Modification': 'Increases your profession levels for the tool by 0.5',
      'Mining Excavator Speed': 'Increases the efficiency by 10%',
      'Mining Finder Depth': 'Increases the average depth by approximately 7.5%',
      'Mining Finder Range': 'Increases the range by 1%',
      'Mining Finder Skill Modification': 'Increases your profession levels for the finder by 0.5'
    };
    return effects[key] || null;
  }

  // ========== COMPUTED VALUES ==========
  $: cost = getCost(attachment);
  $: totalUses = getTotalUses(attachment);
  $: totalDamage = getTotalDamage(attachment);
  $: dpp = getDPP(attachment);
  $: totalDefense = getTotalDefense(attachment);
  $: maxArmorDecay = getMaxArmorDecay(attachment);
  $: totalAbsorptionVal = getTotalAbsorption(attachment);
  $: enhancerEffect = getEnhancerEffect(attachment);

  // Check for effects
  $: hasEquipEffects = attachment?.EffectsOnEquip?.length > 0;

  // Damage types with values for display
  const damageTypes = ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];
  const defenseTypes = ['Block', 'Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'];

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    damage: true,
    defense: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-attachment-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {}
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-attachment-panels', JSON.stringify(panelStates));
    } catch (e) {}
  }
</script>

<WikiSEO
  title={attachment?.Name || `${getTypeName(additional.type)}s`}
  description={seoDescription}
  entityType={getEntityType(additional.type)}
  entity={attachment}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Attachments"
  {breadcrumbs}
  entity={attachment}
  entityType={getEntityType(additional.type)}
  basePath="/items/attachments/{additional.type || ''}"
  {navItems}
  {navFilters}
  {navTableColumns}
  navGetItemHref={getItemHref}
  {user}
  editable={true}
>
  {#if attachment}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <div class="icon-placeholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
              <rect x="3" y="3" width="18" height="18" rx="2" />
            </svg>
          </div>
          <div class="infobox-title">{attachment.Name}</div>
          <div class="infobox-subtitle">
            <span class="type-badge">{getTypeName(additional.type)}</span>
          </div>
        </div>

        <!-- Tier-1 Stats (type-specific primary stats) -->
        <div class="stats-section tier-1">
          <!-- Amplifiers: Efficiency, Total Damage, DPP -->
          {#if additional.type === 'weaponamplifiers'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{attachment.Properties?.Economy?.Efficiency != null ? `${attachment.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Total Damage</span>
              <span class="stat-value">{totalDamage?.toFixed(1) || 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">DPP</span>
              <span class="stat-value">{dpp != null ? dpp.toFixed(4) : 'N/A'}</span>
            </div>

          <!-- Scopes/Sights: Efficiency, Zoom -->
          {:else if additional.type === 'weaponvisionattachments'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{attachment.Properties?.Economy?.Efficiency != null ? `${attachment.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Zoom</span>
              <span class="stat-value">{attachment.Properties?.Zoom != null ? `${attachment.Properties.Zoom.toFixed(1)}x` : 'N/A'}</span>
            </div>

          <!-- Absorbers: Efficiency, Absorption -->
          {:else if additional.type === 'absorbers'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{attachment.Properties?.Economy?.Efficiency != null ? `${attachment.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Absorption</span>
              <span class="stat-value">{attachment.Properties?.Economy?.Absorption != null ? `${clampDecimals(attachment.Properties.Economy.Absorption * 100, 0, 2)}%` : 'N/A'}</span>
            </div>

          <!-- Mindforce implants: TT, Absorption -->
          {:else if additional.type === 'mindforceimplants'}
            <div class="stat-row primary">
              <span class="stat-label">TT Value</span>
              <span class="stat-value">{attachment.Properties?.Economy?.MaxTT != null ? `${clampDecimals(attachment.Properties.Economy.MaxTT, 2, 4)} PED` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Absorption</span>
              <span class="stat-value">{attachment.Properties?.Economy?.Absorption != null ? `${clampDecimals(attachment.Properties.Economy.Absorption * 100, 0, 2)}%` : 'N/A'}</span>
            </div>

          <!-- Finder amplifiers: Efficiency, Decay -->
          {:else if additional.type === 'finderamplifiers'}
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{attachment.Properties?.Efficiency != null ? attachment.Properties.Efficiency.toFixed(1) : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Decay</span>
              <span class="stat-value">{attachment.Properties?.Economy?.Decay != null ? `${attachment.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
            </div>

          <!-- Armor platings: Total Defense, Durability -->
          {:else if additional.type === 'armorplatings'}
            <div class="stat-row primary">
              <span class="stat-label">Total Defense</span>
              <span class="stat-value">{totalDefense?.toFixed(1) || 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Durability</span>
              <span class="stat-value">{attachment.Properties?.Economy?.Durability ?? 'N/A'}</span>
            </div>

          <!-- Enhancers: Tool, Type -->
          {:else if additional.type === 'enhancers'}
            <div class="stat-row primary">
              <span class="stat-label">Tool</span>
              <span class="stat-value">{attachment.Properties?.Tool || 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Type</span>
              <span class="stat-value">{attachment.Properties?.Type || 'N/A'}</span>
            </div>
          {/if}
        </div>

        <!-- Damage Grid in Infobox (weapon amplifiers only) -->
        {#if additional.type === 'weaponamplifiers' && totalDamage > 0}
          <div class="stats-section">
            <h4 class="section-title">Damage</h4>
            <div class="infobox-damage-grid">
              {#each damageTypes as dtype}
                {#if attachment.Properties?.Damage?.[dtype] > 0}
                  <div class="mini-damage-item">
                    <span class="mini-damage-label">{dtype}</span>
                    <span class="mini-damage-value">{attachment.Properties.Damage[dtype].toFixed(1)}</span>
                  </div>
                {/if}
              {/each}
            </div>
          </div>
        {/if}

        <!-- Defense Grid in Infobox (armor platings only) -->
        {#if additional.type === 'armorplatings' && totalDefense > 0}
          <div class="stats-section">
            <h4 class="section-title">Defense</h4>
            <div class="infobox-defense-grid">
              {#if attachment.Properties?.Defense?.Block > 0}
                <div class="mini-defense-item block">
                  <span class="mini-defense-label">Block</span>
                  <span class="mini-defense-value">{attachment.Properties.Defense.Block.toFixed(1)}%</span>
                </div>
              {/if}
              {#each defenseTypes.slice(1) as dtype}
                {#if attachment.Properties?.Defense?.[dtype] > 0}
                  <div class="mini-defense-item">
                    <span class="mini-defense-label">{dtype}</span>
                    <span class="mini-defense-value">{attachment.Properties.Defense[dtype].toFixed(1)}</span>
                  </div>
                {/if}
              {/each}
            </div>
            <!-- Total Defense Full-Width Box -->
            <div class="defense-total-box">
              <span class="defense-total-label">Total Defense</span>
              <span class="defense-total-value">{totalDefense.toFixed(1)}</span>
            </div>
          </div>
        {/if}

        <!-- General Stats -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">{attachment.Properties?.Weight != null ? `${clampDecimals(attachment.Properties.Weight, 1, 6)}kg` : 'N/A'}</span>
          </div>

          {#if additional.type === 'weaponamplifiers'}
            <div class="stat-row">
              <span class="stat-label">Amplifier Type</span>
              <span class="stat-value">{attachment.Properties?.Type || 'N/A'}</span>
            </div>
          {:else if additional.type === 'finderamplifiers'}
            <div class="stat-row">
              <span class="stat-label">Min. Profession Level</span>
              <span class="stat-value">{attachment.Properties?.MinProfessionLevel ?? 'N/A'}</span>
            </div>
          {:else if additional.type === 'enhancers'}
            <div class="stat-row">
              <span class="stat-label">Socket</span>
              <span class="stat-value">{attachment.Properties?.Socket ?? 'N/A'}</span>
            </div>
          {:else if additional.type === 'mindforceimplants'}
            <div class="stat-row">
              <span class="stat-label">Max. Profession Level</span>
              <span class="stat-value">{attachment.Properties?.MaxProfessionLevel ?? 'N/A'}</span>
            </div>
          {/if}
        </div>

        <!-- Economy Stats -->
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>

          <div class="stat-row">
            <span class="stat-label">Max. TT</span>
            <span class="stat-value">{attachment.Properties?.Economy?.MaxTT != null ? `${clampDecimals(attachment.Properties.Economy.MaxTT, 2, 8)} PED` : 'N/A'}</span>
          </div>

          {#if additional.type !== 'enhancers'}
            <div class="stat-row">
              <span class="stat-label">Min. TT</span>
              <span class="stat-value">{attachment.Properties?.Economy?.MinTT != null ? `${clampDecimals(attachment.Properties.Economy.MinTT, 2, 8)} PED` : 'N/A'}</span>
            </div>
          {/if}

          {#if additional.type === 'weaponamplifiers' || additional.type === 'weaponvisionattachments'}
            <div class="stat-row">
              <span class="stat-label">Decay</span>
              <span class="stat-value">{attachment.Properties?.Economy?.Decay != null ? `${attachment.Properties.Economy.Decay.toFixed(4)} PEC` : 'N/A'}</span>
            </div>
          {/if}

          {#if additional.type === 'weaponamplifiers'}
            <div class="stat-row">
              <span class="stat-label">Ammo Burn</span>
              <span class="stat-value">{attachment.Properties?.Economy?.AmmoBurn ?? 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cost</span>
              <span class="stat-value">{cost != null ? `${cost.toFixed(4)} PEC` : 'N/A'}</span>
            </div>
          {/if}

          {#if additional.type === 'armorplatings'}
            <div class="stat-row">
              <span class="stat-label">Max. Decay</span>
              <span class="stat-value">{maxArmorDecay != null ? `${maxArmorDecay.toFixed(4)} PEC` : 'N/A'}</span>
            </div>
          {/if}

          {#if (additional.type === 'weaponamplifiers' || additional.type === 'weaponvisionattachments' || additional.type === 'finderamplifiers') && totalUses}
            <div class="stat-row">
              <span class="stat-label">Total Uses</span>
              <span class="stat-value">{totalUses}</span>
            </div>
          {/if}

          {#if additional.type === 'armorplatings' && totalAbsorptionVal}
            <div class="stat-row">
              <span class="stat-label">Total Absorption</span>
              <span class="stat-value">{totalAbsorptionVal.toFixed(1)} HP</span>
            </div>
          {/if}
        </div>

        <!-- Skill Stats (for scopes and finder amps) -->
        {#if additional.type === 'weaponvisionattachments'}
          <div class="stats-section">
            <h4 class="section-title">Skill</h4>
            <div class="stat-row">
              <span class="stat-label">Skill Modification</span>
              <span class="stat-value">{attachment.Properties?.SkillModification != null ? `${attachment.Properties.SkillModification}%` : 'N/A'}</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Skill Bonus</span>
              <span class="stat-value">{attachment.Properties?.SkillBonus != null ? `${attachment.Properties.SkillBonus.toFixed(1)}%` : 'N/A'}</span>
            </div>
          </div>
        {:else if additional.type === 'finderamplifiers'}
          <div class="stats-section">
            <h4 class="section-title">Skill</h4>
            <div class="stat-row">
              <span class="stat-label">Professions</span>
              <span class="stat-value links">
                <a href={getTypeLink('Prospector', 'Profession')} class="entity-link">Prospector</a>,
                <a href={getTypeLink('Surveyor', 'Profession')} class="entity-link">Surveyor</a>,
                <a href={getTypeLink('Treasure Hunter', 'Profession')} class="entity-link">Treasure Hunter</a>
              </span>
            </div>
          </div>
        {/if}

        <!-- Enhancer Effect -->
        {#if additional.type === 'enhancers' && enhancerEffect}
          <div class="stats-section effect-description">
            <h4 class="section-title">Effect</h4>
            <div class="effect-text">{enhancerEffect}</div>
          </div>
        {/if}

        <!-- Effects on Equip -->
        {#if hasEquipEffects}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects on Equip</h4>
            {#each attachment.EffectsOnEquip.sort((a,b) => a.Name.localeCompare(b.Name)) as effect}
              <div class="stat-row">
                <span class="stat-label">{effect.Name}</span>
                <span class="stat-value effect-value">{effect.Values.Strength}{effect.Values.Unit}</span>
              </div>
            {/each}
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">{attachment.Name}</h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if attachment.Properties?.Description}
            <div class="description-content">{attachment.Properties.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {attachment.Name} is a {getTypeName(additional.type).toLowerCase()} used in Entropia Universe.
            </div>
          {/if}
        </div>

        <!-- Damage Section (weapon amplifiers only) -->
        {#if additional.type === 'weaponamplifiers' && totalDamage > 0}
          <DataSection
            title="Damage"
            icon=""
            bind:expanded={panelStates.damage}
            on:toggle={savePanelStates}
          >
            <div class="damage-grid">
              {#each damageTypes as dtype}
                {#if attachment.Properties?.Damage?.[dtype] > 0}
                  <div class="damage-item">
                    <span class="damage-label">{dtype}</span>
                    <span class="damage-value">{attachment.Properties.Damage[dtype].toFixed(1)}</span>
                  </div>
                {/if}
              {/each}
              <div class="damage-item total">
                <span class="damage-label">Total</span>
                <span class="damage-value">{totalDamage.toFixed(1)}</span>
              </div>
            </div>
          </DataSection>
        {/if}

        <!-- Acquisition Section -->
        {#if additional.acquisition}
          <DataSection
            title="Acquisition"
            icon=""
            bind:expanded={panelStates.acquisition}
            on:toggle={savePanelStates}
          >
            <Acquisition acquisition={additional.acquisition} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>{additional.type ? getTypeName(additional.type) + 's' : 'Attachments'}</h2>
      <p>Select an {additional.type ? getTypeName(additional.type).toLowerCase() : 'attachment'} from the list to view details.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .layout-a {
    position: relative;
    width: 100%;
  }

  .layout-a::after {
    content: '';
    display: block;
    clear: both;
  }

  /* Floating infobox - Wikipedia style */
  .wiki-infobox-float {
    float: right;
    width: 300px;
    margin: 0 0 0 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
  }

  .infobox-header {
    text-align: center;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .icon-placeholder {
    width: 80px;
    height: 80px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--bg-color, var(--primary-color));
    border: 2px dashed var(--border-color, #555);
    border-radius: 8px;
    color: var(--text-muted, #999);
    margin: 0 auto 12px;
  }

  .infobox-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .infobox-subtitle {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .type-badge {
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 600;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

  /* Stats sections */
  .stats-section {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .stats-section.tier-1 {
    background: linear-gradient(135deg, #4a7c59 0%, #3a6349 100%);
    padding: 14px;
  }

  .stats-section.tier-1 .stat-row.primary {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 8px 12px;
    margin-bottom: 6px;
  }

  .stats-section.tier-1 .stat-row.primary:last-child {
    margin-bottom: 0;
  }

  .stats-section.tier-1 .stat-label {
    color: rgba(255, 255, 255, 0.9);
    font-size: 13px;
    text-transform: uppercase;
    font-weight: 500;
  }

  .stats-section.tier-1 .stat-value {
    color: #e8f4e8;
    font-size: 18px;
    font-weight: 700;
  }

  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 4px 0;
    font-size: 13px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
  }

  .stat-value.highlight {
    color: #4ade80;
    font-weight: 600;
  }

  .stat-value.effect-value {
    color: var(--accent-color, #4a9eff);
  }

  .stat-value.links {
    text-align: right;
    font-size: 12px;
  }

  .entity-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .entity-link:hover {
    text-decoration: underline;
  }

  /* Effect description for enhancers */
  .effect-description .effect-text {
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-color);
  }

  /* Effects styling */
  .effects-section .stat-row {
    padding: 3px 0;
  }

  .wiki-article {
    overflow: hidden;
  }

  .article-title {
    font-size: 32px;
    font-weight: 600;
    margin: 0 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--accent-color, #4a9eff);
  }

  .description-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .description-content {
    font-size: 15px;
    line-height: 1.6;
    color: var(--text-color);
  }

  .description-content.placeholder {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  /* Mini damage/defense grids for infobox */
  .infobox-damage-grid, .infobox-defense-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
  }

  .mini-damage-item, .mini-defense-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 6px 4px;
    background-color: var(--secondary-color);
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
  }

  .mini-defense-item.block {
    background-color: #6366f1;
    border-color: #6366f1;
  }

  .mini-defense-item.block .mini-defense-label,
  .mini-defense-item.block .mini-defense-value {
    color: white;
  }

  /* Total defense full-width box */
  .defense-total-box {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    padding: 10px 12px;
    background-color: var(--accent-color, #4a9eff);
    border-radius: 6px;
  }

  .defense-total-label {
    font-size: 12px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.9);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .defense-total-value {
    font-size: 18px;
    font-weight: 700;
    color: white;
  }

  .mini-damage-label, .mini-defense-label {
    font-size: 9px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .mini-damage-value, .mini-defense-value {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  /* Damage/Defense grids (main article) */
  .damage-grid, .defense-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: 8px;
  }

  .damage-item, .defense-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 8px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
  }

  .damage-item.total, .defense-item.total {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  .damage-item.total .damage-label,
  .damage-item.total .damage-value,
  .defense-item.total .defense-label,
  .defense-item.total .defense-value {
    color: white;
  }

  .defense-item.block {
    background-color: #6366f1;
    border-color: #6366f1;
  }

  .defense-item.block .defense-label,
  .defense-item.block .defense-value {
    color: white;
  }

  .damage-label, .defense-label {
    font-size: 11px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
  }

  .damage-value, .defense-value {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
  }

  .no-selection {
    text-align: center;
    padding: 60px 20px;
  }

  .no-selection h2 {
    font-size: 28px;
    margin-bottom: 12px;
  }

  .no-selection p {
    color: var(--text-muted, #999);
    margin: 8px 0;
  }

  /* Tablet adjustments */
  @media (max-width: 1023px) {
    .wiki-infobox-float {
      width: 280px;
      margin-left: 16px;
      padding: 14px;
    }
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .layout-a {
      max-width: 100%;
    }

    .wiki-infobox-float {
      float: none;
      width: auto;
      margin: 0 0 16px 0;
    }

    .article-title {
      display: none;
    }

    .infobox-title {
      font-size: 16px;
    }

    .icon-placeholder {
      width: 60px;
      height: 60px;
    }

    .icon-placeholder svg {
      width: 36px;
      height: 36px;
    }

    .damage-grid, .defense-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }
</style>
