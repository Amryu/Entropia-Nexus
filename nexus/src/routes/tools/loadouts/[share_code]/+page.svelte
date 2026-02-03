<script>
  // @ts-nocheck
  import '$lib/style.css';
  import '../loadouts.css';
  import './share.css';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import { clampDecimals } from '$lib/util.js';
  import * as LoadoutCalc from '$lib/utils/loadoutCalculations.js';
  import { loadLoadoutEntities } from '$lib/utils/entityLoader';

  export let data;

  $: user = data?.session?.user;
  $: shared = data?.object;
  $: shareError = data?.additional?.error ?? data?.error;
  $: shareCode = data?.additional?.shareCode;
  $: loadout = shared?.data ?? null;
  $: displayName = loadout?.Name || shared?.name || 'Shared Loadout';

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const LOCAL_STORAGE_KEY = 'loadouts';

  let weapons = [];
  let amplifiers = [];
  let scopes = [];
  let sights = [];
  let absorbers = [];
  let matrices = [];
  let implants = [];
  let armors = [];
  let armorplatings = [];

  let entitiesLoading = true;
  let entitiesError = null;

  let isCopying = false;
  let copyStatus = null;
  let copyError = null;

  const breadcrumbs = [
    { label: 'Tools', href: '/tools' },
    { label: 'Loadouts', href: '/tools/loadouts' },
    { label: 'Shared' }
  ];

  function alphabeticalSort(a, b) {
    if (a?.Name === null) return 1;
    if (b?.Name === null) return -1;
    return a.Name.localeCompare(b.Name, undefined, { numeric: true });
  }

  function processEntityData(entities) {
    const rawWeapons = entities.weapons || [];
    const rawAmplifiers = entities.weaponAmplifiers || [];
    const rawVisionAttachments = entities.weaponVisionAttachments || [];

    weapons = rawWeapons.filter(x => x.Properties?.Class !== 'Attached' && x.Properties?.Class !== 'Stationary').sort(alphabeticalSort);
    amplifiers = rawAmplifiers.filter(x => x.Properties?.Type !== 'Matrix').sort(alphabeticalSort);
    scopes = rawVisionAttachments.filter(x => x.Properties?.Type === 'Scope').sort(alphabeticalSort);
    sights = rawVisionAttachments.filter(x => x.Properties?.Type === 'Sight').sort(alphabeticalSort);
    absorbers = (entities.absorbers || []).sort(alphabeticalSort);
    matrices = rawAmplifiers.filter(x => x.Properties?.Type === 'Matrix').sort(alphabeticalSort);
    implants = (entities.mindforceImplants || []).sort(alphabeticalSort);
    armors = (entities.armors || []).sort(alphabeticalSort);
    armorplatings = (entities.armorPlatings || []).sort(alphabeticalSort);
  }

  onMount(async () => {
    if (!loadout) {
      entitiesLoading = false;
      return;
    }
    entitiesLoading = true;
    entitiesError = null;
    try {
      const entities = await loadLoadoutEntities();
      processEntityData(entities);
    } catch (error) {
      console.error('Failed to load entity data:', error);
      entitiesError = 'Failed to load reference data.';
    } finally {
      entitiesLoading = false;
    }
  });

  function readLocalLoadouts() {
    if (typeof localStorage === 'undefined') return [];
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      console.error('Failed to read local loadouts:', err);
      return [];
    }
  }

  function writeLocalLoadouts(next) {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(next || []));
  }

  function createCopyLoadout(source) {
    const clone = JSON.parse(JSON.stringify(source));
    clone.Id = crypto?.randomUUID ? crypto.randomUUID() : Math.random().toString(16).slice(2);
    clone.Name = source?.Name ? `Copy of ${source.Name}` : 'Loadout Copy';
    return clone;
  }

  async function handleMakeCopy() {
    if (!loadout || isCopying) return;
    isCopying = true;
    copyStatus = null;
    copyError = null;
    const copy = createCopyLoadout(loadout);

    try {
      if (user) {
        const response = await fetch('/api/tools/loadout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: copy.Name, data: copy })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result?.error || 'Failed to create loadout.');
        }
        copyStatus = 'Loadout saved to your account.';
      } else {
        const local = readLocalLoadouts();
        local.unshift(copy);
        writeLocalLoadouts(local);
        copyStatus = 'Loadout saved locally.';
      }
      await goto('/tools/loadouts');
    } catch (error) {
      console.error('Copy failed:', error);
      copyError = error.message || 'Failed to copy loadout.';
    } finally {
      isCopying = false;
    }
  }

  function getWeapon(name) {
    return weapons.find(x => x.Name === name);
  }

  function getAmplifier(name) {
    return amplifiers.find(x => x.Name === name);
  }

  function getAbsorber(name) {
    return absorbers.find(x => x.Name === name);
  }

  function getScope(name) {
    return scopes.find(x => x.Name === name);
  }

  function getSight(name) {
    return sights.find(x => x.Name === name);
  }

  function getMatrix(name) {
    return matrices.find(x => x.Name === name);
  }

  function getImplant(name) {
    return implants.find(x => x.Name === name);
  }

  function getArmor(name) {
    return armors.find(x => x.Name === name);
  }

  function getArmorPlating(name) {
    return armorplatings.find(x => x.Name === name);
  }

  function getClothingSlot(slotName, side = null) {
    const list = loadout?.Gear?.Clothing || [];
    return list.find(item => item?.Slot === slotName && (side ? item?.Side === side : !item?.Side));
  }

  $: ringLeft = getClothingSlot('Ring', 'Left')?.Name || null;
  $: ringRight = getClothingSlot('Ring', 'Right')?.Name || null;
  $: otherClothing = (loadout?.Gear?.Clothing || []).filter(item => item?.Slot && item.Slot !== 'Ring');

  function calcTotalDamage(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);

    return LoadoutCalc.calculateTotalDamage(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout?.Properties?.BonusDamage ?? 0,
      amplifier
    );
  }

  function calcEffectiveDamage(loadout) {
    const critChance = calcCritChance(loadout);
    const critDamage = calcCritDamage(loadout);
    const hitAbility = calcHitAbility(loadout);
    const damageInterval = calcDamageInterval(loadout);

    return LoadoutCalc.calculateEffectiveDamage(damageInterval, critChance, critDamage, hitAbility);
  }

  function calcDamageInterval(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const totalDamage = calcTotalDamage(loadout);

    return LoadoutCalc.calculateDamageInterval(
      weapon,
      loadout.Skill.Dmg,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0,
      totalDamage
    );
  }

  function calcHitAbility(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);

    return LoadoutCalc.calculateHitAbility(
      weapon,
      loadout.Skill.Hit,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0
    );
  }

  function calcCritChance(loadout) {
    const critAbility = calcCritAbility(loadout);

    return LoadoutCalc.calculateCritChance(
      critAbility,
      loadout.Gear.Weapon.Enhancers.Accuracy,
      loadout?.Properties?.BonusCritChance ?? 0
    );
  }

  function calcCritAbility(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);

    return LoadoutCalc.calculateCritAbility(
      weapon,
      loadout.Skill.Hit,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0
    );
  }

  function calcCritDamage(loadout) {
    return LoadoutCalc.calculateCritDamage(loadout?.Properties?.BonusCritDamage ?? 0);
  }

  function calcRange(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);

    return LoadoutCalc.calculateRange(
      weapon,
      loadout.Skill.Hit,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0,
      loadout.Gear.Weapon.Enhancers.Range
    );
  }

  function calcDecay(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const absorber = getAbsorber(loadout.Gear.Weapon.Absorber?.Name);
    const implant = getImplant(loadout.Gear.Weapon.Implant?.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);
    const scope = getScope(loadout.Gear.Weapon.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon.Sight?.Name);
    const matrix = getMatrix(loadout.Gear.Weapon.Matrix?.Name);

    return LoadoutCalc.calculateDecay(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy,
      absorber,
      implant,
      amplifier,
      scope,
      scopeSight,
      sight,
      matrix,
      loadout.Markup
    );
  }

  function calcAmmo(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);

    return LoadoutCalc.calculateAmmoBurn(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy,
      amplifier
    );
  }

  function calcCost(loadout) {
    const decay = calcDecay(loadout);
    const ammo = calcAmmo(loadout);

    return LoadoutCalc.calculateCost(decay, ammo, loadout.Markup.Ammo ?? 100);
  }

  function calcDpp(loadout) {
    const effectiveDamage = calcEffectiveDamage(loadout);
    const cost = calcCost(loadout);

    return LoadoutCalc.calculateDPP(effectiveDamage, cost);
  }

  function calcReload(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);

    return LoadoutCalc.calculateReload(
      weapon,
      loadout.Skill.Hit,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0,
      loadout?.Properties?.BonusReload ?? 0
    );
  }

  function calcDps(loadout) {
    const effectiveDamage = calcEffectiveDamage(loadout);
    const reload = calcReload(loadout);

    return LoadoutCalc.calculateDPS(effectiveDamage, reload);
  }

  function calcWeaponCost(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);

    return LoadoutCalc.calculateWeaponCost(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy
    );
  }

  function calcEfficiency(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const weaponCost = calcWeaponCost(loadout);
    const absorber = getAbsorber(loadout.Gear.Weapon.Absorber?.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);
    const scope = getScope(loadout.Gear.Weapon.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon.Sight?.Name);
    const matrix = getMatrix(loadout.Gear.Weapon.Matrix?.Name);

    return LoadoutCalc.calculateEfficiency(
      weapon,
      weaponCost,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy,
      absorber,
      amplifier,
      scope,
      scopeSight,
      sight,
      matrix
    );
  }

  function calcArmorDefense(loadout) {
    const armorPieces = armorSlots.map(slot => getArmor(loadout.Gear.Armor[slot].Name));

    return LoadoutCalc.calculateArmorDefense(
      armorPieces,
      loadout.Gear.Armor.Enhancers.Defense
    );
  }

  function calcPlateDefense(loadout) {
    const platePieces = armorSlots.map(slot => getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name));

    return LoadoutCalc.calculatePlateDefense(platePieces);
  }

  function calcTotalDefense(loadout) {
    const armorDefense = calcArmorDefense(loadout);
    const plateDefense = calcPlateDefense(loadout);

    return LoadoutCalc.calculateTotalDefense(armorDefense, plateDefense);
  }

  function calcArmorDurability(loadout) {
    const armorPieces = armorSlots.map(slot => getArmor(loadout.Gear.Armor[slot].Name));

    return LoadoutCalc.calculateArmorDurability(
      armorPieces,
      loadout.Gear.Armor.Enhancers.Durability
    );
  }

  function calcPlateDurability(loadout) {
    const platePieces = armorSlots.map(slot => getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name));

    return LoadoutCalc.calculatePlateDurability(platePieces);
  }

  function calcTotalAbsorption(loadout) {
    const armorPieces = armorSlots.map(slot => getArmor(loadout.Gear.Armor[slot].Name));
    const platePieces = armorSlots.map(slot => getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name));

    return LoadoutCalc.calculateTotalAbsorption(
      armorPieces,
      platePieces,
      loadout.Gear.Armor.Enhancers.Defense,
      loadout.Gear.Armor.Enhancers.Durability
    );
  }

  function calcBlockChance(loadout) {
    const platePieces = armorSlots.map(slot => getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name));

    return LoadoutCalc.calculateBlockChance(platePieces);
  }

  function calcSkillModification(loadout) {
    const scope = getScope(loadout.Gear.Weapon?.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon?.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon?.Sight?.Name);

    return LoadoutCalc.calculateSkillModification(scope, scopeSight, sight);
  }

  function calcSkillBonus(loadout) {
    const scope = getScope(loadout.Gear.Weapon?.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon?.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon?.Sight?.Name);

    return LoadoutCalc.calculateSkillBonus(scope, scopeSight, sight);
  }

  function calcLowestTotalUses(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const absorber = getAbsorber(loadout.Gear.Weapon.Absorber?.Name);
    const implant = getImplant(loadout.Gear.Weapon.Implant?.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);
    const scope = getScope(loadout.Gear.Weapon.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon.Sight?.Name);
    const matrix = getMatrix(loadout.Gear.Weapon.Matrix?.Name);

    return LoadoutCalc.calculateLowestTotalUses(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy,
      absorber,
      implant,
      amplifier,
      scope,
      scopeSight,
      sight,
      matrix
    );
  }
</script>

<svelte:head>
  <title>{displayName} - Shared Loadout</title>
  <meta name="description" content="Shared loadout configuration on Entropia Nexus." />
</svelte:head>

<WikiPage
  title="Loadout Manager"
  {breadcrumbs}
  entity={loadout}
  editable={false}
  canEdit={false}
  user={user}
>
  <div slot="header-actions" class="share-header-actions">
    <button class="action-btn" on:click={handleMakeCopy} disabled={!loadout || isCopying}>
      {isCopying ? 'Copying...' : 'Make a copy'}
    </button>
  </div>

  <div slot="sidebar" let:isMobile>
    <div class="share-sidebar" class:mobile={isMobile}>
      <div class="sidebar-title">Shared Loadout</div>
      <div class="sidebar-meta">Code: {shareCode || shared?.share_code || 'N/A'}</div>
      <a class="sidebar-link" href="/tools/loadouts">Back to Loadout Manager</a>
      <p class="sidebar-hint">This loadout is read-only. Make a copy to edit.</p>
    </div>
  </div>

  <div class="layout-a loadout-layout">
    <aside class="wiki-infobox-float loadout-infobox">
      <div class="infobox-header">
        <div class="infobox-title">Loadout Stats</div>
        <div class="infobox-subtitle">{displayName}</div>
      </div>
      {#if loadout}
        <div class="stats-section">
          <h4 class="section-title">Offense</h4>
          <div class="stat-row"><span class="stat-label">Total Damage</span><span class="stat-value">{calcTotalDamage(loadout) != null ? `${calcTotalDamage(loadout).toFixed(2)}` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Range</span><span class="stat-value">{calcRange(loadout) != null ? `${calcRange(loadout).toFixed(1)}m` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Critical Chance</span><span class="stat-value">{calcCritChance(loadout) != null ? `${(calcCritChance(loadout) * 100).toFixed(1)}%` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Critical Damage</span><span class="stat-value">{calcCritDamage(loadout) != null ? `${(calcCritDamage(loadout) * 100).toFixed(0)}%` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Effective Damage</span><span class="stat-value">{calcEffectiveDamage(loadout) != null ? `${calcEffectiveDamage(loadout).toFixed(2)}` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Reload</span><span class="stat-value">{calcReload(loadout) != null ? `${calcReload(loadout).toFixed(2)}s` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Uses/min</span><span class="stat-value">{calcReload(loadout) != null ? `${clampDecimals(60 / calcReload(loadout), 0, 2)}` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">DPS</span><span class="stat-value">{calcDps(loadout) != null ? `${calcDps(loadout).toFixed(4)}` : 'N/A'}</span></div>
        </div>
        <div class="stats-section">
          <h4 class="section-title">Economy</h4>
          <div class="stat-row"><span class="stat-label">Efficiency</span><span class="stat-value">{calcEfficiency(loadout) != null ? `${calcEfficiency(loadout).toFixed(1)}%` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Decay</span><span class="stat-value">{calcDecay(loadout) != null ? `${calcDecay(loadout).toFixed(4)} PEC` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Ammo</span><span class="stat-value">{calcAmmo(loadout) != null ? Math.round(calcAmmo(loadout)) : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Cost</span><span class="stat-value">{calcCost(loadout) != null ? `${calcCost(loadout).toFixed(4)} PEC` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">DPP</span><span class="stat-value">{calcDpp(loadout) != null ? `${calcDpp(loadout).toFixed(4)}` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Total Uses</span><span class="stat-value">{calcLowestTotalUses(loadout) != null ? calcLowestTotalUses(loadout) : 'N/A'}</span></div>
        </div>
        <div class="stats-section">
          <h4 class="section-title">Defense</h4>
          <div class="stat-row"><span class="stat-label">Armor Defense</span><span class="stat-value">{calcArmorDefense(loadout) != null ? calcArmorDefense(loadout).toFixed(2) : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Plate Defense</span><span class="stat-value">{calcPlateDefense(loadout) != null ? calcPlateDefense(loadout).toFixed(2) : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Total Defense</span><span class="stat-value">{calcTotalDefense(loadout) != null ? calcTotalDefense(loadout).toFixed(2) : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Block</span><span class="stat-value">{calcBlockChance(loadout) != null ? `${calcBlockChance(loadout).toFixed(1)}%` : 'N/A'}</span></div>
        </div>
        <div class="stats-section">
          <h4 class="section-title">Armor Economy</h4>
          <div class="stat-row"><span class="stat-label">Armor Durability</span><span class="stat-value">{calcArmorDurability(loadout) != null ? calcArmorDurability(loadout) : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Plate Durability</span><span class="stat-value">{calcPlateDurability(loadout) != null ? calcPlateDurability(loadout) : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Total Absorption</span><span class="stat-value">{calcTotalAbsorption(loadout) != null ? `${calcTotalAbsorption(loadout).toFixed(0)} HP` : 'N/A'}</span></div>
        </div>
        <div class="stats-section">
          <h4 class="section-title">Skill</h4>
          <div class="stat-row"><span class="stat-label">Hit Ability</span><span class="stat-value">{calcHitAbility(loadout) != null ? `${calcHitAbility(loadout).toFixed(1)}/10.0` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Crit Ability</span><span class="stat-value">{calcCritAbility(loadout) != null ? `${calcCritAbility(loadout).toFixed(1)}/10.0` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Skill Modification</span><span class="stat-value">{calcSkillModification(loadout) != null ? `${calcSkillModification(loadout).toFixed(1)}%` : 'N/A'}</span></div>
          <div class="stat-row"><span class="stat-label">Skill Bonus</span><span class="stat-value">{calcSkillBonus(loadout) != null ? `${calcSkillBonus(loadout).toFixed(1)}%` : 'N/A'}</span></div>
        </div>
      {:else}
        <div class="stats-empty">No loadout data available.</div>
      {/if}
    </aside>

    <article class="wiki-article loadout-article">
      <h1 class="article-title">{displayName}</h1>

      {#if shareError}
        <div class="share-status error">{shareError}</div>
      {:else if entitiesLoading}
        <div class="loading">
          <div class="spinner"></div>
          <p class="loading-text">Loading loadout data...</p>
        </div>
      {:else if entitiesError}
        <div class="share-status error">{entitiesError}</div>
      {:else if loadout}
        {#if copyStatus}
          <div class="share-status success">{copyStatus}</div>
        {/if}
        {#if copyError}
          <div class="share-status error">{copyError}</div>
        {/if}

        <DataSection title="Weapons" collapsible={false}>
          <div class="details-grid">
            <div class="detail-row"><span class="detail-label">Weapon</span><span class="detail-value">{loadout.Gear.Weapon.Name || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Amplifier</span><span class="detail-value">{loadout.Gear.Weapon.Amplifier?.Name || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Scope</span><span class="detail-value">{loadout.Gear.Weapon.Scope?.Name || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Sight</span><span class="detail-value">{loadout.Gear.Weapon.Sight?.Name || loadout.Gear.Weapon.Scope?.Sight?.Name || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Absorber</span><span class="detail-value">{loadout.Gear.Weapon.Absorber?.Name || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Matrix</span><span class="detail-value">{loadout.Gear.Weapon.Matrix?.Name || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Implant</span><span class="detail-value">{loadout.Gear.Weapon.Implant?.Name || 'None'}</span></div>
          </div>
        </DataSection>

        <DataSection title="Armor" collapsible={false}>
          <div class="details-grid">
            <div class="detail-row"><span class="detail-label">Set</span><span class="detail-value">{loadout.Gear.Armor.SetName || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Plate Set</span><span class="detail-value">{loadout.Gear.Armor.PlateName || 'None'}</span></div>
          </div>
          <div class="details-subgrid">
            {#each armorSlots as slot}
              <div class="detail-row">
                <span class="detail-label">{slot}</span>
                <span class="detail-value">
                  {loadout.Gear.Armor[slot]?.Name || 'None'}
                  {#if loadout.Gear.Armor[slot]?.Plate?.Name}
                    <span class="detail-muted">(Plate: {loadout.Gear.Armor[slot].Plate.Name})</span>
                  {/if}
                </span>
              </div>
            {/each}
          </div>
        </DataSection>

        <DataSection title="Accessories" collapsible={false}>
          <div class="details-grid">
            <div class="detail-row"><span class="detail-label">Ring (Left)</span><span class="detail-value">{ringLeft || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Ring (Right)</span><span class="detail-value">{ringRight || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Pet</span><span class="detail-value">{loadout.Gear.Pet?.Name || 'None'}</span></div>
            <div class="detail-row"><span class="detail-label">Pet Effect</span><span class="detail-value">{loadout.Gear.Pet?.Effect || 'None'}</span></div>
          </div>
          {#if otherClothing.length > 0}
            <div class="details-subgrid">
              {#each otherClothing as item}
                <div class="detail-row">
                  <span class="detail-label">{item.Slot}</span>
                  <span class="detail-value">{item.Name || 'None'}</span>
                </div>
              {/each}
            </div>
          {/if}
        </DataSection>

        <DataSection title="Settings" collapsible={false}>
          <div class="details-grid">
            <div class="detail-row"><span class="detail-label">Hit Skill</span><span class="detail-value">{loadout.Skill?.Hit ?? 'N/A'}</span></div>
            <div class="detail-row"><span class="detail-label">Damage Skill</span><span class="detail-value">{loadout.Skill?.Dmg ?? 'N/A'}</span></div>
            <div class="detail-row"><span class="detail-label">Bonus Damage</span><span class="detail-value">{loadout.Properties?.BonusDamage ?? 0}%</span></div>
            <div class="detail-row"><span class="detail-label">Bonus Crit Chance</span><span class="detail-value">{loadout.Properties?.BonusCritChance ?? 0}%</span></div>
            <div class="detail-row"><span class="detail-label">Bonus Crit Damage</span><span class="detail-value">{loadout.Properties?.BonusCritDamage ?? 0}%</span></div>
            <div class="detail-row"><span class="detail-label">Bonus Reload</span><span class="detail-value">{loadout.Properties?.BonusReload ?? 0}%</span></div>
          </div>
        </DataSection>
      {:else}
        <div class="share-status">Shared loadout not available.</div>
      {/if}
    </article>
  </div>
</WikiPage>




