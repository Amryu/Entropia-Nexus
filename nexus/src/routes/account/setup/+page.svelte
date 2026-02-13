<script>
  // @ts-nocheck
  import '$lib/style.css';
</script>

<svelte:head>
  <title>Verify Your Account | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="setup-card">
      <div class="header">
        <div class="icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
          </svg>
        </div>
        <h1>Verify Your Account</h1>
      </div>

      <p class="intro">
        A verified account allows you to contribute, manage your account, and access all features of the site including the marketplace, service listings, and more.
      </p>

      <div class="discord-box">
        <div class="discord-header">
          <img src="/discord.svg" alt="Discord" width="24" height="24" />
          <span>Join our Discord to start verification</span>
        </div>
        <a href="https://discord.gg/hBGKyJ6EDr" target="_blank" rel="noopener" class="discord-btn">
          Join Entropia Nexus Discord
        </a>
      </div>

      <div class="steps">
        <h2>Verification Steps</h2>

        <div class="step">
          <div class="step-number">1</div>
          <div class="step-content">
            <h3>Join the Discord Server</h3>
            <p>Join the Entropia Nexus Discord server using the button above.</p>
          </div>
        </div>

        <div class="step">
          <div class="step-number">2</div>
          <div class="step-content">
            <h3>Wait for Your Verification Thread</h3>
            <p>A private verification thread will be created for you on Discord.</p>
          </div>
        </div>

        <div class="step">
          <div class="step-number">3</div>
          <div class="step-content">
            <h3>Type Your Full EU Name</h3>
            <p>In the thread, enter your full Entropia Universe name exactly as it appears in-game and confirm it.</p>
          </div>
        </div>

        <div class="step">
          <div class="step-number">4</div>
          <div class="step-content">
            <h3>Wait for the In-Game Code</h3>
            <p>You will receive a verification code in Entropia Universe.</p>
          </div>
        </div>

        <div class="step">
          <div class="step-number">5</div>
          <div class="step-content">
            <h3>Complete Verification</h3>
            <p>Enter that code in your verification thread. Once verified, your account will have access to all Entropia Nexus features.</p>
          </div>
        </div>
      </div>

      <div class="help-box">
        <h3>Need Help?</h3>
        <p>If you have questions or run into issues during verification, ask in the <strong>#support</strong> channel on our Discord server.</p>
      </div>
    </div>
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
    background-color: var(--primary-color);
  }

  .page-container {
    max-width: 700px;
    margin: 0 auto;
    padding: 40px 20px;
  }

  .setup-card {
    background-color: var(--secondary-color);
    border-radius: 12px;
    padding: 40px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  }

  .header {
    text-align: center;
    margin-bottom: 24px;
  }

  .icon {
    color: var(--success-color, #10b981);
    margin-bottom: 16px;
  }

  h1 {
    font-size: 28px;
    color: var(--text-color);
    margin: 0;
  }

  .intro {
    text-align: center;
    color: var(--text-muted);
    font-size: 16px;
    line-height: 1.6;
    margin-bottom: 32px;
  }

  .discord-box {
    background-color: rgba(114, 137, 218, 0.1);
    border: 1px solid rgba(114, 137, 218, 0.3);
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    margin-bottom: 32px;
  }

  .discord-header {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--text-color);
    font-weight: 500;
    margin-bottom: 16px;
  }

  .discord-btn {
    display: inline-block;
    background-color: #7289DA;
    color: white;
    padding: 12px 24px;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 500;
    transition: background-color 0.2s;
  }

  .discord-btn:hover {
    background-color: #677bc4;
  }

  .steps {
    margin-bottom: 32px;
  }

  .steps h2 {
    font-size: 20px;
    color: var(--text-color);
    margin: 0 0 20px 0;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color);
  }

  .step {
    display: flex;
    gap: 16px;
    margin-bottom: 20px;
  }

  .step:last-child {
    margin-bottom: 0;
  }

  .step-number {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    background-color: var(--accent-color);
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 14px;
  }

  .step-content {
    flex: 1;
  }

  .step-content h3 {
    font-size: 16px;
    color: var(--text-color);
    margin: 0 0 6px 0;
  }

  .step-content p {
    font-size: 14px;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.5;
  }

  .help-box {
    background-color: var(--hover-color);
    border-radius: 8px;
    padding: 16px 20px;
  }

  .help-box h3 {
    font-size: 16px;
    color: var(--text-color);
    margin: 0 0 8px 0;
  }

  .help-box p {
    font-size: 14px;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.5;
  }
</style>
