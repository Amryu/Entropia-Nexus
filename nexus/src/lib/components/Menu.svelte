<script lang="ts">
  // @ts-nocheck

  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';
  import { afterNavigate } from '$app/navigation';

  import { darkMode } from '../../stores.js';

  import { getTypeLink, getTypeName } from "$lib/util";
  import { loading } from "../../actions/loading";
  import FancyTable from '$lib/components/FancyTable.svelte';

  export let user;
  export let realUser = null; // The actual admin user when impersonating

  let dropdownOpen: string | null = null;
  let dropdownCloseTimeout: ReturnType<typeof setTimeout> | null = null;
  let showImpersonateDialog = false;
  let mobileMenuOpen = false;
  let expandedSections: Set<string> = new Set();
  let mobileSearchMode = false;

  // Media query for auto-closing mobile menu
  let mediaQuery: MediaQueryList | null = null;

  onMount(() => {
    if (typeof window !== 'undefined') {
      mediaQuery = window.matchMedia('(max-width: 900px)');
      mediaQuery.addEventListener('change', handleMediaChange);
    }
  });

  onDestroy(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', handleMediaChange);
    }
    if (timeout) clearTimeout(timeout);
    if (dropdownCloseTimeout) clearTimeout(dropdownCloseTimeout);
  });

  function handleMediaChange(e: MediaQueryListEvent) {
    if (!e.matches) {
      // Switched to desktop mode - close mobile menu
      closeMobileMenu();
    }
  }

  function toggleMobileMenu() {
    mobileMenuOpen = !mobileMenuOpen;
    if (mobileMenuOpen) {
      dropdownOpen = null;
      mobileSearchMode = false;
    }
  }

  function closeMobileMenu() {
    mobileMenuOpen = false;
    dropdownOpen = null;
    mobileSearchMode = false;
    mobileSearchQuery = '';
    mobileSearchResults = [];
  }

  function handleDropdownEnter(menu: string) {
    if (dropdownCloseTimeout) {
      clearTimeout(dropdownCloseTimeout);
      dropdownCloseTimeout = null;
    }
    dropdownOpen = menu;
  }

  function handleDropdownLeave() {
    dropdownCloseTimeout = setTimeout(() => {
      dropdownOpen = null;
      dropdownCloseTimeout = null;
    }, 150);
  }

  function toggleSection(section: string) {
    if (expandedSections.has(section)) {
      expandedSections.delete(section);
    } else {
      expandedSections.add(section);
    }
    expandedSections = expandedSections; // Trigger reactivity
  }

  let impersonateUserId = '';
  let impersonateError = '';
  let isImpersonating = false;

  // User search state (for impersonation)
  let userSearchQuery = '';
  let userSearchResults = [];
  let isUserSearching = false;
  let userSearchTimeout: ReturnType<typeof setTimeout> | null = null;
  let showUserSuggestions = false;
  let selectedUser: { id: string; global_name: string; eu_name: string | null; matches?: any[] } | null = null;

  // Browse users dialog state
  let showBrowseDialog = false;
  let browseTableKey = 0; // Key to force table reload

  // Column definitions for browse users FancyTable
  const browseUserColumns = [
    {
      key: 'global_name',
      header: 'Discord Name',
      sortable: true,
      searchable: true,
      width: '200px',
      formatter: (value, row) => {
        const displayName = row.global_name || row.username || '-';
        return `<span style="font-weight: 500;">${escapeHtmlForTable(displayName)}</span>`;
      }
    },
    {
      key: 'eu_name',
      header: 'EU Name',
      sortable: true,
      searchable: true,
      width: '200px',
      formatter: (value) => value || '-'
    },
    {
      key: 'status',
      header: 'Status',
      sortable: false,
      searchable: false,
      width: '100px',
      formatter: (_, row) => {
        if (row.administrator) return '<span class="status-badge-impersonate admin">Admin</span>';
        if (row.verified) return '<span class="status-badge-impersonate verified">Verified</span>';
        return '<span class="status-badge-impersonate unverified">Unverified</span>';
      }
    }
  ];

  // Escape HTML for table formatters
  function escapeHtmlForTable(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Lazy fetch function for browse users FancyTable
  async function fetchBrowseUsers(offset, limit, sortBy, sortOrder, filters) {
    const page = Math.floor(offset / limit) + 1;
    let url = `/api/admin/users?page=${page}&limit=${limit}`;

    if (sortBy) url += `&sortBy=${sortBy}`;
    if (sortOrder) url += `&sortOrder=${sortOrder}`;

    // Use global_name filter as search query
    if (filters.global_name) {
      url += `&q=${encodeURIComponent(filters.global_name)}`;
    } else if (filters.eu_name) {
      url += `&q=${encodeURIComponent(filters.eu_name)}`;
    }

    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to load users');

    const data = await response.json();
    return {
      rows: data.users || [],
      total: data.total || data.users?.length || 0
    };
  }

  function handleBrowseRowClick(event) {
    const { row } = event.detail;
    if (row) {
      selectUser(row);
    }
  }

  $: isCurrentlyImpersonating = !!realUser;
  $: effectiveAdmin = realUser?.administrator || user?.administrator;
  $: isUnverified = user && !user.verified;

  // Search users as they type (for impersonation)
  async function handleUserSearchInput() {
    if (userSearchQuery.trim().length < 2) {
      userSearchResults = [];
      showUserSuggestions = false;
      return;
    }

    if (userSearchTimeout) clearTimeout(userSearchTimeout);

    userSearchTimeout = setTimeout(async () => {
      isUserSearching = true;
      try {
        const response = await fetch(`/api/admin/users?q=${encodeURIComponent(userSearchQuery.trim())}&limit=10`);
        const data = await response.json();

        if (response.ok) {
          userSearchResults = data.users || [];
          showUserSuggestions = userSearchResults.length > 0;
        }
      } catch (err) {
        console.error('Search failed:', err);
      } finally {
        isUserSearching = false;
      }
    }, 300);
  }

  function selectUser(u: typeof selectedUser) {
    selectedUser = u;
    impersonateUserId = u?.id || '';
    userSearchQuery = u ? (u.eu_name || u.global_name || '') : '';
    showUserSuggestions = false;
    showBrowseDialog = false;
  }

  function clearSelectedUser() {
    selectedUser = null;
    impersonateUserId = '';
    userSearchQuery = '';
    userSearchResults = [];
  }

  function openBrowseDialog() {
    showBrowseDialog = true;
    browseTableKey++; // Force table to reload when dialog opens
  }

  async function startImpersonation() {
    if (!impersonateUserId.trim()) return;

    impersonateError = '';
    isImpersonating = true;

    try {
      const response = await fetch('/api/admin/impersonate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: impersonateUserId.trim() })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to impersonate');
      }

      // Reload page to apply impersonation
      window.location.reload();
    } catch (err) {
      impersonateError = err.message;
    } finally {
      isImpersonating = false;
    }
  }

  function resetImpersonateDialog() {
    showImpersonateDialog = false;
    clearSelectedUser();
    impersonateError = '';
  }

  async function stopImpersonation() {
    try {
      await fetch('/api/admin/impersonate', { method: 'DELETE' });
      window.location.reload();
    } catch (err) {
      console.error('Failed to stop impersonation:', err);
    }
  }

  interface MenuItems {
    [key: string]: { label: string; url: string }[];
  }
  const menuItemsWiki: MenuItems = {
    'Items': [
      { label: 'Weapons', url: 'weapons' },
      { label: 'Armor Sets', url: 'armorsets' },
      { label: 'Medical Tools', url: 'medicaltools' },
      { label: 'Tools', url: 'tools' },
      { label: 'Attachments', url: 'attachments' },
      { label: 'Blueprints', url: 'blueprints' },
      { label: 'Materials', url: 'materials' },
      { label: 'Pets', url: 'pets' },
      { label: 'Consumables', url: 'consumables' },
      { label: 'Vehicles', url: 'vehicles' },
      { label: 'Furnishings', url: 'furnishings' },
      { label: 'Clothing', url: 'clothing' },
      { label: 'Strongboxes', url: 'strongboxes' }
    ],
    'Information': [
      { label: 'Mobs', url: 'mobs' },
      { label: 'Professions', url: 'professions' },
      { label: 'Skills', url: 'skills' },
      { label: 'Vendors', url: 'vendors' },
    ],
    'Maps': [
      { label: 'Calypso', url: 'calypso' },
      { label: 'Setesh', url: 'setesh' },
      { label: 'ARIS', url: 'aris' },
      { label: 'Cyrene', url: 'cyrene' },
      { label: 'Arkadia', url: 'arkadia' },
      { label: 'Arkadia Underground', url: 'arkadiaunderground' },
      { label: 'Arkadia Moon', url: 'arkadiamoon' },
      { label: 'Monria', url: 'monria' },
      { label: 'DSEC9', url: 'dsec9' },
      { label: 'Toulan', url: 'toulan' },
      { label: 'Rocktropia', url: 'rocktropia' },
      { label: 'HELL', url: 'hell' },
      { label: 'Secret Island', url: 'secretisland' },
      { label: 'Hunt the THING', url: 'huntthething' },
      { label: 'Next Island', url: 'nextisland' },
      { label: 'Ancient Greece', url: 'ancientgreece' },
      { label: 'Space', url: 'space' },
      { label: 'Crystal Palace', url: 'crystalpalace' },
      { label: 'Asteroid F.O.M.A', url: 'asteroidfoma' }
    ],
    'Tools': [
      { label: 'Loadout Manager', url: 'loadouts' },
      { label: 'API', url: 'api' },
    ],
    'Market': [
      { label: 'Auction', url: 'auction' },
      { label: 'Exchange', url: 'exchange' },
      { label: 'Rental', url: 'rental' },
      { label: 'Services', url: 'services' },
      { label: 'Shops', url: 'shops' },
    ],
    'External': [
      { label: 'NI Helper', url: 'nihelper' },
      { label: 'Cyrenedream', url: 'cyrenedream' },
      { label: 'Lootius.io (Ad)', url: 'lootiusio' },
    ],
  };

  // Desktop search state
  let timeout;
  let searchQuery = '';
  let searchResults = [];
  let showDropdown = false;
  let isSearching = false;

  // Mobile search state
  let mobileSearchQuery = '';
  let mobileSearchResults = [];
  let isMobileSearching = false;
  let mobileSearchTimeout: ReturnType<typeof setTimeout> | null = null;

  // Close search dropdowns on navigation
  afterNavigate(() => {
    showDropdown = false;
    searchQuery = '';
    searchResults = [];
    mobileSearchMode = false;
    mobileSearchQuery = '';
    mobileSearchResults = [];
    mobileMenuOpen = false;
  });

  // Categorized search results
  interface CategorizedResults {
    [category: string]: Array<{ Name: string; Type: string; SubType?: string }>;
  }

  $: categorizedResults = categorizeResults(searchResults);
  $: mobileCategorizedResults = categorizeResults(mobileSearchResults);

  function categorizeResults(results: Array<{ Name: string; Type: string; SubType?: string }>): CategorizedResults {
    const categories: CategorizedResults = {};

    // Smart limiting: show max 5 per category, but prioritize categories with fewer results
    const maxPerCategory = 5;
    const maxTotal = 20;

    for (const result of results) {
      const category = getTypeName(result.Type) || 'Other';
      if (!categories[category]) {
        categories[category] = [];
      }
      categories[category].push(result);
    }

    // Limit results per category smartly
    let totalShown = 0;
    const sortedCategories = Object.keys(categories).sort((a, b) => categories[a].length - categories[b].length);

    for (const cat of sortedCategories) {
      const remaining = maxTotal - totalShown;
      if (remaining <= 0) {
        categories[cat] = [];
      } else {
        const limit = Math.min(maxPerCategory, remaining);
        categories[cat] = categories[cat].slice(0, limit);
        totalShown += categories[cat].length;
      }
    }

    // Remove empty categories
    for (const cat of Object.keys(categories)) {
      if (categories[cat].length === 0) {
        delete categories[cat];
      }
    }

    return categories;
  }

  function handleSearch(event) {
    searchQuery = event.target.value;

    if (searchQuery.length < 2) {
      showDropdown = false;
      searchResults = [];
      return;
    }

    clearTimeout(timeout);
    isSearching = true;
    timeout = setTimeout(fetchSearchResults, 300);
  }

  // Fuzzy search scoring function - greedy matching
  function scoreSearchResult(name: string, query: string): number {
    const nameLower = name.toLowerCase();
    const queryLower = query.toLowerCase();

    // Exact match
    if (nameLower === queryLower) return 1000;

    // Starts with query (high score)
    if (nameLower.startsWith(queryLower)) return 900;

    // Word starts with query (e.g., "Calypso Sword" matches "sword")
    const words = nameLower.split(/\s+/);
    for (let i = 0; i < words.length; i++) {
      if (words[i].startsWith(queryLower)) {
        return 800 - i * 5; // Less penalty for later words
      }
    }

    // Contains exact substring - minimal penalty for position
    const index = nameLower.indexOf(queryLower);
    if (index !== -1) {
      return 700 - Math.min(index, 50);
    }

    // Fuzzy match: check if all characters appear in sequence
    let queryIdx = 0;
    let score = 0;
    let consecutiveBonus = 0;
    let matchPositions: number[] = [];

    for (let i = 0; i < nameLower.length && queryIdx < queryLower.length; i++) {
      if (nameLower[i] === queryLower[queryIdx]) {
        matchPositions.push(i);
        queryIdx++;
        consecutiveBonus += 10;
        score += consecutiveBonus;
        // Big bonus for matching at word boundaries
        if (i === 0 || nameLower[i - 1] === ' ' || nameLower[i - 1] === '-' || nameLower[i - 1] === '_') {
          score += 30;
        }
      } else {
        consecutiveBonus = 0;
      }
    }

    // If all query chars found in sequence, return fuzzy score
    if (queryIdx === queryLower.length) {
      const spread = matchPositions.length > 1
        ? matchPositions[matchPositions.length - 1] - matchPositions[0]
        : 0;
      const compactBonus = Math.max(0, 50 - spread);
      return 300 + score + compactBonus;
    }

    // Partial match: at least 60% of query characters found in sequence
    const matchRatio = queryIdx / queryLower.length;
    if (matchRatio >= 0.6 && queryLower.length >= 3) {
      return 100 + Math.floor(score * matchRatio);
    }

    // No match
    return 0;
  }

  function rankSearchResults(results: Array<{ Name: string; Type: string; SubType?: string }>, query: string) {
    return results
      .map(result => ({
        ...result,
        _score: scoreSearchResult(result.Name, query)
      }))
      .filter(result => result._score > 0)
      .sort((a, b) => b._score - a._score)
      .map(({ _score, ...result }) => result);
  }

  async function fetchSearchResults() {
    try {
      const response = await fetch(import.meta.env.VITE_API_URL + `/search?query=${encodeURIComponent(searchQuery)}&fuzzy=true`);
      const data = await response.json();
      searchResults = rankSearchResults(data, searchQuery);
      showDropdown = searchResults.length > 0;
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      isSearching = false;
    }
  }

  function hideDropdown() {
    setTimeout(() => {
      showDropdown = false;
    }, 200);
  }

  // Mobile search functions
  function enterMobileSearchMode() {
    mobileSearchMode = true;
    mobileSearchQuery = '';
    mobileSearchResults = [];
  }

  function exitMobileSearchMode() {
    mobileSearchMode = false;
    mobileSearchQuery = '';
    mobileSearchResults = [];
  }

  function handleMobileSearch(event) {
    mobileSearchQuery = event.target.value;

    if (mobileSearchQuery.length < 2) {
      mobileSearchResults = [];
      return;
    }

    if (mobileSearchTimeout) clearTimeout(mobileSearchTimeout);
    isMobileSearching = true;

    mobileSearchTimeout = setTimeout(async () => {
      try {
        const response = await fetch(import.meta.env.VITE_API_URL + `/search?query=${encodeURIComponent(mobileSearchQuery)}&fuzzy=true`);
        const data = await response.json();
        mobileSearchResults = rankSearchResults(data, mobileSearchQuery);
      } catch (err) {
        console.error('Mobile search failed:', err);
      } finally {
        isMobileSearching = false;
      }
    }, 300);
  }

  function handleMobileSearchResultClick() {
    closeMobileMenu();
  }

  function setDarkModePreference(isDarkMode) {
    if (typeof window === 'undefined') return;

    darkMode.set(isDarkMode);
    localStorage.setItem('darkMode', isDarkMode ? 'true' : 'false');
  }

  function getMenuItemUrl(menu: string, item: { label: string; url: string }) {
    if (item.url === 'api') return `${import.meta.env.VITE_API_URL}/docs/`;
    if (item.url === 'nihelper') return 'https://www.nihelper.com';
    if (item.url === 'cyrenedream') return 'https://www.cyrenedream.org';
    if (item.url === 'lootiusio') return 'https://www.lootius.io/User/Register/1456';
    return `/${menu.toLowerCase()}/${item.url.toLowerCase()}`;
  }

  function isExternalLink(item: { label: string; url: string }) {
    return ['api', 'nihelper', 'cyrenedream', 'lootiusio'].includes(item.url);
  }
</script>

<style>
  nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: var(--secondary-color);
    height: 56px;
    padding: 0 16px;
    font-family: 'Arial', sans-serif;
    font-size: 14px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
    position: relative;
    z-index: 100;
  }

  .menu-container, .auth-container {
    display: flex;
    position: relative;
    align-items: center;
    height: 100%;
    gap: 4px;
  }

  .website-icon {
    width: 36px;
    height: 36px;
    margin-right: 12px;
  }

  .menu-item {
    padding: 0 12px;
    cursor: pointer;
    display: flex;
    align-items: center;
    height: 100%;
    position: relative;
    transition: background-color 0.15s ease;
    border-radius: 4px;
  }

  .menu-item:hover {
    background-color: var(--hover-color);
  }

  .dropdown-content {
    display: none;
    position: absolute;
    left: 0;
    min-width: 180px;
    top: calc(100% + 4px);
    background-color: var(--secondary-color);
    box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.3);
    z-index: 100;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 4px 0;
    overflow: hidden;
  }

  .dropdown-content.right {
    left: auto;
    right: 0;
    min-width: 220px;
  }

  .dropdown-content.open {
    display: block;
  }

  .menu-dropdown-item {
    padding: 10px 14px;
    white-space: nowrap;
    font-size: 13px;
    color: var(--text-color);
    transition: background-color 0.15s ease;
    margin: 2px 4px;
    border-radius: 4px;
  }

  .menu-dropdown-item:hover {
    background-color: var(--hover-color);
  }

  .menu-dropdown-item:first-child {
    margin-top: 0;
  }

  .menu-dropdown-item:last-child {
    margin-bottom: 0;
  }

  .dropdown-content a {
    display: block;
    margin: 2px 4px;
    border-radius: 4px;
    color: var(--text-color);
  }

  .dropdown-content a .menu-dropdown-item {
    margin: 0;
  }

  .dropdown-content a:hover {
    background-color: var(--hover-color);
  }

  .dropdown-content a:first-child {
    margin-top: 0;
  }

  .dropdown-content a:last-child {
    margin-bottom: 0;
  }

  .menu-item-icon {
    display: inline-block;
    width: 20px;
    text-align: center;
    margin-right: 6px;
  }

  a {
    text-decoration: none;
  }

  .search {
    font-size: 14px;
    padding: 6px 10px;
    border-radius: 4px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-color);
    color: var(--text-color);
    width: 280px;
  }

  .search-container {
    position: relative;
    margin-left: 20px;
  }

  .dropdown-search {
    position: absolute;
    top: 100%;
    right: 0;
    z-index: 100;
    width: 100%;
    min-width: 280px;
    max-height: 400px;
    overflow-y: auto;
    box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.3);
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .search-category {
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted);
    background-color: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
    letter-spacing: 0.5px;
  }

  .search-result-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    cursor: pointer;
    border-bottom: 1px solid var(--border-color);
    transition: background-color 0.15s ease;
  }

  .search-result-item:last-child {
    border-bottom: none;
  }

  .search-result-item:hover {
    background-color: var(--hover-color);
  }

  .search-result-name {
    font-size: 14px;
    color: var(--text-color);
  }

  .search-result-type {
    font-size: 11px;
    color: var(--text-muted);
    padding: 2px 6px;
    background-color: var(--primary-color);
    border-radius: 3px;
  }

  .search-loading {
    padding: 16px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }

  .menu-item:hover, .menu-dropdown-item:hover {
    background-color: var(--hover-color);
  }

  /* Make button dropdown items look like regular items */
  button.menu-dropdown-item {
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    font-size: 13px;
    font-family: inherit;
    color: inherit;
    cursor: pointer;
    padding: 8px 12px;
  }

  .dark-light-toggle {
    margin-left: 8px;
  }

  .dark-light-button {
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    padding: 8px;
    margin: 0;
    font: inherit;
    color: inherit;
    cursor: pointer;
    border-radius: 4px;
    transition: background-color 0.15s ease;
  }

  .dark-light-button:hover {
    background-color: var(--hover-color);
  }

  .dark-light-button img {
    width: 20px;
    height: 20px;
  }

  .discord-button {
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: #5865F2;
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    margin-left: 20px;
  }

  .discord-button:hover {
    background-color: #4752C4;
  }

  .discord-button img {
    width: 18px;
    height: 18px;
    margin-right: 6px;
  }

  .user {
    margin-left: 12px;
  }

  .user-image {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    transition: box-shadow 0.15s ease;
  }

  .user-image.impersonating {
    box-shadow: 0 0 0 2px var(--error-color, #ef4444);
  }

  .unverified-badge {
    position: absolute;
    top: 50%;
    left: -4px;
    transform: translateY(-50%);
    font-size: 12px;
    font-weight: bold;
    color: white;
    background-color: var(--warning-color, #f59e0b);
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .unverified-notice {
    font-size: 12px;
    color: var(--warning-color, #f59e0b);
    background-color: rgba(245, 158, 11, 0.1);
    border-radius: 4px;
  }

  .verify-link {
    display: block;
    margin: 2px 4px;
  }

  .verify-btn {
    background-color: var(--success-color, #10b981);
    color: white;
    font-weight: 500;
    text-align: center;
    border-radius: 4px;
    margin: 0;
  }

  .verify-btn:hover {
    filter: brightness(1.1);
  }

  .impersonate-info {
    font-size: 12px;
    color: var(--text-muted);
    background-color: rgba(251, 191, 36, 0.1);
    border-radius: 4px;
  }

  .stop-impersonate-btn {
    background-color: var(--error-bg);
    color: var(--error-color);
    border: none;
    cursor: pointer;
    width: calc(100% - 8px);
    text-align: left;
    border-radius: 4px;
  }

  .stop-impersonate-btn:hover {
    background-color: var(--error-color);
    color: white;
  }

  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .dialog {
    background-color: var(--secondary-color);
    padding: 24px;
    border-radius: 8px;
    max-width: 400px;
    width: 90%;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  }

  .dialog h3 {
    margin: 0 0 12px 0;
    color: var(--text-color);
  }

  .dialog-description {
    font-size: 14px;
    color: var(--text-muted);
    margin: 0 0 16px 0;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-group label {
    display: block;
    margin-bottom: 4px;
    font-size: 14px;
    color: var(--text-color);
  }

  .form-group input {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-color);
    font-size: 14px;
    box-sizing: border-box;
  }

  .error-message {
    background-color: var(--error-bg);
    color: var(--error-color);
    padding: 8px 12px;
    border-radius: 4px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  .dialog-buttons {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
  }

  .btn-primary, .btn-secondary {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    border: none;
  }

  .btn-primary {
    background-color: var(--accent-color);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background-color: var(--accent-color-hover);
  }

  .btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    transition: all 0.15s ease;
  }

  .btn-secondary:hover:not(:disabled) {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  /* Wider dialog for impersonate */
  .dialog-wide {
    max-width: 500px;
  }

  .dialog-large {
    max-width: 700px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  /* Search input with suggestions */
  .search-input-wrapper {
    position: relative;
  }

  .search-spinner {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: translateY(-50%) rotate(360deg); }
  }

  .selected-user-chip {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background-color: var(--hover-color);
    border: 1px solid var(--accent-color);
    border-radius: 4px;
  }

  .selected-user-name {
    color: var(--text-color);
    font-size: 14px;
  }

  .chip-remove {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 18px;
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }

  .chip-remove:hover {
    color: var(--error-color);
  }

  .suggestions-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    max-height: 250px;
    overflow-y: auto;
    z-index: 10;
  }

  .suggestion-item {
    padding: 10px 12px;
    cursor: pointer;
    border-bottom: 1px solid var(--border-color);
  }

  .suggestion-item:last-child {
    border-bottom: none;
  }

  .suggestion-item:hover {
    background-color: var(--hover-color);
  }

  .suggestion-name {
    font-size: 14px;
    color: var(--text-color);
    font-weight: 500;
  }

  .verified-badge {
    color: var(--success-color, #10b981);
    font-size: 12px;
    margin-left: 4px;
  }

  .suggestion-eu-name {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .suggestion-matches {
    display: flex;
    gap: 4px;
    margin-top: 4px;
  }

  .match-tag {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    background-color: var(--accent-color);
    color: white;
  }

  .browse-section {
    margin-bottom: 16px;
    text-align: center;
  }

  .btn-browse {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    transition: all 0.15s ease;
  }

  .btn-browse:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  /* Browse dialog FancyTable wrapper */
  .browse-table-wrapper {
    height: 400px;
    margin-bottom: 16px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  /* Status badges for impersonate dialog (global for FancyTable formatters) */
  :global(.status-badge-impersonate) {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
  }

  :global(.status-badge-impersonate.admin) {
    background-color: rgba(139, 92, 246, 0.2);
    color: #8b5cf6;
  }

  :global(.status-badge-impersonate.verified) {
    background-color: rgba(16, 185, 129, 0.2);
    color: var(--success-color, #10b981);
  }

  :global(.status-badge-impersonate.unverified) {
    background-color: rgba(245, 158, 11, 0.2);
    color: var(--warning-color, #f59e0b);
  }

  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-bottom: 16px;
  }

  .btn-page {
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    transition: all 0.15s ease;
  }

  .btn-page:hover:not(:disabled) {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .btn-page:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .page-info {
    font-size: 13px;
    color: var(--text-muted);
  }

  .browse-content {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .browse-content.loading {
    pointer-events: none;
  }

  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 5;
    border-radius: 4px;
  }

  .loading-spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--accent-color);
    border-radius: 50%;
    animation: spinFull 0.8s linear infinite;
  }

  @keyframes spinFull {
    to { transform: rotate(360deg); }
  }

  /* Mobile Menu Styles */
  .burger-button {
    display: none;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    width: 40px;
    height: 40px;
    background: none;
    border: none;
    cursor: pointer;
    padding: 8px;
    border-radius: 4px;
    transition: background-color 0.15s ease;
    margin-left: 8px;
  }

  .burger-button:hover {
    background-color: var(--hover-color);
  }

  .logo-link {
    display: flex;
    align-items: center;
  }

  .burger-line {
    width: 20px;
    height: 2px;
    background-color: var(--text-color);
    margin: 2px 0;
    transition: all 0.3s ease;
  }

  .burger-button.open .burger-line:nth-child(1) {
    transform: translateY(6px) rotate(45deg);
  }

  .burger-button.open .burger-line:nth-child(2) {
    opacity: 0;
  }

  .burger-button.open .burger-line:nth-child(3) {
    transform: translateY(-6px) rotate(-45deg);
  }

  .mobile-menu {
    display: none;
    position: fixed;
    top: 56px;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: var(--secondary-color);
    z-index: 100;
    overflow-y: auto;
    flex-direction: column;
  }

  .mobile-menu.open {
    display: flex;
  }

  .mobile-menu-content {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
  }

  /* Mobile Search Section */
  .mobile-search-section {
    padding: 16px;
    background-color: var(--primary-color);
    border-bottom: 1px solid var(--border-color);
  }

  .mobile-search-input-wrapper {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .mobile-search-input {
    flex: 1;
    padding: 12px 16px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 16px;
  }

  .mobile-search-input:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .mobile-search-cancel {
    padding: 12px 16px;
    background: none;
    border: none;
    color: var(--accent-color);
    font-size: 14px;
    cursor: pointer;
    white-space: nowrap;
  }

  .mobile-search-results {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }

  .mobile-search-category {
    padding: 12px 16px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted);
    background-color: var(--primary-color);
    letter-spacing: 0.5px;
    position: sticky;
    top: 0;
  }

  .mobile-search-result-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid var(--border-color);
    text-decoration: none;
    color: var(--text-color);
  }

  .mobile-search-result-item:active {
    background-color: var(--hover-color);
  }

  .mobile-search-empty {
    padding: 32px 16px;
    text-align: center;
    color: var(--text-muted);
  }

  .mobile-search-loading {
    padding: 32px 16px;
    text-align: center;
    color: var(--text-muted);
  }

  /* Collapsible sections */
  .mobile-section {
    margin-bottom: 8px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .mobile-section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    background-color: var(--hover-color);
    cursor: pointer;
    user-select: none;
  }

  .mobile-section-header:active {
    background-color: var(--primary-color);
  }

  .mobile-section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-color);
  }

  .mobile-section-chevron {
    font-size: 12px;
    color: var(--text-muted);
    transition: transform 0.2s ease;
  }

  .mobile-section-chevron.expanded {
    transform: rotate(180deg);
  }

  .mobile-section-items {
    display: none;
    background-color: var(--secondary-color);
  }

  .mobile-section-items.expanded {
    display: block;
  }

  .mobile-menu-item {
    display: block;
    padding: 12px 16px;
    color: var(--text-color);
    text-decoration: none;
    border-top: 1px solid var(--border-color);
  }

  .mobile-menu-item:active {
    background-color: var(--hover-color);
  }

  /* Mobile User Section */
  .mobile-user-section {
    border-top: 1px solid var(--border-color);
    padding: 16px;
    background-color: var(--primary-color);
  }

  .mobile-user-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .mobile-user-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
  }

  .mobile-user-info {
    flex: 1;
    min-width: 0;
  }

  .mobile-user-quick-actions {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }

  .mobile-quick-btn {
    width: 36px;
    height: 36px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 18px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.15s ease;
    text-decoration: none;
  }

  .mobile-quick-btn:active {
    background-color: var(--hover-color);
  }

  a.mobile-quick-btn {
    text-decoration: none;
  }

  .mobile-user-actions-guest {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .mobile-user-actions-guest .mobile-user-action {
    flex: 1;
  }

  .mobile-user-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-color);
  }

  .mobile-user-status {
    font-size: 12px;
    color: var(--text-muted);
  }

  .mobile-user-actions {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .mobile-user-action {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    text-decoration: none;
    cursor: pointer;
  }

  .mobile-user-action:active {
    background-color: var(--hover-color);
  }

  .mobile-user-action.danger {
    border-color: var(--error-color);
    color: var(--error-color);
  }

  .mobile-user-action.primary {
    background-color: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }

  .mobile-user-action.success {
    background-color: var(--success-color);
    border-color: var(--success-color);
    color: white;
  }

  .mobile-action-icon {
    font-size: 18px;
    width: 24px;
    text-align: center;
  }

  .mobile-action-text {
    flex: 1;
    font-size: 14px;
  }

  .mobile-discord-icon {
    width: 20px;
    height: 20px;
  }

  /* Mobile responsive breakpoint */
  @media (max-width: 900px) {
    nav {
      position: relative;
    }

    .menu-container {
      position: static;
    }

    .menu-container .menu-item:not(.logo-item) {
      display: none;
    }

    .logo-link {
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
    }

    .burger-button {
      display: flex;
    }

    .search-container {
      display: none;
    }

    .auth-container .user {
      display: none;
    }

    .auth-container .dark-light-toggle {
      display: none;
    }

    .auth-container .discord-button,
    .auth-container a:has(.discord-button) {
      display: none;
    }
  }

  @media (max-width: 500px) {
    nav {
      padding: 0 8px;
    }

    .website-icon {
      width: 32px;
      height: 32px;
      margin-right: 8px;
    }

    .discord-button {
      padding: 6px 8px;
    }
  }
</style>

<nav>
  <div class="menu-container">
    <a href="/" class="logo-link"><img class="website-icon" src="/favicon.png" alt="Entropia Nexus" title="Entropia Nexus" width="48px" height="48px" /></a>
    {#each Object.keys(menuItemsWiki) as menu (menu)}
      {#if !(menu === 'Market' && !(user && user.administrator))}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="menu-item" on:mouseenter={() => handleDropdownEnter(menu)} on:mouseleave={handleDropdownLeave}>
          {menu}
          <div class="dropdown-content" class:open={dropdownOpen === menu}>
              {#each menuItemsWiki[menu] as item (item)}
                {#if isExternalLink(item)}
                  <a href={getMenuItemUrl(menu, item)} target="_blank"><div class="menu-dropdown-item">{item.label}</div></a>
                {:else}
                  <a use:loading href={getMenuItemUrl(menu, item)}><div class="menu-dropdown-item">{item.label}</div></a>
                {/if}
              {/each}
          </div>
      </div>
    {/if}
    {/each}
  </div>

  <div class="auth-container">
    <div class="search-container">
      <input type="text" placeholder="Search..." class="search" on:blur={hideDropdown} on:focus={(evt) => { evt.target.select(); handleSearch(evt); }} on:input={handleSearch} />
      {#if showDropdown || isSearching}
        <div class="dropdown-search">
          {#if isSearching}
            <div class="search-loading">Searching...</div>
          {:else}
            {#each Object.keys(categorizedResults) as category}
              <div class="search-category">{category}</div>
              {#each categorizedResults[category] as result}
                <a use:loading href={getTypeLink(result.Name, result.Type, result.SubType)} class="search-result-item">
                  <span class="search-result-name">{result.Name}</span>
                  <span class="search-result-type">{getTypeName(result.Type)}</span>
                </a>
              {/each}
            {/each}
          {/if}
        </div>
      {/if}
    </div>
    {#if user == null}
      <a href="/login">
        <button class="discord-button">
          <img src="/discord.svg" alt="Discord Login" width="24px" height="24px" /> <span>Login with Discord</span>
        </button>
      </a>
    {:else}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="menu-item user" on:mouseenter={() => handleDropdownEnter('user')} on:mouseleave={handleDropdownLeave}>
        {#if !isCurrentlyImpersonating && isUnverified}
          <span class="unverified-badge" title="Account not verified">!</span>
        {/if}
        <img
          src={user.avatar ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png` : `https://cdn.discordapp.com/embed/avatars/${Number(user.id) % 5}.png`}
          class="user-image"
          class:impersonating={isCurrentlyImpersonating}
          alt="Discord Avatar"
          title={isCurrentlyImpersonating ? `Impersonating ${user.global_name || user.username}` : ''}
        />
        <div class="dropdown-content right" class:open={dropdownOpen === 'user'}>
          {#if isCurrentlyImpersonating}
            <div class="menu-dropdown-item impersonate-info">
              Impersonating: {user.global_name || user.username}
            </div>
            <div class="menu-dropdown-item impersonate-info">
              (Admin: {realUser.global_name || realUser.username})
            </div>
            <button class="menu-dropdown-item stop-impersonate-btn" on:click={stopImpersonation}>
              Stop Impersonating
            </button>
          {:else}
            <div class="menu-dropdown-item">Logged in as {user.discriminator == 0 ? user.global_name : `${user.username}#${user.discriminator}`}</div>
            {#if isUnverified}
              <div class="menu-dropdown-item unverified-notice">
                Account not verified
              </div>
              <a href="/account/setup" class="verify-link">
                <div class="menu-dropdown-item verify-btn">
                  Verify Account
                </div>
              </a>
            {/if}
          {/if}
          {#if effectiveAdmin && !isCurrentlyImpersonating}
            <a use:loading href="/admin"><div class="menu-dropdown-item"><span class="menu-item-icon">⚙️</span> Admin Dashboard</div></a>
            <button class="menu-dropdown-item" on:click={() => showImpersonateDialog = true}>
              <span class="menu-item-icon">🎭</span> Impersonate User
            </button>
          {/if}
          <a use:loading href="/discord/logout"><div class="menu-dropdown-item"><span class="menu-item-icon">→</span> Logout</div></a>
        </div>
      </div>
    {/if}
    <div class="dark-light-toggle">
      {#if $darkMode === null || $darkMode === false}
        <button class="dark-light-button" on:click={() => setDarkModePreference(true)}><img width="20px" height="20px" src={'/dark.png'} alt="Dark mode button" title="Enable Dark Mode" /></button>
      {:else}
        <button class="dark-light-button" on:click={() => setDarkModePreference(false)}><img width="20px" height="20px" src={'/light.png'} alt="Light mode button" title="Disable Dark Mode" /></button>
      {/if}
    </div>
    <button class="burger-button" class:open={mobileMenuOpen} on:click={toggleMobileMenu} aria-label="Toggle menu">
      <span class="burger-line"></span>
      <span class="burger-line"></span>
      <span class="burger-line"></span>
    </button>
  </div>
</nav>

<!-- Mobile Menu -->
<div class="mobile-menu" class:open={mobileMenuOpen}>
  <!-- Search Section (always at top) -->
  <div class="mobile-search-section">
    <div class="mobile-search-input-wrapper">
      <input
        type="text"
        class="mobile-search-input"
        placeholder="Search items, mobs, maps..."
        bind:value={mobileSearchQuery}
        on:input={handleMobileSearch}
        on:focus={enterMobileSearchMode}
      />
      {#if mobileSearchMode}
        <button class="mobile-search-cancel" on:click={exitMobileSearchMode}>Cancel</button>
      {/if}
    </div>
  </div>

  {#if mobileSearchMode}
    <!-- Search Results Mode -->
    <div class="mobile-search-results">
      {#if isMobileSearching}
        <div class="mobile-search-loading">Searching...</div>
      {:else if mobileSearchQuery.length < 2}
        <div class="mobile-search-empty">Type at least 2 characters to search</div>
      {:else if Object.keys(mobileCategorizedResults).length === 0}
        <div class="mobile-search-empty">No results found for "{mobileSearchQuery}"</div>
      {:else}
        {#each Object.keys(mobileCategorizedResults) as category}
          <div class="mobile-search-category">{category} ({mobileCategorizedResults[category].length})</div>
          {#each mobileCategorizedResults[category] as result}
            <a
              use:loading
              href={getTypeLink(result.Name, result.Type, result.SubType)}
              class="mobile-search-result-item"
              on:click={handleMobileSearchResultClick}
            >
              <span class="search-result-name">{result.Name}</span>
              <span class="search-result-type">{getTypeName(result.Type)}</span>
            </a>
          {/each}
        {/each}
      {/if}
    </div>
  {:else}
    <!-- Navigation Mode -->
    <div class="mobile-menu-content">
      {#each Object.keys(menuItemsWiki) as menu (menu)}
        {#if !(menu === 'Market' && !(user && user.administrator))}
          <div class="mobile-section">
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <div class="mobile-section-header" on:click={() => toggleSection(menu)}>
              <span class="mobile-section-title">{menu}</span>
              <span class="mobile-section-chevron" class:expanded={expandedSections.has(menu)}>&#9660;</span>
            </div>
            <div class="mobile-section-items" class:expanded={expandedSections.has(menu)}>
              {#each menuItemsWiki[menu] as item (item)}
                {#if isExternalLink(item)}
                  <a href={getMenuItemUrl(menu, item)} target="_blank" class="mobile-menu-item" on:click={closeMobileMenu}>{item.label}</a>
                {:else}
                  <a use:loading href={getMenuItemUrl(menu, item)} class="mobile-menu-item" on:click={closeMobileMenu}>{item.label}</a>
                {/if}
              {/each}
            </div>
          </div>
        {/if}
      {/each}
    </div>

    <!-- User Section (at bottom) -->
    <div class="mobile-user-section">
      {#if user}
        <div class="mobile-user-header">
          <img
            src={user.avatar ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png` : `https://cdn.discordapp.com/embed/avatars/${Number(user.id) % 5}.png`}
            class="mobile-user-avatar"
            alt="Avatar"
          />
          <div class="mobile-user-info">
            <div class="mobile-user-name">{user.global_name || user.username}</div>
            <div class="mobile-user-status">
              {#if isCurrentlyImpersonating}
                Impersonating (Admin: {realUser.global_name || realUser.username})
              {:else if isUnverified}
                Not verified
              {:else}
                Verified
              {/if}
            </div>
          </div>
          <div class="mobile-user-quick-actions">
            <!-- Dark/Light Mode Toggle (small) -->
            <button
              class="mobile-quick-btn"
              on:click={() => setDarkModePreference(!$darkMode)}
              title={$darkMode ? 'Light Mode' : 'Dark Mode'}
            >
              {$darkMode ? '☀' : '☾'}
            </button>
            {#if effectiveAdmin && !isCurrentlyImpersonating}
              <a
                href="/admin"
                class="mobile-quick-btn"
                on:click={closeMobileMenu}
                title="Admin Dashboard"
                use:loading
              >
                ⚙️
              </a>
              <button
                class="mobile-quick-btn"
                on:click={() => { closeMobileMenu(); showImpersonateDialog = true; }}
                title="Impersonate User"
              >
                🎭
              </button>
            {/if}
          </div>
        </div>

        <div class="mobile-user-actions">
          {#if isCurrentlyImpersonating}
            <button class="mobile-user-action danger" on:click={stopImpersonation}>
              <span class="mobile-action-icon">✕</span>
              <span class="mobile-action-text">Stop Impersonating</span>
            </button>
          {:else if isUnverified}
            <a href="/account/setup" class="mobile-user-action success" on:click={closeMobileMenu}>
              <span class="mobile-action-icon">✓</span>
              <span class="mobile-action-text">Verify Account</span>
            </a>
            <a use:loading href="/discord/logout" class="mobile-user-action" on:click={closeMobileMenu}>
              <span class="mobile-action-icon">→</span>
              <span class="mobile-action-text">Logout</span>
            </a>
          {:else}
            <a href="/account" class="mobile-user-action" on:click={closeMobileMenu}>
              <span class="mobile-action-icon">⚙</span>
              <span class="mobile-action-text">User Profile</span>
            </a>
            <a use:loading href="/discord/logout" class="mobile-user-action" on:click={closeMobileMenu}>
              <span class="mobile-action-icon">→</span>
              <span class="mobile-action-text">Logout</span>
            </a>
          {/if}
        </div>
      {:else}
        <div class="mobile-user-actions-guest">
          <!-- Dark/Light Mode Toggle (small, aligned right) -->
          <button
            class="mobile-quick-btn"
            on:click={() => setDarkModePreference(!$darkMode)}
            title={$darkMode ? 'Light Mode' : 'Dark Mode'}
          >
            {$darkMode ? '☀' : '☾'}
          </button>
          <a href="/login" class="mobile-user-action primary" on:click={closeMobileMenu}>
            <img src="/discord.svg" alt="" class="mobile-discord-icon" />
            <span class="mobile-action-text">Login with Discord</span>
          </a>
        </div>
      {/if}
    </div>
  {/if}
</div>

{#if showImpersonateDialog}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="dialog-overlay" on:click={resetImpersonateDialog}>
    <div class="dialog dialog-wide" on:click|stopPropagation>
      <h3>Impersonate User</h3>
      <p class="dialog-description">Search for a user by their Discord name or EU character name.</p>

      {#if impersonateError}
        <div class="error-message">{impersonateError}</div>
      {/if}

      <div class="form-group">
        <label for="impersonate-search">Search User</label>
        <div class="search-input-wrapper">
          {#if selectedUser}
            <div class="selected-user-chip">
              <span class="selected-user-name">{selectedUser.eu_name || selectedUser.global_name}</span>
              <button type="button" class="chip-remove" on:click={clearSelectedUser}>&#10005;</button>
            </div>
          {:else}
            <input
              id="impersonate-search"
              type="text"
              bind:value={userSearchQuery}
              on:input={handleUserSearchInput}
              on:focus={() => { if (userSearchResults.length > 0) showUserSuggestions = true; }}
              placeholder="Type to search by name..."
              disabled={isImpersonating}
              autocomplete="off"
            />
            {#if isUserSearching}
              <span class="search-spinner"></span>
            {/if}
          {/if}
        </div>

        {#if showUserSuggestions && userSearchResults.length > 0}
          <div class="suggestions-dropdown">
            {#each userSearchResults as result}
              <!-- svelte-ignore a11y-click-events-have-key-events -->
              <!-- svelte-ignore a11y-no-static-element-interactions -->
              <div class="suggestion-item" on:click={() => selectUser(result)}>
                <div class="suggestion-name">
                  {result.global_name || result.username}
                  {#if result.verified}
                    <span class="verified-badge" title="Verified">&#10003;</span>
                  {/if}
                </div>
                {#if result.eu_name}
                  <div class="suggestion-eu-name">EU: {result.eu_name}</div>
                {/if}
                <div class="suggestion-matches">
                  {#each result.matches || [] as match}
                    <span class="match-tag">{match.label}</span>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="browse-section">
        <button type="button" class="btn-browse" on:click={openBrowseDialog}>
          Browse All Users
        </button>
      </div>

      <div class="dialog-buttons">
        <button class="btn-secondary" on:click={resetImpersonateDialog} disabled={isImpersonating}>
          Cancel
        </button>
        <button class="btn-primary" on:click={startImpersonation} disabled={isImpersonating || !impersonateUserId.trim()}>
          {isImpersonating ? 'Impersonating...' : 'Impersonate'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showBrowseDialog}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="dialog-overlay" on:click={() => showBrowseDialog = false}>
    <div class="dialog dialog-large" on:click|stopPropagation>
      <h3>Browse Users</h3>
      <p class="dialog-description">Click on a row to select a user. Use the search boxes to filter.</p>

      <div class="browse-table-wrapper">
        {#key browseTableKey}
          <FancyTable
            columns={browseUserColumns}
            fetchData={fetchBrowseUsers}
            rowHeight={44}
            pageSize={50}
            sortable={true}
            searchable={true}
            emptyMessage="No users found"
            on:rowClick={handleBrowseRowClick}
          />
        {/key}
      </div>

      <div class="dialog-buttons">
        <button class="btn-secondary" on:click={() => showBrowseDialog = false}>
          Close
        </button>
      </div>
    </div>
  </div>
{/if}
