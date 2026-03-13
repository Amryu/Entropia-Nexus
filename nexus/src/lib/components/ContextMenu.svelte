<script>
  //@ts-nocheck
  import { onMount } from 'svelte';



  /**
   * @typedef {Object} Props
   * @property {any} [menu]
   * @property {any} element
   * @property {any} [payload]
   * @property {boolean} [visible]
   * @property {any} [contextMenuPos]
   */

  /** @type {Props} */
  let {
    menu = [],
    element = $bindable(),
    payload = null,
    visible = $bindable(false),
    contextMenuPos = { x: 0, y: 0 }
  } = $props();

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

  export {
  	menu,
  	element,
  	payload,
  	visible,
  	contextMenuPos,
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
    background-color: var(--table-row-color-alt);
    width: 100%;
    color: var(--text-color);
    text-align: left;
  }

  .context-menu button:hover {
    background-color: var(--hover-color) !important;
  }

  .show {
    visibility: visible;
  }
</style>

<svelte:body onmousedown={handleMouseDownOutside} />
<div bind:this={element} class="context-menu" style="left: {contextMenuPos.x}px; top: {contextMenuPos.y}px;" class:show={visible}>
  {#each menu as item}
    <button onclick={() => { visible = false; item.action(payload, contextMenuPos); }}>{item.label}</button>
  {/each}
</div>