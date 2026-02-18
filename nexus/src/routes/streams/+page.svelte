<!--
  @component Streams Page
  Lists all content creator streams and channels.
  Live streams shown first, then offline channels.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';

  export let data;

  $: streams = data.streams || [];
  $: hasLive = data.hasLive;

  const platformLabels = { youtube: 'YouTube', twitch: 'Twitch', kick: 'Kick' };

  function formatViewerCount(count) {
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
    return String(count);
  }
</script>

<svelte:head>
  <title>Streams - Entropia Nexus</title>
  <meta name="description" content="Watch live Entropia Universe streams on Twitch and Kick. Find your favorite content creators and discover new channels." />
  <link rel="canonical" href="https://entropianexus.com/streams" />

  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/streams" />
  <meta property="og:title" content="Entropia Universe Streams - Entropia Nexus" />
  <meta property="og:description" content="Watch live Entropia Universe streams on Twitch and Kick. Find your favorite content creators." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />

  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Entropia Universe Streams - Entropia Nexus" />
  <meta name="twitter:description" content="Watch live Entropia Universe streams on Twitch and Kick. Find your favorite content creators." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/">Home</a>
    <span class="separator">/</span>
    <span>Streams</span>
  </nav>

  <div class="page-header">
    <h1>{hasLive ? 'Live Streams' : 'Channels'}</h1>
  </div>

  {#if streams.length === 0}
    <p class="empty-state">No streams or channels available yet.</p>
  {:else}
    <div class="preview-grid">
      {#each streams as stream}
        <a href={stream.channelUrl} class="preview-card" target="_blank" rel="noopener">
          <div class="preview-thumbnail">
            {#if stream.thumbnail}
              <img src={stream.thumbnail} alt={stream.offline ? stream.name : stream.title} loading="lazy" />
            {/if}
            {#if stream.offline}
              <div class="offline-overlay" class:no-thumbnail={!stream.thumbnail}>
                {#if stream.avatar}
                  <img src={stream.avatar} alt={stream.name} class="offline-avatar" />
                {/if}
              </div>
              <span class="platform-badge {stream.platform}">{platformLabels[stream.platform]}</span>
            {:else}
              <span class="platform-badge twitch">Twitch</span>
              {#if stream.avatar}
                <div class="preview-avatar">
                  <img src={stream.avatar} alt={stream.name} />
                </div>
              {/if}
              <div class="live-indicator">
                <span class="live-dot"></span>
                {formatViewerCount(stream.viewerCount)}
              </div>
            {/if}
          </div>
          <div class="preview-info">
            {#if stream.offline}
              <span class="preview-title">{stream.name}</span>
              <span class="preview-meta">Offline</span>
            {:else}
              <span class="preview-title">{stream.title}</span>
              <span class="preview-meta">{stream.name}{stream.gameName ? ` \u00B7 ${stream.gameName}` : ''}</span>
            {/if}
          </div>
        </a>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    box-sizing: border-box;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .separator {
    color: var(--text-muted);
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    margin: 0;
    color: var(--text-color);
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .preview-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }

  .preview-card {
    display: flex;
    flex-direction: column;
    text-decoration: none;
    color: var(--text-color);
    border-radius: 8px;
    overflow: hidden;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    transition: border-color 0.15s ease, transform 0.15s ease;
  }

  .preview-card:hover {
    border-color: var(--accent-color);
    transform: translateY(-2px);
  }

  .preview-thumbnail {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background-color: var(--primary-color);
  }

  .preview-thumbnail img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .offline-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1;
  }

  .offline-overlay.no-thumbnail {
    background: var(--secondary-color);
  }

  .offline-avatar {
    width: 52px;
    height: 52px;
    min-width: 52px;
    min-height: 52px;
    border-radius: 50%;
    border: 2px solid rgba(255, 255, 255, 0.25);
    object-fit: cover;
    flex-shrink: 0;
  }

  .no-thumbnail .offline-avatar {
    width: 64px;
    height: 64px;
    min-width: 64px;
    min-height: 64px;
    border-color: var(--border-color);
  }

  .platform-badge {
    position: absolute;
    top: 8px;
    right: 8px;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.625rem;
    font-weight: 700;
    letter-spacing: 0.3px;
    text-transform: uppercase;
  }

  .platform-badge.twitch {
    background: rgba(145, 70, 255, 0.9);
    color: white;
  }

  .platform-badge.kick {
    background: rgba(83, 252, 24, 0.9);
    color: #111;
  }

  .preview-avatar {
    position: absolute;
    bottom: 8px;
    left: 8px;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    overflow: hidden;
    border: 2px solid rgba(0, 0, 0, 0.4);
    background-color: var(--primary-color);
  }

  .preview-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .live-indicator {
    position: absolute;
    bottom: 8px;
    right: 8px;
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    background: rgba(0, 0, 0, 0.75);
    border-radius: 4px;
    font-size: 0.6875rem;
    color: white;
    font-weight: 600;
  }

  .live-dot {
    width: 7px;
    height: 7px;
    background: #ef4444;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .preview-info {
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .preview-title {
    font-size: 0.8125rem;
    font-weight: 600;
    line-height: 1.35;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .preview-meta {
    font-size: 0.75rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  @media (max-width: 899px) {
    .page-container {
      padding: 16px;
    }

    .preview-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 599px) {
    .preview-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
