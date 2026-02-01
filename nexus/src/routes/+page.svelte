<!--
  @component Home Page
  Landing page for Entropia Nexus with feature highlights and community links.
-->
<script>
  import '$lib/style.css';

  // SvelteKit passes params to all pages - declare to avoid console warnings
  export let params = {};

  const features = [
    {
      name: 'Items Database',
      href: '/items',
      icon: '📦',
      description: 'Browse weapons, armor, tools, materials, blueprints and more'
    },
    {
      name: 'Information Wiki',
      href: '/information',
      icon: '📚',
      description: 'Professions, skills, mobs, vendors and game mechanics'
    },
    {
      name: 'Interactive Maps',
      href: '/maps',
      icon: '🗺️',
      description: 'Planet maps with mob spawns, resources and landmarks'
    },
    {
      name: 'Tools & Calculators',
      href: '/tools',
      icon: '🔧',
      description: 'Loadout calculator, DPS analysis and planning tools'
    },
    {
      name: 'Market & Services',
      href: '/market',
      icon: '💰',
      description: 'Exchange rates, shops and player services'
    }
  ];
</script>

<svelte:head>
  <title>Entropia Nexus - Your Entropia Universe Resource</title>
  <meta name="description" content="Your comprehensive resource for Entropia Universe. Look up items, mobs, maps or use our tools to make your life easier." />
  <meta name="keywords" content="Entropia Universe, Entropia, Entropia Nexus, EU, PE, Items, Mobs, Maps, Tools, MindArk, Wiki" />
  <link rel="canonical" href="https://entropianexus.com" />
</svelte:head>

<div class="home-page">
  <main class="home-content">
    <!-- Hero Section -->
    <section class="hero">
      <h1 class="hero-title">Welcome to Entropia Nexus</h1>
      <p class="hero-subtitle">
        Your comprehensive resource for Entropia Universe
      </p>
    </section>

    <!-- Features Grid -->
    <section class="features">
      <div class="features-grid">
        {#each features as feature}
          <a href={feature.href} class="feature-card">
            <span class="feature-icon">{feature.icon}</span>
            <div class="feature-content">
              <h2 class="feature-name">{feature.name}</h2>
              <p class="feature-description">{feature.description}</p>
            </div>
            <span class="feature-arrow">→</span>
          </a>
        {/each}
      </div>
    </section>

    <!-- About Section -->
    <section class="about-section">
      <div class="about-card">
        <h2>About This Site</h2>
        <p>
          Entropia Nexus is a community-driven wiki and resource hub for Entropia Universe.
          Our goal is to provide accurate, up-to-date information on items, creatures, skills,
          and everything else you need to succeed in the game.
        </p>
        <p>
          This site is a work in progress. If you notice something missing or incorrect,
          or have suggestions for improvements, please let us know!
        </p>
      </div>

      <div class="about-card">
        <h2>Contribute</h2>
        <p>
          Want to help improve Entropia Nexus? Verified users can edit wiki entries,
          submit corrections, and add new information. Join our community to get started.
        </p>
        <p>
          You can also support the site by donating via
          <a href="https://ko-fi.com/C0C21JO3B1" target="_blank" rel="noopener" class="kofi-link">Ko-fi</a>
          or contact <strong>Pugnus Amryu Tonitrus</strong> in-game.
          Donations help cover hosting costs and fund development of new features.
        </p>
      </div>
    </section>

    <!-- Community Section -->
    <section class="community-section">
      <div class="community-card">
        <div class="community-content">
          <h2>Join Our Community</h2>
          <p>
            Connect with other players, get help, report issues, or suggest new features.
          </p>
        </div>
        <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="discord-btn">
          <svg class="discord-icon" viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M20.317 4.37a19.791 19.791 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028 14.09 14.09 0 0 0 1.226-1.994.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128 10.2 10.2 0 0 0 .372-.292.074.074 0 0 1 .077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.01c.12.098.246.198.373.292a.077.077 0 0 1-.006.127 12.299 12.299 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 0 0-.031-.03zM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.956 2.418-2.157 2.418zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.096 2.157 2.42 0 1.333-.946 2.418-2.157 2.418z"/>
          </svg>
          Join Discord Server
        </a>
      </div>
    </section>
  </main>

  <!-- Footer -->
  <footer class="site-footer">
    <div class="footer-content">
      <div class="footer-section">
        <p class="footer-disclaimer">
          Entropia Nexus is a fan-made resource and is not affiliated with MindArk PE AB.
          Entropia Universe is a trademark of MindArk PE AB.
        </p>
      </div>
      <div class="footer-links">
        <a href="/legal/terms">Terms of Service</a>
        <span class="footer-divider">|</span>
        <a href="/legal/privacy">Privacy Policy</a>
        <span class="footer-divider">|</span>
        <a href="/sitemap">Sitemap</a>
      </div>
      <p class="footer-copyright">
        © 2024–2025 Entropia Nexus
      </p>
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
    max-width: 1000px;
    margin: 0 auto;
    padding: 32px 24px;
    width: 100%;
    box-sizing: border-box;
  }

  /* Hero Section */
  .hero {
    text-align: center;
    padding: 40px 0 48px;
  }

  .hero-title {
    margin: 0 0 16px 0;
    font-size: 2.5rem;
    font-weight: 600;
    color: var(--text-color);
    line-height: 1.2;
  }

  .hero-subtitle {
    margin: 0;
    font-size: 1.25rem;
    color: var(--text-muted);
    line-height: 1.5;
  }

  /* Features Grid */
  .features {
    margin-bottom: 48px;
  }

  .features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
  }

  .feature-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.2s ease, background-color 0.2s ease;
  }

  .feature-card:hover {
    border-color: var(--accent-color);
    background-color: var(--hover-color);
  }

  .feature-icon {
    font-size: 1.75rem;
    flex-shrink: 0;
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--primary-color);
    border-radius: 8px;
  }

  .feature-content {
    flex: 1;
    min-width: 0;
  }

  .feature-name {
    margin: 0 0 4px 0;
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .feature-description {
    margin: 0;
    font-size: 0.875rem;
    color: var(--text-muted);
    line-height: 1.4;
  }

  .feature-arrow {
    font-size: 1.25rem;
    color: var(--text-muted);
    flex-shrink: 0;
    transition: transform 0.2s ease, color 0.2s ease;
  }

  .feature-card:hover .feature-arrow {
    transform: translateX(4px);
    color: var(--accent-color);
  }

  /* About Section */
  .about-section {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
    margin-bottom: 48px;
  }

  .about-card {
    padding: 24px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .about-card h2 {
    margin: 0 0 16px 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .about-card p {
    margin: 0 0 12px 0;
    font-size: 0.9375rem;
    line-height: 1.6;
    color: var(--text-muted);
  }

  .about-card p:last-child {
    margin-bottom: 0;
  }

  .about-card strong {
    color: var(--text-color);
  }

  .about-card a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .about-card a:hover {
    text-decoration: underline;
  }

  .kofi-link {
    color: #FF5E5B;
    font-weight: 500;
  }

  /* Community Section */
  .community-section {
    margin-bottom: 48px;
  }

  .community-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 24px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }

  .community-content h2 {
    margin: 0 0 8px 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .community-content p {
    margin: 0;
    font-size: 0.9375rem;
    color: var(--text-muted);
  }

  .discord-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 12px 20px;
    background-color: #5865F2;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 0.9375rem;
    font-weight: 500;
    text-decoration: none;
    transition: background-color 0.2s ease;
    flex-shrink: 0;
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
    padding: 32px 24px;
  }

  .footer-content {
    max-width: 1000px;
    margin: 0 auto;
    text-align: center;
  }

  .footer-section {
    margin-bottom: 16px;
  }

  .footer-disclaimer {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .footer-links {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 16px;
  }

  .footer-links a {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 0.875rem;
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

  /* Mobile Responsive */
  @media (max-width: 899px) {
    .home-content {
      padding: 24px 16px;
    }

    .hero {
      padding: 24px 0 32px;
    }

    .hero-title {
      font-size: 1.75rem;
    }

    .hero-subtitle {
      font-size: 1rem;
    }

    .features-grid {
      grid-template-columns: 1fr;
    }

    .feature-card {
      padding: 16px;
    }

    .feature-icon {
      font-size: 1.5rem;
      width: 40px;
      height: 40px;
    }

    .feature-name {
      font-size: 1rem;
    }

    .about-section {
      grid-template-columns: 1fr;
    }

    .about-card {
      padding: 20px;
    }

    .about-card h2 {
      font-size: 1.1rem;
    }

    .community-card {
      flex-direction: column;
      text-align: center;
      padding: 20px;
    }

    .discord-btn {
      width: 100%;
      justify-content: center;
    }

    .site-footer {
      padding: 24px 16px;
    }

    .footer-links {
      flex-wrap: wrap;
    }
  }
</style>
