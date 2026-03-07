/**
 * Column definitions for the dedicated search page.
 * Keys match the sidebar column keys (wiki-nav-columns-{pageTypeId} in localStorage)
 * so user preferences carry over.
 */

// --- Weapon calculation helpers ---
function weaponTotalDamage(item) {
  const d = item?.Properties?.Damage;
  if (!d) return null;
  return (d.Impact || 0) + (d.Cut || 0) + (d.Stab || 0) + (d.Penetration || 0) +
         (d.Shrapnel || 0) + (d.Burn || 0) + (d.Cold || 0) + (d.Acid || 0) + (d.Electric || 0);
}

function weaponEffectiveDamage(item) {
  const total = weaponTotalDamage(item);
  if (total === null || total === 0) return null;
  return total * (0.88 * 0.75 + 0.02 * 1.75);
}

function weaponReload(item) {
  if (!item?.Properties?.UsesPerMinute) return null;
  return 60 / item.Properties.UsesPerMinute;
}

function weaponCostPerUse(item) {
  const decay = item?.Properties?.Economy?.Decay;
  const ammoBurn = item?.Properties?.Economy?.AmmoBurn ?? 0;
  if (decay === null || decay === undefined) return null;
  return decay + (ammoBurn / 100);
}

function weaponDps(item) {
  const reload = weaponReload(item);
  const eff = weaponEffectiveDamage(item);
  if (eff === null || reload === null) return null;
  return eff / reload;
}

function weaponDpp(item) {
  const cost = weaponCostPerUse(item);
  const eff = weaponEffectiveDamage(item);
  if (cost === null || cost === 0 || eff === null) return null;
  return eff / cost;
}

function weaponTotalUses(item) {
  const maxTT = item?.Properties?.Economy?.MaxTT;
  const minTT = item?.Properties?.Economy?.MinTT ?? 0;
  const decay = item?.Properties?.Economy?.Decay;
  if (maxTT == null || decay == null || decay === 0) return null;
  return Math.floor((maxTT - minTT) / (decay / 100));
}

// --- Armor set calculation helpers ---
function armorTotalDefense(item) {
  const d = item?.Properties?.Defense;
  if (!d) return null;
  return (d.Impact || 0) + (d.Cut || 0) + (d.Stab || 0) + (d.Penetration || 0) +
         (d.Shrapnel || 0) + (d.Burn || 0) + (d.Cold || 0) + (d.Acid || 0) + (d.Electric || 0);
}

// --- Mob calculation helpers ---
// Maturity data is nested: { Properties: { Level, Health, ... } }
function mobLevelMax(item) {
  const mats = item?.Maturities;
  if (!Array.isArray(mats) || mats.length === 0) return null;
  const levels = mats.map(m => m.Properties?.Level).filter(l => l != null);
  return levels.length > 0 ? Math.max(...levels) : null;
}

function mobHealthMax(item) {
  const mats = item?.Maturities;
  if (!Array.isArray(mats) || mats.length === 0) return null;
  const values = mats.map(m => m.Properties?.Health).filter(h => h != null);
  return values.length > 0 ? Math.max(...values) : null;
}

function mobSmallestHpPerLevel(item) {
  const mats = item?.Maturities;
  if (!Array.isArray(mats) || mats.length === 0) return null;
  let min = Infinity;
  for (const m of mats) {
    const health = m.Properties?.Health;
    const level = m.Properties?.Level;
    if (health != null && level != null && level > 0) {
      const ratio = health / level;
      if (ratio < min) min = ratio;
    }
  }
  return min === Infinity ? null : min;
}

// --- Format helpers ---
const fmt = (decimals) => (v) => v != null ? v.toFixed(decimals) : '-';
const fmtInt = (v) => v != null ? String(v) : '-';
const fmtStr = (v) => v || '-';
const fmtBool = (v) => v === true || v === 1 ? 'Yes' : v === false || v === 0 ? 'No' : '-';
/** Format with up to N decimal places, trimming trailing zeros */
const fmtTrim = (maxDecimals) => (v) => {
  if (v == null) return '-';
  if (v === 0) return '0';
  const s = v.toFixed(maxDecimals).replace(/\.?0+$/, '');
  return s || '0';
};

/**
 * Column definitions per entity type.
 * Keyed by pageTypeId (matches localStorage wiki-nav-columns-{pageTypeId}).
 */
export const SEARCH_COLUMN_DEFS = {
  weapons: {
    class:        { key: 'class',        header: 'Class',    width: '70px',  getValue: (item) => item.Properties?.Class, format: fmtStr },
    type:         { key: 'type',         header: 'Type',     width: '70px',  getValue: (item) => item.Properties?.Type, format: fmtStr },
    dps:          { key: 'dps',          header: 'DPS',      width: '55px',  getValue: weaponDps, format: fmt(1) },
    dpp:          { key: 'dpp',          header: 'DPP',      width: '55px',  getValue: weaponDpp, format: fmt(2) },
    eff:          { key: 'eff',          header: 'Eff.',     width: '55px',  getValue: (item) => item.Properties?.Economy?.Efficiency, format: fmt(1) },
    effectiveDmg: { key: 'effectiveDmg', header: 'Eff Dmg',  width: '60px',  getValue: weaponEffectiveDamage, format: fmt(1) },
    damage:       { key: 'damage',       header: 'Damage',   width: '60px',  getValue: weaponTotalDamage, format: fmt(1) },
    range:        { key: 'range',        header: 'Range',    width: '55px',  getValue: (item) => item.Properties?.Range, format: fmtInt },
    upm:          { key: 'upm',          header: 'Uses',     width: '50px',  getValue: (item) => item.Properties?.UsesPerMinute, format: fmtInt },
    maxtt:        { key: 'maxtt',        header: 'Max TT',   width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
    decay:        { key: 'decay',        header: 'Decay',    width: '55px',  getValue: (item) => item.Properties?.Economy?.Decay, format: fmt(2) },
    ammo:         { key: 'ammo',         header: 'Ammo',     width: '55px',  getValue: (item) => item.Properties?.Economy?.AmmoBurn, format: fmtInt },
    uses:         { key: 'uses',         header: 'Uses',     width: '55px',  getValue: weaponTotalUses, format: fmtInt },
    sib:          { key: 'sib',          header: 'SiB',      width: '40px',  getValue: (item) => item.Properties?.Skill?.IsSiB, format: fmtBool },
    costPerUse:   { key: 'costPerUse',   header: 'Cost/Use', width: '65px',  getValue: weaponCostPerUse, format: fmt(4) },
    weight:       { key: 'weight',       header: 'Weight',   width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
    mintt:        { key: 'mintt',        header: 'Min TT',   width: '55px',  getValue: (item) => item.Properties?.Economy?.MinTT, format: fmt(2) },
    category:     { key: 'category',     header: 'Category', width: '75px',  getValue: (item) => item.Properties?.Category, format: fmtStr },
  },

  materials: {
    type:   { key: 'type',   header: 'Type',   width: '90px',  getValue: (item) => item.Properties?.Type, format: fmtStr },
    weight: { key: 'weight', header: 'Weight', width: '60px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
    value:  { key: 'value',  header: 'Value',  width: '70px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
  },

  blueprints: {
    type:       { key: 'type',       header: 'Type',       width: '80px',  getValue: (item) => item.Properties?.Type, format: fmtStr },
    profession: { key: 'profession', header: 'Profession', width: '90px',  getValue: (item) => item.Profession?.Name, format: fmtStr },
    level:      { key: 'level',      header: 'Level',      width: '50px',  getValue: (item) => item.Properties?.Level, format: fmtInt },
    product:    { key: 'product',    header: 'Product',    width: '100px', getValue: (item) => item.Product?.Name, format: fmtStr },
    sib:        { key: 'sib',        header: 'SiB',        width: '40px',  getValue: (item) => item.Properties?.Skill?.IsSiB, format: fmtBool },
  },

  armorsets: {
    defense:     { key: 'defense',     header: 'Def.',      width: '55px',  getValue: armorTotalDefense, format: fmt(1) },
    durability:  { key: 'durability',  header: 'Dur.',      width: '55px',  getValue: (item) => item.Properties?.Economy?.Durability, format: fmt(1) },
    impact:      { key: 'impact',      header: 'Imp',       width: '45px',  getValue: (item) => item.Properties?.Defense?.Impact, format: fmt(1) },
    cut:         { key: 'cut',         header: 'Cut',       width: '45px',  getValue: (item) => item.Properties?.Defense?.Cut, format: fmt(1) },
    stab:        { key: 'stab',        header: 'Stab',      width: '45px',  getValue: (item) => item.Properties?.Defense?.Stab, format: fmt(1) },
    penetration: { key: 'penetration', header: 'Pen',       width: '45px',  getValue: (item) => item.Properties?.Defense?.Penetration, format: fmt(1) },
    shrapnel:    { key: 'shrapnel',    header: 'Shrp',      width: '45px',  getValue: (item) => item.Properties?.Defense?.Shrapnel, format: fmt(1) },
    burn:        { key: 'burn',        header: 'Burn',      width: '45px',  getValue: (item) => item.Properties?.Defense?.Burn, format: fmt(1) },
    cold:        { key: 'cold',        header: 'Cold',      width: '45px',  getValue: (item) => item.Properties?.Defense?.Cold, format: fmt(1) },
    acid:        { key: 'acid',        header: 'Acid',      width: '45px',  getValue: (item) => item.Properties?.Defense?.Acid, format: fmt(1) },
    electric:    { key: 'electric',    header: 'Elec',      width: '45px',  getValue: (item) => item.Properties?.Defense?.Electric, format: fmt(1) },
    maxtt:       { key: 'maxtt',       header: 'Max TT',    width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
    weight:      { key: 'weight',      header: 'Weight',    width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
  },

  clothing: {
    slot:   { key: 'slot',   header: 'Slot',   width: '70px',  getValue: (item) => item.Properties?.Slot, format: fmtStr },
    type:   { key: 'type',   header: 'Type',   width: '70px',  getValue: (item) => item.Properties?.Type, format: fmtStr },
    gender: { key: 'gender', header: 'Gender', width: '55px',  getValue: (item) => item.Properties?.Gender, format: fmtStr },
    weight: { key: 'weight', header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
    maxTT:  { key: 'maxTT',  header: 'Max TT', width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
  },

  vehicles: {
    type:       { key: 'type',       header: 'Type',   width: '80px',  getValue: (item) => item.Properties?.Type, format: fmtStr },
    speed:      { key: 'speed',      header: 'Speed',  width: '55px',  getValue: (item) => item.Properties?.MaxSpeed, format: fmtInt },
    fuel:       { key: 'fuel',       header: 'Fuel',   width: '55px',  getValue: (item) => item.Properties?.Economy?.FuelConsumptionActive ?? item.Properties?.Economy?.FuelConsumptionPassive, format: fmt(2) },
    passengers: { key: 'passengers', header: 'Seats',  width: '50px',  getValue: (item) => item.Properties?.PassengerCount, format: fmtInt },
    maxSI:      { key: 'maxSI',      header: 'Max SI', width: '60px',  getValue: (item) => item.Properties?.MaxStructuralIntegrity, format: fmtInt },
    weight:     { key: 'weight',     header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
    maxTT:      { key: 'maxTT',      header: 'Max TT', width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
  },

  pets: {
    rarity:    { key: 'rarity',    header: 'Rarity',  width: '65px',  getValue: (item) => item.Properties?.Rarity, format: fmtStr },
    effects:   { key: 'effects',   header: 'Effects', width: '55px',  getValue: (item) => item.Effects?.length || 0, format: fmtInt },
    planet:    { key: 'planet',    header: 'Planet',  width: '70px',  getValue: (item) => item.Planet?.Name, format: fmtStr },
    tamingLevel: { key: 'tamingLevel', header: 'Taming', width: '55px', getValue: (item) => item.Properties?.TamingLevel, format: fmtInt },
  },

  mobs: {
    hpPerLevel: { key: 'hpPerLevel', header: 'HP/Lvl', width: '60px',  getValue: mobSmallestHpPerLevel, format: fmt(1) },
    level:      { key: 'level',      header: 'Level',  width: '50px',  getValue: mobLevelMax, format: fmtInt },
    hp:         { key: 'hp',         header: 'HP',     width: '55px',  getValue: mobHealthMax, format: fmtInt },
    type:       { key: 'type',       header: 'Type',   width: '70px',  getValue: (item) => item.EntityType, format: fmtStr },
    planet:     { key: 'planet',     header: 'Planet', width: '70px',  getValue: (item) => item.Planet?.Name, format: fmtStr },
    sweatable:  { key: 'sweatable',  header: 'Sweat',  width: '50px',  getValue: (item) => item.Properties?.IsSweatable, format: fmtBool },
  },

  mobmaturities: {
    mob:    { key: 'mob',    header: 'Mob',    width: '100px', getValue: (item) => item.MobName, format: fmtStr },
    level:  { key: 'level',  header: 'Level',  width: '50px',  getValue: (item) => item.Properties?.Level, format: fmtInt },
    hp:     { key: 'hp',     header: 'HP',     width: '55px',  getValue: (item) => item.Properties?.Health, format: fmtInt },
    planet: { key: 'planet', header: 'Planet', width: '70px',  getValue: (item) => item.Planet?.Name, format: fmtStr },
  },

  skills: {
    category:    { key: 'category',    header: 'Category',  width: '90px',  getValue: (item) => item.Category?.Name, format: fmtStr },
    hpIncrease:  { key: 'hpIncrease',  header: 'HP+',       width: '50px',  getValue: (item) => item.Properties?.HpIncrease || 0, format: fmtTrim(1) },
    professions: { key: 'professions', header: 'Profs',     width: '50px',  getValue: (item) => item.Professions?.length || 0, format: fmtInt },
    hidden:      { key: 'hidden',      header: 'Hidden',    width: '55px',  getValue: (item) => item.Properties?.IsHidden, format: fmtBool },
    extractable: { key: 'extractable', header: 'Extract',   width: '55px',  getValue: (item) => item.Properties?.IsExtractable, format: fmtBool },
  },

  professions: {
    category:    { key: 'category',    header: 'Category', width: '90px',  getValue: (item) => item.Category?.Name, format: fmtStr },
    skills:      { key: 'skills',      header: 'Skills',   width: '50px',  getValue: (item) => item.Skills?.length || 0, format: fmtInt },
    totalWeight: { key: 'totalWeight', header: 'Weight',   width: '55px',  getValue: (item) => item.Skills?.reduce((s, sk) => s + (sk.Weight || 0), 0) || 0, format: fmt(1) },
    unlocks:     { key: 'unlocks',     header: 'Unlocks',  width: '55px',  getValue: (item) => item.Unlocks?.length || 0, format: fmtInt },
  },

  vendors: {
    planet:   { key: 'planet',   header: 'Planet',   width: '70px',  getValue: (item) => item?.Planet?.Name, format: fmtStr },
    category: { key: 'category', header: 'Category', width: '80px',  getValue: (item) => item?.Properties?.Category, format: fmtStr },
    offers:   { key: 'offers',   header: 'Offers',   width: '50px',  getValue: (item) => item?.Offers?.length || 0, format: fmtInt },
  },

  missions: {
    type:   { key: 'type',   header: 'Type',   width: '80px',  getValue: (item) => item?.Properties?.Type, format: fmtStr },
    planet: { key: 'planet', header: 'Planet', width: '70px',  getValue: (item) => item?.Planet?.Name, format: fmtStr },
    chain:  { key: 'chain',  header: 'Chain',  width: '100px', getValue: (item) => item?.MissionChain?.Name, format: fmtStr },
  },

  missionchains: {
    type:   { key: 'type',   header: 'Type',   width: '80px',  getValue: (item) => item?.Properties?.Type, format: fmtStr },
    planet: { key: 'planet', header: 'Planet', width: '70px',  getValue: (item) => item?.Planet?.Name, format: fmtStr },
  },

  locations: {
    type:   { key: 'type',   header: 'Type',   width: '80px',  getValue: (item) => item?.Properties?.Type, format: fmtStr },
    planet: { key: 'planet', header: 'Planet', width: '70px',  getValue: (item) => item?.Planet?.Name, format: fmtStr },
  },

  users: {
    subtype: { key: 'subtype', header: 'Info', width: '80px', getValue: (item) => item?.SubType, format: fmtStr },
  },

  societies: {
    abbreviation: { key: 'abbreviation', header: 'Tag', width: '60px', getValue: (item) => item?.SubType, format: fmtStr },
  },

  blueprintbooks: {
    planet: { key: 'planet', header: 'Planet', width: '70px',  getValue: (item) => item.Planet?.Name, format: fmtStr },
    weight: { key: 'weight', header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
    value:  { key: 'value',  header: 'Value',  width: '60px',  getValue: (item) => item.Properties?.Economy?.Value, format: fmt(2) },
  },

  weaponamplifiers: {
    type:     { key: 'type',     header: 'Type',   width: '70px',  getValue: (item) => item.Properties?.Type, format: fmtStr },
    eff:      { key: 'eff',      header: 'Eff.',   width: '55px',  getValue: (item) => item.Properties?.Economy?.Efficiency, format: fmt(1) },
    dps:      { key: 'dps',      header: 'DPS',    width: '55px',  getValue: weaponDps, format: fmt(1) },
    damage:   { key: 'damage',   header: 'Damage', width: '60px',  getValue: weaponTotalDamage, format: fmt(1) },
    maxtt:    { key: 'maxtt',    header: 'Max TT', width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
    decay:    { key: 'decay',    header: 'Decay',  width: '55px',  getValue: (item) => item.Properties?.Economy?.Decay, format: fmt(2) },
    ammo:     { key: 'ammo',     header: 'Ammo',   width: '55px',  getValue: (item) => item.Properties?.Economy?.AmmoBurn, format: fmtInt },
    weight:   { key: 'weight',   header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
  },

  // Generic item columns — used for simple item sub-types
  items: {
    weight: { key: 'weight', header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
    maxtt:  { key: 'maxtt',  header: 'Max TT', width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
    decay:  { key: 'decay',  header: 'Decay',  width: '55px',  getValue: (item) => item.Properties?.Economy?.Decay, format: fmt(2) },
  },

  // Tools sub-types
  medicalchips: {
    maxtt:  { key: 'maxtt',  header: 'Max TT', width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
    decay:  { key: 'decay',  header: 'Decay',  width: '55px',  getValue: (item) => item.Properties?.Economy?.Decay, format: fmt(2) },
    weight: { key: 'weight', header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
  },

  finders: {
    range:  { key: 'range',  header: 'Range',  width: '55px',  getValue: (item) => item.Properties?.Range, format: fmtInt },
    depth:  { key: 'depth',  header: 'Depth',  width: '55px',  getValue: (item) => item.Properties?.Depth, format: fmtInt },
    maxtt:  { key: 'maxtt',  header: 'Max TT', width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
    decay:  { key: 'decay',  header: 'Decay',  width: '55px',  getValue: (item) => item.Properties?.Economy?.Decay, format: fmt(2) },
    weight: { key: 'weight', header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
  },

  // Attachment sub-types
  enhancers: {
    type:   { key: 'type',   header: 'Type',   width: '80px',  getValue: (item) => item.Properties?.Type, format: fmtStr },
    value:  { key: 'value',  header: 'Value',   width: '55px',  getValue: (item) => item.Properties?.Economy?.Value, format: fmt(2) },
    weight: { key: 'weight', header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
  },

  // Furnishing sub-types
  furnishings: {
    weight: { key: 'weight', header: 'Weight', width: '55px',  getValue: (item) => item.Properties?.Weight, format: fmtInt },
    maxtt:  { key: 'maxtt',  header: 'Max TT', width: '60px',  getValue: (item) => item.Properties?.Economy?.MaxTT, format: fmt(2) },
  },
};

/**
 * Default column keys per type (used when no localStorage config exists).
 * Matches the navTableColumns defaults from each entity page.
 */
export const DEFAULT_SEARCH_COLUMNS = {
  weapons:     ['class', 'type', 'dps', 'dpp', 'eff'],
  materials:   ['type', 'weight', 'value'],
  blueprints:  ['type', 'profession', 'level'],
  armorsets:    ['defense', 'durability', 'impact', 'cut', 'stab'],
  clothing:    ['slot', 'type', 'gender'],
  vehicles:    ['type', 'speed', 'fuel'],
  pets:        ['rarity', 'effects', 'planet'],
  mobs:        ['hpPerLevel', 'level', 'hp', 'planet'],
  mobmaturities: ['mob', 'level', 'hp', 'planet'],
  skills:      ['category', 'hpIncrease', 'professions'],
  professions: ['category', 'skills', 'totalWeight'],
  blueprintbooks: ['planet', 'weight', 'value'],
  weaponamplifiers: ['eff', 'dps', 'damage', 'maxtt', 'decay'],
  vendors:       ['planet', 'category', 'offers'],
  missions:      ['type', 'planet', 'chain'],
  missionchains: ['type', 'planet'],
  locations:     ['type', 'planet'],
  users:         ['subtype'],
  societies:     ['abbreviation'],
  items:         ['weight', 'maxtt', 'decay'],
  medicalchips:  ['maxtt', 'decay', 'weight'],
  finders:       ['range', 'depth', 'maxtt', 'decay'],
  enhancers:     ['type', 'value', 'weight'],
  furnishings:   ['weight', 'maxtt'],
};

/**
 * Map search result Type → pageTypeId for column lookup.
 */
export const SEARCH_TYPE_TO_PAGE_TYPE_ID = {
  Weapon:                 'weapons',
  Material:               'materials',
  Blueprint:              'blueprints',
  ArmorSet:               'armorsets',
  Clothing:               'clothing',
  Vehicle:                'vehicles',
  Pet:                    'pets',
  Mob:                    'mobs',
  MobMaturity:            'mobmaturities',
  Skill:                  'skills',
  Profession:             'professions',
  Vendor:                 'vendors',
  MedicalTool:            'weapons',
  Consumable:             'materials',
  MiscTool:               'items',
  Strongbox:              'items',
  Mission:                'missions',
  MissionChain:           'missionchains',
  Location:               'locations',
  User:                   'users',
  Society:                'societies',
  MedicalChip:            'medicalchips',
  Refiner:                'items',
  Scanner:                'items',
  Finder:                 'finders',
  Excavator:              'items',
  TeleportationChip:      'items',
  EffectChip:             'items',
  Capsule:                'items',
  Furniture:              'furnishings',
  Decoration:             'furnishings',
  StorageContainer:       'furnishings',
  Sign:                   'furnishings',
  WeaponAmplifier:        'weaponamplifiers',
  BlueprintBook:          'blueprintbooks',
  WeaponVisionAttachment: 'items',
  Absorber:               'items',
  ArmorPlating:           'items',
  FinderAmplifier:        'items',
  Enhancer:               'enhancers',
  MindforceImplant:       'items',
};

/**
 * Get resolved columns for a search result type.
 * Reads user preferences from localStorage if available.
 * @param {string} type - Search result Type (e.g. 'Weapon')
 * @param {Storage|null} storage - localStorage (null during SSR)
 * @returns {{ columns: object[], pageTypeId: string|null }}
 */
export function getColumnsForType(type, storage = null) {
  const pageTypeId = SEARCH_TYPE_TO_PAGE_TYPE_ID[type];
  if (!pageTypeId) return { columns: [], pageTypeId: null };

  const defs = SEARCH_COLUMN_DEFS[pageTypeId];
  if (!defs) return { columns: [], pageTypeId };

  // Try user preferences from localStorage
  if (storage) {
    try {
      const stored = storage.getItem(`wiki-nav-columns-${pageTypeId}`);
      if (stored) {
        const keys = JSON.parse(stored);
        if (Array.isArray(keys) && keys.length > 0) {
          const resolved = keys.slice(0, 5).map(k => defs[k]).filter(Boolean);
          if (resolved.length > 0) return { columns: resolved, pageTypeId };
        }
      }
    } catch { /* fall through to defaults */ }
  }

  // Fall back to defaults
  const defaultKeys = DEFAULT_SEARCH_COLUMNS[pageTypeId] || [];
  const columns = defaultKeys.map(k => defs[k]).filter(Boolean);
  return { columns, pageTypeId };
}
