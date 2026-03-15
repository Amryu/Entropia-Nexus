<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { encodeURIComponentSafe } from '$lib/util';

  const columns = [
    {
      key: 'name',
      header: 'Society',
      sortable: true,
      searchable: true,
      formatter: (value, row) => {
        if (!value) return '-';
        const label = `${value}${row.abbreviation ? ` (${row.abbreviation})` : ''}`;
        const url = `/societies/${encodeURIComponentSafe(value)}`;
        return `<a class="society-link" href="${url}">${escapeHtml(label)}</a>`;
      }
    },
    {
      key: 'leader',
      header: 'Leader',
      sortable: false,
      searchable: false,
      width: '200px',
      formatter: (_, row) => {
        const label = row.leader_eu_name || row.leader_global_name || row.leader_username || row.leader_id || '-';
        if (!row.leader_id) return escapeHtml(label);
        const url = `/admin/users/${encodeURIComponentSafe(String(row.leader_id))}`;
        return `<a class="society-link" href="${url}">${escapeHtml(String(label))}</a>`;
      }
    },
    {
      key: 'member_count',
      header: 'Members',
      sortable: false,
      searchable: false,
      width: '110px',
      formatter: (value) => value ?? 0
    }
  ];

  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  async function fetchSocieties(offset, limit, sortBy, sortOrder, filters) {
    const page = Math.floor(offset / limit) + 1;
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('limit', String(limit));
    if (filters.name) {
      params.set('q', filters.name);
    }

    const response = await fetch(`/api/admin/societies?${params}`);
    if (!response.ok) throw new Error('Failed to load societies');
    const data = await response.json();
    return {
      rows: data.societies || [],
      total: data.total || data.societies?.length || 0
    };
  }
</script>

<svelte:head>
  <title>Societies | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .societies-page {
    max-width: 1400px;
    height: calc(100vh - 140px);
    height: calc(100dvh - 140px);
    display: flex;
    flex-direction: column;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .breadcrumb span {
    color: var(--text-muted);
  }

  h1 {
    margin: 0;
    font-size: 24px;
    color: var(--text-color);
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }

  .table-container {
    flex: 1;
    min-height: 400px;
  }

  :global(.society-link) {
    color: var(--accent-color);
    text-decoration: none;
  }

  :global(.society-link:hover) {
    text-decoration: underline;
  }

  @media (max-width: 768px) {
    .societies-page {
      height: auto;
      min-height: calc(100vh - 140px);
      min-height: calc(100dvh - 140px);
    }

    h1 {
      font-size: 20px;
    }

    .page-header {
      flex-direction: column;
      align-items: stretch;
    }

    .table-container {
      min-height: 300px;
    }
  }
</style>

<div class="societies-page">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Societies</span>
  </div>

  <div class="page-header">
    <h1>Societies</h1>
  </div>

  <div class="table-container">
    <FancyTable
      {columns}
      fetchData={fetchSocieties}
      rowHeight={56}
      pageSize={50}
      sortable={true}
      searchable={true}
      emptyMessage="No societies found"
    />
  </div>
</div>
