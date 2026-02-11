# UI Component Styling Guidelines

This document defines the standard patterns for styling UI components across the Entropia Nexus frontend. All components should follow these guidelines to ensure consistency and proper theming support.

## CSS Variables

Always use CSS variables for colors. Never use hardcoded color values. The theme system relies on these variables in `nexus/src/lib/style.css`:

### Core Theme Variables

```css
/* Background colors */
--primary-color     /* Main background */
--secondary-color   /* Secondary/container background */
--bg-color          /* General background (alias) */
--bg-secondary      /* Secondary container background */
--hover-color       /* Hover state background */
--disabled-color    /* Disabled element background */

/* Text colors */
--text-color        /* Primary text color */
--text-muted        /* Secondary/muted text color */

/* Border colors */
--border-color      /* Standard borders */
--border-hover      /* Hover state borders */

/* Accent color */
--accent-color       /* Links, active states, primary actions */
--accent-color-hover /* Hover state for accent elements */

/* Table-specific */
--table-header-color
--table-row-color
--table-row-color-alt
--table-row-hover-color
```

### Semantic Colors (Notifications/States)

```css
/* Error state */
--error-bg          /* Background for error messages */
--error-color       /* Text/border for error state */

/* Success state */
--success-bg        /* Background for success messages */
--success-color     /* Text/border for success state */

/* Warning state */
--warning-bg        /* Background for warning messages */
--warning-color     /* Text/border for warning state */
```

### Damage/Defense Type Colors

Used in damage grids, defense grids, and related components. These colors represent the 9 damage types plus Block:

```css
--damage-impact      /* #6b7280 - Gray for physical impact */
--damage-cut         /* #ef4444 - Red for cutting damage */
--damage-stab        /* #f97316 - Orange for stabbing damage */
--damage-penetration /* #eab308 - Yellow for penetration */
--damage-shrapnel    /* #84cc16 - Lime for shrapnel */
--damage-burn        /* #f59e0b - Amber for burn damage */
--damage-cold        /* #06b6d4 - Cyan for cold damage */
--damage-acid        /* #22c55e - Green for acid damage */
--damage-electric    /* #8b5cf6 - Purple for electric damage */
--damage-block       /* #60a5fa - Blue for block percentage */
```

Use these in damage/defense components:
```svelte
<div style="color: var(--damage-burn)">Burn: 10.5</div>
<div style="border-left-color: var(--damage-electric)">Electric Defense</div>
```

## Form Controls

### Basic Input Styling

All inputs, selects, and textareas inherit from global styles but should include:

**IMPORTANT:** Any input with `width: 100%` MUST also have `box-sizing: border-box`. Without it, padding and border are added on top of the 100% width, causing the element to overflow its container.

```css
input, select, textarea {
  background-color: var(--bg-color, var(--secondary-color));
  color: var(--text-color);
  border: 1px solid var(--border-color);
  padding: 0.5rem;
  border-radius: 4px;
  box-sizing: border-box;  /* always include when using width: 100% */
}

input:focus, select:focus, textarea:focus {
  border-color: var(--accent-color);
  outline: none;
}
```

### Select Dropdowns

Select elements must have proper option styling for both themes:

```css
select option {
  background-color: var(--secondary-color);
  color: var(--text-color);
}
```

### Form Layout

Standard form row pattern using grid:

```css
.form-row {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 8px;
  align-items: center;
  margin: 8px 0;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.form-group label {
  font-weight: 500;
  color: var(--text-color);
}
```

## Buttons

### Standard Button

```css
button {
  background-color: var(--primary-color);
  color: var(--text-color);
  border: 1px solid var(--text-color);
  cursor: pointer;
  padding: 0.5rem 1rem;
  border-radius: 4px;
}

button:hover {
  background-color: var(--hover-color);
}

button:disabled {
  background-color: var(--disabled-color);
  cursor: not-allowed;
  opacity: 0.7;
}
```

### Primary/Action Button

```css
.btn-primary {
  background-color: var(--accent-color);
  color: white;
  border: none;
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--accent-color-hover);
}
```

### Danger Button

```css
.btn-danger {
  background-color: var(--error-bg);
  color: var(--error-color);
  border: 1px solid var(--error-color);
}

.btn-danger:hover:not(:disabled) {
  background-color: var(--error-color);
  color: white;
}
```

## Dialogs/Modals

### Structure

Dialogs use a modal-overlay pattern with proper accessibility:

```svelte
{#if show}
  <div
    class="modal-overlay"
    role="button"
    tabindex="0"
    on:click={(e) => {
      if (e.target.classList.contains('modal-overlay')) close();
    }}
    on:keydown={(e) => {
      if (e.key === 'Escape') close();
    }}
  >
    <div class="modal" role="dialog" aria-modal="true">
      <h3>Dialog Title</h3>
      <!-- Content -->
      <div class="actions">
        <button on:click={close}>Cancel</button>
        <button on:click={submit}>Submit</button>
      </div>
    </div>
  </div>
{/if}
```

### Styling

```css
.modal-overlay {
  position: absolute;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 3;
}

.modal {
  background: var(--secondary-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1.5rem;
  width: 420px;
  max-width: calc(100% - 32px);
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
}

.modal h3 {
  margin-top: 0;
  margin-bottom: 1rem;
}

.modal .actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 1rem;
}
```

## Notifications/Banners

**IMPORTANT**: NEVER use JavaScript `alert()`. Use inline notifications or banners instead.

### Error Banner

```svelte
{#if error}
  <div class="error-banner">{error}</div>
{/if}
```

```css
.error-banner {
  background: var(--error-bg);
  color: var(--error-color);
  padding: 0.75rem 1rem;
  border-radius: 4px;
  border: 1px solid var(--error-color);
  margin-bottom: 1rem;
}
```

### Success Banner

```svelte
{#if successMessage}
  <div class="success-banner">{successMessage}</div>
{/if}
```

```css
.success-banner {
  background: var(--success-bg);
  color: var(--success-color);
  padding: 0.75rem 1rem;
  border-radius: 4px;
  border: 1px solid var(--success-color);
  margin-bottom: 1rem;
}
```

### Warning Banner

```css
.warning-banner {
  background: var(--warning-bg);
  color: var(--warning-color);
  padding: 0.75rem 1rem;
  border-radius: 4px;
  border: 1px solid var(--warning-color);
  margin-bottom: 1rem;
}
```

### Inline Messages (smaller, within forms)

```css
.message {
  margin-top: 1rem;
  padding: 0.75rem;
  border-radius: 4px;
  font-size: 0.9rem;
}

.error-message {
  background: var(--error-bg);
  border: 1px solid var(--error-color);
  color: var(--error-color);
}

.success-message {
  background: var(--success-bg);
  border: 1px solid var(--success-color);
  color: var(--success-color);
}
```

## Page Structure

### Scroll Container Pattern

Pages with scrollable content use the scroll-container pattern:

```svelte
<div class="scroll-container">
  <div class="page-container">
    <!-- Page content -->
  </div>
</div>
```

```css
.scroll-container {
  height: 100%;        /* fills .app-content flex area — NEVER use calc(100vh - Npx) */
  overflow-y: auto;
}

.page-container {
  padding: 1rem;
  padding-bottom: 2rem;
  max-width: 1200px;  /* or appropriate max width */
  margin: 0 auto;
}
```

### Breadcrumbs

Standard breadcrumb navigation:

```svelte
<div class="breadcrumb">
  <a href="/market/services">Services</a>
  <span>/</span>
  <span>Current Page</span>
</div>
```

```css
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.breadcrumb a {
  color: var(--accent-color);
  text-decoration: none;
}

.breadcrumb a:hover {
  text-decoration: underline;
}
```

### Back Navigation

Use buttons (not links) for back navigation:

```svelte
<button class="back-btn" on:click={() => goto('/market/services')}>
  Back to Services
</button>
```

```css
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-color);
  cursor: pointer;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.back-btn:hover {
  background: var(--hover-color);
  border-color: var(--border-hover);
}
```

## Tables

### Table.svelte (Basic Table)

Basic table wrapper for simple data display:

```svelte
<div class="table-wrapper">
  <Table {header} {data} {options} />
</div>
```

```css
.table-wrapper {
  background: var(--secondary-color);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem;
  overflow-x: auto;
}
```

### FancyTable.svelte (Virtualized Table)

Modern table component with virtual scrolling, lazy loading, and reactive sorting.

**Location:** `nexus/src/lib/components/FancyTable.svelte`

**Props:**
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| columns | Array | [] | Column definitions |
| data | Array | [] | Row data (for non-lazy mode) |
| fetchData | Function | null | Async fetch function for lazy loading |
| rowHeight | number | 44 | Row height in pixels |
| pageSize | number | 50 | Rows to fetch at a time |
| sortable | boolean | true | Enable column sorting |
| searchable | boolean | true | Enable column filter inputs |
| stickyHeader | boolean | true | Keep header visible when scrolling |
| emptyMessage | string | 'No data available' | Message when no data |

**Column Definition:**
```javascript
const columns = [
  {
    key: 'name',           // Data property key
    header: 'Name',        // Column header text
    sortable: true,        // Enable sorting (default: true)
    searchable: true,      // Show filter input (default: true)
    width: '200px',        // Fixed width (optional)
    formatter: (value, row) => value,  // Format cell content
    cellClass: (value, row) => ''      // Dynamic cell class
  }
];
```

**Lazy Loading Mode:**
```javascript
// fetchData(offset, limit, sortBy, sortOrder, filters) => { rows, total }
async function fetchUsers(offset, limit, sortBy, sortOrder, filters) {
  const page = Math.floor(offset / limit) + 1;
  const response = await fetch(`/api/users?page=${page}&limit=${limit}&sortBy=${sortBy}`);
  const data = await response.json();
  return { rows: data.users, total: data.total };
}
```

**Events:**
- `on:rowClick` - `{ detail: { row, index } }`
- `on:rowHover` - `{ detail: { row, index } | null }`
- `on:sort` - `{ detail: { column, order } }`

**Filter Operators:**
Column filters support operators:
- `!term` - NOT (exclude matches)
- `>=value` - Greater than or equal
- `<=value` - Less than or equal
- `>value` - Greater than
- `<value` - Less than
- `=value` - Exact match

**Usage Example:**
```svelte
<FancyTable
  {columns}
  fetchData={fetchUsers}
  rowHeight={56}
  pageSize={50}
  emptyMessage="No users found"
  on:rowClick={handleRowClick}
/>
```

**Key Features:**
- Virtual scrolling (only renders visible rows + buffer)
- Lazy loading (fetches data as user scrolls)
- Reactive sorting (no page reloads)
- Column-based filtering with debounce
- Sticky header
- Built-in loading spinner and empty state

### Empty State

```css
.empty-state {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
}
```

## Status Badges

For status indicators (e.g., request status, availability):

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.5rem;
  border-radius: 9999px;  /* pill shape */
  font-weight: 500;
  font-size: 0.75rem;
}

.badge-success {
  background-color: var(--success-bg);
  color: var(--success-color);
  border: 1px solid var(--success-color);
}

.badge-warning {
  background-color: var(--warning-bg);
  color: var(--warning-color);
  border: 1px solid var(--warning-color);
}

.badge-error {
  background-color: var(--error-bg);
  color: var(--error-color);
  border: 1px solid var(--error-color);
}

.badge-muted {
  background-color: var(--bg-secondary);
  color: var(--text-muted);
  border: 1px solid var(--border-color);
}
```

## Loading States

### Spinner

```css
.loading {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.3);
}

.spinner {
  border: 4px solid var(--border-color);
  border-top: 4px solid var(--accent-color);
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
```

### Loading Text

```svelte
{#if isLoading}
  <div class="loading-text">Loading...</div>
{/if}
```

```css
.loading-text {
  color: var(--text-muted);
  text-align: center;
  padding: 2rem;
}
```

## Responsive Design

### Mobile Breakpoints

Standard breakpoints:
- **900px**: Main navigation menu switches to burger menu
- **768px**: Admin sidebar becomes collapsible
- **600px**: Further mobile optimizations

```css
@media (max-width: 900px) {
  /* Menu switches to burger menu */
  /* Desktop menu items hidden, mobile menu activated */
}

@media (max-width: 768px) {
  .page-container {
    padding: 0.5rem;
  }

  /* Hide less important columns in tables */
  .table-wrapper :global(table tbody tr td:nth-child(n)),
  .table-wrapper :global(table thead tr th:nth-child(n)) {
    /* Selectively hide columns */
  }

  /* Stack form rows */
  .form-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  /* Further mobile optimizations */
}
```

### Mobile Navigation (Menu.svelte)

The main navigation (`Menu.svelte`) uses a responsive design pattern:

**Desktop (> 900px):**
- Horizontal menu with dropdown categories
- Search input in navbar
- User avatar with dropdown menu
- Dark/light mode toggle visible

**Mobile (≤ 900px):**
- Burger menu button replaces horizontal navigation
- Full-screen mobile menu with collapsible sections
- Search field at top of mobile menu
- Search mode: when focused, hides navigation and shows categorized search results
- User section at bottom with avatar, actions, and dark/light mode toggle
- Discord login button hidden (available via mobile menu)
- Menu auto-closes when switching back to desktop width

**Key Implementation Details:**
```javascript
// Auto-close mobile menu when switching to desktop
onMount(() => {
  mediaQuery = window.matchMedia('(max-width: 900px)');
  mediaQuery.addEventListener('change', handleMediaChange);
});

function handleMediaChange(e) {
  if (!e.matches) {
    closeMobileMenu(); // Close when switching to desktop
  }
}
```

**Mobile Search Mode:**
- Input focus enters search mode (hides navigation, shows results)
- Categorized results with smart limiting (max 5 per category, 20 total)
- Cancel button exits search mode
- Results display category headers with counts

### Admin Sidebar (Mobile)

The admin panel uses a collapsible sidebar on mobile (≤ 768px):

```css
@media (max-width: 768px) {
  .admin-sidebar {
    position: fixed;
    top: 0;
    left: 0;
    bottom: 0;
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }

  .admin-sidebar.open {
    transform: translateX(0);
  }
}
```

**Features:**
- Fixed floating toggle button (bottom-left)
- Overlay backdrop when open
- Slides in from left
- Closes on navigation item click

## Rich Text / Description Content

Wiki pages use `.description-content` class for rendering rich text from the TipTap editor.

**Location:** Styles defined in `nexus/src/lib/style.css`

**Usage:**
```svelte
<script>
  import { sanitizeHtml } from '$lib/sanitize';
</script>

{#if entity.Properties?.Description}
  <div class="description-content">
    {@html sanitizeHtml(entity.Properties.Description)}
  </div>
{:else}
  <div class="description-content placeholder">
    Default placeholder text...
  </div>
{/if}
```

**Supported Elements:**

| Element | Styling |
|---------|---------|
| `<p>` | 0.75em vertical margins, line-height: 1.6 |
| `<h1>-<h4>` | Proper sizing (1.75em down to 1.1em) |
| `<ul>`, `<ol>` | 1.5em left padding |
| `<strong>` | font-weight: 600 |
| `<em>` | font-style: italic |
| `<s>` | Strikethrough with muted color |
| `<code>` | Inline code with secondary background |
| `<pre>` | Code block with border, monospace font |
| `<blockquote>` | Accent-colored left border, italic |
| `<hr>` | 2px border-top |
| `<a>` | Accent color, underline on hover |
| Video embeds | Responsive 16:9 iframe container |

**Important:** Always sanitize HTML before rendering with `{@html}`:
```javascript
import { sanitizeHtml } from '$lib/sanitize';
{@html sanitizeHtml(htmlContent)}
```

---

## Common Patterns Checklist

When creating new components, verify:

- [ ] All colors use CSS variables, not hardcoded values
- [ ] Text is readable in both light and dark mode
- [ ] Form controls have proper focus states
- [ ] Buttons have hover and disabled states
- [ ] Error/success states use banner patterns (not `alert()`)
- [ ] Dialogs have proper overlay and keyboard handling
- [ ] Tables are wrapped for horizontal scroll
- [ ] Page uses scroll-container pattern
- [ ] Breadcrumbs are consistent with other pages
- [ ] Back navigation uses buttons with clear destination text
