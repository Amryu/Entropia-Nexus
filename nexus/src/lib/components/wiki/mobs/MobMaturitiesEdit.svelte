<!--
  @component MobMaturitiesEdit
  Array editor for mob maturities with nested attacks.
  Supports add/edit/remove for maturities and their attacks.
  Following the editConfig pattern from mobs-legacy.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { editMode, updateField, currentEntity, originalEntity } from '$lib/stores/wikiEditState.js';

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {Array} [maturities]
   * @property {string} [type]
   * @property {string} [mobName]
   * @property {string} [fieldPath]
   */

  /** @type {Props} */
  let {
    maturities = [],
    type = null,
    mobName = '',
    fieldPath = 'Maturities'
  } = $props();

  const NAME_MODES = [
    { value: null, label: '—' },
    { value: 'Suffix', label: 'Suffix' },
    { value: 'Prefix', label: 'Prefix' },
    { value: 'Verbatim', label: 'Verbatim' },
    { value: 'Empty', label: 'Empty' },
  ];

  function getFullNamePreview(maturityName, nameMode) {
    const mob = mobName || '???';
    const mat = maturityName || '???';
    switch (nameMode) {
      case 'Prefix':   return `${mat} ${mob}`;
      case 'Verbatim': return mat;
      case 'Empty':    return mob;
      case 'Suffix':   return `${mob} ${mat}`;
      default:         return `${mob} ${mat}`;
    }
  }

  // Damage types for composition
  const DAMAGE_TYPES = [
    { key: 'Stab', label: 'Stb' },
    { key: 'Cut', label: 'Cut' },
    { key: 'Impact', label: 'Imp' },
    { key: 'Penetration', label: 'Pen' },
    { key: 'Shrapnel', label: 'Shp' },
    { key: 'Burn', label: 'Brn' },
    { key: 'Cold', label: 'Cld' },
    { key: 'Acid', label: 'Acd' },
    { key: 'Electric', label: 'Ele' }
  ];

  // Attack name presets
  const ATTACK_NAMES = ['Primary', 'Secondary', 'Tertiary', 'Quaternary', 'Quinary', 'Senary'];

  let isAsteroid = $derived(type === 'Asteroid');

  // Track open copy menus (by matIndex-attackIndex)
  let openCopyMenu = $state(null);

  // UID tracking for maturity identity (survives reordering)
  let uidCounter = 0;
  const uidMap = new WeakMap();

  function getUid(obj) {
    if (!uidMap.has(obj)) {
      uidMap.set(obj, ++uidCounter);
    }
    return uidMap.get(obj);
  }

  // Clone a maturity object, preserving its UID for stable keyed {#each} identity
  function cloneMaturity(mat) {
    const uid = getUid(mat);
    const clone = JSON.parse(JSON.stringify(mat));
    uidMap.set(clone, uid);
    return clone;
  }

  // Track which maturity panels are expanded (by UID)
  let expandedMaturities = $state({});

  // Sort comparator: Level ascending, Health secondary, Bosses at bottom, nulls at end
  function maturitySortComparator(a, b) {
    const aIsBoss = a.Properties?.Boss || false;
    const bIsBoss = b.Properties?.Boss || false;
    if (aIsBoss !== bIsBoss) return aIsBoss ? 1 : -1;

    const aLvl = a.Properties?.Level;
    const bLvl = b.Properties?.Level;
    const aHasLvl = aLvl != null;
    const bHasLvl = bLvl != null;
    if (aHasLvl !== bHasLvl) return aHasLvl ? -1 : 1;
    if (aHasLvl && bHasLvl && aLvl !== bLvl) return aLvl - bLvl;

    const aHp = a.Properties?.Health;
    const bHp = b.Properties?.Health;
    if (aHp != null && bHp != null) return aHp - bHp;

    return 0;
  }

  // Check if maturities are in sorted order
  function isSorted(arr) {
    for (let i = 1; i < arr.length; i++) {
      if (maturitySortComparator(arr[i - 1], arr[i]) > 0) return false;
    }
    return true;
  }

  // Sort maturities once on initial load — updates the original entity directly
  // so it doesn't create dirty state
  onMount(() => {
    if (maturities && maturities.length > 1 && !isSorted(maturities)) {
      const sorted = [...maturities].sort(maturitySortComparator);
      originalEntity.update(e => {
        if (!e) return e;
        const parts = fieldPath.split('.');
        const copy = JSON.parse(JSON.stringify(e));
        let target = copy;
        for (let i = 0; i < parts.length - 1; i++) target = target[parts[i]];
        target[parts[parts.length - 1]] = sorted;
        return copy;
      });
    }
  });

  // === Maturity Constructor ===
  function createMaturity() {
    const template = {
      Name: '',
      NameMode: 'Suffix',
      Properties: {
        Description: null,
        Level: null,
        Health: null,
        AttacksPerMinute: $currentEntity?.Properties?.AttacksPerMinute ?? null,
        Boss: false,
        RegenerationInterval: null,
        RegenerationAmount: null,
        MissChance: null,
        Taming: {
          IsTameable: false,
          TamingLevel: null
        },
        Attributes: {
          Strength: null,
          Agility: null,
          Intelligence: null,
          Psyche: null,
          Stamina: null
        },
        Defense: {
          Stab: 0,
          Cut: 0,
          Impact: 0,
          Penetration: 0,
          Shrapnel: 0,
          Burn: 0,
          Cold: 0,
          Acid: 0,
          Electric: 0
        }
      },
      Attacks: []
    };

    // For asteroids, null out combat-specific fields
    if (isAsteroid) {
      template.Properties.RegenerationInterval = null;
      template.Properties.RegenerationAmount = null;
      template.Properties.MissChance = null;
      template.Properties.Taming.IsTameable = null;
      template.Properties.Taming.TamingLevel = null;
      template.Properties.Attributes = null;
      template.Properties.Defense = null;
      template.Attacks = [];
    } else {
      // Add one default attack for non-asteroids
      template.Attacks = [createAttack(0, maturities)];
    }

    return template;
  }

  // === Attack Constructor ===
  function createAttack(index, parentMaturities) {
    const attackName = index < ATTACK_NAMES.length ? ATTACK_NAMES[index] : `Attack ${index + 1}`;

    const attack = {
      Name: attackName,
      TotalDamage: null,
      IsAoE: false,
      Damage: {
        Stab: null,
        Cut: null,
        Impact: null,
        Penetration: null,
        Shrapnel: null,
        Burn: null,
        Cold: null,
        Acid: null,
        Electric: null
      }
    };

    // Try to copy from previous maturity's attack at same index
    if (parentMaturities && parentMaturities.length > 0) {
      for (let i = parentMaturities.length - 1; i >= 0; i--) {
        const prevMat = parentMaturities[i];
        if (prevMat.Attacks && prevMat.Attacks[index]) {
          const source = prevMat.Attacks[index];
          attack.TotalDamage = source.TotalDamage;
          attack.IsAoE = source.IsAoE || false;
          if (source.Damage) {
            attack.Damage = { ...source.Damage };
          }
          break;
        }
      }
    }

    return attack;
  }

  // === CRUD Operations ===
  function addMaturity() {
    const newMaturity = createMaturity();
    const newList = [...maturities, newMaturity];
    updateField(fieldPath, newList);
    // Expand the new maturity
    expandedMaturities[getUid(newMaturity)] = true;
  }

  function removeMaturity(mat) {
    const uid = getUid(mat);
    const newList = maturities.filter(m => m !== mat);
    updateField(fieldPath, newList);
    // Clean up expanded state
    delete expandedMaturities[uid];
  }

  function updateMaturityField(matIndex, field, value) {
    const newList = [...maturities];
    const editedMat = cloneMaturity(newList[matIndex]);
    newList[matIndex] = editedMat;

    const parts = field.split('.');
    let target = editedMat;

    for (let i = 0; i < parts.length - 1; i++) {
      if (!target[parts[i]]) target[parts[i]] = {};
      target = target[parts[i]];
    }
    target[parts[parts.length - 1]] = value;

    // Auto-update Stamina when Health changes
    if (field === 'Properties.Health' && value != null && !isNaN(value)) {
      if (!editedMat.Properties.Attributes) {
        editedMat.Properties.Attributes = {};
      }
      editedMat.Properties.Attributes.Stamina = Math.round(value / 10);
    }

    updateField(fieldPath, newList);
  }

  function addAttack(matIndex) {
    const newList = [...maturities];
    const editedMat = cloneMaturity(newList[matIndex]);
    newList[matIndex] = editedMat;
    const attacks = editedMat.Attacks || [];
    const newAttack = createAttack(attacks.length, maturities.slice(0, matIndex));
    editedMat.Attacks = [...attacks, newAttack];
    updateField(fieldPath, newList);
  }

  function removeAttack(matIndex, attackIndex) {
    const newList = [...maturities];
    const editedMat = cloneMaturity(newList[matIndex]);
    newList[matIndex] = editedMat;
    editedMat.Attacks = editedMat.Attacks.filter((_, i) => i !== attackIndex);
    updateField(fieldPath, newList);
  }

  function updateAttackField(matIndex, attackIndex, field, value) {
    const newList = [...maturities];
    const editedMat = cloneMaturity(newList[matIndex]);
    newList[matIndex] = editedMat;
    const attack = editedMat.Attacks[attackIndex];

    if (field.startsWith('Damage.')) {
      const damageType = field.split('.')[1];
      if (!attack.Damage) attack.Damage = {};
      attack.Damage[damageType] = value;
    } else {
      attack[field] = value;
    }

    updateField(fieldPath, newList);
  }

  function toggleMaturity(mat) {
    const uid = getUid(mat);
    expandedMaturities[uid] = !expandedMaturities[uid];
  }

  // Format maturity name for header
  function getMaturityLabel(mat, index) {
    return mat.Name || `Maturity ${index + 1}`;
  }

  // Get auto-generated attack name
  function getAttackName(attackIndex) {
    return attackIndex < ATTACK_NAMES.length ? ATTACK_NAMES[attackIndex] : `Attack ${attackIndex + 1}`;
  }

  // Check if an attack has any damage composition data
  function attackHasCompositionData(attack) {
    if (!attack?.Damage) return false;
    return DAMAGE_TYPES.some(dt => attack.Damage[dt.key] != null && attack.Damage[dt.key] !== 0);
  }

  // Get attack at specific index from a maturity
  function getAttackAt(matIndex, attackIndex) {
    return maturities[matIndex]?.Attacks?.[attackIndex] || null;
  }

  // Ensure a maturity has attacks up to the specified index, creating empty ones as needed
  function ensureAttacksUpToIndex(maturity, targetIndex) {
    if (!maturity.Attacks) maturity.Attacks = [];
    while (maturity.Attacks.length <= targetIndex) {
      const newIndex = maturity.Attacks.length;
      maturity.Attacks.push({
        Name: getAttackName(newIndex),
        TotalDamage: null,
        IsAoE: false,
        Damage: {
          Stab: null,
          Cut: null,
          Impact: null,
          Penetration: null,
          Shrapnel: null,
          Burn: null,
          Cold: null,
          Acid: null,
          Electric: null
        }
      });
    }
  }

  // Copy damage composition from one attack to another
  function copyComposition(fromMatIndex, fromAttackIndex, toMatIndex, toAttackIndex) {
    const sourceAttack = getAttackAt(fromMatIndex, fromAttackIndex);
    if (!sourceAttack?.Damage) return;

    const newList = [...maturities];
    const editedMat = cloneMaturity(newList[toMatIndex]);
    newList[toMatIndex] = editedMat;

    // Ensure target maturity has attacks up to the target index
    ensureAttacksUpToIndex(editedMat, toAttackIndex);

    editedMat.Attacks[toAttackIndex].Damage = { ...sourceAttack.Damage };
    updateField(fieldPath, newList);
    openCopyMenu = null;
  }

  // Copy composition to all maturities at the same attack index
  function copyToAll(fromMatIndex, attackIndex) {
    const sourceAttack = getAttackAt(fromMatIndex, attackIndex);
    if (!sourceAttack?.Damage) return;

    const newList = [...maturities];
    for (let i = 0; i < newList.length; i++) {
      if (i === fromMatIndex) continue;

      const editedMat = cloneMaturity(newList[i]);
      newList[i] = editedMat;

      // Ensure each maturity has attacks up to the target index
      ensureAttacksUpToIndex(editedMat, attackIndex);

      editedMat.Attacks[attackIndex].Damage = { ...sourceAttack.Damage };
    }
    updateField(fieldPath, newList);
    openCopyMenu = null;
  }

  function toggleCopyMenu(matIndex, attackIndex) {
    const key = `${matIndex}-${attackIndex}`;
    if (openCopyMenu === key) {
      openCopyMenu = null;
    } else {
      openCopyMenu = key;
    }
  }

  function closeCopyMenu() {
    openCopyMenu = null;
  }
</script>

<svelte:window onclick={closeCopyMenu} />

<div class="maturities-edit">
  <div class="section-header">
    <h4 class="section-title">Maturities ({maturities?.length || 0})</h4>
  </div>

  <div class="maturities-list">
    {#each maturities as maturity, matIndex (getUid(maturity))}
      <div class="maturity-item" class:expanded={expandedMaturities[getUid(maturity)]}>
        <div class="maturity-header">
          <button
            class="maturity-header-toggle"
            onclick={() => toggleMaturity(maturity)}
            type="button"
          >
            <span class="expand-icon">{expandedMaturities[getUid(maturity)] ? '▼' : '▶'}</span>
            <span class="maturity-name">{getMaturityLabel(maturity, matIndex)}</span>
            <span class="maturity-summary">
              {#if maturity.Properties?.Level}Lv.{maturity.Properties.Level}{/if}
              {#if maturity.Properties?.Health}HP: {maturity.Properties.Health}{/if}
            </span>
          </button>
          <div class="maturity-actions">
            <button
              class="btn-icon danger"
              onclick={(e) => { e.stopPropagation(); removeMaturity(maturity); }}
              title="Remove maturity"
              type="button"
            >×</button>
          </div>
        </div>

        {#if expandedMaturities[getUid(maturity)]}
          <div class="maturity-content">
            <!-- General Fields -->
            <div class="field-group">
              <h5 class="group-title">General</h5>
              <div class="field-grid">
                <label class="field">
                  <span class="field-label">Name</span>
                  <input
                    type="text"
                    value={maturity.Name || ''}
                    oninput={(e) => updateMaturityField(matIndex, 'Name', e.target.value)}
                    placeholder="e.g., Young, Mature, Old"
                  />
                </label>
                <label class="field">
                  <span class="field-label">Name Mode</span>
                  <select
                    value={maturity.NameMode || ''}
                    onchange={(e) => updateMaturityField(matIndex, 'NameMode', e.target.value || null)}
                  >
                    {#each NAME_MODES as mode}
                      <option value={mode.value || ''}>{mode.label}</option>
                    {/each}
                  </select>
                </label>
                <div class="field namemode-preview">
                  <span class="field-label">In-game name</span>
                  <span class="preview-text" class:unknown={!maturity.NameMode}>{getFullNamePreview(maturity.Name, maturity.NameMode)}</span>
                </div>
                <label class="field">
                  <span class="field-label">Level</span>
                  <input
                    type="number"
                    value={maturity.Properties?.Level ?? ''}
                    oninput={(e) => updateMaturityField(matIndex, 'Properties.Level', e.target.value ? parseInt(e.target.value) : null)}
                    min="1"
                  />
                </label>
                <label class="field">
                  <span class="field-label">Health</span>
                  <input
                    type="number"
                    value={maturity.Properties?.Health ?? ''}
                    oninput={(e) => updateMaturityField(matIndex, 'Properties.Health', e.target.value ? parseInt(e.target.value) : null)}
                    min="1"
                  />
                </label>
                {#if !isAsteroid}
                  <label class="field checkbox-field">
                    <input
                      type="checkbox"
                      checked={maturity.Properties?.Boss || false}
                      onchange={(e) => updateMaturityField(matIndex, 'Properties.Boss', e.target.checked)}
                    />
                    <span class="field-label">Boss</span>
                  </label>
                {/if}
              </div>

              {#if !isAsteroid}
                <div class="field-grid attributes">
                  <span class="field-label full">Attributes</span>
                  {#each ['Strength', 'Agility', 'Intelligence', 'Psyche', 'Stamina'] as attr}
                    <label class="field compact">
                      <span class="field-label-mini">{attr.slice(0, 3)}</span>
                      <input
                        type="number"
                        value={maturity.Properties?.Attributes?.[attr] ?? ''}
                        oninput={(e) => updateMaturityField(matIndex, `Properties.Attributes.${attr}`, e.target.value ? parseInt(e.target.value) : null)}
                        min="0"
                      />
                    </label>
                  {/each}
                </div>
              {/if}
            </div>

            {#if !isAsteroid}
              <!-- Combat Fields -->
              <div class="field-group">
                <h5 class="group-title">Combat</h5>
                <div class="field-grid">
                  <label class="field">
                    <span class="field-label">Regen Interval</span>
                    <input
                      type="number"
                      value={maturity.Properties?.RegenerationInterval ?? ''}
                      oninput={(e) => updateMaturityField(matIndex, 'Properties.RegenerationInterval', e.target.value ? parseFloat(e.target.value) : null)}
                      step="0.1"
                      min="0"
                    />
                  </label>
                  <label class="field">
                    <span class="field-label">Regen Amount</span>
                    <input
                      type="number"
                      value={maturity.Properties?.RegenerationAmount ?? ''}
                      oninput={(e) => updateMaturityField(matIndex, 'Properties.RegenerationAmount', e.target.value ? parseFloat(e.target.value) : null)}
                      step="0.1"
                      min="0"
                    />
                  </label>
                  <label class="field">
                    <span class="field-label">Miss Chance</span>
                    <input
                      type="number"
                      value={maturity.Properties?.MissChance ?? ''}
                      oninput={(e) => updateMaturityField(matIndex, 'Properties.MissChance', e.target.value ? parseFloat(e.target.value) : null)}
                      step="0.1"
                      min="0"
                      max="100"
                    />
                  </label>
                </div>

                <!-- Defense Grid -->
                <div class="field-grid defense">
                  <span class="field-label full">Defense</span>
                  {#each DAMAGE_TYPES as dmgType}
                    <label class="field compact">
                      <span class="field-label-mini">{dmgType.label}</span>
                      <input
                        type="number"
                        value={maturity.Properties?.Defense?.[dmgType.key] ?? ''}
                        oninput={(e) => updateMaturityField(matIndex, `Properties.Defense.${dmgType.key}`, e.target.value ? parseFloat(e.target.value) : 0)}
                        step="0.1"
                        min="0"
                      />
                    </label>
                  {/each}
                </div>
              </div>

              <!-- Taming -->
              <div class="field-group">
                <h5 class="group-title">Taming</h5>
                <div class="field-grid taming-grid">
                  <label class="field checkbox-field">
                    <input
                      type="checkbox"
                      checked={maturity.Properties?.Taming?.IsTameable || false}
                      onchange={(e) => {
                        updateMaturityField(matIndex, 'Properties.Taming.IsTameable', e.target.checked);
                        if (e.target.checked) {
                          updateMaturityField(matIndex, 'Properties.Taming.TamingLevel', 1);
                        } else {
                          updateMaturityField(matIndex, 'Properties.Taming.TamingLevel', null);
                        }
                      }}
                    />
                    <span class="field-label">Is Tameable</span>
                  </label>
                  <label class="field" class:disabled={!maturity.Properties?.Taming?.IsTameable}>
                    <span class="field-label">Taming Level</span>
                    <input
                      type="number"
                      value={maturity.Properties?.Taming?.TamingLevel ?? ''}
                      oninput={(e) => updateMaturityField(matIndex, 'Properties.Taming.TamingLevel', e.target.value ? parseInt(e.target.value) : null)}
                      min="1"
                      disabled={!maturity.Properties?.Taming?.IsTameable}
                    />
                  </label>
                </div>
              </div>

              <!-- Attacks -->
              <div class="field-group">
                <h5 class="group-title">Attacks ({maturity.Attacks?.length || 0})</h5>
                <div class="attacks-list">
                  {#each maturity.Attacks || [] as attack, attackIndex}
                    {@const prevAttack = getAttackAt(matIndex - 1, attackIndex)}
                    {@const nextAttack = getAttackAt(matIndex + 1, attackIndex)}
                    {@const hasCurrentData = attackHasCompositionData(attack)}
                    {@const hasPrevData = attackHasCompositionData(prevAttack)}
                    {@const hasNextData = attackHasCompositionData(nextAttack)}
                    {@const showCopyMenu = openCopyMenu === `${matIndex}-${attackIndex}`}
                    <div class="attack-item">
                      <div class="attack-header">
                        <span class="attack-name-title">{getAttackName(attackIndex)}</span>
                        <button
                          class="btn-icon danger small"
                          onclick={() => removeAttack(matIndex, attackIndex)}
                          title="Remove attack"
                          type="button"
                        >×</button>
                      </div>
                      <div class="attack-fields">
                        <label class="field compact">
                          <span class="field-label-mini">Damage</span>
                          <input
                            type="number"
                            value={attack.TotalDamage ?? ''}
                            oninput={(e) => updateAttackField(matIndex, attackIndex, 'TotalDamage', e.target.value ? parseFloat(e.target.value) : null)}
                            step="0.1"
                            min="0"
                          />
                        </label>
                        <label class="field checkbox-field compact">
                          <input
                            type="checkbox"
                            checked={attack.IsAoE || false}
                            onchange={(e) => updateAttackField(matIndex, attackIndex, 'IsAoE', e.target.checked)}
                          />
                          <span class="field-label-mini">AoE</span>
                        </label>
                      </div>
                      <div class="attack-composition">
                        <div class="composition-header">
                          <span class="field-label-mini">Composition %</span>
                          {#if matIndex > 0 || matIndex < maturities.length - 1}
                            <div class="copy-menu-wrapper">
                              <button
                                class="btn-copy"
                                onclick={(e) => { e.stopPropagation(); toggleCopyMenu(matIndex, attackIndex); }}
                                type="button"
                              >Copy...</button>
                              {#if showCopyMenu}
                                  <div class="copy-menu" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="presentation">
                                  {#if matIndex > 0 && hasPrevData}
                                    <button type="button" onclick={() => copyComposition(matIndex - 1, attackIndex, matIndex, attackIndex)}>
                                      from Previous
                                    </button>
                                  {/if}
                                  {#if matIndex > 0 && hasCurrentData}
                                    <button type="button" onclick={() => copyComposition(matIndex, attackIndex, matIndex - 1, attackIndex)}>
                                      to Previous
                                    </button>
                                  {/if}
                                  {#if matIndex < maturities.length - 1 && hasNextData}
                                    <button type="button" onclick={() => copyComposition(matIndex + 1, attackIndex, matIndex, attackIndex)}>
                                      from Next
                                    </button>
                                  {/if}
                                  {#if matIndex < maturities.length - 1 && hasCurrentData}
                                    <button type="button" onclick={() => copyComposition(matIndex, attackIndex, matIndex + 1, attackIndex)}>
                                      to Next
                                    </button>
                                  {/if}
                                  {#if hasCurrentData && maturities.length > 1}
                                    <button type="button" onclick={() => copyToAll(matIndex, attackIndex)}>
                                      to All
                                    </button>
                                  {/if}
                                  {#if !hasPrevData && !hasNextData && !hasCurrentData}
                                    <span class="copy-menu-empty">No data to copy</span>
                                  {/if}
                                </div>
                              {/if}
                            </div>
                          {/if}
                        </div>
                        <div class="composition-grid">
                          {#each DAMAGE_TYPES as dmgType}
                            <label class="field compact">
                              <span class="field-label-mini">{dmgType.label}</span>
                              <input
                                type="number"
                                value={attack.Damage?.[dmgType.key] ?? ''}
                                oninput={(e) => updateAttackField(matIndex, attackIndex, `Damage.${dmgType.key}`, e.target.value ? parseFloat(e.target.value) : null)}
                                step="0.1"
                                min="0"
                                max="100"
                              />
                            </label>
                          {/each}
                        </div>
                      </div>
                    </div>
                  {/each}
                  <button class="btn-add" onclick={() => addAttack(matIndex)} type="button">
                    <span>+</span> Add Attack
                  </button>
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/each}

    <button class="btn-add" onclick={addMaturity} type="button">
      <span>+</span> Add Maturity
    </button>
  </div>
</div>

<style>
  .maturities-edit {
    width: 100%;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .section-title {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
  }

  .maturities-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .maturity-item {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
  }

  .maturity-item.expanded {
    border-color: var(--accent-color, #4a9eff);
  }

  .maturity-header {
    display: flex;
    align-items: center;
    width: 100%;
    transition: background-color 0.15s;
  }

  .maturity-header:hover {
    background-color: var(--hover-color);
  }

  .maturity-header-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    flex: 1;
    padding: 6px 10px;
    background: none;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    text-align: left;
    font-size: 12px;
  }

  .expand-icon {
    font-size: 9px;
    color: var(--text-muted, #999);
    width: 12px;
    flex-shrink: 0;
  }

  .maturity-name {
    font-weight: 600;
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .maturity-summary {
    font-size: 11px;
    color: var(--text-muted, #999);
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .maturity-actions {
    display: flex;
    gap: 2px;
    margin-left: 4px;
    flex-shrink: 0;
  }

  .maturity-content {
    padding: 10px;
    border-top: 1px solid var(--border-color, #555);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .group-title {
    margin: 0;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .field-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    align-items: end;
  }

  .field-grid.defense,
  .field-grid.attributes {
    grid-template-columns: repeat(5, 1fr);
  }

  .field-grid.taming-grid {
    grid-template-columns: auto 1fr;
  }

  .field-label.full {
    grid-column: 1 / -1;
    margin-bottom: 2px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .field.compact {
    gap: 2px;
  }

  .field.disabled {
    opacity: 0.5;
  }

  .field-label {
    font-size: 12px;
    color: var(--text-muted, #999);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .field-label-mini {
    font-size: 11px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
  }

  .field select {
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
    height: 26px;
  }

  .field select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .namemode-preview {
    min-width: 0;
  }

  .preview-text {
    font-size: 12px;
    color: var(--text-color);
    padding: 4px 6px;
    background: var(--secondary-color);
    border-radius: 3px;
    border: 1px solid var(--border-color, #555);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    display: block;
    height: 26px;
    box-sizing: border-box;
    line-height: 18px;
  }

  .preview-text.unknown {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .field input[type="text"],
  .field input[type="number"] {
    padding: 4px 6px;
    font-size: 12px;
    background-color: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-color);
    width: 100%;
    box-sizing: border-box;
    height: 26px;
  }

  .field input[type="number"] {
    appearance: textfield;
    -moz-appearance: textfield;
  }

  .field input[type="number"]::-webkit-outer-spin-button,
  .field input[type="number"]::-webkit-inner-spin-button {
    appearance: none;
    -webkit-appearance: none;
    margin: 0;
  }

  .field input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .checkbox-field {
    flex-direction: row;
    align-items: center;
    gap: 4px;
    height: 26px;
    justify-content: flex-start;
  }

  .checkbox-field input[type="checkbox"] {
    width: 14px;
    height: 14px;
    cursor: pointer;
    flex-shrink: 0;
  }

  /* Attacks */
  .attacks-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .attack-item {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .attack-header {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .attack-name-title {
    flex: 1;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-color);
  }

  .attack-fields {
    display: flex;
    gap: 10px;
    align-items: flex-end;
  }

  .attack-fields .field {
    flex: 0 0 auto;
    width: 80px;
  }

  .attack-fields .checkbox-field {
    flex: 0 0 auto;
    width: auto;
    height: 28px;
    margin-bottom: 0;
  }

  .attack-composition {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .composition-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .copy-menu-wrapper {
    position: relative;
  }

  .btn-copy {
    padding: 2px 6px;
    font-size: 10px;
    background: transparent;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-copy:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .copy-menu {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 2px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    z-index: 100;
    min-width: 120px;
    overflow: hidden;
  }

  .copy-menu button {
    display: block;
    width: 100%;
    padding: 6px 10px;
    font-size: 11px;
    text-align: left;
    background: none;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    transition: background-color 0.15s;
  }

  .copy-menu button:hover {
    background-color: var(--hover-color);
  }

  .copy-menu-empty {
    display: block;
    padding: 6px 10px;
    font-size: 11px;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .composition-grid {
    display: grid;
    grid-template-columns: repeat(9, 1fr);
    gap: 3px;
  }

  .composition-grid .field {
    min-width: 0;
  }

  .composition-grid .field input {
    padding: 2px 3px;
    font-size: 10px;
    text-align: center;
    height: 22px;
  }

  /* Buttons */
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-icon:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .btn-icon:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-icon.danger:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-icon.small {
    width: 18px;
    height: 18px;
    font-size: 12px;
  }

  .btn-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 6px 10px;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    font-size: 11px;
    line-height: 1;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-add:hover {
    background-color: var(--hover-color);
    color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
  }

  /* Mobile adjustments */
  @media (max-width: 899px) {
    .field-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .field-grid.defense,
    .field-grid.attributes {
      grid-template-columns: repeat(3, 1fr);
    }

    .composition-grid {
      grid-template-columns: repeat(5, 1fr);
    }

    .maturity-summary {
      display: none;
    }
  }

  @media (max-width: 600px) {
    .field-grid {
      grid-template-columns: 1fr;
    }

    .field-grid.defense,
    .field-grid.attributes {
      grid-template-columns: repeat(3, 1fr);
    }

    .composition-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }
</style>
