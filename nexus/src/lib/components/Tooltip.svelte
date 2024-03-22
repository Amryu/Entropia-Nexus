<script>
  //@ts-nocheck

  import { onMount, createEventDispatcher } from "svelte";

  export let text = '';

  export const dispatch = createEventDispatcher();

  export let element;
  export let show = false;
  export let tooltipPos = { x: 0, y: 0 };

  onMount(()=>{
    if (typeof document === 'undefined') return;
		document.body.appendChild(element);
	})
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

<svelte:options accessors={true} />
<div bind:this={element} class="tooltip" style="left: {tooltipPos.x}px; top: {tooltipPos.y}px;" class:show={show}>
  {@html text}
</div>