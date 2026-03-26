/**
 * Shared formatting utilities for globals pages.
 */

/** Format a PED value compactly (e.g. 1.5K, 2.3M). */
export function formatPedShort(value) {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
  return value.toFixed(0);
}

/** Format a PED value for table display (e.g. 1.5K or 12.50). */
export function formatPed(v) {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`;
  return v.toFixed(2);
}

/** Format a global's value based on its type and unit. */
export function formatValue(value, unit, type) {
  if (type === 'discovery') return '';
  if (type === 'tier' && unit === 'TIER') return `Tier ${value}`;
  if (type === 'pvp') return `${value} kills`;
  if (unit === 'PEC') {
    const ped = value / 100;
    return `${ped.toFixed(2)} PED`;
  }
  if (value >= 1000) return `${(value / 1000).toFixed(1)}K PED`;
  return `${value.toFixed(2)} PED`;
}

/** Format a timestamp as a relative time string (e.g. "5m ago", "2h ago"). */
export function timeAgo(dateStr) {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days > 365) {
    const years = (days / 365).toFixed(1);
    return `${years}y ago`;
  }
  return `${days}d ago`;
}

/** Get a computed CSS variable value (client-side only). */
export function getComputedCssVar(name) {
  if (typeof getComputedStyle === 'undefined') return null;
  return getComputedStyle(document.documentElement).getPropertyValue(name)?.trim() || null;
}

/** Sort icon character for sortable table columns. */
export function sortIcon(sortState, col) {
  if (sortState.col !== col) return '';
  return sortState.asc ? ' \u25B2' : ' \u25BC';
}

/** Generic client-side sort for data arrays. */
export function sortedData(arr, sort) {
  return [...arr].sort((a, b) => {
    const va = a[sort.col] ?? 0;
    const vb = b[sort.col] ?? 0;
    if (typeof va === 'string') return sort.asc ? va.localeCompare(vb) : vb.localeCompare(va);
    return sort.asc ? va - vb : vb - va;
  });
}

/** Toggle sort state: flip direction if same column, else set new column descending. */
export function toggleSort(sortState, col) {
  if (sortState.col === col) {
    return { col, asc: !sortState.asc };
  }
  return { col, asc: false };
}
