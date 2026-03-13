<script>
	//@ts-nocheck
	import { onMount, onDestroy, tick, untrack } from 'svelte';

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
		children,
		onrowClick = undefined,
		onrowHover = undefined
	} = $props();
  
	// local state
	let viewport_height = $state(0);
	let visible = $derived(items.slice(start, end).map((data, i) => {
		return { index: i + start, data };
	}));
	let mounted = $state();

  let top = $derived(start * itemHeight);
  let bottom = $derived((items.length - end) * itemHeight + (Math.max(viewport_height - start * itemHeight, end * itemHeight) - start * itemHeight));


  let resizeObserver = $state();


  let handlersAttached = false;



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
  $effect(() => {
		if(contents) contents.style.paddingTop = `${top}px`;
	});
  $effect(() => {
		if(contents) contents.style.paddingBottom = `${bottom}px`;
	});

  $effect(() => {
		if(resizeObserver && viewport && !untrack(() => handlersAttached)) {
	    viewport.addEventListener('scroll', handle_scroll);
	    resizeObserver.observe(viewport);
	    handlersAttached = true;
	  }
	});
	// whenever `items` changes, invalidate the current heightmap
	$effect(() => {
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
	<tr onclick={() => onrowClick?.(row)} onmouseover={() => onrowHover?.(row)} onfocus={() => onrowHover?.(row)} onmouseout={() => onrowHover?.(null)} onblur={() => onrowHover?.(null)} style={row.data.trStyle ?? ''}>
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