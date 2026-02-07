<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';

  export let data;

  $: flight = data.flight;
  $: service = data.service;
  $: checkins = data.checkins || [];
  $: stateLog = data.stateLog || [];
  $: user = data.session?.user;
  $: isOwner = user && service && (user.id === service.user_id || user.grants?.includes('admin.panel'));

  let routeStops = [];
  let currentStopIndex = 0;
  let showOptimizedRoute = false;
  let optimizedRoute = [];
  let optimizedValidation = null;

  // Pending action system - delays API calls until 10s undo period elapses
  let pendingAction = null; // 'board', 'start', 'advance'
  let pendingCountdown = 0;
  let pendingInterval = null;
  let pendingStartTime = null;

  // For displaying the "projected" state during pending period
  $: projectedStatus = pendingAction === 'board' ? 'boarding'
    : pendingAction === 'start' ? 'running'
    : flight?.status;
  $: projectedState = pendingAction === 'start' ? 'departing'
    : pendingAction === 'advance' ? getNextState()
    : flight?.current_state;
  $: projectedStopIndex = pendingAction === 'advance' ? getNextStopIndex() : (flight?.current_stop_index || 0);

  function getNextState() {
    const currentState = flight?.current_state || 'departing';
    const stopIndex = flight?.current_stop_index || 0;

    if (currentState === 'departing' || currentState.startsWith('at_stop_')) {
      // Currently at a stop, next is warp to next stop
      const nextIdx = stopIndex + 1;
      if (nextIdx >= routeStops.length) {
        return 'arrived';
      }
      return `warp_to_${nextIdx}`;
    } else if (currentState.startsWith('warp_to_')) {
      // In warp, next is arrival at that stop
      const targetStop = parseInt(currentState.split('_')[2]);
      return `at_stop_${targetStop}`;
    }
    return currentState;
  }

  function getNextStopIndex() {
    const currentState = flight?.current_state || 'departing';
    const stopIndex = flight?.current_stop_index || 0;

    if (currentState?.startsWith('warp_to_')) {
      // Arriving at stop means we update the index
      return parseInt(currentState.split('_')[2]);
    }
    return stopIndex;
  }

  $: if (flight && !pendingAction) {
    routeStops = typeof flight.route_stops === 'string'
      ? JSON.parse(flight.route_stops)
      : (flight.route_stops || []);
    currentStopIndex = flight.current_stop_index || 0;
  }

  // Start pending action countdown
  function startPendingAction(action) {
    pendingAction = action;
    pendingCountdown = 10;
    pendingStartTime = Date.now();

    if (pendingInterval) clearInterval(pendingInterval);

    pendingInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - pendingStartTime) / 1000);
      pendingCountdown = Math.max(0, 10 - elapsed);

      if (pendingCountdown <= 0) {
        executePendingAction();
      }
    }, 100);
  }

  // Cancel pending action (undo before it's sent)
  function cancelPendingAction() {
    if (pendingInterval) clearInterval(pendingInterval);
    pendingAction = null;
    pendingCountdown = 0;
    pendingStartTime = null;
  }

  // Execute the pending action after countdown
  async function executePendingAction() {
    if (pendingInterval) clearInterval(pendingInterval);

    const action = pendingAction;
    pendingAction = null;
    pendingCountdown = 0;
    pendingStartTime = null;

    if (!action) return;

    try {
      const response = await fetch(`/api/services/${service.id}/flights/${flight.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });

      const result = await response.json();
      if (result.error) {
        alert(result.error);
      } else {
        location.reload();
      }
    } catch (e) {
      alert(`Failed to ${action}. Please try again.`);
    }
  }

  onDestroy(() => {
    if (pendingInterval) clearInterval(pendingInterval);
  });

  // Start boarding
  function startBoarding() {
    if (pendingAction) return; // Already have a pending action

    // Check if flight is more than 15 minutes in the future
    const scheduledTime = new Date(flight.scheduled_departure);
    const now = new Date();
    const minutesUntilDeparture = (scheduledTime - now) / (1000 * 60);

    if (minutesUntilDeparture > 15) {
      const hours = Math.floor(minutesUntilDeparture / 60);
      const minutes = Math.floor(minutesUntilDeparture % 60);
      let timeString = '';
      if (hours > 0) {
        timeString = `${hours} hour${hours > 1 ? 's' : ''} ${minutes} minute${minutes !== 1 ? 's' : ''}`;
      } else {
        timeString = `${Math.floor(minutesUntilDeparture)} minutes`;
      }

      if (!confirm(`Warning: This flight is not supposed to start for ${timeString}.\n\nAre you sure you want to start boarding early?`)) {
        return;
      }
    }

    if (!confirm('Start boarding? A Discord thread will be created for this flight.')) return;

    startPendingAction('board');
  }

  // Check if there are pending check-ins
  $: pendingCheckins = checkins.filter(c => c.status === 'pending');
  $: hasPendingCheckins = pendingCheckins.length > 0;
  $: isFlexibleRoute = (flight?.route_type || 'fixed') === 'flexible';

  // Start flight (from boarding status)
  function startFlight() {
    if (pendingAction) return;

    // For flexible routes, check if there are pending check-ins
    if (isFlexibleRoute && hasPendingCheckins) {
      alert(`Cannot start flight with ${pendingCheckins.length} pending check-in(s). Please accept or decline all check-ins first.`);
      return;
    }

    const routeType = flight.route_type || 'fixed';
    let confirmMsg = 'Start the flight?';
    if (routeType === 'flexible') {
      confirmMsg = 'Start this flight? Check-ins will be closed and no more passengers can board.';
    }

    if (!confirm(confirmMsg)) return;

    startPendingAction('start');
  }

  // Advance route (includes warp step)
  function advanceRoute() {
    if (pendingAction) return;
    startPendingAction('advance');
  }

  // Undo/cancel - either cancels pending action or shows error if nothing pending
  function undoAction() {
    if (pendingAction) {
      cancelPendingAction();
    }
  }

  // Cancel flight with double warning
  async function cancelFlight() {
    if (flight.status === 'running') {
      if (!confirm('⚠️ WARNING: This flight is currently ACTIVE! Cancelling will interrupt all passengers. Are you ABSOLUTELY SURE?')) {
        return;
      }
      if (!confirm('⚠️ FINAL WARNING: This action cannot be easily undone. Cancel this active flight?')) {
        return;
      }
    } else {
      if (!confirm('Cancel this flight?')) return;
    }

    try {
      const response = await fetch(`/api/services/${service.id}/flights/${flight.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'cancel' })
      });

      const result = await response.json();
      if (result.error) {
        alert(result.error);
      } else {
        alert('Flight cancelled.');
        goto(`/market/services/${service.id}/flights`);
      }
    } catch (e) {
      alert('Failed to cancel flight. Please try again.');
    }
  }

  // Optimize route (flexible routes only)
  async function optimizeRoute() {
    try {
      const response = await fetch(`/api/services/${service.id}/flights/${flight.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'optimize_route' })
      });

      const result = await response.json();
      if (result.error) {
        alert(result.error);
      } else {
        optimizedRoute = result.optimized_route || [];
        optimizedValidation = result.validation;
        showOptimizedRoute = true;
      }
    } catch (e) {
      alert('Failed to optimize route. Please try again.');
    }
  }

  // Accept optimized route
  async function acceptOptimizedRoute() {
    try {
      const response = await fetch(`/api/services/${service.id}/flights/${flight.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'update_route', route_stops: optimizedRoute })
      });

      const result = await response.json();
      if (result.error) {
        alert(result.error);
      } else {
        showOptimizedRoute = false;
        location.reload();
      }
    } catch (e) {
      alert('Failed to update route. Please try again.');
    }
  }

  // Reject optimized route
  function rejectOptimizedRoute() {
    showOptimizedRoute = false;
    optimizedRoute = [];
    optimizedValidation = null;
  }

  // Accept check-in
  async function acceptCheckin(checkinId) {
    try {
      const response = await fetch(`/api/flights/${flight.id}/checkins/${checkinId}/accept`, {
        method: 'PUT'
      });

      const result = await response.json();
      if (result.error) {
        alert(result.error);
      } else {
        location.reload();
      }
    } catch (e) {
      alert('Failed to accept check-in. Please try again.');
    }
  }

  // Deny check-in
  async function denyCheckin(checkinId) {
    const reason = prompt('Enter reason for denial (optional):');

    try {
      const response = await fetch(`/api/flights/${flight.id}/checkins/${checkinId}/deny`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
      });

      const result = await response.json();
      if (result.error) {
        alert(result.error);
      } else {
        location.reload();
      }
    } catch (e) {
      alert('Failed to deny check-in. Please try again.');
    }
  }

  // Refund check-in
  async function refundCheckin(checkinId) {
    if (!confirm('Refund this check-in? The ticket use will be restored to the customer.')) return;

    try {
      const response = await fetch(`/api/flights/${flight.id}/checkins/${checkinId}/refund`, {
        method: 'POST'
      });

      const result = await response.json();
      if (result.error) {
        alert(result.error);
      } else {
        alert('Check-in refunded. Ticket use has been restored.');
        location.reload();
      }
    } catch (e) {
      alert('Failed to refund check-in. Please try again.');
    }
  }

  // Check if refund is allowed (within 1 hour of flight completion)
  function canRefundCheckin(checkin) {
    if (checkin.status !== 'accepted') return false;

    // Allow refund if flight not completed yet
    if (flight.status !== 'completed') return true;

    // If completed, check if within 1 hour
    if (!flight.completed_at) return false;

    const completedAt = new Date(flight.completed_at);
    const now = new Date();
    const hoursSinceCompletion = (now - completedAt) / (1000 * 60 * 60);

    return hoursSinceCompletion <= 1;
  }

  // Get status badge class
  function getStatusClass(status) {
    return status?.toLowerCase() || 'pending';
  }

  // Get current state description
  function getCurrentStateDescription() {
    if (!flight) return '';

    if (flight.status === 'scheduled') return 'Flight not started';
    if (flight.status === 'boarding') return 'Boarding passengers';
    if (flight.status === 'completed') return 'Flight completed';
    if (flight.status === 'cancelled') return 'Flight cancelled';

    if (flight.status === 'running') {
      if (flight.current_state?.startsWith('at_stop_')) {
        const stopNum = parseInt(flight.current_state.split('_')[2]);
        const stop = routeStops[stopNum];
        return `At ${stop?.name || 'Unknown'}`;
      }
      if (flight.current_state === 'departing') {
        return 'Departing from start';
      }
      if (flight.current_state?.startsWith('warp_to_')) {
        const stopNum = parseInt(flight.current_state.split('_')[2]);
        const stop = routeStops[stopNum];
        return `In warp to ${stop?.name || 'Unknown'}`;
      }
      return 'In transit';
    }

    return flight.status;
  }

  // Get advance button text with specific planet name
  function getAdvanceButtonText() {
    if (!flight || !flight.current_state) return 'Advance';

    if (flight.current_state === 'departing') {
      // Next state will be warp_to_1
      const nextStop = routeStops[1];
      return nextStop ? `Enter warp to ${nextStop.name}` : 'Enter Warp';
    }

    if (flight.current_state.startsWith('at_stop_')) {
      const currentStopNum = parseInt(flight.current_state.split('_')[2]);
      const nextStopNum = currentStopNum + 1;
      const nextStop = routeStops[nextStopNum];

      if (nextStop) {
        return `Enter warp to ${nextStop.name}`;
      }
      return 'Complete Flight';
    }

    if (flight.current_state.startsWith('warp_to_')) {
      const targetStopNum = parseInt(flight.current_state.split('_')[2]);
      const targetStop = routeStops[targetStopNum];

      if (targetStop) {
        return `Dock at ${targetStop.name}`;
      }
      return 'Dock at Stop';
    }

    return 'Advance';
  }
</script>

<div class="scroll-container">
<div class="page-container">
  <div class="header-row">
    <a href="/market/services/{service.id}/flights" class="back-link">&larr; Back to Dashboard</a>
  </div>

  <h1>Flight Management</h1>

  {#if !isOwner}
    <p class="error-message">You do not have permission to manage this flight.</p>
  {:else if !flight}
    <p class="error-message">Flight not found.</p>
  {:else}
    <div class="flight-overview">
      <div class="overview-section">
        <h2>Flight Status</h2>
        <div class="status-badge {getStatusClass(projectedStatus)} {pendingAction ? 'pending' : ''}">{projectedStatus}</div>
        {#if pendingAction}
          <p class="state-description pending-state">Pending confirmation...</p>
        {:else}
          <p class="state-description">{getCurrentStateDescription()}</p>
        {/if}
        <p><strong>Route Type:</strong> {flight.route_type === 'flexible' ? 'Flexible' : 'Fixed'}</p>
        <p><strong>Scheduled Departure:</strong> {new Date(flight.scheduled_departure).toLocaleString()}</p>
        {#if flight.actual_departure}
          <p><strong>Actual Departure:</strong> {new Date(flight.actual_departure).toLocaleString()}</p>
        {/if}
      </div>

      <div class="overview-section">
        <h2>Route Progress</h2>
        <div class="route-progress">
          {#each routeStops as stop, i}
            {@const isInWarpToNext = flight.current_state?.startsWith('warp_to_') && parseInt(flight.current_state.split('_')[2]) === i + 1}
            {@const isCurrentStop = i === currentStopIndex && !flight.current_state?.startsWith('warp_to_')}
            {@const isPastStop = i < currentStopIndex || (i === currentStopIndex && flight.current_state?.startsWith('warp_to_'))}
            <div class="route-stop {isPastStop ? 'visited' : ''} {isCurrentStop ? 'current' : ''}">
              <div class="stop-number">{i + 1}</div>
              <div class="stop-name">{stop.name || `Planet ${stop.planet_id}`}</div>
            </div>
            {#if i < routeStops.length - 1}
              {@const arrowCompleted = i < currentStopIndex || (i === currentStopIndex && flight.current_state?.startsWith('warp_to_'))}
              <div class="route-arrow {arrowCompleted ? 'completed' : ''} {isInWarpToNext ? 'in-warp' : ''}">→</div>
            {/if}
          {/each}
        </div>
      </div>
    </div>

    <!-- Flexible Route Boarding Reminder -->
    {#if isFlexibleRoute && flight.status === 'boarding' && !pendingAction}
      <div class="flexible-reminder">
        <h3>Flexible Route Checklist</h3>
        <ul>
          <li class={hasPendingCheckins ? 'incomplete' : 'complete'}>
            {#if hasPendingCheckins}
              {pendingCheckins.length} pending check-in(s) - accept or decline all before starting
            {:else}
              All check-ins processed
            {/if}
          </li>
          <li>Review and optimize the route based on accepted passengers</li>
        </ul>
        <button on:click={optimizeRoute} class="btn btn-secondary" disabled={showOptimizedRoute}>
          Optimize Route
        </button>
      </div>
    {/if}

    <!-- Flight Controls -->
    <div class="controls-section">
      <h2>Flight Controls</h2>

      {#if pendingAction}
        <div class="pending-indicator">
          <span class="pending-text">
            {#if pendingAction === 'board'}
              Starting boarding...
            {:else if pendingAction === 'start'}
              Starting flight...
            {:else if pendingAction === 'advance'}
              Advancing route...
            {/if}
          </span>
          <span class="pending-countdown">({pendingCountdown}s)</span>
        </div>
      {/if}

      <div class="control-buttons">
        {#if flight.status === 'scheduled' && !pendingAction}
          <button on:click={startBoarding} class="btn btn-primary">Start Boarding</button>
        {/if}

        {#if flight.status === 'boarding' && !pendingAction}
          <button on:click={startFlight} class="btn btn-primary" disabled={isFlexibleRoute && hasPendingCheckins}>
            Start Flight
          </button>
        {/if}

        {#if flight.status === 'running' && !pendingAction}
          <button on:click={advanceRoute} class="btn btn-primary">
            {getAdvanceButtonText()}
          </button>
        {/if}

        {#if pendingAction}
          <button on:click={undoAction} class="btn btn-warning">
            Undo ({pendingCountdown}s)
          </button>
        {/if}

        {#if flight.route_type === 'flexible' && flight.status === 'running' && !showOptimizedRoute && !pendingAction}
          <button on:click={optimizeRoute} class="btn btn-secondary">Optimize Route</button>
        {/if}

        {#if flight.status !== 'completed' && flight.status !== 'cancelled' && !pendingAction}
          <button on:click={cancelFlight} class="btn btn-danger">Cancel Flight</button>
        {/if}
      </div>
    </div>

    <!-- Optimized Route Preview -->
    {#if showOptimizedRoute}
      <div class="optimized-route-section">
        <h2>Optimized Route Preview</h2>
        {#if optimizedValidation && !optimizedValidation.valid}
          <div class="validation-errors">
            <p class="error-message"><strong>Validation Errors:</strong></p>
            <ul>
              {#each optimizedValidation.errors as error}
                <li>{error}</li>
              {/each}
            </ul>
          </div>
        {/if}
        <div class="route-comparison">
          <div class="route-column">
            <h3>Current Route</h3>
            <ol>
              {#each routeStops as stop}
                <li>{stop.name || `Planet ${stop.planet_id}`}</li>
              {/each}
            </ol>
          </div>
          <div class="route-column">
            <h3>Optimized Route</h3>
            <ol>
              {#each optimizedRoute as stop}
                <li>{stop.name || `Planet ${stop.planet_id}`}</li>
              {/each}
            </ol>
          </div>
        </div>
        <div class="route-actions">
          <button on:click={acceptOptimizedRoute} class="btn btn-primary">Accept & Apply</button>
          <button on:click={rejectOptimizedRoute} class="btn btn-secondary">Reject</button>
        </div>
      </div>
    {/if}

    <!-- Check-ins Management -->
    <div class="checkins-section">
      <h2>Check-ins ({checkins.length})</h2>
      {#if checkins.length === 0}
        <p class="muted-text">No check-ins for this flight.</p>
      {:else}
        <div class="checkins-list">
          {#each checkins as checkin}
            <div class="checkin-card {getStatusClass(checkin.status)}">
              <div class="checkin-header">
                <strong>{checkin.user_name}</strong>
                <span class="checkin-status {getStatusClass(checkin.status)}">{checkin.status}</span>
              </div>
              <div class="checkin-details">
                <p><strong>Ticket:</strong> {checkin.offer_name}</p>
                {#if checkin.join_location}
                  <p><strong>Pickup:</strong> {checkin.join_location}</p>
                {/if}
                {#if checkin.exit_location}
                  <p><strong>Dropoff:</strong> {checkin.exit_location}</p>
                {/if}
                <p class="checkin-time">Checked in: {new Date(checkin.checked_in_at).toLocaleString()}</p>
              </div>
              {#if checkin.status === 'pending'}
                <div class="checkin-actions">
                  <button on:click={() => acceptCheckin(checkin.id)} class="btn btn-sm btn-success">Accept</button>
                  <button on:click={() => denyCheckin(checkin.id)} class="btn btn-sm btn-danger">Deny</button>
                </div>
              {:else if canRefundCheckin(checkin)}
                <div class="checkin-actions">
                  <button on:click={() => refundCheckin(checkin.id)} class="btn btn-sm btn-warning">Refund</button>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      {/if}
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
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
    padding-bottom: 3rem;
  }
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
  }

  .page-header h1 {
    margin: 0;
  }

  .back-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .back-link:hover {
    text-decoration: underline;
  }

  .flight-overview {
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 1.5rem;
    margin-bottom: 2rem;
  }

  .overview-section {
    background: #2a2a2a;
    padding: 1.5rem;
    border-radius: 8px;
  }

  .overview-section h2 {
    margin: 0 0 1rem 0;
    font-size: 1.25rem;
  }

  .overview-section p {
    margin: 0.5rem 0;
  }

  .status-badge {
    display: inline-block;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.875rem;
  }

  .status-badge.scheduled {
    background: #2a5a3a;
    color: #6fdc8c;
  }

  .status-badge.boarding {
    background: #5a4a2a;
    color: #ffc107;
  }

  .status-badge.running {
    background: #2a4a5a;
    color: #4a9eff;
  }

  .status-badge.completed {
    background: #3a3a5a;
    color: #9f9fff;
  }

  .status-badge.cancelled {
    background: #5a2a2a;
    color: #ff6b6b;
  }

  .status-badge.pending {
    animation: pulse-pending 1s ease-in-out infinite;
  }

  @keyframes pulse-pending {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }

  .state-description {
    font-size: 1.1rem;
    color: #bbb;
    margin-top: 0.5rem !important;
  }

  .state-description.pending-state {
    color: #f59e0b;
    font-style: italic;
  }

  .route-progress {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .route-stop {
    display: flex;
    flex-direction: column;
    align-items: center;
    opacity: 0.5;
    min-width: 40px;
  }

  .route-stop.visited {
    opacity: 1;
  }

  .route-stop.current {
    opacity: 1;
  }

  .route-stop.current .stop-number {
    background: #4a9eff;
    animation: pulse 2s infinite;
  }

  .route-stop.visited .stop-number {
    background: #4caf50;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }

  .stop-number {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: #3a3a3a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
  }

  .stop-name {
    font-size: 0.75rem;
    margin-top: 0.25rem;
    text-align: center;
    max-width: 90px;
    word-wrap: break-word;
  }

  .route-arrow {
    color: #555;
    font-size: 1.5rem;
    flex-shrink: 0;
    margin-top: -1.5rem;
  }

  .route-arrow.completed {
    color: #4caf50;
  }

  .route-arrow.in-warp {
    color: #4a9eff;
    animation: warp-pulse 1.5s infinite;
  }

  @keyframes warp-pulse {
    0%, 100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.7;
      transform: scale(1.2);
    }
  }

  .flexible-reminder {
    background: #2a3a4a;
    border: 1px solid #4a9eff;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
  }

  .flexible-reminder h3 {
    margin: 0 0 1rem 0;
    color: #4a9eff;
    font-size: 1.1rem;
  }

  .flexible-reminder ul {
    margin: 0 0 1rem 0;
    padding-left: 1.5rem;
  }

  .flexible-reminder li {
    margin: 0.5rem 0;
  }

  .flexible-reminder li.complete {
    color: #4caf50;
  }

  .flexible-reminder li.complete::marker {
    content: "✓ ";
  }

  .flexible-reminder li.incomplete {
    color: #f59e0b;
  }

  .flexible-reminder li.incomplete::marker {
    content: "⚠ ";
  }

  .controls-section {
    background: #2a2a2a;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 2rem;
  }

  .controls-section h2 {
    margin: 0 0 1rem 0;
  }

  .pending-indicator {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: #f59e0b33;
    border: 1px solid #f59e0b;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .pending-text {
    font-weight: 600;
    color: #f59e0b;
  }

  .pending-countdown {
    color: #f59e0b;
    font-family: monospace;
    font-size: 1.1em;
  }

  .control-buttons {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 4px;
    font-weight: 600;
    cursor: pointer;
    font-size: 1rem;
  }

  .btn-primary {
    background: #4a9eff;
    color: white;
  }

  .btn-primary:hover {
    background: #3a8eef;
  }

  .btn-secondary {
    background: #6c757d;
    color: white;
  }

  .btn-secondary:hover {
    background: #5a6268;
  }

  .btn-warning {
    background: #ff9800;
    color: white;
  }

  .btn-warning:hover {
    background: #f57c00;
  }

  .btn-danger {
    background: #dc3545;
    color: white;
  }

  .btn-danger:hover {
    background: #c82333;
  }

  .btn-success {
    background: #28a745;
    color: white;
  }

  .btn-success:hover {
    background: #218838;
  }

  .btn-sm {
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
  }

  .optimized-route-section {
    background: #2a2a2a;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 2rem;
  }

  .optimized-route-section h2 {
    margin: 0 0 1rem 0;
  }

  .validation-errors {
    background: #5a2a2a;
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .validation-errors ul {
    margin: 0.5rem 0 0 1.5rem;
  }

  .route-comparison {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 2rem;
    margin-bottom: 1rem;
  }

  .route-column h3 {
    margin: 0 0 0.5rem 0;
  }

  .route-column ol {
    margin: 0;
    padding-left: 1.5rem;
  }

  .route-column li {
    margin: 0.25rem 0;
  }

  .route-actions {
    display: flex;
    gap: 1rem;
  }

  .checkins-section {
    background: #2a2a2a;
    padding: 1.5rem;
    border-radius: 8px;
  }

  .checkins-section h2 {
    margin: 0 0 1rem 0;
  }

  .checkins-list {
    display: grid;
    gap: 1rem;
  }

  .checkin-card {
    background: #1a1a1a;
    padding: 1rem;
    border-radius: 4px;
    border-left: 4px solid #3a3a3a;
  }

  .checkin-card.pending {
    border-left-color: #ffc107;
  }

  .checkin-card.accepted {
    border-left-color: #4caf50;
  }

  .checkin-card.denied {
    border-left-color: #dc3545;
  }

  .checkin-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .checkin-status {
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .checkin-status.pending {
    background: #5a4a2a;
    color: #ffc107;
  }

  .checkin-status.accepted {
    background: #2a5a3a;
    color: #6fdc8c;
  }

  .checkin-status.denied {
    background: #5a2a2a;
    color: #ff6b6b;
  }

  .checkin-status.refunded {
    background: #5a4a2a;
    color: #ff9800;
  }

  .checkin-card.refunded {
    border-left-color: #ff9800;
  }

  .checkin-details p {
    margin: 0.25rem 0;
    font-size: 0.875rem;
  }

  .checkin-time {
    color: #888;
    font-size: 0.75rem !important;
    margin-top: 0.5rem !important;
  }

  .checkin-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  .error-message {
    color: #ff6b6b;
  }

  .muted-text {
    color: #888;
    font-style: italic;
  }
</style>
