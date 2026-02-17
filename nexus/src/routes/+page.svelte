<!--
  @component Home Page
  Dynamic landing page with EU news feed, upcoming events, content creators,
  feature highlights and community links.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';

  export let data;

  $: ({ news, events, creators } = data);

  const features = [
    { name: 'Items Database', href: '/items', icon: 'ITM', description: 'Weapons, armor, tools, materials, blueprints and more' },
    { name: 'Information Wiki', href: '/information', icon: 'INF', description: 'Professions, skills, mobs, vendors and mechanics' },
    { name: 'Interactive Maps', href: '/maps', icon: 'MAP', description: 'Planet maps with mob spawns and landmarks' },
    { name: 'Tools & Calculators', href: '/tools', icon: 'TLS', description: 'Loadout calculator, DPS analysis and planning' },
    { name: 'Market & Services', href: '/market', icon: 'MKT', description: 'Exchange, shops and player services' }
  ];

  const platformColors = {
    youtube: '#FF0000',
    twitch: '#9146FF',
    kick: '#53FC18'
  };

  const platformLabels = {
    youtube: 'YouTube',
    twitch: 'Twitch',
    kick: 'Kick'
  };

  function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

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
    return formatDate(dateStr);
  }

  function formatEventDate(dateStr) {
    const d = new Date(dateStr);
    return {
      month: d.toLocaleDateString('en-US', { month: 'short' }).toUpperCase(),
      day: d.getDate(),
      time: d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
    };
  }

  function getCreatorDisplayName(creator) {
    if (creator.cached_data?.channelName) return creator.cached_data.channelName;
    if (creator.cached_data?.displayName) return creator.cached_data.displayName;
    return creator.name;
  }

  function getCreatorAvatar(creator) {
    if (creator.cached_data?.channelAvatar) return creator.cached_data.channelAvatar;
    if (creator.cached_data?.avatar) return creator.cached_data.avatar;
    return creator.avatar_url;
  }
</script>

<svelte:head>
  <title>Entropia Nexus - Your Entropia Universe Resource</title>
  <meta name="description" content="Your comprehensive resource for Entropia Universe. News, events, items, mobs, maps, tools and more." />
  <meta name="keywords" content="Entropia Universe, Entropia, Entropia Nexus, EU, PE, Items, Mobs, Maps, Tools, MindArk, Wiki" />
  <link rel="canonical" href="https://entropianexus.com" />
</svelte:head>

<div class="home-page">
  <main class="home-content">
    <!-- Hero -->
    <section class="hero">
      <h1 class="hero-title">Entropia Nexus</h1>
      <p class="hero-subtitle">Your comprehensive resource for Entropia Universe</p>
    </section>

    <!-- News Feed -->
    {#if news && news.length > 0}
      <section class="section">
        <div class="section-header">
          <h2 class="section-title">Latest News</h2>
        </div>
        <div class="news-grid">
          {#each news as item}
            <a href={item.url || '#'} class="news-card" target={item.source === 'steam' || (item.source === 'nexus' && !item.has_content) ? '_blank' : undefined} rel={item.source === 'steam' || (item.source === 'nexus' && !item.has_content) ? 'noopener' : undefined}>
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
      </section>
    {/if}

    <!-- Upcoming Events -->
    {#if events && events.length > 0}
      <section class="section">
        <div class="section-header">
          <h2 class="section-title">Upcoming Events</h2>
          <a href="/events/submit" class="section-action">Submit Event</a>
        </div>
        <div class="events-list">
          {#each events as event}
            {@const ed = formatEventDate(event.start_date)}
            <div class="event-row">
              <div class="event-date-block">
                <span class="event-month">{ed.month}</span>
                <span class="event-day">{ed.day}</span>
              </div>
              <div class="event-info">
                <div class="event-title-row">
                  <h3 class="event-title">{event.title}</h3>
                  <span class="event-type-badge" class:official={event.type === 'official'}>
                    {event.type === 'official' ? 'Official' : 'Player Event'}
                  </span>
                </div>
                <div class="event-details">
                  <span class="event-time">{ed.time} UTC</span>
                  {#if event.location}
                    <span class="event-location">{event.location}</span>
                  {/if}
                </div>
              </div>
              {#if event.link}
                <a href={event.link} class="event-link" target="_blank" rel="noopener">Details</a>
              {/if}
            </div>
          {/each}
        </div>
      </section>
    {/if}

    <!-- Content Creators -->
    {#if creators && creators.length > 0}
      <section class="section">
        <div class="section-header">
          <h2 class="section-title">Content Creators</h2>
        </div>
        <div class="creators-grid">
          {#each creators as creator}
            <a href={creator.channel_url} class="creator-card" target="_blank" rel="noopener">
              <div class="creator-avatar">
                {#if getCreatorAvatar(creator)}
                  <img src={getCreatorAvatar(creator)} alt={getCreatorDisplayName(creator)} />
                {:else}
                  <div class="creator-avatar-placeholder">{creator.name.charAt(0).toUpperCase()}</div>
                {/if}
                {#if creator.platform === 'twitch' && creator.cached_data?.isLive}
                  <span class="live-badge">LIVE</span>
                {/if}
              </div>
              <div class="creator-info">
                <span class="creator-name">{getCreatorDisplayName(creator)}</span>
                <span class="creator-platform" style="color: {platformColors[creator.platform]}">
                  {platformLabels[creator.platform]}
                </span>
                {#if creator.platform === 'twitch' && creator.cached_data?.isLive}
                  <span class="creator-live-detail">{creator.cached_data.viewerCount} viewers — {creator.cached_data.gameName}</span>
                {:else if creator.platform === 'youtube' && creator.cached_data?.latestVideo}
                  <span class="creator-latest">Latest: {creator.cached_data.latestVideo.title}</span>
                {/if}
              </div>
            </a>
          {/each}
        </div>
      </section>
    {/if}

    <!-- Explore -->
    <section class="section">
      <div class="section-header">
        <h2 class="section-title">Explore</h2>
      </div>
      <div class="features-grid">
        {#each features as feature}
          <a href={feature.href} class="feature-card">
            <span class="feature-icon">{feature.icon}</span>
            <div class="feature-content">
              <h3 class="feature-name">{feature.name}</h3>
              <p class="feature-description">{feature.description}</p>
            </div>
            <span class="feature-arrow">&rarr;</span>
          </a>
        {/each}
      </div>
    </section>

    <!-- Community & About -->
    <section class="section two-col">
      <div class="info-card">
        <h2>Join Our Community</h2>
        <p>
          Connect with other players, get help, report issues, or suggest new features.
        </p>
        <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="discord-btn">
          <svg class="discord-icon" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
          </svg>
          Join Discord Server
        </a>
      </div>

      <div class="info-card">
        <h2>About &amp; Contribute</h2>
        <p>
          Entropia Nexus is a community-driven wiki and resource hub. Verified users can
          edit entries, submit corrections, and add new information.
        </p>
        <p>
          Support the site via
          <a href="https://ko-fi.com/C0C21JO3B1" target="_blank" rel="noopener" class="kofi-link">Ko-fi</a>
          or contact <strong>Pugnus Amryu Tonitrus</strong> in-game.
        </p>
      </div>
    </section>
  </main>

  <!-- Footer -->
  <footer class="site-footer">
    <div class="footer-content">
      <p class="footer-disclaimer">
        Entropia Nexus is a fan-made resource and is not affiliated with MindArk PE AB.
        Entropia Universe is a trademark of MindArk PE AB.
      </p>
      <div class="footer-links">
        <a href="/legal/terms">Terms of Service</a>
        <span class="footer-divider">|</span>
        <a href="/legal/privacy">Privacy Policy</a>
        <span class="footer-divider">|</span>
        <a href="/sitemap">Sitemap</a>
      </div>
      <p class="footer-copyright">&copy; 2024&ndash;2026 Entropia Nexus</p>
    </div>
  </footer>
</div>

<style>
  .home-page {
    display: flex;
    flex-direction: column;
    min-height: 100%;
    background-color: var(--primary-color);
    color: var(--text-color);
  }

  .home-content {
    flex: 1;
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px 24px 48px;
    width: 100%;
    box-sizing: border-box;
  }

  /* Hero */
  .hero {
    text-align: center;
    padding: 32px 0 40px;
  }

  .hero-title {
    margin: 0 0 12px 0;
    font-size: 2.25rem;
    font-weight: 600;
    color: var(--text-color);
    line-height: 1.2;
  }

  .hero-subtitle {
    margin: 0;
    font-size: 1.125rem;
    color: var(--text-muted);
  }

  /* Section common */
  .section {
    margin-bottom: 40px;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .section-title {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .section-action {
    font-size: 0.875rem;
    color: var(--accent-color);
    text-decoration: none;
  }

  .section-action:hover {
    text-decoration: underline;
  }

  /* News Grid */
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
    background-color: rgba(59, 130, 246, 0.15);
    color: var(--accent-color);
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

  /* Events */
  .events-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .event-row {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    transition: border-color 0.15s ease;
  }

  .event-row:hover {
    border-color: var(--accent-color);
  }

  .event-date-block {
    flex-shrink: 0;
    width: 52px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    line-height: 1;
  }

  .event-month {
    font-size: 0.6875rem;
    font-weight: 700;
    color: var(--accent-color);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .event-day {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .event-info {
    flex: 1;
    min-width: 0;
  }

  .event-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .event-title {
    margin: 0;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .event-type-badge {
    font-size: 0.6875rem;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    background-color: rgba(107, 114, 128, 0.15);
    color: var(--text-muted);
  }

  .event-type-badge.official {
    background-color: rgba(59, 130, 246, 0.15);
    color: var(--accent-color);
  }

  .event-details {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 4px;
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  .event-location::before {
    content: '\00B7';
    margin-right: 12px;
  }

  .event-link {
    flex-shrink: 0;
    font-size: 0.8125rem;
    color: var(--accent-color);
    text-decoration: none;
    padding: 4px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    transition: border-color 0.15s ease;
  }

  .event-link:hover {
    border-color: var(--accent-color);
  }

  /* Creators */
  .creators-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
  }

  .creator-card {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }

  .creator-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .creator-avatar {
    flex-shrink: 0;
    width: 52px;
    height: 52px;
    border-radius: 50%;
    overflow: hidden;
    position: relative;
  }

  .creator-avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .creator-avatar-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--primary-color);
    color: var(--text-muted);
    font-size: 1.25rem;
    font-weight: 700;
  }

  .live-badge {
    position: absolute;
    bottom: -2px;
    left: 50%;
    transform: translateX(-50%);
    background-color: #ef4444;
    color: white;
    font-size: 0.5625rem;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 3px;
    letter-spacing: 0.5px;
  }

  .creator-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .creator-name {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .creator-platform {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .creator-live-detail,
  .creator-latest {
    font-size: 0.75rem;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Features Grid */
  .features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 12px;
  }

  .feature-card {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }

  .feature-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .feature-icon {
    font-size: 0.875rem;
    font-weight: 700;
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--primary-color);
    border-radius: 8px;
    letter-spacing: 0.5px;
  }

  .feature-content {
    flex: 1;
    min-width: 0;
  }

  .feature-name {
    margin: 0 0 2px 0;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .feature-description {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--text-muted);
    line-height: 1.4;
  }

  .feature-arrow {
    font-size: 1.125rem;
    color: var(--text-muted);
    flex-shrink: 0;
    transition: transform 0.15s ease, color 0.15s ease;
  }

  .feature-card:hover .feature-arrow {
    transform: translateX(4px);
    color: var(--accent-color);
  }

  /* Two-column info cards */
  .two-col {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
  }

  .info-card {
    padding: 24px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .info-card h2 {
    margin: 0 0 12px 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .info-card p {
    margin: 0 0 12px 0;
    font-size: 0.875rem;
    line-height: 1.6;
    color: var(--text-muted);
  }

  .info-card p:last-of-type {
    margin-bottom: 0;
  }

  .info-card strong {
    color: var(--text-color);
  }

  .info-card a:not(.discord-btn) {
    color: var(--accent-color);
    text-decoration: none;
  }

  .info-card a:not(.discord-btn):hover {
    text-decoration: underline;
  }

  .kofi-link {
    color: #FF5E5B !important;
    font-weight: 500;
  }

  .discord-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 10px 18px;
    margin-top: 4px;
    background-color: #5865F2;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    text-decoration: none;
    transition: background-color 0.15s ease;
  }

  .discord-btn:hover {
    background-color: #4752C4;
  }

  .discord-icon {
    flex-shrink: 0;
  }

  /* Footer */
  .site-footer {
    background-color: var(--secondary-color);
    border-top: 1px solid var(--border-color);
    padding: 28px 24px;
  }

  .footer-content {
    max-width: 1200px;
    margin: 0 auto;
    text-align: center;
  }

  .footer-disclaimer {
    margin: 0 0 12px 0;
    font-size: 0.8125rem;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .footer-links {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .footer-links a {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 0.8125rem;
  }

  .footer-links a:hover {
    text-decoration: underline;
  }

  .footer-divider {
    color: var(--text-muted);
  }

  .footer-copyright {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  /* Responsive */
  @media (max-width: 899px) {
    .home-content {
      padding: 16px 16px 40px;
    }

    .hero {
      padding: 20px 0 28px;
    }

    .hero-title {
      font-size: 1.75rem;
    }

    .hero-subtitle {
      font-size: 1rem;
    }

    .news-grid {
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    }

    .features-grid {
      grid-template-columns: 1fr;
    }

    .creators-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 599px) {
    .news-grid {
      grid-template-columns: 1fr;
    }

    .event-row {
      flex-wrap: wrap;
      gap: 12px;
    }

    .event-link {
      margin-left: auto;
    }

    .discord-btn {
      width: 100%;
      justify-content: center;
    }

    .site-footer {
      padding: 20px 16px;
    }

    .footer-links {
      flex-wrap: wrap;
    }
  }
</style>
