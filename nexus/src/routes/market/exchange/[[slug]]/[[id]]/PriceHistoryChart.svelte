<script>
  //@ts-nocheck
  import { onMount, onDestroy } from 'svelte';
  import { Chart, LinearScale, PointElement, LineElement, TimeScale, Tooltip, Filler } from 'chart.js';
  import 'chartjs-adapter-date-fns';

  Chart.register(LinearScale, PointElement, LineElement, TimeScale, Tooltip, Filler);

  /** @type {number|null} */
  export let itemId = null;

  /** @type {string} Price period (24h, 7d, 30d, etc.) */
  export let period = '7d';

  /** @type {boolean} Whether this item uses absolute markup (+PED) */
  export let isAbsoluteMarkup = false;

  /** @type {Array} Pre-fetched history data (from parent) */
  export let data = [];

  /** @type {boolean} */
  export let loading = false;

  let canvasEl;
  let chart = null;

  const PERIOD_TIME_UNITS = {
    '24h': 'hour',
    '7d': 'day',
    '30d': 'day',
    '3m': 'week',
    '6m': 'week',
    '1y': 'month',
    '5y': 'month',
    'all': 'month'
  };

  function getComputedCssVar(name) {
    if (typeof getComputedStyle === 'undefined') return null;
    return getComputedStyle(document.documentElement).getPropertyValue(name)?.trim() || null;
  }

  function buildChart(historyData) {
    if (!canvasEl) return;
    if (chart) chart.destroy();

    const accentColor = getComputedCssVar('--accent-color') || '#60b0ff';
    const textColor = getComputedCssVar('--text-color') || '#ffffff';
    const textMuted = getComputedCssVar('--text-muted') || '#aaaaaa';
    const borderColor = getComputedCssVar('--border-color') || '#555555';

    const labels = historyData.map(d => new Date(d.timestamp));
    const wapData = historyData.map(d => d.wap);
    const volumeData = historyData.map(d => d.volume);
    const hasMinMax = historyData.length > 0 && historyData[0].min != null;

    const datasets = [{
      label: 'WAP',
      data: wapData,
      borderColor: accentColor,
      backgroundColor: accentColor + '20',
      borderWidth: 2,
      pointRadius: historyData.length < 50 ? 3 : 0,
      pointHoverRadius: 5,
      pointBackgroundColor: accentColor,
      fill: true,
      tension: 0.2,
      spanGaps: true
    }];

    if (hasMinMax) {
      const minData = historyData.map(d => d.min);
      const maxData = historyData.map(d => d.max);
      datasets.push({
        label: 'Min',
        data: minData,
        borderColor: textMuted + '60',
        borderWidth: 1,
        borderDash: [4, 4],
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        tension: 0.2,
        spanGaps: true
      });
      datasets.push({
        label: 'Max',
        data: maxData,
        borderColor: textMuted + '60',
        borderWidth: 1,
        borderDash: [4, 4],
        pointRadius: 0,
        pointHoverRadius: 3,
        fill: false,
        tension: 0.2,
        spanGaps: true
      });
    }

    const timeUnit = PERIOD_TIME_UNITS[period] || 'day';

    chart = new Chart(canvasEl, {
      type: 'line',
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        scales: {
          x: {
            type: 'time',
            time: { unit: timeUnit },
            ticks: { color: textMuted, maxTicksLimit: 10, font: { size: 11 } },
            grid: { color: borderColor + '40' }
          },
          y: {
            ticks: {
              color: textMuted,
              font: { size: 11 },
              callback: (val) => isAbsoluteMarkup ? `+${val.toFixed(1)}` : `${val.toFixed(1)}%`
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
                const idx = ctx.dataIndex;
                const row = historyData[idx];
                if (!row) return '';
                const val = ctx.parsed.y;
                const formatted = isAbsoluteMarkup ? `+${val.toFixed(2)} PED` : `${val.toFixed(1)}%`;
                if (ctx.dataset.label === 'WAP') {
                  const lines = [`WAP: ${formatted}`];
                  if (row.volume != null) lines.push(`Volume: ${row.volume}`);
                  if (row.median != null) {
                    const medFormatted = isAbsoluteMarkup ? `+${row.median.toFixed(2)}` : `${row.median.toFixed(1)}%`;
                    lines.push(`Median: ${medFormatted}`);
                  }
                  if (row.sample_count != null) lines.push(`Samples: ${row.sample_count}`);
                  return lines;
                }
                return `${ctx.dataset.label}: ${formatted}`;
              }
            }
          },
          legend: { display: false }
        }
      }
    });
  }

  $: if (canvasEl && data) {
    buildChart(data);
  }

  onDestroy(() => {
    if (chart) { chart.destroy(); chart = null; }
  });
</script>

<div class="price-chart-container">
  {#if loading}
    <div class="chart-placeholder">Loading price history...</div>
  {:else if !data || data.length === 0}
    <div class="chart-placeholder">No price history available</div>
  {:else}
    {#if data.length < 3}
      <div class="chart-notice">Limited data ({data.length} point{data.length === 1 ? '' : 's'})</div>
    {/if}
    <div class="chart-wrapper">
      <canvas bind:this={canvasEl}></canvas>
    </div>
  {/if}
</div>

<style>
  .price-chart-container {
    width: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1;
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
  .chart-notice {
    text-align: center;
    color: var(--text-muted);
    font-size: 11px;
    padding: 2px 0;
    flex-shrink: 0;
  }
</style>
