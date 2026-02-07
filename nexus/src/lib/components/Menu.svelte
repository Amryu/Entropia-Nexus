<script lang="ts">
  // @ts-nocheck

  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';
  import { afterNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';

  import { darkMode } from '../../stores.js';

  import { getTypeLink, getTypeName, encodeURIComponentSafe } from "$lib/util";
  import { loading } from "../../actions/loading";
  import FancyTable from '$lib/components/FancyTable.svelte';
  import SearchInput from '$lib/components/SearchInput.svelte';

  export let user;
  export let realUser = null; // The actual admin user when impersonating

  // Login/Logout URLs with redirect back to current page
  $: loginUrl = `/discord/login?redirect=${encodeURIComponent($page.url.pathname + $page.url.search)}`;
  $: logoutUrl = `/discord/logout?redirect=${encodeURIComponent($page.url.pathname + $page.url.search)}`;
  $: profileUrl = user ? `/users/${encodeURIComponentSafe(String(user.eu_name || user.id))}` : '/discord/login';

  let dropdownOpen: string | null = null;
  let dropdownCloseTimeout: ReturnType<typeof setTimeout> | null = null;
  let showImpersonateDialog = false;
  let mobileMenuOpen = false;
  let expandedSections: Set<string> = new Set();
  let mobileSearchMode = false;
  let mobileUserExpanded = false; // Track mobile user panel expanded state

  // Notifications state
  let notifications = [];
  let notificationsLoading = false;
  let notificationsError = '';
  let notificationsPage = 1;
  const notificationsPageSize = 8;
  let notificationsTotal = 0;
  let notificationsUnread = 0;
  let notificationsLastLoaded = 0;

  $: notificationsTotalPages = Math.max(1, Math.ceil(notificationsTotal / notificationsPageSize));

  // Media query for auto-closing mobile menu
  let mediaQuery: MediaQueryList | null = null;

  function handleGlobalKeydown(event: KeyboardEvent) {
    // Ctrl+F or Cmd+F on Mac
    if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
      // Check if desktop search input is currently focused
      const searchContainer = document.querySelector('.search-container');
      const isSearchFocused = searchContainer && searchContainer.contains(document.activeElement);

      if (isSearchFocused) {
        // Let browser's native search work
        return;
      }

      // Focus the search input
      event.preventDefault();
      desktopSearchRef?.focus?.();
    }
  }

  onMount(() => {
    if (typeof window !== 'undefined') {
      mediaQuery = window.matchMedia('(max-width: 899px)');
      mediaQuery.addEventListener('change', handleMediaChange);
      document.addEventListener('keydown', handleGlobalKeydown);
    }
  });

  onDestroy(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', handleMediaChange);
    }
    if (dropdownCloseTimeout) clearTimeout(dropdownCloseTimeout);
    if (typeof window !== 'undefined') {
      document.removeEventListener('keydown', handleGlobalKeydown);
    }
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
    mobileSearchValue = '';
    mobileSearchRef?.clear?.();
  }

  function handleDropdownEnter(menu: string) {
    if (dropdownCloseTimeout) {
      clearTimeout(dropdownCloseTimeout);
      dropdownCloseTimeout = null;
    }
    dropdownOpen = menu;
    if (menu === 'notifications' && user) {
      loadNotifications(1, { force: true });
    }
  }

  function handleDropdownLeave() {
    dropdownCloseTimeout = setTimeout(() => {
      dropdownOpen = null;
      dropdownCloseTimeout = null;
    }, 150);
  }

  function formatNotificationDate(dateStr) {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleString();
  }

  async function loadNotifications(page = notificationsPage, { force = false } = {}) {
    if (!user) return;
    if (notificationsLoading) return;
    const now = Date.now();
    if (!force && now - notificationsLastLoaded < 15000 && page === notificationsPage) return;

    notificationsLoading = true;
    notificationsError = '';
    try {
      const response = await fetch(`/api/notifications?page=${page}&pageSize=${notificationsPageSize}`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Failed to load notifications.');
      }
      notifications = payload.rows || [];
      notificationsTotal = payload.total || 0;
      notificationsUnread = payload.unread || 0;
      notificationsPage = payload.page || page;
      notificationsLastLoaded = now;
    } catch (err) {
      notificationsError = err.message || 'Failed to load notifications.';
    } finally {
      notificationsLoading = false;
    }
  }

  async function markNotificationRead(notification) {
    if (!notification || notification.read) return;
    try {
      const response = await fetch(`/api/notifications/${notification.id}`, { method: 'PATCH' });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.error || 'Failed to mark notification as read.');
      }
      notifications = notifications.map(item => item.id === notification.id ? { ...item, read: true } : item);
      notificationsUnread = Math.max(0, notificationsUnread - 1);
    } catch (err) {
      notificationsError = err.message || 'Failed to mark notification as read.';
    }
  }

  async function markAllNotificationsRead() {
    if (notificationsUnread === 0) return;
    try {
      const response = await fetch('/api/notifications/read-all', { method: 'POST' });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.error || 'Failed to mark all as read.');
      }
      notifications = notifications.map(item => ({ ...item, read: true }));
      notificationsUnread = 0;
    } catch (err) {
      notificationsError = err.message || 'Failed to mark all as read.';
    }
  }

  function changeNotificationsPage(nextPage) {
    if (nextPage < 1 || nextPage > notificationsTotalPages) return;
    loadNotifications(nextPage, { force: true });
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
      { label: 'Missions', url: 'missions' },
      { label: 'Professions', url: 'professions' },
      { label: 'Skills', url: 'skills' },
      { label: 'Vendors', url: 'vendors' },
      { label: 'Locations', url: 'locations' },
      { label: 'Guides', url: 'guides' },
    ],
    'Maps': [
      { label: 'Calypso', url: 'calypso' },
      { label: 'Cyrene', url: 'cyrene' },
      { label: 'Arkadia', url: 'arkadia' },
      { label: 'Monria', url: 'monria' },
      { label: 'Toulan', url: 'toulan' },
      { label: 'Rocktropia', url: 'rocktropia' },
      { label: 'Next Island', url: 'nextisland' },
      { label: 'Space', url: 'space' },
    ],
    'Tools': [
      { label: 'Loadout Manager', url: 'loadouts' },
      { label: 'Construction Calculator', url: 'construction' },
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

  // Desktop search state (now managed by SearchInput component)
  let desktopSearchValue = '';
  let desktopSearchRef;

  // Mobile search state (now managed by SearchInput component)
  let mobileSearchValue = '';
  let mobileSearchRef;

  // Close search dropdowns on navigation
  afterNavigate(() => {
    desktopSearchValue = '';
    mobileSearchValue = '';
    mobileSearchMode = false;
    mobileMenuOpen = false;
    desktopSearchRef?.clear?.();
    mobileSearchRef?.clear?.();
  });

  // Mobile search functions
  function enterMobileSearchMode() {
    mobileSearchMode = true;
    mobileSearchValue = '';
  }

  function exitMobileSearchMode() {
    mobileSearchMode = false;
    mobileSearchValue = '';
    mobileSearchRef?.clear?.();
  }

  function handleSearchSelect(event) {
    // Navigate to the selected result
    goto(event.detail.url);
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

  // Menus with overview pages that the header should link to
  const menuOverviewUrls: Record<string, string> = {
    'Items': '/items',
    'Information': '/information',
    'Tools': '/tools'
  };

  function getMenuOverviewUrl(menu: string): string | null {
    return menuOverviewUrls[menu] || null;
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

  .menu-item.menu-top {
    padding: 0;
  }

  .menu-item:hover {
    background-color: var(--hover-color);
  }

  .menu-header-link {
    color: var(--text-color);
    text-decoration: none;
  }

  .menu-header-link:hover {
    color: var(--text-color);
  }

  .menu-header-link-full {
    display: flex;
    align-items: center;
    height: 100%;
    width: 100%;
    padding: 0 12px;
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
    display: flex;
    align-items: center;
    gap: 8px;
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
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    text-align: center;
    margin-right: 6px;
    line-height: 0;
  }

  a {
    text-decoration: none;
  }

  .search-container {
    position: relative;
    margin-left: 20px;
    width: 280px;
  }

  .notification-menu {
    padding: 0 12px;
  }

  .notification-menu:hover {
    background-color: transparent;
  }

  .notification-icon {
    position: relative;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
  }

  .notification-bell {
    width: 26px;
    height: 26px;
    display: block;
  }

  .notification-badge {
    position: absolute;
    top: -2px;
    right: -2px;
    background-color: var(--error-color, #ef4444);
    color: white;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 5px;
    border-radius: 999px;
    line-height: 1;
    border: 1px solid var(--secondary-color);
  }

  .notification-dropdown {
    min-width: 320px;
    max-width: 380px;
    padding: 0;
  }

  .notification-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border-color);
    background-color: var(--hover-color);
    font-size: 12px;
    font-weight: 600;
  }

  .notification-markall {
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    color: var(--text-color);
    cursor: pointer;
  }

  .notification-markall:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .notification-state {
    padding: 14px 12px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .notification-state.error {
    color: var(--error-color);
  }

  .notification-list {
    display: flex;
    flex-direction: column;
    max-height: 320px;
    overflow-y: auto;
  }

  .notification-item {
    text-align: left;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid var(--border-color);
    background: none;
    cursor: pointer;
    color: var(--text-color);
  }

  .notification-item:last-child {
    border-bottom: none;
  }

  .notification-item.unread {
    background-color: rgba(59, 130, 246, 0.12);
  }

  .notification-message {
    font-size: 13px;
    line-height: 1.3;
  }

  .notification-meta {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  .notification-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 12px;
    border-top: 1px solid var(--border-color);
    background-color: var(--hover-color);
    font-size: 11px;
  }

  .notification-page-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
    color: var(--text-color);
    cursor: pointer;
  }

  .notification-page-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .notification-page-info {
    color: var(--text-muted);
  }

  /* Desktop SearchInput component styling */
  :global(.desktop-search) {
    width: 100%;
  }

  :global(.desktop-search .search-input) {
    width: 100%;
    font-size: 14px;
    padding: 6px 10px;
    padding-right: 28px;
    border-radius: 4px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-color);
    color: var(--text-color);
  }

  :global(.desktop-search .search-results-container) {
    min-width: 280px;
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
    position: relative; /* Needed for suggestions-dropdown absolute positioning */
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
    /* Fixed height to prevent layout shift when cancel button appears */
    height: 68px;
    box-sizing: border-box;
  }

  .mobile-search-input-wrapper {
    display: flex;
    gap: 8px;
    align-items: flex-start; /* Prevents input from moving when Cancel button appears */
  }

  .mobile-search-cancel {
    padding: 8px 16px;
    background: none;
    border: none;
    color: var(--accent-color);
    font-size: 14px;
    cursor: pointer;
    white-space: nowrap;
    align-self: center; /* Center vertically with input */
  }

  /* Mobile SearchInput component styling */
  :global(.mobile-search) {
    flex: 1;
  }

  :global(.mobile-search .search-input) {
    width: 100%;
    padding: 12px 16px;
    padding-right: 40px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 16px;
  }

  :global(.mobile-search .search-input:focus) {
    outline: none;
    border-color: var(--accent-color);
  }

  :global(.mobile-search .search-results-container) {
    /* !important needed to override SearchInput's Svelte-scoped styles */
    position: fixed !important;
    top: calc(56px + 68px) !important; /* nav height + search section height */
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    max-height: none !important;
    border-radius: 0 !important;
    border: none !important;
    border-top: 1px solid var(--border-color) !important;
    margin-top: 0 !important;
    box-shadow: none !important;
  }

  :global(.mobile-search .search-category) {
    padding: 12px 16px;
    font-size: 12px;
  }

  :global(.mobile-search .search-result-item) {
    padding: 14px 16px;
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
    flex: 1;
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

  /* Mobile User Section - Collapsible */
  .mobile-user-section {
    border-top: 1px solid var(--border-color);
    padding: 12px 16px;
    background-color: var(--primary-color);
    flex-shrink: 0;
  }

  .mobile-user-header {
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
  }

  .mobile-user-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .mobile-user-info {
    flex: 1;
    min-width: 0;
  }

  .mobile-user-quick-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
    align-items: center;
  }

  /* Uniform size for all quick action buttons */
  .mobile-quick-btn {
    width: 36px;
    height: 36px;
    min-width: 36px;
    min-height: 36px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background-color: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.15s ease;
    text-decoration: none;
    padding: 0;
  }

  .mobile-quick-btn img {
    width: 18px;
    height: 18px;
    object-fit: contain;
  }

  .mobile-quick-btn svg {
    width: 18px;
    height: 18px;
  }

  .mobile-quick-btn:active {
    background-color: var(--hover-color);
  }

  a.mobile-quick-btn {
    text-decoration: none;
  }

  /* Chevron for expand/collapse */
  .mobile-user-chevron {
    font-size: 24px;
    color: var(--text-muted);
    transition: transform 0.2s ease;
    margin-left: 4px;
  }

  .mobile-user-chevron.expanded {
    transform: rotate(90deg);
  }

  .mobile-user-chevron-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--text-muted);
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
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .mobile-user-status {
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* User actions - animated expand/collapse */
  .mobile-user-actions {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 0;
    padding-top: 0;
    border-top: none;
    max-height: 0;
    opacity: 0;
    overflow: hidden;
    transition: max-height 0.25s ease-out, opacity 0.2s ease-out, margin-top 0.25s ease-out, padding-top 0.25s ease-out;
  }

  .mobile-user-actions.expanded {
    max-height: 200px; /* Enough for logout + verify/profile buttons */
    opacity: 1;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
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

  /* Mobile responsive breakpoint - aligned with global 899px */
  @media (max-width: 899px) {
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

    .auth-container .notification-menu {
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
      {#if !(menu === 'Market' && !(user && user.grants?.includes('admin.panel')))}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="menu-item" class:menu-top={!!getMenuOverviewUrl(menu)} on:mouseenter={() => handleDropdownEnter(menu)} on:mouseleave={handleDropdownLeave}>
        {#if getMenuOverviewUrl(menu)}
          <a href={getMenuOverviewUrl(menu)} class="menu-header-link menu-header-link-full" use:loading>{menu}</a>
        {:else}
          {menu}
        {/if}
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
      <SearchInput
        bind:this={desktopSearchRef}
        bind:value={desktopSearchValue}
        placeholder="Search..."
        mode="dropdown"
        containerClass="desktop-search"
        on:select={handleSearchSelect}
      />
    </div>
    {#if user}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="menu-item notification-menu" on:mouseenter={() => handleDropdownEnter('notifications')} on:mouseleave={handleDropdownLeave}>
        <div class="notification-icon" title="Notifications">
          <svg class="notification-bell" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M12 3a6 6 0 0 0-6 6v1.4c0 1-.4 2-1.1 2.7l-1.4 1.4A2.6 2.6 0 0 0 2.8 16H2.5a.5.5 0 0 0 0 1H3v1.5A2.5 2.5 0 0 0 5.5 21h13a2.5 2.5 0 0 0 2.5-2.5V17h.5a.5.5 0 0 0 0-1h-.3a2.6 2.6 0 0 0-.7-1.5l-1.4-1.4A3.8 3.8 0 0 1 18 10.4V9a6 6 0 0 0-6-6Zm0 19a2.75 2.75 0 0 0 2.7-2.2h-5.4A2.75 2.75 0 0 0 12 22Z"
            />
            <circle cx="12" cy="18.2" r="1.4" fill="currentColor" />
          </svg>
          {#if notificationsUnread > 0}
            <span class="notification-badge">{notificationsUnread > 99 ? '99+' : notificationsUnread}</span>
          {/if}
        </div>
        <div class="dropdown-content right notification-dropdown" class:open={dropdownOpen === 'notifications'}>
          <div class="notification-header">
            <span>Notifications</span>
            <button
              class="notification-markall"
              on:click|stopPropagation={markAllNotificationsRead}
              disabled={notificationsUnread === 0 || notificationsLoading}
            >
              Mark all as read
            </button>
          </div>

          {#if notificationsLoading && notifications.length === 0}
            <div class="notification-state">Loading notifications...</div>
          {:else if notificationsError}
            <div class="notification-state error">{notificationsError}</div>
          {:else if notifications.length === 0}
            <div class="notification-state">No notifications yet.</div>
          {:else}
            <div class="notification-list">
              {#each notifications as notification}
                <button
                  class="notification-item"
                  class:unread={!notification.read}
                  on:click={() => markNotificationRead(notification)}
                >
                  <div class="notification-message">{notification.message}</div>
                  <div class="notification-meta">{formatNotificationDate(notification.date)} &bull; {notification.type}</div>
                </button>
              {/each}
            </div>
            <div class="notification-footer">
              <button
                class="notification-page-btn"
                on:click={() => changeNotificationsPage(notificationsPage - 1)}
                disabled={notificationsPage <= 1 || notificationsLoading}
              >
                Prev
              </button>
              <div class="notification-page-info">
                Page {notificationsPage} of {notificationsTotalPages}
              </div>
              <button
                class="notification-page-btn"
                on:click={() => changeNotificationsPage(notificationsPage + 1)}
                disabled={notificationsPage >= notificationsTotalPages || notificationsLoading}
              >
                Next
              </button>
            </div>
          {/if}
        </div>
      </div>
    {/if}
    {#if user == null}
      <a href={loginUrl}>
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
            <a use:loading href={profileUrl}>
              <div class="menu-dropdown-item">
                <span class="menu-item-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                </span>
                Profile
              </div>
            </a>
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
          <a use:loading href={logoutUrl}><div class="menu-dropdown-item"><span class="menu-item-icon">→</span> Logout</div></a>
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
      <SearchInput
        bind:this={mobileSearchRef}
        bind:value={mobileSearchValue}
        bind:showResults={mobileSearchMode}
        placeholder="Search items, mobs, maps..."
        mode="dropdown"
        containerClass="mobile-search"
        showOnFocus={true}
        on:select={handleSearchSelect}
        on:close={exitMobileSearchMode}
      />
      {#if mobileSearchMode}
        <button class="mobile-search-cancel" on:click={exitMobileSearchMode}>Cancel</button>
      {/if}
    </div>
  </div>

  {#if !mobileSearchMode}
    <!-- Navigation Mode -->
    <div class="mobile-menu-content">
      {#each Object.keys(menuItemsWiki) as menu (menu)}
        {#if !(menu === 'Market' && !(user && user.grants?.includes('admin.panel')))}
          <div class="mobile-section">
            <!-- svelte-ignore a11y-click-events-have-key-events -->
            <!-- svelte-ignore a11y-no-static-element-interactions -->
            <!-- On mobile, clicking header just expands/collapses - no navigation -->
            <!-- This prevents menu from closing before user can see options -->
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

    <!-- User Section (at bottom, collapsible) -->
    <div class="mobile-user-section" class:expanded={mobileUserExpanded}>
      {#if user}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div class="mobile-user-header" on:click={() => mobileUserExpanded = !mobileUserExpanded}>
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
          <div class="mobile-user-quick-actions" on:click|stopPropagation>
            <!-- Dark/Light Mode Toggle -->
            <button
              class="mobile-quick-btn"
              on:click={() => setDarkModePreference(!$darkMode)}
              title={$darkMode ? 'Light Mode' : 'Dark Mode'}
            >
              {#if $darkMode}
                <img src="/light.png" alt="Light mode" width="18" height="18" />
              {:else}
                <img src="/dark.png" alt="Dark mode" width="18" height="18" />
              {/if}
            </button>
            {#if effectiveAdmin && !isCurrentlyImpersonating}
              <a
                href="/admin"
                class="mobile-quick-btn"
                on:click={closeMobileMenu}
                title="Admin Dashboard"
                use:loading
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </a>
              <button
                class="mobile-quick-btn"
                on:click={() => { closeMobileMenu(); showImpersonateDialog = true; }}
                title="Impersonate User"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </button>
            {/if}
          </div>
          <button
            class="mobile-user-chevron-btn"
            on:click|stopPropagation={() => (mobileUserExpanded = !mobileUserExpanded)}
            aria-label={mobileUserExpanded ? 'Collapse user menu' : 'Expand user menu'}
          >
            <span class="mobile-user-chevron" class:expanded={mobileUserExpanded}>&#9656;</span>
          </button>
        </div>

        <div class="mobile-user-actions" class:expanded={mobileUserExpanded}>
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
            <a use:loading href={logoutUrl} class="mobile-user-action" on:click={closeMobileMenu}>
              <span class="mobile-action-icon">→</span>
              <span class="mobile-action-text">Logout</span>
            </a>
          {:else}
            <a href={profileUrl} class="mobile-user-action" on:click={closeMobileMenu}>
              <span class="mobile-action-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </span>
              <span class="mobile-action-text">User Profile</span>
            </a>
            <a use:loading href={logoutUrl} class="mobile-user-action" on:click={closeMobileMenu}>
              <span class="mobile-action-icon">→</span>
              <span class="mobile-action-text">Logout</span>
            </a>
          {/if}
        </div>
      {:else}
        <div class="mobile-user-actions-guest">
          <!-- Dark/Light Mode Toggle -->
          <button
            class="mobile-quick-btn"
            on:click={() => setDarkModePreference(!$darkMode)}
            title={$darkMode ? 'Light Mode' : 'Dark Mode'}
          >
            {#if $darkMode}
              <img src="/light.png" alt="Light mode" width="18" height="18" />
            {:else}
              <img src="/dark.png" alt="Dark mode" width="18" height="18" />
            {/if}
          </button>
          <a href={loginUrl} class="mobile-user-action primary" on:click={closeMobileMenu}>
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


