<script>
  // @ts-nocheck
  export let serviceId;
  export let currentPlanetId = null;
  export let planets = [];
  export let locationDisplay = 'Location not set';

  // Filter to main planets only (IDs 1-7: Calypso, Arkadia, Monria, ROCKtropia, Toulan, Next Island, Cyrene)
  $: mainPlanets = planets.filter(p => p.Id >= 1 && p.Id <= 7);

  let editing = false;
  let updating = false;
  let editedPlanetId = currentPlanetId;

  function startEdit() {
    editing = true;
    editedPlanetId = currentPlanetId;
  }

  function cancelEdit() {
    editing = false;
    editedPlanetId = currentPlanetId;
  }

  async function saveLocation() {
    updating = true;

    try {
      const response = await fetch(`/api/services/${serviceId}/location`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ planet_id: editedPlanetId })
      });

      const result = await response.json();

      if (!result.error) {
        currentPlanetId = editedPlanetId;
        editing = false;
        // Update display
        if (editedPlanetId) {
          const planet = mainPlanets.find(p => p.Id === editedPlanetId);
          locationDisplay = planet ? `Currently at ${planet.Name}` : 'Location not set';
        } else {
          locationDisplay = 'Location not set';
        }
      }
    } catch (e) {
      console.error('Failed to update location:', e);
    } finally {
      updating = false;
    }
  }
</script>

{#if !editing}
  <span class="location-display">
    {locationDisplay}
    <button class="edit-btn" on:click={startEdit} title="Edit location">
      ✎
    </button>
  </span>
{:else}
  <span class="location-editor">
    <select bind:value={editedPlanetId} disabled={updating}>
      <option value={null}>-- No location set --</option>
      {#each mainPlanets as planet}
        <option value={planet.Id}>{planet.Name}</option>
      {/each}
    </select>
    <button class="save-btn" on:click={saveLocation} disabled={updating}>
      {updating ? '...' : '✓'}
    </button>
    <button class="cancel-btn" on:click={cancelEdit} disabled={updating}>
      ✕
    </button>
  </span>
{/if}

<style>
  .location-display {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }

  .edit-btn {
    background: none;
    border: none;
    color: #4a9eff;
    cursor: pointer;
    font-size: 1.1rem;
    padding: 0.25rem;
    opacity: 0.7;
    transition: opacity 0.2s;
  }

  .edit-btn:hover {
    opacity: 1;
  }

  .location-editor {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
  }

  .location-editor select {
    padding: 0.4rem 0.6rem;
    border: 1px solid #555;
    border-radius: 4px;
    background: var(--secondary-color, #2a2a2a);
    color: var(--text-color, #fff);
    font-size: 0.95rem;
    cursor: pointer;
  }

  .location-editor select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .save-btn,
  .cancel-btn {
    padding: 0.4rem 0.6rem;
    border: none;
    border-radius: 4px;
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.2s;
    min-width: 2rem;
  }

  .save-btn {
    background: #4a9eff;
    color: white;
  }

  .save-btn:hover:not(:disabled) {
    background: #3a8eef;
  }

  .cancel-btn {
    background: #666;
    color: white;
  }

  .cancel-btn:hover:not(:disabled) {
    background: #555;
  }

  .save-btn:disabled,
  .cancel-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
