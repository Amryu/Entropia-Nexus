<!--
  @component TurnstileWidget
  Cloudflare Turnstile captcha widget.
  Loads the Turnstile script dynamically and renders the challenge.
  Dispatches 'verified' event with the token on success.
  Dispatches 'error' event on failure.
-->
<script>
  import { createEventDispatcher, onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';

  const dispatch = createEventDispatcher();

  /** @type {string} Turnstile site key */
  export let siteKey = '';

  /** @type {'auto'|'light'|'dark'} Theme */
  export let theme = 'auto';

  /** @type {string|null} Current token (null if not verified) */
  export let token = null;

  /** @type {boolean} Whether to reset the widget (bind and set true to trigger) */
  export let reset = false;

  let container;
  let widgetId = null;
  let scriptLoaded = false;

  function loadScript() {
    if (!browser) return;
    if (document.querySelector('script[src*="turnstile"]')) {
      scriptLoaded = true;
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      scriptLoaded = true;
      renderWidget();
    };
    document.head.appendChild(script);
  }

  function renderWidget() {
    if (!browser || !scriptLoaded || !container || !window.turnstile || !siteKey) return;

    // Clean up existing widget
    if (widgetId !== null) {
      try { window.turnstile.remove(widgetId); } catch {}
      widgetId = null;
    }

    widgetId = window.turnstile.render(container, {
      sitekey: siteKey,
      theme,
      callback: (t) => {
        token = t;
        dispatch('verified', { token: t });
      },
      'error-callback': () => {
        token = null;
        dispatch('error');
      },
      'expired-callback': () => {
        token = null;
        dispatch('expired');
      }
    });
  }

  function resetWidget() {
    if (widgetId !== null && window.turnstile) {
      window.turnstile.reset(widgetId);
      token = null;
    }
  }

  $: if (reset && browser) {
    resetWidget();
    reset = false;
  }

  onMount(() => {
    if (!siteKey) return;
    if (window.turnstile) {
      scriptLoaded = true;
      renderWidget();
    } else {
      loadScript();
    }
  });

  onDestroy(() => {
    if (browser && widgetId !== null && window.turnstile) {
      try { window.turnstile.remove(widgetId); } catch {}
    }
  });
</script>

<div class="turnstile-container" bind:this={container}></div>

<style>
  .turnstile-container {
    display: flex;
    justify-content: center;
    min-height: 65px;
  }
</style>
