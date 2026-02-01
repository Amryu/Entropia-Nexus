<!--
  @component ArmorSetPieces
  Displays and edits the individual armor pieces in a set.

  Normal view: Uses FancyTable with Slot and Name columns.
  Edit mode: Compact card-based editor with unisex toggle and gender-specific inputs.
-->
<script>
  // @ts-nocheck
  import { encodeURIComponentSafe } from '$lib/util';
  import { editMode, updateField } from '$lib/stores/wikiEditState.js';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import '$lib/style.css';

  export let armorSet;

  const slots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];

  // Process armor pieces by slot
  $: piecesBySlot = (() => {
    const result = {};
    slots.forEach(slot => {
      result[slot] = { male: null, female: null, slotIndex: -1 };
    });

    armorSet?.Armors?.forEach((armorVariants, idx) => {
      armorVariants.forEach(armor => {
        const slot = armor?.Properties?.Slot;
        const gender = armor?.Properties?.Gender;
        if (!slot || !result[slot]) return;

        result[slot].slotIndex = idx;

        if (gender === 'Both' || gender === 'Male') {
          result[slot].male = armor;
        }
        if (gender === 'Both' || gender === 'Female') {
          result[slot].female = armor;
        }
      });
    });

    return result;
  })();

  // Check if there are different male/female variants
  $: hasGenderVariants = (() => {
    return slots.some(slot => {
      const piece = piecesBySlot[slot];
      return piece.male?.Name !== piece.female?.Name && piece.male && piece.female;
    });
  })();

  // Gender toggle for view mode
  let viewGender = 'male';

  // FancyTable columns: Slot, Name, Weight, MaxTT, MinTT
  const tableColumns = [
    { key: 'slot', header: 'Slot', width: '70px', sortable: false, searchable: false, hideOnMobile: true },
    { key: 'name', header: 'Name', main: true, sortable: false, searchable: false },
    { key: 'weight', header: 'Weight', width: '70px', sortable: false, searchable: false, hideOnMobile: true },
    { key: 'maxTT', header: 'Max TT', width: '80px', sortable: false, searchable: false },
    { key: 'minTT', header: 'Min TT', width: '80px', sortable: false, searchable: false, hideOnMobile: true }
  ];

  // Format TT value for display
  function formatTT(value) {
    if (value == null || value === 0) return '-';
    return value.toFixed(2);
  }

  // Transform data for FancyTable based on selected gender
  $: tableData = slots.map(slot => {
    const piece = piecesBySlot[slot];
    // Select piece based on toggle (or fallback if only one exists)
    const displayPiece = viewGender === 'male'
      ? (piece.male || piece.female)
      : (piece.female || piece.male);

    if (!displayPiece) return null;

    return {
      slot,
      name: `<a href="/items/armors/${encodeURIComponentSafe(displayPiece.Name)}" class="piece-link">${displayPiece.Name}</a>`,
      weight: displayPiece.Properties?.Weight?.toFixed(1) || '-',
      maxTT: formatTT(displayPiece.Properties?.Economy?.MaxTT),
      minTT: formatTT(displayPiece.Properties?.Economy?.MinTT)
    };
  }).filter(row => row !== null);

  // ========== EDIT MODE FUNCTIONS ==========

  // Create new armor piece template
  function newArmorPiece(slot, gender) {
    return {
      Name: `${armorSet?.Name || 'Armor'} ${slot}${gender !== 'Both' ? ` (${gender.substring(0, 1)})` : ''}`,
      Properties: {
        Slot: slot,
        Gender: gender,
        Weight: 0,
        Economy: {
          MaxTT: 0,
          MinTT: 0,
          Durability: 0
        },
        Defense: {}
      },
      EffectsOnEquip: []
    };
  }

  // Check if slot has a piece
  function slotHasPiece(slot) {
    const piece = piecesBySlot[slot];
    return piece.male || piece.female;
  }

  // Check if slot is unisex (has Both gender or no pieces)
  function isSlotUnisex(slot) {
    const piece = piecesBySlot[slot];
    if (!piece.male && !piece.female) return true;
    return piece.male?.Properties?.Gender === 'Both';
  }

  // Add piece to slot
  function addPieceToSlot(slot) {
    const armors = [...(armorSet.Armors || [])];
    armors.push([newArmorPiece(slot, 'Both')]);
    updateField('Armors', armors);
  }

  // Remove piece from slot
  function removePieceFromSlot(slot) {
    const piece = piecesBySlot[slot];
    if (piece.slotIndex === -1) return;
    const armors = armorSet.Armors.filter((_, idx) => idx !== piece.slotIndex);
    updateField('Armors', armors);
  }

  // Toggle unisex for slot
  function toggleUnisex(slot) {
    const piece = piecesBySlot[slot];
    if (piece.slotIndex === -1) return;

    const armors = [...armorSet.Armors];
    const currentIsUnisex = isSlotUnisex(slot);

    if (currentIsUnisex) {
      // Convert to gender-specific
      const basePiece = piece.male || piece.female;
      const baseName = basePiece.Name.replace(/ \([MF]\)$/, '');
      armors[piece.slotIndex] = [
        { ...JSON.parse(JSON.stringify(basePiece)), Name: `${baseName} (M)`, Properties: { ...basePiece.Properties, Gender: 'Male' } },
        { ...JSON.parse(JSON.stringify(basePiece)), Name: `${baseName} (F)`, Properties: { ...basePiece.Properties, Gender: 'Female' } }
      ];
    } else {
      // Convert to unisex (use male piece as base)
      const basePiece = piece.male || piece.female;
      const name = basePiece.Name.replace(/ \([MF]\)$/, '');
      armors[piece.slotIndex] = [
        { ...JSON.parse(JSON.stringify(basePiece)), Name: name, Properties: { ...basePiece.Properties, Gender: 'Both' } }
      ];
    }

    updateField('Armors', armors);
  }

  // Update piece property
  function updatePiece(slot, gender, property, value) {
    const piece = piecesBySlot[slot];
    if (piece.slotIndex === -1) return;

    const armors = JSON.parse(JSON.stringify(armorSet.Armors));
    const slotArmors = armors[piece.slotIndex];

    // Find the armor with matching gender
    const targetArmor = slotArmors.find(a =>
      a.Properties.Gender === gender ||
      (gender === 'Male' && a.Properties.Gender === 'Both') ||
      (gender === 'Female' && a.Properties.Gender === 'Both')
    );

    if (!targetArmor) return;

    // Set nested property
    const keys = property.split('.');
    let obj = targetArmor;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!obj[keys[i]]) obj[keys[i]] = {};
      obj = obj[keys[i]];
    }
    obj[keys[keys.length - 1]] = value;

    updateField('Armors', armors);
  }
</script>

{#if $editMode}
  <!-- Edit Mode: Compact card-based piece editor -->
  <div class="pieces-edit-container">
    {#each slots as slot}
      {@const piece = piecesBySlot[slot]}
      {@const hasPiece = slotHasPiece(slot)}
      {@const unisex = isSlotUnisex(slot)}

      <div class="piece-edit-card" class:empty={!hasPiece}>
        <div class="piece-edit-header">
          <span class="slot-label">{slot}</span>
          {#if hasPiece}
            <div class="piece-controls">
              <label class="unisex-toggle" title="When unchecked, allows different male/female variants">
                <input
                  type="checkbox"
                  checked={unisex}
                  on:change={() => toggleUnisex(slot)}
                />
                <span>Unisex</span>
              </label>
              <button class="btn-remove-piece" on:click={() => removePieceFromSlot(slot)} title="Remove piece">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          {:else}
            <button class="btn-add-piece" on:click={() => addPieceToSlot(slot)}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add
            </button>
          {/if}
        </div>

        {#if hasPiece}
          <div class="piece-edit-body">
            {#if unisex}
              <!-- Unisex piece - single compact row -->
              {@const armor = piece.male || piece.female}
              <div class="piece-fields-row">
                <input
                  type="text"
                  class="field-name"
                  value={armor?.Name || ''}
                  placeholder="Name"
                  on:change={(e) => updatePiece(slot, 'Both', 'Name', e.target.value)}
                />
                <div class="labeled-field">
                  <span class="field-label">Wt</span>
                  <input
                    type="number"
                    class="field-compact"
                    step="0.1"
                    min="0"
                    value={armor?.Properties?.Weight ?? 0}
                    on:change={(e) => updatePiece(slot, 'Both', 'Properties.Weight', parseFloat(e.target.value) || 0)}
                  />
                </div>
                <div class="labeled-field">
                  <span class="field-label">Max</span>
                  <input
                    type="number"
                    class="field-compact"
                    step="0.0001"
                    min="0"
                    value={armor?.Properties?.Economy?.MaxTT ?? 0}
                    on:change={(e) => updatePiece(slot, 'Both', 'Properties.Economy.MaxTT', parseFloat(e.target.value) || 0)}
                  />
                </div>
                <div class="labeled-field">
                  <span class="field-label">Min</span>
                  <input
                    type="number"
                    class="field-compact"
                    step="0.0001"
                    min="0"
                    value={armor?.Properties?.Economy?.MinTT ?? 0}
                    on:change={(e) => updatePiece(slot, 'Both', 'Properties.Economy.MinTT', parseFloat(e.target.value) || 0)}
                  />
                </div>
              </div>
            {:else}
              <!-- Gender-specific pieces - compact layout -->
              {#each [{ gender: 'Male', armor: piece.male, label: 'M' }, { gender: 'Female', armor: piece.female, label: 'F' }] as { gender, armor, label }}
                <div class="piece-fields-row">
                  <span class="gender-tag">{label}</span>
                  <input
                    type="text"
                    class="field-name"
                    value={armor?.Name || ''}
                    placeholder="Name"
                    on:change={(e) => updatePiece(slot, gender, 'Name', e.target.value)}
                  />
                  <div class="labeled-field">
                    <span class="field-label">Wt</span>
                    <input
                      type="number"
                      class="field-compact"
                      step="0.1"
                      min="0"
                      value={armor?.Properties?.Weight ?? 0}
                      on:change={(e) => updatePiece(slot, gender, 'Properties.Weight', parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <div class="labeled-field">
                    <span class="field-label">Max</span>
                    <input
                      type="number"
                      class="field-compact"
                      step="0.0001"
                      min="0"
                      value={armor?.Properties?.Economy?.MaxTT ?? 0}
                      on:change={(e) => updatePiece(slot, gender, 'Properties.Economy.MaxTT', parseFloat(e.target.value) || 0)}
                    />
                  </div>
                  <div class="labeled-field">
                    <span class="field-label">Min</span>
                    <input
                      type="number"
                      class="field-compact"
                      step="0.0001"
                      min="0"
                      value={armor?.Properties?.Economy?.MinTT ?? 0}
                      on:change={(e) => updatePiece(slot, gender, 'Properties.Economy.MinTT', parseFloat(e.target.value) || 0)}
                    />
                  </div>
                </div>
              {/each}
            {/if}
          </div>
        {/if}
      </div>
    {/each}
  </div>
{:else}
  <!-- View Mode: FancyTable display -->
  {#if tableData.length > 0}
    {#if hasGenderVariants}
      <div class="gender-toggle-bar">
        <button
          class="gender-btn"
          class:active={viewGender === 'male'}
          on:click={() => viewGender = 'male'}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="10" cy="14" r="5"/>
            <line x1="14" y1="10" x2="21" y2="3"/>
            <polyline points="15,3 21,3 21,9"/>
          </svg>
          Male
        </button>
        <button
          class="gender-btn"
          class:active={viewGender === 'female'}
          on:click={() => viewGender = 'female'}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="8" r="5"/>
            <line x1="12" y1="13" x2="12" y2="21"/>
            <line x1="9" y1="18" x2="15" y2="18"/>
          </svg>
          Female
        </button>
      </div>
    {/if}
    <div class="pieces-table-wrapper">
      <FancyTable
        columns={tableColumns}
        data={tableData}
        rowHeight={40}
        sortable={false}
        searchable={false}
        stickyHeader={false}
        emptyMessage="No armor pieces"
      />
    </div>
  {:else}
    <div class="empty-pieces">No armor pieces defined</div>
  {/if}
{/if}

<style>
  /* ========== EDIT MODE STYLES ========== */
  .pieces-edit-container {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .piece-edit-card {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    overflow: hidden;
  }

  .piece-edit-card.empty {
    border-style: dashed;
    opacity: 0.7;
  }

  .piece-edit-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    background-color: var(--secondary-color);
    border-bottom: 1px solid var(--border-color, #555);
  }

  .piece-edit-card.empty .piece-edit-header {
    border-bottom: none;
  }

  .slot-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .piece-controls {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .unisex-toggle {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: var(--text-muted, #999);
    cursor: pointer;
  }

  .unisex-toggle input {
    cursor: pointer;
    margin: 0;
  }

  .btn-remove-piece,
  .btn-add-piece {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    font-size: 11px;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-remove-piece {
    color: var(--error-color, #ff6b6b);
    padding: 4px;
  }

  .btn-remove-piece:hover {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-add-piece {
    color: var(--accent-color, #4a9eff);
  }

  .btn-add-piece:hover {
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-color: var(--accent-color, #4a9eff);
  }

  .piece-edit-body {
    padding: 8px 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .piece-fields-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .gender-tag {
    width: 20px;
    font-size: 11px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    text-align: center;
    flex-shrink: 0;
  }

  .field-name {
    flex: 1;
    min-width: 120px;
    padding: 5px 8px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    box-sizing: border-box;
  }

  .labeled-field {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
  }

  .field-label {
    font-size: 10px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .field-compact {
    width: 55px;
    padding: 5px 6px;
    font-size: 12px;
    text-align: left;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
  }

  .field-name:focus,
  .field-compact:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  /* ========== VIEW MODE STYLES ========== */
  .gender-toggle-bar {
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
  }

  .gender-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    font-size: 12px;
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
  }

  .gender-btn:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .gender-btn.active {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .pieces-table-wrapper {
    height: 350px;
    max-height: 350px;
  }

  .pieces-table-wrapper :global(.piece-link) {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .pieces-table-wrapper :global(.piece-link:hover) {
    text-decoration: underline;
  }

  .pieces-table-wrapper :global(.same-piece) {
    color: var(--text-muted, #999);
    font-style: italic;
    font-size: 12px;
  }

  .empty-pieces {
    padding: 20px;
    text-align: center;
    color: var(--text-muted, #999);
    font-size: 13px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .piece-edit-body {
      padding: 8px 10px;
    }

    .piece-fields-row {
      flex-wrap: wrap;
    }

    .field-name {
      width: 100%;
      min-width: 0;
      flex: 0 0 100%;
      order: 1;
    }

    .gender-tag {
      order: 0;
      width: 100%;
      text-align: left;
      margin-bottom: 4px;
    }

    .labeled-field {
      order: 2;
      flex: 1;
      min-width: 0;
    }

    .field-compact {
      width: 100%;
      box-sizing: border-box;
    }
  }
</style>
