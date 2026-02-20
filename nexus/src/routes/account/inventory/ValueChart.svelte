<script>
  export let data = []; // [{ imported_at, total_value, estimated_value, unknown_value, item_count }]

  const PADDING = { top: 20, right: 16, bottom: 30, left: 60 };
  const WIDTH = 600;
  const HEIGHT = 180;

  let hoveredIndex = null;
  let tooltipX = 0;
  let tooltipY = 0;

  $: chartWidth = WIDTH - PADDING.left - PADDING.right;
  $: chartHeight = HEIGHT - PADDING.top - PADDING.bottom;

  // Compute display total: estimated_value + unknown_value for modern imports, total_value for legacy
  function getDisplayTotal(d) {
    const est = d.estimated_value != null ? Number(d.estimated_value) : null;
    const tt = d.total_value != null ? Number(d.total_value) : 0;
    const unknown = d.unknown_value != null ? Number(d.unknown_value) : 0;
    return (est != null ? est : tt) + unknown;
  }

  $: values = data.map(d => getDisplayTotal(d));
  $: minVal = values.length > 0 ? Math.min(...values) : 0;
  $: maxVal = values.length > 0 ? Math.max(...values) : 100;
  $: valRange = maxVal - minVal || 1;

  $: points = data.map((d, i) => {
    const total = getDisplayTotal(d);
    const unknownVal = d.unknown_value != null ? Number(d.unknown_value) : 0;
    return {
      x: PADDING.left + (data.length > 1 ? (i / (data.length - 1)) * chartWidth : chartWidth / 2),
      y: PADDING.top + chartHeight - ((total - minVal) / valRange) * chartHeight,
      date: new Date(d.imported_at).toLocaleDateString(),
      value: total,
      unknownValue: unknownVal,
      items: d.item_count,
    };
  });

  $: linePath = points.length > 1
    ? 'M ' + points.map(p => `${p.x},${p.y}`).join(' L ')
    : '';

  $: areaPath = points.length > 1
    ? `M ${points[0].x},${PADDING.top + chartHeight} L ${linePath.slice(2)} L ${points[points.length - 1].x},${PADDING.top + chartHeight} Z`
    : '';

  // Y-axis ticks (5 ticks)
  $: yTicks = Array.from({ length: 5 }, (_, i) => {
    const val = minVal + (valRange * i) / 4;
    return {
      y: PADDING.top + chartHeight - (i / 4) * chartHeight,
      label: val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val.toFixed(0),
    };
  });

  function handleMouseMove(e) {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * WIDTH;

    // Find closest point
    let closest = 0;
    let minDist = Infinity;
    for (let i = 0; i < points.length; i++) {
      const dist = Math.abs(points[i].x - mouseX);
      if (dist < minDist) { minDist = dist; closest = i; }
    }
    hoveredIndex = closest;
    tooltipX = points[closest]?.x ?? 0;
    tooltipY = points[closest]?.y ?? 0;
  }

  function handleMouseLeave() {
    hoveredIndex = null;
  }
</script>

{#if data.length >= 2}
  <div class="chart-wrapper">
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <svg
      viewBox="0 0 {WIDTH} {HEIGHT}"
      preserveAspectRatio="xMidYMid meet"
      class="value-chart"
      on:mousemove={handleMouseMove}
      on:mouseleave={handleMouseLeave}
    >
      <!-- Grid lines -->
      {#each yTicks as tick}
        <line x1={PADDING.left} y1={tick.y} x2={WIDTH - PADDING.right} y2={tick.y} class="grid-line" />
        <text x={PADDING.left - 8} y={tick.y + 4} class="axis-label" text-anchor="end">{tick.label}</text>
      {/each}

      <!-- Area fill -->
      <path d={areaPath} class="chart-area" />

      <!-- Line -->
      <path d={linePath} class="chart-line" />

      <!-- Points -->
      {#each points as point, i}
        <circle
          cx={point.x} cy={point.y} r={hoveredIndex === i ? 4 : 2.5}
          class="chart-point"
          class:active={hoveredIndex === i}
        />
      {/each}

      <!-- Hover indicator -->
      {#if hoveredIndex != null && points[hoveredIndex]}
        <line
          x1={tooltipX} y1={PADDING.top}
          x2={tooltipX} y2={PADDING.top + chartHeight}
          class="hover-line"
        />
      {/if}

      <!-- Y axis label -->
      <text x={12} y={PADDING.top + chartHeight / 2} class="axis-title" text-anchor="middle" transform="rotate(-90 12 {PADDING.top + chartHeight / 2})">PED</text>
    </svg>

    {#if hoveredIndex != null && points[hoveredIndex]}
      <div class="chart-tooltip" style="left: {(tooltipX / WIDTH) * 100}%;">
        <strong>{points[hoveredIndex].value.toFixed(2)} PED</strong>
        <span>
          {points[hoveredIndex].date} &middot; {points[hoveredIndex].items} items
          {#if points[hoveredIndex].unknownValue > 0}
            &middot; {points[hoveredIndex].unknownValue.toFixed(2)} unknown
          {/if}
        </span>
      </div>
    {/if}
  </div>
{:else if data.length === 1}
  <p class="chart-single">Portfolio value: <strong>{getDisplayTotal(data[0]).toFixed(2)} PED</strong> ({data[0].item_count} items)</p>
{/if}

<style>
  .chart-wrapper {
    position: relative;
    width: 100%;
  }

  .value-chart {
    width: 100%;
    height: auto;
    display: block;
  }

  .grid-line {
    stroke: var(--border-color);
    stroke-width: 0.5;
    stroke-dasharray: 3 3;
  }

  .axis-label {
    font-size: 10px;
    fill: var(--text-muted);
  }

  .axis-title {
    font-size: 10px;
    fill: var(--text-muted);
  }

  .chart-area {
    fill: var(--accent-color);
    opacity: 0.1;
  }

  .chart-line {
    fill: none;
    stroke: var(--accent-color);
    stroke-width: 2;
    stroke-linejoin: round;
  }

  .chart-point {
    fill: var(--accent-color);
    stroke: var(--secondary-color);
    stroke-width: 1.5;
    transition: r 0.1s;
  }
  .chart-point.active {
    fill: var(--accent-color);
    stroke: white;
  }

  .hover-line {
    stroke: var(--text-muted);
    stroke-width: 0.5;
    stroke-dasharray: 2 2;
  }

  .chart-tooltip {
    position: absolute;
    top: -8px;
    transform: translateX(-50%);
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
    white-space: nowrap;
    pointer-events: none;
    z-index: 10;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .chart-tooltip span {
    color: var(--text-muted);
    font-size: 10px;
  }

  .chart-single {
    font-size: 0.85rem;
    color: var(--text-muted);
    text-align: center;
    padding: 0.5rem 0;
    margin: 0;
  }
</style>
