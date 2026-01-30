<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { goto, invalidateAll } from '$app/navigation';
  import { apiPost, apiPut } from '$lib/util';
  import {
    canRestoreFlight,
    hasFlightOverlap,
    toDateTimeLocalFormat
  } from '$lib/utils/flightUtils';

  export let data;

  $: service = data.service;
  $: planets = data.planets || [];
  $: flights = data.flights || [];

  let showCreateForm = false;
  let saving = false;
  let error = '';

  // Create flight form
  let scheduledDeparture = '';
  let routeType = 'fixed';
  let routeStops = [{ planet_id: null, name: '' }, { planet_id: null, name: '' }];
  let flexibleEndPoint = { planet_id: null, name: '' };

  function addStop() {
    routeStops = [...routeStops, { planet_id: null, name: '' }];
  }

  function removeStop(index) {
    if (routeStops.length <= 2) return;
    routeStops = routeStops.filter((_, i) => i !== index);
  }

  function getPlanetName(planetId) {
    const planet = planets.find(p => p.Id === planetId);
    return planet?.Name || 'Unknown';
  }

  function getStatusClass(status) {
    const classes = {
      scheduled: 'status-scheduled',
      boarding: 'status-boarding',
      running: 'status-running',
      completed: 'status-completed',
      cancelled: 'status-cancelled'
    };
    return classes[status] || '';
  }

  function getStatusLabel(status) {
    const labels = {
      scheduled: 'Scheduled',
      boarding: 'Boarding',
      running: 'In Flight',
      completed: 'Completed',
      cancelled: 'Cancelled'
    };
    return labels[status] || status;
  }

  function getRouteDisplay(flight) {
    const stops = typeof flight.route_stops === 'string'
      ? JSON.parse(flight.route_stops)
      : flight.route_stops;

    if (!stops || stops.length === 0) return 'No route';

    return stops.map(s => s.name || getPlanetName(s.planet_id)).join(' → ');
  }

  function formatDateTime(dateStr) {
    if (!dateStr) return 'N/A';
    const d = new Date(dateStr);
    return d.toLocaleString();
  }

  async function createFlight() {
    error = '';

    if (!scheduledDeparture) {
      error = 'Scheduled departure is required.';
      return;
    }

    let stops;
    if (routeType === 'flexible') {
      // Flexible: start point required, end point optional
      const startStop = routeStops[0];
      if (!startStop.planet_id && !startStop.name) {
        error = 'Starting point is required.';
        return;
      }
      stops = [{ planet_id: startStop.planet_id, name: startStop.name || getPlanetName(startStop.planet_id) }];
      if (flexibleEndPoint.planet_id || flexibleEndPoint.name) {
        stops.push({ planet_id: flexibleEndPoint.planet_id, name: flexibleEndPoint.name || getPlanetName(flexibleEndPoint.planet_id) });
      }
    } else {
      // Fixed: at least 2 stops required
      const validStops = routeStops.filter(s => s.planet_id || s.name);
      if (validStops.length < 2) {
        error = 'At least 2 route stops are required for fixed routes.';
        return;
      }
      stops = validStops.map(s => ({
        planet_id: s.planet_id,
        name: s.name || getPlanetName(s.planet_id)
      }));
    }

    saving = true;

    try {
      const result = await apiPost(fetch, `/api/services/${service.id}/flights`, {
        scheduled_departure: new Date(scheduledDeparture).toISOString(),
        route_type: routeType,
        route_stops: stops
      });

      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }

      showCreateForm = false;
      scheduledDeparture = '';
      routeType = 'fixed';
      routeStops = [{ planet_id: null, name: '' }, { planet_id: null, name: '' }];
      flexibleEndPoint = { planet_id: null, name: '' };
      await invalidateAll();
    } catch (e) {
      error = 'Failed to create flight.';
    } finally {
      saving = false;
    }
  }

  async function flightAction(flightId, action) {
    saving = true;
    error = '';

    try {
      const result = await apiPut(fetch, `/api/services/${service.id}/flights/${flightId}`, { action });

      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }

      await invalidateAll();
    } catch (e) {
      error = 'Failed to update flight.';
    } finally {
      saving = false;
    }
  }

  $: activeFlights = flights.filter(f => !['completed', 'cancelled'].includes(f.status));
  $: cancelledFlights = flights.filter(f => f.status === 'cancelled' && canRestoreFlight(f, activeFlights));
  $: pastFlights = flights.filter(f => f.status === 'completed' || (f.status === 'cancelled' && !canRestoreFlight(f, activeFlights)));

  async function restoreFlight(flight) {
    if (hasFlightOverlap(flight, activeFlights)) {
      error = 'Cannot restore this flight - it overlaps within 15 minutes of another active flight. Please reschedule one of the flights first.';
      return;
    }

    if (!confirm('Restore this cancelled flight?')) return;

    await flightAction(flight.id, 'restore');
  }

  // Reschedule state
  let reschedulingFlightId = null;
  let rescheduledDeparture = '';

  function startReschedule(flight) {
    reschedulingFlightId = flight.id;
    rescheduledDeparture = toDateTimeLocalFormat(flight.scheduled_departure);
  }

  function cancelReschedule() {
    reschedulingFlightId = null;
    rescheduledDeparture = '';
  }

  async function saveReschedule() {
    if (!rescheduledDeparture) {
      error = 'Scheduled departure is required.';
      return;
    }

    saving = true;
    error = '';

    try {
      const result = await apiPut(fetch, `/api/services/${service.id}/flights/${reschedulingFlightId}`, {
        action: 'reschedule',
        scheduled_departure: rescheduledDeparture
      });

      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }

      cancelReschedule();
      await invalidateAll();
    } catch (e) {
      error = 'Failed to reschedule flight.';
    } finally {
      saving = false;
    }
  }

  // Route editing state
  let editingRouteFlightId = null;
  let editingRouteStops = [];
  let editingRouteLocked = 0;
  let pendingOptimizedRoute = null;

  function startEditRoute(flight) {
    const stops = typeof flight.route_stops === 'string'
      ? JSON.parse(flight.route_stops)
      : (flight.route_stops || []);

    editingRouteFlightId = flight.id;
    editingRouteStops = [...stops];

    // Calculate locked stops: all visited stops plus current stop plus warp target if warping
    let lockedCount = flight.current_stop_index || 0;
    if (flight.status === 'running') {
      lockedCount += 1; // Lock the current/departure stop
      if (flight.current_state?.startsWith('warp_to_')) {
        // Also lock the stop we're warping to
        lockedCount += 1;
      }
    }
    editingRouteLocked = lockedCount;
    pendingOptimizedRoute = null;
  }

  function cancelEditRoute() {
    editingRouteFlightId = null;
    editingRouteStops = [];
    editingRouteLocked = 0;
    pendingOptimizedRoute = null;
  }

  function moveStop(fromIndex, toIndex) {
    if (fromIndex < editingRouteLocked || toIndex < editingRouteLocked) return;
    if (fromIndex === toIndex) return;

    const newStops = [...editingRouteStops];
    const [removed] = newStops.splice(fromIndex, 1);
    newStops.splice(toIndex, 0, removed);
    editingRouteStops = newStops;
  }

  function removeEditStop(index) {
    if (index < editingRouteLocked) return;
    if (editingRouteStops.length <= editingRouteLocked + 1) return;
    editingRouteStops = editingRouteStops.filter((_, i) => i !== index);
  }

  function addEditStop() {
    editingRouteStops = [...editingRouteStops, { planet_id: null, name: '' }];
  }

  async function saveRouteChanges() {
    saving = true;
    error = '';

    try {
      const result = await apiPut(fetch, `/api/services/${service.id}/flights/${editingRouteFlightId}`, {
        action: 'update_route',
        route_stops: editingRouteStops
      });

      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }

      cancelEditRoute();
      await invalidateAll();
    } catch (e) {
      error = 'Failed to save route changes.';
    } finally {
      saving = false;
    }
  }

  async function optimizeRouteForFlight(flightId) {
    saving = true;
    error = '';

    try {
      const result = await apiPut(fetch, `/api/services/${service.id}/flights/${flightId}`, {
        action: 'optimize_route'
      });

      if (result.error) {
        error = result.error;
        saving = false;
        return;
      }

      // Show the optimized route for confirmation
      pendingOptimizedRoute = result.optimized_route;
      editingRouteStops = result.optimized_route;
      editingRouteLocked = result.locked_count;

      if (!result.validation?.valid) {
        error = 'Route has validation warnings: ' + result.validation.errors.join('; ');
      }
    } catch (e) {
      error = 'Failed to optimize route.';
    } finally {
      saving = false;
    }
  }

  function applyOptimizedRoute() {
    // The optimized route is already in editingRouteStops, just save it
    saveRouteChanges();
  }

  function rejectOptimizedRoute() {
    // Restore original route from the flight
    const flight = flights.find(f => f.id === editingRouteFlightId);
    if (flight) {
      const stops = typeof flight.route_stops === 'string'
        ? JSON.parse(flight.route_stops)
        : (flight.route_stops || []);
      editingRouteStops = [...stops];
    }
    pendingOptimizedRoute = null;
  }

  function copyFlight(flight, daysOffset = 0) {
    const stops = typeof flight.route_stops === 'string'
      ? JSON.parse(flight.route_stops)
      : (flight.route_stops || []);

    // For flexible routes (route_type === 'flexible'), only copy the starting point
    // For fixed routes, copy the full route
    const isFlexible = flight.route_type === 'flexible';
    if (isFlexible && stops.length > 0) {
      routeStops = [
        { planet_id: stops[0].planet_id || null, name: stops[0].name || '' },
        { planet_id: null, name: '' }
      ];
    } else {
      routeStops = stops.length > 0
        ? stops.map(s => ({ planet_id: s.planet_id || null, name: s.name || '' }))
        : [{ planet_id: null, name: '' }, { planet_id: null, name: '' }];
    }

    // Calculate new departure date
    const originalDate = new Date(flight.scheduled_departure);
    const newDate = new Date(originalDate.getTime() + (daysOffset * 24 * 60 * 60 * 1000));

    // Format for datetime-local input
    const pad = n => n.toString().padStart(2, '0');
    scheduledDeparture = `${newDate.getFullYear()}-${pad(newDate.getMonth() + 1)}-${pad(newDate.getDate())}T${pad(newDate.getHours())}:${pad(newDate.getMinutes())}`;

    showCreateForm = true;
    error = '';
  }

  function copyFlightNextWeek(flight) {
    copyFlight(flight, 7);
  }
</script>

<svelte:head>
  <title>Flight Dashboard | {service.title} | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="header-row">
      <a href="/market/services/{service.id}" class="back-link">&larr; Back to Service</a>
    </div>

    <h1>Flight Dashboard</h1>
    <p class="subtitle">{service.title}</p>

    {#if error}
      <div class="error-message">{error}</div>
    {/if}

    {#if showCreateForm}
      <div class="form-section">
        <h2>Schedule New Flight</h2>

        <div class="form-group">
          <label for="departure">Departure Time *</label>
          <input type="datetime-local" id="departure" bind:value={scheduledDeparture} />
        </div>

        <div class="form-group">
          <label>Route Type *</label>
          <div class="route-type-selector">
            <label class="route-type-option" class:selected={routeType === 'fixed'}>
              <input type="radio" bind:group={routeType} value="fixed" />
              <span class="route-type-label">Fixed Route</span>
              <span class="route-type-desc">Pre-defined stops in order</span>
            </label>
            <label class="route-type-option" class:selected={routeType === 'flexible'}>
              <input type="radio" bind:group={routeType} value="flexible" />
              <span class="route-type-label">Flexible Route</span>
              <span class="route-type-desc">Route determined by check-ins</span>
            </label>
          </div>
        </div>

        {#if routeType === 'fixed'}
          <div class="form-group">
            <label>Route Stops *</label>
            <div class="route-stops">
              {#each routeStops as stop, i}
                <div class="route-stop">
                  <span class="stop-number">{i + 1}</span>
                  <select bind:value={stop.planet_id} on:change={() => { stop.name = getPlanetName(stop.planet_id); }}>
                    <option value={null}>-- Select Planet --</option>
                    {#each planets as planet}
                      <option value={planet.Id}>{planet.Name}</option>
                    {/each}
                  </select>
                  {#if routeStops.length > 2}
                    <button type="button" class="remove-stop-btn" on:click={() => removeStop(i)}>x</button>
                  {/if}
                </div>
              {/each}
            </div>
            <button type="button" class="add-stop-btn" on:click={addStop}>+ Add Stop</button>
          </div>
        {:else}
          <div class="form-group">
            <label>Starting Point *</label>
            <div class="route-stop">
              <span class="stop-number">1</span>
              <select bind:value={routeStops[0].planet_id} on:change={() => { routeStops[0].name = getPlanetName(routeStops[0].planet_id); }}>
                <option value={null}>-- Select Planet --</option>
                {#each planets as planet}
                  <option value={planet.Id}>{planet.Name}</option>
                {/each}
              </select>
            </div>
            <small>Where the flight starts. Intermediate stops will be determined by customer check-ins.</small>
          </div>

          <div class="form-group">
            <label>End Point (Optional)</label>
            <div class="route-stop">
              <span class="stop-number end">E</span>
              <select bind:value={flexibleEndPoint.planet_id} on:change={() => { flexibleEndPoint.name = getPlanetName(flexibleEndPoint.planet_id); }}>
                <option value={null}>-- No specific end point --</option>
                {#each planets as planet}
                  <option value={planet.Id}>{planet.Name}</option>
                {/each}
              </select>
            </div>
            <small>Optional final destination. Leave empty for fully flexible routing.</small>
          </div>
        {/if}

        <div class="form-actions">
          <button type="button" class="cancel-btn" on:click={() => { showCreateForm = false; error = ''; }} disabled={saving}>Cancel</button>
          <button type="button" class="save-btn" on:click={createFlight} disabled={saving}>
            {saving ? 'Creating...' : 'Create Flight'}
          </button>
        </div>
      </div>
    {:else}
      <div class="actions-bar">
        <button class="create-btn" on:click={() => { showCreateForm = true; error = ''; }}>
          + Schedule New Flight
        </button>
      </div>
    {/if}

    <div class="flights-section">
      <h2>Active Flights ({activeFlights.length})</h2>

      {#if activeFlights.length === 0}
        <div class="empty-state">
          <p>No active flights.</p>
        </div>
      {:else}
        <div class="flights-list">
          {#each activeFlights as flight (flight.id)}
            <div class="flight-card">
              <div class="flight-header">
                <div class="flight-route">
                  {getRouteDisplay(flight)}
                  {#if flight.route_type === 'flexible'}
                    <span class="route-type-badge flexible">Flexible</span>
                  {:else}
                    <span class="route-type-badge fixed">Fixed</span>
                  {/if}
                </div>
                <span class="flight-status {getStatusClass(flight.status)}">{getStatusLabel(flight.status)}</span>
              </div>

              <div class="flight-info">
                <p>Departure: <strong>{formatDateTime(flight.scheduled_departure)}</strong></p>
                {#if flight.current_stop_index > 0}
                  {@const stops = typeof flight.route_stops === 'string' ? JSON.parse(flight.route_stops) : flight.route_stops}
                  <p>Current Stop: <strong>{stops[flight.current_stop_index]?.name || 'Unknown'} ({flight.current_stop_index + 1}/{stops.length})</strong></p>
                {/if}
              </div>

              {#if editingRouteFlightId === flight.id}
                <div class="route-editor">
                  <h4>Edit Route {pendingOptimizedRoute ? '(Optimized)' : ''}</h4>
                  <div class="route-stops-list">
                    {#each editingRouteStops as stop, i}
                      <div class="route-stop-edit" class:locked={i < editingRouteLocked}>
                        <span class="stop-number" class:locked={i < editingRouteLocked}>{i + 1}</span>
                        {#if i < editingRouteLocked}
                          <span class="stop-name locked">{stop.name || getPlanetName(stop.planet_id)}</span>
                          <span class="lock-icon">🔒</span>
                        {:else}
                          <select bind:value={stop.planet_id} on:change={() => { stop.name = getPlanetName(stop.planet_id); }}>
                            <option value={null}>-- Select Planet --</option>
                            {#each planets as planet}
                              <option value={planet.Id}>{planet.Name}</option>
                            {/each}
                          </select>
                          {#if i > 0}
                            <button type="button" class="move-btn" on:click={() => moveStop(i, i - 1)} disabled={i <= editingRouteLocked}>↑</button>
                          {/if}
                          {#if i < editingRouteStops.length - 1}
                            <button type="button" class="move-btn" on:click={() => moveStop(i, i + 1)}>↓</button>
                          {/if}
                          {#if editingRouteStops.length > editingRouteLocked + 1}
                            <button type="button" class="remove-stop-btn" on:click={() => removeEditStop(i)}>x</button>
                          {/if}
                        {/if}
                      </div>
                    {/each}
                  </div>
                  <button type="button" class="add-stop-btn" on:click={addEditStop}>+ Add Stop</button>

                  <div class="route-editor-actions">
                    {#if flight.route_type === 'flexible' && !pendingOptimizedRoute}
                      <button class="action-btn optimize-btn" on:click={() => optimizeRouteForFlight(flight.id)} disabled={saving}>
                        Auto-Optimize
                      </button>
                    {/if}
                    {#if pendingOptimizedRoute}
                      <button class="action-btn apply-btn" on:click={applyOptimizedRoute} disabled={saving}>
                        Accept & Save
                      </button>
                      <button class="action-btn reject-btn" on:click={rejectOptimizedRoute} disabled={saving}>
                        Reject
                      </button>
                    {:else}
                      <button class="action-btn save-route-btn" on:click={saveRouteChanges} disabled={saving}>
                        Save Changes
                      </button>
                    {/if}
                    <button class="action-btn cancel-edit-btn" on:click={cancelEditRoute} disabled={saving}>
                      Cancel
                    </button>
                  </div>
                </div>
              {:else}
                <div class="flight-actions">
                  {#if reschedulingFlightId === flight.id}
                    <div class="reschedule-form">
                      <input type="datetime-local" bind:value={rescheduledDeparture} />
                      <button class="action-btn save-btn" on:click={saveReschedule} disabled={saving}>Save</button>
                      <button class="action-btn cancel-edit-btn" on:click={cancelReschedule} disabled={saving}>Cancel</button>
                    </div>
                  {:else}
                    {#if flight.status === 'scheduled'}
                      <button class="action-btn start-btn" on:click={() => goto(`/market/services/${service.id}/flights/${flight.id}/manage`)} disabled={saving}>
                        Start Boarding
                      </button>
                    {/if}
                    {#if flight.status === 'boarding'}
                      <button class="action-btn start-btn" on:click={() => goto(`/market/services/${service.id}/flights/${flight.id}/manage`)} disabled={saving}>
                        Manage
                      </button>
                      <button class="action-btn reschedule-btn" on:click={() => startReschedule(flight)} disabled={saving}>
                        Reschedule
                      </button>
                    {/if}
                    {#if flight.status === 'running'}
                      <button class="action-btn manage-btn" on:click={() => goto(`/market/services/${service.id}/flights/${flight.id}/manage`)}>
                        Manage Flight
                      </button>
                    {/if}
                    {#if flight.status !== 'completed' && flight.status !== 'cancelled'}
                      <button class="action-btn edit-route-btn" on:click={() => startEditRoute(flight)} disabled={saving}>
                        Edit Route
                      </button>
                      <button class="action-btn cancel-flight-btn" on:click={() => flightAction(flight.id, 'cancel')} disabled={saving}>
                        Cancel
                      </button>
                    {/if}
                    <button class="action-btn copy-btn" on:click={() => copyFlight(flight)} title="Copy to new flight">
                      Copy
                    </button>
                    <button class="action-btn copy-week-btn" on:click={() => copyFlightNextWeek(flight)} title="Copy to same time next week">
                      +7 Days
                    </button>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
    </div>

    {#if cancelledFlights.length > 0}
      <div class="flights-section cancelled-flights">
        <h2>Recently Cancelled Flights ({cancelledFlights.length})</h2>
        <p class="subtitle">Can be restored within 2 hours of scheduled departure</p>
        <div class="flights-list">
          {#each cancelledFlights as flight (flight.id)}
            <div class="flight-card cancelled">
              <div class="flight-header">
                <div class="flight-route">
                  {getRouteDisplay(flight)}
                  {#if flight.route_type === 'flexible'}
                    <span class="route-type-badge flexible">Flexible</span>
                  {:else}
                    <span class="route-type-badge fixed">Fixed</span>
                  {/if}
                </div>
                <span class="flight-status {getStatusClass(flight.status)}">{getStatusLabel(flight.status)}</span>
              </div>
              <div class="flight-info">
                <p>Scheduled: <strong>{formatDateTime(flight.scheduled_departure)}</strong></p>
              </div>
              <div class="flight-actions">
                <button class="action-btn restore-btn" on:click={() => restoreFlight(flight)} disabled={saving}>
                  Restore
                </button>
                <button class="action-btn copy-btn" on:click={() => copyFlight(flight)} title="Copy to new flight">
                  Copy
                </button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if pastFlights.length > 0}
      <div class="flights-section past-flights">
        <h2>Flight History ({pastFlights.length})</h2>
        <div class="flights-list">
          {#each pastFlights.slice(0, 10) as flight (flight.id)}
            <div class="flight-card past">
              <div class="flight-header">
                <div class="flight-route">
                  {getRouteDisplay(flight)}
                  {#if flight.route_type === 'flexible'}
                    <span class="route-type-badge flexible">Flexible</span>
                  {:else}
                    <span class="route-type-badge fixed">Fixed</span>
                  {/if}
                </div>
                <span class="flight-status {getStatusClass(flight.status)}">{getStatusLabel(flight.status)}</span>
              </div>
              <div class="flight-info">
                <p>Scheduled: {formatDateTime(flight.scheduled_departure)}</p>
              </div>
              <div class="flight-actions">
                <button class="action-btn copy-btn" on:click={() => copyFlight(flight)} title="Copy to new flight">
                  Copy
                </button>
                <button class="action-btn copy-week-btn" on:click={() => copyFlightNextWeek(flight)} title="Copy to same time next week">
                  +7 Days
                </button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    padding: 1rem;
    padding-bottom: 2rem;
    max-width: 900px;
    margin: 0 auto;
    box-sizing: border-box;
  }

  .header-row { margin-bottom: 1rem; }

  .back-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .back-link:hover { text-decoration: underline; }

  h1 { margin: 0 0 0.25rem 0; }
  h2 { margin: 1.5rem 0 1rem 0; }

  .subtitle {
    margin: 0 0 1.5rem 0;
    color: var(--text-muted, #888);
  }

  .error-message {
    background: var(--error-bg, #fee2e2);
    border: 1px solid var(--error-color, #ef4444);
    color: var(--error-color, #dc2626);
    padding: 0.75rem 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .actions-bar { margin-bottom: 1rem; }

  .create-btn {
    background: var(--accent-color, #4a9eff);
    color: white;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 4px;
    font-size: 1rem;
    cursor: pointer;
    font-weight: 500;
  }

  .create-btn:hover { background: var(--accent-color-hover, #3a8eef); }

  .form-section {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .form-section h2 {
    margin: 0 0 1rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #666;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: 500;
  }

  .form-group small {
    display: block;
    margin-top: 0.25rem;
    color: var(--text-muted, #888);
    font-size: 0.85rem;
  }

  .route-type-selector {
    display: flex;
    gap: 1rem;
  }

  .route-type-option {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    border: 2px solid #555;
    border-radius: 8px;
    cursor: pointer;
    transition: border-color 0.15s, background-color 0.15s;
  }

  .route-type-option:hover {
    border-color: #777;
  }

  .route-type-option.selected {
    border-color: var(--accent-color, #4a9eff);
    background: rgba(74, 158, 255, 0.1);
  }

  .route-type-option input[type="radio"] {
    display: none;
  }

  .route-type-label {
    font-weight: 600;
    margin-bottom: 0.25rem;
  }

  .route-type-desc {
    font-size: 0.85rem;
    color: var(--text-muted, #888);
  }

  .form-group input,
  .form-group select {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    font-size: 1rem;
    box-sizing: border-box;
    background-color: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .route-stops {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .route-stop {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .stop-number {
    width: 24px;
    height: 24px;
    background: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.8rem;
    font-weight: 600;
    flex-shrink: 0;
  }

  .stop-number.end {
    background: var(--success-color, #10b981);
  }

  .route-stop select {
    flex: 1;
  }

  .remove-stop-btn {
    background: #e74c3c;
    color: white;
    border: none;
    width: 24px;
    height: 24px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
  }

  .add-stop-btn {
    margin-top: 0.5rem;
    background: none;
    border: 1px dashed #666;
    color: var(--text-muted, #888);
    padding: 0.5rem;
    border-radius: 4px;
    cursor: pointer;
    width: 100%;
  }

  .add-stop-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .form-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    margin-top: 1rem;
  }

  .cancel-btn, .save-btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    font-size: 0.95rem;
    cursor: pointer;
  }

  .cancel-btn {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid #666;
  }

  .save-btn {
    background: var(--accent-color, #4a9eff);
    color: white;
  }

  .empty-state {
    background: var(--secondary-color);
    border: 1px dashed #666;
    border-radius: 8px;
    padding: 2rem;
    text-align: center;
    color: var(--text-muted, #888);
  }

  .flights-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .flight-card {
    background: var(--secondary-color);
    border: 1px solid #555;
    border-radius: 8px;
    padding: 1rem;
  }

  .flight-card.past {
    opacity: 0.7;
  }

  .flight-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .flight-route {
    font-weight: 600;
    font-size: 1.05rem;
  }

  .flight-status {
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .status-scheduled { background: rgba(74, 158, 255, 0.2); color: var(--accent-color, #4a9eff); }
  .status-boarding { background: rgba(245, 158, 11, 0.2); color: var(--warning-color, #f59e0b); }
  .status-running { background: rgba(16, 185, 129, 0.2); color: var(--success-color, #10b981); }
  .status-completed { background: rgba(107, 114, 128, 0.2); color: var(--text-muted, #9ca3af); }
  .status-cancelled { background: rgba(239, 68, 68, 0.2); color: var(--error-color, #ef4444); }

  .flight-info {
    font-size: 0.9rem;
    color: var(--text-muted, #888);
  }

  .flight-info p {
    margin: 0.25rem 0;
  }

  .flight-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 0.75rem;
    padding-top: 0.75rem;
    border-top: 1px solid #444;
  }

  .action-btn {
    padding: 0.4rem 0.8rem;
    border: none;
    border-radius: 4px;
    font-size: 0.85rem;
    cursor: pointer;
    font-weight: 500;
  }

  .start-btn { background: #10b981; color: white; }
  .start-btn:hover:not(:disabled) { background: #059669; }
  .advance-btn { background: #4a9eff; color: white; }
  .advance-btn:hover:not(:disabled) { background: #3a8eef; }
  .undo-btn { background: #f59e0b; color: white; }
  .undo-btn:hover:not(:disabled) { background: #d97706; }
  .cancel-flight-btn { background: #e74c3c; color: white; }
  .cancel-flight-btn:hover:not(:disabled) { background: #c0392b; }
  .restore-btn { background: #8b5cf6; color: white; }
  .restore-btn:hover:not(:disabled) { background: #7c3aed; }
  .copy-btn { background: #6b7280; color: white; }
  .copy-btn:hover:not(:disabled) { background: #4b5563; }
  .copy-week-btn { background: #0ea5e9; color: white; }
  .copy-week-btn:hover:not(:disabled) { background: #0284c7; }

  .action-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .past-flights { opacity: 0.8; }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .route-type-badge {
    display: inline-block;
    margin-left: 0.5rem;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    font-size: 0.7rem;
    font-weight: 500;
    vertical-align: middle;
  }

  .route-type-badge.fixed {
    background: #6b728033;
    color: #9ca3af;
  }

  .route-type-badge.flexible {
    background: #8b5cf633;
    color: #a78bfa;
  }

  .route-editor {
    margin-top: 1rem;
    padding: 1rem;
    background: var(--bg-color, #1a1a1a);
    border: 1px solid #666;
    border-radius: 6px;
  }

  .route-editor h4 {
    margin: 0 0 0.75rem 0;
    font-size: 0.95rem;
  }

  .route-stops-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .route-stop-edit {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .route-stop-edit select {
    flex: 1;
    min-width: 0;
    padding: 0.5rem;
    background: var(--secondary-color);
    border: 1px solid #444;
    border-radius: 4px;
    color: var(--text-color);
    font-size: 1rem;
  }

  .route-stop-edit.locked {
    opacity: 0.7;
  }

  .route-stop-edit .stop-number.locked {
    background: #6b7280;
  }

  .route-stop-edit .stop-name.locked {
    flex: 1;
    padding: 0.5rem;
    background: var(--secondary-color);
    border: 1px solid #444;
    border-radius: 4px;
    color: var(--text-muted, #888);
  }

  .lock-icon {
    font-size: 0.9rem;
    color: var(--text-muted, #888);
  }

  .move-btn {
    background: var(--secondary-color);
    border: 1px solid #555;
    color: var(--text-color);
    width: 28px;
    height: 28px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
  }

  .move-btn:hover:not(:disabled) {
    background: var(--hover-color);
  }

  .route-editor-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid #555;
  }

  .edit-route-btn { background: #6366f1; color: white; }
  .edit-route-btn:hover:not(:disabled) { background: #4f46e5; }
  .optimize-btn { background: #8b5cf6; color: white; }
  .optimize-btn:hover:not(:disabled) { background: #7c3aed; }
  .save-route-btn { background: #10b981; color: white; }
  .save-route-btn:hover:not(:disabled) { background: #059669; }
  .apply-btn { background: #10b981; color: white; }
  .apply-btn:hover:not(:disabled) { background: #059669; }
  .reject-btn { background: #ef4444; color: white; }
  .reject-btn:hover:not(:disabled) { background: #dc2626; }
  .cancel-edit-btn { background: #6b7280; color: white; }
  .cancel-edit-btn:hover:not(:disabled) { background: #4b5563; }
</style>
