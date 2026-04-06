<!--
  @component Promo Dashboard
  Overview cards showing promo stats and quick links.
  Shows a landing page for logged-out users.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';

  let { data } = $props();

  let totalPromos = $derived(data.totalPromos ?? 0);
  let activeBookings = $derived(data.activeBookings ?? 0);
  let pendingBookings = $derived(data.pendingBookings ?? 0);
  let totalViews = $derived(data.totalViews ?? 0);
  let totalClicks = $derived(data.totalClicks ?? 0);
  let ctr = $derived(totalViews > 0 ? ((totalClicks / totalViews) * 100).toFixed(2) : '0.00');

  let loginUrl = $derived(`/discord/login?redirect=${encodeURIComponent($page.url.pathname)}`);
</script>

{#if data.loggedOut}
<div class="scroll-container">
  <div class="landing-container">
    <h1>Promote on Entropia Nexus</h1>
    <p class="landing-subtitle">
      Reach the Entropia Universe community with self-serve promotions.
      Create ad creatives, book placement slots, and track performance — all from your dashboard.
    </p>

    <div class="features-grid">
      <div class="feature-card">
        <span class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        </span>
        <h3>Create Promos</h3>
        <p>Design placement banners or featured posts with your own images and text.</p>
      </div>
      <div class="feature-card">
        <span class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
        </span>
        <h3>Book Slots</h3>
        <p>Reserve weekly placement slots on high-traffic pages. Pay in PED.</p>
      </div>
      <div class="feature-card">
        <span class="feature-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        </span>
        <h3>Track Performance</h3>
        <p>Monitor views, clicks, and click-through rate in real time.</p>
      </div>
    </div>

    <div class="login-cta">
      <a href={loginUrl} class="login-btn">
        <svg width="20" height="20" viewBox="0 0 71 55" fill="currentColor">
          <path d="M60.1 4.9A58.5 58.5 0 0045.4.2a.2.2 0 00-.2.1 40.7 40.7 0 00-1.8 3.7 54 54 0 00-16.2 0A38 38 0 0025.4.3a.2.2 0 00-.2-.1A58.4 58.4 0 0010.5 5a.2.2 0 00-.1 0C1.5 18.7-.9 32 .3 45.2v.1a58.9 58.9 0 0018 9.1.2.2 0 00.3-.1 42 42 0 003.6-5.9.2.2 0 00-.1-.3 38.8 38.8 0 01-5.5-2.7.2.2 0 01 0-.4l1.1-.9a.2.2 0 01.2 0 42 42 0 0035.6 0 .2.2 0 01.2 0l1.1.9a.2.2 0 010 .3 36.4 36.4 0 01-5.5 2.7.2.2 0 00-.1.3 47.2 47.2 0 003.6 5.9.2.2 0 00.2.1 58.7 58.7 0 0018-9.1v-.1c1.4-15-2.3-28-9.8-39.6a.2.2 0 00-.1-.1zM23.7 37c-3.4 0-6.2-3.1-6.2-7s2.7-7 6.2-7 6.3 3.2 6.2 7-2.8 7-6.2 7zm23 0c-3.4 0-6.2-3.1-6.2-7s2.7-7 6.2-7 6.3 3.2 6.2 7-2.8 7-6.2 7z"/>
        </svg>
        Log in with Discord to get started
      </a>
    </div>
  </div>
</div>
{:else}
<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/account/settings">Settings</a>
      <span>/</span>
      <span>Promos</span>
    </div>

    <h1>Promo Dashboard</h1>

    <div class="stats-grid">
      <div class="stat-card">
        <span class="stat-value">{totalPromos}</span>
        <span class="stat-label">Total Promos</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{activeBookings}</span>
        <span class="stat-label">Active Bookings</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{pendingBookings}</span>
        <span class="stat-label">Pending Bookings</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{totalViews.toLocaleString()}</span>
        <span class="stat-label">Total Views</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{totalClicks.toLocaleString()}</span>
        <span class="stat-label">Total Clicks</span>
      </div>
      <div class="stat-card">
        <span class="stat-value">{ctr}%</span>
        <span class="stat-label">CTR</span>
      </div>
    </div>

    <div class="quick-actions">
      <h2>Quick Actions</h2>
      <div class="action-grid">
        <a href="/account/settings/promos/library/new" class="action-card">
          <span class="action-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </span>
          <span class="action-title">Create Promo</span>
          <span class="action-desc">Design a new ad creative</span>
        </a>
        <a href="/account/settings/promos/bookings/new" class="action-card">
          <span class="action-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          </span>
          <span class="action-title">Book a Slot</span>
          <span class="action-desc">Schedule an ad placement</span>
        </a>
        <a href="/account/settings/promos/library" class="action-card">
          <span class="action-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          </span>
          <span class="action-title">My Promos</span>
          <span class="action-desc">Manage your creatives</span>
        </a>
        <a href="/account/settings/promos/bookings" class="action-card">
          <span class="action-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          </span>
          <span class="action-title">My Bookings</span>
          <span class="action-desc">View booking history &amp; metrics</span>
        </a>
      </div>
    </div>
  </div>
</div>
{/if}

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    max-width: 900px;
    margin: 0 auto;
    padding: 1.5rem;
    padding-bottom: 2rem;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  h1 {
    margin: 0 0 1.5rem;
    font-size: 1.75rem;
    color: var(--text-color);
  }

  h2 {
    margin: 0 0 1rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 0.75rem;
    margin-bottom: 2rem;
  }

  .stat-card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.25rem 1rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .stat-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .quick-actions {
    margin-top: 0.5rem;
  }

  .action-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 0.75rem;
  }

  .action-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: 1.5rem 1rem;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    text-decoration: none;
    transition: border-color 0.15s, background 0.15s;
  }

  .action-card:hover {
    border-color: var(--accent-color);
    background: var(--hover-color);
  }

  .action-icon {
    font-size: 1.5rem;
    margin-bottom: 0.5rem;
  }

  .action-title {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-color);
  }

  .action-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
  }

  @media (max-width: 768px) {
    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .action-grid {
      grid-template-columns: 1fr;
    }
  }

  /* Landing page for logged-out users */

  .landing-container {
    max-width: 720px;
    margin: 0 auto;
    padding: 3rem 1.5rem;
    text-align: center;
  }

  .landing-container h1 {
    font-size: 2rem;
    margin: 0 0 1rem;
    color: var(--text-color);
  }

  .landing-subtitle {
    font-size: 1.05rem;
    color: var(--text-muted);
    line-height: 1.6;
    margin: 0 0 2.5rem;
  }

  .features-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 2.5rem;
    text-align: center;
  }

  .feature-card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem 1rem;
  }

  .feature-icon {
    display: inline-flex;
    color: var(--accent-color);
    margin-bottom: 0.75rem;
  }

  .feature-card h3 {
    font-size: 0.95rem;
    margin: 0 0 0.5rem;
    color: var(--text-color);
  }

  .feature-card p {
    font-size: 0.8rem;
    color: var(--text-muted);
    line-height: 1.5;
    margin: 0;
  }

  .login-cta {
    display: flex;
    justify-content: center;
  }

  .login-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1.5rem;
    background: #5865F2;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    text-decoration: none;
    transition: background 0.15s;
  }

  .login-btn:hover {
    background: #4752C4;
  }

  @media (max-width: 768px) {
    .features-grid {
      grid-template-columns: 1fr;
    }

    .landing-container {
      padding: 2rem 1rem;
    }
  }
</style>
