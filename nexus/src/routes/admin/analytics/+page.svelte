<script>
  // @ts-nocheck
  import { onMount, onDestroy } from 'svelte';
  import { Chart, registerables } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  Chart.register(...registerables);

  // --- State ---
  let activeTab = $state('overview');
  let period = $state('7d');
  let excludeBots = $state(true);
  let excludeApi = $state(false);
  let isLoading = $state(true);
  let error = $state(null);

  // Overview
  let overview = $state(null);
  let timeseries = $state(null);

  // Routes
  let routeData = $state(null);
  let routeCategory = $state('');
  let routePage = $state(1);
  let expandedRoutes = $state({});  // pattern → { paths, loading }

  // API tab
  let apiRouteData = $state(null);
  let oauthData = $state(null);

  // Geo
  let geoData = $state(null);

  // Referrers
  let referrerData = $state(null);

  // Bots
  let botPatterns = $state(null);
  let newBotPattern = $state('');
  let newBotDescription = $state('');
  let botTestInput = $state('');
  let botTestResult = $state(null);
  let botError = $state('');

  // Live
  let liveVisits = $state(null);
  let liveExcludeBots = $state(true);
  let liveExcludeApi = $state(true);
  let liveCategory = $state('');
  let liveInterval = null;

  // Chart
  let chartCanvas = $state(null);
  let chartInstance = null;

  const PERIODS = [
    { value: 'today', label: 'Today' },
    { value: '7d', label: '7 Days' },
    { value: '30d', label: '30 Days' },
    { value: '90d', label: '90 Days' },
    { value: '1y', label: '1 Year' },
    { value: 'all', label: 'All Time' }
  ];

  const COUNTRY_NAMES = {
    US: 'United States', GB: 'United Kingdom', DE: 'Germany', FR: 'France', CA: 'Canada',
    AU: 'Australia', NL: 'Netherlands', SE: 'Sweden', BR: 'Brazil', JP: 'Japan',
    IN: 'India', CN: 'China', KR: 'South Korea', RU: 'Russia', IT: 'Italy',
    ES: 'Spain', PL: 'Poland', BE: 'Belgium', AT: 'Austria', CH: 'Switzerland',
    DK: 'Denmark', NO: 'Norway', FI: 'Finland', PT: 'Portugal', CZ: 'Czech Republic',
    RO: 'Romania', HU: 'Hungary', GR: 'Greece', IE: 'Ireland', NZ: 'New Zealand',
    MX: 'Mexico', AR: 'Argentina', CL: 'Chile', CO: 'Colombia', ZA: 'South Africa',
    PH: 'Philippines', TH: 'Thailand', SG: 'Singapore', MY: 'Malaysia', ID: 'Indonesia',
    TW: 'Taiwan', HK: 'Hong Kong', UA: 'Ukraine', IL: 'Israel', TR: 'Turkey',
    EG: 'Egypt', NG: 'Nigeria', KE: 'Kenya', PK: 'Pakistan', BD: 'Bangladesh',
    VN: 'Vietnam', PE: 'Peru', SK: 'Slovakia', BG: 'Bulgaria', HR: 'Croatia',
    RS: 'Serbia', LT: 'Lithuania', LV: 'Latvia', EE: 'Estonia', SI: 'Slovenia'
  };

  function countryName(code) {
    return COUNTRY_NAMES[code] || code;
  }

  /**
   * Parse a user-agent string into a short readable label.
   * e.g. "Chrome 120 (Win)", "Safari 17 (iPhone)", "Firefox 121 (Linux)"
   */
  function parseUserAgent(ua) {
    if (!ua) return '-';

    // Mobile detection
    const isMobile = /Mobile|Android|iPhone|iPad|iPod/i.test(ua);

    // OS detection
    let os = '';
    if (/iPhone|iPad|iPod/.test(ua)) os = /iPad/.test(ua) ? 'iPad' : 'iPhone';
    else if (/Android/.test(ua)) os = 'Android';
    else if (/Windows/.test(ua)) os = 'Win';
    else if (/Mac OS X|Macintosh/.test(ua)) os = 'Mac';
    else if (/Linux/.test(ua)) os = 'Linux';
    else if (/CrOS/.test(ua)) os = 'ChromeOS';

    // Browser detection (order matters — check specific before generic)
    let browser = '';
    let m;
    if ((m = ua.match(/Edg(?:e|A|iOS)?\/(\d+)/))) browser = `Edge ${m[1]}`;
    else if ((m = ua.match(/OPR\/(\d+)/))) browser = `Opera ${m[1]}`;
    else if ((m = ua.match(/Vivaldi\/(\d+\.\d+)/))) browser = `Vivaldi ${m[1]}`;
    else if ((m = ua.match(/SamsungBrowser\/(\d+)/))) browser = `Samsung ${m[1]}`;
    else if ((m = ua.match(/Firefox\/(\d+)/))) browser = `Firefox ${m[1]}`;
    else if ((m = ua.match(/CriOS\/(\d+)/))) browser = `Chrome ${m[1]}`;
    else if ((m = ua.match(/FxiOS\/(\d+)/))) browser = `Firefox ${m[1]}`;
    else if ((m = ua.match(/Chrome\/(\d+)/)) && !/Edg/.test(ua)) browser = `Chrome ${m[1]}`;
    else if ((m = ua.match(/Version\/(\d+).*Safari/))) browser = `Safari ${m[1]}`;
    else if (/Safari\//.test(ua) && !/Chrome/.test(ua)) browser = 'Safari';
    else browser = 'Other';

    if (!browser && !os) return ua.substring(0, 30);
    const label = browser || 'Unknown';
    const suffix = os ? ` (${os})` : '';
    return label + suffix;
  }

  function formatNumber(n) {
    return parseInt(n || 0).toLocaleString();
  }

  function formatDate(d) {
    if (!d) return '-';
    return new Date(d).toLocaleString();
  }

  function formatDateShort(d) {
    if (!d) return '-';
    const dt = new Date(d);
    return dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  // --- Route detail (slug expansion) ---
  // A route has expandable slug detail if its last segment is parameterized
  // e.g. /items/[type]/[slug] → yes, /items/[type] → no, /admin/users/[id] → yes
  function hasSlugParam(pattern) {
    if (!pattern) return false;
    const segments = pattern.split('/').filter(Boolean);
    if (segments.length < 2) return false;
    const last = segments[segments.length - 1];
    return last.startsWith('[') && last.endsWith(']');
  }

  async function toggleRouteDetail(pattern) {
    if (expandedRoutes[pattern]) {
      // Collapse
      const next = { ...expandedRoutes };
      delete next[pattern];
      expandedRoutes = next;
      return;
    }
    // Expand — fetch detail
    expandedRoutes = { ...expandedRoutes, [pattern]: { paths: null, loading: true } };
    try {
      const data = await fetchJson(`/api/admin/analytics/routes/detail?pattern=${encodeURIComponent(pattern)}&period=${period}${filterParams()}`);
      expandedRoutes = { ...expandedRoutes, [pattern]: { paths: data.paths, loading: false } };
    } catch {
      expandedRoutes = { ...expandedRoutes, [pattern]: { paths: [], loading: false } };
    }
  }

  // --- Data fetching ---
  /** Build query string with common filter params */
  function filterParams() {
    let p = '';
    if (excludeBots) p += '&excludeBots=true';
    if (excludeApi) p += '&excludeApi=true';
    return p;
  }

  async function fetchJson(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function loadOverview() {
    isLoading = true;
    error = null;
    try {
      const [ov, ts] = await Promise.all([
        fetchJson(`/api/admin/analytics/overview?period=${period}${filterParams()}`),
        fetchJson(`/api/admin/analytics/timeseries?period=${period}${filterParams()}`)
      ]);
      overview = ov;
      timeseries = ts;
      updateChart();
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function loadRoutes() {
    isLoading = true;
    error = null;
    try {
      const categoryParam = routeCategory ? `&category=${encodeURIComponent(routeCategory)}` : '';
      routeData = await fetchJson(`/api/admin/analytics/routes?period=${period}&page=${routePage}&limit=50${categoryParam}${filterParams()}`);
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function loadApi() {
    isLoading = true;
    error = null;
    try {
      const [routes, oauth] = await Promise.all([
        fetchJson(`/api/admin/analytics/routes?period=${period}&category=api&limit=50`),
        fetchJson(`/api/admin/analytics/oauth?period=${period}`)
      ]);
      apiRouteData = routes;
      oauthData = oauth;
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function loadGeo() {
    isLoading = true;
    error = null;
    try {
      geoData = await fetchJson(`/api/admin/analytics/geo?period=${period}${filterParams()}`);
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function loadReferrers() {
    isLoading = true;
    error = null;
    try {
      referrerData = await fetchJson(`/api/admin/analytics/referrers?period=${period}${filterParams()}`);
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function loadBots() {
    isLoading = true;
    error = null;
    try {
      const data = await fetchJson('/api/admin/analytics/bots');
      botPatterns = data.patterns;
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function loadLive() {
    try {
      const excludeParam = liveExcludeBots ? '&excludeBots=true' : '';
      const excludeApiParam = liveExcludeApi ? '&excludeApi=true' : '';
      const catParam = liveCategory ? `&category=${encodeURIComponent(liveCategory)}` : '';
      const data = await fetchJson(`/api/admin/analytics/recent?limit=50${excludeParam}${excludeApiParam}${catParam}`);
      liveVisits = data.visits;
    } catch (e) {
      if (!liveVisits) error = e.message;
    }
  }

  function loadTab() {
    switch (activeTab) {
      case 'overview': loadOverview(); break;
      case 'routes': loadRoutes(); break;
      case 'api': loadApi(); break;
      case 'geo': loadGeo(); break;
      case 'referrers': loadReferrers(); break;
      case 'bots': loadBots(); break;
      case 'live': loadLive(); break;
    }
  }

  // --- Chart ---
  function updateChart() {
    if (!chartCanvas || !timeseries?.points?.length) return;

    const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent-color').trim() || '#3b82f6';
    const mutedColor = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#999';
    const borderColor = getComputedStyle(document.documentElement).getPropertyValue('--border-color').trim() || '#333';
    const errorColor = getComputedStyle(document.documentElement).getPropertyValue('--error-color').trim() || '#ef4444';

    if (chartInstance) chartInstance.destroy();

    chartInstance = new Chart(chartCanvas, {
      type: 'line',
      data: {
        labels: timeseries.points.map(p => p.date),
        datasets: [
          {
            label: 'Requests',
            data: timeseries.points.map(p => p.requests),
            borderColor: accentColor,
            backgroundColor: accentColor + '20',
            fill: true,
            tension: 0.3,
            pointRadius: timeseries.points.length > 30 ? 0 : 3
          },
          {
            label: 'Unique IPs',
            data: timeseries.points.map(p => p.unique_ips),
            borderColor: '#10b981',
            borderDash: [5, 5],
            fill: false,
            tension: 0.3,
            pointRadius: timeseries.points.length > 30 ? 0 : 3
          },
          {
            label: 'Bots',
            data: timeseries.points.map(p => p.bots),
            borderColor: errorColor,
            borderDash: [2, 2],
            fill: false,
            tension: 0.3,
            pointRadius: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        scales: {
          x: {
            type: 'time',
            time: {
              tooltipFormat: 'MMM d, yyyy',
              unit: timeseries.granularity === 'daily' ? 'day' : timeseries.granularity === 'weekly' ? 'week' : 'month'
            },
            grid: { color: borderColor + '40' },
            ticks: { color: mutedColor }
          },
          y: {
            beginAtZero: true,
            grid: { color: borderColor + '40' },
            ticks: { color: mutedColor }
          }
        },
        plugins: {
          legend: { labels: { color: mutedColor } }
        }
      }
    });
  }

  // --- Bot actions ---
  async function addBotPattern() {
    if (!newBotPattern.trim()) return;
    botError = '';
    try {
      const res = await fetch('/api/admin/analytics/bots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pattern: newBotPattern.trim(), description: newBotDescription.trim() || null })
      });
      if (!res.ok) {
        const data = await res.json();
        botError = data.error || 'Failed to add pattern';
        return;
      }
      newBotPattern = '';
      newBotDescription = '';
      await loadBots();
    } catch (e) {
      botError = 'Network error';
    }
  }

  async function toggleBotPattern(id, enabled) {
    try {
      await fetch(`/api/admin/analytics/bots/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      await loadBots();
    } catch (e) {
      console.error('Failed to toggle pattern:', e);
    }
  }

  async function deleteBotPattern(id) {
    if (!confirm('Delete this bot pattern?')) return;
    try {
      await fetch(`/api/admin/analytics/bots/${id}`, { method: 'DELETE' });
      await loadBots();
    } catch (e) {
      console.error('Failed to delete pattern:', e);
    }
  }

  function testBotPattern() {
    if (!botTestInput.trim() || !botPatterns) {
      botTestResult = null;
      return;
    }
    const enabledPatterns = botPatterns.filter(p => p.enabled).map(p => p.pattern);
    if (enabledPatterns.length === 0) {
      botTestResult = { match: false, pattern: null };
      return;
    }
    for (const pattern of enabledPatterns) {
      try {
        const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        if (new RegExp(escaped, 'i').test(botTestInput)) {
          botTestResult = { match: true, pattern };
          return;
        }
      } catch { /* skip invalid */ }
    }
    botTestResult = { match: false, pattern: null };
  }

  // --- Rebuild ---
  let rebuilding = $state(false);
  let reevaluating = $state(false);
  let reevalResult = $state(null);

  async function triggerRebuild() {
    rebuilding = true;
    try {
      const res = await fetch('/api/admin/analytics/rebuild', { method: 'POST' });
      if (res.ok) loadTab();
    } catch (e) {
      console.error('Rebuild failed:', e);
    } finally {
      rebuilding = false;
    }
  }

  async function triggerBotReevaluation() {
    reevaluating = true;
    reevalResult = null;
    try {
      const res = await fetch('/api/admin/analytics/rebuild?bots=true', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        reevalResult = `${data.botsUpdated} rows updated`;
        loadTab();
      }
    } catch (e) {
      reevalResult = 'Failed';
    } finally {
      reevaluating = false;
    }
  }

  // --- Period change ---
  function changePeriod(newPeriod) {
    period = newPeriod;
    routePage = 1;
    expandedRoutes = {};
    loadTab();
  }

  function changeTab(tab) {
    // Always clear any existing live interval first
    if (liveInterval) { clearInterval(liveInterval); liveInterval = null; }
    activeTab = tab;
    if (tab === 'live') {
      loadLive();
      // Use setTimeout chain instead of setInterval to prevent pileup
      // when network is slow (waits for previous fetch to complete)
      function scheduleLiveRefresh() {
        liveInterval = setTimeout(async () => {
          if (activeTab !== 'live') return; // tab switched away
          await loadLive();
          if (activeTab === 'live') scheduleLiveRefresh();
        }, 5000);
      }
      scheduleLiveRefresh();
    } else {
      loadTab();
    }
  }

  onMount(() => {
    loadOverview();
  });

  onDestroy(() => {
    if (chartInstance) chartInstance.destroy();
    if (liveInterval) clearTimeout(liveInterval);
  });

  // Reactively update chart when canvas ref changes
  $effect(() => {
    if (chartCanvas && timeseries) updateChart();
  });
</script>

<svelte:head>
  <title>Analytics | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .analytics { max-width: 1400px; }

  .breadcrumb {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 16px; font-size: 14px;
  }
  .breadcrumb a { color: var(--accent-color); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }
  .breadcrumb span { color: var(--text-muted); }

  h1 { margin: 0 0 8px 0; font-size: 28px; color: var(--text-color); }
  .subtitle { color: var(--text-muted); margin: 0 0 20px 0; font-size: 14px; }

  /* Period picker */
  .period-picker {
    display: flex; gap: 4px; margin-bottom: 20px; flex-wrap: wrap;
  }
  .period-btn {
    padding: 6px 14px; border: 1px solid var(--border-color); border-radius: 6px;
    background: none; color: var(--text-muted); cursor: pointer; font-size: 13px;
    transition: all 0.15s ease;
  }
  .period-btn:hover { color: var(--text-color); border-color: var(--text-muted); }
  .period-btn.active {
    background-color: var(--accent-color); color: white;
    border-color: var(--accent-color);
  }
  .filter-toggle {
    display: flex; align-items: center; gap: 4px; font-size: 13px;
    color: var(--text-muted); cursor: pointer; margin-left: 8px; white-space: nowrap;
  }
  .filter-toggle input { cursor: pointer; }
  .rebuild-btn {
    margin-left: auto; padding: 6px 14px; border: 1px solid var(--border-color);
    border-radius: 6px; background: none; color: var(--text-muted);
    cursor: pointer; font-size: 13px; transition: all 0.15s ease;
  }
  .rebuild-btn:hover { color: var(--text-color); border-color: var(--text-muted); }
  .rebuild-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Tabs */
  .tabs {
    display: flex; gap: 0; border-bottom: 1px solid var(--border-color);
    margin-bottom: 16px; overflow-x: auto;
  }
  .tab {
    padding: 10px 20px; background: none; border: none;
    border-bottom: 2px solid transparent; color: var(--text-muted);
    cursor: pointer; font-size: 14px; white-space: nowrap;
    transition: color 0.15s ease;
  }
  .tab:hover { color: var(--text-color); }
  .tab.active { color: var(--accent-color); border-bottom-color: var(--accent-color); }

  /* Stat cards */
  .stats-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }
  .stat-card {
    background-color: var(--secondary-color); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 16px;
  }
  .stat-card h3 {
    margin: 0 0 6px 0; font-size: 12px; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .stat-value { font-size: 28px; font-weight: bold; margin: 0; color: var(--text-color); }
  .stat-accent { color: var(--accent-color); }
  .stat-success { color: var(--success-color); }
  .stat-warning { color: var(--warning-color); }
  .stat-error { color: var(--error-color); }

  /* Chart */
  .chart-container {
    background-color: var(--secondary-color); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 16px; margin-bottom: 24px; height: 300px;
    position: relative;
  }

  /* Two-column layout */
  .two-col {
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;
  }

  /* Section */
  .section {
    background-color: var(--secondary-color); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 16px;
  }
  .section h3 {
    margin: 0 0 12px 0; font-size: 16px; color: var(--text-color);
  }

  /* Tables */
  .data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .data-table th {
    text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border-color);
    color: var(--text-muted); font-weight: 600; font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.3px;
  }
  .data-table td {
    padding: 8px 10px; border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
  }
  .data-table tr:hover td { background-color: var(--hover-color); }
  .data-table .num { text-align: right; font-variant-numeric: tabular-nums; }
  .data-table .muted { color: var(--text-muted); }
  .data-table .route-pattern { font-family: monospace; font-size: 12px; word-break: break-all; }
  .expand-icon { margin-left: 6px; font-size: 10px; color: var(--text-muted); }
  .expandable:hover td { background-color: var(--hover-color); }
  .detail-row td { background-color: var(--primary-color); }
  .detail-path { padding-left: 20px; color: var(--text-muted); }

  /* Bot management */
  .bot-form {
    display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;
  }
  .bot-form input {
    padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px;
    background-color: var(--primary-color); color: var(--text-color); font-size: 13px;
  }
  .bot-form input:focus { outline: none; border-color: var(--accent-color); }
  .bot-form button {
    padding: 8px 16px; border: none; border-radius: 6px;
    background-color: var(--accent-color); color: white; cursor: pointer;
    font-size: 13px; transition: background-color 0.15s ease;
  }
  .bot-form button:hover { background-color: var(--accent-color-hover); }

  .bot-test {
    margin-top: 16px; padding: 12px;
    background-color: var(--primary-color); border-radius: 6px;
  }
  .bot-test input { width: 100%; margin-bottom: 8px; }
  .bot-test-result { font-size: 13px; }
  .bot-test-match { color: var(--error-color); font-weight: bold; }
  .bot-test-no-match { color: var(--success-color); }

  .toggle-btn {
    padding: 4px 10px; border: 1px solid var(--border-color); border-radius: 4px;
    background: none; color: var(--text-muted); cursor: pointer; font-size: 12px;
  }
  .toggle-btn.enabled { background-color: var(--success-color); color: white; border-color: var(--success-color); }
  .delete-btn {
    padding: 4px 10px; border: 1px solid var(--error-color); border-radius: 4px;
    background: none; color: var(--error-color); cursor: pointer; font-size: 12px;
  }
  .delete-btn:hover { background-color: var(--error-color); color: white; }

  .error-msg { color: var(--error-color); font-size: 13px; margin-bottom: 8px; }

  /* Live view */
  .live-controls {
    display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap;
  }
  .live-controls label { font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 4px; }
  .live-controls select {
    padding: 6px 10px; border: 1px solid var(--border-color); border-radius: 6px;
    background-color: var(--primary-color); color: var(--text-color); font-size: 13px;
  }
  .status-badge {
    display: inline-block; padding: 2px 6px; border-radius: 4px;
    font-size: 11px; font-weight: bold;
  }
  .status-2xx { background-color: rgba(16, 185, 129, 0.2); color: var(--success-color); }
  .status-3xx { background-color: rgba(59, 130, 246, 0.2); color: var(--accent-color); }
  .status-4xx { background-color: rgba(245, 158, 11, 0.2); color: var(--warning-color); }
  .status-5xx { background-color: rgba(239, 68, 68, 0.2); color: var(--error-color); }
  .bot-badge { background-color: rgba(239, 68, 68, 0.15); color: var(--error-color); padding: 2px 6px; border-radius: 4px; font-size: 11px; }
  .ua-label { font-size: 12px; white-space: nowrap; }

  /* Live table: fixed layout with ellipsis */
  .live-table { table-layout: fixed; }
  .live-table .col-time { width: 170px; }
  .live-table .col-ip { width: 130px; }
  .live-table .col-country { width: 36px; }
  .live-table .col-browser { width: 130px; }
  .live-table .col-route { width: auto; }
  .live-table .col-status { width: 52px; }
  .live-table .col-bot { width: 40px; }
  .live-table .col-ms { width: 50px; }
  .cell-ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  /* Category badges */
  .category-badge {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600;
    background-color: var(--hover-color); color: var(--text-muted);
  }

  /* Pagination */
  .pagination {
    display: flex; gap: 8px; align-items: center; justify-content: center; margin-top: 12px;
  }
  .pagination button {
    padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 4px;
    background: none; color: var(--text-color); cursor: pointer; font-size: 13px;
  }
  .pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
  .pagination span { font-size: 13px; color: var(--text-muted); }

  .loading, .error-display {
    text-align: center; padding: 40px; color: var(--text-muted);
  }
  .error-display { color: var(--error-color); }

  .empty-state { text-align: center; padding: 24px; color: var(--text-muted); font-size: 14px; }

  /* Responsive */
  @media (max-width: 768px) {
    h1 { font-size: 22px; }
    .two-col { grid-template-columns: 1fr; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .stat-value { font-size: 22px; }
    .tab { padding: 8px 12px; font-size: 13px; }
    .data-table { font-size: 12px; }
    .data-table th, .data-table td { padding: 6px 6px; }
    .chart-container { height: 220px; }
    .bot-form { flex-direction: column; }
    .bot-form input { width: 100%; }
  }

  @media (max-width: 480px) {
    .stats-grid { grid-template-columns: 1fr; }
  }
</style>

<div class="analytics">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Analytics</span>
  </div>

  <h1>Route Analytics</h1>
  <p class="subtitle">Monitor traffic, API usage, geographic distribution, and bot activity</p>

  <!-- Period picker (shown for all tabs except bots and live) -->
  {#if activeTab !== 'bots' && activeTab !== 'live'}
    <div class="period-picker">
      {#each PERIODS as p}
        <button class="period-btn" class:active={period === p.value} onclick={() => changePeriod(p.value)}>
          {p.label}
        </button>
      {/each}
      {#if activeTab !== 'api'}
        <label class="filter-toggle">
          <input type="checkbox" bind:checked={excludeBots} onchange={() => loadTab()} />
          Exclude bots
        </label>
        <label class="filter-toggle">
          <input type="checkbox" bind:checked={excludeApi} onchange={() => loadTab()} />
          Exclude API
        </label>
      {/if}
      <button class="rebuild-btn" onclick={triggerRebuild} disabled={rebuilding}>
        {rebuilding ? 'Rebuilding...' : 'Rebuild rollups'}
      </button>
    </div>
  {/if}

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab" class:active={activeTab === 'overview'} onclick={() => changeTab('overview')}>Overview</button>
    <button class="tab" class:active={activeTab === 'routes'} onclick={() => changeTab('routes')}>Routes</button>
    <button class="tab" class:active={activeTab === 'api'} onclick={() => changeTab('api')}>API</button>
    <button class="tab" class:active={activeTab === 'geo'} onclick={() => changeTab('geo')}>Geography</button>
    <button class="tab" class:active={activeTab === 'referrers'} onclick={() => changeTab('referrers')}>Referrers</button>
    <button class="tab" class:active={activeTab === 'bots'} onclick={() => changeTab('bots')}>Bots</button>
    <button class="tab" class:active={activeTab === 'live'} onclick={() => changeTab('live')}>Live</button>
  </div>

  {#if isLoading && !overview && !routeData && !geoData && !botPatterns && !liveVisits}
    <div class="loading">Loading analytics...</div>
  {:else if error && !overview && !routeData}
    <div class="error-display">Error: {error}</div>
  {:else}

    <!-- ===== OVERVIEW TAB ===== -->
    {#if activeTab === 'overview' && overview}
      <div class="stats-grid">
        <div class="stat-card">
          <h3>Total Requests</h3>
          <p class="stat-value stat-accent">{formatNumber(overview.totalRequests)}</p>
        </div>
        <div class="stat-card">
          <h3>Unique Visitors</h3>
          <p class="stat-value stat-success">{formatNumber(overview.uniqueVisitors)}</p>
        </div>
        <div class="stat-card">
          <h3>Bot Traffic</h3>
          <p class="stat-value stat-warning">{overview.botPercent}%</p>
        </div>
        <div class="stat-card">
          <h3>Rate Limited</h3>
          <p class="stat-value stat-error">{formatNumber(overview.rateLimited)}</p>
        </div>
        <div class="stat-card">
          <h3>Errors</h3>
          <p class="stat-value" style="color: var(--text-muted)">{formatNumber(overview.errors)}</p>
        </div>
        <div class="stat-card">
          <h3>Avg Response</h3>
          <p class="stat-value" style="color: var(--text-muted)">{overview.avgResponseMs || 0}ms</p>
        </div>
      </div>

      <div class="chart-container">
        <canvas bind:this={chartCanvas}></canvas>
      </div>

      <div class="two-col">
        <div class="section">
          <h3>Top Routes</h3>
          {#if overview.topRoutes?.length > 0}
            <table class="data-table">
              <thead>
                <tr>
                  <th>Route</th>
                  <th class="num">Requests</th>
                  <th class="num">Unique IPs</th>
                </tr>
              </thead>
              <tbody>
                {#each overview.topRoutes as route}
                  <tr>
                    <td><span class="route-pattern">{route.route_pattern}</span></td>
                    <td class="num">{formatNumber(route.requests)}</td>
                    <td class="num">{formatNumber(route.unique_ips)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <div class="empty-state">No data for this period</div>
          {/if}
        </div>

        <div>
          <div class="section" style="margin-bottom: 16px">
            <h3>Top Countries</h3>
            {#if overview.topCountries?.length > 0}
              <table class="data-table">
                <thead><tr><th>Country</th><th class="num">Requests</th></tr></thead>
                <tbody>
                  {#each overview.topCountries as c}
                    <tr>
                      <td>{c.country_code} - {countryName(c.country_code)}</td>
                      <td class="num">{formatNumber(c.requests)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            {:else}
              <div class="empty-state">No geographic data</div>
            {/if}
          </div>

          <div class="section">
            <h3>Top Referrers</h3>
            {#if overview.topReferrers?.length > 0}
              <table class="data-table">
                <thead><tr><th>Domain</th><th class="num">Visits</th></tr></thead>
                <tbody>
                  {#each overview.topReferrers as r}
                    <tr>
                      <td>{r.referrer_domain}</td>
                      <td class="num">{formatNumber(r.requests)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            {:else}
              <div class="empty-state">No external referrers</div>
            {/if}
          </div>
        </div>
      </div>

    <!-- ===== ROUTES TAB ===== -->
    {:else if activeTab === 'routes' && routeData}
      <!-- Category filter -->
      {#if routeData.categories?.length > 0}
        <div style="margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap;">
          <button class="period-btn" class:active={!routeCategory} onclick={() => { routeCategory = ''; routePage = 1; loadRoutes(); }}>
            All
          </button>
          {#each routeData.categories as cat}
            <button class="period-btn" class:active={routeCategory === cat.route_category}
              onclick={() => { routeCategory = cat.route_category; routePage = 1; loadRoutes(); }}>
              {cat.route_category} ({formatNumber(cat.requests)})
            </button>
          {/each}
        </div>
      {/if}

      <div class="section">
        <table class="data-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Route Pattern</th>
              <th class="num">Requests</th>
              <th class="num">Unique IPs</th>
              <th class="num">Bots</th>
              <th class="num">Errors</th>
              <th class="num">Avg ms</th>
            </tr>
          </thead>
          <tbody>
            {#each routeData.routes as route}
              <tr class:expandable={hasSlugParam(route.route_pattern)}
                  onclick={() => hasSlugParam(route.route_pattern) && toggleRouteDetail(route.route_pattern)}
                  style={hasSlugParam(route.route_pattern) ? 'cursor: pointer' : ''}>
                <td><span class="category-badge">{route.route_category}</span></td>
                <td>
                  <span class="route-pattern">{route.route_pattern}</span>
                  {#if hasSlugParam(route.route_pattern)}
                    <span class="expand-icon">{expandedRoutes[route.route_pattern] ? '\u25BC' : '\u25B6'}</span>
                  {/if}
                </td>
                <td class="num">{formatNumber(route.requests)}</td>
                <td class="num">{formatNumber(route.unique_ips)}</td>
                <td class="num muted">{formatNumber(route.bots)}</td>
                <td class="num muted">{formatNumber(route.errors)}</td>
                <td class="num muted">{route.avg_response_ms || '-'}</td>
              </tr>
              {#if expandedRoutes[route.route_pattern]}
                {#if expandedRoutes[route.route_pattern].loading}
                  <tr class="detail-row"><td colspan="7" class="muted" style="padding-left: 40px">Loading...</td></tr>
                {:else if expandedRoutes[route.route_pattern].paths?.length > 0}
                  {#each expandedRoutes[route.route_pattern].paths as path}
                    <tr class="detail-row">
                      <td></td>
                      <td><span class="route-pattern detail-path">{path.route_path}</span></td>
                      <td class="num">{formatNumber(path.requests)}</td>
                      <td class="num">{formatNumber(path.unique_ips)}</td>
                      <td colspan="3"></td>
                    </tr>
                  {/each}
                {:else}
                  <tr class="detail-row"><td colspan="7" class="muted" style="padding-left: 40px">No data in retention window</td></tr>
                {/if}
              {/if}
            {/each}
          </tbody>
        </table>

        {#if routeData.totalPages > 1}
          <div class="pagination">
            <button disabled={routePage <= 1} onclick={() => { routePage--; loadRoutes(); }}>Previous</button>
            <span>Page {routePage} of {routeData.totalPages}</span>
            <button disabled={routePage >= routeData.totalPages} onclick={() => { routePage++; loadRoutes(); }}>Next</button>
          </div>
        {/if}
      </div>

    <!-- ===== API TAB ===== -->
    {:else if activeTab === 'api' && apiRouteData}
      <div class="two-col">
        <div class="section">
          <h3>API Endpoints</h3>
          {#if apiRouteData.routes?.length > 0}
            <table class="data-table">
              <thead>
                <tr>
                  <th>Route</th>
                  <th class="num">Requests</th>
                  <th class="num">Rate Limited</th>
                  <th class="num">Errors</th>
                </tr>
              </thead>
              <tbody>
                {#each apiRouteData.routes as route}
                  <tr>
                    <td><span class="route-pattern">{route.route_pattern}</span></td>
                    <td class="num">{formatNumber(route.requests)}</td>
                    <td class="num" style="color: var(--warning-color)">{formatNumber(route.rate_limited)}</td>
                    <td class="num muted">{formatNumber(route.errors)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <div class="empty-state">No API data for this period</div>
          {/if}
        </div>

        <div class="section">
          <h3>OAuth Clients</h3>
          {#if oauthData?.clients?.length > 0}
            <table class="data-table">
              <thead>
                <tr>
                  <th>Client</th>
                  <th class="num">Requests</th>
                  <th class="num">Rate Limited</th>
                  <th class="num">Routes</th>
                </tr>
              </thead>
              <tbody>
                {#each oauthData.clients as client}
                  <tr>
                    <td>{client.client_name || client.oauth_client_id}</td>
                    <td class="num">{formatNumber(client.requests)}</td>
                    <td class="num" style="color: var(--warning-color)">{formatNumber(client.rate_limited)}</td>
                    <td class="num muted">{client.routes_used}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          {:else}
            <div class="empty-state">No OAuth usage for this period</div>
          {/if}
        </div>
      </div>

      {#if oauthData?.details?.length > 0}
        <div class="section">
          <h3>OAuth Endpoint Details</h3>
          <table class="data-table">
            <thead>
              <tr>
                <th>Client</th>
                <th>Route</th>
                <th class="num">Requests</th>
                <th class="num">Rate Limited</th>
              </tr>
            </thead>
            <tbody>
              {#each oauthData.details as d}
                <tr>
                  <td>{d.client_name || d.oauth_client_id}</td>
                  <td><span class="route-pattern">{d.route_pattern}</span></td>
                  <td class="num">{formatNumber(d.requests)}</td>
                  <td class="num" style="color: var(--warning-color)">{formatNumber(d.rate_limited)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

    <!-- ===== GEO TAB ===== -->
    {:else if activeTab === 'geo' && geoData}
      <div class="section">
        <h3>Visitors by Country</h3>
        {#if geoData.countries?.length > 0}
          <table class="data-table">
            <thead>
              <tr>
                <th>Country</th>
                <th class="num">Requests</th>
                <th class="num">Unique IPs</th>
              </tr>
            </thead>
            <tbody>
              {#each geoData.countries as c}
                <tr>
                  <td>{c.country_code} - {countryName(c.country_code)}</td>
                  <td class="num">{formatNumber(c.requests)}</td>
                  <td class="num">{formatNumber(c.unique_ips)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No geographic data for this period</div>
        {/if}
      </div>

    <!-- ===== REFERRERS TAB ===== -->
    {:else if activeTab === 'referrers' && referrerData}
      <div class="section">
        <h3>External Referrers</h3>
        {#if referrerData.referrers?.length > 0}
          <table class="data-table">
            <thead>
              <tr>
                <th>Domain</th>
                <th class="num">Visits</th>
              </tr>
            </thead>
            <tbody>
              {#each referrerData.referrers as r}
                <tr>
                  <td>{r.referrer_domain}</td>
                  <td class="num">{formatNumber(r.requests)}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No external referrer data for this period</div>
        {/if}
      </div>

    <!-- ===== BOTS TAB ===== -->
    {:else if activeTab === 'bots' && botPatterns}
      <div class="section">
        <h3>Bot / Crawler Patterns</h3>
        <p class="subtitle" style="margin-bottom: 16px">
          User-agent strings matching these patterns are flagged as bot traffic.
        </p>

        <div class="bot-form">
          <input type="text" bind:value={newBotPattern} placeholder="Pattern (e.g. MyBot)" style="flex: 1; min-width: 200px" />
          <input type="text" bind:value={newBotDescription} placeholder="Description (optional)" style="flex: 1; min-width: 200px" />
          <button onclick={addBotPattern}>Add Pattern</button>
        </div>
        {#if botError}
          <div class="error-msg">{botError}</div>
        {/if}

        <table class="data-table">
          <thead>
            <tr>
              <th>Pattern</th>
              <th>Description</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each botPatterns as bp}
              <tr>
                <td><code>{bp.pattern}</code></td>
                <td class="muted">{bp.description || '-'}</td>
                <td>
                  <button class="toggle-btn" class:enabled={bp.enabled}
                    onclick={() => toggleBotPattern(bp.id, !bp.enabled)}>
                    {bp.enabled ? 'Enabled' : 'Disabled'}
                  </button>
                </td>
                <td>
                  <button class="delete-btn" onclick={() => deleteBotPattern(bp.id)}>Delete</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>

        <div class="bot-test">
          <h3 style="margin: 0 0 8px 0; font-size: 14px;">Test User-Agent</h3>
          <input type="text" bind:value={botTestInput} oninput={testBotPattern}
            placeholder="Paste a user-agent string to test..." style="padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; background-color: var(--secondary-color); color: var(--text-color); font-size: 13px;" />
          {#if botTestResult !== null}
            <div class="bot-test-result">
              {#if botTestResult.match}
                <span class="bot-test-match">MATCH</span> — matched pattern: <code>{botTestResult.pattern}</code>
              {:else}
                <span class="bot-test-no-match">NO MATCH</span> — this user-agent would not be flagged as a bot
              {/if}
            </div>
          {/if}
        </div>

        <div style="margin-top: 16px; display: flex; align-items: center; gap: 12px">
          <button class="rebuild-btn" onclick={triggerBotReevaluation} disabled={reevaluating}>
            {reevaluating ? 'Re-evaluating...' : 'Re-evaluate existing entries'}
          </button>
          <span class="muted" style="font-size: 12px">
            {#if reevalResult}
              {reevalResult}
            {:else}
              Applies current patterns + version thresholds to all stored visits
            {/if}
          </span>
        </div>
      </div>

    <!-- ===== LIVE TAB ===== -->
    {:else if activeTab === 'live'}
      <div class="live-controls">
        <label>
          <input type="checkbox" bind:checked={liveExcludeBots} onchange={loadLive} />
          Exclude bots
        </label>
        <label>
          <input type="checkbox" bind:checked={liveExcludeApi} onchange={loadLive} />
          Exclude API calls
        </label>
        <select bind:value={liveCategory} onchange={loadLive}>
          <option value="">All categories</option>
          <option value="home">home</option>
          <option value="api">api</option>
          <option value="items">items</option>
          <option value="information">information</option>
          <option value="market">market</option>
          <option value="tools">tools</option>
          <option value="globals">globals</option>
          <option value="admin">admin</option>
          <option value="maps">maps</option>
          <option value="events">events</option>
          <option value="users">users</option>
        </select>
        <span class="muted" style="font-size: 12px">Auto-refreshes every 5s</span>
      </div>

      <div class="section" style="overflow-x: auto">
        {#if liveVisits?.length > 0}
          <table class="data-table live-table">
            <thead>
              <tr>
                <th class="col-time">Time</th>
                <th class="col-ip">IP</th>
                <th class="col-country">CC</th>
                <th class="col-browser">Browser</th>
                <th class="col-route">Route</th>
                <th class="col-status">Status</th>
                <th class="col-bot">Bot</th>
                <th class="col-ms num">ms</th>
              </tr>
            </thead>
            <tbody>
              {#each liveVisits as v}
                <tr>
                  <td class="muted cell-ellipsis col-time" style="font-size: 12px">{formatDate(v.visited_at)}</td>
                  <td class="cell-ellipsis col-ip" title={v.ip_address} style="font-family: monospace; font-size: 12px">{v.ip_address}</td>
                  <td class="col-country">{v.country_code || '-'}</td>
                  <td class="col-browser" title={v.user_agent || ''}><span class="ua-label">{parseUserAgent(v.user_agent)}</span></td>
                  <td class="cell-ellipsis col-route" title={v.route_path}><span class="route-pattern">{v.method !== 'GET' ? v.method + ' ' : ''}{v.route_path}</span></td>
                  <td>
                    <span class="status-badge"
                      class:status-2xx={v.status_code >= 200 && v.status_code < 300}
                      class:status-3xx={v.status_code >= 300 && v.status_code < 400}
                      class:status-4xx={v.status_code >= 400 && v.status_code < 500}
                      class:status-5xx={v.status_code >= 500}>
                      {v.status_code}
                    </span>
                  </td>
                  <td>{#if v.is_bot}<span class="bot-badge">BOT</span>{/if}</td>
                  <td class="num muted">{v.response_time_ms ?? '-'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {:else}
          <div class="empty-state">No recent visits{liveExcludeBots || liveExcludeApi ? ` (excluding${liveExcludeBots ? ' bots' : ''}${liveExcludeBots && liveExcludeApi ? ' &' : ''}${liveExcludeApi ? ' API' : ''})` : ''}</div>
        {/if}
      </div>
    {/if}
  {/if}
</div>
