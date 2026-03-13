<!--
  @component WaypointInput
  A unified input for editing waypoint/location data.

  Features:
  - Parses pasted waypoints: [Planet, x, y, z, Name] or simple "x, y, z"
  - Planet field with searchable dropdown (from /planets endpoint)
  - Individual coordinate fields (Longitude, Latitude, Altitude)
  - Optional name field
  - Lock/hide capabilities for planet and name fields
  - Looks like a single cohesive input

  Usage:
    <WaypointInput
      value={{ planet: 'Calypso', x: 123, y: 456, z: 100, name: 'Location' }}
      onchange={handleChange}
    />

    With locked/hidden fields:
    <WaypointInput
      value={{ planet: 'Calypso', x: 123, y: 456, z: 100, name: '' }}
      planetLocked={true}
      hidePlanet={false}
      hideName={true}
      onchange={handleChange}
    />
-->
<script>
  // @ts-nocheck
  import { onMount, tick } from 'svelte';
  import { browser } from '$app/environment';
  import { clickable } from '$lib/actions/clickable.js';

  

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {{ planet?: string|null, planetId?: number|null, x?: number|null, y?: number|null, z?: number|null, name?: string|null }} [value]
   * @property {boolean} [planetLocked] - Lock the planet field (won't be overwritten on paste)
   * @property {boolean} [nameLocked] - Lock the name field (won't be overwritten on paste)
   * @property {boolean} [hidePlanet] - Hide the planet field entirely
   * @property {boolean} [hideName] - Hide the name field entirely
   * @property {boolean} [disabled] - Whether the input is disabled
   * @property {Function} [onchange]
   */

  /** @type {Props} */
  let {
    value = {},
    planetLocked = false,
    nameLocked = false,
    hidePlanet = false,
    hideName = false,
    disabled = false,
    onchange
  } = $props();

  // Internal state
  let planets = $state([]);
  let planetSearchValue = $state('');
  let showPlanetDropdown = $state(false);
  let filteredPlanets = $state([]);
  let highlightedPlanetIndex = $state(-1);
  let containerEl = $state();
  let planetInputEl = $state();
  let coordInputEl = $state();
  let isFocused = $state(false);

  // Local values for controlled inputs
  let localX = $state('');
  let localY = $state('');
  let localZ = $state('');
  let localName = $state('');

  // Sync local values with prop
  $effect(() => {
    localX = value?.x != null ? String(value.x) : '';
    localY = value?.y != null ? String(value.y) : '';
    localZ = value?.z != null ? String(value.z) : '';
    localName = value?.name ?? '';
    planetSearchValue = value?.planet ?? '';
  });

  // Filter planets based on search
  $effect(() => {
    const search = planetSearchValue.toLowerCase().trim();
    if (search.length === 0) {
      filteredPlanets = planets;
    } else {
      filteredPlanets = planets.filter(p =>
        p.Name.toLowerCase().includes(search)
      );
    }
    highlightedPlanetIndex = filteredPlanets.length > 0 ? 0 : -1;
  });

  // Load planets on mount
  onMount(async () => {
    if (!browser) return;
    try {
      const response = await fetch(import.meta.env.VITE_API_URL + '/planets');
      const data = await response.json();
      // Filter to only planets with Id > 0
      planets = (data || []).filter(p => p.Id > 0);
    } catch (err) {
      console.error('Failed to load planets:', err);
      planets = [];
    }
  });

  // Parse waypoint string: [Planet, x, y, z, Name]
  function parseWaypoint(str) {
    // Try full waypoint format: [Planet, x, y, z, Name]
    const fullMatch = str.match(/\[([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,\]]+)(?:,\s*([^\]]*))?\]/);
    if (fullMatch) {
      return {
        planet: fullMatch[1].trim(),
        x: parseFloat(fullMatch[2]) || 0,
        y: parseFloat(fullMatch[3]) || 0,
        z: parseFloat(fullMatch[4]) || 0,
        name: fullMatch[5]?.trim() || ''
      };
    }

    // Try simple x, y, z format (with or without brackets)
    const simpleMatch = str.match(/^\[?\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]?$/);
    if (simpleMatch) {
      return {
        planet: null,
        x: parseFloat(simpleMatch[1]) || 0,
        y: parseFloat(simpleMatch[2]) || 0,
        z: parseFloat(simpleMatch[3]) || 0,
        name: null
      };
    }

    return null;
  }

  function emitChange(updates) {
    const newValue = { ...value, ...updates };
    onchange?.(newValue);
  }

  function handlePaste(event) {
    const pastedText = event.clipboardData?.getData('text') || '';
    const parsed = parseWaypoint(pastedText);

    if (parsed) {
      event.preventDefault();

      const updates = {};

      // Update coordinates (always)
      updates.x = parsed.x;
      updates.y = parsed.y;
      updates.z = parsed.z;

      // Update planet if not locked and we have a value
      if (!planetLocked && parsed.planet) {
        updates.planet = parsed.planet;
        // Try to find matching planet ID
        const matchingPlanet = planets.find(p =>
          p.Name.toLowerCase() === parsed.planet.toLowerCase()
        );
        if (matchingPlanet) {
          updates.planetId = matchingPlanet.Id;
        }
      }

      // Update name if not locked and we have a value
      if (!nameLocked && parsed.name !== null) {
        updates.name = parsed.name;
      }

      emitChange(updates);
    }
  }

  function handleCoordInput(field, inputValue) {
    // Allow empty, minus sign, or valid number patterns
    const cleanValue = inputValue.replace(/[^\d.\-]/g, '');

    // Validate it's a proper number or empty
    if (cleanValue === '' || cleanValue === '-' || cleanValue === '.') {
      if (field === 'x') localX = cleanValue;
      else if (field === 'y') localY = cleanValue;
      else if (field === 'z') localZ = cleanValue;
      return;
    }

    const num = parseFloat(cleanValue);
    if (!isNaN(num)) {
      emitChange({ [field]: num });
    }
  }

  function handleCoordBlur(field) {
    // On blur, clean up any incomplete entries
    let localVal;
    if (field === 'x') localVal = localX;
    else if (field === 'y') localVal = localY;
    else localVal = localZ;

    if (localVal === '' || localVal === '-' || localVal === '.') {
      emitChange({ [field]: null });
    }
  }

  function handleNameInput(inputValue) {
    localName = inputValue;
    emitChange({ name: inputValue || null });
  }

  function handlePlanetInput(inputValue) {
    planetSearchValue = inputValue;
    showPlanetDropdown = true;

    // If empty, clear planet
    if (!inputValue.trim()) {
      emitChange({ planet: null, planetId: null });
    }
  }

  function selectPlanet(planet) {
    planetSearchValue = planet.Name;
    emitChange({ planet: planet.Name, planetId: planet.Id });
    showPlanetDropdown = false;
    highlightedPlanetIndex = -1;
  }

  function handlePlanetKeydown(event) {
    if (!showPlanetDropdown || filteredPlanets.length === 0) {
      if (event.key === 'Escape') {
        showPlanetDropdown = false;
      }
      return;
    }

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        highlightedPlanetIndex = Math.min(highlightedPlanetIndex + 1, filteredPlanets.length - 1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        highlightedPlanetIndex = Math.max(highlightedPlanetIndex - 1, 0);
        break;
      case 'Enter':
        event.preventDefault();
        if (highlightedPlanetIndex >= 0 && highlightedPlanetIndex < filteredPlanets.length) {
          selectPlanet(filteredPlanets[highlightedPlanetIndex]);
        }
        break;
      case 'Escape':
        event.preventDefault();
        showPlanetDropdown = false;
        break;
      case 'Tab':
        showPlanetDropdown = false;
        break;
    }
  }

  function handlePlanetBlur() {
    setTimeout(() => {
      showPlanetDropdown = false;

      // If the entered value doesn't match a planet, try to find a match
      if (planetSearchValue.trim()) {
        const matchingPlanet = planets.find(p =>
          p.Name.toLowerCase() === planetSearchValue.toLowerCase().trim()
        );
        if (matchingPlanet) {
          selectPlanet(matchingPlanet);
        } else {
          // Keep as-is (allow free text for now, or clear if strict)
          emitChange({ planet: planetSearchValue.trim(), planetId: null });
        }
      }
    }, 150);
  }

  function handlePlanetFocus() {
    showPlanetDropdown = true;
  }

  function handleContainerFocus() {
    isFocused = true;
  }

  function handleContainerBlur(event) {
    // Check if focus moved outside container
    setTimeout(() => {
      if (browser && containerEl && !containerEl.contains(document.activeElement)) {
        isFocused = false;
      }
    }, 10);
  }

  function getWaypointPreview() {
    const parts = [];
    if (value?.planet) parts.push(value.planet);
    else if (!hidePlanet) parts.push('?');

    parts.push(value?.x ?? '?');
    parts.push(value?.y ?? '?');
    parts.push(value?.z ?? '?');

    // Always include a name for in-game compatibility, default to "Waypoint"
    parts.push(value?.name || 'Waypoint');

    return `[${parts.join(', ')}]`;
  }
</script>

<div
  class="waypoint-input"
  class:focused={isFocused}
  class:disabled
  bind:this={containerEl}
  onfocusin={handleContainerFocus}
  onfocusout={handleContainerBlur}
  onpaste={handlePaste}
>
  <!-- Paste indicator / preview -->
  <div class="waypoint-header">
    <span class="paste-hint" title="Paste a waypoint to auto-fill: [Planet, x, y, z, Name] or x, y, z">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
    </span>
    <span class="waypoint-preview">{getWaypointPreview()}</span>
  </div>

  <div class="waypoint-fields">
    <!-- Planet field -->
    {#if !hidePlanet}
      <div class="field-group planet-group">
        <label class="field-label">
          Planet
          {#if planetLocked}
            <span class="lock-icon" title="Locked - won't change on paste">🔒</span>
          {/if}
        </label>
        <div class="planet-search">
          <input
            bind:this={planetInputEl}
            type="text"
            class="field-input"
            value={planetSearchValue}
            oninput={(e) => handlePlanetInput(e.target.value)}
            onkeydown={handlePlanetKeydown}
            onfocus={handlePlanetFocus}
            onblur={handlePlanetBlur}
            placeholder="Search planet..."
            disabled={disabled || planetLocked}
            autocomplete="off"
          />
          {#if showPlanetDropdown && filteredPlanets.length > 0}
            <div class="planet-dropdown">
              {#each filteredPlanets as planet, idx}
                <div
                  class="planet-option"
                  class:highlighted={idx === highlightedPlanetIndex}
                  onmousedown={(e) => { e.preventDefault(); selectPlanet(planet); }}
                  onmouseenter={() => highlightedPlanetIndex = idx}
                  use:clickable
                  role="button"
                  tabindex="0"
                >
                  {planet.Name}
                </div>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <!-- Coordinates -->
    <div class="coords-group">
      <div class="field-group coord-field">
        <label class="field-label">Longitude</label>
        <input
          bind:this={coordInputEl}
          type="text"
          inputmode="decimal"
          class="field-input coord-input"
          value={localX}
          oninput={(e) => handleCoordInput('x', e.target.value)}
          onblur={() => handleCoordBlur('x')}
          placeholder="X"
          {disabled}
        />
      </div>
      <div class="field-group coord-field">
        <label class="field-label">Latitude</label>
        <input
          type="text"
          inputmode="decimal"
          class="field-input coord-input"
          value={localY}
          oninput={(e) => handleCoordInput('y', e.target.value)}
          onblur={() => handleCoordBlur('y')}
          placeholder="Y"
          {disabled}
        />
      </div>
      <div class="field-group coord-field">
        <label class="field-label">Altitude</label>
        <input
          type="text"
          inputmode="decimal"
          class="field-input coord-input"
          value={localZ}
          oninput={(e) => handleCoordInput('z', e.target.value)}
          onblur={() => handleCoordBlur('z')}
          placeholder="Z"
          {disabled}
        />
      </div>
    </div>

    <!-- Name field -->
    {#if !hideName}
      <div class="field-group name-group">
        <label class="field-label">
          Name
          {#if nameLocked}
            <span class="lock-icon" title="Locked - won't change on paste">🔒</span>
          {/if}
        </label>
        <input
          type="text"
          class="field-input"
          value={localName}
          oninput={(e) => handleNameInput(e.target.value)}
          placeholder="Location name"
          disabled={disabled || nameLocked}
        />
      </div>
    {/if}
  </div>
</div>

<style>
  .waypoint-input {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    transition: border-color 0.15s;
  }

  .waypoint-input.focused {
    border-color: var(--accent-color, #4a9eff);
  }

  .waypoint-input.disabled {
    opacity: 0.6;
    pointer-events: none;
  }

  .waypoint-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-bottom: 6px;
    border-bottom: 1px dashed var(--border-color, #555);
  }

  .paste-hint {
    display: flex;
    align-items: center;
    color: var(--text-muted, #999);
    cursor: help;
  }

  .paste-hint:hover {
    color: var(--accent-color, #4a9eff);
  }

  .waypoint-preview {
    font-family: monospace;
    font-size: 11px;
    color: var(--text-muted, #999);
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .waypoint-fields {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .field-label {
    font-size: 11px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .lock-icon {
    font-size: 10px;
    cursor: help;
  }

  .field-input {
    padding: 6px 8px;
    font-size: 12px;
    background: var(--bg-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
  }

  .field-input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .field-input:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .field-input::placeholder {
    color: var(--text-muted, #999);
  }

  /* Planet search dropdown */
  .planet-group {
    position: relative;
  }

  .planet-search {
    position: relative;
  }

  .planet-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    z-index: 100;
    max-height: 150px;
    overflow-y: auto;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-top: none;
    border-radius: 0 0 3px 3px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  }

  .planet-option {
    padding: 6px 8px;
    font-size: 12px;
    cursor: pointer;
    color: var(--text-color);
  }

  .planet-option:hover,
  .planet-option.highlighted {
    background: var(--hover-color);
  }

  .planet-option.highlighted {
    outline: 1px solid var(--accent-color, #4a9eff);
    outline-offset: -1px;
  }

  /* Coordinates group */
  .coords-group {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }

  .coord-field {
    min-width: 0;
  }

  .coord-input {
    text-align: center;
    font-family: monospace;
  }

  /* Name group */
  .name-group {
    /* Full width */
  }

  /* Mobile adjustments */
  @media (max-width: 500px) {
    .coords-group {
      grid-template-columns: 1fr;
    }

    .waypoint-header {
      flex-wrap: wrap;
    }

    .waypoint-preview {
      width: 100%;
      order: 1;
      margin-top: 4px;
    }
  }
</style>
