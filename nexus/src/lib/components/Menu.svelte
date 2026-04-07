<script lang="ts">
  // @ts-nocheck

  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';
  import { afterNavigate, goto } from '$app/navigation';
  import { page } from '$app/stores';



  import { getTypeLink, getTypeName, encodeURIComponentSafe, copyToClipboard } from "$lib/util";
  import { addToast } from '$lib/stores/toasts';
  import { PREFERRED_SHORT_ROUTE_BY_PREFIX } from '$lib/short-url-routes.js';
  import { loading } from "../../actions/loading";
  import FancyTable from '$lib/components/FancyTable.svelte';
  import SearchInput from '$lib/components/SearchInput.svelte';

  interface Props {
    user: any;
    realUser?: any; // The actual admin user when impersonating
  }

  let { user, realUser = null }: Props = $props();

  const SHORT_LINK_ORIGIN = 'eunex.us';
  const SHORT_ROUTE_PREFIXES = Object.entries(PREFERRED_SHORT_ROUTE_BY_PREFIX)
    .sort((a, b) => b[0].length - a[0].length);

  let dropdownOpen: string | null = $state(null);
  let dropdownCloseTimeout: ReturnType<typeof setTimeout> | null = null;
  let showImpersonateDialog = $state(false);
  let mobileMenuOpen = $state(false);
  let expandedSections: Set<string> = $state(new Set());
  let mobileSearchMode = $state(false);
  let mobileUserExpanded = $state(false); // Track mobile user panel expanded state

  // Ko-fi support prompt
  let showKofiPrompt = $state(false);
  let kofiTimeInterval = null;

  // Notifications state
  let notifications = $state([]);
  let notificationsLoading = $state(false);
  let notificationsError = $state('');
  let notificationsPage = $state(1);
  const notificationsPageSize = 8;
  let notificationsTotal = $state(0);
  let notificationsUnread = $state(0);
  let notificationsLastLoaded = 0;
  let expandedNotificationId = $state(null);

  const notificationActionMap = {
    Society: { label: 'View Societies', href: '/societies' },
    Rental: { label: 'View Rentals', href: '/rental' },
    Admin: { label: 'Review', href: '/admin/review' },
  };


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

      // Ko-fi support prompt tracking
      // Skip entirely if user already consented to ads (no double-dipping)
      try {
        if (!localStorage.getItem('nexus.kofi.dismissed') && localStorage.getItem('nexus.consent.ads') !== 'granted') {
          const snoozed = localStorage.getItem('nexus.kofi.snoozed');
          const isSnoozed = snoozed && new Date(snoozed).getTime() > Date.now();

          // Increment visit count (once per session via sessionStorage)
          if (!sessionStorage.getItem('nexus.kofi.counted')) {
            const visits = (parseInt(localStorage.getItem('nexus.kofi.visits')) || 0) + 1;
            localStorage.setItem('nexus.kofi.visits', String(visits));
            sessionStorage.setItem('nexus.kofi.counted', '1');
          }

          // Track time (save every 30s)
          kofiTimeInterval = setInterval(() => {
            try {
              const secs = (parseInt(localStorage.getItem('nexus.kofi.seconds')) || 0) + 30;
              localStorage.setItem('nexus.kofi.seconds', String(secs));
            } catch {}
          }, 30000);

          // Check threshold after a delay so user settles in first
          if (!isSnoozed) {
            setTimeout(() => {
              try {
                const visits = parseInt(localStorage.getItem('nexus.kofi.visits')) || 0;
                const secs = parseInt(localStorage.getItem('nexus.kofi.seconds')) || 0;
                if (visits >= 5 || secs >= 1800) {
                  showKofiPrompt = true;
                }
              } catch {}
            }, 5000);
          }
        }
      } catch {}
    }
  });

  onDestroy(() => {
    if (mediaQuery) {
      mediaQuery.removeEventListener('change', handleMediaChange);
    }
    if (dropdownCloseTimeout) clearTimeout(dropdownCloseTimeout);
    if (kofiTimeInterval) clearInterval(kofiTimeInterval);
    if (typeof window !== 'undefined') {
      document.removeEventListener('keydown', handleGlobalKeydown);
    }
  });

  function dismissKofi() {
    showKofiPrompt = false;
    try { localStorage.setItem('nexus.kofi.dismissed', '1'); } catch {}
  }

  function snoozeKofi() {
    showKofiPrompt = false;
    try {
      const snoozeUntil = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
      localStorage.setItem('nexus.kofi.snoozed', snoozeUntil);
    } catch {}
  }

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

  function trimTrailingSlash(pathname: string) {
    if (!pathname || pathname === '/') return '/';
    return pathname.replace(/\/+$/, '');
  }

  function getTailAfterPrefix(pathname: string, prefix: string): string | null {
    if (pathname === prefix) return '';
    if (pathname.startsWith(`${prefix}/`)) return pathname.slice(prefix.length + 1);
    return null;
  }

  function appendQuery(path: string, params: URLSearchParams) {
    const queryString = params.toString();
    return `${path}${queryString ? `?${queryString}` : ''}`;
  }

  function getPseudoShortPath(pathname: string, search: string) {
    const params = new URLSearchParams(search || '');

    // Missions chains view: use mg/mc pseudo routes.
    if (pathname === '/information/missions' && params.get('view') === 'chains') {
      const chain = params.get('chain');
      params.delete('view');
      params.delete('chain');

      if (chain) {
        return appendQuery(`/mc/${encodeURIComponent(chain)}`, params);
      }
      return appendQuery('/mg', params);
    }

    // Exchange direct item filter: use eq pseudo route.
    if (pathname === '/market/exchange' && params.has('item')) {
      const item = params.get('item');
      params.delete('item');
      if (item) {
        return appendQuery(`/eq/${encodeURIComponent(item)}`, params);
      }
      return appendQuery('/eq', params);
    }

    return null;
  }

  function getShortPath(pathname: string, search: string) {
    const normalizedPath = trimTrailingSlash(pathname || '/');
    const query = search || '';
    const pseudoPath = getPseudoShortPath(normalizedPath, query);
    if (pseudoPath) return pseudoPath;

    for (const [prefix, code] of SHORT_ROUTE_PREFIXES) {
      const tail = getTailAfterPrefix(normalizedPath, prefix);
      if (tail == null) continue;
      return tail ? `/${code}/${tail}${query}` : `/${code}${query}`;
    }

    return null;
  }

  function getShortLinkForCurrentPage(currentUrl: URL | null) {
    if (!currentUrl) return null;
    const shortPath = getShortPath(currentUrl.pathname, currentUrl.search);
    if (!shortPath) return null;
    return `${SHORT_LINK_ORIGIN}${shortPath}`;
  }

  async function copyCurrentShortLink() {
    if (!shortLinkUrl) return;

    const copied = await copyToClipboard(shortLinkUrl);
    if (copied) {
      addToast('Short link copied to clipboard.', { type: 'success', duration: 3000 });
      return;
    }

    addToast('Failed to copy short link.', { type: 'error' });
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

  function toggleNotification(notification) {
    if (expandedNotificationId === notification.id) {
      expandedNotificationId = null;
    } else {
      expandedNotificationId = notification.id;
      if (!notification.read) {
        markNotificationRead(notification);
      }
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
    const next = new Set(expandedSections);
    if (next.has(section)) {
      next.delete(section);
    } else {
      next.add(section);
    }
    expandedSections = next;
  }

  let impersonateUserId = $state('');
  let impersonateError = $state('');
  let isImpersonating = $state(false);

  // User search state (for impersonation)
  let userSearchQuery = $state('');
  let userSearchResults = $state([]);
  let isUserSearching = $state(false);
  let userSearchTimeout: ReturnType<typeof setTimeout> | null = null;
  let showUserSuggestions = $state(false);
  let selectedUser: { id: string; global_name: string; eu_name: string | null; matches?: any[] } | null = $state(null);

  // Browse users dialog state
  let showBrowseDialog = $state(false);
  let browseTableKey = $state(0); // Key to force table reload

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

  function handleBrowseRowClick(data) {
    const { row } = data;
    if (row) {
      selectUser(row);
    }
  }


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

  interface MenuItem {
    label: string;
    url: string;
    disabled?: boolean;
    highlighted?: boolean;
    badge?: string;
    children?: { label: string; url: string }[];
  }
  interface MenuItems {
    [key: string]: MenuItem[];
  }
  const menuItemsWiki: MenuItems = {
    'Home': [
      { label: 'News', url: 'news' },
      { label: 'Events', url: 'events' },
      { label: 'Globals', url: 'globals' },
    ],
    'Items': [
      { label: 'Weapons', url: 'weapons' },
      { label: 'Armor Sets', url: 'armorsets' },
      { label: 'Medical Tools', url: 'medicaltools', children: [
        { label: 'Tools', url: 'medicaltools/tools' },
        { label: 'Chips', url: 'medicaltools/chips' },
      ]},
      { label: 'Tools', url: 'tools', children: [
        { label: 'Refiners', url: 'tools/refiners' },
        { label: 'Scanners', url: 'tools/scanners' },
        { label: 'Finders', url: 'tools/finders' },
        { label: 'Excavators', url: 'tools/excavators' },
        { label: 'TP Chips', url: 'tools/teleportationchips' },
        { label: 'Effect Chips', url: 'tools/effectchips' },
        { label: 'Misc. Tools', url: 'tools/misctools' },
      ]},
      { label: 'Attachments', url: 'attachments', children: [
        { label: 'Amplifiers', url: 'attachments/weaponamplifiers' },
        { label: 'Scopes', url: 'attachments/weaponvisionattachments' },
        { label: 'Absorbers', url: 'attachments/absorbers' },
        { label: 'Finder Amps', url: 'attachments/finderamplifiers' },
        { label: 'Platings', url: 'attachments/armorplatings' },
        { label: 'Enhancers', url: 'attachments/enhancers' },
        { label: 'Implants', url: 'attachments/mindforceimplants' },
      ]},
      { label: 'Blueprints', url: 'blueprints' },
      { label: 'Materials', url: 'materials' },
      { label: 'Pets', url: 'pets' },
      { label: 'Consumables', url: 'consumables', children: [
        { label: 'Stimulants', url: 'consumables/stimulants' },
        { label: 'Capsules', url: 'consumables/capsules' },
      ]},
      { label: 'Vehicles', url: 'vehicles' },
      { label: 'Furnishings', url: 'furnishings', children: [
        { label: 'Furniture', url: 'furnishings/furniture' },
        { label: 'Decorations', url: 'furnishings/decorations' },
        { label: 'Storage', url: 'furnishings/storagecontainers' },
        { label: 'Signs', url: 'furnishings/signs' },
      ]},
      { label: 'Clothing', url: 'clothing' },
      { label: 'Strongboxes', url: 'strongboxes' }
    ],
    'Information': [
      { label: 'Guides', url: 'guides', highlighted: true },
      { label: 'Mobs', url: 'mobs', children: [
        { label: 'Calypso', url: 'mobs?planet=Calypso' },
        { label: 'Arkadia', url: 'mobs?planet=Arkadia' },
        { label: 'Cyrene', url: 'mobs?planet=Cyrene' },
        { label: 'Rocktropia', url: 'mobs?planet=ROCKtropia' },
        { label: 'Next Island', url: 'mobs?planet=Next Island' },
        { label: 'Toulan', url: 'mobs?planet=Toulan' },
        { label: 'Monria', url: 'mobs?planet=Monria' },
      ]},
      { label: 'Missions', url: 'missions', children: [
        { label: 'Calypso', url: 'missions?planet=Calypso' },
        { label: 'Arkadia', url: 'missions?planet=Arkadia' },
        { label: 'Cyrene', url: 'missions?planet=Cyrene' },
        { label: 'Rocktropia', url: 'missions?planet=ROCKtropia' },
        { label: 'Next Island', url: 'missions?planet=Next Island' },
        { label: 'Toulan', url: 'missions?planet=Toulan' },
        { label: 'Monria', url: 'missions?planet=Monria' },
      ]},
      { label: 'Professions', url: 'professions' },
      { label: 'Skills', url: 'skills' },
      { label: 'Vendors', url: 'vendors' },
      { label: 'Locations', url: 'locations' },
      { label: 'Enumerations', url: 'enumerations' },
    ],
    'Maps': [
      { label: 'Calypso', url: 'calypso', children: [
        { label: 'Setesh', url: 'setesh' },
        { label: 'ARIS', url: 'aris' },
        { label: 'Crystal Palace', url: 'crystalpalace' },
        { label: 'Asteroid F.O.M.A', url: 'asteroidfoma' },
      ]},
      { label: 'Arkadia', url: 'arkadia', children: [
        { label: 'Arkadia Underground', url: 'arkadiaunderground' },
        { label: 'Arkadia Moon', url: 'arkadiamoon' },
      ]},
      { label: 'Cyrene', url: 'cyrene' },
      { label: 'Rocktropia', url: 'rocktropia', children: [
        { label: 'HELL', url: 'hell' },
        { label: 'Hunt The THING', url: 'huntthething' },
        { label: 'Secret Island', url: 'secretisland' },
      ]},
      { label: 'Next Island', url: 'nextisland', children: [
        { label: 'Ancient Greece', url: 'ancientgreece' },
      ]},
      { label: 'Toulan', url: 'toulan' },
      { label: 'Monria', url: 'monria', children: [
        { label: 'DSEC9', url: 'dsec9' },
      ]},
      { label: 'Space', url: 'space' },
    ],
    'Tools': [
      { label: 'Client', url: 'client', badge: 'Beta' },
      { label: 'Loadout Manager', url: 'loadouts' },
      { label: 'Construction Calculator', url: 'construction' },
      { label: 'Gear Advisor', url: 'gear-advisor' },
      { label: 'Skills Calculator', url: 'skills', disabled: true },
      { label: 'API', url: 'api' },
    ],
    'Market': [
      { label: 'Exchange', url: 'exchange', highlighted: true },
      { label: 'Auction', url: 'auction' },
      { label: 'Rental', url: 'rental' },
      { label: 'Services', url: 'services' },
      { label: 'Shops', url: 'shops' },
      { label: 'PCF Trade', url: 'forum' },
    ],
    'External': [
      { label: 'Entropia Museum', url: 'entropiamuseum' },
      { label: 'NI Helper', url: 'nihelper' },
      { label: 'Cyrenedream', url: 'cyrenedream' },
      { label: 'The Delta Project', url: 'deltaproject' },
      { label: 'RipCraze', url: 'ripcraze' },
      { label: 'Entropia Life', url: 'entropialife' },
      { label: 'Planet Calypso Forum', url: 'pcforum' },
    ],
  };

  // Desktop search state (now managed by SearchInput component)
  let desktopSearchValue = $state('');
  let desktopSearchRef = $state();

  // Mobile search state (now managed by SearchInput component)
  let mobileSearchValue = $state('');
  let mobileSearchRef = $state();

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

  function handleSearchSelect({ url }) {
    // Navigate to the selected result
    goto(url);
    closeMobileMenu();
  }

  function handleSearchNavigate({ query }) {
    // Navigate to dedicated search page
    if (query && query.trim().length >= 2) {
      goto(`/search?q=${encodeURIComponent(query.trim())}`);
      desktopSearchRef?.clear?.();
      mobileSearchRef?.clear?.();
      closeMobileMenu();
    }
  }


  const customUrls: Record<string, string> = {
    'api': `${import.meta.env.VITE_API_URL}/docs/`,
    'entropiamuseum': 'https://www.entropiamuseum.com/',
    'nihelper': 'https://www.nihelper.com',
    'cyrenedream': 'https://www.cyrenedream.org',
    'deltaproject': 'https://www.thedeltaproject.net',
    'ripcraze': 'https://ripcraze.com/',
    'entropialife': 'http://www.entropialife.com',
    'pcforum': 'https://www.planetcalypsoforum.com',
    'news': '/',
    'events': '/events',
    'globals': '/globals',
  };

  function getMenuItemUrl(menu: string, item: { label: string; url: string }) {
    if (customUrls[item.url]) return customUrls[item.url];
    const qIdx = item.url.indexOf('?');
    if (qIdx >= 0) {
      return `/${menu.toLowerCase()}/${item.url.substring(0, qIdx).toLowerCase()}${item.url.substring(qIdx)}`;
    }
    return `/${menu.toLowerCase()}/${item.url.toLowerCase()}`;
  }

  function isExternalLink(item: { label: string; url: string }) {
    return ['api', 'entropiamuseum', 'nihelper', 'cyrenedream', 'deltaproject', 'ripcraze', 'entropialife', 'pcforum'].includes(item.url);
  }

  // Top-level menus to visually highlight
  const highlightedMenus = new Set(['Market']);

  // Menus with overview pages that the header should link to
  const menuOverviewUrls: Record<string, string> = {
    'Home': '/',
    'Items': '/items',
    'Information': '/information',
    'Tools': '/tools',
    'Market': '/market',
    'Maps': '/maps'
  };

  function getMenuOverviewUrl(menu: string): string | null {
    return menuOverviewUrls[menu] || null;
  }
  // Login/Logout URLs with redirect back to current page
  let loginUrl = $derived(`/discord/login?redirect=${encodeURIComponent($page.url.pathname + $page.url.search)}`);
  let logoutUrl = $derived(`/discord/logout?redirect=${encodeURIComponent($page.url.pathname + $page.url.search)}`);
  let profileUrl = $derived(user ? `/users/${encodeURIComponentSafe(String(user.eu_name || user.id))}` : '/discord/login');
  let notificationsTotalPages = $derived(Math.max(1, Math.ceil(notificationsTotal / notificationsPageSize)));
  let shortLinkUrl = $derived(getShortLinkForCurrentPage($page.url));
  let canCopyShortLink = $derived(!!shortLinkUrl);
  let isCurrentlyImpersonating = $derived(!!realUser);
  let effectiveAdmin = $derived(realUser?.administrator || user?.administrator);
  let isUnverified = $derived(user && !user.verified);
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

  .dev-mode-notice {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 2px;
    color: var(--warning-color, #f59e0b);
    border: 2px solid var(--warning-color, #f59e0b);
    padding: 2px 12px;
    border-radius: 4px;
    pointer-events: none;
    user-select: none;
    text-transform: uppercase;
    z-index: 1;
  }

  .menu-container, .auth-container {
    display: flex;
    position: relative;
    align-items: center;
    height: 100%;
    gap: 12px;
  }


  .menu-container {
    flex-shrink: 0;
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
    flex-shrink: 0;
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

  .menu-item.highlighted .menu-header-link,
  .menu-item.highlighted {
    color: var(--accent-color);
    font-weight: 600;
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

  .has-submenu {
    position: relative;
  }

  .has-submenu > a > .menu-dropdown-item {
    justify-content: space-between;
  }

  .submenu-arrow {
    font-size: 13px;
    color: var(--text-muted);
    margin-left: auto;
  }

  .submenu {
    display: none;
    position: absolute;
    left: 100%;
    top: -4px;
    min-width: 180px;
    background-color: var(--secondary-color);
    box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.3);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 4px 0;
    z-index: 101;
  }

  .has-submenu:hover > .submenu {
    display: block;
  }

  .menu-dropdown-item.highlighted {
    color: var(--accent-color);
    font-weight: 600;
  }

  .menu-dropdown-item.disabled {
    opacity: 0.4;
    cursor: default;
    pointer-events: none;
  }

  .menu-badge {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    background-color: var(--accent-color);
    color: #000;
    padding: 1px 5px;
    border-radius: 3px;
    margin-left: 6px;
    vertical-align: middle;
  }

  .coming-soon {
    font-size: 10px;
    font-style: italic;
    opacity: 0.7;
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
    flex: 0 1 280px;
    min-width: 80px;
    height: 32px;
  }

  .notification-menu {
    padding: 0;
    flex-shrink: 0;
  }

  .menu-item.user {
    padding: 0;
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
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .notification-item.expanded .notification-message {
    white-space: normal;
    overflow: visible;
    text-overflow: unset;
  }

  .notification-meta {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  .notification-action {
    display: inline-block;
    margin-top: 6px;
    font-size: 12px;
    color: var(--accent);
    text-decoration: none;
    padding: 3px 10px;
    border: 1px solid var(--accent);
    border-radius: 4px;
    transition: background 0.15s;
  }
  .notification-action:hover {
    background: var(--accent);
    color: var(--text-light);
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
    height: 32px;
    font-size: 14px;
    padding: 6px 10px;
    padding-right: 28px;
    border-radius: 4px;
    border: 1px solid var(--border-color);
    background-color: var(--bg-color);
    color: var(--text-color);
    box-sizing: border-box;
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

  .short-link-action {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    border: none;
    background: none;
    color: var(--text-color);
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.15s ease;
    flex-shrink: 0;
  }

  .short-link-action:hover {
    background-color: var(--hover-color);
  }

  .short-link-action svg {
    width: 26px;
    height: 26px;
  }

  .bounty-button {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    color: var(--text-muted);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
    flex-shrink: 0;
    text-decoration: none;
  }
  .bounty-button:hover {
    background-color: var(--hover-color);
    color: #fbbf24;
  }
  .bounty-button svg {
    width: 26px;
    height: 26px;
  }

  .kofi-button {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    background: none;
    color: var(--text-muted);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
    flex-shrink: 0;
    text-decoration: none;
  }
  .kofi-button:hover {
    background-color: var(--hover-color);
    color: #ff5e5b;
  }
  .kofi-button svg {
    width: 26px;
    height: 26px;
  }

  .kofi-wrapper {
    position: relative;
    flex-shrink: 0;
  }

  .kofi-bubble {
    position: absolute;
    top: calc(100% + 10px);
    right: -8px;
    width: 240px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
    z-index: 1000;
    animation: kofi-fade-in 0.3s ease;
  }

  .kofi-bubble-arrow {
    position: absolute;
    top: -6px;
    right: 16px;
    width: 12px;
    height: 12px;
    background: var(--secondary-color);
    border-left: 1px solid var(--border-color);
    border-top: 1px solid var(--border-color);
    transform: rotate(45deg);
  }

  .kofi-bubble-text {
    margin: 0 0 10px;
    font-size: 13px;
    color: var(--text-color);
    line-height: 1.4;
  }

  .kofi-bubble-actions {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .kofi-bubble-btn {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    text-align: center;
    text-decoration: none;
    border: none;
    transition: opacity 0.15s;
  }

  .kofi-bubble-btn.support {
    background: #ff5e5b;
    color: white;
  }
  .kofi-bubble-btn.support:hover { opacity: 0.9; }

  .kofi-bubble-btn.later {
    background: var(--hover-color);
    color: var(--text-color);
  }
  .kofi-bubble-btn.later:hover { background: var(--border-color); }

  .kofi-bubble-btn.dismiss {
    background: none;
    color: var(--text-muted);
    font-size: 11px;
  }
  .kofi-bubble-btn.dismiss:hover { color: var(--text-color); }

  @keyframes kofi-fade-in {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
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
    flex-shrink: 0;
    white-space: nowrap;
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

  /* Hide dev mode notice on mobile (logo occupies center) */
  @media (max-width: 899px) {
    .dev-mode-notice {
      display: none;
    }
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

  .mobile-section-title.highlighted {
    color: var(--accent-color);
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

  .mobile-menu-item.highlighted {
    color: var(--accent-color);
    font-weight: 600;
  }

  .mobile-menu-item.disabled {
    opacity: 0.4;
    cursor: default;
  }

  .mobile-sub-item {
    padding-left: 32px;
    font-size: 13px;
    color: var(--text-muted);
  }

  /* Mobile Ko-fi Link */
  .mobile-kofi-link {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 16px;
    color: var(--text-color);
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    border-top: 1px solid var(--border-color);
    background-color: var(--hover-color);
  }
  .mobile-kofi-link:active {
    background-color: var(--primary-color);
  }
  .mobile-kofi-icon {
    width: 18px;
    height: 18px;
    color: #ff5e5b;
    flex-shrink: 0;
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

    .auth-container .short-link-action {
      display: none;
    }

    .auth-container .discord-button,
    .auth-container a:has(:global(.discord-button)) {
      display: none;
    }

    .kofi-wrapper,
    .bounty-button {
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
  {#if import.meta.env.DEV}
    <span class="dev-mode-notice">DEV MODE</span>
  {/if}
  <div class="menu-container">
    <a href="/" class="logo-link"><img class="website-icon" src="/favicon.png" alt="Entropia Nexus" title="Entropia Nexus" width="48px" height="48px" /></a>
    {#each Object.keys(menuItemsWiki) as menu (menu)}
      <div class="menu-item" role="none" class:menu-top={!!getMenuOverviewUrl(menu)} class:highlighted={highlightedMenus.has(menu)} onmouseenter={() => handleDropdownEnter(menu)} onmouseleave={handleDropdownLeave}>
        {#if getMenuOverviewUrl(menu)}
          <a href={getMenuOverviewUrl(menu)} class="menu-header-link menu-header-link-full" use:loading>{menu}</a>
        {:else}
          {menu}
        {/if}
        <div class="dropdown-content" class:open={dropdownOpen === menu}>
              {#each menuItemsWiki[menu] as item (item)}
                {#if item.disabled}
                  <div class="menu-dropdown-item disabled">{item.label} <span class="coming-soon">coming soon</span></div>
                {:else if isExternalLink(item)}
                  <a href={getMenuItemUrl(menu, item)} target="_blank"><div class="menu-dropdown-item" class:highlighted={item.highlighted}>{item.label}</div></a>
                {:else if item.children?.length}
                  <div class="has-submenu">
                    <a use:loading href={getMenuItemUrl(menu, item)}><div class="menu-dropdown-item" class:highlighted={item.highlighted}>{item.label}<span class="submenu-arrow">&#9656;</span></div></a>
                    <div class="submenu">
                      {#each item.children as child}
                        <a use:loading href={getMenuItemUrl(menu, child)}><div class="menu-dropdown-item">{child.label}</div></a>
                      {/each}
                    </div>
                  </div>
                {:else}
                  <a use:loading href={getMenuItemUrl(menu, item)}><div class="menu-dropdown-item" class:highlighted={item.highlighted}>{item.label}{#if item.badge}<span class="menu-badge">{item.badge}</span>{/if}</div></a>
                {/if}
              {/each}
          </div>
      </div>
    {/each}
  </div>

  <div class="auth-container">
    <a href="/bounties" class="bounty-button" title="Contributor Bounties">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/>
        <circle cx="12" cy="12" r="7.5" fill="none" stroke="currentColor" stroke-width="0.75" opacity="0.4"/>
        <text x="12" y="13" text-anchor="middle" dominant-baseline="middle" fill="currentColor" font-size="6.5" font-weight="700" font-family="Arial,sans-serif">PED</text>
      </svg>
    </a>
    <div class="kofi-wrapper">
      <a href="https://ko-fi.com/C0C21JO3B1" target="_blank" rel="noopener noreferrer" class="kofi-button" title="Support me on Ko-fi">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path fill="currentColor" d="M23.881 8.948c-.773-4.085-4.859-4.593-4.859-4.593H.723c-.604 0-.679.798-.679.798s-.082 7.324-.022 11.822c.164 2.424 2.586 2.672 2.586 2.672s8.267-.023 11.966-.049c2.438-.426 2.683-2.566 2.658-3.734 4.352.24 7.422-2.831 6.649-6.916zm-11.062 3.511c-1.246 1.453-4.011 3.976-4.011 3.976s-.121.119-.31.023c-.076-.057-.108-.09-.108-.09-.443-.441-3.368-3.049-4.034-3.954-.709-.965-1.041-2.7-.091-3.71.951-1.01 3.005-1.086 4.363.407 0 0 1.565-1.782 3.468-.963 1.904.82 1.832 3.011.723 4.311zm6.173.478c-.928.116-1.682.028-1.682.028V7.284h1.77s1.971.551 1.971 2.638c0 1.913-.985 2.667-2.059 3.015z"/>
        </svg>
      </a>
      {#if showKofiPrompt}
        <div class="kofi-bubble">
          <div class="kofi-bubble-arrow"></div>
          <p class="kofi-bubble-text">Enjoying Entropia Nexus? Consider supporting me!</p>
          <div class="kofi-bubble-actions">
            <a href="https://ko-fi.com/C0C21JO3B1" target="_blank" rel="noopener noreferrer" class="kofi-bubble-btn support" onclick={dismissKofi}>Support Me</a>
            <button class="kofi-bubble-btn later" onclick={snoozeKofi}>Maybe Later</button>
            <button class="kofi-bubble-btn dismiss" onclick={dismissKofi}>No, Thanks</button>
          </div>
        </div>
      {/if}
    </div>
    <div class="search-container">
      <SearchInput
        bind:this={desktopSearchRef}
        bind:value={desktopSearchValue}
        placeholder="Search..."
        mode="dropdown"
        containerClass="desktop-search"
        onselect={handleSearchSelect}
        onsearch={handleSearchNavigate}
      />
    </div>
    {#if canCopyShortLink}
      <button
        class="short-link-action"
        onclick={copyCurrentShortLink}
        title="Copy short link"
        aria-label="Copy short link"
        data-short-url={shortLinkUrl}
      >
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M13.8 10.2a3.5 3.5 0 0 1 0 5l-2.6 2.6a3.5 3.5 0 1 1-5-5l2.1-2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          <path d="M10.2 13.8a3.5 3.5 0 0 1 0-5l2.6-2.6a3.5 3.5 0 0 1 5 5l-2.1 2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
    {/if}
    {#if user}
      <div class="menu-item notification-menu" role="none" onmouseenter={() => handleDropdownEnter('notifications')} onmouseleave={handleDropdownLeave}>
        <div class="notification-icon" title="Notifications">
          <svg class="notification-bell" viewBox="0 0 24 24" aria-hidden="true">
            <path fill="currentColor" d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2z"/>
            <path fill="currentColor" d="M18 16v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.93 6 11v5l-2 2v1h16v-1l-2-2z"/>
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
              onclick={(e) => { e.stopPropagation(); markAllNotificationsRead(); }}
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
                  class:expanded={expandedNotificationId === notification.id}
                  onclick={() => toggleNotification(notification)}
                >
                  <div class="notification-message">{notification.message}</div>
                  <div class="notification-meta">{formatNotificationDate(notification.date)} &bull; {notification.type}</div>
                  {#if expandedNotificationId === notification.id && notificationActionMap[notification.type]}
                    <a
                      class="notification-action"
                      href={notificationActionMap[notification.type].href}
                      onclick={(e) => e.stopPropagation()}
                    >{notificationActionMap[notification.type].label}</a>
                  {/if}
                </button>
              {/each}
            </div>
            <div class="notification-footer">
              <button
                class="notification-page-btn"
                onclick={() => changeNotificationsPage(notificationsPage - 1)}
                disabled={notificationsPage <= 1 || notificationsLoading}
              >
                Prev
              </button>
              <div class="notification-page-info">
                Page {notificationsPage} of {notificationsTotalPages}
              </div>
              <button
                class="notification-page-btn"
                onclick={() => changeNotificationsPage(notificationsPage + 1)}
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
      <div class="menu-item user" role="none" onmouseenter={() => handleDropdownEnter('user')} onmouseleave={handleDropdownLeave}>
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
            <button class="menu-dropdown-item stop-impersonate-btn" onclick={stopImpersonation}>
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
            <a use:loading href="/account/inventory">
              <div class="menu-dropdown-item">
                <span class="menu-item-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                  </svg>
                </span>
                Inventory
              </div>
            </a>
            <a use:loading href="/account/settings">
              <div class="menu-dropdown-item">
                <span class="menu-item-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                </span>
                Settings
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
            <a use:loading href="/admin">
              <div class="menu-dropdown-item">
                <span class="menu-item-icon">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                </span>
                Admin Dashboard
              </div>
            </a>
            <button class="menu-dropdown-item" onclick={() => showImpersonateDialog = true}>
              <span class="menu-item-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </span>
              Impersonate User
            </button>
          {/if}
          <a use:loading href={logoutUrl}>
            <div class="menu-dropdown-item">
              <span class="menu-item-icon">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
              </span>
              Logout
            </div>
          </a>
        </div>
      </div>
    {/if}
    <button class="burger-button" class:open={mobileMenuOpen} onclick={toggleMobileMenu} aria-label="Toggle menu">
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
        onselect={handleSearchSelect}
        onsearch={handleSearchNavigate}
        onclose={exitMobileSearchMode}
      />
      {#if mobileSearchMode}
        <button class="mobile-search-cancel" onclick={exitMobileSearchMode}>Cancel</button>
      {/if}
    </div>
  </div>

  {#if !mobileSearchMode}
    <!-- Navigation Mode -->
    <div class="mobile-menu-content">
      {#each Object.keys(menuItemsWiki) as menu (menu)}
          <div class="mobile-section">
            <!-- On mobile, clicking header just expands/collapses - no navigation -->
            <!-- This prevents menu from closing before user can see options -->
            <div class="mobile-section-header" role="button" tabindex="0" onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), e.currentTarget.click())} onclick={() => toggleSection(menu)}>
              <span class="mobile-section-title" class:highlighted={highlightedMenus.has(menu)}>{menu}</span>
              <span class="mobile-section-chevron" class:expanded={expandedSections.has(menu)}>&#9660;</span>
            </div>
            <div class="mobile-section-items" class:expanded={expandedSections.has(menu)}>
              {#each menuItemsWiki[menu] as item (item)}
                {#if item.disabled}
                  <span class="mobile-menu-item disabled">{item.label} <span class="coming-soon">coming soon</span></span>
                {:else if isExternalLink(item)}
                  <a href={getMenuItemUrl(menu, item)} target="_blank" class="mobile-menu-item" class:highlighted={item.highlighted} onclick={closeMobileMenu}>{item.label}</a>
                {:else}
                  <a use:loading href={getMenuItemUrl(menu, item)} class="mobile-menu-item" class:highlighted={item.highlighted} onclick={closeMobileMenu}>{item.label}{#if item.badge}<span class="menu-badge">{item.badge}</span>{/if}</a>
                {/if}
                {#if item.children?.length}
                  {#each item.children as child}
                    <a use:loading href={getMenuItemUrl(menu, child)} class="mobile-menu-item mobile-sub-item" onclick={closeMobileMenu}>{child.label}</a>
                  {/each}
                {/if}
              {/each}
            </div>
          </div>
      {/each}
    </div>

    <!-- Ko-fi support link -->
    <a href="https://ko-fi.com/C0C21JO3B1" target="_blank" rel="noopener noreferrer" class="mobile-kofi-link" onclick={closeMobileMenu}>
      <svg viewBox="0 0 24 24" aria-hidden="true" class="mobile-kofi-icon">
        <path fill="currentColor" d="M23.881 8.948c-.773-4.085-4.859-4.593-4.859-4.593H.723c-.604 0-.679.798-.679.798s-.082 7.324-.022 11.822c.164 2.424 2.586 2.672 2.586 2.672s8.267-.023 11.966-.049c2.438-.426 2.683-2.566 2.658-3.734 4.352.24 7.422-2.831 6.649-6.916zm-11.062 3.511c-1.246 1.453-4.011 3.976-4.011 3.976s-.121.119-.31.023c-.076-.057-.108-.09-.108-.09-.443-.441-3.368-3.049-4.034-3.954-.709-.965-1.041-2.7-.091-3.71.951-1.01 3.005-1.086 4.363.407 0 0 1.565-1.782 3.468-.963 1.904.82 1.832 3.011.723 4.311zm6.173.478c-.928.116-1.682.028-1.682.028V7.284h1.77s1.971.551 1.971 2.638c0 1.913-.985 2.667-2.059 3.015z"/>
      </svg>
      <span>Support me on Ko-fi</span>
    </a>

    <!-- User Section (at bottom, collapsible) -->
    <div class="mobile-user-section" class:expanded={mobileUserExpanded}>
      {#if user}
        <div class="mobile-user-header" role="button" tabindex="0" onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), e.currentTarget.click())} onclick={() => mobileUserExpanded = !mobileUserExpanded}>
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
          <div class="mobile-user-quick-actions" role="presentation" onclick={(e) => e.stopPropagation()}>
            {#if canCopyShortLink}
              <button
                class="mobile-quick-btn short-link-mobile-btn"
                onclick={copyCurrentShortLink}
                title="Copy short link"
                aria-label="Copy short link"
                data-short-url={shortLinkUrl}
              >
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M13.8 10.2a3.5 3.5 0 0 1 0 5l-2.6 2.6a3.5 3.5 0 1 1-5-5l2.1-2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                  <path d="M10.2 13.8a3.5 3.5 0 0 1 0-5l2.6-2.6a3.5 3.5 0 0 1 5 5l-2.1 2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </button>
            {/if}
            {#if effectiveAdmin && !isCurrentlyImpersonating}
              <a
                href="/admin"
                class="mobile-quick-btn"
                onclick={closeMobileMenu}
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
                onclick={() => { closeMobileMenu(); showImpersonateDialog = true; }}
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
            onclick={(e) => { e.stopPropagation(); mobileUserExpanded = !mobileUserExpanded; }}
            aria-label={mobileUserExpanded ? 'Collapse user menu' : 'Expand user menu'}
          >
            <span class="mobile-user-chevron" class:expanded={mobileUserExpanded}>&#9656;</span>
          </button>
        </div>

        <div class="mobile-user-actions" class:expanded={mobileUserExpanded}>
          {#if isCurrentlyImpersonating}
            <button class="mobile-user-action danger" onclick={stopImpersonation}>
              <span class="mobile-action-icon">✕</span>
              <span class="mobile-action-text">Stop Impersonating</span>
            </button>
          {:else if isUnverified}
            <a href="/account/setup" class="mobile-user-action success" onclick={closeMobileMenu}>
              <span class="mobile-action-icon">✓</span>
              <span class="mobile-action-text">Verify Account</span>
            </a>
            <a use:loading href={logoutUrl} class="mobile-user-action" onclick={closeMobileMenu}>
              <span class="mobile-action-icon">→</span>
              <span class="mobile-action-text">Logout</span>
            </a>
          {:else}
            <a href={profileUrl} class="mobile-user-action" onclick={closeMobileMenu}>
              <span class="mobile-action-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
              </span>
              <span class="mobile-action-text">User Profile</span>
            </a>
            <a href="/account/inventory" class="mobile-user-action" onclick={closeMobileMenu}>
              <span class="mobile-action-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
                </svg>
              </span>
              <span class="mobile-action-text">Inventory</span>
            </a>
            <a href="/account/settings" class="mobile-user-action" onclick={closeMobileMenu}>
              <span class="mobile-action-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </span>
              <span class="mobile-action-text">Settings</span>
            </a>
            <a use:loading href={logoutUrl} class="mobile-user-action" onclick={closeMobileMenu}>
              <span class="mobile-action-icon">→</span>
              <span class="mobile-action-text">Logout</span>
            </a>
          {/if}
        </div>
      {:else}
        <div class="mobile-user-actions-guest">
          {#if canCopyShortLink}
            <button
              class="mobile-quick-btn short-link-mobile-btn"
              onclick={copyCurrentShortLink}
              title="Copy short link"
              aria-label="Copy short link"
              data-short-url={shortLinkUrl}
            >
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M13.8 10.2a3.5 3.5 0 0 1 0 5l-2.6 2.6a3.5 3.5 0 1 1-5-5l2.1-2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                <path d="M10.2 13.8a3.5 3.5 0 0 1 0-5l2.6-2.6a3.5 3.5 0 0 1 5 5l-2.1 2.1" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          {/if}
          <a href={loginUrl} class="mobile-user-action primary" onclick={closeMobileMenu}>
            <img src="/discord.svg" alt="" class="mobile-discord-icon" />
            <span class="mobile-action-text">Login with Discord</span>
          </a>
        </div>
      {/if}
    </div>
  {/if}
</div>

{#if showImpersonateDialog}
  <div class="dialog-overlay" role="presentation" onclick={resetImpersonateDialog}>
    <div class="dialog dialog-wide" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
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
              <button type="button" class="chip-remove" onclick={clearSelectedUser}>&#10005;</button>
            </div>
          {:else}
            <input
              id="impersonate-search"
              type="text"
              bind:value={userSearchQuery}
              oninput={handleUserSearchInput}
              onfocus={() => { if (userSearchResults.length > 0) showUserSuggestions = true; }}
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
              <div class="suggestion-item" role="button" tabindex="0" onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), e.currentTarget.click())} onclick={() => selectUser(result)}>
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
        <button type="button" class="btn-browse" onclick={openBrowseDialog}>
          Browse All Users
        </button>
      </div>

      <div class="dialog-buttons">
        <button class="btn-secondary" onclick={resetImpersonateDialog} disabled={isImpersonating}>
          Cancel
        </button>
        <button class="btn-primary" onclick={startImpersonation} disabled={isImpersonating || !impersonateUserId.trim()}>
          {isImpersonating ? 'Impersonating...' : 'Impersonate'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showBrowseDialog}
  <div class="dialog-overlay" role="presentation" onclick={() => showBrowseDialog = false}>
    <div class="dialog dialog-large" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
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
            onrowClick={handleBrowseRowClick}
          />
        {/key}
      </div>

      <div class="dialog-buttons">
        <button class="btn-secondary" onclick={() => showBrowseDialog = false}>
          Close
        </button>
      </div>
    </div>
  </div>
{/if}


