# Entropia Nexus Frontend Guidelines

## Project Overview

**Framework**: SvelteKit  
**Language**: TypeScript/JavaScript  
**Build Tool**: Vite  
**Adapter**: Node.js (with precompression)  
**Port**: 3001  
**Purpose**: Web interface for Entropia Universe database and community tools

## Technology Stack

- **SvelteKit 2.0** - Full-stack framework with file-based routing
- **Svelte 4.2** - Reactive component framework
- **TypeScript 5.0** - Type-safe JavaScript
- **Vite 5.0** - Fast build tool and dev server
- **PostgreSQL** - Database via `pg` library
- **Ajv** - JSON schema validation
- **dotenv** - Environment configuration

## Project Structure

```
nexus/
├── src/
│   ├── lib/
│   │   ├── components/       # Reusable Svelte components
│   │   │   ├── services/     # Service-related components (healing, DPS, etc.)
│   │   │   ├── NavList.svelte
│   │   │   └── ...
│   │   ├── utils/            # Utility functions
│   │   │   ├── loadoutCalculations.js
│   │   │   ├── weaponValidation.js
│   │   │   └── ...
│   │   ├── style.css         # Global styles
│   │   └── util.js           # Common utilities
│   ├── routes/               # SvelteKit file-based routes
│   │   ├── +page.svelte      # Homepage
│   │   ├── +layout.svelte    # Root layout
│   │   ├── market/
│   │   │   └── services/
│   │   └── ...
│   └── static/               # Static assets
├── build/                    # Production build output
├── .env                      # Environment variables (not committed)
├── .env.development          # Development environment
└── svelte.config.js          # SvelteKit configuration
```

## Coding Guidelines

### General Principles

1. **Type Safety**: Use TypeScript where beneficial, but allow JavaScript for flexibility
2. **Null Safety**: Always check for `null` and `undefined` before accessing nested properties
3. **Reactive by Default**: Leverage Svelte's reactivity (`$:`) for computed values
4. **Component Composition**: Break complex UI into smaller, reusable components
5. **Server-Side First**: Use `+page.server.js` for data loading to leverage SSR

### Svelte-Specific Patterns

#### Null-Safe Property Access

Always check nested properties exist before accessing them:

```javascript
// ❌ Bad - will throw if weapon is null
const skill = weapon.Properties.Skill;

// ✅ Good - null-safe
if (weapon == null || !weapon.Properties || !weapon.Properties.Skill) return null;
const skill = weapon.Properties.Skill;
```

#### Reactive Declarations

Use `$:` for computed values that depend on reactive state:

```javascript
// ✅ Reactive computed value
$: canHaveWeaponAttachments = itemType === 'weapons';

// ✅ Reactive side effect
$: if (selectedService) {
  initializeServiceState();
}
```

#### Component State Management

- Use `let` for component-local state
- Use stores (`$store`) for shared state across components
- Keep state as close to usage as possible

#### Props and Exports

```javascript
export let serviceType; // Required prop
export let equipment = []; // Prop with default
```

### File Naming Conventions

- **Components**: PascalCase (e.g., `EquipmentEditor.svelte`)
- **Routes**: lowercase with hyphens (e.g., `+page.svelte`, `[[slug]]/+page.svelte`)
- **Utilities**: camelCase (e.g., `loadoutCalculations.js`)
- **Server files**: `+page.server.js`, `+layout.server.js`

### Database Access

Use the `db.js` module pattern for database queries:

```javascript
// In +page.server.js
import db from '$lib/db.js';

export async function load() {
  const items = await db.query('SELECT * FROM items');
  return { items };
}
```

### Styling Guidelines

1. **Scoped by Default**: Styles in `<style>` blocks are scoped to the component
2. **CSS Variables**: Use CSS custom properties for theming
   ```css
   background: var(--secondary-color);
   color: var(--text-color);
   ```
3. **Responsive Design**: Mobile-first approach with media queries
4. **Dark/Light Theme Support**: The site supports both dark and light themes via CSS variables

IMPORTANT: When using recurring CSS rules in one part of the site that do not need to be global, make sure to use CSS files when appropiate. If a CSS rules might make more sense to be global then add it to the globals css file instead. For rules than only duplicate 1-2 times, make a judgement call whether it makes sense to keep it local or extract it.

#### Theme CSS Variables

The following CSS variables are defined in `style.css` and should be used for consistent theming:

```css
/* Background colors */
var(--bg-color)        /* Main background */
var(--secondary-color) /* Secondary/card backgrounds */
var(--hover-color)     /* Hover states */

/* Text colors */
var(--text-color)      /* Primary text */
var(--text-muted)      /* Secondary/muted text */

/* Border colors */
var(--border-color)    /* Standard borders */

/* Accent colors */
var(--accent-color)       /* Primary accent (links, buttons) */
var(--accent-color-hover) /* Accent hover state */

/* Status colors */
var(--success-color)   /* Success states */
var(--success-bg)      /* Success backgrounds */
var(--error-color)     /* Error states */
var(--error-bg)        /* Error backgrounds */
var(--warning-color)   /* Warning states */
var(--warning-bg)      /* Warning backgrounds */
```

#### Form Elements (Dropdowns, Inputs, Buttons)

Form elements must explicitly inherit theme colors for proper dark/light mode support. Global styles in `style.css` handle this:

```css
/* Global form element styles (already in style.css) */
select, input, textarea {
  background-color: var(--bg-color, var(--secondary-color));
  color: var(--text-color);
  border: 1px solid var(--border-color, #555555);
}

select option {
  background-color: var(--bg-color, var(--secondary-color));
  color: var(--text-color);
}

button {
  color: var(--text-color);
}
```

**Important**: When styling form elements in component `<style>` blocks, always use theme variables:

```css
/* ❌ Bad - hardcoded colors break dark mode */
.my-input {
  background: white;
  color: black;
}

/* ✅ Good - uses theme variables */
.my-input {
  background: var(--bg-color);
  color: var(--text-color);
  border: 1px solid var(--border-color);
}
```

#### Scrolling Containers

The root layout uses a flexbox structure that automatically handles the menu bar height. Pages should use `height: 100%` for full-height content - no manual `calc()` needed:

```svelte
<div class="scroll-container">
  <div class="page-container">
    <!-- Page content here -->
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    padding: 1rem;
    max-width: 1000px;
    margin: 0 auto;
  }
</style>
```

**Key points:**
- Use `height: 100%` to fill the available space (the root layout handles menu offset)
- The scroll-container should wrap the page-container
- DO NOT use `calc(100vh - Xpx)` - the flexbox layout handles this automatically

#### Breadcrumbs

Whenever there is nested navigation in the navigation bar there should be breadcrumbs present at the top left of the page content. This still needs to be implemented in many places.

Careful, don't do this yet for the older sites (the ones that use the left and right side bar). It will be handled in a future rework.

#### Lazy Loading & Loading Indicators

Heavy API preloading in `+page.server.js` can cause page stuttering. Entity data (items, weapons, clothings, etc.) should be lazy loaded on the client instead.

**Entity Loader Utility**

Use the `entityLoader.js` utility for lazy loading game entities:

```javascript
import { loadEntity, loadEntities, loadAllServiceEntities } from '$lib/utils/entityLoader';
import { onMount } from 'svelte';

// Single entity
let clothings = [];
let loading = true;

onMount(async () => {
  loading = true;
  clothings = await loadEntity('clothings');
  loading = false;
});

// Multiple entities
const entities = await loadEntities(['clothings', 'weapons', 'armorSets']);

// All service-related entities
const allEntities = await loadAllServiceEntities();
```

Available entity types: `clothings`, `medicalTools`, `medicalChips`, `armorSets`, `consumables`, `weapons`, `pets`, `armors`, `armorPlatings`, `weaponAmplifiers`, `absorbers`, `weaponVisionAttachments`, `mindforceImplants`, `planets`

**Loading State Patterns**

1. **FancyTable** - Pass `loading` prop to show built-in spinner:
   ```svelte
   <FancyTable {columns} data={tableData} loading={entitiesLoading} />
   ```

2. **SkeletonTable** - Use for table placeholders:
   ```svelte
   import SkeletonTable from '$lib/components/SkeletonTable.svelte';

   {#if loading}
     <SkeletonTable rows={5} columns={4} />
   {:else}
     <ActualContent />
   {/if}
   ```

3. **Simple text** - For small areas:
   ```svelte
   {#if loading}
     <p class="loading-text">Loading...</p>
   {:else}
     <Content />
   {/if}
   ```

**What to Keep Server-Side**

- Essential page data (the service being viewed, user data)
- Data needed for SEO/initial render
- Small datasets like planet lists for dropdowns

**What to Lazy Load Client-Side**

- Large entity datasets (weapons, clothings, etc.)
- Data used for calculations/display enrichment
- Data not critical for initial page render

#### Button Styling

Use consistent button styles with theme variables:

```css
.btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  border: 1px solid transparent;
}

.btn.primary {
  background: var(--accent-color, #4a9eff);
  color: white;
  border-color: var(--accent-color, #4a9eff);
}

.btn.primary:hover:not(:disabled) {
  background: var(--accent-color-hover, #3a8eef);
}

.btn.secondary {
  background: var(--bg-color, #fff);
  color: var(--text-color, #333);
  border-color: var(--border-color, #ccc);
}

.btn.secondary:hover:not(:disabled) {
  background: var(--hover-color, #f0f0f0);
}

.btn.danger {
  background: var(--error-bg);
  color: var(--error-color);
  border-color: var(--error-color);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
```

### State Initialization Pattern

For services and complex components:

```javascript
// Reset state when data changes
$: if (selectedService) {
  // Initialize or reset component state
  activeWeapon = primaryWeaponEquip || null;
  enhancerType = 'Damage';
  enhancerTiers = [];
}
```

### Form Handling

1. Use `bind:value` for two-way binding
2. Validate on submit, not on every keystroke
3. Provide user feedback for errors and success
4. Reset forms after successful submission

### API Integration

```javascript
import { apiCall } from '$lib/util';

// Use the apiCall wrapper for consistency
const items = await apiCall(fetch, '/weapons');
```

### Error Handling

1. Always handle async errors with try/catch
2. Log errors to console for debugging
3. Show user-friendly error messages
4. Fail gracefully - don't crash the entire page (keep watch for this one in particular, fix these issues as you go)

### Performance Considerations

1. **Lazy Load**: Only load data when needed (show loading indicators when page relys on it in the meantime)
2. **Pagination**: For large lists, implement pagination or virtual scrolling
3. **Caching**: Cache API responses when appropriate
4. **Debounce**: Debounce search inputs and expensive operations
5. **Bundle Size**: Import only what you need from libraries

### Service Calculations Pattern

For DPS/Healing service calculations:

1. **Extract Pure Functions**: Place calculation logic in utility files (e.g., `loadoutCalculations.js`)
2. **Null-Safe**: All calculation functions must handle null inputs gracefully
3. **Return Null on Error**: Don't throw, return `null` or `0` for invalid calculations
4. **Chainable**: Design functions to work together in pipelines

Example:
```javascript
export function calculateHitAbility(weapon, hitSkill, skillModEnhancers) {
  if (weapon == null || !weapon.Properties || !weapon.Properties.Skill) return null;
  
  const baseAbility = hitSkill + (weapon.Properties.Skill / 50);
  const enhancerBonus = skillModEnhancers * 0.1;
  return baseAbility + enhancerBonus;
}
```

### Attachment and Enhancer Pattern

For equipment with attachments (weapons, armor):

1. Store attachments in a structured object:
   ```javascript
   attachments: {
     amplifier_id: null,
     amplifier_name: null,
     enhancerType: 'Damage', // 'Damage', 'Range', 'Economy', or ''
     // ... other attachments
   }
   ```

2. Make UI conditional on item selection:
   ```svelte
   {#if itemType === 'weapons' && itemName}
     <!-- Show weapon attachments -->
   {/if}
   ```

3. Display attachments as badges in lists

### Environment Variables

- `.env` - Production configuration
- `.env.development` - Development configuration
- Access via `import.meta.env.VITE_*` prefix for client-side
- Use server-only vars in `+page.server.js` files

## Development Workflow

### Running Locally

```bash
# Development mode with hot reload
npm run dev

# Build for production
npm run build:prod

# Preview production build
npm run preview
```

### Development Server

- Runs on `http://dev.entropianexus.com:3001`
- Hot module replacement (HMR) enabled
- Auto-restarts on file changes

### Building

- Production: `npm run build:prod` (uses `.env`)
- Development: `npm run build:dev` (uses `.env` with dev mode)
- Output: `build/` directory

## Common Patterns to Follow

### Dynamic Routes

Use `[slug]` for required parameters, `[[slug]]` for optional:

```
routes/market/services/[[slug]]/+page.svelte
```

### Conditional Rendering

```svelte
{#if condition}
  <Component />
{:else if otherCondition}
  <OtherComponent />
{:else}
  <Fallback />
{/if}
```

### Iteration with Context

```svelte
{#each items as item, index}
  {@const computed = calculateSomething(item)}
  <div>{computed}</div>
{/each}
```

You MUST place the @const right after the control structure (#if, #each, etc.)

## Testing Considerations

1. Test calculation functions in isolation
2. Verify null safety with edge cases
3. Test reactive statements with state changes
4. Validate form submissions

## E2E Testing

- Framework: **Playwright**
- Config: `nexus/playwright.config.ts`
- Tests directory: `nexus/tests/`

### Running Tests

```bash
# Run all tests
npx playwright test

# Run with UI mode
npx playwright test --ui

# Run specific test file
npx playwright test tests/menu.spec.ts

# Run tests in headed mode (visible browser)
npx playwright test --headed
```

### Writing Tests

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test('should do something', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.some-element')).toBeVisible();
  });
});
```

### Mobile Testing

Playwright supports viewport emulation for mobile testing:

```typescript
test.describe('Mobile Menu', () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test('should show burger menu on mobile', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('.burger-button')).toBeVisible();
  });
});
```

### Key Test Areas

- **Menu**: Desktop dropdowns, mobile burger menu, search, user actions
- **Login**: Discord OAuth flow, redirect handling
- **Admin Dashboard**: User management, change monitoring, sidebar navigation
- **Forms**: Validation, submission, error handling

Whenever you edit frontend code, create or update E2E tests alongside it. Test all workflows and verify element placement.

### Database Access for Testing

Test databases are available via MCP servers:
- `mcp__postgres-nexus-test__query` - Test nexus database
- `mcp__postgres-nexus-users-test__query` - Test users database

These are read-only and clone the production schema structure.

## Accessibility (A11y)

1. Use semantic HTML elements
2. Add ARIA labels where appropriate
3. Ensure keyboard navigation works
4. Maintain good color contrast
5. Add `alt` text to images

## Common Pitfalls to Avoid

1. ❌ Accessing nested properties without null checks
2. ❌ Mutating reactive state directly (use reassignment)
3. ❌ Creating circular reactive dependencies
4. ❌ Forgetting to handle async errors
5. ❌ Using `{#if}` when `{#key}` is needed for reinitialization
6. ❌ Over-using stores when component props suffice

## Database Schema Awareness

- **nexus**: Static game data (items, maps, mobs, blueprints, etc.)
- **nexus-users**: User data (accounts, shops, services, etc.)
- Join tables carefully - know which DB owns which data
- Use proper indexes for performance

## Deployment

- Adapter: Node.js with precompression enabled
- Build artifacts in `build/` directory
- Uses environment variables for configuration
- Reverse proxy recommended (nginx/Caddy)

## Reusable Components

### FancyTable

A virtualized table component with lazy loading, sorting, and filtering. Located at `src/lib/components/FancyTable.svelte`.

**Features:**
- Virtual scrolling for large datasets (handles 1000s of rows smoothly)
- Lazy loading via `fetchData` prop
- Client-side sorting and filtering
- Column-level search inputs
- Click handlers for row interactions

**Usage - Lazy Loading Mode:**

```svelte
<script>
  import FancyTable from '$lib/components/FancyTable.svelte';

  const columns = [
    { key: 'name', header: 'Name', sortable: true, searchable: true },
    { key: 'status', header: 'Status', sortable: false, width: '100px',
      formatter: (value, row) => `<span class="badge">${value}</span>` }
  ];

  async function fetchData(offset, limit, sortBy, sortOrder, filters) {
    const response = await fetch(`/api/data?offset=${offset}&limit=${limit}`);
    const data = await response.json();
    return { rows: data.items, total: data.total };
  }

  function handleRowClick(event) {
    const { row, index } = event.detail;
    console.log('Clicked:', row);
  }
</script>

<FancyTable
  {columns}
  {fetchData}
  rowHeight={44}
  pageSize={50}
  sortable={true}
  searchable={true}
  emptyMessage="No items found"
  on:rowClick={handleRowClick}
/>
```

**Column Definition:**

```typescript
interface Column {
  key: string;           // Object property key
  header: string;        // Column header text
  sortable?: boolean;    // Enable sorting (default: true)
  searchable?: boolean;  // Show search input (default: true)
  width?: string;        // CSS width (e.g., '100px', '20%')
  formatter?: (value: any, row: object) => string;  // HTML formatter
  cellClass?: (value: any, row: object) => string;  // CSS class function
}
```

**FetchData Function:**

```typescript
type FetchData = (
  offset: number,       // Starting row index
  limit: number,        // Number of rows to fetch
  sortBy: string,       // Column key to sort by
  sortOrder: 'ASC' | 'DESC',
  filters: { [key: string]: string }  // Column filter values
) => Promise<{ rows: object[], total: number }>;
```

**Props:**
- `columns` - Array of column definitions
- `data` - Static data array (for non-lazy mode)
- `fetchData` - Async function for lazy loading
- `rowHeight` - Row height in pixels (default: 44)
- `pageSize` - Rows per fetch batch (default: 50)
- `sortable` - Enable sorting (default: true)
- `searchable` - Show search inputs (default: true)
- `stickyHeader` - Keep header visible (default: true)
- `emptyMessage` - No data message (default: 'No data available')

**Events:**
- `rowClick` - `{ detail: { row, index } }`
- `rowHover` - `{ detail: { row, index } }` or null
- `sort` - `{ detail: { column, order } }`

**Important Notes:**
- Use `{#key tableKey}` wrapper and increment key to force reload
- Formatters return HTML strings - escape user input with helper function
- For global styles in formatters, use `:global(.class-name)` in parent component

### Menu Component

The main navigation menu (`src/lib/components/Menu.svelte`) includes:

**Features:**
- Desktop dropdown menus with hover
- Mobile burger menu with collapsible sections
- Search with fuzzy matching and result ranking
- User authentication state display
- Dark/light mode toggle
- Admin impersonation (admin-only)

**Mobile Breakpoints:**
- ≤900px: Mobile menu mode (burger button visible)
- ≤500px: Compact mobile styling

**Search Ranking:**
The search implements client-side fuzzy matching with the following priority:
1. Exact match (highest)
2. Starts with query
3. Word boundary match
4. Contains substring
5. Fuzzy character sequence match

## Resources

- [SvelteKit Docs](https://kit.svelte.dev/)
- [Svelte Tutorial](https://svelte.dev/tutorial)
- [Vite Docs](https://vitejs.dev/)
- Project README: `../README.md`
