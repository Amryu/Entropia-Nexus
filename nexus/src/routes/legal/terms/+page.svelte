<!--
  @component Terms of Service Page
  Legal terms and conditions for using Entropia Nexus.
-->
<script>
  import '$lib/style.css';

  const lastUpdated = 'January 31, 2025';
</script>

<svelte:head>
  <title>Terms of Service - Entropia Nexus</title>
  <meta name="description" content="Terms of Service for Entropia Nexus - a community-driven wiki for Entropia Universe." />
  <link rel="canonical" href="https://entropianexus.com/legal/terms" />
</svelte:head>

<div class="legal-page">
  <div class="legal-container">
    <header class="legal-header">
      <h1>Terms of Service</h1>
      <p class="last-updated">Last updated: {lastUpdated}</p>
    </header>

    <article class="legal-content">
      <p class="intro">
        By accessing or using this website (the "Service"), you agree to these Terms of Service ("Terms").
        If you do not agree, do not use the Service.
      </p>

      <section class="legal-section">
        <h2>1. Nature of the Service</h2>
        <p>
          This website is a community-driven wiki where users may contribute factual information and advertise
          or search for in-game services. All content is provided by users unless explicitly stated otherwise.
        </p>
      </section>

      <section class="legal-section">
        <h2>2. User Accounts</h2>
        <p>
          Authentication is handled via Discord. We do not store user email addresses or passwords.
        </p>
        <p>
          Access to the Service may be suspended or terminated at any time, with or without notice, for any
          reason, including violations of these Terms or misuse of the Service.
        </p>
      </section>

      <section class="legal-section">
        <h2>3. User-Contributed Content</h2>
        <p>
          Users are responsible for the content they submit.
        </p>
        <p>
          By submitting content, you grant the website a non-exclusive, royalty-free right to use, modify,
          display, and remove that content as necessary to operate the Service.
        </p>
        <p>
          We reserve the right to edit, remove, or reject any content at our sole discretion.
        </p>
      </section>

      <section class="legal-section">
        <h2>4. Intellectual Property and Game Content</h2>
        <p>
          This website displays content from Entropia Universe, including but not limited to: item names,
          descriptions, and images; creature/mob names and statistics; NPC names and dialogue; mission text
          and objectives; skill and profession information; and other in-game data.
        </p>
        <p>
          Entropia Universe and all related content, trademarks, and intellectual property are owned by
          MindArk PE AB. This website is a fan-made resource operated under principles of fair use for
          informational, educational, and commentary purposes. We do not claim ownership of any MindArk
          intellectual property.
        </p>
        <p>
          Users who upload or submit content must ensure they have the right to share such content or that
          its use qualifies as fair use. Do not upload copyrighted content from sources other than Entropia
          Universe without proper authorization.
        </p>
      </section>

      <section class="legal-section">
        <h2>5. Content Removal Requests (DMCA)</h2>
        <p>
          If you are a rights holder and believe content on this website infringes your intellectual property,
          please contact us through our Discord server with:
        </p>
        <ul>
          <li>Identification of the copyrighted work</li>
          <li>Location of the allegedly infringing content</li>
          <li>Your contact information</li>
          <li>A statement of good faith belief that the use is not authorized</li>
        </ul>
        <p>
          We will respond to valid removal requests in a timely manner.
        </p>
      </section>

      <section class="legal-section">
        <h2>6. Accuracy Disclaimer</h2>
        <p>
          Content on this website is community-contributed and may be incomplete, outdated, or incorrect.
          No guarantees are made regarding accuracy or reliability.
        </p>
        <p>
          Use of any information on this website is at your own risk.
        </p>
      </section>

      <section class="legal-section">
        <h2>7. In-Game Services and Advertisements</h2>
        <p>
          The website may allow users to advertise or search for in-game services.
        </p>
        <p>
          The website is not a party to any agreement, transaction, or interaction between users. We do not
          verify, endorse, or guarantee any services offered by users and are not responsible for disputes,
          losses, or damages resulting from such interactions.
        </p>
      </section>

      <section class="legal-section">
        <h2>8. Acceptable Use</h2>
        <p>You agree not to:</p>
        <ul>
          <li>Post false, misleading, or deceptive content</li>
          <li>Advertise scams or engage in fraudulent behavior</li>
          <li>Impersonate others</li>
          <li>Upload illegal or infringing content</li>
          <li>Abuse, disrupt, or attempt to exploit the Service</li>
        </ul>
      </section>

      <section class="legal-section">
        <h2>9. Termination</h2>
        <p>
          We may suspend or terminate access to the Service at any time, with or without notice. Content
          associated with terminated accounts may be removed.
        </p>
      </section>

      <section class="legal-section">
        <h2>10. Limitation of Liability</h2>
        <p>
          The Service is provided "as is" and "as available." To the maximum extent permitted by law, we
          disclaim all liability for damages arising from use of the Service.
        </p>
      </section>

      <section class="legal-section">
        <h2>11. Changes to These Terms</h2>
        <p>
          These Terms may be updated at any time. Continued use of the Service after changes constitutes
          acceptance of the updated Terms.
        </p>
      </section>
    </article>

    <nav class="legal-nav">
      <a href="/" class="back-link">← Back to Home</a>
      <a href="/legal/privacy" class="nav-link">Privacy Policy →</a>
    </nav>
  </div>
</div>

<style>
  .legal-page {
    min-height: 100%;
    background-color: var(--primary-color);
    color: var(--text-color);
    padding: 32px 24px;
    box-sizing: border-box;
  }

  .legal-container {
    max-width: 800px;
    margin: 0 auto;
  }

  .legal-header {
    margin-bottom: 32px;
  }

  .legal-header h1 {
    margin: 0 0 8px 0;
    font-size: 2rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .last-updated {
    margin: 0;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .legal-content {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 32px;
    margin-bottom: 24px;
  }

  .intro {
    font-size: 1rem;
    line-height: 1.6;
    color: var(--text-color);
    margin: 0 0 32px 0;
    padding-bottom: 24px;
    border-bottom: 1px solid var(--border-color);
  }

  .legal-section {
    margin-bottom: 28px;
  }

  .legal-section:last-child {
    margin-bottom: 0;
  }

  .legal-section h2 {
    margin: 0 0 12px 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .legal-section p {
    margin: 0 0 12px 0;
    font-size: 0.9375rem;
    line-height: 1.7;
    color: var(--text-muted);
  }

  .legal-section p:last-child {
    margin-bottom: 0;
  }

  .legal-section ul {
    margin: 0;
    padding-left: 24px;
    color: var(--text-muted);
  }

  .legal-section li {
    margin-bottom: 8px;
    font-size: 0.9375rem;
    line-height: 1.6;
  }

  .legal-section li:last-child {
    margin-bottom: 0;
  }

  .legal-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }

  .back-link,
  .nav-link {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 0.9375rem;
  }

  .back-link:hover,
  .nav-link:hover {
    text-decoration: underline;
  }

  /* Mobile Responsive */
  @media (max-width: 899px) {
    .legal-page {
      padding: 24px 16px;
    }

    .legal-header h1 {
      font-size: 1.5rem;
    }

    .legal-content {
      padding: 24px 20px;
    }

    .legal-section h2 {
      font-size: 1rem;
    }

    .legal-section p,
    .legal-section li {
      font-size: 0.875rem;
    }

    .legal-nav {
      flex-direction: column;
      gap: 12px;
      text-align: center;
    }
  }
</style>
