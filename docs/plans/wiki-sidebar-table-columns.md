# Wiki Sidebar Table Columns Plan

## Goal
Define consistent, filter-friendly columns for the expandable sidebar tables across all wiki pages. Columns should make sense for quick scanning and filtering, and stay consistent with existing data models. This plan covers Items, Information, and Shops.

## Column Principles
- **Always include Name** (primary, searchable).
- **One or two high-signal numeric stats** per category to enable meaningful filtering.
- **Category/type columns** to narrow scope quickly (Type/Class/Slot/Profession/etc.).
- **Avoid overly granular columns** that cause noise; keep to 4–7 columns total.
- **Default visible** columns should be the most filter-worthy; optional columns can remain hidden by default.

## Items Section

### Weapons (`/items/weapons`)
Default columns:
- Name
- Class (Ranged/Melee/Mindforce)
- Type (Pistol/Rifle/etc.)
- DPS
- DPP
- Efficiency

### Tools (`/items/tools/*`)
Common columns (all tools):
- Name
- Tool Type (Scanner/Finder/Excavator/Refiner/Teleport/Effect/Misc) (hide this if filtered)
- Uses/Minute
- Decay
Tool-specific optional columns:
- Scanners: Range, Depth
- Finders/Excavators: Average Depth, Range
- Refiners: -
- Teleport/Effect chips: Cost per Use, Range

### Medical Tools (`/items/medicaltools/*`)
Default columns:
- Name
- Type (Tool/Chip) (hide if filtered)
- Heal Interval
- Uses/Minute
- Max Level

### Attachments
**Weapon Amplifiers** (`/items/attachments/weaponamplifiers`)
- Name
- Damage
- DPP
- Efficiency

**Weapon Vision Attachments** (`/items/attachments/weaponvisionattachments`)
- Name
- Type (Scope/Sight)
- Efficiency

**Absorbers** (`/items/attachments/absorbers`)
- Name
- Absorption
- Efficiency

**Armor Platings** (`/items/attachments/armorplatings`)
- Name
- Total Defense
- Durability

**Finder Amplifiers** (`/items/attachments/finderamplifiers`)
- Name
- Decay
- Efficiency

**Enhancers** (`/items/attachments/enhancers`)
- Name
- Type (Damage/Range/etc.)
- Tier

**Mindforce Implants** (`/items/attachments/mindforceimplants`)
- Name
- Absorption
- Level

### Armor Sets (`/items/armorsets`)
Default columns:
- Name
- Total Defense
- Durability

### Clothing (`/items/clothing`)
Default columns:
- Name
- Slot
- Type
- Effects (Yes/No)

### Consumables (`/items/consumables/*`)
Default columns:
- Name
- Type (Stimulant/Capsule)
- Effect # / Mob Type

### Materials (`/items/materials`)
Default columns:
- Name
- Type (Ore/Enmatter/Refined/etc.)

### Blueprints (`/items/blueprints`)
Default columns:
- Name
- Type (Weapon/Armor/etc.)
- Profession
- Level

### Vehicles (`/items/vehicles`)
Default columns:
- Name
- Type
- Speed
- Fuel Usage

### Pets (`/items/pets`)
Default columns:
- Name
- Rarity
- Effect #

## Information Section

### Mobs (`/information/mobs`)
Default columns:
- Name
- Species
- Level Range
- HP Range
- **Cat 4** (Yes/No, based on species data)

### Professions (`/information/professions`)
Default columns:
- Name
- Category (Combat/Crafting/Gathering/etc.)

### Skills (`/information/skills`)
Default columns:
- Name
- Category

### Vendors (`/information/vendors`)
Default columns:
- Name
- Planet
- Category

## Shops / Market

### Shops (`/market/shops`)
Default columns:
- Name
- Location (Short Format)
- Owner (if available)

## Implementation Notes
- Use consistent column keys across pages where possible (e.g., `type`, `class`, `efficiency`, `durability`).
- Keep **Name** as the primary column and enable text search on it.
- Ensure numeric columns are sortable and filterable.
- Provide sensible defaults
