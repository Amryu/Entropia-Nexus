<script>
	//@ts-nocheck
	import { onMount, onDestroy, tick, createEventDispatcher } from 'svelte';

  import '$lib/style.css';

	// props
	export let items;
	export let itemHeight;
	export let viewport;
  export let contents;

	// read-only, but visible to consumers via bind:start
	export let start = 0;
	export let end = 0;
  
	// local state
	let viewport_height = 0;
	let visible;
	let mounted;

  let top = 0;
  let bottom = 0;

  $: if(contents) contents.style.paddingTop = `${top}px`;
  $: if(contents) contents.style.paddingBottom = `${bottom}px`;

  let resizeObserver;

  let dispatch = createEventDispatcher();
  
	$: visible = items.slice(start, end).map((data, i) => {
		return { index: i + start, data };
	});

  let handlersAttached = false;

  $: if(resizeObserver && viewport && !handlersAttached) {
    viewport.addEventListener('scroll', handle_scroll);
    resizeObserver.observe(viewport);
    handlersAttached = true;
  }

	// whenever `items` changes, invalidate the current heightmap
	$: if (mounted) refresh(items, viewport_height, itemHeight);

	async function refresh() {
    if (end > items.length) {
      viewport.scrollTop = 0;
    }

    await tick();

    handle_scroll();
	}

	async function handle_scroll() {
		const { scrollTop } = viewport;

		let i = 0;

		while (i < items.length) {
			if ((i + 1) * itemHeight >= scrollTop) {
				start = i;

				break;
			}

			i += 1;
		}

		while (i < items.length) {
			i += 1;

			if (i * itemHeight > scrollTop + viewport_height) break;
		}

		end = i;
	}

	$: top = start * itemHeight;
	$: bottom = (items.length - end) * itemHeight + (Math.max(viewport_height - start * itemHeight, end * itemHeight) - start * itemHeight);

	// trigger initial refresh
	onMount(() => {
    resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        if (entry.target === viewport) {
          viewport_height = viewport.offsetHeight;
        }
      }
    });

    mounted = true;
	});
  
  onDestroy(() => {
    if (resizeObserver) {
      resizeObserver.disconnect();
    }
  });
</script>

<style>
  tr {
    display: contents;
  }
</style>

{#if typeof window !== 'undefined'}
	{#each visible as row, rowIndex (row.index)}
	<tr on:click={() => dispatch('rowClick', row)} on:mouseover={() => dispatch('rowHover', row)} on:focus={() => dispatch('rowHover', row)} on:mouseout={() => dispatch('rowHover', null)} on:blur={() => dispatch('rowHover', null)} style={row.data.trStyle ?? ''}>
		<slot item={row.data} index={rowIndex + start}>Missing template</slot>
	</tr>
	{/each}
{:else}
	{#each items as item, i}
	<tr>
		<slot item={item} index={i}>Missing template</slot>
	</tr>
	{/each}
{/if}