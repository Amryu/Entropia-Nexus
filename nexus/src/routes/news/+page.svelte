<!--
  @component News Page
  Lists all news items (Nexus announcements + Steam news), sorted by date.
  Uses IntersectionObserver for progressive loading.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';

  let { data } = $props();

  const BATCH_SIZE = 12;
  let visibleCount = $state(BATCH_SIZE);
  let sentinel = $state();
  let observer;

  let allNews = $derived(data.news || []);
  let visibleNews = $derived(allNews.slice(0, visibleCount));
  let hasMore = $derived(visibleCount < allNews.length);

  function timeAgo(dateStr) {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const diff = now - then;
    const minutes = Math.floor(diff / 60000);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  onMount(() => {
    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore) {
        visibleCount = Math.min(visibleCount + BATCH_SIZE, allNews.length);
      }
    }, { rootMargin: '200px' });

    if (sentinel) observer.observe(sentinel);
  });

  onDestroy(() => {
    observer?.disconnect();
  });
</script>

<svelte:head>
  <title>News - Entropia Nexus</title>
  <meta name="description" content="Latest Entropia Universe news, official announcements and community updates. Stay informed about patches, events and game changes." />
  <link rel="canonical" href="https://entropianexus.com/news" />

  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/news" />
  <meta property="og:title" content="Entropia Universe News - Entropia Nexus" />
  <meta property="og:description" content="Latest Entropia Universe news, official announcements and community updates." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />

  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Entropia Universe News - Entropia Nexus" />
  <meta name="twitter:description" content="Latest Entropia Universe news, official announcements and community updates." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/">Home</a>
    <span class="separator">/</span>
    <span>News</span>
  </nav>

  <div class="page-header">
    <h1>News</h1>
  </div>

  {#if allNews.length === 0}
    <p class="empty-state">No news available yet.</p>
  {:else}
    <div class="news-grid">
      {#each visibleNews as item}
        <a href={item.url || '#'} class="news-card" target={!item.has_content ? '_blank' : undefined} rel={!item.has_content ? 'noopener' : undefined}>
          {#if item.image_url}
            <div class="news-image" style="background-image: url({item.image_url})"></div>
          {/if}
          <div class="news-body">
            <div class="news-meta">
              <span class="news-source" class:nexus={item.source === 'nexus'} class:steam={item.source === 'steam'}>
                {item.source === 'nexus' ? 'Nexus' : 'EU News'}
              </span>
              {#if item.pinned}
                <span class="news-pinned">Pinned</span>
              {/if}
              <span class="news-date">{timeAgo(item.date)}</span>
            </div>
            <h3 class="news-title">{item.title}</h3>
            {#if item.summary}
              <p class="news-summary">{item.summary}</p>
            {/if}
          </div>
        </a>
      {/each}
    </div>

    {#if hasMore}
      <div class="sentinel" bind:this={sentinel}></div>
    {/if}
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

  .news-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
  }

  .news-card {
    display: flex;
    flex-direction: column;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }

  .news-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .news-image {
    height: 160px;
    background-size: cover;
    background-position: center;
    background-color: var(--primary-color);
  }

  .news-body {
    padding: 16px;
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .news-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    font-size: 0.75rem;
  }

  .news-source {
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .news-source.nexus {
    background-color: #000;
    color: #fff;
  }

  .news-source.steam {
    background-color: rgba(102, 192, 244, 0.12);
    color: #66c0f4;
  }

  .news-pinned {
    padding: 2px 8px;
    border-radius: 4px;
    background-color: rgba(234, 179, 8, 0.15);
    color: #eab308;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .news-date {
    color: var(--text-muted);
    margin-left: auto;
  }

  .news-title {
    margin: 0 0 8px 0;
    font-size: 1rem;
    font-weight: 600;
    line-height: 1.35;
    color: var(--text-color);
  }

  .news-summary {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--text-muted);
    line-height: 1.5;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .sentinel {
    height: 1px;
  }

  @media (max-width: 899px) {
    .page-container {
      padding: 16px;
    }

    .news-grid {
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    }
  }

  @media (max-width: 599px) {
    .news-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
