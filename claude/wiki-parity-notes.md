# Wiki Page Parity Notes

## Overview

This document tracks the work to ensure consistency between legacy (`EntityViewer`-based) and new (wiki-style with `WikiPage` + `InlineEdit`) pages for editing functionality.

## Goals

1. **Same editable fields**: New wiki pages should allow editing the same data as legacy pages
2. **Same payload format**: The data submitted to `/api/changes` should match what the API expects
3. **Conditional editing**: Same rules for when fields are editable (e.g., owner-based restrictions)

---

## Shops Page (`/market/shops/`)

### Status: Complete

### Comparison

| Feature | Legacy (`shops-legacy`) | New (`shops`) | Status |
|---------|------------------------|---------------|--------|
| Name | text | InlineEdit text | OK |
| Description | textarea | RichTextEditor | OK (enhanced) |
| Planet | select (disabled if owner exists) | InlineEdit select (disabled if owner exists) | FIXED |
| Coordinates | waypoint type (disabled if owner exists) | 3 separate InlineEdit numbers (disabled if owner exists) | FIXED |
| MaxGuests | number | InlineEdit number | OK |
| HasAdditionalArea | checkbox | InlineEdit checkbox | ADDED |
| Sections array | list with MaxItemPoints per section | Inline editing in Estate Areas section | ADDED |

### Implemented Changes (2026-01-31)

1. **Added HasAdditionalArea checkbox** - toggles visibility of Additional section
2. **Added Sections editing** - Indoor/Display/Additional areas with MaxItemPoints per section
3. **Added conditional editing** - Planet and Coordinates fields disabled when `shop.Owner?.Name` exists (matches legacy behavior)
4. **Added `hasOwner` computed property** to track owner state
5. **Added handler functions** for section MaxItemPoints updates

### Notes

- Sections editing implemented inline in Estate Areas section
- SECTION_NAMES constant: `['Indoor', 'Display', 'Additional']`
- Section points displayed with "pts" suffix in edit mode
- View mode shows section tags with points in parentheses

---

## Materials Page (`/items/materials/`)

### Status: Partial

### Comparison

| Feature | Legacy (`materials-legacy`) | New (`materials`) | Status |
|---------|---------------------------|-------------------|--------|
| Name | text | InlineEdit text | OK |
| Description | textarea | RichTextEditor | OK (enhanced) |
| Weight | number | InlineEdit number | OK |
| Value (MaxTT) | number | InlineEdit number | OK |
| RefiningRecipes | nested list (Amount + Ingredients) | **MISSING** | **LOW PRIORITY** |

### Notes

- RefiningRecipes editing is complex (nested list structure)
- May be lower priority if rarely edited
- Consider adding as a DataSection with edit mode support

---

## Weapons Page (`/items/weapons/`)

### Status: Complete (Reference Implementation)

The weapons page is the most complete wiki implementation and serves as the reference for:
- Full edit state integration
- Pending change viewing
- Reactive calculations
- Conditional field options (smart inference)
- Image upload
- Child component passing

---

## Mobs Page (`/information/mobs/`)

### Status: Complete

Has full editing support for:
- Name, Description, Type, Planet
- Species selection
- Attack properties (AttacksPerMinute, AttackRange, AggressionRange)
- Sweatable checkbox
- Cat 4 Codex checkbox
- DefensiveProfession selection
- Maturities array editing (`MobMaturitiesEdit`)
- Spawns array editing (`MobSpawnsEdit`)
- Loots array editing (`MobLootsEdit`)

---

## Common Patterns

### Empty Entity Templates

Each new wiki page needs an empty template for create mode:

```javascript
const emptyEntity = {
  Id: null,
  Name: '',
  Properties: {
    Description: '',
    // ... entity-specific fields
  }
};
```

### Edit State Initialization

```javascript
$: if (user) {
  if (data.isCreateMode) {
    initEditState(existingChange?.data || emptyEntity, 'EntityType', true, existingChange);
  } else if (entity) {
    initEditState(entity, 'EntityType', false, null);
  }
}
```

### Active Entity Pattern

```javascript
$: activeEntity = $editMode
  ? $currentEntity
  : ($viewingPendingChange && $existingPendingChange?.data)
    ? $existingPendingChange.data
    : entity;
```

### Conditional Editing

For fields that should only be editable under certain conditions:

```svelte
{#if $editMode && someCondition}
  <InlineEdit ... />
{:else}
  {displayValue}
{/if}
```

---

## Priority Order

1. ~~**High**: Shops page - add Sections editing and conditional field disabling~~ COMPLETED
2. **Medium**: Materials page - add RefiningRecipes editing (complex nested list)
3. **Low**: Review other item pages for similar issues

---

## Other Fixes (2026-01-31)

### MobCodex Component (`MobCodex.svelte`)

- **Skill links added** - Skills in the codex table now link to their respective wiki pages
- Uses existing `getTypeLink(skill, 'Skill')` utility function for URL generation
- Added `.skill-link` CSS class for proper link styling

### MobLocations Component (`MobLocations.svelte`)

- **Map column width increased** - Changed from 50px to 80px (60px on mobile)
- Fixes issue where Map button was partially hidden behind scrollbar

### FancyTable Component (`FancyTable.svelte`)

- **Forced scrollbar visibility** - Changed `overflow-y: auto` to `overflow-y: scroll` on `.table-body`
- **Last row border removed** - Added `.last-row` class and CSS to hide bottom border on last row
- Prevents layout shift when scrollbar appears/disappears

---

## Component Consolidation (2026-01-31)

### Weapons Page - EffectsEditor Consolidation

Replaced `WeaponEffects.svelte` with generic `EffectsEditor.svelte` in weapons page:
- Uses two EffectsEditor instances (equip + use) with combined layout wrapper
- Added `.effects-combined` CSS class for side-by-side display
- Reduces code duplication - EffectsEditor is now the single source for all effect editing

### TieringEditor Component Created

Created generic `TieringEditor.svelte` for all item types with tiering support:
- Location: `nexus/src/lib/components/wiki/TieringEditor.svelte`
- Supports entity types: `Weapon`, `ArmorSet`, `MedicalTool`, `Finder`, `Excavator`
- Props: `entity`, `entityType`, `tierInfo`, `compact`, `setPieceCount`
- Full edit mode support with material amount editing
- Tier selection buttons (1-10)
- Markup calculator with cost summaries
- Extrapolation for missing tier data
- ArmorSet support with full set cost multiplier
- FancyTable-styled grid layout with integrated footer
- **Mobile responsive**: On mobile (≤899px), shows only Material, Amount, Cost columns
  - TT and MU% columns hidden to save horizontal space
  - Markup calculator hidden (uses TT values directly)
  - Materials title wrapper hidden for more space
  - Simplified footer showing just TT total

Usage:
```svelte
<TieringEditor
  entity={activeEntity}
  entityType="Finder"
  tierInfo={additional.tierInfo}
/>
```

---

## Armor Sets Page (`/items/armorsets/`)

### Status: Complete

### Implemented Changes (2026-01-31)

1. **Created SetEffectsEditor component** - Generic editor for EffectsOnSetEquip arrays
   - Supports add/edit/remove effects
   - Each effect has Name, Strength, and MinSetPieces (pieces needed to activate)
   - Groups effects by MinSetPieces in view mode
2. **Added effects data fetching** - page.js fetches effects list for dropdown
3. **Integrated SetEffectsEditor** - Replaces static display in infobox

### Data Structure

```javascript
EffectsOnSetEquip: [{
  Name: 'Effect Name',
  Values: {
    Strength: 10,
    MinSetPieces: 3,  // Number of pieces needed
    Unit: '%'
  }
}]
```

### Notes

- TieringEditor (generic) replaces ArmorSetTiers - supports Weapon, ArmorSet, MedicalTool, Finder, Excavator
- TieringEditor has full edit mode support for tier material amounts
- Old ArmorSetTiers.svelte can be deleted (no longer used)

---

## Materials Page (`/items/materials/`)

### Status: Complete

### Implemented Changes (2026-01-31)

1. **Created RefiningRecipesEditor component** - Nested list editor for recipes
   - Each recipe has Amount (product count) and Ingredients array
   - Ingredients are Item.Name + Amount pairs
   - Uses SearchableSelect for item selection
2. **Added availableItems data fetching** - page.js fetches all items for dropdown
3. **Integrated RefiningRecipesEditor** - Replaces static display, supports edit mode

### Data Structure

```javascript
RefiningRecipes: [{
  Amount: 1,  // How many of this material produced
  Ingredients: [{
    Item: { Name: 'Item Name' },
    Amount: 1  // How many of this ingredient needed
  }]
}]
```

---

## Blueprints Page (`/items/blueprints/`)

### Status: Complete

### Implemented Changes (2026-01-31)

1. **Added Book editing** - SearchableSelect with all blueprint books
2. **Added Product editing** - SearchableSelect with filtered items (excludes Blueprint and Pet types)
3. **Added Profession editing** - SearchableSelect filtered to Manufacturing professions
4. **Added Drops section** - Editable list of blueprints that can drop from crafting
5. **Updated page.js** - Fetches blueprintbooks, professions, and items for edit mode dropdowns

### Data Structure

- `Book.Name` - Reference to blueprint book
- `Product.Name` - Reference to crafted item
- `Profession.Name` - Manufacturing profession
- `Drops[]` - Array of `{ Name: string }` for dropped blueprints

---

## Remaining Parity Work

### Component Needs

1. **NestedListEditor** - For RefiningRecipes, Loots, AttachmentSlots
2. **SetEffectsEditor** - For armor set bonuses and equipment set effects

### Pages Needing Updates

| Page | Missing Features |
|------|-----------------|
| ~~Blueprints~~ | ~~Book, Product, Profession, Drops selection~~ COMPLETED |
| ~~Armor Sets~~ | ~~Set Effects~~ COMPLETED (Tiering edit deferred) |
| ~~Materials~~ | ~~RefiningRecipes~~ COMPLETED |
| ~~Tools~~ | ~~Effects on Equip/Use~~ COMPLETED (Tiering edit deferred) |
| Clothing | Set association, Set Effects |
| Medical Tools | Effects on Equip/Use |
| Vehicles | Fuel select, Attachment Slots, Defense edit |
| Attachments | Effects on Equip (all types) |
| Consumables | Mob/Profession for Capsules |
| Pets | Planet, complex Effects with unlock |
| Strongboxes | Loots array |

---

## Next Steps

1. ~~Add missing fields to Blueprints page (Book, Product, Profession)~~ DONE
2. Add tiering support to Tools page using TieringEditor
3. Add effects editing to Tools and Medical Tools pages
4. Add Set Effects editing to Armor Sets page
