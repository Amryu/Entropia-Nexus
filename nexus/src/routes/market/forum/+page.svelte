<!--
  @component PCF Trade
  Browse Planet Calypso Forum trading posts with item matching.
  All filtering happens client-side for instant responsiveness.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { timeAgo } from '$lib/utils/globalsFormat.js';

  let { data } = $props();

  let allThreads = $derived(data.threads || []);
  let stats = $derived(data.stats || {});

  // Initialize type from URL query param (for links like /market/forum?type=selling)
  const validTypes = new Set(['selling', 'buying']);
  const initialType = typeof window !== 'undefined' ? new URL(window.location.href).searchParams.get('type') : null;
  let activeType = $state(validTypes.has(initialType) ? initialType : 'all');
  let searchQuery = $state('');
  let sortBy = $state('activity');

  const PAGE_SIZE = 30;
  let currentPage = $state(1);

  // Track previous filter state to reset page on change
  let prevFilterKey = $state('');
  let filterKey = $derived(`${activeType}|${searchQuery}|${sortBy}`);
  $effect(() => {
    if (filterKey !== prevFilterKey) {
      prevFilterKey = filterKey;
      currentPage = 1;
    }
  });

  let filteredThreads = $derived((() => {
    let list = allThreads;

    // Filter by type
    if (activeType !== 'all') {
      list = list.filter(t => t.forum_type === activeType);
    }

    // Filter by search query (title + matched item names)
    const q = searchQuery.trim().toLowerCase();
    if (q.length >= 2) {
      list = list.filter(t => {
        if (t.title.toLowerCase().includes(q)) return true;
        if (t.author.toLowerCase().includes(q)) return true;
        const items = t.matched_items;
        if (Array.isArray(items)) {
          return items.some(mi => mi.itemName?.toLowerCase().includes(q));
        }
        return false;
      });
    }

    // Sort
    if (sortBy === 'created') {
      list = [...list].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    } else if (sortBy === 'comments') {
      list = [...list].sort((a, b) => b.comment_count - a.comment_count);
    }
    // 'activity' is the default server sort, no need to re-sort

    return list;
  })());

  let totalPages = $derived(Math.ceil(filteredThreads.length / PAGE_SIZE));
  let pagedThreads = $derived(filteredThreads.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE));

  function goToPage(p) {
    currentPage = Math.max(1, Math.min(p, totalPages));
  }

  function getItemLink(itemName) {
    return `/search?q=${encodeURIComponent(itemName)}`;
  }

  function formatCount(n) {
    if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    return String(n ?? 0);
  }

  const MAX_VISIBLE_ITEMS = 3;
</script>

<svelte:head>
  <title>PCF Trade - Market - Entropia Nexus</title>
  <meta name="description" content="Browse Planet Calypso Forum trading posts — find items for sale or wanted by other players." />
  <link rel="canonical" href="https://entropianexus.com/market/forum" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/market/forum" />
  <meta property="og:title" content="PCF Trade - Entropia Nexus" />
  <meta property="og:description" content="Browse Planet Calypso Forum trading posts — find items for sale or wanted by other players." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      <span>PCF Trade</span>
    </div>

    <div class="page-header">
      <div class="header-left">
        <h1>PCF Trade</h1>
        <p class="subtitle">
          Browse trading posts from the
          <a href="https://www.planetcalypsoforum.com/forum/index.php?forums/trading.110/" target="_blank" rel="noopener">Planet Calypso Forum</a>
        </p>
      </div>
      {#if stats.total_active}
        <div class="header-stats">
          <span class="stat">{formatCount(stats.total_active)} active</span>
        </div>
      {/if}
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button class="tab" class:active={activeType === 'all'} onclick={() => activeType = 'all'}>
        All
      </button>
      <button class="tab tab-selling" class:active={activeType === 'selling'} onclick={() => activeType = 'selling'}>
        Selling
        {#if stats.sell_count}<span class="tab-count">{formatCount(stats.sell_count)}</span>{/if}
      </button>
      <button class="tab tab-buying" class:active={activeType === 'buying'} onclick={() => activeType = 'buying'}>
        Buying
        {#if stats.buy_count}<span class="tab-count">{formatCount(stats.buy_count)}</span>{/if}
      </button>
    </div>

    <!-- Filters -->
    <div class="filters">
      <div class="filter-group filter-search">
        <input
          type="text"
          bind:value={searchQuery}
          placeholder="Search by item name or thread title..."
          class="search-input"
        />
      </div>
      <div class="filter-group filter-sort">
        <select bind:value={sortBy}>
          <option value="activity">Last Activity</option>
          <option value="created">Newest</option>
          <option value="comments">Most Replies</option>
        </select>
      </div>
    </div>

    <!-- Thread Cards -->
    {#if pagedThreads.length === 0}
      <div class="empty-state">
        <p>No forum threads found</p>
        {#if searchQuery}
          <button class="btn-secondary" onclick={() => searchQuery = ''}>
            Clear search
          </button>
        {/if}
      </div>
    {:else}
      <div class="thread-list">
        {#each pagedThreads as thread (thread.thread_id)}
          <div class="thread-card">
            <div class="thread-top">
              <span class="badge badge-type" class:badge-selling={thread.forum_type === 'selling'} class:badge-buying={thread.forum_type === 'buying'}>
                {thread.forum_type === 'selling' ? 'WTS' : 'WTB'}
              </span>
              <a href={thread.url} target="_blank" rel="noopener" class="thread-title">
                {thread.title}
                <svg class="external-icon" viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
                  <path d="M3.75 2a1.75 1.75 0 0 0-1.75 1.75v8.5c0 .966.784 1.75 1.75 1.75h8.5A1.75 1.75 0 0 0 14 12.25v-3.5a.75.75 0 0 0-1.5 0v3.5a.25.25 0 0 1-.25.25h-8.5a.25.25 0 0 1-.25-.25v-8.5a.25.25 0 0 1 .25-.25h3.5a.75.75 0 0 0 0-1.5h-3.5zm6.25 0a.75.75 0 0 0 0 1.5h1.44L6.22 8.72a.75.75 0 1 0 1.06 1.06L12.5 4.56v1.44a.75.75 0 0 0 1.5 0V2.75a.75.75 0 0 0-.75-.75H10z"/>
                </svg>
              </a>
            </div>

            {#if thread.content_snippet}
              <p class="thread-snippet">{thread.content_snippet}</p>
            {/if}

            {#if thread.matched_items?.length > 0}
              <div class="thread-items">
                {#each thread.matched_items.slice(0, MAX_VISIBLE_ITEMS) as mi}
                  <a href={getItemLink(mi.itemName)} class="item-badge">{mi.itemName}</a>
                {/each}
                {#if thread.matched_items.length > MAX_VISIBLE_ITEMS}
                  <span class="item-badge item-badge-more">+{thread.matched_items.length - MAX_VISIBLE_ITEMS} more</span>
                {/if}
              </div>
            {/if}

            <div class="thread-footer">
              <span class="thread-author">{thread.author}</span>
              <span class="thread-sep">&middot;</span>
              <span class="thread-replies">{thread.comment_count} {thread.comment_count === 1 ? 'reply' : 'replies'}</span>
              <span class="thread-sep">&middot;</span>
              <span class="thread-activity">{timeAgo(thread.last_activity_at)}</span>
            </div>
          </div>
        {/each}
      </div>

      {#if totalPages > 1}
        <div class="pagination">
          <button class="page-btn" disabled={currentPage <= 1} onclick={() => goToPage(currentPage - 1)}>
            Previous
          </button>
          <span class="page-info">Page {currentPage} of {totalPages}</span>
          <button class="page-btn" disabled={currentPage >= totalPages} onclick={() => goToPage(currentPage + 1)}>
            Next
          </button>
        </div>
      {/if}
    {/if}
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 1rem;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
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

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .header-left h1 {
    margin: 0 0 4px 0;
    font-size: 1.5rem;
  }

  .subtitle {
    color: var(--text-muted);
    margin: 0;
    font-size: 0.9rem;
  }

  .subtitle a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .subtitle a:hover {
    text-decoration: underline;
  }

  .header-stats {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .stat {
    font-size: 0.85rem;
    color: var(--text-muted);
    font-weight: 600;
  }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 1rem;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 0;
  }

  .tab {
    padding: 8px 16px;
    border: none;
    background: none;
    color: var(--text-muted);
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: color 0.15s, border-color 0.15s;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .tab:hover {
    color: var(--text-color);
  }

  .tab.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
  }

  .tab-count {
    font-size: 0.75rem;
    background-color: var(--hover-color);
    padding: 1px 6px;
    border-radius: 10px;
  }

  /* Filters */
  .filters {
    display: flex;
    gap: 10px;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
  }

  .filter-search {
    flex: 3;
    min-width: 0;
  }

  .filter-sort {
    flex: 1;
    min-width: 0;
  }

  .search-input {
    width: 100%;
    box-sizing: border-box;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 0.9rem;
  }

  .search-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .filter-sort select {
    width: 100%;
    box-sizing: border-box;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 0.9rem;
    cursor: pointer;
  }

  /* Thread Cards */
  .thread-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .thread-card {
    padding: 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    transition: border-color 0.15s;
  }

  .thread-card:hover {
    border-color: var(--accent-color);
  }

  .thread-top {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 6px;
  }

  .badge-type {
    flex-shrink: 0;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 2px;
  }

  .badge-selling {
    background-color: rgba(96, 176, 255, 0.15);
    color: var(--accent-color);
  }

  .badge-buying {
    background-color: rgba(22, 163, 74, 0.15);
    color: var(--success-color);
  }

  .thread-title {
    color: var(--text-color);
    text-decoration: none;
    font-weight: 600;
    font-size: 0.95rem;
    line-height: 1.4;
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
  }

  .thread-title:hover {
    color: var(--accent-color);
  }

  .external-icon {
    flex-shrink: 0;
    opacity: 0.4;
    vertical-align: baseline;
  }

  .thread-title:hover .external-icon {
    opacity: 0.7;
  }

  .thread-snippet {
    margin: 0 0 8px 0;
    color: var(--text-muted);
    font-size: 0.85rem;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  /* Item badges */
  .thread-items {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
  }

  .item-badge {
    font-size: 0.75rem;
    padding: 2px 8px;
    border-radius: 4px;
    background-color: rgba(251, 146, 60, 0.12);
    color: #fb923c;
    text-decoration: none;
    transition: background-color 0.15s;
  }

  .item-badge:hover {
    background-color: rgba(251, 146, 60, 0.25);
  }

  .item-badge-more {
    background-color: var(--hover-color);
    color: var(--text-muted);
    cursor: default;
  }

  /* Footer */
  .thread-footer {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .thread-sep {
    opacity: 0.5;
  }

  /* Empty state */
  .empty-state {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
  }

  .btn-secondary {
    margin-top: 1rem;
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    font-size: 0.85rem;
    text-decoration: none;
  }

  .btn-secondary:hover {
    border-color: var(--accent-color);
  }

  /* Pagination */
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 1rem;
    margin-top: 2rem;
  }

  .page-btn {
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    font-size: 0.85rem;
  }

  .page-btn:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .page-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .page-info {
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  @media (max-width: 600px) {
    .page-container {
      padding: 0.75rem;
    }

    .filters {
      flex-direction: column;
    }

    .thread-top {
      flex-wrap: wrap;
    }
  }
</style>
