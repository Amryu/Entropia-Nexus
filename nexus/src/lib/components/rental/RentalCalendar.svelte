<!--
  @component RentalCalendar
  Month-grid calendar showing rental availability.
  Color codes days as available, booked, blocked, or selected.
-->
<script>
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {Array<{start: string, end: string, reason?: string}>} [blockedDates]
   * @property {Array<{start: string, end: string, requestId?: number}>} [bookedDates]
   * @property {boolean} [selectable]
   * @property {string|null} [selectedStart]
   * @property {string|null} [selectedEnd]
   * @property {number} [months]
   */

  /** @type {Props} */
  let {
    blockedDates = [],
    bookedDates = [],
    selectable = false,
    selectedStart = $bindable(null),
    selectedEnd = $bindable(null),
    months = 3
  } = $props();

  const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

  let currentMonthOffset = $state(0);
  let clickedStart = null;


  function toDateStr(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  function buildDateSet(ranges) {
    const set = new Set();
    for (const range of ranges) {
      const start = new Date(range.start + 'T00:00:00');
      const end = new Date(range.end + 'T00:00:00');
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        set.add(toDateStr(d));
      }
    }
    return set;
  }

  function buildStartSet(ranges) {
    const set = new Set();
    for (const range of ranges) set.add(range.start);
    return set;
  }

  function buildEndSet(ranges) {
    const set = new Set();
    for (const range of ranges) set.add(range.end);
    return set;
  }

  function getVisibleMonths(offset, count) {
    const result = [];
    const now = new Date();
    for (let i = 0; i < count; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() + offset + i, 1);
      result.push({ year: d.getFullYear(), month: d.getMonth() });
    }
    return result;
  }

  function getMonthDays(year, month) {
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const days = [];

    // Monday = 0, Sunday = 6
    let startDow = firstDay.getDay() - 1;
    if (startDow < 0) startDow = 6;

    // Leading blanks
    for (let i = 0; i < startDow; i++) {
      days.push(null);
    }

    for (let d = 1; d <= lastDay.getDate(); d++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      days.push(dateStr);
    }

    return days;
  }

  function getDayStatus(dateStr) {
    if (!dateStr) return 'blank';
    if (dateStr < today) return 'past';
    if (blockedSet.has(dateStr)) return 'blocked';
    if (bookedSet.has(dateStr)) return 'booked';
    return 'available';
  }

  function isHalfDay(dateStr) {
    if (!dateStr) return false;
    return bookedStartSet.has(dateStr) || bookedEndSet.has(dateStr);
  }

  function isBookedStart(dateStr) {
    return bookedStartSet.has(dateStr);
  }

  function isBookedEnd(dateStr) {
    return bookedEndSet.has(dateStr);
  }

  function isInSelection(dateStr) {
    if (!dateStr || !selectedStart) return false;
    const end = selectedEnd || selectedStart;
    return dateStr >= selectedStart && dateStr <= end;
  }

  function isSelectionStart(dateStr) {
    return dateStr === selectedStart;
  }

  function isSelectionEnd(dateStr) {
    return dateStr === (selectedEnd || selectedStart);
  }

  function handleDayClick(dateStr) {
    if (!selectable || !dateStr) return;
    const status = getDayStatus(dateStr);
    if (status === 'past' || status === 'blocked' || status === 'booked') return;

    if (!clickedStart || selectedEnd) {
      // Start new selection
      clickedStart = dateStr;
      selectedStart = dateStr;
      selectedEnd = null;
      dispatch('select', { start: dateStr, end: null });
    } else {
      // Complete selection
      let start = clickedStart;
      let end = dateStr;
      if (end < start) [start, end] = [end, start];

      // Check for conflicts in range
      if (hasConflictInRange(start, end)) return;

      selectedStart = start;
      selectedEnd = end;
      clickedStart = null;
      dispatch('select', { start, end });
    }
  }

  function hasConflictInRange(start, end) {
    const s = new Date(start + 'T00:00:00');
    const e = new Date(end + 'T00:00:00');
    for (let d = new Date(s); d <= e; d.setDate(d.getDate() + 1)) {
      const ds = toDateStr(d);
      if (blockedSet.has(ds) || bookedSet.has(ds)) return true;
    }
    return false;
  }

  function prevMonths() {
    if (currentMonthOffset > 0) currentMonthOffset -= 1;
  }

  function nextMonths() {
    if (currentMonthOffset < 12 - months) currentMonthOffset += 1;
  }
  let today = $derived(toDateStr(new Date()));
  let blockedSet = $derived(buildDateSet(blockedDates));
  let bookedSet = $derived(buildDateSet(bookedDates));
  let bookedStartSet = $derived(buildStartSet(bookedDates));
  let bookedEndSet = $derived(buildEndSet(bookedDates));
  let visibleMonths = $derived(getVisibleMonths(currentMonthOffset, months));
</script>

<div class="rental-calendar">
  <div class="calendar-nav">
    <button class="nav-btn" onclick={prevMonths} disabled={currentMonthOffset <= 0} aria-label="Previous month">
      &larr;
    </button>
    <span class="nav-label">
      {MONTH_NAMES[visibleMonths[0].month]} {visibleMonths[0].year}
      {#if visibleMonths.length > 1}
        &ndash; {MONTH_NAMES[visibleMonths[visibleMonths.length - 1].month]} {visibleMonths[visibleMonths.length - 1].year}
      {/if}
    </span>
    <button class="nav-btn" onclick={nextMonths} disabled={currentMonthOffset >= 12 - months} aria-label="Next month">
      &rarr;
    </button>
  </div>

  <div class="months-grid" style="--month-count: {months}">
    {#each visibleMonths as vm}
      <div class="month">
        <div class="day-headers">
          {#each DAY_NAMES as dayName}
            <div class="day-header">{dayName}</div>
          {/each}
        </div>
        <div class="days-grid">
          {#each getMonthDays(vm.year, vm.month) as dateStr}
            {#if dateStr === null}
              <div class="day blank"></div>
            {:else}
              {@const status = getDayStatus(dateStr)}
              {@const halfDay = isHalfDay(dateStr)}
              <button
                class="day {status}"
                class:selected={selectedStart && dateStr >= selectedStart && dateStr <= (selectedEnd || selectedStart)}
                class:selection-start={dateStr === selectedStart}
                class:selection-end={dateStr === (selectedEnd || selectedStart)}
                class:half-day-start={halfDay && isBookedStart(dateStr) && !isBookedEnd(dateStr)}
                class:half-day-end={halfDay && isBookedEnd(dateStr) && !isBookedStart(dateStr)}
                class:half-day-both={halfDay && isBookedStart(dateStr) && isBookedEnd(dateStr)}
                class:selectable
                disabled={!selectable || status === 'past' || status === 'blocked' || status === 'booked'}
                onclick={() => handleDayClick(dateStr)}
                title={status === 'blocked' ? 'Blocked by owner' : status === 'booked' ? 'Already booked' : status === 'past' ? 'Past date' : ''}
              >
                {parseInt(dateStr.split('-')[2])}
              </button>
            {/if}
          {/each}
        </div>
      </div>
    {/each}
  </div>

  <div class="legend">
    <div class="legend-item">
      <span class="legend-swatch available"></span>
      <span>Available</span>
    </div>
    <div class="legend-item">
      <span class="legend-swatch booked"></span>
      <span>Booked</span>
    </div>
    <div class="legend-item">
      <span class="legend-swatch blocked"></span>
      <span>Blocked</span>
    </div>
    {#if selectable}
      <div class="legend-item">
        <span class="legend-swatch selected"></span>
        <span>Selected</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .rental-calendar {
    width: 100%;
  }

  .calendar-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
  }

  .nav-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-color);
    padding: 0.4rem 0.8rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
  }

  .nav-btn:hover:not(:disabled) {
    background: var(--hover-color);
  }

  .nav-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .nav-label {
    font-weight: 600;
    font-size: 1rem;
  }

  .months-grid {
    display: grid;
    grid-template-columns: repeat(var(--month-count), 1fr);
    gap: 1.5rem;
  }

  .day-headers {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
    margin-bottom: 4px;
  }

  .day-header {
    text-align: center;
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-muted);
    padding: 2px 0;
  }

  .days-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
  }

  .day {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    border-radius: 4px;
    border: none;
    background: transparent;
    color: var(--text-color);
    cursor: default;
    padding: 0;
    position: relative;
  }

  .day.blank {
    visibility: hidden;
  }

  .day.past {
    color: var(--text-muted);
    opacity: 0.4;
  }

  .day.available {
    background: var(--secondary-color);
  }

  .day.available.selectable {
    cursor: pointer;
  }

  .day.available.selectable:hover {
    background: var(--hover-color);
    border: 1px solid var(--accent-color);
  }

  .day.booked {
    background: var(--accent-color);
    color: white;
  }

  .day.half-day-start {
    background: linear-gradient(135deg, var(--secondary-color) 50%, var(--accent-color) 50%);
    color: var(--text-color);
  }

  .day.half-day-end {
    background: linear-gradient(135deg, var(--accent-color) 50%, var(--secondary-color) 50%);
    color: var(--text-color);
  }

  .day.half-day-both {
    background: linear-gradient(135deg, var(--secondary-color) 25%, var(--accent-color) 25%, var(--accent-color) 75%, var(--secondary-color) 75%);
    color: var(--text-color);
  }

  .day.blocked {
    background: var(--hover-color);
    color: var(--text-muted);
    text-decoration: line-through;
  }

  .day.selected {
    background: var(--accent-color) !important;
    color: white !important;
  }

  .day.selection-start {
    border-radius: 4px 0 0 4px;
  }

  .day.selection-end {
    border-radius: 0 4px 4px 0;
  }

  .day.selection-start.selection-end {
    border-radius: 4px;
  }

  .legend {
    display: flex;
    gap: 1rem;
    margin-top: 1rem;
    flex-wrap: wrap;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .legend-swatch {
    width: 14px;
    height: 14px;
    border-radius: 3px;
  }

  .legend-swatch.available {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
  }

  .legend-swatch.booked {
    background: var(--accent-color);
  }

  .legend-swatch.blocked {
    background: var(--hover-color);
  }

  .legend-swatch.selected {
    background: var(--accent-color);
  }

  @media (max-width: 899px) {
    .months-grid {
      grid-template-columns: 1fr;
    }

    .day {
      font-size: 0.75rem;
    }
  }
</style>
