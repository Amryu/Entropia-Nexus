<script>
  // @ts-nocheck
  export let data;
</script>

<svelte:head>
  <title>API Reference | Entropia Nexus</title>
</svelte:head>

<div class="api-docs">
  <div class="prose">
    {@html data.html}
  </div>
</div>

<style>
  .api-docs {
    padding: 2rem;
    max-width: 900px;
  }

  /* Prose styling for rendered markdown */
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
    margin: 2rem 0 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color);
  }

  .prose :global(h3) {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin: 1.5rem 0 0.75rem;
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
