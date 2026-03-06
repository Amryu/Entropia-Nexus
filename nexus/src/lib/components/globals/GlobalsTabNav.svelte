<!--
  @component GlobalsTabNav
  Tab navigation for globals sub-pages: Overview, Players, Targets.
  Preserves current filter query params across tabs.
-->
<script>
  import { page } from '$app/stores';

  /** Function that returns a URLSearchParams for current filters */
  export let buildParams = null;

  const TABS = [
    { label: 'Overview', path: '/globals' },
    { label: 'Live', path: '/globals', query: 'view=live' },
    { label: 'Top Players', path: '/globals/players' },
    { label: 'Top Targets', path: '/globals/targets' },
  ];

  function getHref(tab) {
    if (tab.query) {
      if (!buildParams) return `${tab.path}?${tab.query}`;
      const params = buildParams();
      params.set('view', 'live');
      return `${tab.path}?${params}`;
    }
    if (!buildParams) return tab.path;
    const params = buildParams();
    const qs = params.toString();
    return qs ? `${tab.path}?${qs}` : tab.path;
  }

  $: activeIdx = (() => {
    const path = $page.url.pathname;
    const view = $page.url.searchParams.get('view');
    if (path === '/globals' && view === 'live') return 1;
    if (path === '/globals' && !view) return 0;
    const sub = TABS.findIndex((t, i) => i > 1 && path.startsWith(t.path));
    return sub >= 0 ? sub : 0;
  })();
</script>

<nav class="globals-tab-nav">
  {#each TABS as tab, i}
    <a
      href={getHref(tab)}
      class="tab-link"
      class:active={activeIdx === i}
    >
      {tab.label}
    </a>
  {/each}
</nav>

<style>
  .globals-tab-nav {
    display: flex;
    gap: 2px;
    margin-bottom: 20px;
    border-bottom: 1px solid var(--border-color);
  }

  .tab-link {
    padding: 10px 20px;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-muted);
    text-decoration: none;
    border-bottom: 2px solid transparent;
    transition: all 0.15s ease;
    margin-bottom: -1px;
  }

  .tab-link:hover {
    color: var(--text-color);
  }

  .tab-link.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
    font-weight: 600;
  }
</style>
