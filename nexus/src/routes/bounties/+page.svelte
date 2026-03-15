<!--
  @component Bounties Page
  Public page showing reward rules and top contributors.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount } from 'svelte';

  let categories = $state({});
  let contributors = $state([]);
  let isLoading = $state(true);

  onMount(async () => {
    try {
      const res = await fetch('/api/bounties');
      if (res.ok) {
        const data = await res.json();
        categories = data.categories;
        contributors = data.contributors;
      }
    } catch {}
    isLoading = false;
  });

  function formatAmount(rule) {
    const min = parseFloat(rule.min_amount);
    const max = parseFloat(rule.max_amount);
    if (min === max) return `${min.toFixed(2)} PED`;
    return `${min.toFixed(2)} - ${max.toFixed(2)} PED`;
  }

  const categoryIcons = {
    'Mapping': '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon><line x1="8" y1="2" x2="8" y2="18"></line><line x1="16" y1="6" x2="16" y2="22"></line></svg>',
    'Item Data': '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>',
    'Mob Data': '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>',
    'Information': '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>'
  };
</script>

<svelte:head>
  <title>Bounties - Entropia Nexus</title>
  <meta name="description" content="Earn PED by contributing to the Entropia Nexus wiki. View bounty rates for mapping, item data, and mob data contributions." />
  <link rel="canonical" href="https://entropianexus.com/bounties" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/bounties" />
  <meta property="og:title" content="Bounties - Entropia Nexus" />
  <meta property="og:description" content="Earn PED by contributing to the Entropia Nexus wiki. View bounty rates for mapping, item data, and mob data contributions." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Bounties - Entropia Nexus" />
  <meta name="twitter:description" content="Earn PED by contributing to the Entropia Nexus wiki. View bounty rates for mapping, item data, and mob data contributions." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<style>
  .page-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    height: 100%;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--text-muted);
  }
  .breadcrumb a { color: var(--accent-color); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }

  .page-header {
    text-align: center;
    margin-bottom: 2rem;
  }
  .page-header h1 {
    margin: 0 0 0.5rem;
    font-size: 2rem;
    color: var(--text-color);
  }
  .page-subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 1.05rem;
    line-height: 1.5;
  }

  .category-section {
    margin-bottom: 2rem;
  }
  .category-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
  }
  .category-icon { color: var(--accent-color); display: flex; align-items: center; }
  .category-header h2 {
    margin: 0;
    font-size: 1.3rem;
    color: var(--text-color);
  }

  .bounty-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .bounty-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 18px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    gap: 16px;
  }
  .bounty-card:hover { border-color: var(--accent-color); }

  .bounty-info { flex: 1; min-width: 0; }
  .bounty-name {
    font-weight: 600;
    font-size: 15px;
    color: var(--text-color);
    margin-bottom: 3px;
  }
  .bounty-desc {
    font-size: 13px;
    color: var(--text-muted);
    line-height: 1.4;
  }

  .bounty-amount {
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 16px;
    font-weight: 700;
    color: var(--success-color);
    white-space: nowrap;
    flex-shrink: 0;
  }

  .info-box {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 18px;
    margin-bottom: 2rem;
  }
  .info-box h3 {
    margin: 0 0 8px;
    font-size: 15px;
    color: var(--text-color);
  }
  .info-box p, .info-box li {
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.6;
    margin: 0;
  }
  .info-box ul {
    margin: 8px 0 0;
    padding-left: 20px;
  }

  .warning-box {
    border-color: var(--warning-color);
    background: rgba(245, 158, 11, 0.05);
  }
  .warning-box h3 { color: var(--warning-color); }

  /* Leaderboard */
  .leaderboard {
    margin-top: 2rem;
  }
  .leaderboard h2 {
    margin: 0 0 12px;
    font-size: 1.3rem;
    color: var(--text-color);
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 8px;
  }

  .leaderboard-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .leaderboard-entry {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .lb-rank {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-muted);
    width: 28px;
    text-align: center;
    flex-shrink: 0;
  }
  .lb-rank.top1 { color: #fbbf24; }
  .lb-rank.top2 { color: #9ca3af; }
  .lb-rank.top3 { color: #b45309; }

  .lb-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--hover-color);
    flex-shrink: 0;
  }

  .lb-name {
    flex: 1;
    min-width: 0;
  }
  .lb-name-primary {
    font-weight: 500;
    color: var(--text-color);
    font-size: 14px;
  }
  .lb-name-eu {
    font-size: 12px;
    color: var(--text-muted);
  }

  .lb-count {
    font-weight: 600;
    color: var(--accent-color);
    font-size: 14px;
    white-space: nowrap;
  }

  .loading-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
  }

  @media (max-width: 768px) {
    .page-container { padding: 16px; }
    .page-header h1 { font-size: 1.5rem; }
    .bounty-card { flex-direction: column; align-items: flex-start; gap: 8px; }
    .bounty-amount { font-size: 15px; }
  }
</style>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/">Home</a>
    <span>/</span>
    <span>Bounties</span>
  </nav>

  <div class="page-header">
    <h1>Contributor Bounties</h1>
    <p class="page-subtitle">
      Help build the Entropia Nexus wiki and earn PED for your contributions.
      Below are the current bounty rates for different types of contributions.
    </p>
  </div>

  {#if isLoading}
    <div class="loading-state">Loading bounties...</div>
  {:else}
    <div class="info-box">
      <h3>How it works</h3>
      <ul>
        <li>Submit wiki changes through the site - locations, items, mobs, and more</li>
        <li>Your changes will be reviewed and approved by admins</li>
        <li>Once approved, you earn PED based on the bounty rates below</li>
        <li>There will be bonuses for contributors who provide a lot of coverage individually</li>
        <li>Any other corrections or additions will be individually assessed and paid for too</li>
        <li>Payouts happen as the admin is available, mostly on Calypso</li>
      </ul>
    </div>

    {#each Object.entries(categories) as [categoryName, categoryRules]}
      <div class="category-section">
        <div class="category-header">
          <span class="category-icon">{@html categoryIcons[categoryName] || ''}</span>
          <h2>{categoryName}</h2>
        </div>
        <div class="bounty-list">
          {#each categoryRules as rule}
            <div class="bounty-card">
              <div class="bounty-info">
                <div class="bounty-name">{rule.name}</div>
                {#if rule.description}
                  <div class="bounty-desc">{rule.description}</div>
                {/if}
              </div>
              <div class="bounty-amount">{formatAmount(rule)}</div>
            </div>
          {/each}
        </div>
      </div>
    {/each}

    <div class="info-box warning-box">
      <h3>Important</h3>
      <p>Providing intentionally wrong or incomplete data will void all your earnings. Quality and accuracy are required for all contributions.</p>
    </div>

    {#if contributors.length > 0}
      <div class="leaderboard">
        <h2>Top Contributors</h2>
        <div class="leaderboard-list">
          {#each contributors as contributor, i}
            <div class="leaderboard-entry">
              <div class="lb-rank" class:top1={i === 0} class:top2={i === 1} class:top3={i === 2}>
                #{i + 1}
              </div>
              {#if contributor.avatar}
                <img class="lb-avatar" src="https://cdn.discordapp.com/avatars/{contributor.id}/{contributor.avatar}.webp?size=64" alt="" />
              {:else}
                <div class="lb-avatar"></div>
              {/if}
              <div class="lb-name">
                <div class="lb-name-primary">{contributor.global_name || 'Unknown'}</div>
                {#if contributor.eu_name}
                  <div class="lb-name-eu">{contributor.eu_name}</div>
                {/if}
              </div>
              <div class="lb-count">{contributor.approved_count} approved</div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>
