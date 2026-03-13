<script>
	import { run } from 'svelte/legacy';

	//@ts-nocheck
	import { onMount, onDestroy, tick, createEventDispatcher } from 'svelte';

  import '$lib/style.css';

	

	
	/**
	 * @typedef {Object} Props
	 * @property {any} items - props
	 * @property {any} itemHeight
	 * @property {any} viewport
	 * @property {any} contents
	 * @property {number} [start] - read-only, but visible to consumers via bind:start
	 * @property {number} [end]
	 * @property {import('svelte').Snippet<[any]>} [children]
	 */

	/** @type {Props} */
	let {
		items,
		itemHeight,
		viewport = $bindable(),
		contents = $bindable(),
		start = $bindable(0),
		end = $bindable(0),
		children
	} = $props();
  
	// local state
	let viewport_height = $state(0);
	let visible = $derived(items.slice(start, end).map((data, i) => {
		return { index: i + start, data };
	}));
	let mounted = $state();

  let top = $state(0);
  let bottom = $state(0);


  let resizeObserver = $state();

  let dispatch = createEventDispatcher();
  

  let handlersAttached = $state(false);



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
	run(() => {
		top = start * itemHeight;
	});
  run(() => {
		if(contents) contents.style.paddingTop = `${top}px`;
	});
	run(() => {
		bottom = (items.length - end) * itemHeight + (Math.max(viewport_height - start * itemHeight, end * itemHeight) - start * itemHeight);
	});
  run(() => {
		if(contents) contents.style.paddingBottom = `${bottom}px`;
	});
	
  run(() => {
		if(resizeObserver && viewport && !handlersAttached) {
	    viewport.addEventListener('scroll', handle_scroll);
	    resizeObserver.observe(viewport);
	    handlersAttached = true;
	  }
	});
	// whenever `items` changes, invalidate the current heightmap
	run(() => {
		if (mounted) refresh(items, viewport_height, itemHeight);
	});
</script>

<style>
  tr {
    display: contents;
  }
</style>

{#if typeof window !== 'undefined'}
	{#each visible as row, rowIndex (row.index)}
	<tr onclick={() => dispatch('rowClick', row)} onmouseover={() => dispatch('rowHover', row)} onfocus={() => dispatch('rowHover', row)} onmouseout={() => dispatch('rowHover', null)} onblur={() => dispatch('rowHover', null)} style={row.data.trStyle ?? ''}>
		{@render children?.({ item: row.data, index: rowIndex + start, })}
	</tr>
	{/each}
{:else}
	{#each items as item, i}
	<tr>
		{@render children?.({ item, index: i, })}
	</tr>
	{/each}
{/if}