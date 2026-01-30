<script>
  // @ts-nocheck
  import '$lib/style.css';

  import { onMount } from 'svelte';

  import ItemPicker from '$lib/components/ItemPicker.svelte';
  import LoadoutList from '$lib/components/LoadoutList.svelte';
  import { darkMode, loading } from '../../../stores.js';
  import Table from '$lib/components/Table.svelte';
  import { clampDecimals } from '$lib/util.js';
  import * as LoadoutCalc from '$lib/utils/loadoutCalculations.js';
  import { loadLoadoutEntities } from '$lib/utils/entityLoader';

  export let data;

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];

  let settings = {
    onlyShowReasonableAmplifiers: true,
    overampCap: 10,
  }

  let weapons = [];
  let amplifiers = [];
  let scopes = [];
  let sights = [];
  let absorbers = [];
  let matrices = [];
  let implants = [];
  let armorsets = [];
  let armors = [];
  let armorplatings = [];
  let enhancers = [];
  let clothing = [];
  let pets = [];
  let stimulants = [];

  let entitiesLoading = true;

  let loadout = null;
  let loadouts = null;

  let picking = null;

  let compareMode = false;

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
    armorsets = (entities.armorSets || []).sort(alphabeticalSort);
    armors = (entities.armors || []).sort(alphabeticalSort);
    armorplatings = (entities.armorPlatings || []).sort(alphabeticalSort);
    enhancers = (entities.enhancers || []).sort(alphabeticalSort);
    clothing = (entities.clothings || []).sort(alphabeticalSort);
    pets = (entities.pets || []).sort(alphabeticalSort);
    stimulants = (entities.consumables || []).sort(alphabeticalSort);
  }

  onMount(async () => {
    // Load loadouts from localStorage
    if (typeof localStorage !== 'undefined') {
      loadouts = localStorage.getItem('loadouts') ? JSON.parse(localStorage.getItem('loadouts')) : [];
    }

    // Lazy load entity data
    entitiesLoading = true;
    try {
      const entities = await loadLoadoutEntities();
      processEntityData(entities);
    } catch (error) {
      console.error('Failed to load entity data:', error);
    } finally {
      entitiesLoading = false;
    }
  });

  $: if(loadout?.Gear.Weapon.Enhancers) {
    loadout.Gear.Weapon.Enhancers.Damage = clamp(loadout.Gear.Weapon.Enhancers.Damage, 0, 10);
    loadout.Gear.Weapon.Enhancers.Accuracy = clamp(loadout.Gear.Weapon.Enhancers.Accuracy, 0, 10);
    loadout.Gear.Weapon.Enhancers.Range = clamp(loadout.Gear.Weapon.Enhancers.Range, 0, 10);
    loadout.Gear.Weapon.Enhancers.Economy = clamp(loadout.Gear.Weapon.Enhancers.Economy, 0, 10);
    loadout.Gear.Weapon.Enhancers.SkillMod = clamp(loadout.Gear.Weapon.Enhancers.SkillMod, 0, 10);
  }

  $: if(loadout?.Gear.Armor.Enhancers) {
    loadout.Gear.Armor.Enhancers.Defense = clamp(loadout.Gear.Armor.Enhancers.Defense, 0, 10);
    loadout.Gear.Armor.Enhancers.Durability = clamp(loadout.Gear.Armor.Enhancers.Durability, 0, 10);
  }

  $: if (loadout && loadout.Markup == null) {
    resetMarkup();
  }

  function resetMarkup() {
    loadout.Markup = {
      Weapon: 100,
      Ammo: 100,
      Amplifier: 100,
      Absorber: 100,
      Scope: 100,
      Sight: 100,
      ScopeSight: 100,
      Matrix: 100,
      Implant: 100,
      ArmorSet: 100,
      PlateSet: 100,
      Armors: {
        Head: 100,
        Torso: 100,
        Arms: 100,
        Hands: 100,
        Legs: 100,
        Shins: 100,
        Feet: 100,
      },
      Plates: {
        Head: 100,
        Torso: 100,
        Arms: 100,
        Hands: 100,
        Legs: 100,
        Shins: 100,
        Feet: 100,
      },
    };
  }

  $: if (loadout?.Gear?.Armor?.ManageIndividual === false && loadout?.Gear?.Armor?.SetName === null) {
    resetArmor();
  } else if (loadout?.Gear?.Armor?.ManageIndividual === true) {
    loadout.Gear.Armor.SetName = null;
    loadout.Gear.Armor.PlateName = null;
  }

  $: if (loadouts !== null && typeof localStorage !== 'undefined') {
    localStorage.setItem('loadouts', JSON.stringify(loadouts));
  }

  function getTotalDamage(item) {
    return (item.Properties?.Damage?.Impact
      + item.Properties?.Damage?.Cut
      + item.Properties?.Damage?.Stab
      + item.Properties?.Damage?.Penetration
      + item.Properties?.Damage?.Shrapnel
      + item.Properties?.Damage?.Burn
      + item.Properties?.Damage?.Cold
      + item.Properties?.Damage?.Acid
      + item.Properties?.Damage?.Electric) || null;
  }

  function getEffectiveDamage(item) {
    const totalDamage = getTotalDamage(item);

    return totalDamage != null
      ? totalDamage * (0.88*0.75 + 0.02*1.75)
      : null;
  }

  function getDps(item) {
    const reload = getReload(item);
    const effectiveDamage = getEffectiveDamage(item);

    return effectiveDamage != null && reload != null
      ? effectiveDamage / reload
      : null;
  }

  function getDpp(item) {
    const cost = getCost(item);
    const effectiveDamage = getEffectiveDamage(item);

    return effectiveDamage > 0 && cost != null
      ? effectiveDamage / cost
      : null;
  }

  function getCost(item) {
    return item.Properties?.Economy?.Decay != null && (item.Properties?.Economy?.AmmoBurn == undefined || item.Properties?.Economy?.AmmoBurn >= 0)
      ? (item.Properties?.Economy?.Decay + (item.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;
  }

  function getReload(item) {
    return item.Properties?.UsesPerMinute != null
      ? 60 / item.Properties?.UsesPerMinute
      : null;
  }

  function getTotalUses(item) {
    let maxTT = item.Properties?.Economy?.MaxTT || null;
    let minTT = item.Properties?.Economy?.MinTT ?? 0;
    let decay = item.Properties?.Economy?.Decay || null;

    return maxTT != null && decay != null
      ? Math.floor((maxTT - minTT) / (decay / 100))
      : null;
  }
  
  function getTotalAbsorberUses(absorber, weapon) {
    let maxTT = absorber.Properties?.Economy?.MaxTT || null;
    let minTT = absorber.Properties?.Economy?.MinTT ?? 0;
    let decay = absorber.Properties?.Economy?.Absorption != null 
      ? weapon.Properties?.Economy?.Decay * absorber.Properties?.Economy?.Absorption
      : null;

    return maxTT != null && decay != null
      ? Math.floor((maxTT - minTT) / (decay / 100))
      : null;
  }

  function getTotalDefense(item) {
    return (item.Properties?.Defense?.Impact ?? 0) + (item.Properties?.Defense?.Cut ?? 0) + (item.Properties?.Defense?.Stab ?? 0) + (item.Properties?.Defense?.Penetration ?? 0) + (item.Properties?.Defense?.Shrapnel ?? 0) + (item.Properties?.Defense?.Burn ?? 0) + (item.Properties?.Defense?.Cold ?? 0) + (item.Properties?.Defense?.Acid ?? 0) + (item.Properties?.Defense?.Electric ?? 0);
  }

  function getMaxArmorDecay(item) {
    return item.Properties?.Economy.Durability && getTotalDefense(item)
      ? getTotalDefense(item) * ((100000 - item.Properties?.Economy.Durability) / 100000) * 0.05
      : null;
  }

  function getTotalAbsorption(item) {
    return item.Properties?.Economy.MaxTT && getMaxArmorDecay(item)
      ? getTotalDefense(item) * ((item.Properties?.Economy.MaxTT - (item.Properties?.Economy.MinTT ?? 0)) / (getMaxArmorDecay(item) / 100))
      : null;
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

  function getArmorSet(name) {
    return armorsets.find(x => x.Name === name);
  }

  function getArmor(name) {
    return armors.find(x => x.Name === name);
  }

  function getArmorPlating(name) {
    return armorplatings.find(x => x.Name === name);
  }

  function getAttachmentCount() {
    let weapon = getWeapon();

    return 3 + (weapon?.Properties?.Class === 'Ranged'
      ? 2
      : weapon?.Properties?.Class === 'Melee'
      ? 1
      : weapon?.Properties?.Class === 'Mindforce'
      ? 1
      : 0);
  }

  function clamp(value, min, max) {
    return LoadoutCalc.clamp(value, min, max);
  }

  function resetArmor() {
    const newArmorObject = () => ({
      Name: null,
      Plate: null
    });

    loadout.Gear.Armor.SetName = null;
    loadout.Gear.Armor.PlateName = null;

    armorSlots.forEach(slot => {
      loadout.Gear.Armor[slot] = newArmorObject();
    });

    loadouts = loadouts;
  }

  function clearSlot(e, slot) {
    e.preventDefault();

    if (slot === 'weapon') {
      loadout.Gear.Weapon.Name = null;
      loadout.Gear.Weapon.Amplifier = null;
      loadout.Gear.Weapon.Scope = null;
      loadout.Gear.Weapon.Sight = null;
      loadout.Gear.Weapon.Absorber = null;
      loadout.Gear.Weapon.Matrix = null;
      loadout.Gear.Weapon.Implant = null;
    } else if (slot === 'amplifier') {
      loadout.Gear.Weapon.Amplifier = null;
    } else if (slot === 'scope') {
      loadout.Gear.Weapon.Scope = null;
    } else if (slot === 'sight') {
      loadout.Gear.Weapon.Sight = null;
    } else if (slot === 'absorber') {
      loadout.Gear.Weapon.Absorber = null;
    } else if (slot === 'matrix') {
      loadout.Gear.Weapon.Matrix = null;
    } else if (slot === 'implant') {
      loadout.Gear.Weapon.Implant = null;
    } else if (slot === 'scope-sight') {
      loadout.Gear.Weapon.Scope.Sight = null;
    } else if (slot.startsWith('armor-')) {
      loadout.Gear.Armor[slot.split('-')[1]].Name = null;
      loadout.Gear.Armor[slot.split('-')[1]].Plate = null;
    } else if (slot.startsWith('armorplating-')) {
      loadout.Gear.Armor[slot.split('-')[1]].Plate = null;
    } else if (slot === 'armorplating') {
      loadout.Gear.Armor.PlateName = null;

      armorSlots.forEach(slot => {
        loadout.Gear.Armor[slot].Plate = null;
      });
    } else if (slot === 'armorset') {
      resetArmor();
    }
  }

  function getLerpProgress(start, end, current) {
    return LoadoutCalc.getLerpProgress(start, end, current);
  }

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

  function weightedAverage(weightA, valueA, weightB, valueB) {
    return LoadoutCalc.weightedAverage(weightA, valueA, weightB, valueB);
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

  function compareValue(loadout, getter, setter, newObject, valueFunction) {
    let loadoutCopy = JSON.parse(JSON.stringify(loadout));

    console.log(loadoutCopy);

    let currentValue = valueFunction(loadoutCopy);

    console.log('curr: ' + currentValue);

    if (currentValue == null) return null;

    let currentObject = getter(loadoutCopy);

    console.log(currentObject);

    setter(loadoutCopy, newObject);

    console.log(newObject);
    console.log(getter(loadoutCopy));

    let newValue = valueFunction(loadoutCopy);

    console.log('new: ' + newValue);

    if (newValue == null) return null;

    setter(loadoutCopy, currentObject);
    
    console.log(getter(loadoutCopy));

    let difference = newValue - currentValue;

    console.log('diff: ' + difference);

    return difference > 0
      ? `<span style='color: ${$darkMode ? 'lightgreen' : 'darkgreen'};'>+${difference.toFixed(2)}</span>`
      : difference < 0
      ? `<span style='color: ${$darkMode ? '#FF5555' : 'darkred'};'>${difference.toFixed(2)}</span>`
      : difference.toFixed(2);
  }

  function compareEfficiency(loadout, getter, setter, object) {
    return compareValue(loadout, getter, setter, object, calcEfficiency);
  }

  function compareDpp(loadout, getter, setter, object) {
    return compareValue(loadout, getter, setter, object, calcDpp);
  }

  function compareDps(loadout, getter, setter, object) {
    return compareValue(loadout, getter, setter, object, calcDps);
  }

  // Gets the set effects of all equipped armors
  function getArmorSetEffects(loadout) {
    if (!loadout.Gear.Armor.ManageIndividual && loadout.Gear.Armor.SetName) {
      let armorSet = getArmorSet(loadout.Gear.Armor.SetName);

      if (armorSet == null) return [];

      return armorSet.EffectsOnSetEquip;
    }
    else if (loadout.Gear.Armor.ManageIndividual) {
      let sets = [];

      armorSlots.forEach(slot => {
        let armor = getArmor(loadout.Gear.Armor[slot].Name);

        if (armor == null || armor.Set == null) return;

        sets.push(armor.Set);
      });

      return sets.filter((value, index, self) => self.indexOf(value) === index).flatMap(set => getArmorSet(set.Name).EffectsOnSetEquip);
    }
  }

  // Gets the amount of pieces equipped of a specific set
  function getArmorSetPieceCount(setName) {
    return armorSlots.reduce((acc, slot) => acc + (getArmor(loadout.Gear.Armor[slot].Name)?.Set.Name === setName ? 1 : 0), 0);
  }

  // Gets the active set effects of a specific set
  function getActiveArmorSetEffects(setName) {
    let set = getArmorSet(setName);
    let setPieceCount = getArmorSetPieceCount(setName);

    // Get unique effects with the highest piece count that is less than or equal to the current piece count
    return set.EffectsOnSetEquip
      .filter(effect => effect.MinSetPieces <= setPieceCount)
      .sort((a, b) => b.MinSetPieces - a.MinSetPieces)
      .filter((value, index, self) => self.findIndex(effect => effect.Name === value.Name) === index);
  }

  function getWeaponUseEffects(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return [];

    return [
      ...weapon.EffectsOnUse,
      ...(loadout.Gear.Weapon.Amplifier?.Name != null ? getAmplifier(loadout.Gear.Weapon.Amplifier.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Scope?.Name != null ? getScope(loadout.Gear.Weapon.Scope.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Scope?.Sight?.Name != null ? getSight(loadout.Gear.Weapon.Scope.Sight.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Sight?.Name != null ? getSight(loadout.Gear.Weapon.Sight.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Matrix?.Name != null ? getMatrix(loadout.Gear.Weapon.Matrix.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Implant?.Name != null ? getImplant(loadout.Gear.Weapon.Implant.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Absorber?.Name != null ? getAbsorber(loadout.Gear.Weapon.Absorber.Name).EffectsOnUse ?? [] : [])
    ];
  }

  function getWeaponEquipEffects(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return [];

    return [
      ...(weapon.EffectsOnEquip ?? []),
      ...(loadout.Gear.Weapon.Amplifier?.Name != null ? getAmplifier(loadout.Gear.Weapon.Amplifier.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Scope?.Name != null ? getScope(loadout.Gear.Weapon.Scope.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Scope?.Sight?.Name != null ? getSight(loadout.Gear.Weapon.Scope.Sight.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Sight?.Name != null ? getSight(loadout.Gear.Weapon.Sight.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Matrix?.Name != null ? getMatrix(loadout.Gear.Weapon.Matrix.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Implant?.Name != null ? getImplant(loadout.Gear.Weapon.Implant.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Absorber?.Name != null ? getAbsorber(loadout.Gear.Weapon.Absorber.Name).EffectsOnEquip ?? [] : [])
    ];
  }

  function getArmorEquipEffects(loadout) {
    return armorSlots.flatMap(slot => {
      let armor = getArmor(loadout.Gear.Armor[slot].Name);

      if (armor == null) return [];

      return [
        ...(armor.EffectsOnEquip ?? []),
        ...(loadout.Gear.Armor[slot].Plate?.Name != null ? getArmorPlating(loadout.Gear.Armor[slot].Plate.Name).EffectsOnEquip ?? [] : [])
      ];
    });
  }
</script>

<style>
  .loadout-list {
    display: flex;
    flex-direction: column;
    flex: 0 0 300px;
    overflow: auto;
    background-color: var(--secondary-color);
    padding: 15px;
    height: calc(100% - 32px);
    border-right: 1px solid #ccc;
  }

  .info {
    width: 100%;
    text-align: center;
    margin-top: 50px;
  }

  .flex-content {
    padding: 0;
    height: 100%;
    overflow: hidden;
  }

  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 1rem;
  }

  .loading-text {
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .loadout-manager {
    display: grid;
    grid-template-columns: 1fr 350px;
    height: 100%;
    width: 100%;
    align-self: stretch;
    overflow-x: auto;
    overflow-y: hidden;
  }

  .select {
    display: grid;
    margin-bottom: 10px;
    grid-template-columns: 0.2fr 0.2fr 0.2fr 0.2fr 0.2fr 100px 300px 80px;
    gap: 1px;
    background-color: var(--text-color);
    border: 1px solid var(--text-color);
  }

  .select:last-child, .picker:last-child {
    margin-bottom: 0;
  }

  .select div {
    display: grid;
    align-items: center;
    padding: 5px;
  }

  .gear-select {
    background-color: var(--secondary-color);
    border-right: 1px solid var(--text-color);
    padding: 10px;
    display: grid;
    grid-template-rows: min-content min-content min-content min-content min-content 1fr;
    overflow-y: auto;
  }

  .weapon-markup {
    background-color: var(--secondary-color);
  }

  .weapon-slot {
    display: grid;
    justify-content: center;
    align-items: center;
    background-color: var(--secondary-color);
    grid-column: span 4;
  }

  .armor-slot {
    display: grid;
    justify-content: center;
    align-items: center;
    background-color: var(--secondary-color);
    grid-column: span 4;
  }

  .empty-slot {
    grid-column: span 3;
    background-color: var(--primary-color);
  }

  .select-title {
    grid-column: span 5;
    background-color: var(--primary-color);
    font-size: 24px;
    padding-left: 8px;
  }

  .select-compare {
    grid-column: span 3;
    background-color: var(--primary-color);
    font-size: 18px;
    text-align: center;
  }

  .select-compare:hover {
    cursor: pointer;
    background-color: var(--hover-color);
  }

  .header-color {
    background-color: var(--table-header-color);
  }

  .even-color {
    background-color: var(--table-row-color);
  }

  .odd-color {
    background-color: var(--table-row-color-alt);
  }

  .primary-color {
    background-color: var(--primary-color);
  }

  .slot, .empty-slot {
    min-height: 31px;
  }

  .empty-slot {
    padding: 0 !important;
  }

  .slot:hover {
    cursor: pointer;
    background-color: var(--hover-color);
  }

  .slot:disabled {
    background-color: var(--disabled-color);
    cursor: not-allowed;
  }

  button.slot {
    border: none;
    padding: 5px;
    text-align: left;
    background-color: var(--primary-color);
  }

  .picker {
    border: 1px solid var(--text-color);
    height: 300px;
    overflow: hidden;
    margin-bottom: 10px;
  }

  .stat-viewer {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 1px;
    background-color: var(--text-color);
    align-self: self-start;
    border-bottom: 1px solid var(--text-color);
    overflow-y: auto;
    overflow-x: hidden;
    height: 100%;
  }

  .stat-viewer > div {
    padding: 3px;
  }

  .stat-viewer input {
    width: calc(100% - 8px);
  }
</style>

<svelte:head>
  <title>Entropia Nexus - Loadout Manager</title>
  <meta name="description" content="Tool for managing and comparing different combinations of weapons, armor, clothing, pets and pills and comparing them to each other.">
  <meta name="keywords" content="Weapon Compare, Weapon, Compare, Calculator, Loadouts, Manager, Loadout Manager, Entropia Universe, Entropia, Entropia Nexus, EU, PE, Items, Mobs, Maps, Tools, MindArk, Wiki">
  <link rel="canonical" href="https://entropianexus.com/tools/loadouts" />
</svelte:head>
<div class="flex-container">
  <div class="loadout-list centered">
    <LoadoutList
      bind:loadouts={loadouts}
      bind:currentLoadout={loadout} />
  </div>
  <div class="flex-content">
    {#if $loading || entitiesLoading}
      <div class="loading">
        <div class="spinner"></div>
        {#if entitiesLoading}
          <p class="loading-text">Loading game data...</p>
        {/if}
      </div>
    {/if}
    {#if !entitiesLoading && loadout != null}
      <div class="loadout-manager">
        <div class="gear-select">
          {#if compareMode}
          <div class="select compare-select">
            <div class="select-title">Comparing</div>
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <div class="select-compare" on:click={() => compareMode = false}>Stop Comparing</div>
            <div style="grid-column: span 8; background-color: var(--primary-color);">
              <Table
                style="height: calc(100vh - 152px); white-space: nowrap; text-overflow: ellipsis; overflow-x: auto;"
                header={{ 
                  values: [
                    'Name',
                    'DPS',
                    'Total Dmg',
                    'Effective Dmg',
                    'Reload',
                    'Range',
                    'Efficiency',
                    'Decay',
                    'Ammo',
                    'Cost',
                    'DPP',
                    'Skill Mod',
                    'Skill Bonus',
                    'Block',
                    'Tot. Defense',
                  ],
                  widths: ['1fr', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content']
                }}
                data={
                  loadouts.map(x => ({
                    values: [
                      x.Name,
                      calcDps(x) != null ? calcDps(x).toFixed(4) : null,
                      calcTotalDamage(x) != null ? calcTotalDamage(x).toFixed(2) : null,
                      calcEffectiveDamage(x) != null ? calcEffectiveDamage(x).toFixed(2) : null,
                      calcReload(x) != null ? `${calcReload(x).toFixed(2)}s` : null,
                      calcRange(x) != null ? `${calcRange(x).toFixed(2)}m` : null,
                      calcEfficiency(x) != null ? `${calcEfficiency(x).toFixed(1)}%` : null,
                      calcDecay(x) != null ? `${calcDecay(x).toFixed(2)} PEC` : null,
                      calcAmmo(x) != null ? calcAmmo(x).toFixed(2) : null,
                      calcCost(x) != null ? `${calcCost(x).toFixed(2)} PEC` : null,
                      calcDpp(x) != null ? calcDpp(x).toFixed(4) : null,
                      calcSkillModification(x) != null ? `${calcSkillModification(x).toFixed(1)}%` : null,
                      calcSkillBonus(x) != null ? `${calcSkillBonus(x).toFixed(1)}%` : null,
                      calcBlockChance(x) != null ? `${calcBlockChance(x).toFixed(1)}%` : null,
                      calcTotalDefense(x) != null ? calcTotalDefense(x).toFixed(0) : null,
                    ]
                  }))
                }
                options={{
                  searchable: true,
                  virtual: true
                }} />
            </div>
          </div>
          {:else}
            <div class="select weapon-select">
              <div class="select-title">Weapon</div>
              <!-- svelte-ignore a11y-no-static-element-interactions -->
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <div class="select-compare" on:click={() => compareMode = true}>Compare Loadouts...</div>
              <button class="slot weapon-slot" style="grid-row: span 5;" on:contextmenu={e => clearSlot(e, "weapon")} on:click={() => picking = picking === 'weapon' ? null : 'weapon'}>
                {#if loadout?.Gear.Weapon.Name != null}
                  {loadout.Gear.Weapon.Name}
                {:else}
                  <span style="color: gray;">Click here to select a weapon...</span>
                {/if}
              </button>
              <div class="weapon-markup" style="grid-row: span 5; grid-template-rows: repeat(4, 0.25fr) 34px; gap: 1px; text-align: center; padding: 0;">
                Weapon Markup
                <input type="text" size="1" bind:value={loadout.Markup.Weapon} style="margin-left: 5px; margin-right: 5px;" />
                Ammo Markup
                <input type="text" size="1" bind:value={loadout.Markup.Ammo} style="margin-left: 5px; margin-right: 5px;" />
                <button class="slot" on:click={resetMarkup} style="border-top: 1px solid var(--text-color); height: 30px; text-align: center;">Reset ALL Markup</button>
              </div>
              <div class="even-color">Amplifier:</div>
              <button class="slot amplifier-slot" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "amplifier")} on:click={() => picking = picking === 'amplifier' ? null : 'amplifier'}>
                {#if loadout?.Gear.Weapon.Name != null}
                  {#if loadout?.Gear.Weapon.Amplifier?.Name != null}
                    {loadout.Gear.Weapon.Amplifier.Name}
                  {:else}
                    <span style="color: gray;">Click here to select an amplifier...</span>
                  {/if}
                {:else}
                  <span style="color: lightgray;">Choose a weapon first!</span>
                {/if}
              </button>
              <div class="even-color"><input type="text" size="1" bind:value={loadout.Markup.Amplifier} /></div>
              <div class="odd-color">Absorber:</div>
              <button class="slot absorber-slot" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "absorber")} on:click={() => picking = picking === 'absorber' ? null : 'absorber'}>
                {#if loadout?.Gear.Weapon.Name != null}
                  {#if loadout?.Gear.Weapon.Absorber?.Name != null}
                    {loadout.Gear.Weapon.Absorber.Name}
                  {:else}
                    <span style="color: gray;">Click here to select an absorber...</span>
                  {/if}
                {:else}
                  <span style="color: lightgray;">Choose a weapon first!</span>
                {/if}
              </button>
              <div class="odd-color"><input type="text" size="1" bind:value={loadout.Markup.Absorber} /></div>
              {#if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Ranged'}
                <div class="even-color">Scope:</div>
                <button class="slot scope-slot" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "scope")} on:click={() => picking = picking === 'scope' ? null : 'scope'}>
                  {#if loadout?.Gear.Weapon.Scope?.Name != null}
                    {loadout.Gear.Weapon.Scope.Name}
                  {:else}
                  <span style="color: gray;">Click here to select a scope...</span>
                  {/if}
                </button>
                <div class="even-color"><input type="text" size="1" bind:value={loadout.Markup.Scope} /></div>
                <div class="odd-color" style="padding-left: 5px;"><span><span style="font-size: 13px">&#x21B3;</span> Sight:</span></div>
                <button class="slot scope-sight-slot" disabled={loadout?.Gear.Weapon.Scope == null} on:contextmenu={e => clearSlot(e, "scope-sight")} on:click={() => picking = picking === 'scope-sight' ? null : 'scope-sight'}>
                  {#if loadout.Gear.Weapon.Scope != null}
                    {#if loadout?.Gear.Weapon.Scope?.Sight?.Name != null}
                      {loadout.Gear.Weapon.Scope.Sight.Name}
                    {:else}
                      <span style="color: gray;">Click here to select a sight...</span>
                    {/if}
                  {:else}
                    <span style="color: lightgray;">Add a scope first!</span>
                  {/if}
                </button>
                <div class="odd-color"><input type="text" size="1" bind:value={loadout.Markup.ScopeSight} /></div>
                <div class="even-color">Sight:</div>
                <button class="slot sight-slot" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "sight")} on:click={() => picking = picking === 'sight' ? null : 'sight'}>
                  {#if loadout?.Gear.Weapon.Sight?.Name != null}
                    {loadout.Gear.Weapon.Sight.Name}
                  {:else}
                    <span style="color: gray;">Click here to select a sight...</span>
                  {/if}
                </button>
                <div class="even-color"><input type="text" size="1" bind:value={loadout.Markup.Sight} /></div>
              {:else if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Melee'}
                <div class="even-color">Matrix:</div>
                <button class="slot matrix-slot" disabled={getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class !== 'Melee'} on:contextmenu={e => clearSlot(e, "matrix")} on:click={() => picking = picking === 'matrix' ? null : 'matrix'}>
                  {#if loadout?.Gear.Weapon.Matrix?.Name != null}
                    {loadout.Gear.Weapon.Matrix.Name}
                  {:else}
                    <span style="color: gray;">Click here to select a matrix...</span>
                  {/if}
                </button>
                <div class="even-color"><input type="text" size="1" bind:value={loadout.Markup.Matrix} /></div>
                <div class="empty-slot"></div>
                <div class="empty-slot"></div>
              {:else if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Mindforce'}
                <div class="even-color">Implant:</div>
                <button class="slot implant-slot" disabled={getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class !== 'Mindforce'} on:contextmenu={e => clearSlot(e, "weapon")} on:click={() => picking = picking === 'implant' ? null : 'implant'}>
                  {#if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Mindforce'}
                    {#if loadout?.Gear.Weapon.Implant?.Name != null}
                      {loadout.Gear.Weapon.Implant.Name}
                    {:else}
                      <span style="color: gray;">Click here to select an implant...</span>
                    {/if}
                  {:else}
                  <span style="color: lightgray;">Choose a Mindforce weapon!</span>
                  {/if}
                </button>
                <div class="even-color"><input type="text" size="1" bind:value={loadout.Markup.Implant} /></div>
                <div class="empty-slot"></div>
                <div class="empty-slot"></div>
              {:else}
                <div class="empty-slot"></div>
                <div class="empty-slot"></div>
                <div class="empty-slot"></div>
              {/if}
              <div class="even-color">Damage<input type="number" min="0" max="10" bind:value={loadout.Gear.Weapon.Enhancers.Damage}></div>
              <div class="odd-color">Accuracy<input type="number" min="0" max="10" bind:value={loadout.Gear.Weapon.Enhancers.Accuracy}></div>
              <div class="even-color">Range<input type="number" min="0" max="10" bind:value={loadout.Gear.Weapon.Enhancers.Range}></div>
              <div class="odd-color">Economy<input type="number" min="0" max="10" bind:value={loadout.Gear.Weapon.Enhancers.Economy}></div>
              <div class="even-color">Skill Mod<input type="number" min="0" max="10" bind:value={loadout.Gear.Weapon.Enhancers.SkillMod}></div>
              <div class="empty-slot">
                <span>
                  <input type="checkbox" bind:checked={settings.onlyShowReasonableAmplifiers} /> Include overcapped amplifiers up to <input type="number" min="0" max="100" bind:value={settings.overampCap} />%
                </span>
              </div>
            </div>
            {#if picking === 'weapon' || picking === 'amplifier' || picking === 'absorber' || picking === 'scope' || picking === 'scope-sight' || picking === 'sight' || picking === 'matrix' || picking === 'implant'}
              <div class="picker">
                {#if picking === 'weapon'}
                  <ItemPicker 
                    items={weapons}
                    columns={['Class', 'Type', 'Efficiency', 'DPS', 'DPP', 'Min', 'Max', 'Cost', 'Total Uses']}
                    columnWidths={['80px', '80px', '80px', '60px', '60px', '60px', '60px', '75px', '90px']}
                    columnFunctions={[
                      x => x.Properties.Class,
                      x => x.Properties.Type,
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => getDps(x) != null ? getDps(x).toFixed(2) : 'N/A',
                      x => getDpp(x) != null ? getDpp(x).toFixed(2) : 'N/A',
                      x => x.Properties?.Skill?.Hit?.LearningIntervalStart != null ? x.Properties?.Skill?.Hit?.LearningIntervalStart.toFixed(1) : 'N/A',
                      x => x.Properties?.Skill?.Hit?.LearningIntervalEnd != null ? x.Properties?.Skill?.Hit?.LearningIntervalEnd.toFixed(1) : 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A',
                      x => getTotalUses(x) ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Name = e.detail.values[0];

                      loadout.Gear.Weapon.Amplifier = null;
                      loadout.Gear.Weapon.Scope = null;
                      loadout.Gear.Weapon.Sight = null;
                      loadout.Gear.Weapon.Absorber = null;
                      loadout.Gear.Weapon.Matrix = null;
                      loadout.Gear.Weapon.Implant = null;

                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking ==='amplifier'}
                  <ItemPicker 
                    items={amplifiers.filter(x => {
                      let weapon = getWeapon(loadout.Gear.Weapon.Name);
                      
                      let ampDamage = getTotalDamage(x);
                      let weaponDamage = getTotalDamage(weapon);

                      if (!ampDamage) {
                        return false;
                      }

                      if (2 * ampDamage > (1 + ((settings.overampCap ?? 0) / 100)) * weaponDamage && settings.onlyShowReasonableAmplifiers) {
                        return false;
                      }

                      if (weapon.Properties.Class === 'Ranged') {
                        if (weapon.Properties.Type === 'BLP') {
                          return x.Properties.Type === 'BLP';
                        } else {
                          return x.Properties.Type === 'Energy';
                        }
                      } else if (weapon.Properties.Class === 'Melee') {
                        return x.Properties.Type === 'Melee';
                      } else if (weapon.Properties.Class === 'Mindforce') {
                        return x.Properties.Type === 'Mindforce';
                      }

                      return false;
                    })}
                    columns={['Damage', '~DPS', 'Efficiency', '~Eff', 'DPP', '~DPP', 'Cost', 'Total Uses']}
                    columnWidths={['75px', '70px', '80px', '70px', '60px', '70px', '75px', '90px']}
                    columnFunctions={[
                      x => getTotalDamage(x) != null ? getTotalDamage(x) : 'N/A',
                      x => compareDps(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, x) ?? 'N/A',
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => compareEfficiency(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, x) ?? 'N/A',
                      x => getDpp(x) != null ? getDpp(x).toFixed(2) : 'N/A',
                      x => compareDpp(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, x) ?? 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A',
                      x => getTotalUses(x) ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Amplifier = { Name: e.detail.values[0] };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking === 'absorber'}
                  <ItemPicker
                    items={absorbers}
                    columns={['Efficiency', '~Eff', 'Absorption', 'Absorbed Decay', 'Total Uses']}
                    columnWidths={['90px', '70px', '100px', '120px', '90px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => compareEfficiency(loadout, x => x.Gear.Weapon.Absorber, (x, v) => x.Gear.Weapon.Absorber = v, x) ?? 'N/A',
                      x => x.Properties.Economy.Absorption != null ? `${(x.Properties.Economy.Absorption * 100).toFixed(1)}%` : 'N/A',
                      x => x.Properties.Economy.Absorption != null ? `${(getWeapon(loadout.Gear.Weapon.Name).Properties.Economy.Decay * x.Properties.Economy.Absorption).toFixed(4)} PEC` : 'N/A',
                      x => getTotalAbsorberUses(x, getWeapon(loadout.Gear.Weapon.Name)) ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Absorber = { Name: e.detail.values[0] };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking === 'scope'}
                  <ItemPicker
                    items={scopes}
                    columns={['Efficiency', '~Eff', '~DPP', 'Skill Mod.', 'Skill Bonus', 'Zoom', 'Cost', 'Total Uses']}
                    columnWidths={['85px', '70px', '70px', '85px', '85px', '60px', '75px', '90px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => compareEfficiency(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, x) ?? 'N/A',
                      x => compareDpp(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, x) ?? 'N/A',
                      x => x.Properties.SkillModification != null ? `${x.Properties.SkillModification.toFixed(1)}%` : 'N/A',
                      x => x.Properties.SkillBonus != null ? x.Properties.SkillBonus.toFixed(1) : 'N/A',
                      x => x.Properties.Zoom != null ? `${x.Properties.Zoom}x` : 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A',
                      x => getTotalUses(x) ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Scope = { Name: e.detail.values[0] };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking === 'scope-sight' || picking === 'sight'}
                  <ItemPicker
                    items={sights}
                    columns={['Efficiency', '~Eff', '~DPP', 'Skill Mod.', 'Skill Bonus', 'Cost', 'Total Uses']}
                    columnWidths={['85px', '70px', '70px', '85px', '85px', '75px', '90px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => compareEfficiency(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, x) ?? 'N/A',
                      x => compareDpp(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, x) ?? 'N/A',
                      x => x.Properties.SkillModification != null ? `${x.Properties.SkillModification.toFixed(1)}%` : 'N/A',
                      x => x.Properties.SkillBonus != null ? x.Properties.SkillBonus.toFixed(1) : 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A',
                      x => getTotalUses(x) ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      if (picking === 'scope-sight') {
                        loadout.Gear.Weapon.Scope.Sight = { Name: e.detail.values[0] };
                      } else {
                        loadout.Gear.Weapon.Sight = { Name: e.detail.values[0] };
                      }

                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking === 'matrix'}
                  <ItemPicker
                    items={matrices}
                    columns={['Damage', '~DPS', 'Efficiency', '~Eff', '~DPP', 'Cost', 'Total Uses']}
                    columnWidths={['75px', '70px', '85px', '70px', '70px', '75px', '90px']}
                    columnFunctions={[
                      x => getTotalDamage(x) != null ? getTotalDamage(x) : 'N/A',
                      x => compareDps(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, x) ?? 'N/A',
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => compareEfficiency(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, x) ?? 'N/A',
                      x => compareDpp(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, x) ?? 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A',
                      x => getTotalUses(x) ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Matrix = { Name: e.detail.values[0] };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking === 'implant'}
                  <ItemPicker
                    items={implants.filter(x =>
                      getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Skill?.Hit?.LearningIntervalStart <= x.Properties.MaxProfessionLevel
                      && getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Skill?.Dmg?.LearningIntervalStart <= x.Properties.MaxProfessionLevel)}
                    columns={['Efficiency', '~Eff', 'Max. Level', 'Absorption', 'Absorbed Decay', 'Total Uses']}
                    columnWidths={['80px', '70px', '85px', '90px', '120px', '90px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => compareEfficiency(loadout, x => x.Gear.Weapon.Implant, (x, v) => x.Gear.Weapon.Implant = v, x) ?? 'N/A',
                      x => x.Properties.MaxProfessionLevel != null ? x.Properties.MaxProfessionLevel : 'N/A',
                      x => x.Properties.Economy.Absorption != null ? `${(x.Properties.Economy.Absorption * 100).toFixed(1)}%` : 'N/A',
                      x => x.Properties.Economy.Absorption != null ? `${(getWeapon(loadout.Gear.Weapon.Name).Properties.Economy.Decay * x.Properties.Economy.Absorption).toFixed(4)} PEC` : 'N/A',
                      x => getTotalAbsorberUses(x, getWeapon(loadout.Gear.Weapon.Name)) ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Implant = { Name: e.detail.values[0] };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {/if}
              </div>
            {/if}
            <div class="select armor-select">
              <div class="select-title">Armor</div>
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <!-- svelte-ignore a11y-no-static-element-interactions -->
              <div class="select-compare" on:click={() => compareMode = true}>Compare Loadouts...</div>
              {#if loadout.Gear.Armor.ManageIndividual}
                {#each armorSlots as slot, index}
                  <button class="slot armor-slot" on:contextmenu={e => clearSlot(e, `armor-${slot}`)} on:click={() => picking = picking === `armor-${slot}` ? null : `armor-${slot}`}>
                    {#if loadout?.Gear.Armor[slot].Name != null}
                      {loadout.Gear.Armor[slot].Name}
                    {:else}
                      <span style="color: gray;">Click here to select a piece of armor...</span>
                    {/if}
                  </button>
                  <div class={index % 2 === 0 ? 'even-color' : 'odd-color'}><input type="text" size="1" bind:value={loadout.Markup.Armors[slot]} /></div>
                  <div class={index % 2 === 0 ? 'even-color' : 'odd-color'}>Plate:</div>
                  <button class='slot plate-slot' disabled={loadout?.Gear.Armor[slot].Name == null} on:contextmenu={e => clearSlot(e, `armorplating-${slot}`)} on:click={() => picking = picking === `armorplating-${slot}` ? null : `armorplating-${slot}`}>
                    {#if loadout?.Gear.Armor[slot].Name != null}
                      {#if loadout?.Gear.Armor[slot].Plate?.Name != null}
                        {loadout.Gear.Armor[slot].Plate.Name}
                      {:else}
                        <span style="color: gray;">Click here to select a plate...</span>
                      {/if}
                    {:else}
                      <span style="color: lightgray;">Select an armor piece first!</span>
                    {/if}
                  </button>
                  <div class={index % 2 === 0 ? 'even-color' : 'odd-color'}><input type="text" size="1" bind:value={loadout.Markup.Plates[slot]} /></div>
                {/each}
              {:else}
                <button class="slot armor-slot" on:contextmenu={e => clearSlot(e, "armorset")} on:click={() => picking = picking === 'armorset' ? null : 'armorset'}>
                  {#if loadout?.Gear.Armor.SetName != null}
                    {loadout.Gear.Armor.SetName}
                  {:else}
                    <span style="color: gray;">Click here to select an armor set...</span>
                  {/if}
                </button>
                <div class="even-color"><input type="text" size="1" bind:value={loadout.Markup.ArmorSet} /></div>
                <div class="even-color">Plate:</div>
                <button class='slot plate-slot' disabled={loadout?.Gear.Armor.SetName == null} on:contextmenu={e => clearSlot(e, "armorplating")} on:click={() => picking = picking === 'armorplating' ? null : 'armorplating'}>
                  {#if loadout?.Gear.Armor.SetName != null}
                    {#if loadout?.Gear.Armor.PlateName != null}
                      {loadout.Gear.Armor.PlateName}
                    {:else}
                      <span style="color: gray;">Click here to select a plate set...</span>
                    {/if}
                  {:else}
                    <span style="color: lightgray;">Select an armor set first!</span>
                  {/if}
                </button>
                <div class="even-color"><input type="text" size="1" bind:value={loadout.Markup.PlateSet} /></div>
              {/if}
              <div class="even-color">Defense<input type="number" min="0" max="10" bind:value={loadout.Gear.Armor.Enhancers.Defense}></div>
              <div class="odd-color">Durability<input type="number" min="0" max="10" bind:value={loadout.Gear.Armor.Enhancers.Durability}></div>
              <div class="primary-color"></div>
              <div class="primary-color"></div>
              <div class="primary-color"></div>
              <div class="empty-slot">
                <span style="text-decoration: underline dotted;" title="If enabled, you can use incomplete/mixed sets of both armor and plates.">
                  <input type="checkbox" bind:checked={loadout.Gear.Armor.ManageIndividual} /> Manage armor pieces individually
                </span>
              </div>
            </div>
            {#if picking != null && picking.startsWith('armor')}
              <div class="picker">
                {#if picking === 'armorset'}
                  <ItemPicker
                    items={armorsets}
                    columns={['Stb', 'Cut', 'Imp', 'Pen', 'Shr', 'Brn', 'Cld', 'Acd', 'Ele', 'Total', 'Durability']}
                    columnWidths={['50px', '50px', '50px', '50px', '50px', '50px', '50px', '50px', '50px', '60px', '90px']}
                    columnFunctions={[
                      x => x.Properties.Defense.Stab ?? 'N/A',
                      x => x.Properties.Defense.Cut ?? 'N/A',
                      x => x.Properties.Defense.Impact ?? 'N/A',
                      x => x.Properties.Defense.Penetration ?? 'N/A',
                      x => x.Properties.Defense.Shrapnel ?? 'N/A',
                      x => x.Properties.Defense.Burn ?? 'N/A',
                      x => x.Properties.Defense.Cold ?? 'N/A',
                      x => x.Properties.Defense.Acid ?? 'N/A',
                      x => x.Properties.Defense.Electric ?? 'N/A',
                      x => getTotalDefense(x) ?? 'N/A',
                      x => x.Properties.Economy.Durability ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      let armorSet = armorsets.find(x => x.Name === e.detail.values[0]);

                      loadout.Gear.Armor.SetName = armorSet.Name;

                      armorSlots.forEach(slot => {
                        loadout.Gear.Armor[slot] = { Name: armorSet.Armors.flat().find(x => slot == x.Properties.Slot)?.Name, Plate: loadout.Gear.Armor[slot].Plate };
                      });

                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking.startsWith('armor-')}
                  <ItemPicker
                    items={armors.filter(x => x.Properties.Slot === picking.split('-')[1])}
                    columns={['Stb', 'Cut', 'Imp', 'Pen', 'Shr', 'Brn', 'Cld', 'Acd', 'Ele', 'Total', 'Durability']}
                    columnWidths={['50px', '50px', '50px', '50px', '50px', '50px', '50px', '50px', '50px', '60px', '90px']}
                    columnFunctions={[
                      x => x.Properties.Defense.Stab ?? 'N/A',
                      x => x.Properties.Defense.Cut ?? 'N/A',
                      x => x.Properties.Defense.Impact ?? 'N/A',
                      x => x.Properties.Defense.Penetration ?? 'N/A',
                      x => x.Properties.Defense.Shrapnel ?? 'N/A',
                      x => x.Properties.Defense.Burn ?? 'N/A',
                      x => x.Properties.Defense.Cold ?? 'N/A',
                      x => x.Properties.Defense.Acid ?? 'N/A',
                      x => x.Properties.Defense.Electric ?? 'N/A',
                      x => getTotalDefense(x) ?? 'N/A',
                      x => x.Properties.Economy.Durability ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Armor[picking.split('-')[1]] = { Name: e.detail.values[0], Plate: loadout.Gear.Armor[picking.split('-')[1]].Plate };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking.startsWith('armorplating')}
                  <ItemPicker
                    items={armorplatings}
                    columns={['Stb', 'Cut', 'Imp', 'Pen', 'Shr', 'Brn', 'Cld', 'Acd', 'Ele', 'Total', 'Durability']}
                    columnWidths={['50px', '50px', '50px', '50px', '50px', '50px', '50px', '50px', '50px', '60px', '90px']}
                    columnFunctions={[
                      x => x.Properties.Defense.Stab ?? 'N/A',
                      x => x.Properties.Defense.Cut ?? 'N/A',
                      x => x.Properties.Defense.Impact ?? 'N/A',
                      x => x.Properties.Defense.Penetration ?? 'N/A',
                      x => x.Properties.Defense.Shrapnel ?? 'N/A',
                      x => x.Properties.Defense.Burn ?? 'N/A',
                      x => x.Properties.Defense.Cold ?? 'N/A',
                      x => x.Properties.Defense.Acid ?? 'N/A',
                      x => x.Properties.Defense.Electric ?? 'N/A',
                      x => getTotalDefense(x) ?? 'N/A',
                      x => x.Properties.Economy.Durability ?? 'N/A'
                    ]}
                    on:rowClick={e => {
                      if (loadout.Gear.Armor.ManageIndividual) {
                        if (loadout.Gear.Armor[picking.split('-')[1]].Name === null) {
                          return;
                        }
                          
                        loadout.Gear.Armor[picking.split('-')[1]].Plate = { Name: e.detail.values[0] };
                      } else {
                        loadout.Gear.Armor.PlateName = e.detail.values[0];

                        armorSlots.forEach(slot => {
                          if (loadout.Gear.Armor[slot].Name === null) {
                            return;
                          }

                          loadout.Gear.Armor[slot].Plate = { Name: e.detail.values[0] };
                        });
                      }

                      loadouts = loadouts;
                      picking = null;
                    }} />
                {/if}
              </div>
            {/if}
            <!--
            <div class="select effect-select">
              <div class="select-title">Effects</div>
              <div class="select-compare" on:click={() => compareMode = true}>Compare Loadouts...</div>
            </div>
            -->
          {/if}
        </div>
        <div class="stat-viewer">
          {#if loadout}
          <div style="grid-column: span 2; text-align: center; font-size: 24px; padding: 5px;" class="header-color">Offense</div>
          <div class="row-color">Total Damage</div><div class="row-color">{calcTotalDamage(loadout) != null ? `${calcTotalDamage(loadout).toFixed(2)}` : 'N/A'}</div>
          <div class="row-color-alt">Range</div><div class="row-color-alt">{calcRange(loadout) != null ? `${calcRange(loadout).toFixed(1)}m` : 'N/A'}</div>
          <div class="row-color">Critical Chance</div><div class="row-color">{calcCritChance(loadout) != null ? `${(calcCritChance(loadout)*100).toFixed(1)}%` : 'N/A'}</div>
          <div class="row-color-alt">Critical Damage</div><div class="row-color-alt">{calcCritDamage(loadout) != null ? `${(calcCritDamage(loadout)*100).toFixed(0)}%` : 'N/A'}</div>
          <div class="row-color">Effective Damage</div><div class="row-color">{calcEffectiveDamage(loadout) != null ? `${calcEffectiveDamage(loadout).toFixed(2)}` : 'N/A'}</div>
          <div class="row-color-alt">Reload</div><div class="row-color-alt">{calcReload(loadout) != null ? `${calcReload(loadout).toFixed(2)}s` : 'N/A'}</div>
          <div class="row-color">Uses/min</div><div class="row-color">{calcReload(loadout) != null ? `${clampDecimals(60 / calcReload(loadout), 0, 2)}` : 'N/A'}</div>
          <div class="row-color-alt">DPS</div><div class="row-color-alt">{calcDps(loadout) != null ? `${calcDps(loadout).toFixed(4)}` : 'N/A'}</div>
          <div style="grid-column: span 2; text-align: center; font-size: 16px; padding: 3px;" class="header-color">Economy</div>
          <div class="row-color">Efficiency</div><div class="row-color">{calcEfficiency(loadout) != null ? `${calcEfficiency(loadout).toFixed(1)}%` : 'N/A'}</div>
          <div class="row-color-alt">Decay</div><div class="row-color-alt">{calcDecay(loadout) != null ? `${calcDecay(loadout).toFixed(4)} PEC` : 'N/A'}</div>
          <div class="row-color">Ammo</div><div class="row-color">{calcAmmo(loadout) != null ? Math.round(calcAmmo(loadout)) : 'N/A'}</div>
          <div class="row-color-alt">Cost</div><div class="row-color-alt">{calcCost(loadout) != null ? `${calcCost(loadout).toFixed(4)} PEC` : 'N/A'}</div>
          <div class="row-color">DPP</div><div class="row-color">{calcDpp(loadout) != null ? `${calcDpp(loadout).toFixed(4)}` : 'N/A'}</div>
          <div class="row-color-alt">Total Uses</div><div class="row-color-alt">{calcLowestTotalUses(loadout) != null ? calcLowestTotalUses(loadout) : 'N/A'}</div>
          <div style="grid-column: span 2; text-align: center; font-size: 24px; padding: 5px;" class="header-color">Defense</div>
          <div class="row-color">Armor Defense</div><div class="row-color">{calcArmorDefense(loadout) != null ? calcArmorDefense(loadout).toFixed(2) : 'N/A'}</div>
          <div class="row-color-alt">Plate Defense</div><div class="row-color-alt">{calcPlateDefense(loadout) != null ? calcPlateDefense(loadout).toFixed(2) : 'N/A'}</div>
          <div class="row-color">Total Defense</div><div class="row-color">{calcTotalDefense(loadout) != null ? calcTotalDefense(loadout).toFixed(2) : 'N/A'}</div>
          <div class="row-color-alt">Block</div><div class="row-color-alt">{calcBlockChance(loadout) != null ? `${(calcBlockChance(loadout)).toFixed(1)}%` : 'N/A'}</div>
          <div style="grid-column: span 2; text-align: center; font-size: 16px; padding: 3px;" class="header-color">Economy</div>
          <div class="row-color">Armor Durability</div><div class="row-color">{calcArmorDurability(loadout) != null ? calcArmorDurability(loadout) : 'N/A'}</div>
          <div class="row-color-alt">Plate Durability</div><div class="row-color-alt">{calcPlateDurability(loadout) != null ? calcPlateDurability(loadout) : 'N/A'}</div>
          <div class="row-color">Total Absorption</div><div class="row-color">{calcTotalAbsorption(loadout) != null ? `${calcTotalAbsorption(loadout).toFixed(0)} HP` : 'N/A'}</div>
          <div style="grid-column: span 2; text-align: center; font-size: 24px; padding: 5px;" class="header-color">Skill</div>
          <div class="row-color">Hit Ability</div><div class="row-color">{calcHitAbility(loadout) != null ? `${calcHitAbility(loadout).toFixed(1)}/10.0` : 'N/A'}</div>
          <div class="row-color-alt">Crit Ability</div><div class="row-color-alt">{calcCritAbility(loadout) != null ? `${calcCritAbility(loadout).toFixed(1)}/10.0` : 'N/A'}</div>
          <div class="row-color">Skill Modification</div><div class="row-color">{calcSkillModification(loadout) != null ? `${calcSkillModification(loadout).toFixed(1)}%` : 'N/A'}</div>
          <div class="row-color-alt">Skill Bonus</div><div class="row-color-alt">{calcSkillBonus(loadout) != null ? `${calcSkillBonus(loadout).toFixed(1)}%` : 'N/A'}</div>
          <div style="grid-column: span 2; text-align: center; font-size: 24px; padding: 5px;" class="header-color">Settings</div>
          <div class="row-color">Name</div><div class="row-color"><input type="text" bind:value={loadout.Name} /></div>
          <div class="row-color-alt">Hit Profession</div><div class="row-color-alt"><input type="number" bind:value={loadout.Skill.Hit} /></div>
          <div class="row-color">Dmg Profession</div><div class="row-color"><input type="number" bind:value={loadout.Skill.Dmg} /></div>
          <div class="row-color-alt">% Damage</div><div class="row-color-alt"><input type="number" bind:value={loadout.Properties.BonusDamage} /></div>
          <div class="row-color">% Crit Chance</div><div class="row-color"><input type="number" bind:value={loadout.Properties.BonusCritChance} /></div>
          <div class="row-color-alt">% Crit Damage</div><div class="row-color-alt"><input type="number" bind:value={loadout.Properties.BonusCritDamage} /></div>
          <div class="row-color">% Reload</div><div class="row-color"><input type="number" bind:value={loadout.Properties.BonusReload} /></div>
          {/if}
        </div>
      </div>
    {:else if data?.error != null}
      <div class="info error"><h2>{data?.error?.status}</h2><br />{data?.error?.message}</div>
    {:else}
      <div class="info">
        <h1>Loadout Manager</h1>
        <br />
        <p>Create or select an existing loadout on the left!</p>
        <br />
        <p style="text-align: left; margin-left: 100px; margin-right: 100px; width: 100%;">
          Instructions:<br />
          <br />
          - <b>Click "Add"</b> to get started.<br />
          - <b>Left-click</b> to select gear.<br />
          - <b>Right-click</b> to clear the slot.<br />
          - <b>Bottom-right</b> are settings for name and simulating profession levels and buffs.<br />
          - <b>Compare</b> by clicking the button at the top right.<br />
          <br />
          Your loadouts will persist until you clear your browser cache. If you want to avoid losing them, you can export them to a file and import them later.
        </p>
      </div>
    {/if}
  </div>
</div>