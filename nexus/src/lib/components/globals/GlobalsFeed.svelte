<!--
  @component GlobalsFeed
  Live feed of recent global events with 5-second polling.
  Used on the home page to show latest globals.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy } from 'svelte';

  /** @type {Array<object>} Initial globals from server-side load */
  export let initialGlobals = [];

  const POLL_INTERVAL = 5000;
  const MAX_ITEMS = 15;

  const TYPE_CONFIG = {
    kill:       { label: 'Hunting',     cssClass: 'type-kill' },
    team_kill:  { label: 'Team Hunt',  cssClass: 'type-kill' },
    deposit:    { label: 'Mining',     cssClass: 'type-deposit' },
    craft:      { label: 'Crafting',   cssClass: 'type-craft' },
    rare_item:  { label: 'Rare Find',  cssClass: 'type-rare' },
    discovery:  { label: 'Discovery',  cssClass: 'type-discovery' },
    tier:       { label: 'Tier Record', cssClass: 'type-tier' },
    examine:    { label: 'Instance',   cssClass: 'type-examine' },
    pvp:        { label: 'PvP',        cssClass: 'type-pvp' },
  };

  let globals = [...initialGlobals].slice(0, MAX_ITEMS);
  let pollTimer = null;
  let latestTimestamp = globals.length > 0 ? globals[0].timestamp : null;
  let newIds = new Set();

  function timeAgo(dateStr) {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diff = now - then;
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  }

  function formatValue(value, unit, type) {
    if (type === 'discovery') return '';
    if (type === 'tier' && unit === 'TIER') return `Tier ${value}`;
    if (type === 'pvp') return `${value} kills`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K PED`;
    return `${value.toFixed(2)} PED`;
  }

  async function poll() {
    try {
      const params = new URLSearchParams({ limit: '20' });
      if (latestTimestamp) {
        params.set('since', latestTimestamp);
      }
      const res = await fetch(`/api/globals?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.globals && data.globals.length > 0) {
        // Mark new entries for animation
        const incoming = data.globals.filter(g =>
          !globals.some(existing => existing.id === g.id)
        );
        for (const g of incoming) {
          newIds.add(g.id);
        }
        // Merge and sort
        const merged = [...incoming, ...globals];
        merged.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        globals = merged.slice(0, MAX_ITEMS);
        if (globals.length > 0) {
          latestTimestamp = globals[0].timestamp;
        }
        // Clear animation class after transition
        if (incoming.length > 0) {
          setTimeout(() => { newIds = new Set(); }, 600);
        }
      }
    } catch {
      // Silently ignore poll errors
    }
  }

  onMount(() => {
    pollTimer = setInterval(poll, POLL_INTERVAL);
  });

  onDestroy(() => {
    if (pollTimer) clearInterval(pollTimer);
  });

  function getTypeConfig(type) {
    return TYPE_CONFIG[type] || { label: type, cssClass: '' };
  }
</script>

<div class="globals-feed">
  {#if globals.length === 0}
    <p class="feed-empty">No globals recorded yet</p>
  {:else}
    <ul class="feed-list">
      {#each globals as g (g.id)}
        {@const tc = getTypeConfig(g.type)}
        <li class="feed-item" class:feed-item-new={newIds.has(g.id)}>
          <span class="feed-type {tc.cssClass}">{tc.label}</span>
          <span class="feed-content">
            <a href="/globals/player/{encodeURIComponent(g.player)}" class="feed-player">
              {g.player}
            </a>
            <span class="feed-target">{g.target}</span>
          </span>
          <span class="feed-value">
            {formatValue(g.value, g.unit, g.type)}
          </span>
          <span class="feed-badges">
            {#if g.ath}
              <span class="badge-ath">ATH</span>
            {:else if g.hof}
              <span class="badge-hof">HoF</span>
            {/if}
          </span>
          <span class="feed-time">{timeAgo(g.timestamp)}</span>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .globals-feed {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .feed-empty {
    padding: 24px;
    text-align: center;
    color: var(--text-muted);
    font-size: 0.875rem;
    margin: 0;
  }

  .feed-list {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .feed-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-color);
    font-size: 0.8125rem;
    transition: background-color 0.3s ease, opacity 0.3s ease;
  }

  .feed-item:last-child {
    border-bottom: none;
  }

  .feed-item:hover {
    background-color: var(--hover-color);
  }

  .feed-item-new {
    animation: feed-slide-in 0.4s ease-out;
    background-color: rgba(59, 130, 246, 0.06);
  }

  @keyframes feed-slide-in {
    from {
      opacity: 0;
      transform: translateY(-8px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .feed-type {
    flex-shrink: 0;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    min-width: 64px;
    text-align: center;
  }

  .type-kill     { background: rgba(239, 68, 68, 0.15);  color: #ef4444; }
  .type-deposit  { background: rgba(59, 130, 246, 0.15); color: #60b0ff; }
  .type-craft    { background: rgba(249, 115, 22, 0.15); color: #f97316; }
  .type-rare     { background: rgba(96, 176, 255, 0.15); color: var(--accent-color); }
  .type-discovery { background: rgba(155, 89, 182, 0.15); color: #9b59b6; }
  .type-tier     { background: rgba(241, 196, 15, 0.15); color: #f1c40f; }
  .type-examine  { background: rgba(46, 204, 113, 0.15); color: #2ecc71; }
  .type-pvp      { background: rgba(231, 76, 60, 0.15);  color: #e74c3c; }

  .feed-content {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .feed-player {
    color: var(--text-color);
    font-weight: 600;
    text-decoration: none;
  }

  .feed-player:hover {
    color: var(--accent-color);
    text-decoration: underline;
  }

  .feed-target {
    color: var(--text-muted);
    margin-left: 4px;
  }

  .feed-value {
    flex-shrink: 0;
    font-weight: 600;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
    min-width: 80px;
    text-align: right;
  }

  .feed-badges {
    flex-shrink: 0;
    min-width: 32px;
    text-align: center;
  }

  .badge-hof, .badge-ath {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  .badge-hof {
    background: rgba(234, 179, 8, 0.15);
    color: #eab308;
  }

  .badge-ath {
    background: rgba(239, 68, 68, 0.2);
    color: #ef4444;
    animation: ath-pulse 2s ease-in-out infinite;
  }

  @keyframes ath-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }

  .feed-time {
    flex-shrink: 0;
    color: var(--text-muted);
    font-size: 0.75rem;
    min-width: 50px;
    text-align: right;
  }

  /* Responsive */
  @media (max-width: 599px) {
    .feed-item {
      flex-wrap: wrap;
      gap: 6px;
    }

    .feed-value {
      min-width: auto;
    }

    .feed-badges {
      min-width: auto;
    }

    .feed-time {
      min-width: auto;
      margin-left: auto;
    }
  }
</style>
