<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { encodeURIComponentSafe, getTypeLink } from '$lib/util';

  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import FancyTable from '$lib/components/FancyTable.svelte';

  export let data;

  $: enumeration = data.object;
  $: allItems = data.allItems || [];
  $: user = data.session?.user;
  $: activeEnumeration = enumeration;
  $: navItems = allItems;

  $: breadcrumbs = [
    { label: 'Information', href: '/information' },
    { label: 'Enumerations', href: '/information/enumerations' },
    ...(activeEnumeration?.Name ? [{ label: activeEnumeration.Name }] : [])
  ];

  $: canonicalUrl = activeEnumeration?.Name
    ? `https://entropianexus.com/information/enumerations/${encodeURIComponentSafe(activeEnumeration.Name)}`
    : 'https://entropianexus.com/information/enumerations';

  const navFilters = [
    {
      key: 'Properties.Source',
      label: 'Source',
      values: [
        { value: 'builtin', label: 'Built-in' },
        { value: 'custom', label: 'Custom' }
      ]
    }
  ];

  const navTableColumns = [
    {
      key: 'source',
      header: 'Source',
      width: '90px',
      getValue: (item) => item?.Properties?.Source || '-',
      format: (v) => v || '-'
    },
    {
      key: 'unit',
      header: 'Unit',
      width: '90px',
      getValue: (item) => item?.Properties?.Unit || '-',
      format: (v) => v || '-'
    }
  ];

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function normalizeLocationType(type) {
    return String(type || '')
      .trim()
      .toLowerCase();
  }

  function buildLocationHref(ref) {
    if (!ref?.name || !ref?.locationType) return null;
    const type = normalizeLocationType(ref.locationType);
    if (!type) return null;
    const base = `/information/locations/${encodeURIComponentSafe(type)}/${encodeURIComponentSafe(ref.name)}`;
    return ref.id != null ? `${base}?id=${encodeURIComponent(String(ref.id))}` : base;
  }

  function buildPlanetHref(ref) {
    if (!ref?.technicalName) return null;
    const technical = String(ref.technicalName).replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
    return technical ? `/maps/${technical}` : null;
  }

  function resolveRefHref(ref) {
    if (!ref?.type || !ref?.name) return null;

    if (ref.type === 'Location') {
      return buildLocationHref(ref);
    }

    if (ref.type === 'Planet') {
      return buildPlanetHref(ref);
    }

    return getTypeLink(ref.name, ref.type, ref.subType || null);
  }

  function formatCellValue(value, row, key) {
    const text = value === null || value === undefined || value === '' ? '-' : String(value);
    const escapedText = escapeHtml(text);

    const ref = row?.__refs?.[key];
    const href = resolveRefHref(ref);
    if (!href) return escapedText;

    return `<a href="${escapeHtml(href)}" class="enum-link">${escapedText}</a>`;
  }

  $: metadataJson = activeEnumeration?.Properties?.Metadata
    ? JSON.stringify(activeEnumeration.Properties.Metadata, null, 2)
    : null;

  $: tableColumns = (activeEnumeration?.Table?.Columns || []).map((col) => ({
    key: col.key,
    header: col.label,
    sortable: true,
    searchable: true,
    widthBasis: 'both',
    main: col.key === 'Description' || col.key === 'Name',
    formatter: (value, row) => formatCellValue(value, row, col.key)
  }));

  $: tableRows = activeEnumeration?.Table?.Rows || [];
</script>

<svelte:head>
  <title>{activeEnumeration?.Name ? `${activeEnumeration.Name} - Enumerations` : 'Enumerations'} - Entropia Nexus</title>
  <meta
    name="description"
    content={activeEnumeration?.Properties?.Description || 'Browse built-in and custom enumerations used across Entropia Nexus.'}
  />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>

<WikiPage
  title="Enumerations"
  {breadcrumbs}
  entity={activeEnumeration}
  basePath="/information/enumerations"
  {navItems}
  {navFilters}
  {navTableColumns}
  navPageTypeId="enumerations"
  {user}
  editable={false}
  canEdit={false}
>
  {#if activeEnumeration}
    <article class="wiki-article">
      <h1 class="article-title">{activeEnumeration.Name}</h1>

      <div class="description-panel">
        {#if activeEnumeration?.Properties?.Description}
          <div class="description-content">{activeEnumeration.Properties.Description}</div>
        {:else}
          <div class="description-content placeholder">
            No description available for this enumeration.
          </div>
        {/if}
      </div>

      <div class="meta-grid">
        <div class="meta-item">
          <span class="meta-label">Source</span>
          <span class="meta-value">{activeEnumeration?.Properties?.Source || '-'}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Unit</span>
          <span class="meta-value">{activeEnumeration?.Properties?.Unit || '-'}</span>
        </div>
      </div>

      {#if metadataJson}
        <section class="metadata-block">
          <h2>Metadata</h2>
          <pre>{metadataJson}</pre>
        </section>
      {/if}

      <section class="table-section">
        <h2>Values</h2>
        <div class="table-shell">
          <FancyTable
            columns={tableColumns}
            data={tableRows}
            emptyMessage="No rows available."
            rowHeight={32}
            sortable={true}
            searchable={true}
            stickyHeader={true}
            defaultWidthBasis="both"
            horizontalScroll={true}
            compact={true}
          />
        </div>
      </section>
    </article>
  {:else}
    <div class="no-selection">
      <h2>Enumerations</h2>
      <p>Select an enumeration from the list to view details.</p>
      <p class="hint">Built-in and custom enumerations are shown in a unified list.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .meta-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
    margin: 14px 0 18px;
  }

  .meta-item {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .meta-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    color: var(--text-muted);
  }

  .meta-value {
    font-size: 14px;
    color: var(--text-color);
  }

  .metadata-block {
    margin: 8px 0 18px;
  }

  .metadata-block h2,
  .table-section h2 {
    font-size: 18px;
    margin: 0 0 8px;
  }

  .metadata-block pre {
    margin: 0;
    padding: 12px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background-color: var(--secondary-color);
    overflow: auto;
    font-size: 12px;
    line-height: 1.45;
  }

  .table-section {
    margin-top: 12px;
  }

  .table-shell {
    height: min(68vh, 760px);
  }

  :global(.enum-link) {
    color: var(--accent-color);
    text-decoration: underline;
  }
</style>
