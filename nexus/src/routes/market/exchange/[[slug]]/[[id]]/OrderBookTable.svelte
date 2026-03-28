<script>
  //@ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { computeState } from '../../exchangeConstants.js';
  import { formatMarkupValue } from '../../orderUtils';
  import { PLATE_SET_SIZE } from '$lib/common/itemTypes.js';


















  /**
   * @typedef {Object} Props
   * @property {'buy'|'sell'} [side]
   * @property {Array} [orders]
   * @property {boolean} [loading]
   * @property {boolean} [tierable]
   * @property {boolean} [absoluteMarkup]
   * @property {string|null} [currentUserId]
   * @property {boolean} [isArmorPlating]
   * @property {boolean} [isGendered]
   * @property {string} [planetFilter]
   * @property {(data: any) => void} [onrowClick]
   * @property {(data: any) => void} [onsellerClick]
   */

  /** @type {Props} */
  let {
    side = 'sell',
    orders = [],
    loading = false,
    tierable = false,
    absoluteMarkup = false,
    currentUserId = null,
    isArmorPlating = false,
    isGendered = false,
    planetFilter = 'All Planets',
    onrowClick,
    onsellerClick,
  } = $props();


  function buildColumns(isTierable, isAbsoluteMu, isPlating, isGend) {
    const cols = [];

    if (isTierable) {
      cols.push({ key: 'tier', header: 'Tier', width: '60px', sortable: true, searchable: false });
      cols.push({ key: 'tir', header: 'TiR', width: '80px', sortable: true, searchable: false });
    }

    cols.push({ key: 'quantity', header: 'Qty', width: '80px', sortable: true, searchable: false });

    if (isPlating) {
      cols.push({
        key: 'is_set',
        header: 'Set',
        width: '55px',
        sortable: true,
        searchable: false,
        formatter: (val) => val
          ? '<span class="badge badge-subtle badge-accent">Yes</span>'
          : '<span class="badge badge-subtle">No</span>'
      });
    }
    if (isGend) {
      cols.push({
        key: 'gender',
        header: 'Gender',
        width: '70px',
        sortable: true,
        searchable: false,
        formatter: (val) => val === 'Male' ? 'M' : val === 'Female' ? 'F' : '-'
      });
    }
    cols.push({
      key: 'markup',
      header: isAbsoluteMu ? 'MU (+PED)' : 'MU (%)',
      width: '100px',
      sortable: true,
      searchable: false,
      formatter: (val) => {
        if (val === null) return '<span class="negotiable-badge">Negotiable</span>';
        if (val == null) return 'N/A';
        return formatMarkupValue(val, isAbsoluteMu);
      }
    });
    cols.push({ key: 'planet', header: 'Planet', width: '120px', sortable: true, searchable: false });
    cols.push({
      key: 'seller_name',
      header: side === 'buy' ? 'Buyer' : 'Seller',
      main: true,
      width: '120px',
      sortable: true,
      searchable: false,
      formatter: (val, row) => {
        const userId = row?.user_id ?? '';
        const name = val || 'Unknown';
        return `<span class="seller-link" data-seller-id="${userId}" data-seller-name="${name.replace(/"/g, '&quot;')}">${name}</span>`;
      }
    });
    cols.push({
      key: 'state',
      header: 'Status',
      width: '80px',
      sortable: true,
      searchable: false,
      formatter: (val) => {
        const s = val || 'active';
        const cls = s === 'active' ? 'badge-success' : s === 'stale' ? 'badge-warning' : 'badge-error';
        return `<span class="badge badge-subtle ${cls}">${s}</span>`;
      }
    });
    cols.push({
      key: 'bumped_at',
      header: 'Updated',
      width: '120px',
      sortable: true,
      searchable: false,
      formatter: (val) => formatAge(val)
    });

    return cols;
  }



  function formatAge(dateStr) {
    if (!dateStr) return 'N/A';
    const ts = new Date(dateStr);
    const diff = Math.max(0, Date.now() - ts.getTime());
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.floor(hrs / 24);
    return `${days}d`;
  }

  function handleRowClick(data) {
    onrowClick?.(data);
  }

  function handleTableClick(e) {
    const sellerEl = e.target.closest('[data-seller-id]');
    if (!sellerEl) return;
    e.stopPropagation();
    e.preventDefault();
    const userId = sellerEl.dataset.sellerId;
    const name = sellerEl.dataset.sellerName || 'Unknown';
    if (userId) onsellerClick?.({ id: userId, name });
  }
  // Build columns dynamically based on item type
  let columns = $derived(buildColumns(tierable, absoluteMarkup, isArmorPlating, isGendered));
  // Filter and sort orders for display
  let filteredOrders = $derived((orders || [])
    .filter(o => planetFilter === 'All Planets' || o.planet === planetFilter)
    .map(o => ({
      ...o,
      state: o.computed_state || computeState(o.bumped_at),
      seller_name: o.seller_name || 'Unknown',
      tier: o.details?.Tier ?? o.details?.tier ?? null,
      tir: o.details?.TierIncreaseRate ?? o.details?.tir ?? null,
      is_set: Number(o.quantity) === PLATE_SET_SIZE,
      gender: o.details?.Gender ?? null,
    })));
  let tableData = $derived(filteredOrders);
</script>

<div class="order-book-table" role="presentation" onclickcapture={handleTableClick}>
  <div class="table-header">
    <h3 class="table-title {side}">{side === 'buy' ? 'Buy' : 'Sell'} Orders</h3>
    {#if loading}
      <span class="loading-indicator">Loading...</span>
    {/if}
  </div>
  <div class="table-body">
    <FancyTable
      columns={columns}
      data={tableData}
      rowHeight={36}
      sortable={true}
      searchable={false}
      emptyMessage="No {side} orders"
      rowClass={(row) => currentUserId && String(row.user_id) === String(currentUserId) ? 'my-order' : null}
      onrowClick={handleRowClick}
    />
  </div>
</div>

<style>
  .order-book-table {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }
  .table-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    flex-shrink: 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 4px;
  }
  .table-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
  }
  .table-title.sell { color: var(--error-color, #ef4444); }
  .table-title.buy { color: var(--success-color, #16a34a); }
  .loading-indicator {
    font-size: 11px;
    color: var(--text-muted);
  }
  .table-body {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
  .order-book-table :global(.my-order) {
    background-color: var(--hover-color) !important;
    box-shadow: inset 2px 0 0 var(--accent-color);
  }
  .order-book-table :global(.seller-link) {
    cursor: pointer;
    color: var(--accent-color);
  }
  .order-book-table :global(.seller-link:hover) {
    text-decoration: underline;
  }
  .order-book-table :global(.badge-accent) {
    background: var(--accent-color);
    color: #fff;
    font-weight: 600;
  }

  :global(.negotiable-badge) {
    display: inline-block;
    padding: 1px 6px;
    border-radius: 3px;
    background: var(--secondary-color);
    color: var(--text-muted);
    font-size: 0.75rem;
    font-style: italic;
    border: 1px solid var(--border-color);
  }
</style>
