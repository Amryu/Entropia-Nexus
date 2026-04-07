<!--
  @component Privacy Policy Page
  Privacy policy explaining data collection and handling practices.
-->
<script>
  import '$lib/style.css';

  import { resetConsent } from '$lib/stores/consent.svelte.js';

  const lastUpdated = 'April 7, 2026';
</script>

<svelte:head>
  <title>Privacy Policy - Entropia Nexus</title>
  <meta name="description" content="Privacy Policy for Entropia Nexus - how we collect, use, and handle your information." />
  <link rel="canonical" href="https://entropianexus.com/legal/privacy" />
</svelte:head>

<div class="legal-page">
  <div class="legal-container">
    <header class="legal-header">
      <h1>Privacy Policy</h1>
      <p class="last-updated">Last updated: {lastUpdated}</p>
    </header>

    <article class="legal-content">
      <p class="intro">
        This Privacy Policy explains how this website (the "Service") collects, uses, and handles
        information when you use the Service.
      </p>

      <section class="legal-section">
        <h2>1. Information We Collect</h2>

        <h3>1.1 Information from Discord</h3>
        <p>
          When you log in using Discord, we receive limited account information from Discord, such as:
        </p>
        <ul>
          <li>Your Discord user ID</li>
          <li>Your Discord username and discriminator</li>
          <li>Your avatar (if provided by Discord)</li>
        </ul>
        <p>
          We do not receive or store your email address or Discord password.
          Authentication and account security are handled entirely by Discord.
        </p>

        <h3>1.2 Automatically Collected Information</h3>
        <p>
          When you access the Service, we may automatically collect basic technical information, such as:
        </p>
        <ul>
          <li>IP address</li>
          <li>Browser type</li>
          <li>Device information</li>
          <li>Access timestamps</li>
        </ul>
        <p>
          This data is used for basic operation, security, and abuse prevention.
        </p>

        <h3>1.3 Cookies</h3>
        <p>
          The Service uses cookies or similar technologies for:
        </p>
        <ul>
          <li><strong>Essential cookies:</strong> Login/session functionality and basic site operation. These are always active.</li>
          <li><strong>Advertising cookies:</strong> If you consent, Google AdSense may set cookies for ad personalization and measurement. No advertising cookies are set without your explicit consent.</li>
        </ul>
        <p>
          When you first visit the site, a consent banner allows you to choose whether to allow advertising cookies.
          You can change your preferences at any time by clicking the button below.
        </p>
        <p>
          <button class="change-preferences-btn" onclick={resetConsent}>Change Cookie Preferences</button>
        </p>
      </section>

      <section class="legal-section">
        <h2>2. How We Use Information</h2>
        <p>We use collected information to:</p>
        <ul>
          <li>Operate and maintain the Service</li>
          <li>Authenticate users via Discord</li>
          <li>Prevent abuse, spam, or misuse</li>
          <li>Moderate content and enforce Terms of Service</li>
        </ul>
        <p>
          We do not sell or rent user data.
        </p>
      </section>

      <section class="legal-section">
        <h2>3. User-Contributed Content</h2>
        <p>
          Content you submit to the Service (such as wiki edits or advertisements) is publicly visible by default.
        </p>
        <p>
          Do not submit personal information you do not wish to make public.
        </p>
      </section>

      <section class="legal-section">
        <h2>4. Data Sharing</h2>
        <p>We do not share personal data with third parties except:</p>
        <ul>
          <li>As required to operate the Service (e.g., Discord authentication)</li>
          <li>When required by law or legal process</li>
          <li>To protect the security or integrity of the Service</li>
        </ul>
      </section>

      <section class="legal-section">
        <h2>5. Data Retention</h2>
        <p>
          We retain information only as long as necessary to operate the Service or enforce our policies.
        </p>
        <p>
          You may request deletion of your account-related data, subject to reasonable limitations
          (such as retaining logs for security or legal reasons).
        </p>
      </section>

      <section class="legal-section">
        <h2>6. Third-Party Services</h2>
        <p>
          The Service relies on Discord for authentication. Use of Discord is subject to Discord's own
          Privacy Policy and Terms of Service.
        </p>
        <p>
          If you consent to advertising cookies, the Service uses Google AdSense to display advertisements.
          Google may collect data and use cookies for ad personalization and performance measurement,
          subject to <a href="https://policies.google.com/privacy" target="_blank" rel="noopener">Google's Privacy Policy</a>.
          You may manage Google's ad personalization at <a href="https://adssettings.google.com" target="_blank" rel="noopener">Google Ad Settings</a>.
        </p>
        <p>
          We are not responsible for the privacy practices of third-party services.
        </p>
      </section>

      <section class="legal-section">
        <h2>7. Children's Privacy</h2>
        <p>
          The Service is not intended for children under the age of 13. We do not knowingly collect
          personal data from children.
        </p>
      </section>

      <section class="legal-section">
        <h2>8. Changes to This Policy</h2>
        <p>
          This Privacy Policy may be updated from time to time. Continued use of the Service after
          changes constitutes acceptance of the updated policy.
        </p>
      </section>

      <section class="legal-section">
        <h2>9. Contact</h2>
        <p>
          If you have questions or requests regarding this Privacy Policy, you may contact the site
          administrators through the provided contact method or associated
          <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener">Discord server</a>.
        </p>
      </section>
    </article>

    <nav class="legal-nav">
      <a href="/" class="back-link">← Back to Home</a>
      <a href="/legal/terms" class="nav-link">← Terms of Service</a>
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
    margin: 0 0 16px 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .legal-section h3 {
    margin: 16px 0 8px 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .legal-section h3:first-child {
    margin-top: 0;
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
    margin: 0 0 12px 0;
    padding-left: 24px;
    color: var(--text-muted);
  }

  .legal-section ul:last-child {
    margin-bottom: 0;
  }

  .legal-section li {
    margin-bottom: 6px;
    font-size: 0.9375rem;
    line-height: 1.6;
  }

  .legal-section li:last-child {
    margin-bottom: 0;
  }

  .legal-section a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .legal-section a:hover {
    text-decoration: underline;
  }

  .change-preferences-btn {
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 0.8125rem;
    font-weight: 600;
    border: 1px solid var(--border-color);
    background: var(--hover-color);
    color: var(--text-color);
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
  }

  .change-preferences-btn:hover {
    background: var(--border-color);
    border-color: var(--accent-color);
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

    .legal-section h3 {
      font-size: 0.9375rem;
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
