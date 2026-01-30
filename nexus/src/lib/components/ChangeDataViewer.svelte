<script>
  // @ts-nocheck
  /**
   * ChangeDataViewer - Smart JSON viewer for entity change data
   *
   * This component renders entity data in a human-readable format, understanding
   * common patterns in the Entropia Nexus entity structures.
   *
   * IMPORTANT: Update this component when adding new entity types to the change system.
   * Currently supported entities:
   * - Weapon, ArmorSet, MedicalTool, MedicalChip, Refiner, Scanner, Finder, Excavator
   * - TeleportChip, EffectChip, MiscTool, WeaponAmplifier, WeaponVisionAttachment
   * - Absorber, FinderAmplifier, ArmorPlating, MindforceImplant, Blueprint, Material
   * - Pet, Consumable, CreatureControlCapsule, Vehicle, Furniture, Decoration
   * - StorageContainer, Sign, Clothing, Mob, Vendor, RefiningRecipe, Shop
   */

  import { getTypeLink } from '$lib/util.js';
  import TextViewerDialog from './TextViewerDialog.svelte';
  import { matchArrayItems, hasChanged, getItemIdentifier } from '$lib/utils/compareJson.js';

  export let data = {};
  export let previousData = null; // For diff highlighting
  export let entity = ''; // Entity type for context-aware rendering
  export let showChangesOnly = false; // Only show fields that changed
  export let parentField = ''; // Track parent field name for better type inference

  let expandedSections = {};

  // Create a key that changes when previousData changes to force diff recalculation
  // This ensures background colors update when switching comparison versions
  $: previousDataKey = previousData ? JSON.stringify(previousData) : 'none';

  // Text viewer dialog state
  let showTextDialog = false;
  let textDialogTitle = '';
  let textDialogContent = '';

  // Fields that typically contain long text content
  const longTextFields = ['Description', 'Notes', 'Comment', 'Details', 'Info'];
  const LONG_TEXT_THRESHOLD = 100; // Characters before showing expand button

  function isLongText(value, key) {
    if (typeof value !== 'string') return false;
    // Check if it's a known long text field or exceeds threshold
    if (longTextFields.includes(key)) return value.length > 50;
    return value.length > LONG_TEXT_THRESHOLD || value.includes('\n');
  }

  function openTextDialog(title, content) {
    textDialogTitle = title;
    textDialogContent = content;
    showTextDialog = true;
  }

  function closeTextDialog() {
    showTextDialog = false;
  }

  // Map field names to their entity types for linking
  const fieldTypeMap = {
    'Species': 'Mob',
    'Maturity': null, // Part of mob, no separate link
    'Ammo': 'Material',
    'ProfessionHit': 'Profession',
    'ProfessionDmg': 'Profession',
    'DefensiveProfession': 'Profession',
    'ScanningProfession': 'Profession',
    'Planet': null, // No link for planets currently
    'Type': null,
    'Category': null,
    'AttachmentType': null,
    'Effect': null // Effects are not directly linkable
  };

  // Map parent field + field name to type (for nested contexts)
  const nestedFieldTypeMap = {
    'Loots.Item': 'Material',
    'EffectsOnEquip.Effect': null,
    'EffectsOnUse.Effect': null,
    'Tiers.Material': 'Material',
    'BlueprintMaterials.Material': 'Material',
    'Ingredients.Material': 'Material',
    'Materials.Material': 'Material'
  };

  // Map entity prop values to getTypeLink types
  const entityTypeMap = {
    'Weapon': 'Weapon',
    'ArmorSet': 'Armor',
    'MedicalTool': 'MedicalTool',
    'MedicalChip': 'MedicalChip',
    'Refiner': 'Refiner',
    'Scanner': 'Scanner',
    'Finder': 'Finder',
    'Excavator': 'Excavator',
    'TeleportChip': 'TeleportationChip',
    'EffectChip': 'EffectChip',
    'MiscTool': 'MiscTool',
    'WeaponAmplifier': 'WeaponAmplifier',
    'WeaponVisionAttachment': 'WeaponVisionAttachment',
    'Absorber': 'Absorber',
    'FinderAmplifier': 'FinderAmplifier',
    'ArmorPlating': 'ArmorPlating',
    'MindforceImplant': 'MindforceImplant',
    'Blueprint': 'Blueprint',
    'Material': 'Material',
    'Pet': 'Pet',
    'Consumable': 'Consumable',
    'CreatureControlCapsule': 'CreatureControlCapsule',
    'Vehicle': 'Vehicle',
    'Furniture': 'Furniture',
    'Decoration': 'Decoration',
    'StorageContainer': 'StorageContainer',
    'Sign': 'Sign',
    'Clothing': 'Clothing',
    'Mob': 'Mob',
    'Vendor': 'Vendor'
  };

  // Properties that should be grouped and labeled nicely
  const propertyGroups = {
    'Economy': 'Economy Stats',
    'Damage': 'Damage Values',
    'Defense': 'Defense Values',
    'Skill': 'Skill Information',
    'Coordinates': 'Location',
    'Attributes': 'Attributes',
    'Taming': 'Taming Info',
    'Mindforce': 'Mindforce'
  };

  // Get the wiki link for a named entity reference
  function getEntityLink(name, fieldName, contextField = null) {
    if (!name) return null;

    // Check nested field type map first (parent.field context)
    const nestedKey = contextField ? `${contextField}.${fieldName}` : (parentField ? `${parentField}.${fieldName}` : null);
    if (nestedKey && nestedKey in nestedFieldTypeMap) {
      const type = nestedFieldTypeMap[nestedKey];
      if (type) {
        return getTypeLink(name, type);
      }
      return null; // Explicitly null means no link
    }

    // Check if field has a specific type mapping
    if (fieldName in fieldTypeMap) {
      const type = fieldTypeMap[fieldName];
      if (type) {
        return getTypeLink(name, type);
      }
      return null;
    }

    // For 'Item' field without explicit mapping, check context
    if (fieldName === 'Item') {
      // In Loots context, Item is a Material
      if (parentField === 'Loots' || contextField === 'Loots') {
        return getTypeLink(name, 'Material');
      }
    }

    return null;
  }

  // Determine if a value is a NamedEntity reference
  function isNamedEntity(value) {
    return value && typeof value === 'object' && !Array.isArray(value) &&
           Object.keys(value).length === 1 && 'Name' in value;
  }

  function toggleSection(key) {
    expandedSections[key] = !expandedSections[key];
    expandedSections = expandedSections;
  }

  function formatValue(value) {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') return value.toLocaleString();
    return String(value);
  }

  function getPreview(value) {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') return value.toLocaleString();
    if (typeof value === 'string') return value.length > 50 ? value.slice(0, 50) + '...' : value;
    if (Array.isArray(value)) return `[${value.length} item${value.length !== 1 ? 's' : ''}]`;
    if (isNamedEntity(value)) return value.Name;
    if (typeof value === 'object') {
      const keys = Object.keys(value);
      if (keys.length <= 3) return keys.map(k => `${k}: ${getPreview(value[k])}`).join(', ');
      return `{${keys.length} properties}`;
    }
    return String(value);
  }

  function getFieldLabel(key) {
    return key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()).trim();
  }

  function isPrimitive(value) {
    return value === null || value === undefined ||
           typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean';
  }

  // Keys to ignore during comparison - API-only fields
  const ignoredKeys = ['Links', '$Url', 'ItemId'];

  function getDiffInfo(key, currentValue) {
    if (!previousData) return { type: 'none', oldValue: null };
    if (!(key in previousData)) return { type: 'added', oldValue: null };

    const oldValue = previousData[key];

    // For arrays, use matchArrayItems which is more accurate for identifier-based matching
    if (Array.isArray(currentValue) && Array.isArray(oldValue)) {
      const matched = matchArrayItems(oldValue, currentValue);
      if (matched.some(m => m.status !== 'unchanged')) {
        return { type: 'changed', oldValue };
      }
      return { type: 'none', oldValue: null };
    }

    // Use hasChanged from compareJson.js which properly ignores API-only fields
    if (hasChanged(oldValue, currentValue)) {
      return { type: 'changed', oldValue };
    }
    return { type: 'none', oldValue: null };
  }

  $: removedKeys = previousData ? Object.keys(previousData).filter(k => !(k in data)) : [];

  function getSortedKeys(obj) {
    // Priority keys always come first in this order (Name first for better identification)
    const priorityKeys = ['Name', 'Id', 'Properties'];
    let keys = Object.keys(obj);

    // Filter to only changed keys if showChangesOnly is enabled
    if (showChangesOnly && previousData) {
      keys = keys.filter(key => {
        // Always show Id and Name for context
        if (key === 'Id' || key === 'Name') return true;

        const value = obj[key];

        // For arrays, check if any items have changed using matchArrayItems
        // This is more accurate than hasChanged for arrays with identifier-based matching
        if (Array.isArray(value) && Array.isArray(previousData[key])) {
          const matched = matchArrayItems(previousData[key], value);
          return matched.some(m => m.status !== 'unchanged');
        }

        const diffInfo = getDiffInfo(key, obj[key]);
        return diffInfo.type !== 'none';
      });
    }

    // Categorize keys by value type
    const getValueCategory = (key) => {
      const value = obj[key];
      if (Array.isArray(value)) return 3; // Arrays last
      if (value && typeof value === 'object') return 2; // Objects second
      return 1; // Primitives first
    };

    return keys.sort((a, b) => {
      // Priority keys come first
      const aIdx = priorityKeys.indexOf(a);
      const bIdx = priorityKeys.indexOf(b);
      if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
      if (aIdx !== -1) return -1;
      if (bIdx !== -1) return 1;

      // Then sort by value type: primitives -> objects -> arrays
      const aCat = getValueCategory(a);
      const bCat = getValueCategory(b);
      if (aCat !== bCat) return aCat - bCat;

      // Finally, alphabetical within same category
      return a.localeCompare(b);
    });
  }

  // Format value change as "oldValue → newValue"
  function formatValueChange(oldValue, newValue) {
    const oldStr = oldValue === null || oldValue === undefined ? '<empty>' : formatValue(oldValue);
    const newStr = newValue === null || newValue === undefined ? '<empty>' : formatValue(newValue);
    return `${oldStr} → ${newStr}`;
  }

  // Get sorted keys for array items - no filtering, shows all properties
  // Array items are already filtered at the array level, so we show all their properties
  function getArrayItemKeys(obj) {
    const priorityKeys = ['Name', 'Id', 'Properties'];
    let keys = Object.keys(obj).filter(k => !ignoredKeys.includes(k));

    const getValueCategory = (key) => {
      const value = obj[key];
      if (Array.isArray(value)) return 3;
      if (value && typeof value === 'object') return 2;
      return 1;
    };

    return keys.sort((a, b) => {
      const aIdx = priorityKeys.indexOf(a);
      const bIdx = priorityKeys.indexOf(b);
      if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
      if (aIdx !== -1) return -1;
      if (bIdx !== -1) return 1;
      const aCat = getValueCategory(a);
      const bCat = getValueCategory(b);
      if (aCat !== bCat) return aCat - bCat;
      return a.localeCompare(b);
    });
  }
</script>

<style>
  .change-data-viewer {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
  }

  .data-field {
    border-bottom: 1px solid var(--border-color);
  }

  .data-field:last-child {
    border-bottom: none;
  }

  .field-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    cursor: pointer;
    transition: background-color 0.15s ease;
    user-select: none;
    gap: 8px;
  }

  .field-header:hover {
    background-color: var(--hover-color);
  }

  .field-header.primitive {
    cursor: default;
  }

  .field-header.primitive:hover {
    background-color: transparent;
  }

  .field-key {
    font-weight: 500;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .field-value {
    color: var(--text-muted);
    font-size: 13px;
    text-align: right;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }

  .field-value.string { color: #22c55e; }
  .field-value.number { color: #3b82f6; }
  .field-value.boolean { color: #f59e0b; }
  .field-value.null { color: var(--text-muted); font-style: italic; }

  .field-content {
    padding: 6px 12px 6px 20px;
    background-color: var(--primary-color);
    border-top: 1px solid var(--border-color);
  }

  /* Named entity reference */
  .named-entity {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 1px 6px;
    background-color: rgba(59, 130, 246, 0.15);
    border-radius: 3px;
    font-size: 13px;
    color: var(--accent-color);
    text-decoration: none;
  }

  a.named-entity:hover {
    background-color: rgba(59, 130, 246, 0.25);
    text-decoration: underline;
  }


  /* Diff indicators */
  .diff-indicator {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .diff-added { background-color: #22c55e; }
  .diff-changed { background-color: #f59e0b; }
  .diff-removed { background-color: #ef4444; }

  .field-header.changed { background-color: rgba(245, 158, 11, 0.1); }
  .field-header.added { background-color: rgba(34, 197, 94, 0.1); }
  .field-header.removed { background-color: rgba(239, 68, 68, 0.1); opacity: 0.7; }

  /* Array items - compact but readable */
  .array-items {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .array-item {
    padding: 6px 10px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .array-item.added {
    background-color: rgba(34, 197, 94, 0.1);
    border-color: rgba(34, 197, 94, 0.3);
  }

  .array-item.removed {
    background-color: rgba(239, 68, 68, 0.1);
    border-color: rgba(239, 68, 68, 0.3);
    opacity: 0.7;
  }

  .array-item.changed {
    background-color: rgba(245, 158, 11, 0.1);
    border-color: rgba(245, 158, 11, 0.3);
  }

  .status-added { background-color: #22c55e !important; color: white; }
  .status-removed { background-color: #ef4444 !important; color: white; }
  .status-changed { background-color: #f59e0b !important; color: white; }

  .removed-text { text-decoration: line-through; opacity: 0.7; }
  .prop-changed { font-weight: 500; }

  /* Value change display */
  .value-change {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
  }

  .value-change .old-value {
    color: var(--error-color);
    text-decoration: line-through;
    opacity: 0.8;
  }

  .value-change .arrow {
    color: var(--text-muted);
    font-size: 11px;
  }

  .value-change .new-value {
    color: var(--success-color);
  }

  .array-item-inline {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .array-index {
    font-size: 10px;
    color: var(--text-muted);
    background-color: var(--hover-color);
    padding: 1px 4px;
    border-radius: 3px;
    flex-shrink: 0;
    min-width: 14px;
    text-align: center;
  }

  .array-index-spacer {
    display: inline-block;
    width: 14px;
    flex-shrink: 0;
  }

  .array-item-content {
    flex: 1;
    min-width: 0;
  }

  /* Expand/collapse indicator */
  .expand-icon {
    font-size: 10px;
    color: var(--text-muted);
    transition: transform 0.2s ease;
  }

  .expand-icon.expanded {
    transform: rotate(90deg);
  }

  /* Property group */
  .property-group-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    background-color: var(--hover-color);
    padding: 1px 4px;
    border-radius: 3px;
  }

  .simple-value {
    color: var(--text-color);
    font-size: 13px;
  }

  /* Nested items - reduce indent */
  .nested-content {
    margin-left: 8px;
  }

  .inline-props {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    font-size: 13px;
  }

  .inline-prop {
    display: flex;
    gap: 4px;
  }

  .inline-prop-key {
    color: var(--text-muted);
  }

  .inline-prop-value {
    color: var(--text-color);
  }

  /* Expand text button */
  .expand-text-btn {
    background: none;
    border: none;
    padding: 2px 4px;
    cursor: pointer;
    border-radius: 3px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: background-color 0.15s ease;
    margin-left: 4px;
  }

  .expand-text-btn:hover {
    background-color: var(--hover-color);
  }

  .expand-text-icon {
    font-size: 12px;
    opacity: 0.7;
  }

  .expand-text-btn:hover .expand-text-icon {
    opacity: 1;
  }
</style>

<div class="change-data-viewer">
  {#key previousDataKey}
  {#each getSortedKeys(data) as key (key)}
    {@const value = data[key]}
    {@const diffInfo = getDiffInfo(key, value)}
    {@const isExpanded = expandedSections[key]}

    <div class="data-field">
      {#if isPrimitive(value)}
        <div class="field-header primitive" class:changed={diffInfo.type === 'changed'} class:added={diffInfo.type === 'added'}>
          <span class="field-key">
            {#if diffInfo.type !== 'none'}
              <span class="diff-indicator" class:diff-added={diffInfo.type === 'added'} class:diff-changed={diffInfo.type === 'changed'}></span>
            {/if}
            {getFieldLabel(key)}
            {#if isLongText(value, key)}
              <button type="button" class="expand-text-btn" on:click={() => openTextDialog(getFieldLabel(key), value)} title="View full text">
                <span class="expand-text-icon">&#x1F50D;</span>
              </button>
            {/if}
          </span>
          {#if diffInfo.type === 'changed'}
            <span class="value-change">
              <span class="old-value">{formatValue(diffInfo.oldValue)}</span>
              <span class="arrow">→</span>
              <span class="new-value">{formatValue(value)}</span>
              {#if isLongText(diffInfo.oldValue, key) || isLongText(value, key)}
                <button type="button" class="expand-text-btn" on:click={() => openTextDialog(`${getFieldLabel(key)} (Old → New)`, `OLD:\n${diffInfo.oldValue || '<empty>'}\n\n---\n\nNEW:\n${value || '<empty>'}`)} title="View full text comparison">
                  <span class="expand-text-icon">&#x1F50D;</span>
                </button>
              {/if}
            </span>
          {:else}
            <span class="field-value"
                  class:string={typeof value === 'string'}
                  class:number={typeof value === 'number'}
                  class:boolean={typeof value === 'boolean'}
                  class:null={value === null || value === undefined}>
              {formatValue(value)}
            </span>
          {/if}
        </div>
      {:else if isNamedEntity(value)}
        {@const link = getEntityLink(value.Name, key)}
        {@const oldName = diffInfo.oldValue?.Name}
        <div class="field-header primitive" class:changed={diffInfo.type === 'changed'} class:added={diffInfo.type === 'added'}>
          <span class="field-key">
            {#if diffInfo.type !== 'none'}
              <span class="diff-indicator" class:diff-added={diffInfo.type === 'added'} class:diff-changed={diffInfo.type === 'changed'}></span>
            {/if}
            {getFieldLabel(key)}
          </span>
          {#if diffInfo.type === 'changed' && oldName}
            <span class="value-change">
              <span class="old-value">{oldName}</span>
              <span class="arrow">→</span>
              {#if link}
                <a href={link} class="named-entity">
                  {value.Name}
                </a>
              {:else}
                <span class="new-value">{value.Name}</span>
              {/if}
            </span>
          {:else if link}
            <a href={link} class="named-entity">{value.Name}</a>
          {:else}
            <span class="named-entity">{value.Name}</span>
          {/if}
        </div>
      {:else}
        <!-- svelte-ignore a11y-click-events-have-key-events -->
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div class="field-header" class:changed={diffInfo.type === 'changed'} class:added={diffInfo.type === 'added'} on:click={() => toggleSection(key)}>
          <span class="field-key">
            <span class="expand-icon" class:expanded={isExpanded}>▶</span>
            {#if diffInfo.type !== 'none'}
              <span class="diff-indicator" class:diff-added={diffInfo.type === 'added'} class:diff-changed={diffInfo.type === 'changed'}></span>
            {/if}
            {getFieldLabel(key)}
            {#if propertyGroups[key]}
              <span class="property-group-label">{propertyGroups[key]}</span>
            {/if}
          </span>
          <span class="field-value">{getPreview(value)}</span>
        </div>

        {#if isExpanded}
          <div class="field-content">
            {#if Array.isArray(value)}
              {@const allMatchedItems = previousData && Array.isArray(diffInfo.oldValue)
                ? matchArrayItems(diffInfo.oldValue, value)
                : value.map(v => ({ old: null, new: v, status: 'unchanged' }))}
              {@const matchedItems = showChangesOnly
                ? allMatchedItems.filter(m => m.status !== 'unchanged')
                : allMatchedItems}
              {@const hasAnyChangedItems = allMatchedItems.some(m => m.status !== 'unchanged')}
              <div class="array-items">
                {#each matchedItems as matched, i (`${getItemIdentifier(matched.new || matched.old) ?? 'item'}-${i}`)}
                  {@const item = matched.new || matched.old}
                  {@const itemStatus = matched.status}
                  {@const matchedOld = matched.old}
                  <div class="array-item"
                       class:added={itemStatus === 'added'}
                       class:removed={itemStatus === 'removed'}
                       class:changed={itemStatus === 'changed'}>
                    <div class="array-item-inline">
                      {#if itemStatus !== 'unchanged'}
                        <span class="array-index"
                              class:status-added={itemStatus === 'added'}
                              class:status-removed={itemStatus === 'removed'}
                              class:status-changed={itemStatus === 'changed'}>
                          {#if itemStatus === 'added'}+
                          {:else if itemStatus === 'removed'}-
                          {:else if itemStatus === 'changed'}~{/if}
                        </span>
                      {:else if hasAnyChangedItems}
                        <span class="array-index-spacer"></span>
                      {/if}
                      {#if typeof item === 'object' && item !== null}
                        {@const sortedKeys = getArrayItemKeys(item)}
                        {#if sortedKeys.length > 0 && sortedKeys.length <= 5 && sortedKeys.every(k => isPrimitive(item[k]))}
                          <div class="inline-props">
                            {#each sortedKeys as propKey (propKey)}
                              {@const propChanged = matchedOld && hasChanged(matchedOld[propKey], item[propKey])}
                              <span class="inline-prop" class:prop-changed={propChanged}>
                                <span class="inline-prop-key">{getFieldLabel(propKey)}:</span>
                                {#if propChanged && matchedOld}
                                  <span class="inline-prop-value value-change">
                                    <span class="old-value">{formatValue(matchedOld[propKey])}</span>
                                    <span class="arrow">→</span>
                                    <span class="new-value">{formatValue(item[propKey])}</span>
                                  </span>
                                {:else}
                                  <span class="inline-prop-value" class:removed-text={itemStatus === 'removed'}>{formatValue(item[propKey])}</span>
                                {/if}
                              </span>
                            {/each}
                          </div>
                        {:else if sortedKeys.length > 0}
                          <div class="array-item-content nested-content">
                            <svelte:self
                              data={Object.fromEntries(sortedKeys.map(k => [k, item[k]]))}
                              previousData={matchedOld
                                ? Object.fromEntries(sortedKeys.map(k => [k, matchedOld[k]]))
                                : null}
                              {entity}
                              {showChangesOnly}
                              parentField={key}
                            />
                          </div>
                        {/if}
                      {:else}
                        <span class="simple-value" class:removed-text={itemStatus === 'removed'}>{formatValue(item)}</span>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {:else if typeof value === 'object'}
              <div class="nested-content">
                <svelte:self
                  data={value}
                  previousData={diffInfo.oldValue}
                  {entity}
                  {showChangesOnly}
                  parentField={key}
                />
              </div>
            {/if}
          </div>
        {/if}
      {/if}
    </div>
  {/each}

  {#each removedKeys as key (key)}
    {@const value = previousData[key]}
    <div class="data-field">
      <div class="field-header removed">
        <span class="field-key">
          <span class="diff-indicator diff-removed"></span>
          {getFieldLabel(key)}
          <span style="color: var(--error-color); font-size: 11px;">(removed)</span>
        </span>
        <span class="field-value" style="color: var(--error-color);">{getPreview(value)}</span>
      </div>
    </div>
  {/each}
  {/key}
</div>

<TextViewerDialog
  show={showTextDialog}
  title={textDialogTitle}
  content={textDialogContent}
  on:close={closeTextDialog}
/>
