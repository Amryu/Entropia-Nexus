<script>
  //@ts-nocheck

  import { onMount, createEventDispatcher } from "svelte";


  export const dispatch = createEventDispatcher();

  /**
   * @typedef {Object} Props
   * @property {string} [text]
   * @property {any} element
   * @property {boolean} [show]
   * @property {any} [tooltipPos]
   */

  /** @type {Props} */
  let {
    text = '',
    element = $bindable(),
    show = false,
    tooltipPos = { x: 0, y: 0 }
  } = $props();

  onMount(()=>{
    if (typeof document === 'undefined') return;
		document.body.appendChild(element);
	})

  export {
  	text,
  	element,
  	show,
  	tooltipPos,
  }
</script>
<style>
  .tooltip {
    visibility: hidden;
    background-color: black;
    color: #fff;
    text-align: center;
    padding: 5px;
    border-radius: 6px;
    position: absolute;
    z-index: 10;
    pointer-events: none;
  }

  .show {
    visibility: visible;
  }
</style>

<div bind:this={element} class="tooltip" style="left: {tooltipPos.x}px; top: {tooltipPos.y}px;" class:show={show}>
  {@html text}
</div>