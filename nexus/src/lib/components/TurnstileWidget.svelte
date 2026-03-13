<!--
  @component TurnstileWidget
  Cloudflare Turnstile captcha widget.
  Loads the Turnstile script dynamically and renders the challenge.
  Calls onverified({ token }) on success.
  Calls onerror() on failure.
-->
<script>
  import { onMount, onDestroy } from 'svelte';
  import { browser } from '$app/environment';



  

  

  
  /**
   * @typedef {Object} Props
   * @property {string} [siteKey]
   * @property {'auto'|'light'|'dark'} [theme]
   * @property {string|null} [token]
   * @property {boolean} [reset]
   * @property {(detail: { token: string }) => void} [onverified]
   * @property {() => void} [onerror]
   * @property {() => void} [onexpired]
   */

  /** @type {Props} */
  let {
    siteKey = '',
    theme = 'auto',
    token = $bindable(null),
    reset = $bindable(false),
    onverified = undefined,
    onerror = undefined,
    onexpired = undefined
  } = $props();

  let container = $state();
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
        onverified?.({ token: t });
      },
      'error-callback': () => {
        token = null;
        onerror?.();
      },
      'expired-callback': () => {
        token = null;
        onexpired?.();
      }
    });
  }

  function resetWidget() {
    if (widgetId !== null && window.turnstile) {
      window.turnstile.reset(widgetId);
      token = null;
    }
  }

  $effect(() => {
    if (reset && browser) {
      resetWidget();
      reset = false;
    }
  });

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
