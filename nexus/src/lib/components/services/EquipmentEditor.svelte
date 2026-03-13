<script lang="ts">
  // @ts-nocheck
  import { apiCall, getTypeLink } from '$lib/util';
  
  
  let showAddModal = $state(false);
  let editingIndex = $state(null);
  
  // Form fields
  let itemName = $state('');
  let itemType = $state('');
  let tier = $state(null);
  let isPrimary = $state(false); // Default to false, auto-check when appropriate
  let extraPrice = $state(null);
  let notes = $state('');
  
  // Attachments (for weapons and armor)
  let attachments = $state({
    // For ranged weapons
    amplifier_id: null,
    amplifier_name: null,
    scope_id: null,
    scope_name: null,
    scope_sight_id: null,  // Sight attached to the scope (nested)
    scope_sight_name: null,
    sight_id: null,
    sight_name: null,
    absorber_id: null,
    absorber_name: null,
    // For melee weapons
    matrix_id: null,
    matrix_name: null,
    // For mindforce weapons
    implant_id: null,
    implant_name: null,
    enhancerType: 'Damage', // 'Damage', 'Range', 'Economy', or 'Accuracy'
    // For armor (plating)
    plate_id: null,
    plate_name: null
  });
  
  // Available items from API
  let availableItems = $state({});
  let loadingItems = $state(false);
  
  const healingItemTypes = [
    { value: 'medicaltools', label: 'Medical Tool' },
    { value: 'medicalchips', label: 'Medical Chip' },
    { value: 'armorsets', label: 'Armor Set' },
    { value: 'clothings', label: 'Clothing/Accessory' },
    { value: 'consumables', label: 'Consumable' }
  ];
  
  const dpsItemTypes = [
    { value: 'weapons', label: 'Weapon' },
    { value: 'armorsets', label: 'Armor Set' },
    { value: 'medicaltools', label: 'Medical Tool' },
    { value: 'clothings', label: 'Clothing/Accessory' },
    { value: 'pets', label: 'Pet' },
    { value: 'consumables', label: 'Consumable' }
  ];
  
  import { hasItemTag } from '$lib/util';
  let { serviceType, equipment = $bindable([]), clothings = [] } = $props();
  

  
  async function loadItemsForType(type) {
    if (availableItems[type]) return; // Already loaded
    
    loadingItems = true;
    try {
      // Map consumables to the correct API endpoint
      const endpoint = type === 'consumables' ? 'stimulants' : type;
      const items = await apiCall(fetch, `/${endpoint}`);
      availableItems[type] = items || [];
    } catch (error) {
      console.error(`Failed to load ${type}:`, error);
      availableItems[type] = [];
    } finally {
      loadingItems = false;
    }
  }
  
  // Helper to get clothing slot from preloaded clothing items
  function getClothingSlot(itemName) {
    if (!itemName || !clothings) return null;
    const clothingItem = clothings.find(item => item.Name === itemName);
    if (clothingItem?.Properties?.Slot) {
      return clothingItem.Properties.Slot.toLowerCase().replace(/\s+/g, '_');
    }
    return null;
  }
  
  
  
  function checkHasPrimary(type, itemSlot = null) {
    // Check if a primary item of this type/slot already exists
    return equipment.some((item, idx) => {
      if (editingIndex === idx) return false; // Exclude item being edited
      if (!item.is_primary) return false;
      
      // For clothing, check both type and slot (only 1 primary per slot)
      if (type === 'clothings') {
        return item.item_type === 'clothings' && item.clothing_slot === itemSlot;
      }
      
      // For armor sets, only 1 primary armor set allowed
      if (type === 'armorsets') {
        return item.item_type === 'armorsets';
      }
      
      // For healing services: medical tools and medical chips share a slot
      if (serviceType === 'healing' && (type === 'medicaltools' || type === 'medicalchips')) {
        return item.item_type === 'medicaltools' || item.item_type === 'medicalchips';
      }
      
      // For other types, just check the type
      return item.item_type === type;
    });
  }
  
  function validatePrimaryConflict(currentItemSlot = null) {
    if (!isPrimary) return null; // No conflict if not marking as primary
    
    const conflictingItem = equipment.find((item, idx) => {
      if (editingIndex === idx) return false;
      if (!item.is_primary) return false;
      
      // For clothing, check both type and slot (only 1 primary per slot)
      if (itemType === 'clothings') {
        return item.item_type === 'clothings' && item.clothing_slot === currentItemSlot;
      }
      
      // For armor sets, only 1 primary armor set allowed
      if (itemType === 'armorsets') {
        return item.item_type === 'armorsets';
      }
      
      // For healing services: medical tools and medical chips share a slot
      if (serviceType === 'healing' && (itemType === 'medicaltools' || itemType === 'medicalchips')) {
        return item.item_type === 'medicaltools' || item.item_type === 'medicalchips';
      }
      
      // For other types, just check the type
      return item.item_type === itemType;
    });
    
    return conflictingItem;
  }
  
  function autoCheckPrimary() {
    // Don't auto-check if editing an existing item
    if (editingIndex !== null) return;
    
    // Get the slot from the selected item if it's clothing
    let itemSlot = null;
    if (itemType === 'clothings' && itemName) {
      const selectedItem = availableItems[itemType]?.find(item => item.Name === itemName.trim());
      if (selectedItem?.Properties?.Slot) {
        itemSlot = selectedItem.Properties.Slot.toLowerCase().replace(/\s+/g, '_');
      }
    }
    
    const hasPrimary = checkHasPrimary(itemType, itemSlot);
    if (!hasPrimary) {
      isPrimary = true;
    }
  }
  




  
  // Helper to look up attachment IDs when names are selected
  function updateAmplifierId() {
    const item = availableItems['weaponamplifiers']?.find(x => x.Name === attachments.amplifier_name);
    attachments.amplifier_id = item?.ItemId || null;
  }
  
  function updateScopeId() {
    const item = availableItems['weaponvisionattachments']?.find(x => x.Name === attachments.scope_name);
    attachments.scope_id = item?.ItemId || null;
  }
  
  function updateSightId() {
    const item = availableItems['weaponvisionattachments']?.find(x => x.Name === attachments.sight_name);
    attachments.sight_id = item?.ItemId || null;
  }
  
  function updateAbsorberId() {
    const item = availableItems['absorbers']?.find(x => x.Name === attachments.absorber_name);
    attachments.absorber_id = item?.ItemId || null;
  }
  
  function updatePlateId() {
    const item = availableItems['armorplatings']?.find(x => x.Name === attachments.plate_name);
    attachments.plate_id = item?.ItemId || null;
  }

  function updateMatrixId() {
    const item = availableItems['weaponamplifiers']?.find(x => x.Name === attachments.matrix_name);
    attachments.matrix_id = item?.ItemId || null;
  }

  function updateImplantId() {
    const item = availableItems['mindforceimplants']?.find(x => x.Name === attachments.implant_name);
    attachments.implant_id = item?.ItemId || null;
  }

  function updateScopeSightId() {
    const item = availableItems['weaponvisionattachments']?.find(x => x.Name === attachments.scope_sight_name);
    attachments.scope_sight_id = item?.ItemId || null;
  }
  
  function openAddModal() {
    resetForm();
    editingIndex = null;
    showAddModal = true;
  }
  
  function openEditModal(index) {
    const item = equipment[index];
    itemName = item.item_name || '';
    itemType = item.item_type || '';
    tier = item.tier;
    isPrimary = item.is_primary !== false;
    extraPrice = item.extra_price;
    notes = item.notes || '';

    // Reset attachments first, then load from item if they exist
    attachments = {
      // Ranged weapon attachments
      amplifier_id: null,
      amplifier_name: null,
      scope_id: null,
      scope_name: null,
      scope_sight_id: null,
      scope_sight_name: null,
      sight_id: null,
      sight_name: null,
      absorber_id: null,
      absorber_name: null,
      // Melee weapon attachments
      matrix_id: null,
      matrix_name: null,
      // Mindforce weapon attachments
      implant_id: null,
      implant_name: null,
      enhancerType: 'Damage',
      // Armor attachments
      plate_id: null,
      plate_name: null,
      // Pet abilities
      enabledAbilities: []
    };

    // Load existing attachments if they exist
    if (item.attachments) {
      attachments = {
        ...attachments,
        ...item.attachments,
        enhancerType: item.attachments.enhancerType || 'Damage',
        enabledAbilities: item.attachments.enabledAbilities || []
      };
    }

    editingIndex = index;
    showAddModal = true;
  }
  
  function resetForm() {
    itemName = '';
    itemType = '';
    tier = null;
    isPrimary = false;
    extraPrice = null;
    notes = '';
    attachments = {
      // Ranged weapon attachments
      amplifier_id: null,
      amplifier_name: null,
      scope_id: null,
      scope_name: null,
      scope_sight_id: null,
      scope_sight_name: null,
      sight_id: null,
      sight_name: null,
      absorber_id: null,
      absorber_name: null,
      // Melee weapon attachments
      matrix_id: null,
      matrix_name: null,
      // Mindforce weapon attachments
      implant_id: null,
      implant_name: null,
      enhancerType: 'Damage',
      // Armor attachments
      plate_id: null,
      plate_name: null,
      // Pet abilities
      enabledAbilities: []
    };
  }
  
  async function saveItem() {
    // Consumables cannot be primary
    if (itemType === 'consumables') {
      isPrimary = false;
    }
    
    // Validate pets have at least one ability enabled
    if (itemType === 'pets') {
      if (!attachments.enabledAbilities || attachments.enabledAbilities.length === 0) {
        alert('Please enable at least one pet ability before saving.');
        return;
      }
    }
    
    // Check for duplicate items (same name, regardless of tier)
    const duplicateItem = equipment.find((item, idx) => {
      if (editingIndex === idx) return false; // Exclude item being edited
      return item.item_name === itemName.trim() && item.item_type === itemType;
    });
    
    if (duplicateItem) {
      alert(`This item is already in the equipment list. Each item can only be added once, even at different tiers.`);
      return;
    }
    
    // Look up the item to get its slot (for clothing)
    let itemSlot = null;
    if (itemType === 'clothings' && itemName) {
      const selectedItem = availableItems[itemType]?.find(item => item.Name === itemName.trim());
      if (selectedItem?.Properties?.Slot) {
        itemSlot = selectedItem.Properties.Slot.toLowerCase().replace(/\s+/g, '_');
      }
    }
    
    // Check for primary conflicts
    const conflictingItem = validatePrimaryConflict(itemSlot);
    if (conflictingItem) {
      const itemTypeLabel = getItemTypeLabel(conflictingItem.item_type);
      const slotInfo = conflictingItem.clothing_slot ? ` (${conflictingItem.clothing_slot})` : '';
      const message = `Another ${itemTypeLabel}${slotInfo} is already marked as primary: "${conflictingItem.item_name}". Do you want to change it to this item instead?`;
      
      if (!confirm(message)) {
        return; // User cancelled
      }
      
      // Remove primary from conflicting item
      const conflictIdx = equipment.findIndex((item, idx) => {
        if (editingIndex === idx) return false;
        if (!item.is_primary) return false;
        
        if (itemType === 'clothings') {
          return item.item_type === 'clothings' && item.clothing_slot === itemSlot;
        }
        
        if (itemType === 'armorsets') {
          return item.item_type === 'armorsets';
        }
        
        if (serviceType === 'healing' && (itemType === 'medicaltools' || itemType === 'medicalchips')) {
          return item.item_type === 'medicaltools' || item.item_type === 'medicalchips';
        }
        
        return item.item_type === itemType;
      });
      
      if (conflictIdx !== -1) {
        equipment[conflictIdx] = { ...equipment[conflictIdx], is_primary: false };
      }
    }
    
    // Look up the item to get its actual ID
    let itemId = null;
    if (itemType && itemName.trim()) {
      try {
        const items = availableItems[itemType] || [];
        const foundItem = items.find(item => item.Name === itemName.trim());
        if (foundItem) {
          // Armor sets use Id instead of ItemId since they're collections, not items
          itemId = itemType === 'armorsets' ? foundItem.Id : foundItem.ItemId;
        }
      } catch (error) {
        console.error('Error looking up item:', error);
      }
    }
    
    // Build attachments object based on item type and weapon class
    let itemAttachments = null;
    if (canHaveWeaponAttachments) {
      // Store weapon class and class-specific attachments
      if (isRangedWeapon) {
        // Ranged weapons: amplifier, absorber (common) + scope, scope_sight, sight (class-specific)
        itemAttachments = {
          weaponClass: 'Ranged',
          amplifier_id: attachments.amplifier_id,
          amplifier_name: attachments.amplifier_name,
          absorber_id: attachments.absorber_id,
          absorber_name: attachments.absorber_name,
          scope_id: attachments.scope_id,
          scope_name: attachments.scope_name,
          scope_sight_id: attachments.scope_sight_id,
          scope_sight_name: attachments.scope_sight_name,
          sight_id: attachments.sight_id,
          sight_name: attachments.sight_name,
          enhancerType: attachments.enhancerType || null
        };
      } else if (isMeleeWeapon) {
        // Melee weapons: amplifier, absorber (common) + matrix (class-specific)
        itemAttachments = {
          weaponClass: 'Melee',
          amplifier_id: attachments.amplifier_id,
          amplifier_name: attachments.amplifier_name,
          absorber_id: attachments.absorber_id,
          absorber_name: attachments.absorber_name,
          matrix_id: attachments.matrix_id,
          matrix_name: attachments.matrix_name,
          enhancerType: attachments.enhancerType || null
        };
      } else if (isMindforceWeapon) {
        // Mindforce weapons: amplifier, absorber (common) + implant (class-specific)
        itemAttachments = {
          weaponClass: 'Mindforce',
          amplifier_id: attachments.amplifier_id,
          amplifier_name: attachments.amplifier_name,
          absorber_id: attachments.absorber_id,
          absorber_name: attachments.absorber_name,
          implant_id: attachments.implant_id,
          implant_name: attachments.implant_name,
          enhancerType: attachments.enhancerType || null
        };
      } else {
        // Unknown weapon class - store enhancerType only
        itemAttachments = {
          weaponClass: weaponClass || 'Unknown',
          enhancerType: attachments.enhancerType || null
        };
      }
    } else if (canHavePlating) {
      // For armor: include plating
      itemAttachments = {
        plate_id: attachments.plate_id,
        plate_name: attachments.plate_name
      };
    } else if (itemType === 'pets') {
      // For pets: include enabled abilities
      itemAttachments = {
        enabledAbilities: attachments.enabledAbilities || []
      };
    }
    
    const item = {
      item_id: itemId,
      item_name: itemName.trim(),
      item_type: itemType,
      tier: canHaveTier && tier ? parseInt(tier) : null,
      is_primary: isPrimary,
      extra_price: extraPrice ? parseFloat(parseFloat(extraPrice).toFixed(2)) : null,
      notes: notes.trim() || null,
      clothing_slot: itemSlot,
      attachments: itemAttachments
    };
    
    if (editingIndex !== null) {
      equipment[editingIndex] = item;
    } else {
      equipment = [...equipment, item];
    }
    
    closeModal();
  }
  
  function removeItem(index) {
    equipment = equipment.filter((_, i) => i !== index);
  }
  
  function closeModal() {
    showAddModal = false;
    resetForm();
    editingIndex = null;
  }
  
  function getItemTypeLabel(type) {
    const allTypes = [...healingItemTypes, ...dpsItemTypes];
    const typeObj = allTypes.find(t => t.value === type);
    return typeObj ? typeObj.label : type;
  }
  
  function getItemInternalUrl(itemType, itemName) {
    if (!itemName) return '#';

    // Remove tier info from name if present
    const cleanName = itemName.replace(/\s*Tier\s*\d+/i, '').trim();

    // Map item types to their internal type names
    const typeMap = {
      'weapons': 'Weapon',
      'armorsets': 'Armor',
      'medicaltools': 'MedicalTool',
      'medicalchips': 'MedicalChip',
      'clothings': 'Clothing',
      'pets': 'Pet'
    };

    const type = typeMap[itemType];
    if (!type) return '#';

    return getTypeLink(cleanName, type);
  }

  // Check if equipment has any attachments configured
  function hasAttachments(item) {
    const att = item.attachments;
    if (!att) return false;

    // Check for weapon attachments
    if (att.amplifier_name || att.scope_name || att.sight_name || att.absorber_name || att.scope_sight_name) return true;
    if (att.matrix_name) return true;
    if (att.implant_name) return true;
    // Check for armor attachments
    if (att.plate_name) return true;

    return false;
  }

  // Count number of attachments on equipment
  function countAttachments(item) {
    const att = item.attachments;
    if (!att) return 0;

    let count = 0;
    if (att.amplifier_name) count++;
    if (att.scope_name) count++;
    if (att.scope_sight_name) count++;
    if (att.sight_name) count++;
    if (att.absorber_name) count++;
    if (att.matrix_name) count++;
    if (att.implant_name) count++;
    if (att.plate_name) count++;

    return count;
  }
  let itemTypes = $derived(serviceType === 'healing' ? healingItemTypes : dpsItemTypes);
  let canHaveTier = $derived(itemType && ['medicaltools', 'weapons', 'armorsets'].includes(itemType));
  let canHaveWeaponAttachments = $derived(itemType === 'weapons');
  let currentItemIsTierable = $derived(itemType && itemName && !hasItemTag(itemName, 'L'));
  let canHavePlating = $derived(itemType === 'armorsets');
  // Get the selected weapon's class for attachment type filtering
  let selectedWeaponData = $derived(itemType === 'weapons' && itemName && availableItems['weapons']
    ? availableItems['weapons'].find(w => w.Name === itemName.trim())
    : null);
  let weaponClass = $derived(selectedWeaponData?.Properties?.Class || null);
  let isRangedWeapon = $derived(weaponClass === 'Ranged');
  let isMeleeWeapon = $derived(weaponClass === 'Melee');
  let isMindforceWeapon = $derived(weaponClass === 'Mindforce');
  let requiresSlot = $derived(itemType === 'clothings');
  let currentItemOptions = $derived(itemType && availableItems[itemType] ? 
    availableItems[itemType]
      .filter(item => {
        // For healing services, only show items with reload speed effects
        if (serviceType === 'healing') {
          if (itemType === 'armorsets') {
            // Check EffectsOnSetEquip (armor sets use this property name)
            const hasReloadSpeed = 
              item.EffectsOnSetEquip?.some(e => e.Name === 'Reload Speed Increased');
            return hasReloadSpeed;
          } else if (itemType === 'clothings') {
            // Only show clothings with reload speed effects
            return item.EffectsOnEquip?.some(e => e.Name === 'Reload Speed Increased');
          } else if (itemType === 'consumables') {
            // Only show consumables with reload speed effects
            return item.EffectsOnConsume?.some(e => e.Name === 'Reload Speed Increased');
          }
        } else {
          // For DPS services, show clothings only if they have effects
          if (itemType === 'clothings') {
            return item.EffectsOnEquip && item.EffectsOnEquip.length > 0;
          }
        }
        return true;
      })
      .map(item => item.Name)
      .sort() 
    : []);
  // Load items when item type changes
  $effect(() => {
    if (itemType && showAddModal) {
      loadItemsForType(itemType);
      // Auto-check primary if no primary exists for this type/slot
      autoCheckPrimary();
      // Also load attachment types if needed
      if (itemType === 'weapons') {
        loadItemsForType('weaponamplifiers');  // Contains both regular amps and matrices
        loadItemsForType('weaponvisionattachments');  // Scopes and sights
        loadItemsForType('absorbers');
        loadItemsForType('mindforceimplants');  // For mindforce weapons
      } else if (itemType === 'armorsets') {
        loadItemsForType('armorplatings');
      }
    }
  });
  // Auto-check primary when item type changes
  $effect(() => {
    if (itemType) {
      autoCheckPrimary();
    }
  });
  // Helper to get attachment item options
  // Filter amplifiers by weapon class and type (excluding Matrix which is a special type)
  let rangedAmplifierOptions = $derived(availableItems['weaponamplifiers']?.filter(x => {
    const type = x.Properties?.Type;
    return (type === 'BLP' || type === 'Energy') && type !== 'Matrix';
  }).map(x => x.Name).sort() || []);
  let meleeAmplifierOptions = $derived(availableItems['weaponamplifiers']?.filter(x => {
    const type = x.Properties?.Type;
    return type === 'Melee' && type !== 'Matrix';
  }).map(x => x.Name).sort() || []);
  let mindforceAmplifierOptions = $derived(availableItems['weaponamplifiers']?.filter(x => {
    const type = x.Properties?.Type;
    return type === 'Mindforce' && type !== 'Matrix';
  }).map(x => x.Name).sort() || []);
  // Get the appropriate amplifier options based on weapon class
  let amplifierOptions = $derived(isRangedWeapon ? rangedAmplifierOptions
    : isMeleeWeapon ? meleeAmplifierOptions
    : isMindforceWeapon ? mindforceAmplifierOptions
    : []);
  let matrixOptions = $derived(availableItems['weaponamplifiers']?.filter(x => x.Properties?.Type === 'Matrix').map(x => x.Name).sort() || []);
  let implantOptions = $derived(availableItems['mindforceimplants']?.map(x => x.Name).sort() || []);
  let scopeOptions = $derived(availableItems['weaponvisionattachments']?.filter(x => x.Properties?.Type === 'Scope').map(x => x.Name).sort() || []);
  let sightOptions = $derived(availableItems['weaponvisionattachments']?.filter(x => x.Properties?.Type === 'Sight').map(x => x.Name).sort() || []);
  let absorberOptions = $derived(availableItems['absorbers']?.map(x => x.Name).sort() || []);
  let platingOptions = $derived(availableItems['armorplatings']?.map(x => x.Name).sort() || []);
</script>

<div class="equipment-editor">
  <div class="equipment-header">
    <h3>Equipment <span class="formula-text">({equipment.length}/50)</span></h3>
    <button type="button" class="add-btn" onclick={openAddModal}>+ Add Equipment</button>
  </div>
  
  {#if equipment.length === 0}
    <p class="empty-message">No equipment added yet.</p>
  {:else}
    {@const typeOrder = serviceType === 'dps' 
      ? ['weapons', 'clothings', 'armorsets', 'consumables', 'pets']
      : ['medicaltools', 'medicalchips', 'armorsets', 'clothings', 'consumables']}
    {@const sortedEquipment = [...equipment].sort((a, b) => {
      // Sort by type first
      const aTypeIndex = typeOrder.indexOf(a.item_type);
      const bTypeIndex = typeOrder.indexOf(b.item_type);
      const aOrder = aTypeIndex === -1 ? 999 : aTypeIndex;
      const bOrder = bTypeIndex === -1 ? 999 : bTypeIndex;
      if (aOrder !== bOrder) return aOrder - bOrder;
      
      // Then by primary status
      const aPrimary = a.is_primary !== false;
      const bPrimary = b.is_primary !== false;
      if (aPrimary && !bPrimary) return -1;
      if (!aPrimary && bPrimary) return 1;
      
      // Finally alphabetically by name
      return (a.item_name || '').localeCompare(b.item_name || '');
    })}
    <div class="equipment-list">
      {#each sortedEquipment as item}
        <div class="equipment-item" class:is-primary={item.is_primary}>
          <div class="item-info">
            <div class="item-name">
              <div class="item-name-text">
                {#if item.item_name}
                  <a href={getItemInternalUrl(item.item_type, item.item_name)} class="item-link">
                    {item.item_name}
                  </a>
                {:else}
                  <span class="unnamed-item">Unnamed Item</span>
                {/if}
              </div>
              <div class="item-badges">
                {#if item.tier !== null}
                  <span class="tier-badge">T{item.tier}</span>
                {/if}
                {#if item.item_type === 'clothings'}
                  {@const slot = getClothingSlot(item.item_name)}
                  {#if slot}
                    <span class="slot-badge">{slot.replace(/_/g, ' ')}</span>
                  {/if}
                {/if}
                {#if item.item_type === 'weapons' && item.tier > 0}
                  {@const validEnhancerType = ['Damage', 'Range', 'Economy', 'Accuracy'].includes(item.attachments?.enhancerType) ? item.attachments.enhancerType : 'Damage'}
                  <span class="enhancer-badge">{validEnhancerType} Enhancers</span>
                {/if}
                {#if item.is_primary}
                  <span class="primary-badge">Primary</span>
                {/if}
                {#if hasAttachments(item)}
                  <span class="attachments-indicator" title="{countAttachments(item)} attachment{countAttachments(item) > 1 ? 's' : ''} configured">
                    {countAttachments(item)} attachment{countAttachments(item) > 1 ? 's' : ''}
                  </span>
                {/if}
              </div>
            </div>
            <div class="item-details">
              {getItemTypeLabel(item.item_type)}
              {#if item.extra_price}
                • +{parseFloat(item.extra_price).toFixed(2)} PED/h
              {/if}
              {#if item.notes}
                • {item.notes}
              {/if}
            </div>
          </div>
          <div class="item-actions">
            <button type="button" class="edit-btn" onclick={() => openEditModal(equipment.indexOf(item))}>Edit</button>
            <button type="button" class="remove-btn" onclick={() => removeItem(equipment.indexOf(item))}>Remove</button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if showAddModal}
  <div class="modal-backdrop" onclick={closeModal}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <h3>{editingIndex !== null ? 'Edit' : 'Add'} Equipment</h3>
        <button type="button" class="modal-close" onclick={closeModal}>&times;</button>
      </div>
      
      <div class="modal-body">
        <div class="form-group">
          <label for="itemType">Item Type *</label>
          <select id="itemType" bind:value={itemType} required>
            <option value="">-- Select Type --</option>
            {#each itemTypes as type}
              <option value={type.value}>{type.label}</option>
            {/each}
          </select>
        </div>
        
        <div class="form-group">
          <label for="itemName">Item Name *</label>
          {#if itemType && currentItemOptions.length > 0}
            <div class="select-editable">
              <select onchange={e => itemName = e.target.value}>
                <option value="" selected></option>
                {#each currentItemOptions as option}
                  <option value={option}>{option}</option>
                {/each}
              </select>
              <input type="text" id="itemName" bind:value={itemName} placeholder="Type or select an item" required />
            </div>
            {#if loadingItems}
              <small>Loading items...</small>
            {/if}
          {:else}
            <input type="text" id="itemName" bind:value={itemName} placeholder="Select item type first" required disabled={!itemType} />
          {/if}
        </div>
        
        {#if canHaveTier && serviceType !== 'healing'}
          <div class="form-group">
            <label for="tier">Tier</label>
            <input type="number" id="tier" bind:value={tier} min="0" max="10" placeholder="0-10" />
          </div>
        {/if}
        
        <!-- Weapon Attachments (only for DPS services and when weapon is selected) -->
        {#if canHaveWeaponAttachments && serviceType !== 'healing' && itemName && itemName.trim()}
          <div class="attachments-section">
            <h4>Attachments {#if weaponClass}<span class="weapon-class-badge">{weaponClass}</span>{/if}</h4>

            {#if weaponClass && (isRangedWeapon || isMeleeWeapon || isMindforceWeapon)}
              <!-- Common Attachments for ALL weapon types -->
              <div class="form-row">
                <div class="form-group">
                  <label for="amplifier">Amplifier</label>
                  {#if amplifierOptions.length > 0}
                    <div class="select-editable">
                      <select onchange={e => { attachments.amplifier_name = e.target.value; updateAmplifierId(); }}>
                        <option value="" selected></option>
                        {#each amplifierOptions as option}
                          <option value={option}>{option}</option>
                        {/each}
                      </select>
                      <input type="text" id="amplifier" bind:value={attachments.amplifier_name} onblur={updateAmplifierId} placeholder="e.g., Herman ARK-0 (L)" />
                    </div>
                  {:else}
                    <input type="text" id="amplifier" bind:value={attachments.amplifier_name} placeholder="e.g., Herman ARK-0 (L)" />
                  {/if}
                  <small>{weaponClass} weapon amplifier</small>
                </div>

                <div class="form-group">
                  <label for="absorber">Absorber</label>
                  {#if absorberOptions.length > 0}
                    <div class="select-editable">
                      <select onchange={e => { attachments.absorber_name = e.target.value; updateAbsorberId(); }}>
                        <option value="" selected></option>
                        {#each absorberOptions as option}
                          <option value={option}>{option}</option>
                        {/each}
                      </select>
                      <input type="text" id="absorber" bind:value={attachments.absorber_name} onblur={updateAbsorberId} placeholder="e.g., 5B Genesis Star" />
                    </div>
                  {:else}
                    <input type="text" id="absorber" bind:value={attachments.absorber_name} placeholder="e.g., 5B Genesis Star" />
                  {/if}
                </div>
              </div>

              <!-- Class-specific Attachments -->
              {#if isRangedWeapon}
                <!-- Ranged: Vision attachments -->
                <h4 class="subsection-title">Vision Attachments</h4>
                <div class="form-row">
                  <div class="form-group">
                    <label for="scope">Scope</label>
                    {#if scopeOptions.length > 0}
                      <div class="select-editable">
                        <select onchange={e => { attachments.scope_name = e.target.value; updateScopeId(); }}>
                          <option value="" selected></option>
                          {#each scopeOptions as option}
                            <option value={option}>{option}</option>
                          {/each}
                        </select>
                        <input type="text" id="scope" bind:value={attachments.scope_name} onblur={updateScopeId} placeholder="e.g., Herman LAD mk.2" />
                      </div>
                    {:else}
                      <input type="text" id="scope" bind:value={attachments.scope_name} placeholder="e.g., Herman LAD mk.2" />
                    {/if}
                  </div>

                  <div class="form-group nested-attachment">
                    <label for="scope-sight"><span class="nested-arrow">↳</span> Scope Sight</label>
                    {#if attachments.scope_name}
                      {#if sightOptions.length > 0}
                        <div class="select-editable">
                          <select onchange={e => { attachments.scope_sight_name = e.target.value; updateScopeSightId(); }}>
                            <option value="" selected></option>
                            {#each sightOptions as option}
                              <option value={option}>{option}</option>
                            {/each}
                          </select>
                          <input type="text" id="scope-sight" bind:value={attachments.scope_sight_name} onblur={updateScopeSightId} placeholder="Sight for scope" />
                        </div>
                      {:else}
                        <input type="text" id="scope-sight" bind:value={attachments.scope_sight_name} placeholder="Sight for scope" />
                      {/if}
                    {:else}
                      <input type="text" disabled placeholder="Add a scope first" />
                    {/if}
                    <small>Sight attached to the scope</small>
                  </div>
                </div>

                <div class="form-group" style="max-width: calc(50% - 0.5rem);">
                  <label for="sight">Sight</label>
                  {#if sightOptions.length > 0}
                    <div class="select-editable">
                      <select onchange={e => { attachments.sight_name = e.target.value; updateSightId(); }}>
                        <option value="" selected></option>
                        {#each sightOptions as option}
                          <option value={option}>{option}</option>
                        {/each}
                      </select>
                      <input type="text" id="sight" bind:value={attachments.sight_name} onblur={updateSightId} placeholder="e.g., Omegaton A103" />
                    </div>
                  {:else}
                    <input type="text" id="sight" bind:value={attachments.sight_name} placeholder="e.g., Omegaton A103" />
                  {/if}
                  <small>Direct weapon sight</small>
                </div>

              {:else if isMeleeWeapon}
                <!-- Melee: Matrix -->
                <h4 class="subsection-title">Melee Attachments</h4>
                <div class="form-group" style="max-width: calc(50% - 0.5rem);">
                  <label for="matrix">Matrix</label>
                  {#if matrixOptions.length > 0}
                    <div class="select-editable">
                      <select onchange={e => { attachments.matrix_name = e.target.value; updateMatrixId(); }}>
                        <option value="" selected></option>
                        {#each matrixOptions as option}
                          <option value={option}>{option}</option>
                        {/each}
                      </select>
                      <input type="text" id="matrix" bind:value={attachments.matrix_name} onblur={updateMatrixId} placeholder="e.g., Genesis Star Matrix" />
                    </div>
                  {:else}
                    <input type="text" id="matrix" bind:value={attachments.matrix_name} placeholder="e.g., Genesis Star Matrix" />
                  {/if}
                </div>

              {:else if isMindforceWeapon}
                <!-- Mindforce: Implant -->
                <h4 class="subsection-title">Mindforce Attachments</h4>
                <div class="form-group" style="max-width: calc(50% - 0.5rem);">
                  <label for="implant">Implant</label>
                  {#if implantOptions.length > 0}
                    <div class="select-editable">
                      <select onchange={e => { attachments.implant_name = e.target.value; updateImplantId(); }}>
                        <option value="" selected></option>
                        {#each implantOptions as option}
                          <option value={option}>{option}</option>
                        {/each}
                      </select>
                      <input type="text" id="implant" bind:value={attachments.implant_name} onblur={updateImplantId} placeholder="e.g., Genesis Star Implant" />
                    </div>
                  {:else}
                    <input type="text" id="implant" bind:value={attachments.implant_name} placeholder="e.g., Genesis Star Implant" />
                  {/if}
                </div>
              {/if}

            {:else}
              <p class="no-attachments-msg">This weapon type ({weaponClass || 'Unknown'}) doesn't support standard attachments.</p>
            {/if}

            <h4 class="enhancers-title">Enhancers</h4>
            <div class="form-group">
              <label for="enhancer-type">The kind of enhancers to be used</label>
              <select id="enhancer-type" bind:value={attachments.enhancerType}>
                <option value="Damage">Damage</option>
                <option value="Range">Range</option>
                <option value="Economy">Economy</option>
                <option value="Accuracy">Accuracy</option>
              </select>
              <small>All enhancers of the selected type will be used</small>
            </div>
          </div>
        {/if}
        
        <!-- Armor Plating (only for DPS services) -->
        {#if canHavePlating && serviceType !== 'healing'}
          <div class="attachments-section">
            <h4>Armor Plating</h4>
            <div class="form-group">
              <label for="plating">Plating</label>
              {#if platingOptions.length > 0}
                <div class="select-editable">
                  <select onchange={e => { attachments.plate_name = e.target.value; updatePlateId(); }}>
                    <option value="" selected></option>
                    {#each platingOptions as option}
                      <option value={option}>{option}</option>
                    {/each}
                  </select>
                  <input type="text" id="plating" bind:value={attachments.plate_name} onblur={updatePlateId} placeholder="e.g., 5A Plate" />
                </div>
              {:else}
                <input type="text" id="plating" bind:value={attachments.plate_name} placeholder="e.g., 5A Plate" />
              {/if}
              <small>Applied to all armor pieces</small>
            </div>
          </div>
        {/if}
        
        {#if itemType === 'pets' && itemName}
          {@const petData = availableItems.pets?.find(p => p.Name === itemName.trim())}
          {@const allEffects = petData?.Effects || []}
          {#if allEffects.length > 0}
            <div class="attachments-section">
              <h4>Pet Abilities</h4>
              <small>Select which abilities are unlocked for customers to use</small>
              <div class="pet-abilities-list">
                {#each allEffects as effect, index (`${effect.Id}-${index}`)}
                  {@const uniqueKey = `${effect.Id}-${effect.Properties?.Strength || 0}-${index}`}
                  {@const isEnabled = attachments.enabledAbilities.includes(uniqueKey)}
                  <label class="checkbox-label">
                    <input 
                      type="checkbox" 
                      checked={isEnabled}
                      onchange={(e) => {
                        if (e.target.checked) {
                          attachments.enabledAbilities = [...attachments.enabledAbilities, uniqueKey];
                        } else {
                          attachments.enabledAbilities = attachments.enabledAbilities.filter(id => id !== uniqueKey);
                        }
                        attachments = attachments; // Trigger reactivity
                      }}
                    />
                    <span class="ability-name">{effect.Name}</span>
                    {#if effect.Properties?.Strength}
                      <span class="ability-value">+{effect.Properties.Strength}{effect.Properties?.Unit || ''}</span>
                    {/if}
                  </label>
                {/each}
              </div>
            </div>
          {:else if petData}
            <div class="attachments-section">
              <h4>Pet Abilities</h4>
              <small>This pet has no abilities available</small>
            </div>
          {/if}
        {/if}
        
        {#if itemType !== 'consumables'}
          <div class="form-group checkbox-group">
            <label>
              <input type="checkbox" bind:checked={isPrimary} />
              Primary equipment
            </label>
            <small>Uncheck for utility/support items</small>
          </div>
        {/if}
        
        <div class="form-group">
          <label for="extraPrice">Extra Price (PED/hour)</label>
          <input type="number" id="extraPrice" bind:value={extraPrice} step="0.01" min="0" placeholder="Additional hourly fee for using this item" />
          <small>Leave empty if included in base price</small>
        </div>
        
        <div class="form-group">
          <label for="notes">Notes</label>
          <textarea id="notes" bind:value={notes} rows="2" placeholder="e.g., Available tier ranges, special conditions"></textarea>
        </div>
      </div>
      
      <div class="modal-footer">
        <button type="button" class="cancel-btn" onclick={closeModal}>Cancel</button>
        <button type="button" class="save-btn" onclick={saveItem} disabled={!itemName.trim() || !itemType}>
          {editingIndex !== null ? 'Update' : 'Add'} Equipment
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .equipment-editor {
    margin-top: 1rem;
  }
  
  .equipment-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }
  
  .equipment-header h3 {
    margin: 0;
    font-size: 1rem;
  }
  
  .add-btn {
    background: #4a9eff;
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
  }
  
  .add-btn:hover {
    background: #3a8eef;
  }
  
  .empty-message {
    color: #888;
    font-style: italic;
    margin: 1rem 0;
  }
  
  .equipment-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .equipment-item {
    background: var(--secondary-color);
    border: 1px solid #666;
    border-radius: 4px;
    padding: 0.75rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }
  
  .equipment-item.is-primary {
    border-color: #4a9eff;
    background: linear-gradient(to right, rgba(74, 158, 255, 0.1), var(--secondary-color));
  }
  
  .item-info {
    flex: 1;
    display: grid;
    grid-template-rows: auto auto;
    gap: 0.25rem;
  }

  .item-name {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .item-name-text {
    font-weight: 500;
    flex-shrink: 0;
  }

  .item-badges {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    flex: 1;
    min-width: 0;
  }

  .item-link {
    color: #4a9eff;
    text-decoration: none;
  }

  .item-link:hover {
    text-decoration: underline;
  }

  .tier-badge {
    background: #4a9eff;
    color: white;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.75rem;
  }

  .slot-badge {
    background: #2a2a2a;
    color: #aaa;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.75rem;
    text-transform: capitalize;
  }

  .primary-badge {
    background: var(--accent-color, #4a9eff);
    color: white;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.75rem;
  }

  .attachments-indicator {
    background: var(--bg-secondary, rgba(255, 255, 255, 0.05));
    color: var(--text-muted, #888);
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.75rem;
    border: 1px solid var(--border-color, #444);
  }

  .item-details {
    font-size: 0.9rem;
    color: #888;
    grid-row: 2;
  }
  
  .item-actions {
    display: flex;
    gap: 0.5rem;
  }
  
  .edit-btn, .remove-btn {
    padding: 0.25rem 0.75rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
  }
  
  .enhancer-badge {
    background: #6c3;
    color: white;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    font-size: 0.75rem;
  }
  
  .edit-btn {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid #666;
  }
  
  .edit-btn:hover {
    background: var(--hover-color);
  }
  
  .remove-btn {
    background: #dc3545;
    color: white;
  }
  
  .remove-btn:hover {
    background: #c82333;
  }
  
  /* Modal styles */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
  }
  
  .modal {
    background: var(--secondary-color);
    border: 1px solid #666;
    border-radius: 8px;
    width: 100%;
    max-width: 650px;
    max-height: 90vh;
    overflow-y: auto;
  }
  
  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid #444;
  }
  
  .modal-header h3 {
    margin: 0;
    font-size: 1.1rem;
  }
  
  .modal-close {
    background: none;
    border: none;
    color: var(--text-color);
    font-size: 1.5rem;
    cursor: pointer;
    line-height: 1;
    padding: 0;
  }
  
  .modal-close:hover {
    color: #4a9eff;
  }
  
  .modal-body {
    padding: 1rem;
  }
  
  /* Ensure all selects in modal follow theme */
  .modal-body select {
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    border: 1px solid var(--border-color, #ccc);
  }

  .modal-body select option {
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .attachments-section {
    background: var(--bg-secondary, rgba(255, 255, 255, 0.03));
    border: 1px solid var(--border-color, #444);
    border-radius: 4px;
    padding: 1rem;
    margin-bottom: 1rem;
  }

  .attachments-section h4 {
    margin: 0 0 1rem 0;
    font-size: 0.95rem;
    color: var(--accent-color, #4a9eff);
  }

  .subsection-title {
    margin: 1rem 0 0.75rem 0;
    font-size: 0.9rem;
    color: var(--text-muted, #888);
    font-weight: 500;
  }

  .enhancers-title {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color, #444);
  }

  .weapon-class-badge {
    font-size: 0.75rem;
    font-weight: normal;
    background: var(--accent-color, #4a9eff);
    color: white;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    margin-left: 0.5rem;
    vertical-align: middle;
  }

  .nested-attachment label {
    color: var(--text-muted, #888);
  }

  .nested-arrow {
    color: var(--accent-color, #4a9eff);
    margin-right: 0.25rem;
  }

  .no-attachments-msg {
    color: var(--text-muted, #888);
    font-style: italic;
    margin: 0.5rem 0;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: 500;
  }

  .form-group input,
  .form-group select,
  .form-group textarea {
    width: 100%;
    padding: 0.5rem;
    background: var(--bg-color, var(--secondary-color));
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    color: var(--text-color);
    font-family: inherit;
    box-sizing: border-box;
    font-size: 1rem;
  }

  .form-group select {
    cursor: pointer;
  }

  .form-group select option {
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    border: none;
  }

  .select-editable {
    position: relative;
    border: 1px solid var(--border-color, #ccc);
    border-radius: 4px;
    background: var(--bg-color, var(--secondary-color));
  }
  
  .select-editable select {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    border: none;
    outline: none;
    opacity: 0;
    cursor: pointer;
    z-index: 2;
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
  }

  .select-editable select option {
    background: var(--bg-color, var(--secondary-color));
    color: var(--text-color);
    border: none;
    padding: 0.5rem;
  }
  
  .select-editable select:focus {
    outline: none;
    border: none;
  }
  
  .select-editable input {
    position: relative;
    width: 100%;
    padding: 0.5rem;
    padding-right: 2rem;
    border: none;
    background: transparent;
    z-index: 1;
  }
  
  .select-editable::after {
    content: '▼';
    position: absolute;
    top: 50%;
    right: 0.5rem;
    transform: translateY(-50%);
    pointer-events: none;
    color: #888;
    font-size: 0.7rem;
    z-index: 0;
  }
  
  .select-editable select:focus,
  .select-editable input:focus {
    outline: none;
  }
  
  .form-group small {
    display: block;
    margin-top: 0.25rem;
    color: #888;
    font-size: 0.85rem;
  }
  
  .checkbox-group label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: normal;
  }
  
  .checkbox-group input[type="checkbox"] {
    width: auto;
  }
  
  .pet-abilities-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  
  .pet-abilities-list .checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem;
    background: var(--main-color);
    border-radius: 4px;
    cursor: pointer;
  }
  
  .pet-abilities-list .checkbox-label:hover {
    background: var(--hover-color);
  }
  
  .pet-abilities-list input[type="checkbox"] {
    width: auto;
    margin: 0;
  }
  
  .ability-name {
    flex: 1;
  }
  
  .ability-value {
    color: #4a9eff;
    font-weight: 500;
  }
  
  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    padding: 1rem;
    border-top: 1px solid #444;
  }
  
  .cancel-btn, .save-btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  
  .cancel-btn {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid #666;
  }
  
  .cancel-btn:hover {
    background: var(--hover-color);
  }
  
  .save-btn {
    background: #4a9eff;
    color: white;
  }
  
  .save-btn:hover:not(:disabled) {
    background: #3a8eef;
  }
  
  .save-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  
  .unnamed-item {
    color: #888;
    font-style: italic;
  }
</style>
