<!--
  @component WikiSEO
  SEO component that renders meta tags and JSON-LD structured data.
  Handles title, description, Open Graph, Twitter Cards, and schema.org markup.
-->
<script>
  // @ts-nocheck

  /** @type {string} Page title */
  export let title = '';

  /** @type {string} Page description (max ~160 chars for search results) */
  export let description = '';

  /** @type {string} Entity type for structured data (e.g., 'weapon', 'mob') */
  export let entityType = '';

  /** @type {object|null} Entity data for structured data */
  export let entity = null;

  /** @type {string|null} Image URL for social sharing */
  export let imageUrl = null;

  /** @type {string} Canonical URL */
  export let canonicalUrl = '';

  /** @type {Array} Breadcrumb items for schema.org [{name, url}] */
  export let breadcrumbs = [];

  /** @type {string} Site name */
  export let siteName = 'Entropia Nexus';

  /** @type {string} Twitter handle (without @) */
  export let twitterHandle = '';

  /** @type {Array|null} Sidebar table columns for building social summary */
  export let sidebarColumns = null;

  /** @type {object|null} Sidebar entity for building social summary */
  export let sidebarEntity = null;

  /** @type {string} Optional override for Open Graph description */
  export let ogDescription = '';

  // Computed values
  $: pageTitle = title ? `${title} | ${siteName}` : siteName;

  $: truncatedDescription = description
    ? description.substring(0, 160) + (description.length > 160 ? '...' : '')
    : '';

  $: ogImage = imageUrl || '/default-og-image.png';

  const MAX_OG_DESCRIPTION = 200;

  function clampText(text, limit = MAX_OG_DESCRIPTION) {
    if (!text) return '';
    const cleaned = `${text}`.replace(/\s+/g, ' ').trim();
    if (cleaned.length <= limit) return cleaned;
    return cleaned.substring(0, limit - 1).trimEnd() + '…';
  }

  function getValueByPath(obj, path) {
    if (!obj || !path) return undefined;
    const parts = `${path}`.split('.');
    let current = obj;
    for (const part of parts) {
      if (current == null) return undefined;
      current = current[part];
    }
    return current;
  }

  function normalizeFactValue(value) {
    if (value == null) return null;
    if (typeof value === 'string') {
      const trimmed = value.replace(/\s+/g, ' ').trim();
      if (!trimmed || trimmed === '-') return null;
      return trimmed;
    }
    if (Array.isArray(value)) {
      const items = value.map(v => normalizeFactValue(v)).filter(Boolean);
      return items.length ? items.join(', ') : null;
    }
    if (typeof value === 'number') {
      if (Number.isNaN(value)) return null;
      return `${value}`;
    }
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    return null;
  }

  function buildSidebarFacts(columns, entity, limit = 4) {
    if (!columns || !Array.isArray(columns) || !entity) return [];
    const facts = [];
    for (const column of columns) {
      if (!column || !column.header) continue;
      let rawValue = null;
      try {
        if (typeof column.getValue === 'function') {
          rawValue = column.getValue(entity);
        } else if (column.key) {
          rawValue = getValueByPath(entity, column.key);
        }
      } catch (err) {
        rawValue = null;
      }

      let formatted = rawValue;
      if (typeof column.format === 'function') {
        try {
          formatted = column.format(rawValue);
        } catch (err) {
          formatted = rawValue;
        }
      }

      const normalized = normalizeFactValue(formatted);
      if (!normalized) continue;
      facts.push({ label: column.header, value: normalized });
      if (facts.length >= limit) break;
    }
    return facts;
  }

  $: sidebarFacts = buildSidebarFacts(sidebarColumns, sidebarEntity || entity);
  $: sidebarFactsText = sidebarFacts.map(fact => `${fact.label}: ${fact.value}`).join(' · ');

  $: computedOgDescription = clampText(
    ogDescription ||
      (sidebarFactsText
        ? (description ? `${sidebarFactsText} — ${description}` : `${title} — ${sidebarFactsText}`)
        : truncatedDescription)
  );

  // Generate JSON-LD structured data
  $: jsonLd = generateJsonLd(entity, entityType, breadcrumbs, canonicalUrl);

  function generateJsonLd(entity, type, breadcrumbs, url) {
    const schemas = [];

    // Breadcrumb schema
    if (breadcrumbs.length > 0) {
      schemas.push({
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': breadcrumbs.map((crumb, index) => ({
          '@type': 'ListItem',
          'position': index + 1,
          'name': crumb.name,
          'item': crumb.url
        }))
      });
    }

    // Entity-specific schema
    if (entity) {
      if (type === 'weapon' || type === 'armor' || type === 'tool' || type === 'material') {
        // Item/Product schema for game items
        schemas.push({
          '@context': 'https://schema.org',
          '@type': 'Product',
          'name': entity.Name,
          'description': entity.Properties?.Description || truncatedDescription,
          'image': imageUrl,
          'url': url,
          'category': type,
          'brand': {
            '@type': 'Brand',
            'name': entity.Properties?.Manufacturer || 'Unknown'
          },
          ...(entity.Properties?.MaxTT && {
            'offers': {
              '@type': 'Offer',
              'price': entity.Properties.MaxTT,
              'priceCurrency': 'PED',
              'availability': 'https://schema.org/InStock'
            }
          })
        });
      } else if (type === 'mob' || type === 'mission' || type === 'mission-chain') {
        // Article schema for informational content
        schemas.push({
          '@context': 'https://schema.org',
          '@type': 'Article',
          'headline': entity.Name,
          'description': entity.Properties?.Description || truncatedDescription,
          'image': imageUrl,
          'url': url,
          'publisher': {
            '@type': 'Organization',
            'name': siteName,
            'url': 'https://entropianexus.com'
          }
        });
      } else if (type === 'blueprint') {
        // Recipe schema for blueprints
        schemas.push({
          '@context': 'https://schema.org',
          '@type': 'HowTo',
          'name': `How to craft ${entity.Name}`,
          'description': entity.Properties?.Description || `Crafting guide for ${entity.Name}`,
          'url': url,
          ...(entity.Materials && {
            'supply': entity.Materials.map(mat => ({
              '@type': 'HowToSupply',
              'name': mat.Name,
              'requiredQuantity': mat.Quantity
            }))
          })
        });
      } else {
        // Generic Article for other types
        schemas.push({
          '@context': 'https://schema.org',
          '@type': 'Article',
          'headline': entity.Name || title,
          'description': entity.Properties?.Description || truncatedDescription,
          'image': imageUrl,
          'url': url,
          'publisher': {
            '@type': 'Organization',
            'name': siteName,
            'url': 'https://entropianexus.com'
          }
        });
      }
    }

    // WebPage schema
    schemas.push({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      'name': title,
      'description': truncatedDescription,
      'url': url,
      'isPartOf': {
        '@type': 'WebSite',
        'name': siteName,
        'url': 'https://entropianexus.com'
      }
    });

    return schemas;
  }
</script>

<svelte:head>
  <!-- Primary Meta Tags -->
  <title>{pageTitle}</title>
  <meta name="title" content={pageTitle} />
  <meta name="description" content={truncatedDescription} />

  <!-- Robots -->
  <meta name="robots" content="index, follow" />

  <!-- Canonical URL -->
  {#if canonicalUrl}
    <link rel="canonical" href={canonicalUrl} />
  {/if}

  <!-- Open Graph / Facebook -->
  <meta property="og:type" content={entity ? 'article' : 'website'} />
  <meta property="og:url" content={canonicalUrl} />
  <meta property="og:title" content={pageTitle} />
  <meta property="og:description" content={computedOgDescription} />
  <meta property="og:image" content={ogImage} />
  <meta property="og:site_name" content={siteName} />

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:url" content={canonicalUrl} />
  <meta name="twitter:title" content={pageTitle} />
  <meta name="twitter:description" content={computedOgDescription} />
  <meta name="twitter:image" content={ogImage} />
  {#if twitterHandle}
    <meta name="twitter:site" content="@{twitterHandle}" />
  {/if}

  <!-- Keywords (entity-specific) -->
  {#if entity}
    <meta name="keywords" content="{entity.Name}, {entityType}, Entropia Universe, EU, Wiki, {siteName}" />
  {/if}

  <!-- JSON-LD Structured Data -->
  {#each jsonLd as schema}
    {@html `<script type="application/ld+json">${JSON.stringify(schema)}</script>`}
  {/each}
</svelte:head>
