<script>
  // @ts-nocheck
  export let serviceId;
  export let pilots = [];
  export let isOwner = false;

  // Manager/owner role props
  export let managerId = null;
  export let managerName = '';
  export let ownerUserId = null;
  export let ownerDisplayName = '';
  export let currentUserId = null;

  let adding = false;
  let removing = false;
  let transferring = false;
  let identifier = '';
  let error = '';
  let success = '';

  $: isManagerOrOwner = currentUserId && (currentUserId === managerId || currentUserId === ownerUserId);
  $: ownerIsDifferent = ownerDisplayName || (ownerUserId && ownerUserId !== managerId);

  async function addPilot() {
    if (!identifier.trim()) {
      error = 'Please enter a username or Discord tag.';
      return;
    }

    adding = true;
    error = '';
    success = '';

    try {
      const response = await fetch(`/api/services/${serviceId}/pilots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ identifier: identifier.trim() })
      });

      const result = await response.json();

      if (result.error) {
        error = result.error;
      } else {
        success = result.message || 'Pilot added successfully.';
        identifier = '';
        // Refresh pilot list
        await fetchPilots();
        setTimeout(() => { success = ''; }, 3000);
      }
    } catch (e) {
      error = 'Failed to add pilot.';
    } finally {
      adding = false;
    }
  }

  async function removePilot(userId) {
    if (!confirm('Remove this pilot? They will no longer be able to manage flights.')) {
      return;
    }

    removing = true;
    error = '';
    success = '';

    try {
      const response = await fetch(`/api/services/${serviceId}/pilots`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId })
      });

      const result = await response.json();

      if (result.error) {
        error = result.error;
      } else {
        success = result.message || 'Pilot removed successfully.';
        // Refresh pilot list
        await fetchPilots();
        setTimeout(() => { success = ''; }, 3000);
      }
    } catch (e) {
      error = 'Failed to remove pilot.';
    } finally {
      removing = false;
    }
  }

  async function makeManager(newManagerUserId, name) {
    const currentIsOwner = currentUserId === ownerUserId;
    const message = currentIsOwner
      ? `Transfer the manager role to ${name}? You will keep your owner role.`
      : `Transfer the manager role to ${name}? You will become a pilot instead.`;

    if (!confirm(message)) return;

    transferring = true;
    error = '';
    success = '';

    try {
      const response = await fetch(`/api/services/${serviceId}/transfer-manager`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ newManagerUserId })
      });

      const result = await response.json();

      if (result.error) {
        error = result.error;
      } else {
        success = `Manager role transferred to ${name}. Reloading...`;
        // Reload page to reflect new roles
        setTimeout(() => { location.reload(); }, 1500);
      }
    } catch (e) {
      error = 'Failed to transfer manager role.';
    } finally {
      transferring = false;
    }
  }

  async function fetchPilots() {
    try {
      const response = await fetch(`/api/services/${serviceId}/pilots`);
      const result = await response.json();
      if (!result.error) {
        pilots = result;
      }
    } catch (e) {
      console.error('Failed to fetch pilots:', e);
    }
  }
</script>

<div class="pilot-manager">
  <h4>Team</h4>
  <p class="description">
    Pilots can manage flights, update ship location, and accept check-ins. The manager has full control over service settings, ticket offers, and team.
  </p>

  <!-- Role display -->
  {#if managerId}
    <div class="role-cards">
      <div class="role-card">
        <div class="role-info">
          <span class="role-badge manager-badge">Manager</span>
          <span class="role-name">{managerName || 'Unknown'}</span>
          {#if !ownerIsDifferent}
            <span class="role-badge owner-badge">Owner</span>
          {/if}
        </div>
      </div>

      {#if ownerIsDifferent}
        <div class="role-card">
          <div class="role-info">
            <span class="role-badge owner-badge">Owner</span>
            <span class="role-name">{ownerDisplayName || 'Unknown'}</span>
          </div>
          {#if isOwner && ownerUserId && ownerUserId !== currentUserId && currentUserId === managerId}
            <button
              class="make-manager-btn"
              on:click={() => makeManager(ownerUserId, ownerDisplayName || 'the owner')}
              disabled={transferring}
            >
              Make Manager
            </button>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  {#if isOwner}
    <div class="add-pilot-section">
      <div class="form-group">
        <label for="pilot-identifier">Add Pilot (EU Username or Discord tag)</label>
        <div class="add-pilot-row">
          <input
            type="text"
            id="pilot-identifier"
            bind:value={identifier}
            disabled={adding}
            placeholder="e.g., John Doe or johndoe"
          />
          <button
            class="add-btn"
            on:click={addPilot}
            disabled={adding || !identifier.trim()}
          >
            {adding ? 'Adding...' : 'Add Pilot'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  {#if pilots.length > 0}
    <div class="pilots-list">
      <h5>Pilots</h5>
      {#each pilots as pilot (pilot.id)}
        <div class="pilot-card">
          <div class="pilot-info">
            <div class="pilot-name">{pilot.username}</div>
            {#if pilot.eu_name && pilot.eu_name !== pilot.username}
              <div class="pilot-euname">EU: {pilot.eu_name}</div>
            {/if}
            <div class="pilot-added">Added by {pilot.added_by_name || 'Unknown'}</div>
          </div>
          <div class="pilot-actions">
            {#if isOwner && currentUserId === managerId && pilot.user_id !== currentUserId}
              <button
                class="make-manager-btn"
                on:click={() => makeManager(pilot.user_id, pilot.eu_name || pilot.username)}
                disabled={transferring}
              >
                Make Manager
              </button>
            {/if}
            {#if isOwner}
              <button
                class="remove-btn"
                on:click={() => removePilot(pilot.user_id)}
                disabled={removing}
              >
                Remove
              </button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <p class="no-pilots">No pilots added yet.</p>
  {/if}

  {#if error}
    <div class="message error-message">{error}</div>
  {/if}

  {#if success}
    <div class="message success-message">{success}</div>
  {/if}
</div>

<style>
  .pilot-manager {
    background: var(--bg-color, #1a1a1a);
    border: 1px solid #555;
    border-radius: 8px;
    padding: 1.5rem;
    margin-top: 1rem;
  }

  h4 {
    margin: 0 0 0.5rem 0;
    font-size: 1.1rem;
  }

  h5 {
    margin: 0 0 0.75rem 0;
    font-size: 1rem;
    color: var(--text-muted, #888);
  }

  .description {
    margin: 0 0 1rem 0;
    font-size: 0.9rem;
    color: var(--text-muted, #888);
  }

  .role-cards {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 1rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #555;
  }

  .role-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: var(--secondary-color, #2a2a2a);
    border: 1px solid #555;
    border-radius: 4px;
  }

  .role-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .role-badge {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }

  .manager-badge {
    background: #1e3a5f;
    color: #7cb3e0;
    border: 1px solid #2d5a8a;
  }

  .owner-badge {
    background: #3a2f1e;
    color: #e0c07c;
    border: 1px solid #8a6e2d;
  }

  .role-name {
    font-weight: 500;
  }

  .add-pilot-section {
    margin-bottom: 1.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #555;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
  }

  .add-pilot-row {
    display: flex;
    gap: 0.75rem;
  }

  .form-group input {
    flex: 1;
    padding: 0.5rem;
    border: 1px solid #555;
    border-radius: 4px;
    background: var(--input-bg, #2a2a2a);
    color: var(--text-color, #fff);
    font-size: 1rem;
  }

  .form-group input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .add-btn {
    padding: 0.5rem 1.2rem;
    border: none;
    border-radius: 4px;
    font-size: 0.95rem;
    font-weight: 500;
    cursor: pointer;
    background: #4a9eff;
    color: white;
    transition: background 0.2s;
  }

  .add-btn:hover:not(:disabled) {
    background: #3a8eef;
  }

  .add-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .pilots-list {
    margin-top: 1rem;
  }

  .pilot-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    background: var(--secondary-color, #2a2a2a);
    border: 1px solid #555;
    border-radius: 4px;
    margin-bottom: 0.5rem;
  }

  .pilot-info {
    flex: 1;
  }

  .pilot-name {
    font-weight: 500;
    margin-bottom: 0.25rem;
  }

  .pilot-euname {
    font-size: 0.85rem;
    color: var(--text-muted, #888);
    margin-bottom: 0.25rem;
  }

  .pilot-added {
    font-size: 0.8rem;
    color: var(--text-muted, #666);
  }

  .pilot-actions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .make-manager-btn {
    padding: 0.35rem 0.7rem;
    border: 1px solid #2d5a8a;
    border-radius: 4px;
    font-size: 0.8rem;
    cursor: pointer;
    background: #1e3a5f;
    color: #7cb3e0;
    transition: background 0.2s;
  }

  .make-manager-btn:hover:not(:disabled) {
    background: #2a4d75;
  }

  .make-manager-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .remove-btn {
    padding: 0.4rem 0.8rem;
    border: none;
    border-radius: 4px;
    font-size: 0.85rem;
    cursor: pointer;
    background: #ef4444;
    color: white;
    transition: background 0.2s;
  }

  .remove-btn:hover:not(:disabled) {
    background: #dc2626;
  }

  .remove-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .no-pilots {
    margin: 1rem 0;
    color: var(--text-muted, #888);
    font-style: italic;
  }

  .message {
    margin-top: 1rem;
    padding: 0.75rem;
    border-radius: 4px;
    font-size: 0.9rem;
  }

  .error-message {
    background: #5a2a2a;
    border: 1px solid #ff6b6b;
    color: #ffcccc;
  }

  .success-message {
    background: #2a5a2a;
    border: 1px solid #10b981;
    color: #ccffcc;
  }
</style>
