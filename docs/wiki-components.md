# Wiki Components Architecture

Documentation for the wiki-style page system used across Items and Information sections.

## Overview

The wiki system provides a consistent, mobile-responsive layout for displaying entity data with inline editing capabilities. It follows a hybrid Wikipedia-style design with collapsible sections and floating infoboxes.

## Component Hierarchy

```
WikiPage.svelte (main container)
├── WikiHeader.svelte (breadcrumbs, title, edit toggle)
├── WikiNavigation.svelte (sidebar: search, filters, virtualized item list)
│   └── MobileDrawer.svelte (slide-in drawer for mobile navigation)
├── WikiSEO.svelte (meta tags, JSON-LD structured data)
├── EntityImageUpload.svelte (entity image display + upload in edit mode)
├── EntityInfobox.svelte (icon + key stats)
├── DataSection.svelte (collapsible content sections)
│   └── [Entity-specific components]
├── EditActionBar.svelte (sticky save/cancel bar)
└── HistoryPanel.svelte (version history viewer)
```

---

## Core Components

### WikiPage.svelte

Main responsive container that orchestrates the wiki layout.

**Location:** `nexus/src/lib/components/wiki/WikiPage.svelte`

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `title` | `string` | Page title (e.g., "Weapons") |
| `breadcrumbs` | `Array<{label, href}>` | Breadcrumb navigation |
| `entity` | `object\|null` | The entity being displayed |
| `entityType` | `string` | Type identifier (e.g., "weapon", "mob") |
| `basePath` | `string` | Base URL for entity links |
| `navItems` | `Array` | Items for sidebar navigation |
| `user` | `object\|null` | Current user (for edit permissions) |
| `editable` | `boolean` | Whether the page supports editing (shows login hint if not authenticated) |
| `canEdit` | `boolean` | Whether the current user can edit (has permission) |
| `canCreateNew` | `boolean` | Whether user can create new entities (may be limited by pending creates count) |
| `userPendingCreates` | `Array` | User's pending create changes to show at top of sidebar |
| `navFilters` | `Array` | Filter definitions for navigation |
| `navTableColumns` | `Array\|null` | Custom columns for sidebar expanded table view |
| `navColumnFormatters` | `Object\|null` | Custom value formatters for sidebar columns |
| `navGetItemHref` | `Function\|null` | Custom link generator for sidebar items |
| `onSave` | `Function\|null` | Custom save handler for EditActionBar |
| `onSubmit` | `Function\|null` | Custom submit handler for EditActionBar |

**Usage:**
```svelte
<WikiPage
  title="Weapons"
  breadcrumbs={[{label: 'Items', href: '/items'}]}
  entity={weapon}
  entityType="Weapon"
  basePath="/items/weapons"
  navItems={allWeapons}
  navFilters={navFilters}
  user={data.session?.user}
  editable={true}
  canEdit={canEdit}
  canCreateNew={canCreateNew}
  userPendingCreates={userPendingCreates}
>
  <!-- Content slots -->
</WikiPage>
```

---

### WikiNavigation.svelte

Sidebar with search, filters, and virtualized item list. Supports expanded table view mode.

**Location:** `nexus/src/lib/components/wiki/WikiNavigation.svelte`

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `items` | `Array` | Items to display in the list |
| `filters` | `Array` | Filter options (see below) |
| `basePath` | `string` | Base path for item links |
| `title` | `string` | Navigation title |
| `currentSlug` | `string\|null` | Currently selected item |
| `expanded` | `boolean` | Whether sidebar is in table view mode |
| `tableColumns` | `Array\|null` | Custom columns for expanded view |
| `columnFormatters` | `Object\|null` | Custom value formatters |
| `customGetItemHref` | `Function\|null` | Custom link generator |

**Filter Structure:**
```javascript
filters = [
  {
    key: 'Properties.Type',      // Field path to filter on
    label: 'Type',               // Display label
    values: [                    // Filter options
      { value: 'Melee', label: 'Melee' },
      { value: 'Ranged', label: 'Ranged' }
    ],
    multiSelect: false,          // Allow multiple selections
    filterFn: (item, value) => true,  // Custom filter function
    sortFn: (item, value) => 0,  // Custom sort function
    helpText: ['Line 1', '...']  // Help popover content
  }
]
```

**Smart Filter Syntax (Expanded Mode):**
- `>50` - Greater than 50
- `<100` - Less than 100
- `>=10`, `<=20` - Greater/less or equal
- `!melee` - Does not contain
- `=ranged` - Exact match
- `sword` - Contains text

**Events:**
- `select` - Item selected (detail: `{ item }`)
- `toggleExpand` - Expand/collapse button clicked

---

### DataSection.svelte

Collapsible content section with icon and title.

**Location:** `nexus/src/lib/components/wiki/DataSection.svelte`

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `title` | `string` | `''` | Section title |
| `icon` | `string` | `''` | Icon emoji or SVG |
| `expanded` | `boolean` | `true` | Initial expanded state |
| `collapsible` | `boolean` | `true` | Whether section can collapse |
| `subtitle` | `string` | `''` | Secondary text |
| `allowOverflow` | `boolean` | `false` | Allow content to overflow (for dropdowns) |

**Usage:**
```svelte
<DataSection title="Damage & DPS" icon="⚔️" expanded={true}>
  <WeaponDamageGrid {weapon} />
  <WeaponCalculator {weapon} />
</DataSection>
```

**Dropdown Overflow Pattern:**

When a DataSection contains a dropdown (like SearchableSelect) that needs to overflow the container, use the `allowOverflow` prop. Typically this should only be enabled in edit mode:

```svelte
<DataSection title="Facilities" allowOverflow={$editMode}>
  <SearchableSelect ... />
</DataSection>
```

This sets `overflow: visible` on the section, allowing dropdowns to display properly without being clipped.

---

### EntityInfobox.svelte

Compact infobox displaying entity icon and key stats. Adapts for mobile (horizontal) and desktop (vertical/floating).

**Location:** `nexus/src/lib/components/wiki/EntityInfobox.svelte`

**Props:**

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `entity` | `object\|null` | `null` | Entity object |
| `name` | `string` | `''` | Entity name (fallback) |
| `type` | `string` | `''` | Type label (e.g., "Melee Weapon") |
| `subtype` | `string` | `''` | Subtype/class (e.g., "Sword") |
| `imageUrl` | `string\|null` | `null` | Image URL |
| `stats` | `Array` | `[]` | Key stats `[{label, value, suffix?}]` |
| `compact` | `boolean` | `false` | Horizontal layout mode |
| `variant` | `string` | `'default'` | Layout variant: 'default', 'floating', 'card' |

**Variants:**
- `default` - Standard vertical layout
- `floating` - Wikipedia-style right sidebar (280px, floats right)
- `card` - Full width, centered content
- `compact` - Horizontal layout (icon left, content right)

**Slots:**
- `extra` - Additional content after stats

---

### EditActionBar.svelte

Sticky bottom bar shown during edit mode with save/submit actions.

**Location:** `nexus/src/lib/components/wiki/EditActionBar.svelte`

**Props:**

| Prop | Type | Description |
|------|------|-------------|
| `onSave` | `Function\|null` | Custom save handler |
| `onSubmit` | `Function\|null` | Custom submit handler |

**Actions:**
- **Save Draft** - Saves changes with state `Draft`
- **Submit for Review** - Saves with state `Pending`
- **Cancel** - Discards changes (with confirmation if unsaved)

---

### WikiSEO.svelte

Generates meta tags and JSON-LD structured data for SEO.

**Location:** `nexus/src/lib/components/wiki/WikiSEO.svelte`

**Generates:**
- `<title>` tag
- `<meta name="description">`
- `<link rel="canonical">`
- Open Graph tags (og:title, og:description, og:image)
- Twitter Card tags
- JSON-LD structured data (ItemPage, BreadcrumbList)

---

## Entity-Specific Components

### Weapons (`/wiki/weapons/`)

| Component | Description |
|-----------|-------------|
| `WeaponDamageGrid.svelte` | 9 damage types display with colored bars |
| `WeaponEconomy.svelte` | TT, decay, cost/use display |
| `WeaponEffects.svelte` | Effects on equip/use lists |
| `WeaponTiers.svelte` | Tier progression table |

### Mobs (`/wiki/mobs/`)

| Component | Description |
|-----------|-------------|
| `MobMaturities.svelte` | Maturity progression table (HP, Level, attacks) |
| `MobLocations.svelte` | Spawn locations with waypoint copy, map links |
| `MobLoots.svelte` | Drop table with frequency badges |
| `MobCodex.svelte` | Interactive codex calculator (25 ranks) |
| `MobDamageGrid.svelte` | Damage type breakdown visualization |
| `MapLinkButton.svelte` | Link to view spawn on interactive map |

### Armor (`/wiki/armor/`)

| Component | Description |
|-----------|-------------|
| `ArmorSetPieces.svelte` | Armor set piece list with slot, name, MaxTT display |
| `SetEffectsEditor.svelte` | Section-based set effects grouped by piece count |

### Tiering (Generic)

| Component | Description |
|-----------|-------------|
| `TieringEditor.svelte` | Generic tiering editor for weapons, armor sets, medical tools, finders, excavators. Shows materials per tier with markup calculator. |

### Professions (`/wiki/professions/`)

| Component | Description |
|-----------|-------------|
| `ProfessionSkills.svelte` | Contributing skills table |
| `ProfessionUnlocks.svelte` | Level unlock thresholds |

### Skills (`/wiki/skills/`)

| Component | Description |
|-----------|-------------|
| `SkillProfessions.svelte` | Professions this skill contributes to |
| `SkillUnlockedBy.svelte` | How to unlock this skill |

### Vendors (`/wiki/vendors/`)

| Component | Description |
|-----------|-------------|
| `VendorOffers.svelte` | Items sold by vendor with prices |

### Shops (`/wiki/shops/`)

| Component | Description |
|-----------|-------------|
| `ShopInventory.svelte` | Shop inventory display |
| `ShopOwnerDialog.svelte` | Shop owner management dialog |
| `ShopManagersDialog.svelte` | Shop managers management |
| `ShopInventoryDialog.svelte` | Inventory editing dialog |

---

## Calculators

Located in `nexus/src/lib/components/wiki/calculators/`:

| Calculator | Entity | Features |
|------------|--------|----------|
| `WeaponCalculator.svelte` | Weapons | DPS, DPP, Cost/Use, Total Uses with skill slider |

---

## Utility Components

### RichTextEditor.svelte

TipTap-based WYSIWYG editor for entity descriptions.

**Location:** `nexus/src/lib/components/wiki/RichTextEditor.svelte`

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `content` | `string` | `''` | Initial HTML content |
| `placeholder` | `string` | `''` | Placeholder when empty |
| `disabled` | `boolean` | `false` | Disable editing |

**Features:**
- Bold, italic, strikethrough
- Headings (H2, H3, H4)
- Bullet and numbered lists
- Blockquotes and code blocks
- Horizontal rules
- Links with custom label text
- YouTube/Vimeo video embeds

**Events:**
- `change` - Fires with HTML content when editor content changes

See [wiki-editing.md](wiki-editing.md) for detailed usage.

---

### WaypointCopyButton.svelte

Button to copy `/wp` command to clipboard for in-game waypoints.

**Location:** `nexus/src/lib/components/wiki/WaypointCopyButton.svelte`

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `waypoint` | `string` | The waypoint command to copy |

---

### EntityImageUpload.svelte

Consolidated component for displaying and uploading entity images. Handles all image state management internally including pending images, approval status, and upload dialog.

**Location:** `nexus/src/lib/components/wiki/EntityImageUpload.svelte`

**Props:**
| Prop | Type | Description |
|------|------|-------------|
| `entityId` | `string\|number\|null` | The entity's ID |
| `entityName` | `string` | The entity's name (for display) |
| `entityType` | `string` | Entity type in lowercase (e.g., "weapon", "mob", "armorset") |
| `user` | `object\|null` | Current user object |
| `isEditMode` | `boolean` | Whether edit mode is active |
| `isCreateMode` | `boolean` | Whether creating a new entity |

**Features:**
- Displays approved entity image or placeholder icon
- Shows upload overlay on hover during edit mode
- Handles pending image preview for current user
- Displays "Pending" banner when user has uploaded a pending image
- Shows "Available after approval" message during create mode
- Integrates with ImageUploadDialog for cropping
- Responsive sizing (320px max, adapts on mobile)

**Events:**
- `uploaded` - Fires when image is successfully uploaded (detail: `{ tempPath, previewUrl }`)

**Usage:**
```svelte
<script>
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';
  import { editMode } from '$lib/stores/wikiEditState';
</script>

<EntityImageUpload
  entityId={activeEntity?.Id}
  entityName={activeEntity?.Name}
  entityType="weapon"
  {user}
  isEditMode={$editMode}
  {isCreateMode}
/>
```

**Image URL Pattern:**
- SEO/approved images: `/api/img/{entityType}/{entityId}`
- Pending images: Handled internally by component

**Notes:**
- Component handles its own styling (aspect-ratio: 1, centered in infobox)
- Automatically fetches pending image status when edit mode is entered
- Works with the approval workflow defined in [image-upload.md](image-upload.md)

---

## HTML Sanitization Utility

**Location:** `nexus/src/lib/sanitize.js`

Client-side HTML sanitization for rendering rich text descriptions safely.

**Functions:**

| Function | Description |
|----------|-------------|
| `sanitizeHtml(html)` | Sanitize HTML string, returns safe HTML for `{@html}` |
| `containsHtml(str)` | Check if string contains HTML tags |

**Usage:**
```svelte
<script>
  import { sanitizeHtml } from '$lib/sanitize';
</script>

{#if entity.Properties?.Description}
  <div class="description-content">
    {@html sanitizeHtml(entity.Properties.Description)}
  </div>
{/if}
```

**Important:** Always use `sanitizeHtml()` when rendering user-provided HTML with `{@html}`. This prevents XSS attacks from malicious content.

---

## State Management

Edit state is managed via the `wikiEditState.js` store. See [wiki-editing.md](wiki-editing.md) for details.

---

## Adding a New Entity Type

### Step 1: Create Entity-Specific Components

Create a folder in `nexus/src/lib/components/wiki/{entityType}/` with display components:

```
wiki/{entityType}/
├── {Entity}MainContent.svelte    # Primary content display
├── {Entity}Properties.svelte     # Key properties section
└── {Entity}Related.svelte        # Related items section
```

### Step 2: Create the Page Route

Create route at `nexus/src/routes/{section}/{entityType}/[[slug]]/`:

```
{entityType}/[[slug]]/
├── +page.js       # Data loader
└── +page.svelte   # Page component using WikiPage
```

### Step 3: Page Component Template

```svelte
<script>
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import { editMode } from '$lib/stores/wikiEditState';
  // Import entity-specific components

  export let data;
  $: entity = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: isCreateMode = data.isCreateMode || false;

  // SEO Image URL
  $: entityImageUrl = entity?.Id ? `/api/img/entitytype/${entity.Id}` : null;
</script>

<WikiSEO
  title={entity?.Name || 'Entity Type'}
  description={entity?.Properties?.Description || ''}
  entityType="EntityType"
  {entity}
  imageUrl={entityImageUrl}
  canonicalUrl="https://entropianexus.com/section/entitytype"
/>

<WikiPage
  title="Entity Types"
  breadcrumbs={[{label: 'Section', href: '/section'}]}
  {entity}
  entityType="EntityType"
  basePath="/section/entitytype"
  navItems={allItems}
  {user}
  editable={true}
  canEdit={user?.verified || user?.isAdmin}
>
  {#if entity || isCreateMode}
    <div class="layout-a">
      <aside class="wiki-infobox-float">
        <div class="infobox-header">
          <EntityImageUpload
            entityId={entity?.Id}
            entityName={entity?.Name}
            entityType="entitytype"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit value={entity?.Name} path="Name" type="text" />
          </div>
        </div>
        <!-- Stats sections -->
      </aside>

      <article class="wiki-article">
        <DataSection title="Main Content" icon="📊">
          <!-- Entity-specific content -->
        </DataSection>
      </article>
    </div>
  {:else}
    <!-- List/browse view when no entity selected -->
  {/if}
</WikiPage>
```

### Step 4: Data Loader Template

```javascript
// +page.js
import { apiCall } from '$lib/util';

export async function load({ fetch, params }) {
  const items = await apiCall(fetch, '/entitytype');

  let entity = null;
  if (params.slug) {
    entity = items.find(i => i.Name === decodeURIComponent(params.slug)) || null;
  }

  return { items, entity };
}
```

### Step 5: Update Navigation

Add the new entity type to the relevant overview page (`/items/+page.svelte` or `/information/+page.svelte`).

---

## Responsive Breakpoints

All wiki components use the global 900px breakpoint:

```css
/* Desktop (> 900px) */
.component { /* desktop styles */ }

/* Mobile (≤ 899px) */
@media (max-width: 899px) {
  .component { /* mobile styles */ }
}
```

**Mobile Behaviors:**
- Navigation becomes hamburger menu via MobileDrawer
- EntityInfobox switches from floating to full-width
- DataSections collapse by default
- EditActionBar stacks vertically

---

## CSS Variables

Wiki components use variables from `nexus/src/lib/style.css`:

| Variable | Usage |
|----------|-------|
| `--text-color` | Primary text |
| `--text-muted` | Secondary/label text |
| `--bg-color` | Page background |
| `--secondary-color` | Card/panel backgrounds |
| `--border-color` | Borders and dividers |
| `--accent-color` | Interactive elements, badges |
| `--hover-color` | Hover states |
| `--error-color` | Validation errors |
| `--success-color` | Success states |
| `--warning-color` | Warning states |

---

## Related Documentation

- [wiki-editing.md](wiki-editing.md) - WYSIWYG editing system
- [image-upload.md](image-upload.md) - Image upload workflow
- [ui-styling.md](ui-styling.md) - CSS variable reference
- [information.md](information.md) - Information section details
- [items.md](items.md) - Items section details
