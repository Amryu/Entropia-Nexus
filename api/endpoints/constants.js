// Centralized ID offsets used to compute ItemId values for item subtypes
// Mirrors the legacy values from the previous monolithic db.js
const idOffsets = {
  Materials:                1000000,
  Weapons:                  2000000,
  Armors:                   3000000,
  Tools:                    4000000,
  MedicalTools:             4100000,
  MiscTools:                4200000,
  Refiners:                 4300000,
  Scanners:                 4400000,
  Finders:                  4500000,
  Excavators:               4600000,
  BlueprintBooks:           4700000,
  MedicalChips:             4800000,
  TeleportationChips:       4810000,
  EffectChips:              4820000,
  Attachments:              5000000,
  WeaponAmplifiers:         5100000,
  WeaponVisionAttachments:  5200000,
  Absorbers:                5300000,
  FinderAmplifiers:         5400000,
  ArmorPlatings:            5500000,
  Enhancers:                5600000,
  MindforceImplants:        5700000,
  Blueprints:               6000000,
  Vehicles:                 7000000,
  Clothings:                8000000,
  Furnishings:              9000000,
  Furniture:                9100000,
  Decorations:              9200000,
  StorageContainers:        9300000,
  Signs:                    9400000,
  Consumables:              10000000,
  Capsules:                 10100000,
  Pets:                     11000000,
  Strongboxes:              12000000,
  ArmorSets:                13000000,

  equipSet:                 100000,
};

// All physical tables behind the Items VIEW (including sub-views: Tools, Attachments, Furnishings).
// Used for cache invalidation — Items/Tools/Attachments/Furnishings are VIEWs with no TableChanges triggers.
const ITEM_TABLES = [
  // Direct in Items VIEW
  'Materials', 'Weapons', 'Armors', 'Blueprints', 'Vehicles', 'Clothes',
  'Consumables', 'CreatureControlCapsules', 'Pets',
  // Tools VIEW
  'MedicalTools', 'MiscTools', 'Refiners', 'Scanners', 'Finders', 'Excavators',
  'BlueprintBooks', 'MedicalChips', 'TeleportationChips', 'EffectChips',
  // Attachments VIEW
  'WeaponAmplifiers', 'WeaponVisionAttachments', 'Absorbers', 'FinderAmplifiers',
  'ArmorPlatings', 'Enhancers', 'MindforceImplants',
  // Furnishings VIEW
  'Furniture', 'Decorations', 'StorageContainers', 'Signs',
];

// Maps DB table names (or view names) to the EntityType string used in the ClassIds lookup table.
// EntityType strings match the entity type names used in the Items VIEW, search results, and wiki changes.
const TABLE_TO_ENTITY_TYPE = {
  Materials:                'Material',
  Weapons:                  'Weapon',
  Armors:                   'Armor',
  Blueprints:               'Blueprint',
  Vehicles:                 'Vehicle',
  Clothes:                  'Clothing',
  Consumables:              'Consumable',
  CreatureControlCapsules:  'Capsule',
  Pets:                     'Pet',
  Strongboxes:              'Strongbox',
  ArmorSets:                'ArmorSet',
  MedicalTools:             'MedicalTool',
  MiscTools:                'MiscTool',
  Refiners:                 'Refiner',
  Scanners:                 'Scanner',
  Finders:                  'Finder',
  Excavators:               'Excavator',
  BlueprintBooks:           'BlueprintBook',
  MedicalChips:             'MedicalChip',
  TeleportationChips:       'TeleportationChip',
  EffectChips:              'EffectChip',
  WeaponAmplifiers:         'WeaponAmplifier',
  WeaponVisionAttachments:  'WeaponVisionAttachment',
  Absorbers:                'Absorber',
  FinderAmplifiers:         'FinderAmplifier',
  ArmorPlatings:            'ArmorPlating',
  Enhancers:                'Enhancer',
  MindforceImplants:        'MindforceImplant',
  Furniture:                'Furniture',
  Decorations:              'Decoration',
  StorageContainers:        'StorageContainer',
  Signs:                    'Sign',
  Mobs:                     'Mob',
  Skills:                   'Skill',
  Professions:              'Profession',
};

// Blueprint drop category mapping
// Types within the same category can drop from each other
const BLUEPRINT_DROP_CATEGORIES = {
  'Weapon': 'Weapon',
  'Textile': 'Textile',
  'Vehicle': 'Vehicle',
  'Enhancer': 'Enhancer',
  'Furniture': 'Furniture',
  'Tool': 'Tool',
  'Armor': 'Armor',
  'Attachment': 'Attachment',
  'Metal Component': 'Components',
  'Electrical Component': 'Components',
  'Mechanical Component': 'Components',
  'Chemistry': 'Chemistry',
};

// Level range for blueprint drops: crafting a level N BP can drop BPs from level N-3 to N+2
const BLUEPRINT_DROP_LEVEL_RANGE = { above: 2, below: 3 };

const BLUEPRINT_DROP_RARITIES = ['Common', 'Uncommon', 'Rare', 'Very Rare', 'Extremely Rare'];

module.exports = { idOffsets, ITEM_TABLES, TABLE_TO_ENTITY_TYPE, BLUEPRINT_DROP_CATEGORIES, BLUEPRINT_DROP_LEVEL_RANGE, BLUEPRINT_DROP_RARITIES };
