<script>
  //@ts-nocheck
  import { onMount } from 'svelte';

  export let menu = [];

  export let element;

  export let payload = null;
  export let visible = false;
  export let contextMenuPos = { x: 0, y: 0 };

  onMount(() => {
    if (typeof document === 'undefined') return;
		document.body.appendChild(element);
	});

  function handleMouseDownOutside(event) {
    if (visible === false) return;

    let targetElement = event.target; // clicked element
    do {
      if (targetElement === element) {
        // This is a click inside the context menu, do nothing
        return;
      }
      // Go up the DOM
      targetElement = targetElement.parentNode;
    } while (targetElement);

    // This is a click outside the context menu, hide it
    visible = false;
  }
</script>

<style>
  .context-menu {
    visibility: hidden;
    background-color: black;
    color: #fff;
    text-align: center;
    border-radius: 6px;
    position: absolute;
    z-index: 2;
    overflow: hidden;
  }

  .context-menu button {
    margin: 0;
    padding: 6px;
    display: block;
    background: none; /* Remove default background */
    border: none; /* Remove default border */
    font: inherit; /* Inherit font from parent */
    color: inherit; /* Inherit text color from parent */
    cursor: pointer;
    background-color: #f0f0f0;
    width: 100%;
    color: black;
    text-align: left;
  }

  .context-menu button:hover {
    background-color: #888888;
  }

  .show {
    visibility: visible;
  }
</style>

<svelte:options accessors={true} />
<svelte:body on:mousedown={handleMouseDownOutside} />
<div bind:this={element} class="context-menu" style="left: {contextMenuPos.x}px; top: {contextMenuPos.y}px;" class:show={visible}>
  {#each menu as item}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <button on:click={() => { visible = false; item.action(payload, contextMenuPos); }}>{item.label}</button>
  {/each}
</div>