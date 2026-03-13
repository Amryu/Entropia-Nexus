<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';

  interface Props {
    availability?: any; // Array of { day_of_week, start_time, end_time, is_available }
    readonly?: boolean;
    onchange?: (data: { day_of_week: number; start_time: string; is_available: boolean }) => void;
    onupdate?: (data: any[]) => void;
  }

  let { availability = [], readonly = false, onchange, onupdate }: Props = $props();

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const fullDays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  // Map display index to database day_of_week (0=Sunday, 1=Monday, etc.)
  const displayToDayOfWeek = [1, 2, 3, 4, 5, 6, 0]; // Mon-Sun mapped to 1-6,0
  const dayOfWeekToDisplay = [6, 0, 1, 2, 3, 4, 5]; // 0-6 (Sun-Sat) mapped to display indices

  // Current time tracking (in MA Time / UTC+1)
  let currentTime = $state(new Date());
  let timeUpdateInterval;

  onMount(() => {
    // Update current time every minute
    timeUpdateInterval = setInterval(() => {
      currentTime = new Date();
    }, 60000);
  });

  onDestroy(() => {
    if (timeUpdateInterval) {
      clearInterval(timeUpdateInterval);
    }
  });


  // Check if a given day and hour is the current time
  function isCurrentHour(dayOfWeek, hour) {
    return currentMATime.dayOfWeek === dayOfWeek && currentMATime.hour === hour;
  }

  // Check if a given day and time slot is the current slot
  function isCurrentSlot(dayOfWeek, time) {
    const [slotHour, slotMinute] = time.split(':').map(Number);
    const slotEndMinute = (slotMinute + 15) % 60;
    const slotEndHour = slotMinute + 15 >= 60 ? slotHour + 1 : slotHour;

    if (currentMATime.dayOfWeek !== dayOfWeek) return false;
    if (currentMATime.hour !== slotHour) return false;
    return currentMATime.minute >= slotMinute && currentMATime.minute < (slotMinute + 15);
  }

  // Generate time slots (every 15 minutes)
  const timeSlots = [];
  for (let hour = 0; hour < 24; hour++) {
    for (let minute = 0; minute < 60; minute += 15) {
      timeSlots.push({
        hour,
        minute,
        label: `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`
      });
    }
  }


  function buildAvailabilityMap(slots) {
    const map = new Map();
    for (const slot of slots) {
      // Normalize time format by stripping seconds if present
      const startTime = slot.start_time.substring(0, 5); // "16:00:00" -> "16:00"
      const key = `${slot.day_of_week}-${startTime}`;
      const value = slot.is_available !== false;
      map.set(key, value);
    }
    return map;
  }

  function isSlotAvailable(day, time) {
    const key = `${day}-${time}`;
    return availabilityMap.get(key) ?? false;
  }

  function toggleSlot(day, time) {
    if (readonly) return;

    const key = `${day}-${time}`;
    const currentValue = availabilityMap.get(key) ?? false;
    const newValue = !currentValue;

    // Update the map
    availabilityMap.set(key, newValue);
    availabilityMap = new Map(availabilityMap); // Trigger reactivity

    // Dispatch change event with the updated slot
    onchange?.({
      day_of_week: day,
      start_time: time,
      is_available: newValue
    });
  }

  // Drag selection state
  let isDragging = false;
  let dragValue = null;
  let dragStart = null;
  let hasDragged = false; // Track if we actually moved to another cell

  function handleMouseDown(day, time, event) {
    if (readonly) return;
    event.preventDefault();

    isDragging = true;
    hasDragged = false;
    dragStart = { day, time };
    dragValue = !isSlotAvailable(day, time);

    // Apply to the starting cell immediately
    applyDragValue(day, time);
  }

  function handleMouseEnter(day, time) {
    if (!isDragging || readonly) return;
    hasDragged = true; // We moved to another cell
    applyDragValue(day, time);
  }

  function handleHourMouseDown(day, hour, event) {
    if (readonly) return;
    event.preventDefault();

    isDragging = true;
    hasDragged = false;
    dragStart = { day, hour };
    // Determine drag value based on current state of the hour
    dragValue = !isHourFullyAvailable(day, hour);

    // Apply to all slots in this hour immediately
    applyDragValueToHour(day, hour);
  }

  function handleHourMouseEnter(day, hour) {
    if (!isDragging || readonly) return;
    hasDragged = true;
    applyDragValueToHour(day, hour);
  }

  function handleHourTouchStart(day, hour, event) {
    if (readonly) return;
    event.preventDefault();
    handleHourMouseDown(day, hour, event);
  }

  function applyDragValueToHour(day, hour) {
    for (const slot of hourGroups[hour]) {
      const key = `${day}-${slot.label}`;
      availabilityMap.set(key, dragValue);
    }
    availabilityMap = new Map(availabilityMap);
  }

  function handleMouseUp() {
    if (isDragging) {
      isDragging = false;
      dragValue = null;
      dragStart = null;
      hasDragged = false;
      // Dispatch final availability state
      onupdate?.(getAvailabilityArray());
    }
  }

  function applyDragValue(day, time) {
    const key = `${day}-${time}`;
    availabilityMap.set(key, dragValue);
    availabilityMap = new Map(availabilityMap);
  }

  // Touch support
  function handleTouchStart(day, time, event) {
    if (readonly) return;
    // Prevent scroll while dragging
    event.preventDefault();
    handleMouseDown(day, time, event);
  }

  function handleTouchMove(event) {
    if (!isDragging || readonly) return;
    event.preventDefault();

    const touch = event.touches[0];
    const element = document.elementFromPoint(touch.clientX, touch.clientY);
    if (element?.dataset?.day !== undefined && element?.dataset?.time) {
      const day = parseInt(element.dataset.day);
      const time = element.dataset.time;
      applyDragValue(day, time);
    }
  }

  function handleTouchEnd() {
    handleMouseUp();
  }

  // Convert map back to array format for saving
  function getAvailabilityArray() {
    const slots = [];
    const seen = new Set();
    for (const [key, isAvailable] of availabilityMap.entries()) {
      if (isAvailable) {
        const [day, time] = key.split('-');
        const uniqueKey = `${day}-${time}`;
        // Skip duplicates
        if (seen.has(uniqueKey)) continue;
        seen.add(uniqueKey);
        
        const [hour, minute] = time.split(':');
        const endMinute = (parseInt(minute) + 15) % 60;
        const endHour = parseInt(minute) + 15 >= 60 ? parseInt(hour) + 1 : parseInt(hour);
        slots.push({
          day_of_week: parseInt(day),
          start_time: time,
          end_time: `${endHour.toString().padStart(2, '0')}:${endMinute.toString().padStart(2, '0')}`,
          is_available: true
        });
      }
    }
    return slots;
  }

  // Quick actions
  function selectAll() {
    if (readonly) return;
    // Iterate through all days (0-6 in database format)
    for (const day of [0, 1, 2, 3, 4, 5, 6]) {
      for (const slot of timeSlots) {
        availabilityMap.set(`${day}-${slot.label}`, true);
      }
    }
    availabilityMap = new Map(availabilityMap);
    onupdate?.(getAvailabilityArray());
  }

  function clearAll() {
    if (readonly) return;
    availabilityMap = new Map();
    onupdate?.([]);
  }

  function selectDay(day) {
    if (readonly) return;
    for (const slot of timeSlots) {
      availabilityMap.set(`${day}-${slot.label}`, true);
    }
    availabilityMap = new Map(availabilityMap);
    onupdate?.(getAvailabilityArray());
  }

  function clearDay(day) {
    if (readonly) return;
    for (const slot of timeSlots) {
      availabilityMap.set(`${day}-${slot.label}`, false);
    }
    availabilityMap = new Map(availabilityMap);
    onupdate?.(getAvailabilityArray());
  }

  // Select time range across all days
  function selectHourRange(startHour, endHour) {
    if (readonly) return;
    // Iterate through all days (0-6 in database format)
    for (const day of [0, 1, 2, 3, 4, 5, 6]) {
      for (const slot of timeSlots) {
        if (slot.hour >= startHour && slot.hour < endHour) {
          availabilityMap.set(`${day}-${slot.label}`, true);
        }
      }
    }
    availabilityMap = new Map(availabilityMap);
    onupdate?.(getAvailabilityArray());
  }


  // Check if we should show condensed view (show only hours, expand on click)
  let expandedHours = $state(new Set());

  function toggleHourExpand(hour) {
    if (expandedHours.has(hour)) {
      expandedHours.delete(hour);
    } else {
      expandedHours.add(hour);
    }
  }

  // For display, check if any slot in an hour is available
  function isHourPartiallyAvailable(day, hour) {
    for (const slot of hourGroups[hour]) {
      if (isSlotAvailable(day, slot.label)) {
        return true;
      }
    }
    return false;
  }

  function isHourFullyAvailable(day, hour) {
    for (const slot of hourGroups[hour]) {
      if (!isSlotAvailable(day, slot.label)) {
        return false;
      }
    }
    return true;
  }

  // Toggle entire hour for a single day
  function toggleHour(day, hour) {
    if (readonly) return;
    const shouldEnable = !isHourFullyAvailable(day, hour);
    for (const slot of hourGroups[hour]) {
      availabilityMap.set(`${day}-${slot.label}`, shouldEnable);
    }
    availabilityMap = new Map(availabilityMap);
    onupdate?.(getAvailabilityArray());
  }

  // Toggle entire hour row (all days)
  function toggleHourRow(hour) {
    if (readonly) return;
    // Check if the entire row is fully available
    let allFull = true;
    for (let day = 0; day < 7; day++) {
      for (const slot of hourGroups[hour]) {
        if (!availabilityMap.get(`${day}-${slot.label}`)) {
          allFull = false;
          break;
        }
      }
      if (!allFull) break;
    }
    // If all full, clear; otherwise, select all
    const shouldEnable = !allFull;
    for (let day = 0; day < 7; day++) {
      for (const slot of hourGroups[hour]) {
        availabilityMap.set(`${day}-${slot.label}`, shouldEnable);
      }
    }
    availabilityMap = new Map(availabilityMap);
    onupdate?.(getAvailabilityArray());
  }

  // Toggle a specific time slot across all days (for sub-labels)
  function toggleTimeSlotRow(time) {
    if (readonly) return;
    // Check if all days have this time slot available
    let allAvailable = true;
    for (let day = 0; day < 7; day++) {
      if (!availabilityMap.get(`${day}-${time}`)) {
        allAvailable = false;
        break;
      }
    }
    // If all available, clear; otherwise, select all
    const shouldEnable = !allAvailable;
    for (let day = 0; day < 7; day++) {
      availabilityMap.set(`${day}-${time}`, shouldEnable);
    }
    availabilityMap = new Map(availabilityMap);
    onupdate?.(getAvailabilityArray());
  }
  // Get current day and time in MA Time (UTC+1)
  let currentMATime = $derived((() => {
    // Convert to MA Time (UTC+1)
    const maTime = new Date(currentTime.getTime() + (currentTime.getTimezoneOffset() + 60) * 60000);
    return {
      dayOfWeek: maTime.getDay(), // 0 = Sunday
      hour: maTime.getHours(),
      minute: maTime.getMinutes()
    };
  })());
  // Build a map for quick lookup: key = "day-HH:MM"
  let availabilityMap = $derived(buildAvailabilityMap(availability));
  // Group time slots by hour for display
  let hourGroups = $derived(timeSlots.reduce((groups, slot) => {
    if (!groups[slot.hour]) {
      groups[slot.hour] = [];
    }
    groups[slot.hour].push(slot);
    return groups;
  }, {}));
</script>

<svelte:window onmouseup={handleMouseUp} ontouchend={handleTouchEnd} ontouchmove={handleTouchMove} />

<div class="calendar-container">
  <div class="calendar-header">
    <span class="timezone-note">All times in MA Time (UTC+1/CET)</span>
    {#if !readonly}
      <div class="quick-actions">
        <button type="button" class="quick-btn" onclick={selectAll}>Select All</button>
        <button type="button" class="quick-btn" onclick={clearAll}>Clear All</button>
        <button type="button" class="quick-btn" onclick={() => selectHourRange(9, 17)}>9-5</button>
        <button type="button" class="quick-btn" onclick={() => selectHourRange(18, 24)}>Evening</button>
      </div>
    {/if}
  </div>

  <div class="calendar-scroll-container">
    <div class="calendar-grid" class:readonly>
      <!-- Header row with days -->
      <div class="time-header"></div>
      {#each days as day, displayIndex}
        {@const dayOfWeek = displayToDayOfWeek[displayIndex]}
        <div class="day-header" class:clickable={!readonly}>
          <span class="day-full">{fullDays[displayIndex]}</span>
          <span class="day-short">{day}</span>
          {#if !readonly}
            <div class="day-actions">
              <button type="button" class="tiny-btn" onclick={() => selectDay(dayOfWeek)} title="Select all">+</button>
              <button type="button" class="tiny-btn" onclick={() => clearDay(dayOfWeek)} title="Clear all">-</button>
            </div>
          {/if}
        </div>
      {/each}

      <!-- Time rows -->
      {#each Object.entries(hourGroups) as [hour, slots]}
        <!-- Hour row (always visible) -->
        <div class="time-label">
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -- tabindex is conditional: only set when !readonly makes this a button -->
          <span
            class="hour-label"
            class:clickable={!readonly}
            role={readonly ? undefined : 'button'}
            tabindex={readonly ? undefined : 0}
            onclick={() => !readonly && toggleHourRow(parseInt(hour))}
            onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && !readonly && (e.preventDefault(), toggleHourRow(parseInt(hour)))}
            title={readonly ? '' : 'Toggle all slots in this hour'}
          >{hour.toString().padStart(2, '0')}:00</span>
          <button
            type="button"
            class="expand-btn"
            onclick={() => toggleHourExpand(parseInt(hour))}
            title={expandedHours.has(parseInt(hour)) ? 'Collapse' : 'Expand 15-min slots'}
          >
            {#if !expandedHours.has(parseInt(hour))}
              ▼
            {:else}
              ▲
            {/if}
          </button>
        </div>
        {#each days as _, displayIndex}
          {@const dayOfWeek = displayToDayOfWeek[displayIndex]}
          {@const hourFull = hourGroups[hour].every(s => availabilityMap.get(`${dayOfWeek}-${s.label}`) === true)}
          {@const hourPartial = hourGroups[hour].some(s => availabilityMap.get(`${dayOfWeek}-${s.label}`) === true)}
          {@const isCurrent = isCurrentHour(dayOfWeek, parseInt(hour))}
          <div
            class="slot hour-slot"
            class:available={hourFull}
            class:partial={hourPartial && !hourFull}
            class:readonly
            class:expanded={expandedHours.has(parseInt(hour))}
            class:current-time={isCurrent}
            onmousedown={(e) => handleHourMouseDown(dayOfWeek, parseInt(hour), e)}
            onmouseenter={() => handleHourMouseEnter(dayOfWeek, parseInt(hour))}
            ontouchstart={(e) => handleHourTouchStart(dayOfWeek, parseInt(hour), e)}
            onkeydown={(e) => e.key === 'Enter' && toggleHour(dayOfWeek, parseInt(hour))}
            role="gridcell"
            tabindex={readonly ? -1 : 0}
          >
            <span class="slot-indicator"></span>
          </div>
        {/each}

        <!-- 15-minute slots (expanded view) -->
        {#if expandedHours.has(parseInt(hour))}
          {#each slots as slot}
            <!-- svelte-ignore a11y_no_noninteractive_tabindex -- tabindex is conditional: only set when !readonly makes this a button -->
            <div
              class="time-label sub-label"
              class:clickable={!readonly}
              role={readonly ? undefined : 'button'}
              tabindex={readonly ? undefined : 0}
              onclick={() => !readonly && toggleTimeSlotRow(slot.label)}
              onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && !readonly && (e.preventDefault(), toggleTimeSlotRow(slot.label))}
              title={readonly ? '' : 'Toggle this time slot for all days'}
            >
              {slot.label}
            </div>
            {#each days as _, displayIndex}
              {@const dayOfWeek = displayToDayOfWeek[displayIndex]}
              {@const isCurrentSlotNow = isCurrentSlot(dayOfWeek, slot.label)}
              <div
                class="slot sub-slot"
                class:available={availabilityMap.get(`${dayOfWeek}-${slot.label}`) === true}
                class:readonly
                class:current-time={isCurrentSlotNow}
                data-day={dayOfWeek}
                data-time={slot.label}
                onmousedown={(e) => handleMouseDown(dayOfWeek, slot.label, e)}
                onmouseenter={() => handleMouseEnter(dayOfWeek, slot.label)}
                ontouchstart={(e) => handleTouchStart(dayOfWeek, slot.label, e)}
                onkeydown={(e) => e.key === 'Enter' && toggleSlot(dayOfWeek, slot.label)}
                role="gridcell"
                tabindex={readonly ? -1 : 0}
              >
                <span class="slot-indicator"></span>
              </div>
            {/each}
          {/each}
        {/if}
      {/each}
    </div>
  </div>

  <div class="calendar-legend">
    <div class="legend-item">
      <span class="legend-box available"></span>
      <span>Available</span>
    </div>
    <div class="legend-item">
      <span class="legend-box partial"></span>
      <span>Partially Available</span>
    </div>
    <div class="legend-item">
      <span class="legend-box"></span>
      <span>Unavailable</span>
    </div>
    <div class="legend-item">
      <span class="legend-box current"></span>
      <span>Current Time</span>
    </div>
  </div>
</div>

<style>
  .calendar-container {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .calendar-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .timezone-note {
    font-size: 0.85rem;
    color: #888;
  }

  .quick-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .quick-btn {
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
    border: 1px solid #666;
    background: var(--secondary-color);
    color: var(--text-color);
    border-radius: 4px;
    cursor: pointer;
  }

  .quick-btn:hover {
    background: var(--hover-color);
  }

  .calendar-scroll-container {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  .calendar-grid {
    display: grid;
    grid-template-columns: 60px repeat(7, minmax(40px, 1fr));
    gap: 1px;
    background: #666;
    border: 1px solid #666;
    border-radius: 4px;
    min-width: 350px;
    user-select: none;
  }

  .calendar-grid.readonly {
    pointer-events: auto;
  }

  .time-header,
  .day-header,
  .time-label,
  .slot {
    background: var(--primary-color);
    padding: 0.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .day-header {
    flex-direction: column;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 0.5rem 0.25rem;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  .day-full {
    display: none;
  }

  .day-short {
    display: block;
  }

  @media (min-width: 600px) {
    .day-full {
      display: block;
    }
    .day-short {
      display: none;
    }
  }

  .day-actions {
    display: flex;
    gap: 2px;
    margin-top: 2px;
  }

  .tiny-btn {
    width: 18px;
    height: 18px;
    padding: 0;
    font-size: 0.7rem;
    border: 1px solid #666;
    background: var(--secondary-color);
    color: var(--text-color);
    border-radius: 2px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .tiny-btn:hover {
    background: var(--hover-color);
  }

  .time-label {
    font-size: 0.75rem;
    color: #888;
    justify-content: flex-start;
    padding-left: 0.25rem;
    padding-right: 0.125rem;
    position: sticky;
    left: 0;
    z-index: 1;
    background: var(--secondary-color);
    gap: 0.125rem;
    overflow: hidden;
  }

  .sub-label {
    font-size: 0.7rem;
    padding-left: 0.5rem;
    background: var(--primary-color);
  }

  .sub-label.clickable {
    cursor: pointer;
  }

  .sub-label.clickable:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .hour-label {
    font-weight: 500;
    padding: 0.125rem 0.2rem;
    border-radius: 2px;
    flex-shrink: 0;
  }

  .hour-label.clickable {
    cursor: pointer;
  }

  .hour-label.clickable:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .expand-btn {
    font-size: 0.5rem;
    margin-left: auto;
    padding: 0.1rem 0.15rem;
    background: transparent;
    border: none;
    color: #888;
    cursor: pointer;
    border-radius: 2px;
    line-height: 1;
    flex-shrink: 0;
  }

  .expand-btn:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .slot {
    min-height: 24px;
    cursor: pointer;
    transition: background-color 0.1s;
    position: relative;
  }

  .slot.readonly {
    cursor: default;
  }

  .slot:not(.readonly):hover {
    background: var(--hover-color);
  }

  .slot.available {
    background: #2d5a3d;
  }

  .slot.available:not(.readonly):hover {
    background: #3a7a50;
  }

  .slot.partial {
    background: linear-gradient(135deg, #2d5a3d 50%, var(--primary-color) 50%);
  }

  .hour-slot {
    min-height: 28px;
  }

  .sub-slot {
    min-height: 20px;
    background: #2a2a2a; /* Slightly brighter than default background */
  }

  .sub-slot.available {
    background: #3a7a50;
  }

  .sub-slot.available:not(.readonly):hover {
    background: #4a9a60;
  }

  .slot-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    opacity: 0;
  }

  .slot.available .slot-indicator {
    background: #2d5a3d;
    opacity: 0.6;
  }

  .calendar-legend {
    display: flex;
    gap: 1rem;
    margin-top: 0.75rem;
    flex-wrap: wrap;
    font-size: 0.85rem;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .legend-box {
    width: 16px;
    height: 16px;
    border: 1px solid #666;
    border-radius: 2px;
    background: var(--primary-color);
  }

  .legend-box.available {
    background: #2d5a3d;
  }

  .legend-box.partial {
    background: linear-gradient(135deg, #2d5a3d 50%, var(--primary-color) 50%);
  }

  .legend-box.current {
    background: var(--primary-color);
    border: 2px solid #f59e0b;
    box-shadow: 0 0 4px rgba(245, 158, 11, 0.5);
  }

  /* Current time highlighting */
  .slot.current-time {
    outline: 2px solid #f59e0b;
    outline-offset: -2px;
    box-shadow: inset 0 0 6px rgba(245, 158, 11, 0.4);
    z-index: 1;
    position: relative;
  }

  .slot.current-time::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(245, 158, 11, 0.15);
    pointer-events: none;
  }

  /* Mobile optimizations */
  @media (max-width: 480px) {
    .calendar-grid {
      grid-template-columns: 50px repeat(7, minmax(35px, 1fr));
    }

    .day-header {
      font-size: 0.75rem;
      padding: 0.35rem 0.15rem;
    }

    .time-label {
      font-size: 0.6rem;
      padding-left: 0.15rem;
      padding-right: 0.1rem;
      gap: 0.1rem;
    }

    .expand-btn {
      font-size: 0.45rem;
      padding: 0.075rem 0.1rem;
    }

    .hour-label {
      padding: 0.075rem 0.1rem;
      font-size: 0.6rem;
    }

    .sub-label {
      padding-left: 0.25rem;
      font-size: 0.55rem;
    }

    .slot {
      min-height: 20px;
    }

    .hour-slot {
      min-height: 24px;
    }

    .sub-slot {
      min-height: 18px;
    }

    .quick-actions {
      width: 100%;
      justify-content: flex-start;
    }

    .quick-btn {
      font-size: 0.75rem;
      padding: 0.2rem 0.4rem;
    }

    .calendar-legend {
      font-size: 0.75rem;
    }
  }
</style>
