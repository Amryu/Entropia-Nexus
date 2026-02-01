# Wiki Editing System

Documentation for the WYSIWYG-style inline editing system used in wiki pages.

## Overview

The wiki editing system provides inline field editing with real-time validation, change tracking, and a draft/submit workflow. Changes are tracked in a centralized store and submitted through the changes API.

---

## State Management

### wikiEditState.js Store

**Location:** `nexus/src/lib/stores/wikiEditState.js`

#### Stores

| Store | Type | Description |
|-------|------|-------------|
| `editMode` | `writable<boolean>` | Whether edit mode is active |
| `isCreateMode` | `writable<boolean>` | Whether creating a new entity (auto-enters edit mode, cannot exit) |
| `originalEntity` | `writable<object\|null>` | Original entity data before edits |
| `pendingChanges` | `writable<object>` | Changed fields: `{ path: value }` |
| `validationErrors` | `writable<object>` | Field errors: `{ path: message }` |
| `changeMetadata` | `writable<object>` | API submission metadata |
| `existingPendingChange` | `writable<object\|null>` | Pending change from API (for viewing unapproved changes) |
| `viewingPendingChange` | `writable<boolean>` | Whether viewing pending change data vs original |

#### Derived Stores

| Store | Description |
|-------|-------------|
| `hasChanges` | `true` if any pending changes exist |
| `hasErrors` | `true` if any validation errors exist |
| `currentEntity` | Original entity with pending changes applied |

#### Functions

**`initEditState(entity, entityType, userId, createMode = false)`**

Initialize editing for an entity. In create mode, edit mode is automatically enabled and cannot be exited.

```javascript
import { initEditState } from '$lib/stores/wikiEditState.js';

// Update mode (editing existing entity)
initEditState(weapon, 'Weapon', user.id, false);

// Create mode (new entity)
initEditState(emptyTemplate, 'Weapon', user.id, true);
```

**`startEdit()`** / **`cancelEdit()`**

Enter or exit edit mode.

```javascript
import { startEdit, cancelEdit } from '$lib/stores/wikiEditState.js';

startEdit();  // Enter edit mode
cancelEdit(); // Exit and discard changes
```

**`updateField(path, value)`**

Update a field value. Automatically tracks if value differs from original.

```javascript
import { updateField } from '$lib/stores/wikiEditState.js';

updateField('Properties.Weight', 3.5);
updateField('Name', 'New Name');
```

**`setFieldError(path, error)`**

Set or clear a validation error.

```javascript
import { setFieldError } from '$lib/stores/wikiEditState.js';

setFieldError('Properties.Weight', 'Weight must be positive');
setFieldError('Properties.Weight', null); // Clear error
```

**`getChangeForSubmission()`**

Get the change object ready for API submission.

```javascript
import { getChangeForSubmission } from '$lib/stores/wikiEditState.js';

const change = getChangeForSubmission();
// Returns: { id, state, type, entity, author_id, data, entityId }
```

**`getNestedValue(obj, path)`**

Utility to get a value from an object using dot notation.

```javascript
import { getNestedValue } from '$lib/stores/wikiEditState.js';

const weight = getNestedValue(entity, 'Properties.Weight'); // 3.5
```

**`resetEditState()`**

Reset all edit state (call on page unmount).

**`setExistingPendingChange(change)`**

Set the pending change object from the API for viewing.

```javascript
import { setExistingPendingChange } from '$lib/stores/wikiEditState.js';

// From page load data
$: if (pendingChange) {
  setExistingPendingChange(pendingChange);
} else {
  setExistingPendingChange(null);
}
```

**`setViewingPendingChange(viewing)`**

Toggle between viewing the pending change data and original entity.

```javascript
import { setViewingPendingChange } from '$lib/stores/wikiEditState.js';

setViewingPendingChange(true);  // View pending changes
setViewingPendingChange(false); // View original
```

---

## InlineEdit Component

**Location:** `nexus/src/lib/components/wiki/InlineEdit.svelte`

Inline editable field that integrates with the edit state store.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `any` | - | Current field value |
| `path` | `string` | - | Dot notation path (e.g., `'Properties.Weight'`) |
| `type` | `string` | `'text'` | Field type (see below) |
| `prefix` | `string` | `''` | Text before value |
| `suffix` | `string` | `''` | Text after value |
| `placeholder` | `string` | `''` | Placeholder when empty |
| `options` | `Array` | `[]` | Options for select type |
| `validate` | `Function` | `null` | Validation function |
| `min` | `number` | - | Min value for number type |
| `max` | `number` | - | Max value for number type |
| `step` | `number` | - | Step for number type |
| `required` | `boolean` | `false` | Whether field is required |

### Supported Types

| Type | Input | Description |
|------|-------|-------------|
| `text` | `<input type="text">` | Single line text |
| `number` | `<input type="number">` | Numeric value |
| `select` | `<select>` | Dropdown selection |
| `checkbox` | `<input type="checkbox">` | Boolean toggle |
| `textarea` | `<textarea>` | Multi-line text |
| `date` | `<input type="date">` | Date picker |

### Validation

Provide a validation function that returns `null` (valid) or an error message:

```svelte
<InlineEdit
  value={entity.Properties.Weight}
  path="Properties.Weight"
  type="number"
  suffix="kg"
  validate={(v) => {
    if (v === null || v === undefined) return 'Weight is required';
    if (v < 0) return 'Weight must be positive';
    if (v > 100) return 'Weight cannot exceed 100kg';
    return null;
  }}
/>
```

### Usage Examples

**Text Field:**
```svelte
<InlineEdit
  value={entity.Name}
  path="Name"
  type="text"
  required
/>
```

**Number with Suffix:**
```svelte
<InlineEdit
  value={entity.Properties.Weight}
  path="Properties.Weight"
  type="number"
  suffix="kg"
  min={0}
  max={100}
  step={0.1}
/>
```

**Select Dropdown:**
```svelte
<InlineEdit
  value={entity.Properties.Type}
  path="Properties.Type"
  type="select"
  options={[
    { value: 'Melee', label: 'Melee' },
    { value: 'Ranged', label: 'Ranged' }
  ]}
/>
```

**Checkbox:**
```svelte
<InlineEdit
  value={entity.Properties.Limited}
  path="Properties.Limited"
  type="checkbox"
/>
```

### Behavior

- **View Mode**: Displays formatted value with prefix/suffix
- **Edit Mode**: Shows appropriate input control
- **Validation**: Runs on blur/change, shows error below field
- **Change Detection**: Automatically compares to original value

---

## EditActionBar Component

**Location:** `nexus/src/lib/components/wiki/EditActionBar.svelte`

Sticky bottom bar with save/submit actions during edit mode.

### Props

| Prop | Type | Description |
|------|------|-------------|
| `onSave` | `Function\|null` | Custom save handler |
| `onSubmit` | `Function\|null` | Custom submit handler |

### Default Behavior

If no custom handlers provided:

1. **Save Draft**: `POST /api/changes` with `state: 'Draft'`
2. **Submit**: `POST /api/changes` with `state: 'Pending'`

### Custom Handlers

Override default API calls:

```svelte
<EditActionBar
  onSave={async (change) => {
    // Custom save logic
    await customSave(change);
  }}
  onSubmit={async (change) => {
    // Custom submit logic
    await customSubmit(change);
  }}
/>
```

---

## Change Workflow

### States

| State | Description |
|-------|-------------|
| `Draft` | Saved but not submitted; editable |
| `Pending` | Submitted for review; awaiting approval |
| `Approved` | Accepted; changes applied to entity |
| `Rejected` | Denied; changes discarded |

### Flow

```
┌─────────────┐     Save Draft     ┌─────────────┐
│  Editing    │ ─────────────────► │   Draft     │
│  (unsaved)  │                    │  (saved)    │
└─────────────┘                    └─────────────┘
       │                                  │
       │ Submit                           │ Submit
       ▼                                  ▼
┌─────────────────────────────────────────────────┐
│                   Pending                        │
│              (awaiting review)                   │
└─────────────────────────────────────────────────┘
       │                           │
       │ Approve                   │ Reject
       ▼                           ▼
┌─────────────┐             ┌─────────────┐
│  Approved   │             │  Rejected   │
│  (applied)  │             │ (discarded) │
└─────────────┘             └─────────────┘
```

### API Endpoints

**IMPORTANT:** The API uses URL query parameters for metadata, NOT in the body.

**Create Change:**
```
POST /api/changes?type=Create|Update&entity=Weapon&state=Draft|Pending
Body: <raw entity object>  (NOT wrapped in a change object)
```

**Update Change:**
```
PUT /api/changes/:id?state=Draft|Pending
Body: <raw entity object>
```

**Get Pending Changes:**
```
GET /api/changes?state=Pending
```

> **Note:** The `EditActionBar` component handles this format automatically. If you need custom submission logic, ensure you use the URL params + raw entity body format, not wrapped JSON.

---

## Rich Text Editing

**Location:** `nexus/src/lib/components/wiki/RichTextEditor.svelte`

TipTap-based rich text editor for entity descriptions.

### Features

| Category | Features |
|----------|----------|
| **Text Formatting** | Bold, Italic, Strikethrough |
| **Headings** | H2, H3, H4 |
| **Lists** | Bullet lists, Numbered lists |
| **Block Elements** | Blockquotes, Code blocks, Horizontal rules |
| **Links** | Internal/external links with custom label text |
| **Media** | YouTube and Vimeo video embeds |

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `content` | `string` | `''` | Initial HTML content |
| `placeholder` | `string` | `''` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable editing |

### Usage

```svelte
<script>
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import { sanitizeHtml } from '$lib/sanitize';
</script>

{#if $editMode}
  <RichTextEditor
    content={entity.Properties?.Description || ''}
    placeholder="Enter description..."
    on:change={(e) => updateField('Properties.Description', e.detail)}
  />
{:else if entity.Properties?.Description}
  <div class="description-content">
    {@html sanitizeHtml(entity.Properties.Description)}
  </div>
{/if}
```

### Video Embeds

The editor includes a custom TipTap extension for YouTube and Vimeo video embeds:

```javascript
// Supported URL formats:
// YouTube: youtube.com/watch?v=..., youtu.be/..., youtube.com/embed/...
// Vimeo: vimeo.com/..., player.vimeo.com/video/...
```

The video embed renders as an iframe wrapped in a responsive container (16:9 aspect ratio).

### Link Dialog

The link dialog supports:
- **Link Text**: Custom display text for the link
- **URL**: The destination URL
- If no text is provided, the URL is used as the display text
- All links open in a new tab with `rel="noopener noreferrer"`

---

## HTML Sanitization

Rich text content is sanitized at two points to prevent XSS attacks.

### Server-Side Sanitization

**Location:** `nexus/src/routes/api/changes/[[slug]]/+server.js`

Uses `sanitize-html` library to sanitize the Description field when changes are submitted.

```javascript
import sanitizeHtml from "sanitize-html";

const SANITIZE_CONFIG = {
  allowedTags: [
    'p', 'strong', 'em', 's', 'code', 'br',           // Basic formatting
    'h1', 'h2', 'h3', 'h4',                            // Headings
    'ul', 'ol', 'li',                                  // Lists
    'blockquote', 'pre', 'hr',                         // Block elements
    'a',                                               // Links
    'div', 'iframe'                                    // Video embeds
  ],
  allowedAttributes: {
    'a': ['href', 'target', 'rel'],
    'div': ['data-type', 'data-provider', 'data-src', 'class'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen']
  },
  allowedIframeHostnames: ['www.youtube.com', 'youtube.com', 'player.vimeo.com', 'vimeo.com'],
  transformTags: {
    'a': (tagName, attribs) => ({
      tagName: 'a',
      attribs: { href: attribs.href || '', target: '_blank', rel: 'noopener noreferrer' }
    })
  }
};
```

### Client-Side Sanitization

**Location:** `nexus/src/lib/sanitize.js`

Uses `DOMPurify` library for browser-side sanitization before rendering with `{@html}`.

```javascript
import { sanitizeHtml } from '$lib/sanitize';

// In template:
{@html sanitizeHtml(entity.Properties.Description)}
```

**Why both?**
- **Server**: Protects against forged API requests bypassing the frontend
- **Client**: Defense-in-depth for existing/legacy content, SSR safety

### Sanitization Utility API

```javascript
import { sanitizeHtml, containsHtml } from '$lib/sanitize';

// Sanitize HTML for safe rendering
const safeHtml = sanitizeHtml(unsafeHtml);

// Check if string contains HTML tags
const hasHtml = containsHtml(str); // Returns boolean
```

---

## Description Display Styles

**Location:** `nexus/src/lib/style.css`

Global styles for `.description-content` class to properly render rich text:

| Element | Styling |
|---------|---------|
| Headings (h1-h4) | Proper sizing and margins |
| Paragraphs | 0.75em vertical margins |
| Lists (ul, ol) | 1.5em left padding |
| `<strong>` | font-weight: 600 |
| `<em>` | font-style: italic |
| `<s>` | Strikethrough with muted color |
| `<code>` | Inline code with background |
| `<pre>` | Code block with border and overflow |
| `<blockquote>` | Left border accent, muted italic |
| `<hr>` | 2px border-top |
| `<a>` | Accent color, underline on hover |
| Video embeds | Responsive 16:9 container |

### Placeholder Text

```svelte
<div class="description-content placeholder">
  {entity.Name} is a weapon in Entropia Universe.
</div>
```

The `.placeholder` class applies muted color and italic styling.

---

## Implementing Inline Editing

### The Active Entity Pattern

When in edit mode, you need to display the entity with pending changes applied in real-time. The pattern accounts for three states:

1. **Edit mode**: Show `currentEntity` (original + pending edits)
2. **Viewing pending change**: Show the pending change's data
3. **Normal view**: Show original entity

```svelte
<script>
  import {
    editMode,
    currentEntity,
    initEditState,
    resetEditState,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange
  } from '$lib/stores/wikiEditState.js';
  import { onDestroy } from 'svelte';

  export let data;
  $: entity = data.entity;
  $: user = data.session?.user;
  $: pendingChange = data.pendingChange; // From server load

  // Initialize edit state when entity changes
  $: if (entity && user) {
    initEditState(entity, 'EntityType', user.id, false);
  }

  // Initialize pending change state
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
    // Auto-enable viewing for author or admin
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
  // 3. Otherwise: show original entity
  $: activeEntity = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : entity;

  // Cleanup on component destroy
  onDestroy(() => {
    resetEditState();
  });
</script>
```

**Why this matters:**
- `currentEntity` is a derived store that applies `pendingChanges` to `originalEntity`
- Without `activeEntity`, edits wouldn't be visible until save/reload
- Computed values (like DPS, totals) should use `activeEntity` to update live
- Pending change viewing lets users preview unapproved changes

**Common mistakes:**
- Using `entity` directly in template after setting up edit state (values won't update)
- Forgetting to pass `activeEntity` to child components
- Using `entity` in reactive calculations instead of `activeEntity`
- Not handling pending change viewing state separately from edit mode

### Step 1: Initialize Edit State

In your page's `+page.svelte`:

```svelte
<script>
  import { onDestroy } from 'svelte';
  import { initEditState, resetEditState, changeMetadata } from '$lib/stores/wikiEditState.js';

  export let data;
  $: entity = data.entity;
  $: user = data.session?.user;
  $: existingChange = data.existingChange; // For edit existing draft/pending

  // Empty template for create mode
  const emptyEntity = {
    Id: null,
    Name: '',
    Properties: { /* ... */ }
  };

  // Initialize edit state when entity/user changes
  $: if (user) {
    if (data.isCreateMode) {
      // Create mode: use existing draft data or empty template
      const initialData = existingChange?.data || emptyEntity;
      initEditState(initialData, 'EntityType', user.id, true);
      // If editing existing draft, set the change ID so saves update it
      if (existingChange?.id) {
        changeMetadata.update(m => ({ ...m, id: existingChange.id }));
      }
    } else if (entity) {
      // Update mode: edit existing entity
      initEditState(entity, 'EntityType', user.id, false);
    }
  }

  // Clean up on unmount
  onDestroy(() => {
    resetEditState();
  });
</script>
```

### Step 2: Add Edit Toggle

```svelte
<script>
  import { editMode, startEdit, cancelEdit } from '$lib/stores/wikiEditState.js';
</script>

{#if user?.canEdit}
  <button on:click={() => $editMode ? cancelEdit() : startEdit()}>
    {$editMode ? 'Cancel' : 'Edit'}
  </button>
{/if}
```

### Step 3: Use InlineEdit Components

```svelte
<script>
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
</script>

<div class="property-row">
  <span class="label">Weight:</span>
  <InlineEdit
    value={entity.Properties.Weight}
    path="Properties.Weight"
    type="number"
    suffix="kg"
    min={0}
  />
</div>
```

### Step 4: Add EditActionBar

```svelte
<script>
  import EditActionBar from '$lib/components/wiki/EditActionBar.svelte';
</script>

<!-- At the end of your page component -->
<EditActionBar />
```

---

## Validation Patterns

### Required Field

```svelte
<InlineEdit
  value={entity.Name}
  path="Name"
  required
  validate={(v) => !v?.trim() ? 'Name is required' : null}
/>
```

### Numeric Range

```svelte
<InlineEdit
  value={entity.Properties.Damage}
  path="Properties.Damage"
  type="number"
  min={0}
  max={1000}
  validate={(v) => {
    if (v < 0) return 'Damage cannot be negative';
    if (v > 1000) return 'Maximum damage is 1000';
    return null;
  }}
/>
```

### Dependent Validation

For fields that depend on each other:

```svelte
<script>
  import { currentEntity } from '$lib/stores/wikiEditState.js';

  function validateMinDamage(v) {
    const maxDamage = $currentEntity?.Properties?.MaxDamage || 0;
    if (v > maxDamage) return 'Min damage cannot exceed max damage';
    return null;
  }
</script>

<InlineEdit
  value={entity.Properties.MinDamage}
  path="Properties.MinDamage"
  type="number"
  validate={validateMinDamage}
/>
```

---

## Testing Edit Flow

### Manual Testing

1. Navigate to an entity page
2. Click "Edit" button
3. Modify fields, verify validation errors appear
4. Click "Save Draft" - verify draft saved
5. Click "Submit for Review" - verify state changes to Pending
6. Check admin panel for pending change

### Playwright Testing

```javascript
import { test, expect } from '../fixtures/auth';

test('can edit entity', async ({ verifiedUser }) => {
  await verifiedUser.goto('/items/weapons/armatrix-ln-35');

  // Enter edit mode
  await verifiedUser.getByRole('button', { name: 'Edit' }).click();

  // Modify a field
  await verifiedUser.getByLabel('Weight').fill('4.5');

  // Save draft
  await verifiedUser.getByRole('button', { name: 'Save Draft' }).click();
  await expect(verifiedUser.getByText('Draft saved')).toBeVisible();
});
```

---

## Implementation Checklist

Use this checklist when adding editing to a new wiki page:

### Script Setup
- [ ] Import `onDestroy` from svelte
- [ ] Import `InlineEdit` component
- [ ] Import from wikiEditState: `editMode`, `isCreateMode`, `initEditState`, `resetEditState`, `currentEntity`, `existingPendingChange`, `viewingPendingChange`, `setExistingPendingChange`, `setViewingPendingChange`, `updateField`, `changeMetadata`
- [ ] Define empty entity template for create mode
- [ ] Create reactive init for both create and update modes:
  ```javascript
  $: if (user) {
    if (data.isCreateMode) {
      initEditState(existingChange?.data || emptyEntity, 'EntityType', user.id, true);
    } else if (entity) {
      initEditState(entity, 'EntityType', user.id, false);
    }
  }
  ```
- [ ] Create reactive pending change state:
  ```javascript
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }
  ```
- [ ] Create reactive `activeEntity` with pending change viewing support:
  ```javascript
  $: activeEntity = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : entity;
  ```
- [ ] Add `onDestroy(() => { resetEditState(); });`
- [ ] Update all reactive calculations to use `activeEntity` instead of `entity`

### Template Updates
- [ ] Replace all `{entity.X}` with `{activeEntity.X}` in display code
- [ ] Wrap editable fields with `<InlineEdit>` components
- [ ] Pass `activeEntity` (not `entity`) to child components
- [ ] Ensure WikiPage has these props:
  - `editable={true}` - Enable edit UI
  - `canEdit={canEdit}` - Permission check
  - `canCreateNew={canCreateNew}` - Can create new entities
  - `userPendingCreates={userPendingCreates}` - Show pending creates in sidebar
- [ ] Add pending change banner UI (if supporting pending change viewing)

### Fields to Make Editable
For each field:
- [ ] Determine correct `type` (text, number, select, checkbox, textarea)
- [ ] Set appropriate `min`, `max`, `step` for numbers
- [ ] Add `suffix` for units (kg, %, PED, etc.)
- [ ] Define `options` array for select fields
- [ ] Add `required` and `validate` if needed
- [ ] Consider conditional options based on other field values (smart inference)

### Child Components
- [ ] Check all child components receive the active entity
- [ ] Update component props from `{entity}` to `entity={activeEntity}`

### Create Mode Support
- [ ] Add `?mode=create` route handling in `+page.js`
- [ ] Load existing draft if `?changeId=` provided
- [ ] Pass `isCreateMode` flag to component
- [ ] Show appropriate UI when no entity selected in create mode

### Testing
- [ ] Verify edit mode toggles on/off
- [ ] Verify changes appear in real-time as you type
- [ ] Verify computed values update when editing source fields
- [ ] Verify Save Draft creates a change in the database
- [ ] Verify Submit changes state to Pending
- [ ] Verify validation errors display correctly
- [ ] Verify create mode works (new entity from scratch)
- [ ] Verify editing existing drafts works
- [ ] Verify pending change viewing toggle works

---

## Reference Implementation

See the weapons page for a complete example:
- **File:** `nexus/src/routes/items/weapons/[[slug]]/+page.svelte`
- **Demonstrates:**
  - Full edit state integration with create and update modes
  - Pending change viewing with toggle banner
  - Reactive calculations using activeEntity (DPS, DPP, cost/use)
  - Conditional field options based on other fields (smart inference)
  - Image upload dialog integration
  - Child component passing (WeaponDamageGrid, WeaponEffects, WeaponTiers)
  - Panel state persistence via localStorage
  - Permission-based edit UI (canEdit, canCreateNew)

---

## Related Documentation

- [wiki-components.md](wiki-components.md) - Component architecture
- [image-upload.md](image-upload.md) - Image upload workflow
- [site-overview.md](site-overview.md) - Site architecture
