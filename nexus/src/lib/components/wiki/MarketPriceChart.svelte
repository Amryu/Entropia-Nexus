<!--
  @component MarketPriceChart
  Time-series line chart for market price snapshot history.
  Shows either markup (%) or sales (count) over time for a selected period.
-->
<script>
  import { run } from 'svelte/legacy';

  //@ts-nocheck
  import { onDestroy } from 'svelte';
  import { Chart, LineController, LinearScale, PointElement, LineElement, TimeScale, Tooltip, Filler } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  Chart.register(LineController, LinearScale, PointElement, LineElement, TimeScale, Tooltip, Filler);

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {Array} [data]
   * @property {string} [period]
   * @property {'markup' | 'sales'} [field]
   * @property {boolean} [loading]
   * @property {string} [title]
   */

  /** @type {Props} */
  let {
    data = [],
    period = '30d',
    field = 'markup',
    loading = false,
    title = ''
  } = $props();

  let canvasEl = $state();
  let chart = null;

  function getComputedCssVar(name) {
    if (typeof getComputedStyle === 'undefined') return null;
    return getComputedStyle(document.documentElement).getPropertyValue(name)?.trim() || null;
  }

  function buildChart(snapshots) {
    if (!canvasEl) return;
    if (chart) chart.destroy();

    const col = `${field}_${period}`;
    const points = snapshots
      .filter(r => r[col] != null)
      .map(r => ({ x: new Date(r.recorded_at), y: Number(r[col]) }))
      .sort((a, b) => a.x - b.x);

    if (points.length === 0) {
      chart = null;
      return;
    }

    const accentColor = field === 'markup'
      ? (getComputedCssVar('--accent-color') || '#60b0ff')
      : '#4ecdc4';
    const textMuted = getComputedCssVar('--text-muted') || '#aaaaaa';
    const borderColor = getComputedCssVar('--border-color') || '#555555';
    const isMarkup = field === 'markup';

    // Determine time unit based on data range
    const rangeMs = points[points.length - 1].x - points[0].x;
    const rangeDays = rangeMs / (24 * 60 * 60 * 1000);
    const timeUnit = rangeDays <= 2 ? 'hour' : rangeDays <= 14 ? 'day' : rangeDays <= 90 ? 'week' : 'month';

    chart = new Chart(canvasEl, {
      type: 'line',
      data: {
        datasets: [{
          data: points,
          borderColor: accentColor,
          backgroundColor: accentColor + '20',
          borderWidth: 2,
          pointRadius: points.length < 50 ? 3 : 0,
          pointHoverRadius: 5,
          pointBackgroundColor: accentColor,
          fill: true,
          tension: 0.2,
          spanGaps: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: {
            type: 'time',
            time: { unit: timeUnit },
            ticks: { color: textMuted, maxTicksLimit: 8, font: { size: 11 } },
            grid: { color: borderColor + '40' }
          },
          y: {
            ticks: {
              color: textMuted,
              font: { size: 11 },
              callback: (val) => isMarkup ? `${Number(val).toFixed(1)}%` : Number(val).toLocaleString()
            },
            grid: { color: borderColor + '40' }
          }
        },
        plugins: {
          tooltip: {
            backgroundColor: 'rgba(0,0,0,0.85)',
            titleColor: '#fff',
            bodyColor: '#ddd',
            borderColor: accentColor,
            borderWidth: 1,
            padding: 10,
            callbacks: {
              title: (items) => {
                if (!items.length) return '';
                const d = new Date(items[0].parsed.x);
                return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
              },
              label: (ctx) => {
                const val = ctx.parsed.y;
                return isMarkup ? `Markup: ${Number(val).toFixed(2)}%` : `Sales: ${Number(val).toLocaleString()}`;
              }
            }
          },
          legend: { display: false }
        }
      }
    });
  }

  run(() => {
    if (canvasEl && data && period && field) {
      buildChart(data);
    }
  });

  onDestroy(() => {
    if (chart) { chart.destroy(); chart = null; }
  });
</script>

<div class="mps-chart-container">
  {#if title}
    <div class="chart-title">{title}</div>
  {/if}
  {#if loading}
    <div class="chart-placeholder">Loading...</div>
  {:else if !data || data.length === 0 || !data.some(r => r[`${field}_${period}`] != null)}
    <div class="chart-placeholder">No data</div>
  {:else}
    <div class="chart-wrapper">
      <canvas bind:this={canvasEl}></canvas>
    </div>
  {/if}
</div>

<style>
  .mps-chart-container {
    width: 100%;
    display: flex;
    flex-direction: column;
    min-height: 180px;
    flex: 1;
  }
  .chart-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
  }
  .chart-wrapper {
    flex: 1;
    min-height: 0;
    position: relative;
  }
  .chart-wrapper canvas {
    width: 100% !important;
    height: 100% !important;
  }
  .chart-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    color: var(--text-muted);
    font-size: 13px;
  }
</style>
