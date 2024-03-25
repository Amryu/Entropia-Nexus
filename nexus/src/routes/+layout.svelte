<script>
  import '$lib/style.css';

  import { darkMode } from '../stores.js';

  import Menu from "$lib/components/Menu.svelte";
  import { onMount, onDestroy } from 'svelte';

  let darkModeValue;

  const unsubscribe = darkMode.subscribe(value => {
    darkModeValue = value;
    updateDarkMode();
  });

  onMount(() => {
    updateDarkMode();
    
    if (typeof window !== 'undefined') {
      darkMode.set(localStorage.getItem('darkMode') === 'true');
    }
  });

  function updateDarkMode() {
    if (typeof window === 'undefined') return;

    if (darkModeValue === true) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  }

  // Remember to unsubscribe when the component is destroyed
  onDestroy(() => {
    unsubscribe();
  });
</script>
<style global>
:global(html), :global(body) {
  height: 100%;
  margin: 0;
  padding: 0;
  font-family: 'Gill Sans', 'Gill Sans MT', Calibri, 'Trebuchet MS', sans-serif;
  overflow: hidden;
  color: var(--text-color);
  background-color: var(--primary-color);
}

:global(a) {
  text-decoration: none;
  color: var(--text-color);
}

:global(a:visited) {
  text-decoration: none;
  color: var(--text-color);
}
</style>

<Menu />
<slot></slot>