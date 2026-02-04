<!--
  @component Weapon Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: All numeric stats + damage breakdown
  Article: Description → Tiers → Acquisition
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe, hasItemTag, clampDecimals, getTypeLink } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  // Edit state management
  import {
    editMode,
    isCreateMode,
    initEditState,
    resetEditState,
    currentEntity,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField,
    changeMetadata
  } from '$lib/stores/wikiEditState.js';

  // Weapon-specific components
  import DamageBreakdownGrid from '$lib/components/wiki/DamageBreakdownGrid.svelte';

  // Generic wiki components
  import TieringEditor from '$lib/components/wiki/TieringEditor.svelte';
  import EffectsEditor from '$lib/components/wiki/EffectsEditor.svelte';

  // Legacy components for comparison
  import Acquisition from '$lib/components/Acquisition.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  export let data;

  $: weapon = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: additional = data.additional || {};
  $: pendingChange = data.pendingChange;
  $: effects = data.effects || [];
  $: vehicleAttachmentTypes = data.vehicleAttachmentTypes || [];
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: canCreateNew = data.canCreateNew !== false;
  $: pendingCreatesCount = data.pendingCreatesCount || 0;
  $: existingChange = data.existingChange;

  // Empty weapon template for create mode
  const emptyWeapon = {
    Id: null,
    ItemId: null,
    Name: '',
    Properties: {
      Description: '',
      Weight: null,
      Type: null,
      Category: null,
      Class: 'Ranged',
      UsesPerMinute: null,
      Range: null,
      ImpactRadius: null,
      Mindforce: null,
      Economy: {
        Efficiency: null,
        MaxTT: null,
        MinTT: null,
        Decay: null,
        AmmoBurn: null,
      },
      Damage: {
        Stab: null,
        Cut: null,
        Impact: null,
        Penetration: null,
        Shrapnel: null,
        Burn: null,
        Cold: null,
        Acid: null,
        Electric: null,
      },
      Skill: {
        Hit: { LearningIntervalStart: null, LearningIntervalEnd: null },
        Dmg: { LearningIntervalStart: null, LearningIntervalEnd: null },
        IsSiB: false,
      },
    },
    Ammo: { Name: null },
    ProfessionHit: { Name: null },
    ProfessionDmg: { Name: null },
    AttachmentType: { Name: null },
    EffectsOnEquip: [],
    EffectsOnUse: [],
    Tiers: [],
  };

  $: currentChangeId = $page.url.searchParams.get('changeId');
  $: createSeed = existingChange?.data || pendingChange?.data || emptyWeapon;

  // ========== EDIT STATE MANAGEMENT ==========
  // Initialize edit state when weapon changes or in create mode
  let lastInitKey = null;
  $: if (user) {
    const createSeedSource = existingChange?.data ? 'existing' : (pendingChange?.data ? 'pending' : 'empty');
    const initKey = data.isCreateMode
      ? `create:${currentChangeId || 'new'}:${createSeedSource}`
      : (weapon?.Id ?? weapon?.ItemId)
        ? `view:${weapon?.Id ?? weapon?.ItemId}`
        : null;

    if (initKey && initKey !== lastInitKey) {
      if (data.isCreateMode) {
        // If editing an existing pending create, use that data; otherwise use empty template
        initEditState(createSeed, 'Weapon', true, existingChange || pendingChange || null);
      } else if (weapon) {
        initEditState(weapon, 'Weapon', false);
      }
      lastInitKey = initKey;
    }
  }

  // Initialize pending change state
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
    // Auto-enable viewing pending change for author or admin
    if (user && (pendingChange.author_id === user.id || user.isAdmin)) {
      setViewingPendingChange(true);
    }
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Determine which entity to display:
  // 1. In edit mode: show currentEntity (original + pending edits)
  // 2. Viewing pending change: show pending change data
  // 3. Otherwise: show original weapon
  $: activeWeapon = $editMode
    ? ($currentEntity || createSeed)
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : (weapon || (data.isCreateMode ? createSeed : null));

  // Track previous entity for navigation detection
  let previousEntityId = null;

  // Exit edit mode when navigating to a different entity (unless it's a draft/pending change)
  $: if (weapon?.Id !== previousEntityId && previousEntityId !== null) {
    // Only exit edit mode if not viewing a draft/pending change
    const hasUnsavedDraft = $editMode && !$existingPendingChange;
    if ($editMode && !hasUnsavedDraft) {
      resetEditState();
    }
    previousEntityId = weapon?.Id;
  } else if (previousEntityId === null && weapon?.Id) {
    previousEntityId = weapon.Id;
  }

  // Cleanup on component destroy
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items from grouped weapons
  $: navItems = allItems;

  // Navigation filters
  const navFilters = [
    {
      key: 'Properties.Class',
      label: 'Class',
      values: [
        { value: 'Ranged', label: 'Ranged' },
        { value: 'Melee', label: 'Melee' },
        { value: 'Mindforce', label: 'Mindforce' },
        { value: 'Attached', label: 'Attached' },
      ]
    }
  ];

  const navTableColumns = [
    {
      key: 'class',
      header: 'Class',
      width: '70px',
      filterPlaceholder: 'Ranged',
      getValue: (item) => item.Properties?.Class,
      format: (v) => v || '-'
    },
    {
      key: 'type',
      header: 'Type',
      width: '70px',
      filterPlaceholder: 'Laser',
      getValue: (item) => item.Properties?.Type,
      format: (v) => v || '-'
    },
    {
      key: 'dps',
      header: 'DPS',
      width: '55px',
      filterPlaceholder: '>10',
      getValue: (item) => getDps(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    },
    {
      key: 'dpp',
      header: 'DPP',
      width: '55px',
      filterPlaceholder: '>2',
      getValue: (item) => getDpp(item),
      format: (v) => v != null ? v.toFixed(2) : '-'
    },
    {
      key: 'eff',
      header: 'Eff',
      width: '55px',
      filterPlaceholder: '>50',
      getValue: (item) => getEfficiency(item),
      format: (v) => v != null ? v.toFixed(1) : '-'
    }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Items', href: '/items' },
    { label: 'Weapons', href: '/items/weapons' },
    ...(data.isCreateMode ? [{ label: 'New Weapon' }] : (weapon ? [{ label: weapon.Name }] : []))
  ];

  // SEO
  $: seoDescription = weapon?.Properties?.Description ||
    `${weapon?.Name || 'Weapon'} - ${weapon?.Properties?.Class || ''} ${weapon?.Properties?.Type || ''} weapon in Entropia Universe.`;

  $: canonicalUrl = weapon
    ? `https://entropianexus.com/items/weapons/${encodeURIComponentSafe(weapon.Name)}`
    : 'https://entropianexus.com/items/weapons';

  // ========== EDITING PERMISSIONS ==========
  // Verified users and admins can edit
  $: canEdit = user?.verified || user?.isAdmin;

  // Check if weapon is tierable
  $: isTierable = activeWeapon && !hasItemTag(activeWeapon.Name, 'L');
  $: hasEffects = (activeWeapon?.EffectsOnEquip?.length > 0) || (activeWeapon?.EffectsOnUse?.length > 0);

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    tiers: true,
    acquisition: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-weapon-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-weapon-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // Image URL for SEO (approved images only)
  $: entityImageUrl = weapon?.Id ? `/api/img/weapon/${weapon.Id}` : null;

  // ========== RELOAD/USES TOGGLE ==========
  let showReload = true;
  $: showReloadEffective = $editMode ? false : showReload;

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-weapon-show-reload');
      if (stored !== null) {
        showReload = stored === 'true';
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function toggleReloadUses() {
    showReload = !showReload;
    try {
      localStorage.setItem('wiki-weapon-show-reload', String(showReload));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== CALCULATOR FUNCTIONS ==========
  function getTotalDamage(item) {
    if (!item?.Properties?.Damage) return null;
    const d = item.Properties.Damage;
    return (d.Impact || 0) + (d.Cut || 0) + (d.Stab || 0) + (d.Penetration || 0) +
           (d.Shrapnel || 0) + (d.Burn || 0) + (d.Cold || 0) + (d.Acid || 0) + (d.Electric || 0);
  }

  function getEffectiveDamage(item) {
    const totalDamage = getTotalDamage(item);
    if (totalDamage === null || totalDamage === 0) return null;
    const multiplier = 0.88 * 0.75 + 0.02 * 1.75;
    return totalDamage * multiplier;
  }

  function getReload(item) {
    if (!item?.Properties?.UsesPerMinute) return null;
    return 60 / item.Properties.UsesPerMinute;
  }

  function getCostPerUse(item) {
    const decay = item?.Properties?.Economy?.Decay;
    const ammoBurn = item?.Properties?.Economy?.AmmoBurn ?? 0;
    if (decay === null || decay === undefined) return null;
    return decay + (ammoBurn / 100);
  }

  function getDps(item) {
    const reload = getReload(item);
    const effectiveDamage = getEffectiveDamage(item);
    if (effectiveDamage === null || reload === null) return null;
    return effectiveDamage / reload;
  }

  function getDpp(item) {
    const cost = getCostPerUse(item);
    const effectiveDamage = getEffectiveDamage(item);
    if (cost === null || cost === 0 || effectiveDamage === null) return null;
    return effectiveDamage / cost;
  }

  function getEfficiency(item) {
    return item?.Properties?.Economy?.Efficiency || null;
  }

  function getTotalUses(item) {
    const maxTT = item?.Properties?.Economy?.MaxTT;
    const minTT = item?.Properties?.Economy?.MinTT ?? 0;
    const decay = item?.Properties?.Economy?.Decay;
    if (maxTT === null || maxTT === undefined || decay === null || decay === undefined || decay === 0) return null;
    return Math.floor((maxTT - minTT) / (decay / 100));
  }

  // Skill-related getters
  function getSkillInfo(item) {
    return item?.Properties?.Skill || null;
  }

  function getProfessionNames(item) {
    // Profession names are at top level, not in Properties.Skill
    return {
      hit: item?.ProfessionHit?.Name || null,
      dmg: item?.ProfessionDmg?.Name || null
    };
  }

  function getSkillIntervals(item) {
    const skill = getSkillInfo(item);
    if (!skill) return null;
    return {
      hit: {
        min: skill.Hit?.LearningIntervalStart ?? null,
        max: skill.Hit?.LearningIntervalEnd ?? null
      },
      dmg: {
        min: skill.Dmg?.LearningIntervalStart ?? null,
        max: skill.Dmg?.LearningIntervalEnd ?? null
      }
    };
  }

  // Reactive calculations - use activeWeapon to update in real-time during editing
  $: dps = getDps(activeWeapon);
  $: dpp = getDpp(activeWeapon);
  $: efficiency = getEfficiency(activeWeapon);
  $: costPerUse = getCostPerUse(activeWeapon);
  $: reload = getReload(activeWeapon);
  $: totalUses = getTotalUses(activeWeapon);
  $: effectiveDamage = getEffectiveDamage(activeWeapon);
  $: skillInfo = getSkillInfo(activeWeapon);
  $: professionNames = getProfessionNames(activeWeapon);
  $: skillIntervals = getSkillIntervals(activeWeapon);

  // ========== CONDITIONAL FIELD OPTIONS ==========
  // Category options based on Class
  $: categoryOptions = (() => {
    const cls = activeWeapon?.Properties?.Class;
    if (cls === 'Ranged') return ['Rifle', 'Carbine', 'Pistol', 'Cannon', 'Flamethrower', 'Support', 'Mounted'];
    if (cls === 'Melee') return ['Axe', 'Sword', 'Knife', 'Whip', 'Club', 'Power Fist'];
    if (cls === 'Mindforce') return ['Chip'];
    if (cls === 'Attached') return ['Hanging', 'Turret'];
    if (cls === 'Stationary') return ['Turret'];
    return [];
  })();

  // Type options based on Class
  $: typeOptions = (() => {
    const cls = activeWeapon?.Properties?.Class;
    if (cls === 'Ranged' || cls === 'Attached' || cls === 'Stationary') {
      return ['Laser', 'BLP', 'Explosive', 'Gauss', 'Plasma', 'Mining Laser (Low)', 'Mining Laser (Medium)', 'Mining Laser (High)'];
    }
    if (cls === 'Melee') return ['Blades', 'Clubs', 'Fists', 'Whips'];
    if (cls === 'Mindforce') return ['Pyrokinetic', 'Cryogenic', 'Electrokinesis'];
    return [];
  })();

  // Ammo Type options based on Class
  $: ammoOptions = (() => {
    const cls = activeWeapon?.Properties?.Class;
    if (cls === 'Ranged' || cls === 'Attached' || cls === 'Stationary') {
      return ['Weapon Cells', 'BLP Pack', 'Explosive Projectiles'];
    }
    if (cls === 'Melee') return [null, 'Weapon Cells'];
    if (cls === 'Mindforce') return ['Synthetic Mind Essence', 'Mind Essence', 'Light Mind Essence'];
    return [];
  })();

  // Hit Profession options based on Type
  $: hitProfessionOptions = (() => {
    const type = activeWeapon?.Properties?.Type;
    if (type === 'Laser') return ['Laser Pistoleer (Hit)', 'Laser Sniper (Hit)', 'Mounted Laser (Hit)'];
    if (type === 'BLP') return ['BLP Pistoleer (Hit)', 'BLP Sniper (Hit)', 'Mounted BLP (Hit)'];
    if (type === 'Plasma') return ['Plasma Pistoleer (Hit)', 'Plasma Sniper (Hit)'];
    if (type === 'Gauss') return ['Gauss Sniper (Hit)'];
    if (type === 'Explosive') return ['Grenadier (Hit)', 'Mounted Grenadier (Hit)'];
    if (type?.startsWith('Mining Laser')) return ['Mining Laser (Hit)'];
    if (type === 'Pyrokinetic') return ['Pyro Kinetic (Hit)'];
    if (type === 'Cryogenic') return ['Cryogenic (Hit)'];
    if (type === 'Electrokinesis') return ['Electro Kinetic (Hit)'];
    if (type === 'Blades') return ['Swordsman (Hit)', 'Knifefighter (Hit)', 'Whipper (Hit)'];
    if (type === 'Clubs') return ['One Handed Clubber (Hit)', 'Two Handed Clubber (Hit)'];
    if (type === 'Fists') return ['Brawler (Hit)'];
    if (type === 'Whips') return ['Whipper (Hit)'];
    return [];
  })();

  // Dmg Profession options based on Type
  $: dmgProfessionOptions = (() => {
    const type = activeWeapon?.Properties?.Type;
    if (type === 'Laser') return ['Ranged Laser (Dmg)'];
    if (type === 'BLP') return ['Ranged BLP (Dmg)'];
    if (type === 'Plasma') return ['Ranged Plasma (Dmg)'];
    if (type === 'Gauss') return ['Ranged Gauss (Dmg)'];
    if (type === 'Explosive') return ['Grenadier (Dmg)'];
    if (type?.startsWith('Mining Laser')) return ['Mining Laser (Dmg)'];
    if (type === 'Pyrokinetic') return ['Pyro Kinetic (Dmg)'];
    if (type === 'Cryogenic') return ['Cryogenic (Dmg)'];
    if (type === 'Electrokinesis') return ['Electro Kinetic (Dmg)'];
    if (type === 'Blades') return ['Swordsman (Dmg)', 'Knifefighter (Dmg)', 'Whipper (Dmg)'];
    if (type === 'Clubs') return ['One Handed Clubber (Dmg)', 'Two Handed Clubber (Dmg)'];
    if (type === 'Fists') return ['Brawler (Dmg)'];
    if (type === 'Whips') return ['Whipper (Dmg)'];
    return [];
  })();

  // ========== SMART INFERENCE ==========
  // Auto-select values when there's only one valid option.
  // This speeds up editing by inferring obvious choices.

  // Track previous values to detect changes
  let prevClass = null;
  let prevType = null;

  // When Class changes, auto-select Category if only one option exists
  $: if ($editMode && activeWeapon?.Properties?.Class && activeWeapon.Properties.Class !== prevClass) {
    prevClass = activeWeapon.Properties.Class;
    // If only one category option for this class, auto-select it
    if (categoryOptions.length === 1 && activeWeapon.Properties.Category !== categoryOptions[0]) {
      updateField('Properties.Category', categoryOptions[0]);
    }
    // If current category is not valid for new class, clear it
    if (categoryOptions.length > 0 && activeWeapon.Properties.Category && !categoryOptions.includes(activeWeapon.Properties.Category)) {
      updateField('Properties.Category', categoryOptions.length === 1 ? categoryOptions[0] : null);
    }
    // If only one type option for this class, auto-select it
    if (typeOptions.length === 1 && activeWeapon.Properties.Type !== typeOptions[0]) {
      updateField('Properties.Type', typeOptions[0]);
    }
    // If current type is not valid for new class, clear it
    if (typeOptions.length > 0 && activeWeapon.Properties.Type && !typeOptions.includes(activeWeapon.Properties.Type)) {
      updateField('Properties.Type', typeOptions.length === 1 ? typeOptions[0] : null);
    }
  }

  // When Type changes, auto-select professions if only one option exists
  $: if ($editMode && activeWeapon?.Properties?.Type && activeWeapon.Properties.Type !== prevType) {
    prevType = activeWeapon.Properties.Type;
    // Auto-select Hit Profession if only one option
    if (hitProfessionOptions.length === 1 && professionNames.hit !== hitProfessionOptions[0]) {
      updateField('ProfessionHit.Name', hitProfessionOptions[0]);
    }
    // If current hit profession is not valid for new type, clear or auto-select
    if (hitProfessionOptions.length > 0 && professionNames.hit && !hitProfessionOptions.includes(professionNames.hit)) {
      updateField('ProfessionHit.Name', hitProfessionOptions.length === 1 ? hitProfessionOptions[0] : null);
    }
    // Auto-select Dmg Profession if only one option
    if (dmgProfessionOptions.length === 1 && professionNames.dmg !== dmgProfessionOptions[0]) {
      updateField('ProfessionDmg.Name', dmgProfessionOptions[0]);
    }
    // If current dmg profession is not valid for new type, clear or auto-select
    if (dmgProfessionOptions.length > 0 && professionNames.dmg && !dmgProfessionOptions.includes(professionNames.dmg)) {
      updateField('ProfessionDmg.Name', dmgProfessionOptions.length === 1 ? dmgProfessionOptions[0] : null);
    }
  }
</script>

<WikiSEO
  title={weapon?.Name || 'Weapons'}
  description={seoDescription}
  entityType="weapon"
  entity={weapon}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

  <WikiPage
    title="Weapons"
    {breadcrumbs}
    entity={data.isCreateMode ? ($currentEntity || createSeed) : weapon}
    entityType="Weapon"
    basePath="/items/weapons"
    {navItems}
    {navFilters}
    {navTableColumns}
    {user}
  editable={true}
  canEdit={canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if activeWeapon}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode}
      <PendingChangeBanner
        pendingChange={$existingPendingChange}
        viewing={$viewingPendingChange}
        onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
      />
    {/if}

    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeWeapon?.Id}
            entityName={activeWeapon?.Name}
            entityType="weapon"
            {user}
            isEditMode={$editMode}
            isCreateMode={$isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeWeapon.Name}
              path="Name"
              type="text"
              required
            />
          </div>
          <div class="infobox-subtitle">
            <span class="type-badge">{activeWeapon.Properties?.Class || 'Unknown'}</span>
            <span>{activeWeapon.Properties?.Category || ''} &bull; {activeWeapon.Properties?.Type || ''}</span>
          </div>
        </div>

        <!-- Tier 1 Stats (toned down) -->
        <div class="stats-section tier-1">
          <div class="stat-row primary">
            <span class="stat-label">Efficiency</span>
            <span class="stat-value">{efficiency ? `${efficiency.toFixed(1)}%` : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">DPS</span>
            <span class="stat-value">{dps ? dps.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">DPP</span>
            <span class="stat-value">{dpp ? dpp.toFixed(2) : 'N/A'}</span>
          </div>
        </div>

        <!-- Tier 2 Stats -->
        <div class="stats-section tier-2">
          <h4 class="section-title">Performance</h4>
          <div class="stat-row">
            <span class="stat-label">Effective Dmg</span>
            <span class="stat-value">{effectiveDamage ? effectiveDamage.toFixed(2) : 'N/A'}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Range</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Range}
                path="Properties.Range"
                type="number"
                suffix="m"
                min={0}
                step={0.1}
              />
            </span>
          </div>
          {#if $editMode}
            <!-- In edit mode, always show Uses/min as editable -->
            <div class="stat-row">
              <span class="stat-label">Uses/min</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.UsesPerMinute}
                  path="Properties.UsesPerMinute"
                  type="number"
                  min={0}
                  step={0.01}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Reload</span>
              <span class="stat-value">{reload ? `${reload.toFixed(2)}s` : 'N/A'}</span>
            </div>
          {:else}
            <!-- In view mode, toggle between Reload and Uses/min -->
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div class="stat-row toggleable" on:click={toggleReloadUses} title="Click to toggle between Reload and Uses/min">
              {#if showReloadEffective}
                <span class="stat-label">Reload <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{reload ? `${reload.toFixed(2)}s` : 'N/A'}</span>
              {:else}
                <span class="stat-label">Uses/min <span class="toggle-hint">⇄</span></span>
                <span class="stat-value">{activeWeapon.Properties?.UsesPerMinute ?? 'N/A'}</span>
              {/if}
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Cost/Use</span>
            <span class="stat-value">{costPerUse ? `${costPerUse.toFixed(4)} PEC` : 'N/A'}</span>
          </div>
        </div>

        <!-- Economy Stats -->
        <div class="stats-section tier-3">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row">
            <span class="stat-label">Efficiency</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Economy?.Efficiency}
                path="Properties.Economy.Efficiency"
                type="number"
                suffix="%"
                min={0}
                max={100}
                step={0.1}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max TT</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Economy?.MaxTT}
                path="Properties.Economy.MaxTT"
                type="number"
                suffix=" PED"
                min={0}
                step={0.00001}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Min TT</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Economy?.MinTT}
                path="Properties.Economy.MinTT"
                type="number"
                suffix=" PED"
                min={0}
                step={0.00001}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Decay</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Economy?.Decay}
                path="Properties.Economy.Decay"
                type="number"
                suffix=" PEC"
                min={0}
                step={0.00001}
              />
            </span>
          </div>
          {#if activeWeapon.Ammo?.Name || $editMode}
            <div class="stat-row">
              <span class="stat-label">Ammo Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Ammo?.Name}
                  path="Ammo.Name"
                  type="select"
                  placeholder="None"
                  options={ammoOptions.filter(v => v !== null).map(v => ({ value: v, label: v }))}
                />
              </span>
            </div>
            {#if activeWeapon.Ammo?.Name}
              <div class="stat-row">
                <span class="stat-label">Ammo Burn</span>
                <span class="stat-value">
                  <InlineEdit
                    value={activeWeapon.Properties?.Economy?.AmmoBurn}
                    path="Properties.Economy.AmmoBurn"
                    type="number"
                    min={0}
                    step={1}
                  />
                </span>
              </div>
            {/if}
          {/if}
          <div class="stat-row">
            <span class="stat-label">Total Uses</span>
            <span class="stat-value">{totalUses ?? 'N/A'}</span>
          </div>
        </div>

        <!-- Properties -->
        <div class="stats-section">
          <h4 class="section-title">Properties</h4>
          <div class="stat-row">
            <span class="stat-label">Class</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Class}
                path="Properties.Class"
                type="select"
                options={[
                  { value: 'Ranged', label: 'Ranged' },
                  { value: 'Melee', label: 'Melee' },
                  { value: 'Mindforce', label: 'Mindforce' },
                  { value: 'Attached', label: 'Attached' },
                  { value: 'Stationary', label: 'Stationary' }
                ]}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Category</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Category}
                path="Properties.Category"
                type="select"
                options={categoryOptions.map(v => ({ value: v, label: v }))}
              />
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Type</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Type}
                path="Properties.Type"
                type="select"
                options={typeOptions.map(v => ({ value: v, label: v }))}
              />
            </span>
          </div>
          {#if activeWeapon.Properties?.Class === 'Attached'}
            <div class="stat-row">
              <span class="stat-label">Attachment Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.AttachmentType?.Name}
                  path="AttachmentType.Name"
                  type="select"
                  placeholder="None"
                  options={vehicleAttachmentTypes.map(v => ({ value: v.Name, label: v.Name }))}
                />
              </span>
            </div>
          {/if}
          <div class="stat-row">
            <span class="stat-label">Weight</span>
            <span class="stat-value">
              <InlineEdit
                value={activeWeapon.Properties?.Weight}
                path="Properties.Weight"
                type="number"
                suffix="kg"
                min={0}
                step={0.1}
              />
            </span>
          </div>
          {#if activeWeapon.Properties?.Type === 'Explosive'}
            <div class="stat-row">
              <span class="stat-label">Impact Radius</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.ImpactRadius}
                  path="Properties.ImpactRadius"
                  type="number"
                  suffix="m"
                  min={0}
                  step={0.1}
                />
              </span>
            </div>
          {/if}
        </div>

        <!-- Skilling Info -->
        <div class="stats-section">
          <h4 class="section-title">Skilling</h4>
          <div class="stat-row">
            <span class="stat-label">SiB</span>
            <span class="stat-value" class:highlight-yes={skillInfo?.IsSiB}>
              <InlineEdit
                value={skillInfo?.IsSiB}
                path="Properties.Skill.IsSiB"
                type="checkbox"
              />
            </span>
          </div>
          {#if professionNames.hit || $editMode}
            <div class="stat-row">
              <span class="stat-label">Hit Profession</span>
              <span class="stat-value wide-select">
                {#if $editMode}
                  <InlineEdit
                    value={professionNames.hit}
                    path="ProfessionHit.Name"
                    type="select"
                    placeholder="None"
                    options={hitProfessionOptions.map(v => ({ value: v, label: v }))}
                  />
                {:else}
                  <a href={getTypeLink(professionNames.hit, 'Profession')} class="profession-link">{professionNames.hit}</a>
                {/if}
              </span>
            </div>
            {#if skillInfo?.IsSiB && (skillIntervals?.hit?.min !== null || skillIntervals?.hit?.max !== null || $editMode)}
              <div class="stat-row indent">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">
                  {#if $editMode}
                    <span class="interval-edit">
                      <InlineEdit
                        value={skillIntervals?.hit?.min}
                        path="Properties.Skill.Hit.LearningIntervalStart"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="Min"
                      />
                      <span class="interval-sep">-</span>
                      <InlineEdit
                        value={skillIntervals?.hit?.max}
                        path="Properties.Skill.Hit.LearningIntervalEnd"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="Max"
                      />
                    </span>
                  {:else}
                    {skillIntervals?.hit?.min ?? '?'} - {skillIntervals?.hit?.max ?? '?'}
                  {/if}
                </span>
              </div>
            {/if}
          {/if}
          {#if professionNames.dmg || $editMode}
            <div class="stat-row">
              <span class="stat-label">Dmg Profession</span>
              <span class="stat-value wide-select">
                {#if $editMode}
                  <InlineEdit
                    value={professionNames.dmg}
                    path="ProfessionDmg.Name"
                    type="select"
                    placeholder="None"
                    options={dmgProfessionOptions.map(v => ({ value: v, label: v }))}
                  />
                {:else}
                  <a href={getTypeLink(professionNames.dmg, 'Profession')} class="profession-link">{professionNames.dmg}</a>
                {/if}
              </span>
            </div>
            {#if skillInfo?.IsSiB && (skillIntervals?.dmg?.min !== null || skillIntervals?.dmg?.max !== null || $editMode)}
              <div class="stat-row indent">
                <span class="stat-label">Level Range</span>
                <span class="stat-value">
                  {#if $editMode}
                    <span class="interval-edit">
                      <InlineEdit
                        value={skillIntervals?.dmg?.min}
                        path="Properties.Skill.Dmg.LearningIntervalStart"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="Min"
                      />
                      <span class="interval-sep">-</span>
                      <InlineEdit
                        value={skillIntervals?.dmg?.max}
                        path="Properties.Skill.Dmg.LearningIntervalEnd"
                        type="number"
                        min={0}
                        step={0.1}
                        placeholder="Max"
                      />
                    </span>
                  {:else}
                    {skillIntervals?.dmg?.min ?? '?'} - {skillIntervals?.dmg?.max ?? '?'}
                  {/if}
                </span>
              </div>
            {/if}
          {/if}
        </div>

        <!-- Mindforce Properties (only for Mindforce weapons) -->
        {#if activeWeapon.Properties?.Class === 'Mindforce'}
          <div class="stats-section">
            <h4 class="section-title">Mindforce</h4>
            <div class="stat-row">
              <span class="stat-label">Level</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.Mindforce?.Level}
                  path="Properties.Mindforce.Level"
                  type="number"
                  min={1}
                  step={1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Concentration</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.Mindforce?.Concentration}
                  path="Properties.Mindforce.Concentration"
                  type="number"
                  suffix="s"
                  min={0}
                  step={0.1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.Mindforce?.Cooldown}
                  path="Properties.Mindforce.Cooldown"
                  type="number"
                  suffix="s"
                  min={0}
                  step={0.1}
                />
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Cooldown Group</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeWeapon.Properties?.Mindforce?.CooldownGroup}
                  path="Properties.Mindforce.CooldownGroup"
                  type="number"
                  min={1}
                  step={1}
                />
              </span>
            </div>
          </div>
        {/if}

        <!-- Damage Breakdown (bars) -->
        <div class="stats-section damage-section">
          <h4 class="section-title">Damage Breakdown</h4>
          <DamageBreakdownGrid weapon={activeWeapon} />
        </div>

        <!-- Effects (if any) -->
        {#if hasEffects || $editMode}
          <div class="stats-section effects-section">
            <h4 class="section-title">Effects</h4>
            <div class="effects-combined">
              <EffectsEditor
                effects={activeWeapon?.EffectsOnEquip || []}
                fieldName="EffectsOnEquip"
                availableEffects={effects}
                effectType="equip"
                showEmpty={$editMode}
              />
              <EffectsEditor
                effects={activeWeapon?.EffectsOnUse || []}
                fieldName="EffectsOnUse"
                availableEffects={effects}
                effectType="use"
                showEmpty={$editMode}
              />
            </div>
          </div>
        {/if}

        <!-- Loadout Calculator Link -->
        <a href="/tools/loadouts?weapon={encodeURIComponentSafe(activeWeapon.Name)}" class="loadout-link-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="4" y="4" width="16" height="16" rx="2" />
            <path d="M9 9h6M9 12h6M9 15h4" />
          </svg>
          <span>Open in Loadout Calculator</span>
        </a>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeWeapon.Name}
            path="Name"
            type="text"
            required
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeWeapon.Properties?.Description || ''}
              placeholder="Enter weapon description..."
              on:change={(e) => updateField('Properties.Description', e.detail)}
            />
          {:else if activeWeapon.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeWeapon.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeWeapon.Name} is a {activeWeapon.Properties?.Class?.toLowerCase() || ''} {activeWeapon.Properties?.Type?.toLowerCase() || ''} weapon.
            </div>
          {/if}
        </div>

        <!-- Tiering Section -->
        {#if isTierable}
          <DataSection
            title="Tiers"
            icon=""
            bind:expanded={panelStates.tiers}
            subtitle="{(additional.tierInfo?.length || activeWeapon?.Tiers?.length || 0)} tiers"
            on:toggle={savePanelStates}
          >
            <TieringEditor entity={activeWeapon} entityType="Weapon" tierInfo={additional.tierInfo || []} />
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
      {#if data.isCreateMode && !user}
        <h2>Login Required</h2>
        <p>You need to log in and verify your account to create new weapons.</p>
        <a href="/discord/login?redirect={encodeURIComponent($page.url.pathname + $page.url.search)}" class="login-link-btn">
          Login with Discord
        </a>
      {:else if data.isCreateMode}
        <h2>Loading...</h2>
        <p>Preparing new weapon form...</p>
      {:else}
        <h2>Weapons</h2>
        <p>Select a weapon from the list to view details.</p>
      {/if}
    </div>
  {/if}
</WikiPage>

<style>
  /* Pending Change Banner */
  .pending-change-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 16px;
    background-color: var(--warning-bg, #422006);
    border: 1px solid var(--warning-color, #f59e0b);
    border-radius: 8px;
    margin-bottom: 16px;
  }

  .pending-change-banner.viewing {
    background-color: var(--info-bg, #0c1929);
    border-color: var(--accent-color, #4a9eff);
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .banner-icon {
    display: flex;
    color: var(--warning-color, #f59e0b);
  }

  .pending-change-banner.viewing .banner-icon {
    color: var(--accent-color, #4a9eff);
  }

  .banner-text {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-color);
  }

  .banner-toggle {
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    background-color: var(--warning-color, #f59e0b);
    color: #000;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
  }

  .pending-change-banner.viewing .banner-toggle {
    background-color: var(--accent-color, #4a9eff);
    color: #fff;
  }

  .banner-toggle:hover {
    filter: brightness(1.1);
  }

  .layout-a {
    position: relative;
    width: 100%;
  }

  /* Clearfix to ensure spacing after floated infobox */
  .layout-a::after {
    content: '';
    display: block;
    clear: both;
  }

  /* Floating infobox - Wikipedia style */
  .wiki-infobox-float {
    float: right;
    width: 320px;
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
    background: linear-gradient(135deg, #3a6d99 0%, #2d5577 100%);
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
    color: #e8f4ff;
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

  .stat-value.highlight-yes {
    color: var(--success-color, #4ade80);
  }

  .stat-row.toggleable {
    cursor: pointer;
    padding: 4px 6px;
    margin: 0 -6px;
    border-radius: 4px;
    transition: background-color 0.15s;
  }

  .stat-row.toggleable:hover {
    background-color: var(--hover-color);
  }

  .toggle-hint {
    font-size: 10px;
    color: var(--text-muted, #999);
    margin-left: 4px;
    opacity: 0.7;
  }

  .stat-row.toggleable:hover .toggle-hint {
    opacity: 1;
  }

  .stat-row.indent {
    padding-left: 12px;
  }

  .stat-row.indent .stat-label {
    font-size: 11px;
  }

  .profession-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .profession-link:hover {
    text-decoration: underline;
  }

  .interval-edit {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .interval-sep {
    color: var(--text-muted, #999);
    font-weight: 400;
  }

  /* Wider select dropdowns for Class, Category, Type, Professions */
  .stat-value :global(.inline-edit .edit-select) {
    min-width: 160px;
  }

  .stat-value.wide-select :global(.inline-edit .edit-select) {
    min-width: 180px;
  }

  .damage-section,
  .effects-section {
    padding: 12px;
  }

  /* Combined effects layout (equip + use side by side) */
  .effects-combined {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 16px;
  }

  .effects-combined :global(.effects-editor) {
    flex: 1;
    min-width: 200px;
  }

  @media (max-width: 899px) {
    .effects-combined {
      flex-direction: column;
    }
  }

  .loadout-link-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 10px 16px;
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    color: var(--text-color);
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s;
  }

  .loadout-link-btn:hover {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .loadout-link-btn svg {
    flex-shrink: 0;
  }

  .wiki-article {
    overflow: hidden; /* Contains floated infobox */
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

  .no-selection .login-link-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-top: 16px;
    padding: 10px 20px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    text-decoration: none;
    border-radius: 6px;
    font-weight: 500;
    transition: all 0.15s;
  }

  .no-selection .login-link-btn:hover {
    filter: brightness(1.1);
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

    /* Hide article title on mobile - redundant with infobox */
    .article-title {
      display: none;
    }

    .infobox-title {
      font-size: 16px;
    }
  }
</style>
