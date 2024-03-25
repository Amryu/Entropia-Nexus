<script>
  // @ts-nocheck
  import '$lib/style.css';

  import { onMount } from 'svelte';

  import ItemPicker from '$lib/components/ItemPicker.svelte';
  import LoadoutList from '$lib/components/LoadoutList.svelte';
  import { loading } from '../../../stores.js';
  import Table from '$lib/components/Table.svelte';

  export let data;

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];

  let settings = {
    onlyShowReasonableAmplifiers: true
  }

  let weapons;
  let amplifiers;
  let scopes;
  let sights;
  let absorbers;
  let matrices;
  let implants;
  let armorsets;
  let armors;
  let armorplatings;
  let enhancers;
  let clothing;
  let pets;
  let consumables;

  let loadout = null;
  let loadouts = null;

  let picking = null;

  let compareMode = false;

  function alphabeticalSort(a, b) {
    if (a?.Name === null) return 1;
    if (b?.Name === null) return -1;

    return a.Name.localeCompare(b.Name, undefined, { numeric: true });
  }

  $: if(data && data.additional) {
    weapons = data.additional.weapons.filter(x => x.Properties.Class !== 'Attached' && x.Properties.Class !== 'Stationary').sort(alphabeticalSort);
    amplifiers = data.additional.weaponamplifiers.filter(x => x.Properties.Type !== 'Matrix').sort(alphabeticalSort);
    scopes = data.additional.weaponvisionattachments.filter(x => x.Properties.Type === 'Scope').sort(alphabeticalSort);
    sights = data.additional.weaponvisionattachments.filter(x => x.Properties.Type === 'Sight').sort(alphabeticalSort);
    absorbers = data.additional.absorbers.sort(alphabeticalSort);
    matrices = data.additional.weaponamplifiers.filter(x => x.Properties.Type === 'Matrix').sort(alphabeticalSort);
    implants = data.additional.mindforceimplants.sort(alphabeticalSort);
    armorsets = data.additional.armorsets.sort(alphabeticalSort);
    armors = data.additional.armors.sort(alphabeticalSort);
    armorplatings = data.additional.armorplatings.sort(alphabeticalSort);
    enhancers = data.additional.enhancers.sort(alphabeticalSort);
    clothing = data.additional.clothing.sort(alphabeticalSort);
    pets = data.additional.pets.sort(alphabeticalSort);
    consumables = data.additional.consumables.sort(alphabeticalSort);
  }

  onMount(() => {
    if (typeof localStorage === 'undefined') return;

    loadouts = localStorage.getItem('loadouts') ? JSON.parse(localStorage.getItem('loadouts')) : [];
  });

  function getTotalWeaponEnhancersCount() {
    return weaponEnhancersDamage + weaponEnhancersAccuracy + weaponEnhancersRange + weaponEnhancersEconomy + weaponEnhancersSkillMod;
  }

  function getTotalArmorEnhancersCount() {
    return armorEnhancersDefense + armorEnhancersDurability;
  }

  function clampWeaponEnhancers(value) {
    let total = getTotalWeaponEnhancersCount();

    if (total > 10) {
      return 10 - (total - value);
    }

    return value;
  }

  function clampArmorEnhancers(value) {
    let total = getTotalArmorEnhancersCount();

    if (total > 10) {
      return 10 - (total - value);
    }

    return value;
  }

  let weaponEnhancersDamage = 0;
  let weaponEnhancersAccuracy = 0;
  let weaponEnhancersRange = 0;
  let weaponEnhancersEconomy = 0;
  let weaponEnhancersSkillMod = 0;

  let armorEnhancersDefense = 0;
  let armorEnhancersDurability = 0;

  function setEnhancers(loadout) {
    weaponEnhancersDamage = loadout.Gear.Weapon?.Enhancers.Damage;
    weaponEnhancersAccuracy = loadout.Gear.Weapon?.Enhancers.Accuracy;
    weaponEnhancersRange = loadout.Gear.Weapon?.Enhancers.Range;
    weaponEnhancersEconomy = loadout.Gear.Weapon?.Enhancers.Economy;
    weaponEnhancersSkillMod = loadout.Gear.Weapon?.Enhancers.SkillMod;

    armorEnhancersDefense = loadout.Gear.Armor?.Enhancers.Defense;
    armorEnhancersDurability = loadout.Gear.Armor?.Enhancers.Durability;
  }

  $: if (loadout) setEnhancers(loadout);

  function updateWeaponEnhancersDamage(value) {
    if (loadout == null) return;

    weaponEnhancersDamage = clampWeaponEnhancers(value);
    loadout.Gear.Weapon.Enhancers.Damage = weaponEnhancersDamage;

    loadouts = loadouts;
  }
  $: updateWeaponEnhancersDamage(weaponEnhancersDamage);
  function updateWeaponEnhancersAccuracy(value) {
    if (loadout == null) return;

    weaponEnhancersAccuracy = clampWeaponEnhancers(value);
    loadout.Gear.Weapon.Enhancers.Damage = weaponEnhancersAccuracy;

    loadouts = loadouts;
  }
  $: updateWeaponEnhancersAccuracy(weaponEnhancersAccuracy);
  function updateWeaponEnhancersRange(value) {
    if (loadout == null) return;

    weaponEnhancersRange = clampWeaponEnhancers(value);
    loadout.Gear.Weapon.Enhancers.Damage = weaponEnhancersRange;

    loadouts = loadouts;
  }
  $: updateWeaponEnhancersRange(weaponEnhancersRange);
  function updateWeaponEnhancersEconomy(value) {
    if (loadout == null) return;

    weaponEnhancersEconomy = clampWeaponEnhancers(value);
    loadout.Gear.Weapon.Enhancers.Damage = weaponEnhancersEconomy;

    loadouts = loadouts;
  }
  $: updateWeaponEnhancersEconomy(weaponEnhancersEconomy);
  function updateWeaponEnhancersSkillMod(value) {
    if (loadout == null) return;

    weaponEnhancersSkillMod = clampWeaponEnhancers(value);
    loadout.Gear.Weapon.Enhancers.Damage = weaponEnhancersSkillMod;

    loadouts = loadouts;
  }
  $: updateWeaponEnhancersSkillMod(weaponEnhancersSkillMod);

  function updateArmorEnhancersDefense(value) {
    if (loadout == null) return;

    armorEnhancersDefense = clampArmorEnhancers(value);
    loadout.Gear.Armor.Enhancers.Defense = armorEnhancersDefense;

    loadouts = loadouts;
  }
  $: updateArmorEnhancersDefense(armorEnhancersDefense);
  function updateArmorEnhancersDurability(value) {
    if (loadout == null) return;

    armorEnhancersDurability = clampArmorEnhancers(value);
    loadout.Gear.Armor.Enhancers.Durability = armorEnhancersDurability;

    loadouts = loadouts;
  }
  $: updateArmorEnhancersDurability(armorEnhancersDurability);

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
    return item.Properties?.Economy?.Decay != null && item.Properties?.Economy?.AmmoBurn >= 0
      ? (item.Properties?.Economy?.Decay + (item.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;
  }

  function getReload(item) {
    return item.Properties?.UsesPerMinute != null
      ? 60 / item.Properties?.UsesPerMinute
      : null;
  }

  function getTotalUses(item) {
    let maxTT = item.Properties?.Economy?.MaxTT ?? null;
    let minTT = item.Properties?.Economy?.MinTT ?? 0;
    let decay = item.Properties?.Economy?.Decay ?? null;

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

  let propertiesDataFunction = (weapon, additional) => {
    let cost = getCost(weapon);
    let totalDamage = getTotalDamage(weapon);
    let effectiveDamage = getEffectiveDamage(weapon);
    let reload = getReload(weapon);

    let totalUses = getTotalUses(weapon);
    let cyclePerRepair = totalUses * (cost / 100);
    let cyclePerHour = (3600 / reload) * (cost / 100);

    return {
    }
  };

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
    return Math.min(Math.max(value, min), max);
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
    // Just a hack to avoid making fully maxed weapons unusable just because we don't know the max value
    if (start == null || end == null) return 1;

    return clamp((current - start) / (end - start), 0, 1);
  }

  function calcTotalDamage(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    let baseDamage = getTotalDamage(weapon);

    let totalDamage = baseDamage;

    totalDamage *= 1 + (weaponEnhancersDamage * 0.1);

    let amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);

    if (amplifier != null) {
      totalDamage += Math.min(baseDamage / 2, getTotalDamage(amplifier));
    }

    return totalDamage * (1 + (loadout?.Properties?.BonusDamage ?? 0) / 100);
  }

  function calcEffectiveDamage(loadout) {
    if (loadout.Gear.Weapon.Name == null) return null;

    let critChance = calcCritChance(loadout);
    let critDamage = calcCritDamage(loadout);
    let hitAbility = calcHitAbility(loadout);
    let damageInterval = calcDamageInterval(loadout);
    
    let averageDamage = (damageInterval.min + damageInterval.max) / 2;
    let hitChance = 0.8 + (hitAbility / 100);

    return averageDamage * (hitChance - critChance) + (averageDamage + critDamage * damageInterval.max) * critChance;
  }

  function calcDamageInterval(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    let totalDamage = calcTotalDamage(loadout);

    if (weapon.Properties.Skill.IsSiB) {
      let progress = getLerpProgress(weapon.Properties.Skill.Dmg.LearningIntervalStart, weapon.Properties.Skill.Dmg.LearningIntervalEnd, loadout.Skill.Dmg);

      return { 
        min: totalDamage * 0.25 * (1 + progress),
        max: totalDamage * 0.5 * (1 + progress)
      };
    }
    else {
      return { 
        min: totalDamage * 0.25 + (totalDamage * 0.25 * Math.min(loadout.Skill.Dmg / 100, 1)),
        max: totalDamage
      };
    }
  }

  function calcHitAbility(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    if (weapon.Properties.Skill.IsSiB) {
      if (loadout.Skill.Hit < weapon.Properties.Skill.Hit.LearningIntervalStart) {
        return 0;
      }

      let progress = getLerpProgress(weapon.Properties.Skill.Hit.LearningIntervalStart, weapon.Properties.Skill.Hit.LearningIntervalEnd, loadout.Skill.Hit);

      return clamp(3 + 7 * progress, 0, 10);
    }
    else {
      return clamp(4 + 6 * (loadout.Skill.Hit / 100), 0, 10);
    }
  }

  function calcCritChance(loadout) {
    let critAbility = calcCritAbility(loadout);
    
    return 0.01 + (critAbility / 1000) + weaponEnhancersAccuracy * 0.002 + ((loadout?.Properties?.BonusCritChance ?? 0) / 100);
  }

  function calcCritAbility(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    if (weapon.Properties.Skill.IsSiB) {
      let progress = getLerpProgress(weapon.Properties.Skill.Hit.LearningIntervalStart, weapon.Properties.Skill.Hit.LearningIntervalEnd, loadout.Skill.Hit);

      return clamp(Math.sqrt(progress * 100), 0, 10);
    }
    else {
      return clamp(Math.min(10, Math.sqrt(loadout.Skill.Hit)), 0, 10);
    }
  }

  function calcCritDamage(loadout) {
    return 1 + ((loadout?.Properties?.BonusCritDamage ?? 0) / 100);
  }

  function calcRange(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    let rangeEnhancerFactor = 1 + weaponEnhancersRange * 0.05;

    if (weapon.Properties.Class === 'Melee') {
      return weapon.Properties.Range * rangeEnhancerFactor;
    }

    if (loadout.Skill.Hit < weapon.Properties.Skill.Hit.LearningIntervalStart) {
      return weapon.Properties.Range * 10/11 * rangeEnhancerFactor;
    }

    if (weapon.Properties.Skill.IsSiB) {
      let progress = getLerpProgress(weapon.Properties.Skill.Hit.LearningIntervalStart, weapon.Properties.Skill.Hit.LearningIntervalEnd, loadout.Skill.Hit);

      return weapon.Properties.Range * (0.935 + 0.065 * progress) * rangeEnhancerFactor;
    }
    else {
      return weapon.Properties.Range * (0.945 + 0.055 * (loadout.Skill.Hit / 100)) * rangeEnhancerFactor;
    }
  }

  function calcDecay(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    let decay = weapon.Properties.Economy.Decay * (1 + weaponEnhancersDamage * 0.1) / (1 + weaponEnhancersEconomy * 0.0108);

    if (loadout.Gear.Weapon.Amplifier?.Name != null) {
      let amp = getAmplifier(loadout.Gear.Weapon.Amplifier.Name);
      
      decay += amp.Properties.Economy.Decay;
    }

    if (loadout.Gear.Weapon.Scope?.Name != null) {
      let scope = getScope(loadout.Gear.Weapon.Scope.Name);

      decay += scope.Properties.Economy.Decay;
    }

    if (loadout.Gear.Weapon.Scope?.Sight?.Name != null) {
      let scopeSight = getSight(loadout.Gear.Weapon.Scope.Sight.Name);

      decay += scopeSight.Properties.Economy.Decay;
    }

    if (loadout.Gear.Weapon.Sight?.Name != null) {
      let sight = getSight(loadout.Gear.Weapon.Sight.Name);

      decay += sight.Properties.Economy.Decay;
    }

    if (loadout.Gear.Weapon.Matrix?.Name != null) {
      let matrix = getMatrix(loadout.Gear.Weapon.Matrix.Name);

      decay += matrix.Properties.Economy.Decay;
    }

    return decay;
  }

  function calcAmmo(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    let ammoBurn = weapon.Properties.Economy.AmmoBurn * (1 + weaponEnhancersDamage * 0.1) / (1 + weaponEnhancersEconomy * 0.0108);

    if (loadout.Gear.Weapon.Amplifier?.Name != null) {
      let amp = getAmplifier(loadout.Gear.Weapon.Amplifier.Name);
      
      ammoBurn += amp.Properties.Economy.AmmoBurn;
    }

    return ammoBurn;
  }

  function calcCost(loadout) {
    return calcDecay(loadout) + calcAmmo(loadout) / 100;
  }

  function calcDpp(loadout) {
    let effectiveDamage = calcEffectiveDamage(loadout);
    let cost = calcCost(loadout);

    return effectiveDamage && cost
      ? effectiveDamage / cost
      : null;
  }

  function calcReload(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    let bonusFactor = 1/(1 + (loadout?.Properties?.BonusReload ?? 0) / 100);

    if (weapon == null) return null;

    if (!weapon.Properties.Skill.IsSiB) {
      return (60 / weapon.Properties.UsesPerMinute) * bonusFactor;
    }

    if (loadout.Skill.Hit < weapon.Properties.Skill.Hit.LearningIntervalStart) {
      return (60 / (weapon.Properties.UsesPerMinute * 0.45)) * bonusFactor;
    }
    else {
      let intervalSize = weapon.Properties.Skill.Hit.LearningIntervalEnd - weapon.Properties.Skill.Hit.LearningIntervalStart;
      let scalingRange = intervalSize * 1.25;

      let progress = getLerpProgress(weapon.Properties.Skill.Hit.LearningIntervalStart, weapon.Properties.Skill.Hit.LearningIntervalEnd + scalingRange, loadout.Skill.Hit);

      return (60 / (weapon.Properties.UsesPerMinute * 0.8 + weapon.Properties.UsesPerMinute * 0.2 * progress)) * bonusFactor;
    }
  }

  function calcDps(loadout) {
    let effectiveDamage = calcEffectiveDamage(loadout);
    let reload = calcReload(loadout);

    return effectiveDamage && reload
      ? effectiveDamage / reload
      : null;
  }

  function calcWeaponCost(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    let cost = getCost(weapon);

    cost *= (1 + weaponEnhancersDamage * 0.1) / (1 + weaponEnhancersEconomy * 0.0108);

    return cost;
  }

  function calcEfficiency(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return null;

    let cost = calcWeaponCost(loadout);
    let efficiency = weapon.Properties.Economy.Efficiency;

    if (loadout.Gear.Weapon.Absorber?.Name != null) {
      let absorber = getAbsorber(loadout.Gear.Weapon.Absorber.Name);

      let absorberCost = cost * absorber.Properties.Economy.Absorption;
      cost -= absorberCost;
      efficiency = weightedAverage(cost, efficiency, absorberCost, absorber.Properties.Economy.Efficiency);

      cost += absorberCost;
    }

    if (loadout.Gear.Weapon.Implant?.Name != null) {
      let implant = getImplant(loadout.Gear.Weapon.Implant.Name);

      let implantCost = cost * implant.Properties.Economy.Absorption;
      cost -= implantCost;
      efficiency = weightedAverage(cost, efficiency, implantCost, implant.Properties.Economy.Efficiency);

      cost += implantCost;
    }

    if (loadout.Gear.Weapon.Amplifier?.Name != null) {
      let amp = getAmplifier(loadout.Gear.Weapon.Amplifier.Name);
      let ampCost = getCost(amp);

      efficiency = weightedAverage(cost, efficiency, ampCost, amp.Properties.Economy.Efficiency);
      cost += ampCost;
    }

    if (loadout.Gear.Weapon.Scope?.Name != null) {
      let scope = getScope(loadout.Gear.Weapon.Scope.Name);
      let scopeCost = getCost(scope);

      efficiency = weightedAverage(cost, efficiency, scopeCost, scope.Properties.Economy.Efficiency);
      cost += scopeCost;
    }

    if (loadout.Gear.Weapon.Scope?.Sight?.Name != null) {
      let scopeSight = getSight(loadout.Gear.Weapon.Scope.Sight.Name);
      let scopeSightCost = getCost(scopeSight);

      efficiency = weightedAverage(cost, efficiency, scopeSightCost, scopeSight.Properties.Economy.Efficiency);
      cost += scopeSightCost;
    }

    if (loadout.Gear.Weapon.Sight?.Name != null) {
      let sight = getSight(loadout.Gear.Weapon.Sight.Name);
      let sightCost = getCost(sight);

      efficiency = weightedAverage(cost, efficiency, sightCost, sight.Properties.Economy.Efficiency);
      cost += sightCost;
    }

    if (loadout.Gear.Weapon.Matrix?.Name != null) {
      let matrix = getMatrix(loadout.Gear.Weapon.Matrix.Name);
      let matrixCost = getCost(matrix);

      efficiency = weightedAverage(cost, efficiency, matrixCost, matrix.Properties.Economy.Efficiency);
      cost += matrixCost;
    }

    return efficiency;
  }

  function weightedAverage(weightA, valueA, weightB, valueB) {
    return (valueA * weightA + valueB * weightB) / (weightA + weightB);
  }

  function calcArmorDefense(loadout) {
    let totalDefense = 0;

    armorSlots.forEach(slot => {
      let armor = getArmor(loadout.Gear.Armor[slot].Name);

      if (armor == null) return;

      totalDefense = totalDefense === 0
        ? getTotalDefense(armor)
        : (totalDefense + getTotalDefense(armor)) / 2;
    });

    totalDefense *= 1 + (armorEnhancersDefense * 0.05);

    return totalDefense;
  }

  function calcPlateDefense(loadout) {
    let totalDefense = 0;

    armorSlots.forEach(slot => {
      let plate = getArmorPlating(loadout.Gear.Armor[slot].Plate);

      if (plate == null) return;

      totalDefense = totalDefense === 0
        ? getTotalDefense(armor)
        : (totalDefense + getTotalDefense(plate)) / 2;
    });

    return totalDefense;
  }

  function calcTotalDefense(loadout) {
    return calcArmorDefense(loadout) + calcPlateDefense(loadout);
  }

  function calcArmorDurability(loadout) {
    let totalDurability = 0;

    armorSlots.forEach(slot => {
      let armor = getArmor(loadout.Gear.Armor[slot].Name);

      if (armor == null) return;

      totalDurability = totalDurability === 0
        ? armor.Properties.Economy.Durability
        : (totalDurability + armor.Properties.Economy.Durability) / 2;
    });

    totalDurability *= 1 + (armorEnhancersDurability * 0.05);

    return totalDurability || null;
  }

  function calcPlateDurability(loadout) {
    let totalDurability = 0;

    armorSlots.forEach(slot => {
      let plate = getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name);

      if (plate == null) return;

      totalDurability = totalDurability === 0
        ? plate.Properties.Economy.Durability
        : (totalDurability + plate.Properties.Economy.Durability) / 2;
    });

    return totalDurability || null;
  }

  function calcTotalAbsorption(loadout) {
    let totalAbsorption = 0;

    armorSlots.forEach(slot => {
      let armor = getArmor(loadout.Gear.Armor[slot].Name);

      if (armor == null) return;

      let totalDefense = (getTotalDefense(armor)) * (1 + armorEnhancersDefense * 0.05);
      let durability = armor.Properties?.Economy.Durability * (1 + armorEnhancersDurability * 0.1);

      let maxDecay = totalDefense * ((100000 - durability) / 100000) * 0.05
      totalAbsorption += totalDefense * ((armor.Properties?.Economy.MaxTT - (armor.Properties?.Economy.MinTT ?? 0)) / (maxDecay / 100));
    });

    armorSlots.forEach(slot => {
      let plate = getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name);

      if (plate == null) return;

      let totalDefense = getTotalDefense(plate);

      let maxDecay = totalDefense * ((100000 - plate.Properties?.Economy.Durability) / 100000) * 0.05
      totalAbsorption += totalDefense * ((plate.Properties?.Economy.MaxTT - (plate.Properties?.Economy.MinTT ?? 0)) / (maxDecay / 100));
    });

    return totalAbsorption
  }

  function calcBlockChance(loadout) {
    let blockChance = 0;

    armorSlots.forEach(slot => {
      let plate = getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name);

      if (plate == null) return;

      blockChance = blockChance === 0
        ? plate.Properties.Defense.Block ?? 0
        : (blockChance + plate.Properties.Defense.Block ?? 0) / 2;
    });

    return blockChance || null;
  }

  function calcSkillModification(loadout) {
    let skillMod = 0;

    if (loadout.Gear.Weapon?.Scope?.Name != null) {
      let scope = getScope(loadout.Gear.Weapon.Scope.Name);

      skillMod += scope.Properties.SkillModification;
    }

    if (loadout.Gear.Weapon?.Scope?.Sight?.Name != null) {
      let scopeSight = getSight(loadout.Gear.Weapon.Scope.Sight.Name);

      skillMod += scopeSight.Properties.SkillModification;
    }

    if (loadout.Gear.Weapon?.Sight?.Name != null) {
      let sight = getSight(loadout.Gear.Weapon.Sight.Name);

      skillMod += sight.Properties.SkillModification;
    }

    return skillMod;
  }

  function calcSkillBonus(loadout) {
    let skillBonus = 0;

    if (loadout.Gear.Weapon?.Scope?.Name != null) {
      let scope = getScope(loadout.Gear.Weapon.Scope.Name);

      skillBonus += scope.Properties.SkillBonus;
    }

    if (loadout.Gear.Weapon?.Scope?.Sight?.Name != null) {
      let scopeSight = getSight(loadout.Gear.Weapon.Scope.Sight.Name);

      skillBonus += scopeSight.Properties.SkillBonus;
    }

    if (loadout.Gear.Weapon?.Sight?.Name != null) {
      let sight = getSight(loadout.Gear.Weapon.Sight.Name);

      skillBonus += sight.Properties.SkillBonus;
    }

    return skillBonus;
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

  .loadout-manager {
    display: grid;
    grid-template-columns: 1fr 350px;
    height: 100%;
    width: 100%;
    align-self: stretch;
  }

  .select {
    display: grid;
    margin-bottom: 10px;
  }

  .select:last-child {
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
  }

  .compare-select {
    grid-template-columns: 0.2fr 0.2fr 0.2fr 0.2fr 0.2fr 100px 300px;
    gap: 1px;
    background-color: var(--text-color);
    border: 1px solid var(--text-color);
  }

  .weapon-select {
    grid-template-columns: 0.2fr 0.2fr 0.2fr 0.2fr 0.2fr 100px 300px;
    gap: 1px;
    background-color: var(--text-color);
    border: 1px solid var(--text-color);
  }

  .armor-select {
    grid-template-columns: 0.2fr 0.2fr 0.2fr 0.2fr 0.2fr 100px 300px;
    gap: 1px;
    background-color: var(--text-color);
    border: 1px solid var(--text-color);
  }

  .weapon-slot {
    display: grid;
    justify-content: center;
    align-items: center;
    background-color: var(--secondary-color);
    grid-column: span 5;
  }

  .armor-slot {
    display: grid;
    justify-content: center;
    align-items: center;
    background-color: var(--secondary-color);
    grid-column: span 5;
  }

  .empty-slot {
    grid-column: span 2;
    background-color: var(--primary-color);
  }

  .select-title {
    grid-column: span 5;
    background-color: var(--primary-color);
    font-size: 24px;
    padding-left: 8px;
  }

  .select-compare {
    grid-column: span 2;
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
    min-height: 30px;
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
</svelte:head>
<div class="flex-container">
  <div class="loadout-list centered">
    <LoadoutList
      bind:loadouts={loadouts}
      bind:currentLoadout={loadout} />
  </div>
  <div class="flex-content">
    {#if $loading}
      <div class="loading">
        <div class="spinner"></div>
      </div>
    {/if}
    {#if data != null && data?.error == null && loadout != null}
      <div class="loadout-manager">
        <div class="gear-select">
          {#if compareMode}
          <div class="select compare-select">
            <div class="select-title">Comparing</div>
            <div class="select-compare" on:click={() => compareMode = false}>Stop Comparing</div>
            <div style="grid-column: span 7; background-color: var(--primary-color);">
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
              <div class="select-compare" on:click={() => compareMode = true}>Compare Loadouts...</div>
              <button class="slot weapon-slot" style="grid-row: span 5;" on:contextmenu={e => clearSlot(e, "weapon")} on:click={() => picking = picking === 'weapon' ? null : 'weapon'}>
                {#if loadout?.Gear.Weapon.Name != null}
                  {loadout.Gear.Weapon.Name}
                {:else}
                  <span style="color: gray;">Click here to select a weapon...</span>
                {/if}
              </button>
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
              <div class="odd-color">Absorber:</div>
              <button class="slot sight-slot" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "absorber")} on:click={() => picking = picking === 'absorber' ? null : 'absorber'}>
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
              {#if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Ranged'}
                <div class="even-color">Scope:</div>
                <button class="slot scope-slot" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "scope")} on:click={() => picking = picking === 'scope' ? null : 'scope'}>
                  {#if loadout?.Gear.Weapon.Scope?.Name != null}
                    {loadout.Gear.Weapon.Scope.Name}
                  {:else}
                  <span style="color: gray;">Click here to select a scope...</span>
                  {/if}
                </button>
                <div class="odd-color" style="padding-left: 5px;"><span><span style="font-size: 13px">&#x21B3;</span> Sight:</span></div>
                <button class="slot scope-sight-slot" disabled={loadout?.Gear.Weapon.Scope == null} on:contextmenu={e => clearSlot(e, "scope-sight")} on:click={() => picking = picking === 'scope-sight' ? null : 'scope-sight'}>
                  {#if loadout.Gear.Weapon.Scope != null}
                    {#if loadout?.Gear.Weapon.Scope?.Sight?.Name != null}
                      {loadout.Gear.Weapon.Scope.Sight.Name}
                    {:else}
                      <span style="color: gray;">Click here to select a Sight...</span>
                    {/if}
                  {:else}
                    <span style="color: lightgray;">Add a scope first!</span>
                  {/if}
                </button>
                <div class="even-color">Sight:</div>
                <button class="slot sight-slot" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "sight")} on:click={() => picking = picking === 'sight' ? null : 'sight'}>
                  {#if loadout?.Gear.Weapon.Sight?.Name != null}
                    {loadout.Gear.Weapon.Sight.Name}
                  {:else}
                    <span style="color: gray;">Click here to select a Sight...</span>
                  {/if}
                </button>
              {:else if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Melee'}
                <div class="even-color">Matrix:</div>
                <button class="slot matrix-slot" disabled={getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class !== 'Melee'} on:contextmenu={e => clearSlot(e, "matrix")} on:click={() => picking = picking === 'matrix' ? null : 'matrix'}>
                  {#if loadout?.Gear.Weapon.Matrix?.Name != null}
                    {loadout.Gear.Weapon.Matrix.Name}
                  {:else}
                    <span style="color: gray;">Click here to select a matrix...</span>
                  {/if}
                </button>
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
                <div class="empty-slot"></div>
                <div class="empty-slot"></div>
              {:else}
                <div class="empty-slot"></div>
                <div class="empty-slot"></div>
                <div class="empty-slot"></div>
              {/if}
              <div class="even-color">Damage<input type="number" min="0" max="10" bind:value={weaponEnhancersDamage}></div>
              <div class="odd-color">Accuracy<input type="number" min="0" max="10" bind:value={weaponEnhancersAccuracy}></div>
              <div class="even-color">Range<input type="number" min="0" max="10" bind:value={weaponEnhancersRange}></div>
              <div class="odd-color">Economy<input type="number" min="0" max="10" bind:value={weaponEnhancersEconomy}></div>
              <div class="even-color">Skill Mod<input type="number" min="0" max="10" bind:value={weaponEnhancersSkillMod}></div>
              <div class="empty-slot">
                <span style="text-decoration: underline dotted;" title="If enabled, will only show amplifiers that overcap by 10% max">
                  <input type="checkbox" bind:checked={settings.onlyShowReasonableAmplifiers} /> Only show reasonable amplifiers
                </span>
              </div>
            </div>
            {#if picking === 'weapon' || picking === 'amplifier' || picking === 'absorber' || picking === 'scope' || picking === 'scope-sight' || picking === 'sight' || picking === 'matrix' || picking === 'implant'}
              <div class="picker">
                {#if picking === 'weapon'}
                  <ItemPicker 
                    items={weapons}
                    columns={['Class', 'Type', 'Efficiency', 'DPS', 'DPP', 'Min', 'Max', 'Cost']}
                    columnWidths={['80px', '80px', '80px', '60px', '60px', '60px', '60px', '75px']}
                    columnFunctions={[
                      x => x.Properties.Class,
                      x => x.Properties.Type,
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => getDps(x) != null ? getDps(x).toFixed(2) : 'N/A',
                      x => getDpp(x) != null ? getDpp(x).toFixed(2) : 'N/A',
                      x => x.Properties?.Skill?.Hit?.LearningIntervalStart != null ? x.Properties?.Skill?.Hit?.LearningIntervalStart.toFixed(1) : 'N/A',
                      x => x.Properties?.Skill?.Hit?.LearningIntervalEnd != null ? x.Properties?.Skill?.Hit?.LearningIntervalEnd.toFixed(1) : 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A'
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

                      if (2 * ampDamage > 1.1 * weaponDamage && settings.onlyShowReasonableAmplifiers) {
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

                      return false
                    })}
                    columns={['Damage', 'Efficiency', 'DPP', 'Cost']}
                    columnWidths={['75px', '80px', '60px', '75px']}
                    columnFunctions={[
                      x => getTotalDamage(x) != null ? getTotalDamage(x) : 'N/A',
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => getDpp(x) != null ? getDpp(x).toFixed(2) : 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Amplifier = { Name: e.detail.values[0] };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking === 'absorber'}
                  <ItemPicker
                    items={absorbers}
                    columns={['Efficiency', 'Absorption']}
                    columnWidths={['80px', '80px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => x.Properties.Economy.Absorption != null ? `${(x.Properties.Economy.Absorption * 100).toFixed(1)}%` : 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Absorber = { Name: e.detail.values[0] };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking === 'scope'}
                  <ItemPicker
                    items={scopes}
                    columns={['Efficiency', 'Skill Mod.', 'Skill Bonus', 'Zoom', 'Cost']}
                    columnWidths={['85px', '85px', '85px', '60px', '75px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => x.Properties.SkillModification != null ? `${x.Properties.SkillModification.toFixed(1)}%` : 'N/A',
                      x => x.Properties.SkillBonus != null ? x.Properties.SkillBonus.toFixed(1) : 'N/A',
                      x => x.Properties.Zoom != null ? `${x.Properties.Zoom}x` : 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A'
                    ]}
                    on:rowClick={e => {
                      loadout.Gear.Weapon.Scope = { Name: e.detail.values[0] };
                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking === 'scope-sight' || picking === 'sight'}
                  <ItemPicker
                    items={sights}
                    columns={['Efficiency', 'Skill Mod.', 'Skill Bonus', 'Cost']}
                    columnWidths={['85px', '85px', '85px', '75px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => x.Properties.SkillModification != null ? `${x.Properties.SkillModification.toFixed(1)}%` : 'N/A',
                      x => x.Properties.SkillBonus != null ? x.Properties.SkillBonus.toFixed(1) : 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A'
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
                    columns={['Efficiency', 'Cost']}
                    columnWidths={['80px', '75px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => getCost(x) != null ? `${getCost(x).toFixed(2)} PEC` : 'N/A'
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
                    columns={['Efficiency', 'Max. Level', 'Absorption']}
                    columnWidths={['80px', '80px', '80px']}
                    columnFunctions={[
                      x => x.Properties.Economy.Efficiency != null ? `${x.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A',
                      x => x.Properties.MaxProfessionLevel != null ? x.Properties.MaxProfessionLevel : 'N/A',
                      x => x.Properties.Economy.Absorption != null ? `${(x.Properties.Economy.Absorption * 100).toFixed(1)}%` : 'N/A'
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
                {/each}
              {:else}
                <button class="slot armor-slot" on:contextmenu={e => clearSlot(e, "armorset")} on:click={() => picking = picking === 'armorset' ? null : 'armorset'}>
                  {#if loadout?.Gear.Armor.SetName != null}
                    {loadout.Gear.Armor.SetName}
                  {:else}
                    <span style="color: gray;">Click here to select an armor set...</span>
                  {/if}
                </button>
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
              {/if}
              <div class="even-color">Defense<input type="number" min="0" max="10" bind:value={armorEnhancersDefense}></div>
              <div class="odd-color">Durability<input type="number" min="0" max="10" bind:value={armorEnhancersDurability}></div>
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
                        loadout.Gear.Armor[slot] = { Name: armorSet.Armors.find(x => slot == x.Properties.Slot)?.Name, Plate: loadout.Gear.Armor[slot].Plate };
                      });

                      loadouts = loadouts;
                      picking = null;
                    }} />
                {:else if picking.startsWith('armor-')}
                  <ItemPicker
                    items={armors}
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
            <div class="select clothing-select">
              
            </div>
            <div class="select pet-select">
              
            </div>
            <div class="select consumable-select">
              
            </div>
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
          <div class="row-color">DPS</div><div class="row-color">{calcDps(loadout) != null ? `${calcDps(loadout).toFixed(4)}` : 'N/A'}</div>
          <div style="grid-column: span 2; text-align: center; font-size: 16px; padding: 3px;" class="header-color">Economy</div>
          <div class="row-color">Efficiency</div><div class="row-color">{calcEfficiency(loadout) != null ? `${calcEfficiency(loadout).toFixed(1)}%` : 'N/A'}</div>
          <div class="row-color-alt">Decay</div><div class="row-color-alt">{calcDecay(loadout) != null ? `${calcDecay(loadout).toFixed(4)} PEC` : 'N/A'}</div>
          <div class="row-color">Ammo</div><div class="row-color">{calcAmmo(loadout) != null ? Math.round(calcAmmo(loadout)) : 'N/A'}</div>
          <div class="row-color-alt">Cost</div><div class="row-color-alt">{calcCost(loadout) != null ? `${calcCost(loadout).toFixed(4)} PEC` : 'N/A'}</div>
          <div class="row-color">DPP</div><div class="row-color">{calcDpp(loadout) != null ? `${calcDpp(loadout).toFixed(4)}` : 'N/A'}</div>
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
      <div class="info">Create or select an existing loadout on the left!</div>
    {/if}
  </div>
</div>