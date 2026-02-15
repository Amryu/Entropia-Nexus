<!--
  @component MarketSearch
  Unified market search component for the market dashboard.
  Searches across exchange, services, auctions, rentals, and shops.
  Displays results with type badges, prices, and navigation links.

  @example
  <MarketSearch />
-->
<script>
  // @ts-nocheck
  import { onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { browser } from '$app/environment';

  /** @type {string} */
  let value = '';

  /** @type {number} Debounce delay in ms */
  export let debounceMs = 300;

  // Internal state
  let inputElement;
  let results = [];
  let isSearching = false;
  let showResults = false;
  let highlightedIndex = -1;
  let searchTimeout;
  let preventBlurClose = false;

  const BADGE_CONFIG = {
    exchange: { label: 'Exchange', cls: 'badge-exchange' },
    service: { label: 'Service', cls: 'badge-service' },
    auction: { label: 'Auction', cls: 'badge-auction' },
    rental: { label: 'Rental', cls: 'badge-rental' },
    shop: { label: 'Shop', cls: 'badge-shop' }
  };

  onDestroy(() => {
    if (searchTimeout) clearTimeout(searchTimeout);
  });

  async function performSearch() {
    if (!browser) return;
    if (value.length < 2) {
      results = [];
      showResults = false;
      return;
    }

    isSearching = true;
    showResults = true;

    try {
      const response = await fetch(`/api/market/search?query=${encodeURIComponent(value)}`);
      const data = await response.json();
      results = Array.isArray(data) ? data : [];
    } catch (err) {
      console.error('Market search failed:', err);
      results = [];
    } finally {
      isSearching = false;
    }
  }

  function handleInput(event) {
    value = event.target.value;
    highlightedIndex = -1;

    if (searchTimeout) clearTimeout(searchTimeout);

    if (value.length < 2) {
      results = [];
      isSearching = false;
      showResults = false;
      return;
    }

    isSearching = true;
    showResults = true;
    searchTimeout = setTimeout(performSearch, debounceMs);
  }

  function handleKeydown(event) {
    if (!showResults || results.length === 0) {
      if (event.key === 'Escape') {
        closeResults();
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        highlightedIndex = Math.min(highlightedIndex + 1, results.length - 1);
        scrollToHighlighted();
        break;

      case 'ArrowUp':
        event.preventDefault();
        highlightedIndex = Math.max(highlightedIndex - 1, 0);
        scrollToHighlighted();
        break;

      case 'Enter':
        event.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < results.length) {
          selectResult(results[highlightedIndex]);
        }
        break;

      case 'Escape':
        event.preventDefault();
        closeResults();
        break;

      case 'Tab':
        closeResults();
        break;
    }
  }

  function scrollToHighlighted() {
    const container = inputElement?.parentElement?.querySelector('.market-search-results');
    const highlighted = container?.querySelector('.market-result-item.highlighted');
    if (container && highlighted) {
      highlighted.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function selectResult(result) {
    if (result?.url) {
      goto(result.url);
    }
    closeResults();
  }

  function closeResults() {
    showResults = false;
    highlightedIndex = -1;
  }

  function handleBlur() {
    setTimeout(() => {
      if (!preventBlurClose) {
        closeResults();
      }
      preventBlurClose = false;
    }, 200);
  }

  function handleFocus() {
    if (value.length >= 2 && results.length > 0) {
      showResults = true;
    }
  }

  function handleResultClick(event, result) {
    if (event.button === 0) {
      event.preventDefault();
      selectResult(result);
    }
  }

  function handleResultMouseEnter(index) {
    highlightedIndex = index;
  }

  function handleResultMouseDown(event) {
    if (event.button === 1 || event.button === 2) {
      preventBlurClose = true;
    }
  }

  function getBadge(marketType) {
    return BADGE_CONFIG[marketType] || { label: marketType, cls: 'badge-shop' };
  }
</script>

<div class="market-search-container">
  <div class="market-search-wrapper">
    <svg class="search-icon" viewBox="0 0 20 20" fill="currentColor" width="20" height="20">
      <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" />
    </svg>
    <input
      bind:this={inputElement}
      type="text"
      class="market-search-input"
      placeholder="Search items, services, auctions, rentals, shops..."
      value={value}
      on:input={handleInput}
      on:keydown={handleKeydown}
      on:blur={handleBlur}
      on:focus={handleFocus}
      autocomplete="off"
      spellcheck="false"
    />
    {#if isSearching}
      <span class="market-search-spinner"></span>
    {/if}
  </div>

  {#if showResults}
    <div class="market-search-results">
      {#if isSearching && results.length === 0}
        <div class="market-search-status">Searching...</div>
      {:else if results.length === 0 && !isSearching}
        <div class="market-search-status">No results found for "{value}"</div>
      {:else}
        {#each results as result, i}
          {@const badge = getBadge(result.marketType)}
          <a
            href={result.url}
            class="market-result-item"
            class:highlighted={i === highlightedIndex}
            on:mousedown={handleResultMouseDown}
            on:click={(e) => handleResultClick(e, result)}
            on:mouseenter={() => handleResultMouseEnter(i)}
          >
            <span class="market-result-badge {badge.cls}">{badge.label}</span>
            <span class="market-result-name">{result.name}</span>
            {#if result.price}
              <span class="market-result-price">{result.price}</span>
            {/if}
            {#if result.detail}
              <span class="market-result-detail">{result.detail}</span>
            {/if}
          </a>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .market-search-container {
    position: relative;
    width: 100%;
    max-width: 700px;
    margin: 0 auto;
  }

  .market-search-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .search-icon {
    position: absolute;
    left: 16px;
    color: var(--text-muted);
    pointer-events: none;
    z-index: 1;
  }

  .market-search-input {
    width: 100%;
    font-size: 16px;
    padding: 14px 44px 14px 48px;
    border-radius: 12px;
    border: 2px solid var(--border-color);
    background-color: var(--secondary-color);
    color: var(--text-color);
    box-sizing: border-box;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
  }

  .market-search-input::placeholder {
    color: var(--text-muted);
  }

  .market-search-input:focus {
    outline: none;
    border-color: var(--accent-color);
    box-shadow: 0 0 0 3px var(--accent-color-bg);
  }

  .market-search-spinner {
    position: absolute;
    right: 16px;
    width: 18px;
    height: 18px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .market-search-results {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 100;
    max-height: 420px;
    overflow-y: auto;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    margin-top: 4px;
  }

  .market-search-status {
    padding: 20px;
    text-align: center;
    color: var(--text-muted);
    font-size: 14px;
  }

  .market-result-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    cursor: pointer;
    border-bottom: 1px solid var(--border-color);
    transition: background-color 0.1s ease;
    text-decoration: none;
    color: inherit;
  }

  .market-result-item:last-child {
    border-bottom: none;
  }

  .market-result-item:visited {
    color: inherit;
  }

  .market-result-item:hover,
  .market-result-item.highlighted {
    background-color: var(--hover-color);
  }

  .market-result-item.highlighted {
    outline: 2px solid var(--accent-color);
    outline-offset: -2px;
  }

  .market-result-badge {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    padding: 2px 6px;
    border-radius: 3px;
    flex-shrink: 0;
    line-height: 1.3;
  }

  .badge-exchange {
    background-color: rgba(96, 176, 255, 0.15);
    color: var(--accent-color);
  }

  .badge-service {
    background-color: rgba(168, 85, 247, 0.15);
    color: #a855f7;
  }

  .badge-auction {
    background-color: rgba(251, 191, 36, 0.15);
    color: var(--warning-color);
  }

  .badge-rental {
    background-color: rgba(22, 163, 74, 0.15);
    color: var(--success-color);
  }

  .badge-shop {
    background-color: rgba(148, 163, 184, 0.15);
    color: var(--text-muted);
  }

  .market-result-name {
    font-size: 14px;
    color: var(--text-color);
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .market-result-price {
    font-size: 13px;
    font-weight: 600;
    color: var(--accent-color);
    flex-shrink: 0;
    white-space: nowrap;
  }

  .market-result-detail {
    font-size: 12px;
    color: var(--text-muted);
    flex-shrink: 0;
    white-space: nowrap;
  }

  /* Mobile */
  @media (max-width: 600px) {
    .market-search-input {
      font-size: 15px;
      padding: 12px 40px 12px 44px;
    }

    .market-result-item {
      padding: 12px 14px;
      flex-wrap: wrap;
      gap: 6px;
    }

    .market-result-name {
      flex-basis: calc(100% - 80px);
    }

    .market-result-price,
    .market-result-detail {
      font-size: 11px;
    }
  }
</style>
