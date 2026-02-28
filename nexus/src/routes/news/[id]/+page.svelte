<script>
  // @ts-nocheck
  import { sanitizeHtml } from '$lib/sanitize';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';

  /** @type {import('./$types').PageData} */
  export let data;

  $: announcement = data.announcement;

  onMount(() => {
    const autoplayId = ($page.url.searchParams.get('autoplay') || '').replace(/[^a-zA-Z0-9_-]/g, '');
    if (autoplayId) {
      const iframe = document.querySelector(`.article-body iframe[src*="/embed/${autoplayId}"]`);
      if (iframe) {
        const url = new URL(iframe.src);
        url.searchParams.set('autoplay', '1');
        iframe.src = url.toString();
        iframe.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  });

  function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  }
</script>

<svelte:head>
  <title>{announcement.title} - Entropia Nexus</title>
  {#if announcement.summary}
    <meta name="description" content={announcement.summary} />
  {/if}
  <link rel="canonical" href={`https://entropianexus.com/news/${announcement.id}`} />

  <meta property="og:type" content="article" />
  <meta property="og:url" content={`https://entropianexus.com/news/${announcement.id}`} />
  <meta property="og:title" content={announcement.title} />
  {#if announcement.summary}
    <meta property="og:description" content={announcement.summary} />
  {/if}
  <meta property="og:image" content={announcement.image_url || 'https://entropianexus.com/icon.png'} />
  <meta property="og:site_name" content="Entropia Nexus" />

  <meta name="twitter:card" content={announcement.image_url ? 'summary_large_image' : 'summary'} />
  <meta name="twitter:title" content={announcement.title} />
  {#if announcement.summary}
    <meta name="twitter:description" content={announcement.summary} />
  {/if}
  <meta name="twitter:image" content={announcement.image_url || 'https://entropianexus.com/icon.png'} />
</svelte:head>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/">Home</a>
    <span class="separator">/</span>
    <span>News</span>
  </nav>

  <article class="article">
    <header class="article-header">
      <h1>{announcement.title}</h1>
      <div class="article-meta">
        <span class="source-badge" class:steam={announcement.source === 'steam'}>
          {announcement.source === 'steam' ? 'EU News' : 'Nexus'}
        </span>
        {#if announcement.author_name}
          <span class="author">By {announcement.author_name}</span>
          <span class="dot">&middot;</span>
        {/if}
        <time datetime={announcement.created_at}>{formatDate(announcement.created_at)}</time>
      </div>
    </header>

    {#if announcement.image_url}
      <div class="article-image">
        <img src={announcement.image_url} alt={announcement.title} />
      </div>
    {/if}

    {#if announcement.content_html}
      <div class="article-body">
        {@html sanitizeHtml(announcement.content_html)}
      </div>
    {:else if announcement.summary}
      <div class="article-body">
        <p>{announcement.summary}</p>
      </div>
    {/if}

    {#if announcement.link}
      <div class="external-link">
        <a href={announcement.link} target="_blank" rel="noopener noreferrer">
          {announcement.source === 'steam' ? 'View on Steam' : 'View original source'} &rarr;
        </a>
      </div>
    {/if}

    <div class="back-link">
      <a href="/news">&larr; Back to News</a>
    </div>
  </article>
</div>

<style>
  .page-container {
    padding: 1rem;
    padding-bottom: 2rem;
    max-width: 800px;
    margin: 0 auto;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1.5rem;
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

  .article {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 2rem;
  }

  .article-header {
    margin-bottom: 1.5rem;
  }

  .article-header h1 {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 0.75rem 0;
    line-height: 1.3;
  }

  .article-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .source-badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    background-color: rgba(59, 130, 246, 0.15);
    color: var(--accent-color);
  }

  .source-badge.steam {
    background-color: rgba(102, 192, 244, 0.12);
    color: #66c0f4;
  }

  .author {
    font-weight: 500;
  }

  .article-image {
    margin-bottom: 1.5rem;
    border-radius: 6px;
    overflow: hidden;
  }

  .article-image img {
    width: 100%;
    display: block;
  }

  .article-body {
    line-height: 1.7;
    color: var(--text-color);
    font-size: 0.95rem;
  }

  .article-body :global(h2) {
    font-size: 1.4rem;
    font-weight: 600;
    margin: 1.5rem 0 0.5rem 0;
    color: var(--text-color);
  }

  .article-body :global(h3) {
    font-size: 1.2rem;
    font-weight: 600;
    margin: 1.25rem 0 0.5rem 0;
    color: var(--text-color);
  }

  .article-body :global(h4) {
    font-size: 1.05rem;
    font-weight: 600;
    margin: 1rem 0 0.5rem 0;
    color: var(--text-color);
  }

  .article-body :global(p) {
    margin: 0 0 0.75rem 0;
  }

  .article-body :global(p:last-child) {
    margin-bottom: 0;
  }

  .article-body :global(a) {
    color: var(--accent-color);
    text-decoration: none;
  }

  .article-body :global(a:hover) {
    text-decoration: underline;
  }

  .article-body :global(strong) {
    font-weight: 600;
  }

  .article-body :global(blockquote) {
    border-left: 3px solid var(--accent-color);
    padding-left: 1rem;
    margin: 1rem 0;
    color: var(--text-muted);
    font-style: italic;
  }

  .article-body :global(code) {
    background-color: var(--primary-color);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.875em;
  }

  .article-body :global(pre) {
    background-color: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 1rem;
    margin: 1rem 0;
    overflow-x: auto;
    font-size: 0.875rem;
  }

  .article-body :global(ul),
  .article-body :global(ol) {
    padding-left: 1.5rem;
    margin: 0.5rem 0;
  }

  .article-body :global(li) {
    margin: 0.25rem 0;
  }

  .article-body :global(img) {
    max-width: 100%;
    height: auto;
    border-radius: 6px;
    margin: 1rem 0;
  }

  .article-body :global(hr) {
    border: none;
    border-top: 1px solid var(--border-color);
    margin: 1.5rem 0;
  }

  .article-body :global(.video-embed-wrapper) {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    margin: 1rem 0;
    border-radius: 8px;
    overflow: hidden;
  }

  .article-body :global(.video-embed-wrapper iframe),
  .article-body :global(.video-embed-iframe) {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border: none;
  }

  .external-link {
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .external-link a {
    color: var(--accent-color);
    text-decoration: none;
    font-weight: 500;
  }

  .external-link a:hover {
    text-decoration: underline;
  }

  .back-link {
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .back-link a {
    color: var(--text-muted);
    text-decoration: none;
    font-size: 0.875rem;
  }

  .back-link a:hover {
    color: var(--accent-color);
  }

  @media (max-width: 899px) {
    .article {
      padding: 1.25rem;
    }

    .article-header h1 {
      font-size: 1.4rem;
    }
  }
</style>
