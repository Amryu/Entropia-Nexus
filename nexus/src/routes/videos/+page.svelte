<!--
  @component Videos Page
  Lists all YouTube videos from content creators, sorted by publish date.
  Uses IntersectionObserver for progressive loading.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';

  export let data;

  const BATCH_SIZE = 12;
  let visibleCount = BATCH_SIZE;
  let sentinel;
  let observer;

  $: allVideos = data.videos || [];
  $: visibleVideos = allVideos.slice(0, visibleCount);
  $: hasMore = visibleCount < allVideos.length;

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
        visibleCount = Math.min(visibleCount + BATCH_SIZE, allVideos.length);
      }
    }, { rootMargin: '200px' });

    if (sentinel) observer.observe(sentinel);
  });

  onDestroy(() => {
    observer?.disconnect();
  });
</script>

<svelte:head>
  <title>Videos - Entropia Nexus</title>
  <meta name="description" content="Watch the latest Entropia Universe YouTube videos from community content creators. Gameplay, guides, hunting and more." />
  <link rel="canonical" href="https://entropianexus.com/videos" />

  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/videos" />
  <meta property="og:title" content="Entropia Universe Videos - Entropia Nexus" />
  <meta property="og:description" content="Watch the latest Entropia Universe YouTube videos from community content creators." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />

  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Entropia Universe Videos - Entropia Nexus" />
  <meta name="twitter:description" content="Watch the latest Entropia Universe YouTube videos from community content creators." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/">Home</a>
    <span class="separator">/</span>
    <span>Videos</span>
  </nav>

  <div class="page-header">
    <h1>Videos</h1>
  </div>

  {#if allVideos.length === 0}
    <p class="empty-state">No videos available yet.</p>
  {:else}
    <div class="preview-grid">
      {#each visibleVideos as video}
        <a href={`https://www.youtube.com/watch?v=${video.videoId}`} class="preview-card" target="_blank" rel="noopener">
          <div class="preview-thumbnail">
            <img src={video.thumbnail} alt={video.title} loading="lazy" />
            <span class="platform-badge youtube">YouTube</span>
            {#if video.creatorAvatar}
              <div class="preview-avatar">
                <img src={video.creatorAvatar} alt={video.creatorName} />
              </div>
            {/if}
          </div>
          <div class="preview-info">
            <span class="preview-title">{video.title}</span>
            <span class="preview-meta">{video.creatorName}{video.publishedAt ? ` \u00B7 ${timeAgo(video.publishedAt)}` : ''}</span>
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

  .platform-badge.youtube {
    background: rgba(255, 0, 0, 0.9);
    color: white;
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

  .sentinel {
    height: 1px;
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
