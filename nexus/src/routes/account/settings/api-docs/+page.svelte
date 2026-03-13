<script>
  // @ts-nocheck
  import { onMount } from 'svelte';

  let { data } = $props();

  let activeId = $state('');
  let tocOpen = $state(false);

  function scrollTo(id) {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      activeId = id;
      tocOpen = false;
    }
  }

  onMount(() => {
    const headingEls = data.headings
      .map(h => document.getElementById(h.id))
      .filter(Boolean);

    if (!headingEls.length) return;

    const scrollContainer = document.querySelector('.settings-content');
    if (!scrollContainer) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            activeId = entry.target.id;
          }
        }
      },
      {
        root: scrollContainer,
        rootMargin: '-5% 0px -80% 0px',
        threshold: 0
      }
    );

    for (const el of headingEls) observer.observe(el);

    return () => observer.disconnect();
  });
</script>

<svelte:head>
  <title>API Reference | Entropia Nexus</title>
</svelte:head>

<div class="api-docs">
  <div class="toc-mobile">
    <button class="toc-toggle" onclick={() => tocOpen = !tocOpen}>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="6" x2="21" y2="6" />
        <line x1="3" y1="12" x2="15" y2="12" />
        <line x1="3" y1="18" x2="18" y2="18" />
      </svg>
      Table of Contents
      <span class="toc-arrow" class:open={tocOpen}>&#9662;</span>
    </button>
    {#if tocOpen}
      <nav class="toc-dropdown">
        {#each data.headings.filter(h => h.level === 2) as heading}
          <button class="toc-link" class:active={activeId === heading.id} onclick={() => scrollTo(heading.id)}>
            {heading.text}
          </button>
        {/each}
      </nav>
    {/if}
  </div>

  <div class="docs-layout">
    <div class="prose">
      {@html data.html}
    </div>
    <nav class="toc-sidebar">
      <div class="toc-title">On this page</div>
      {#each data.headings as heading}
        <button
          class="toc-item"
          class:sub={heading.level === 3}
          class:active={activeId === heading.id}
          onclick={() => scrollTo(heading.id)}
        >
          {heading.text}
        </button>
      {/each}
    </nav>
  </div>
</div>

<style>
  .api-docs {
    padding: 2rem;
  }

  .prose :global(.h1-row) {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: 0 0 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-color);
  }

  .prose :global(.h1-row h1) {
    margin: 0;
    padding: 0;
    border: none;
  }

  .prose :global(.download-btn) {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    margin-left: auto;
    flex-shrink: 0;
    padding: 0.35rem 0.65rem;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background: var(--secondary-color);
    color: var(--text-secondary);
    font-size: 0.8rem;
    font-weight: 400;
    text-decoration: none;
    cursor: pointer;
    font-family: inherit;
    white-space: nowrap;
    transition: color 0.15s, border-color 0.15s;
  }

  .prose :global(.download-btn:hover) {
    color: var(--text-primary);
    border-color: var(--text-muted);
    text-decoration: none;
  }

  .docs-layout {
    display: flex;
    gap: 2rem;
    align-items: flex-start;
  }

  .prose {
    flex: 1;
    min-width: 0;
    max-width: 900px;
  }

  /* ── Desktop TOC sidebar ── */
  .toc-sidebar {
    position: sticky;
    top: 1rem;
    align-self: flex-start;
    width: 200px;
    flex-shrink: 0;
    max-height: calc(100vh - 6rem);
    overflow-y: auto;
    padding-bottom: 2rem;
    border-left: 1px solid var(--border-color);
    padding-left: 1rem;
  }

  .toc-title {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-secondary);
    font-weight: 600;
    margin-bottom: 0.5rem;
  }

  .toc-item {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    padding: 0.2rem 0;
    font-size: 0.78rem;
    color: var(--text-muted);
    cursor: pointer;
    line-height: 1.4;
    transition: color 0.15s;
    font-family: inherit;
  }

  .toc-item:hover {
    color: var(--text-primary);
  }

  .toc-item.active {
    color: var(--accent-color);
  }

  .toc-item.sub {
    padding-left: 0.75rem;
    font-size: 0.73rem;
  }

  /* ── Mobile TOC ── */
  .toc-mobile {
    display: none;
    margin-bottom: 1rem;
  }

  .toc-toggle {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    background: var(--secondary-color);
    color: var(--text-primary);
    font-size: 0.85rem;
    cursor: pointer;
    font-family: inherit;
    width: 100%;
  }

  .toc-arrow {
    margin-left: auto;
    font-size: 0.7rem;
    transition: transform 0.15s;
  }

  .toc-arrow.open {
    transform: rotate(180deg);
  }

  .toc-dropdown {
    display: flex;
    flex-direction: column;
    margin-top: 0.5rem;
    padding: 0.5rem;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
  }

  .toc-link {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    padding: 0.4rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
    color: var(--text-secondary);
    cursor: pointer;
    font-family: inherit;
    transition: background 0.15s, color 0.15s;
  }

  .toc-link:hover {
    background: var(--hover-bg);
    color: var(--text-primary);
  }

  .toc-link.active {
    color: var(--accent-color);
  }

  /* ── Prose styling for rendered markdown ── */
  .prose :global(h1) {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 1.5rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--border-color);
  }

  .prose :global(h2) {
    font-size: 1.35rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 2.5rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color);
  }

  .prose :global(h2:first-child),
  .prose :global(h1 + h2) {
    margin-top: 1.5rem;
  }

  .prose :global(h3) {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 1.75rem 0 0.75rem;
  }

  .prose :global(h4) {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 1.25rem 0 0.5rem;
  }

  .prose :global(h4 code) {
    font-size: 0.9rem;
    background: var(--accent-color);
    color: white;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-weight: 600;
  }

  .prose :global(p) {
    color: var(--text-secondary);
    line-height: 1.6;
    margin: 0.5rem 0;
  }

  .prose :global(strong) {
    color: var(--text-primary);
  }

  .prose :global(a) {
    color: var(--accent-color);
    text-decoration: none;
  }

  .prose :global(a:hover) {
    text-decoration: underline;
  }

  .prose :global(code) {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 0.85em;
    background: var(--hover-bg);
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    color: var(--accent-color);
  }

  .prose :global(pre) {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
    overflow-x: auto;
    margin: 0.75rem 0;
  }

  .prose :global(pre code) {
    background: none;
    padding: 0;
    font-size: 0.8rem;
    color: var(--text-primary);
    line-height: 1.5;
  }

  .prose :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin: 0.75rem 0;
    font-size: 0.85rem;
  }

  .prose :global(th) {
    text-align: left;
    padding: 0.5rem 0.75rem;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    font-weight: 600;
  }

  .prose :global(td) {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
  }

  .prose :global(blockquote) {
    border-left: 3px solid var(--accent-color);
    margin: 0.75rem 0;
    padding: 0.5rem 1rem;
    background: var(--secondary-color);
    border-radius: 0 6px 6px 0;
  }

  .prose :global(blockquote p) {
    margin: 0;
    font-size: 0.85rem;
  }

  .prose :global(hr) {
    border: none;
    border-top: 1px solid var(--border-color);
    margin: 2rem 0;
  }

  .prose :global(ul),
  .prose :global(ol) {
    color: var(--text-secondary);
    padding-left: 1.5rem;
    margin: 0.5rem 0;
  }

  .prose :global(li) {
    margin: 0.25rem 0;
    line-height: 1.5;
  }

  @media (max-width: 1100px) {
    .toc-sidebar {
      display: none;
    }

    .toc-mobile {
      display: block;
    }
  }

  @media (max-width: 768px) {
    .api-docs {
      padding: 1rem;
    }

    .prose :global(h1) {
      font-size: 1.4rem;
    }

    .prose :global(h2) {
      font-size: 1.15rem;
    }

    .prose :global(pre) {
      font-size: 0.75rem;
      padding: 0.75rem;
    }

    .prose :global(table) {
      font-size: 0.8rem;
    }

    .prose :global(th),
    .prose :global(td) {
      padding: 0.35rem 0.5rem;
    }
  }
</style>
