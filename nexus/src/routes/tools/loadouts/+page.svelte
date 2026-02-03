<script>
  // @ts-nocheck
  import '$lib/style.css';
  import './loadouts.css';

  import { onMount, onDestroy } from 'svelte';
  import { slide } from 'svelte/transition';
  import { browser } from '$app/environment';

  import FancyTable from '$lib/components/FancyTable.svelte';
  import { loading, darkMode } from '../../../stores.js';
  import Table from '$lib/components/Table.svelte';
  import { clampDecimals, hasItemTag, encodeURIComponentSafe } from '$lib/util.js';
  import * as LoadoutCalc from '$lib/utils/loadoutCalculations.js';
  import { loadLoadoutEntities } from '$lib/utils/entityLoader';
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import EffectsEditor from '$lib/components/wiki/EffectsEditor.svelte';

  export let data;
  $: user = data?.session?.user;
  $: isLoggedIn = !!user;

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const LOCAL_STORAGE_KEY = 'loadouts';
  const AUTOSAVE_DELAY_MS = 10000;

  const isLimitedName = (name) => !!name && hasItemTag(name, 'L');

  const BUFF_DEFS = {
    damage: {
      label: 'Damage',
      unit: '%',
      positive: ['Increased Damage'],
      negative: ['Decreased Damage']
    },
    critChance: {
      label: 'Crit Chance',
      unit: '%',
      positive: ['Added Crit Chance', 'Added Critical Chance'],
      negative: ['Decreased Crit Chance', 'Decreased Critical Chance']
    },
    critDamage: {
      label: 'Crit Damage',
      unit: '%',
      positive: ['Increased Crit Damage', 'Increased Critical Damage', 'Added Critical Damage', 'Added Crit Damage'],
      negative: ['Decreased Crit Damage', 'Decreased Critical Damage']
    },
    reload: {
      label: 'Reload Speed',
      unit: '%',
      positive: ['Increased Reload Speed', 'Increased Reload'],
      negative: ['Decreased Reload Speed', 'Decreased Reload']
    }
  };

  const BUFF_ORDER = ['damage', 'critChance', 'critDamage', 'reload'];

  const CAP_EFFECT_NAMES = {
    damage: 'Increased Damage',
    critChance: 'Added Critical Chance',
    critDamage: 'Added Critical Damage',
    reload: 'Increased Reload Speed'
  };

  const OFFENSIVE_EFFECTS = [
    { key: 'reload', type: 'mult', base: 'Reload Speed', name: 'Increased Reload Speed' },
    { key: 'critChance', type: 'add', base: 'Critical Chance', name: 'Added Critical Chance' },
    { key: 'critDamage', type: 'add', base: 'Critical Damage', name: 'Added Critical Damage' },
    { key: 'damage', type: 'mult', base: 'Damage', name: 'Increased Damage' }
  ];

  const DEFENSIVE_EFFECT_NAMES = new Set([
    'Added Health',
    'Added Lifesteal',
    'Decreased Damage Taken',
    'Increased Evade Chance',
    'Increased Dodge Chance',
    'Increased Jamming Chance',
    'Decreased Critical Damage Taken'
  ]);

  const PREFIX_RULES = [
    { positive: 'Increased', negative: 'Decreased', type: 'mult' },
    { positive: 'Added', negative: 'Reduced', type: 'add' }
  ];

  function getApiBase() {
    return browser
      ? (import.meta.env.VITE_API_URL || 'https://api.entropianexus.com')
      : (process.env.INTERNAL_API_URL || 'http://api:3000');
  }

  let settings = {
    onlyShowReasonableAmplifiers: true,
    overampCap: 10,
  }

  let weapons = [];
  let amplifiers = [];
  let scopes = [];
  let sights = [];
  let absorbers = [];
  let matrices = [];
  let implants = [];
  let armorsets = [];
  let armors = [];
  let armorplatings = [];
  let enhancers = [];
  let clothing = [];
  let pets = [];
  let stimulants = [];
  let effectsCatalog = [];
  let effectCaps = {};

  let entitiesLoading = true;
  let entitiesVersion = 0;

  let localLoadouts = [];
  let onlineLoadouts = [];
  let loadouts = [];
  let loadout = null;
  let activeSource = 'local';
  let activeOnlineId = null;
  let loadoutSearch = '';
  let onlineLoading = false;
  let onlineError = null;
  let isDirty = false;
  let autosaveDueAt = null;
  let autosaveTimeout = null;
  let autosaveTicker = null;
  let autosaveNow = Date.now();
  let isSaving = false;
  let saveError = null;
  let showShareDialog = false;
  let sharePublic = false;
  let shareLink = '';
  let showImportDialog = false;
  let showImportSourceDialog = false;
  let importInProgress = false;
  let importError = null;
  let importSuccess = false;
  let hasPromptedImport = false;
  let showFileImport = false;
  let fileInput;

  let activePicker = null;
  let showPickerDialog = false;
  let showPickerPreview = false;
  let pickerPreviewRow = null;
  let pickerPreviewItem = null;
  let suppressDirty = false;
  let clothingReplaceNotice = '';
  let loadoutVersion = 0;
  let activeBuffSummary = null;
  let allEffects = [];
  let offensiveEffects = [];
  let defensiveEffects = [];
  let utilityEffects = [];
  let offensiveTotals = { damage: 0, reload: 0, critChance: 0, critDamage: 0 };
  let expandedEffectKeys = new Set();

  let compareMode = false;

  let windowWidth = 0;
  let touchStartX = 0;
  let touchStartY = 0;
  let swipeOffset = 0;
  let swipeActive = false;
  let mobilePanelsEl;

  const mobilePanelItems = [
    { key: 'info', label: 'Stats', icon: 'icon-stats' },
    { key: 'settings', label: 'Settings', icon: 'icon-settings' },
    { key: 'weapons', label: 'Weapons', icon: 'icon-weapon' },
    { key: 'armor', label: 'Armor', icon: 'icon-armor' },
    { key: 'accessories', label: 'Accessories & Buffs', icon: 'icon-accessories' },
  ];
  const mobilePanels = mobilePanelItems.map((panel) => panel.key);
  let activeMobilePanel = 'weapons';

  function toggleEffectExpanded(key) {
    if (!key) return;
    if (expandedEffectKeys.has(key)) expandedEffectKeys.delete(key);
    else expandedEffectKeys.add(key);
    // Reassign so Svelte updates.
    expandedEffectKeys = new Set(expandedEffectKeys);
  }

  $: isMobileLayout = windowWidth < 900;
  $: activeMobilePanelIndex = Math.max(0, mobilePanels.indexOf(activeMobilePanel));
  $: mobilePanelTranslate = isMobileLayout
    ? `translateX(calc(-${activeMobilePanelIndex * 100}% + ${swipeOffset}px))`
    : 'translateX(0)';

  $: breadcrumbs = [
    { label: 'Tools', href: '/tools' },
    { label: 'Loadouts', href: '/tools/loadouts' },
    ...(loadout?.Name ? [{ label: loadout.Name }] : [])
  ];

  function alphabeticalSort(a, b) {
    if (a?.Name === null) return 1;
    if (b?.Name === null) return -1;

    return a.Name.localeCompare(b.Name, undefined, { numeric: true });
  }

  function processEntityData(entities) {
    const rawWeapons = entities.weapons || [];
    const rawAmplifiers = entities.weaponAmplifiers || [];
    const rawVisionAttachments = entities.weaponVisionAttachments || [];

    weapons = rawWeapons.filter(x => x.Properties?.Class !== 'Attached' && x.Properties?.Class !== 'Stationary').sort(alphabeticalSort);
    amplifiers = rawAmplifiers.filter(x => x.Properties?.Type !== 'Matrix').sort(alphabeticalSort);
    scopes = rawVisionAttachments.filter(x => x.Properties?.Type === 'Scope').sort(alphabeticalSort);
    sights = rawVisionAttachments.filter(x => x.Properties?.Type === 'Sight').sort(alphabeticalSort);
    absorbers = (entities.absorbers || []).sort(alphabeticalSort);
    matrices = rawAmplifiers.filter(x => x.Properties?.Type === 'Matrix').sort(alphabeticalSort);
    implants = (entities.mindforceImplants || []).sort(alphabeticalSort);
    armorsets = (entities.armorSets || []).sort(alphabeticalSort);
    armors = (entities.armors || []).sort(alphabeticalSort);
    armorplatings = (entities.armorPlatings || []).sort(alphabeticalSort);
    enhancers = (entities.enhancers || []).sort(alphabeticalSort);
    clothing = (entities.clothings || []).sort(alphabeticalSort);
    pets = (entities.pets || []).sort(alphabeticalSort);
    stimulants = (entities.consumables || []).sort(alphabeticalSort);
    entitiesVersion += 1;
    if (loadout) {
      loadout = loadout;
    }
  }

  function parseCapValue(description, label) {
    if (!description) return null;
    const regex = new RegExp(`${label}\\s*cap[^0-9]*([0-9]+(?:\\.[0-9]+)?)`, 'i');
    const match = description.match(regex);
    return match ? Number(match[1]) : null;
  }

  function parseCapsFromDescription(description) {
    if (!description) return null;
    const equipment = parseCapValue(description, 'equipment');
    const consumable = parseCapValue(description, 'consumable');
    const total = parseCapValue(description, 'total');
    if (equipment == null && consumable == null && total == null) return null;
    return { equipment, consumable, total };
  }

  function buildEffectCaps(list) {
    const caps = {};
    (list || []).forEach(effect => {
      const limits = effect?.Properties?.Limits || effect?.Limits;
      if (limits && (limits.Item != null || limits.Action != null || limits.Total != null)) {
        const normalize = (value) => {
          if (value == null) return null;
          const num = Number(value);
          return Number.isFinite(num) && num > 0 ? num : null;
        };
        caps[effect.Name] = {
          item: normalize(limits.Item),
          action: normalize(limits.Action),
          total: normalize(limits.Total)
        };
        return;
      }

      // Back-compat: parse older description-based caps if present.
      const description = effect?.Properties?.Description || effect?.Description || '';
      const parsed = parseCapsFromDescription(description);
      if (parsed) {
        const normalize = (value) => {
          if (value == null) return null;
          const num = Number(value);
          return Number.isFinite(num) && num > 0 ? num : null;
        };
        caps[effect.Name] = {
          item: normalize(parsed.equipment),
          action: normalize(parsed.consumable),
          total: normalize(parsed.total)
        };
      }
    });
    return caps;
  }

  function getCapsForBuffKey(key) {
    const primary = CAP_EFFECT_NAMES[key];
    const candidates = [
      primary,
      ...(BUFF_DEFS[key]?.positive || [])
    ].filter(Boolean);
    for (const name of candidates) {
      if (effectCaps?.[name]) return effectCaps[name];
    }
    return null;
  }

  const isRingSlot = (slot) => /ring|finger/i.test(slot || '');
  const getRingSide = (slot) => {
    const normalized = (slot || '').toLowerCase();
    if (normalized.includes('left')) return 'Left';
    if (normalized.includes('right')) return 'Right';
    return null;
  };

  $: ringItems = (clothing || []).filter(item => isRingSlot(item?.Properties?.Slot));

  $: selectedClothing = (loadout?.Gear?.Clothing || []).filter(item => !isRingSlot(item?.Slot));
  $: selectedConsumables = loadout?.Gear?.Consumables || [];
  $: leftRing = loadout?.Gear?.Clothing ? getClothingSlot('Ring', 'Left') : null;
  $: rightRing = loadout?.Gear?.Clothing ? getClothingSlot('Ring', 'Right') : null;
  $: activePet = loadout?.Gear?.Pet?.Name
    ? pets.find(pet => pet.Name === loadout.Gear.Pet.Name)
    : null;
  $: activePetEffects = activePet?.Effects || [];
  $: {
    // Ensure this recomputes when caps/catalog/entities/loadout change.
    loadoutVersion;
    effectCaps;
    effectsCatalog;
    entitiesVersion;
    allEffects = loadout ? getAllEffectsSummary(loadout) : [];
  }
  $: offensiveEffects = OFFENSIVE_EFFECTS
    .map(def => allEffects.find(effect => effect?.prefix?.type === def.type && effect?.prefix?.base === def.base) || null)
    .filter(Boolean)
    .filter(effect => Math.abs(effect.signedTotal) > 0.0001);
  $: defensiveEffects = allEffects
    .filter(effect => DEFENSIVE_EFFECT_NAMES.has(effect.name))
    .filter(effect => Math.abs(effect.signedTotal) > 0.0001);
  $: utilityEffects = allEffects
    .filter(effect => !effect?.prefix || !OFFENSIVE_EFFECTS.some(def => def.type === effect.prefix.type && def.base === effect.prefix.base))
    .filter(effect => !DEFENSIVE_EFFECT_NAMES.has(effect.name))
    .filter(effect => Math.abs(effect.signedTotal) > 0.0001);

  $: offensiveTotals = {
    damage: (allEffects.find(effect => effect?.prefix?.type === 'mult' && effect?.prefix?.base === 'Damage')?.signedTotal) ?? 0,
    reload: (allEffects.find(effect => effect?.prefix?.type === 'mult' && effect?.prefix?.base === 'Reload Speed')?.signedTotal) ?? 0,
    critChance: (allEffects.find(effect => effect?.prefix?.type === 'add' && effect?.prefix?.base === 'Critical Chance')?.signedTotal) ?? 0,
    critDamage: (allEffects.find(effect => effect?.prefix?.type === 'add' && effect?.prefix?.base === 'Critical Damage')?.signedTotal) ?? 0
  };

  function createEmptyLoadout() {
    const newArmorObject = () => ({
      Name: null,
      Plate: null
    });

    return {
      Id: crypto?.randomUUID ? crypto.randomUUID() : Math.random().toString(16).slice(2),
      Name: 'New Loadout',
      Properties: {
        BonusDamage: 0,
        BonusCritChance: 0,
        BonusCritDamage: 0,
        BonusReload: 0
      },
      Gear: {
        Weapon: {
          Name: null,
          Amplifier: null,
          Scope: null,
          Sight: null,
          Absorber: null,
          Implant: null,
          Matrix: null,
          Enhancers: {
            Damage: 0,
            Accuracy: 0,
            Range: 0,
            Economy: 0,
            SkillMod: 0,
          }
        },
        Armor: {
          SetName: null,
          PlateName: null,
          Head: newArmorObject(),
          Torso: newArmorObject(),
          Arms: newArmorObject(),
          Hands: newArmorObject(),
          Legs: newArmorObject(),
          Shins: newArmorObject(),
          Feet: newArmorObject(),
          Enhancers: {
            Defense: 0,
            Durability: 0,
          },
          ManageIndividual: false,
        },
        Clothing: [],
        Consumables: [],
        Pet: {
          Name: null,
          Effect: null,
        }
      },
      Skill: {
        Hit: 200,
        Dmg: 200,
      },
      Markup: {
        Weapon: 100,
        Ammo: 100,
        Amplifier: 100,
        Absorber: 100,
        Scope: 100,
        Sight: 100,
        ScopeSight: 100,
        Matrix: 100,
        Implant: 100,
        ArmorSet: 100,
        PlateSet: 100,
        Armors: {
          Head: 100,
          Torso: 100,
          Arms: 100,
          Hands: 100,
          Legs: 100,
          Shins: 100,
          Feet: 100,
        },
        Plates: {
          Head: 100,
          Torso: 100,
          Arms: 100,
          Hands: 100,
          Legs: 100,
          Shins: 100,
          Feet: 100,
        },
      }
    };
  }

  function ensureLoadoutIds(items) {
    return (items || []).map(item => {
      if (!item || typeof item !== 'object') return createEmptyLoadout();
      if (!item.Id) {
        item.Id = crypto?.randomUUID ? crypto.randomUUID() : Math.random().toString(16).slice(2);
      }
      const normalizedConsumables = (item.Gear?.Consumables || []).map(entry => (
        typeof entry === 'string' ? { Name: entry } : entry
      ));
      item.Gear = {
        ...item.Gear,
        Clothing: item.Gear?.Clothing ?? [],
        Pet: item.Gear?.Pet ?? { Name: null, Effect: null },
        Consumables: normalizedConsumables
      };
      return item;
    });
  }

  function readLocalLoadouts() {
    if (typeof localStorage === 'undefined') return [];
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return ensureLoadoutIds(Array.isArray(parsed) ? parsed : []);
    } catch (err) {
      console.error('Failed to read local loadouts:', err);
      return [];
    }
  }

  function writeLocalLoadouts(next) {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(next || []));
  }

  function setActiveLoadout(nextLoadout) {
    suppressDirty = true;
    loadout = nextLoadout || null;
    isDirty = false;
    autosaveDueAt = null;
    clearAutosaveTicker();
    saveError = null;
    if (activeSource === 'online') {
      const record = onlineLoadouts.find(r => r.data === loadout);
      activeOnlineId = record?.id || null;
      sharePublic = record?.public || false;
      shareLink = record?.share_code && typeof window !== 'undefined'
        ? `${window.location.origin}/tools/loadouts/${record.share_code}`
        : '';
    }
    clothingReplaceNotice = '';
    setTimeout(() => {
      suppressDirty = false;
    }, 0);
  }

  function setActiveSource(nextSource) {
    activeSource = nextSource;
    loadouts = activeSource === 'online'
      ? onlineLoadouts.map(r => r.data)
      : localLoadouts;
    setActiveLoadout(loadouts[0] || null);
  }

  async function fetchOnlineLoadouts() {
    if (!isLoggedIn) return;
    onlineLoading = true;
    onlineError = null;
    try {
      const response = await fetch('/api/tools/loadout');
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error || 'Failed to load online loadouts');
      }
      onlineLoadouts = (data || []).map(row => ({
        id: row.id,
        name: row.name,
        public: !!row.public,
        share_code: row.share_code || null,
        last_update: row.last_update,
        data: row.data || createEmptyLoadout()
      }));
      if (activeSource === 'online') {
        loadouts = onlineLoadouts.map(r => r.data);
        setActiveLoadout(loadouts[0] || null);
      }
    } catch (err) {
      console.error('Failed to load online loadouts:', err);
      onlineError = err.message;
    } finally {
      onlineLoading = false;
    }
  }

  function markDirty() {
    if (suppressDirty) return;
    loadoutVersion += 1;
    if (activeSource !== 'online') return;
    if (!loadout) return;
    isDirty = true;
    scheduleAutosave();
  }

  function touchLoadouts() {
    if (activeSource === 'online') {
      onlineLoadouts = onlineLoadouts;
    } else {
      localLoadouts = localLoadouts;
      loadouts = localLoadouts;
      writeLocalLoadouts(localLoadouts);
    }
    loadoutVersion += 1;
  }

  function scheduleAutosave() {
    if (autosaveTimeout) clearTimeout(autosaveTimeout);
    autosaveDueAt = Date.now() + AUTOSAVE_DELAY_MS;
    autosaveTimeout = setTimeout(() => {
      autosaveTimeout = null;
      handleSave();
    }, AUTOSAVE_DELAY_MS);
    if (!autosaveTicker) {
      autosaveTicker = setInterval(() => {
        autosaveNow = Date.now();
      }, 1000);
    }
  }

  function clearAutosaveTicker() {
    if (autosaveTicker) {
      clearInterval(autosaveTicker);
      autosaveTicker = null;
    }
  }

  async function handleSave() {
    if (activeSource !== 'online' || !loadout) return;
    if (!activeOnlineId) return;
    isSaving = true;
    saveError = null;
    try {
      const payload = {
        name: loadout.Name || 'New Loadout',
        data: loadout,
        public: sharePublic || false
      };
      const response = await fetch(`/api/tools/loadout/${activeOnlineId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result?.error || 'Failed to save loadout');
      }
      const recordIndex = onlineLoadouts.findIndex(r => r.id === activeOnlineId);
      if (recordIndex >= 0) {
        onlineLoadouts[recordIndex] = {
          ...onlineLoadouts[recordIndex],
          name: result?.name || payload.name,
          public: result?.public ?? sharePublic,
          share_code: result?.share_code ?? onlineLoadouts[recordIndex].share_code,
          last_update: result?.last_update || onlineLoadouts[recordIndex].last_update,
          data: loadout
        };
        onlineLoadouts = onlineLoadouts;
      }
      if (result?.share_code && typeof window !== 'undefined') {
        shareLink = `${window.location.origin}/tools/loadouts/${result.share_code}`;
      }
      isDirty = false;
      autosaveDueAt = null;
      clearAutosaveTicker();
    } catch (err) {
      console.error('Save failed:', err);
      saveError = err.message;
    } finally {
      isSaving = false;
    }
  }

  async function createOnlineLoadout() {
    const newLoadout = createEmptyLoadout();
    try {
      const response = await fetch('/api/tools/loadout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newLoadout.Name, data: newLoadout })
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result?.error || 'Failed to create loadout');
      }
      const record = {
        id: result.id,
        name: result.name,
        public: !!result.public,
        share_code: result.share_code || null,
        last_update: result.last_update,
        data: result.data || newLoadout
      };
      onlineLoadouts = [record, ...onlineLoadouts];
      loadouts = onlineLoadouts.map(r => r.data);
      setActiveLoadout(record.data);
      isDirty = false;
      autosaveDueAt = null;
      clearAutosaveTicker();
    } catch (err) {
      console.error('Create failed:', err);
      onlineError = err.message;
    }
  }

  function createLocalLoadout() {
    const newLoadout = createEmptyLoadout();
    localLoadouts = [newLoadout, ...localLoadouts];
    loadouts = localLoadouts;
    setActiveLoadout(newLoadout);
    writeLocalLoadouts(localLoadouts);
  }

  async function deleteActiveLoadout() {
    if (!loadout) return;
    if (activeSource === 'online') {
      if (!activeOnlineId) return;
      try {
        const response = await fetch(`/api/tools/loadout/${activeOnlineId}`, { method: 'DELETE' });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result?.error || 'Failed to delete loadout');
        }
        onlineLoadouts = onlineLoadouts.filter(r => r.id !== activeOnlineId);
        loadouts = onlineLoadouts.map(r => r.data);
        setActiveLoadout(loadouts[0] || null);
      } catch (err) {
        console.error('Delete failed:', err);
        saveError = err.message;
      }
    } else {
      const index = localLoadouts.findIndex(x => x.Id === loadout.Id);
      if (index < 0) return;
      localLoadouts.splice(index, 1);
      localLoadouts = localLoadouts;
      loadouts = localLoadouts;
      setActiveLoadout(loadouts[0] || null);
      writeLocalLoadouts(localLoadouts);
    }
  }

  function exportActiveLoadout() {
    if (!loadout) return;
    const data = JSON.stringify(loadout);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (loadout.Name ?? 'loadout') + '.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleFileChange() {
    const file = fileInput?.files?.[0];
    if (!file) return;
    const reader = new FileReader();

    reader.onload = (e) => {
      try {
        const contents = e.target.result;
        const data = JSON.parse(contents);
        if (!data || typeof data !== 'object') return;
        const parsed = ensureLoadoutIds([data])[0];
        localLoadouts = [parsed, ...localLoadouts];
        loadouts = localLoadouts;
        setActiveLoadout(parsed);
        writeLocalLoadouts(localLoadouts);
      } catch (err) {
        console.error('Failed to import loadout:', err);
      }
    };

    reader.readAsText(file);
  }

  function importLoadoutFile() {
    if (!fileInput) return;
    fileInput.click();
  }

  function openPicker(kind) {
    if (activePicker === kind && showPickerDialog) {
      closePicker();
      return;
    }
    activePicker = kind;
    showPickerDialog = true;
    showPickerPreview = false;
    pickerPreviewRow = null;
    pickerPreviewItem = null;
  }

  function closePicker() {
    showPickerDialog = false;
    activePicker = null;
    showPickerPreview = false;
    pickerPreviewRow = null;
    pickerPreviewItem = null;
  }

  function setMobilePanelIndex(index) {
    if (compareMode) {
      activeMobilePanel = 'weapons';
      return;
    }
    const count = mobilePanels.length;
    const nextIndex = ((index % count) + count) % count;
    activeMobilePanel = mobilePanels[nextIndex];
  }

  function handlePanelSwipe(direction) {
    if (!isMobileLayout) return;
    if (compareMode) {
      activeMobilePanel = 'weapons';
      return;
    }
    if (direction === 'next') {
      setMobilePanelIndex(activeMobilePanelIndex + 1);
    } else if (direction === 'prev') {
      setMobilePanelIndex(activeMobilePanelIndex - 1);
    }
  }

  function handleTouchStart(event) {
    if (!isMobileLayout) return;
    if (compareMode) return;
    const touch = event.touches?.[0];
    if (!touch) return;
    touchStartX = touch.clientX;
    touchStartY = touch.clientY;
    swipeActive = true;
    swipeOffset = 0;
  }

  function handleTouchMove(event) {
    if (!isMobileLayout || !swipeActive) return;
    if (compareMode) return;
    const touch = event.touches?.[0];
    if (!touch) return;
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;
    if (Math.abs(deltaX) < Math.abs(deltaY)) return;
    const width = mobilePanelsEl?.clientWidth || windowWidth || 0;
    const clamped = Math.max(-width, Math.min(width, deltaX));
    swipeOffset = clamped;
  }

  function handleTouchEnd(event) {
    if (!isMobileLayout) return;
    if (compareMode) return;
    const touch = event.changedTouches?.[0];
    if (!touch) return;
    const deltaX = touch.clientX - touchStartX;
    const deltaY = touch.clientY - touchStartY;
    swipeActive = false;
    if (Math.abs(deltaX) < 40 || Math.abs(deltaX) < Math.abs(deltaY)) {
      swipeOffset = 0;
      return;
    }
    if (deltaX < 0) {
      handlePanelSwipe('next');
    } else {
      handlePanelSwipe('prev');
    }
    swipeOffset = 0;
  }

  function applyPickerSelection(item) {
    if (!loadout || !activePicker || !item) return;

    if (activePicker === 'weapon') {
      loadout.Gear.Weapon.Name = item.Name;
      loadout.Gear.Weapon.Amplifier = null;
      loadout.Gear.Weapon.Scope = null;
      loadout.Gear.Weapon.Sight = null;
      loadout.Gear.Weapon.Absorber = null;
      loadout.Gear.Weapon.Matrix = null;
      loadout.Gear.Weapon.Implant = null;
    } else if (activePicker === 'amplifier') {
      loadout.Gear.Weapon.Amplifier = { Name: item.Name };
    } else if (activePicker === 'absorber') {
      loadout.Gear.Weapon.Absorber = { Name: item.Name };
    } else if (activePicker === 'scope') {
      loadout.Gear.Weapon.Scope = { Name: item.Name };
    } else if (activePicker === 'scope-sight') {
      if (!loadout.Gear.Weapon.Scope) {
        loadout.Gear.Weapon.Scope = { Name: null, Sight: null };
      }
      loadout.Gear.Weapon.Scope.Sight = { Name: item.Name };
    } else if (activePicker === 'sight') {
      loadout.Gear.Weapon.Sight = { Name: item.Name };
    } else if (activePicker === 'matrix') {
      loadout.Gear.Weapon.Matrix = { Name: item.Name };
    } else if (activePicker === 'implant') {
      loadout.Gear.Weapon.Implant = { Name: item.Name };
    } else if (activePicker === 'armorset') {
      const armorSet = getArmorSet(item.Name);
      if (armorSet) {
        loadout.Gear.Armor.SetName = armorSet.Name;
        armorSlots.forEach(slot => {
          loadout.Gear.Armor[slot] = {
            Name: armorSet.Armors.flat().find(x => slot === x.Properties.Slot)?.Name,
            Plate: loadout.Gear.Armor[slot].Plate
          };
        });
      }
    } else if (activePicker.startsWith('armor-')) {
      const slot = activePicker.split('-')[1];
      loadout.Gear.Armor[slot] = { Name: item.Name, Plate: loadout.Gear.Armor[slot].Plate };
    } else if (activePicker.startsWith('armorplating')) {
      if (loadout.Gear.Armor.ManageIndividual) {
        const slot = activePicker.split('-')[1];
        if (!slot || loadout.Gear.Armor[slot].Name == null) {
          return;
        }
        loadout.Gear.Armor[slot].Plate = { Name: item.Name };
      } else {
        loadout.Gear.Armor.PlateName = item.Name;
        armorSlots.forEach(slot => {
          if (loadout.Gear.Armor[slot].Name == null) return;
          loadout.Gear.Armor[slot].Plate = { Name: item.Name };
        });
      }
    } else if (activePicker === 'pet') {
      loadout.Gear.Pet = { Name: item.Name, Effect: null };
    } else if (activePicker === 'ring-left') {
      setClothingSlot('Ring', 'Left', item.Name);
    } else if (activePicker === 'ring-right') {
      setClothingSlot('Ring', 'Right', item.Name);
    } else if (activePicker === 'consumable') {
      addConsumableItem(item);
      return;
    } else if (activePicker === 'clothing') {
      addClothingItem(item);
    } else if (activePicker.startsWith('clothing-')) {
      const slotName = activePicker.replace('clothing-', '');
      setClothingSlot(slotName, null, item.Name);
    }

  }

  function handlePickerRowClick(event) {
    if (!loadout || !activePicker) return;
    const row = event?.detail?.row;
    const item = row?._item;
    if (!item) return;
    pickerPreviewRow = row;
    pickerPreviewItem = item;
    showPickerPreview = true;
  }

  function confirmPickerSelection() {
    if (!pickerPreviewItem) return;
    applyPickerSelection(pickerPreviewItem);
    touchLoadouts();
    markDirty();
    closePicker();
  }

  function returnToPickerList() {
    showPickerPreview = false;
    pickerPreviewRow = null;
    pickerPreviewItem = null;
  }

  function openImportSourceDialog() {
    showImportSourceDialog = true;
  }

  function handleImportFromFile() {
    showImportSourceDialog = false;
    importLoadoutFile();
  }

  function handleImportLocal() {
    showImportSourceDialog = false;
    showImportDialog = true;
  }

  function openShareDialog() {
    if (activeSource !== 'online' || !loadout) return;
    const record = onlineLoadouts.find(r => r.data === loadout);
    sharePublic = record?.public || false;
    shareLink = record?.share_code && typeof window !== 'undefined'
      ? `${window.location.origin}/tools/loadouts/${record.share_code}`
      : '';
    showShareDialog = true;
  }

  async function handleShareToggle(event) {
    sharePublic = !!event?.target?.checked;
    if (activeSource !== 'online' || !loadout || !activeOnlineId) return;
    await handleSave();
  }

  function applyShareSettings() {
    showShareDialog = false;
  }

  async function importLocalLoadouts() {
    if (!isLoggedIn || importInProgress) return;
    importInProgress = true;
    importError = null;
    importSuccess = false;
    try {
      const candidates = [...localLoadouts];
      if (candidates.length === 0) {
        importInProgress = false;
        return;
      }
      const batches = [];
      let currentBatch = [];
      const encoder = new TextEncoder();
      const maxPayloadSize = 20000;
      const basePayloadSize = encoder.encode(JSON.stringify({ loadouts: [] })).length;
      let currentSize = basePayloadSize;
      for (const item of candidates) {
        const payload = JSON.stringify(item);
        const itemSize = encoder.encode(payload).length;
        if (itemSize + basePayloadSize > maxPayloadSize) {
          continue;
        }
        const nextSize = currentSize + itemSize + (currentBatch.length > 0 ? 1 : 0);
        if (nextSize > maxPayloadSize && currentBatch.length > 0) {
          batches.push(currentBatch);
          currentBatch = [item];
          currentSize = basePayloadSize + itemSize;
          continue;
        }
        currentBatch.push(item);
        currentSize = nextSize;
      }
      if (currentBatch.length > 0) batches.push(currentBatch);

      for (const batch of batches) {
        const response = await fetch('/api/tools/loadout/import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ loadouts: batch })
        });
        const result = await response.json();
        if (!response.ok) {
          throw new Error(result?.error || 'Failed to import loadouts');
        }
      }

      localLoadouts = [];
      writeLocalLoadouts(localLoadouts);
      importSuccess = true;
      await fetchOnlineLoadouts();
      if (activeSource === 'online' && onlineLoadouts.length > 0) {
        setActiveLoadout(onlineLoadouts[0].data);
      }
    } catch (err) {
      console.error('Import failed:', err);
      importError = err.message;
    } finally {
      importInProgress = false;
    }
  }

  function handleBeforeUnload(event) {
    if (activeSource === 'online' && isDirty) {
      event.preventDefault();
      event.returnValue = '';
    }
  }

  onMount(async () => {
    localLoadouts = readLocalLoadouts();
    loadouts = localLoadouts;
    if (localLoadouts.length > 0) {
      setActiveLoadout(localLoadouts[0]);
    }

    if (isLoggedIn) {
      await fetchOnlineLoadouts();
      setActiveSource('online');
      if (!hasPromptedImport && onlineLoadouts.length === 0 && localLoadouts.length > 0) {
        showImportDialog = true;
        hasPromptedImport = true;
      }
    } else {
      setActiveSource('local');
    }

    // Lazy load entity data
    entitiesLoading = true;
    try {
      const entities = await loadLoadoutEntities();
      processEntityData(entities);
    } catch (error) {
      console.error('Failed to load entity data:', error);
    } finally {
      entitiesLoading = false;
    }

    try {
      const response = await fetch(`${getApiBase()}/effects`);
      if (response.ok) {
        effectsCatalog = await response.json();
        effectCaps = buildEffectCaps(effectsCatalog);
      }
    } catch (error) {
      console.error('Failed to load effects catalog:', error);
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', handleBeforeUnload);
    }
  });

  onDestroy(() => {
    if (autosaveTimeout) clearTimeout(autosaveTimeout);
    clearAutosaveTicker();
    if (typeof window !== 'undefined') {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    }
  });

  $: if (activeSource === 'local') {
    writeLocalLoadouts(localLoadouts);
  }

  $: autosaveSeconds = autosaveDueAt ? Math.max(0, Math.ceil((autosaveDueAt - autosaveNow) / 1000)) : null;

  $: activeLoadoutKey = activeSource === 'online' ? activeOnlineId : loadout?.Id;
  $: activeRecord = activeSource === 'online'
    ? onlineLoadouts.find(r => r.id === activeOnlineId)
    : null;
  $: isPublicLoadout = !!activeRecord?.public;
  $: pickerConfig = activePicker ? (isMobileLayout, getPickerConfig(activePicker)) : null;
  $: pickerRowHeight = isMobileLayout ? 30 : 34;
  $: {
    // Back-compat: still used by some compare rows; keep it reactive.
    loadoutVersion;
    effectCaps;
    entitiesVersion;
    activeBuffSummary = loadout ? getBuffSummary(loadout) : null;
  }

  function getLoadoutListLabel(item) {
    if (!item) return 'Untitled';
    if (item.Name && item.Name !== 'New Loadout') return item.Name;
    const weaponName = item.Gear?.Weapon?.Name;
    const armorName = item.Gear?.Armor?.SetName;
    if (weaponName && armorName) return `${weaponName} (${armorName})`;
    if (weaponName) return weaponName;
    return item.Name || 'New Loadout';
  }

  function handleNewLoadout() {
    if (activeSource === 'online') {
      createOnlineLoadout();
    } else {
      createLocalLoadout();
    }
  }

  function handleManualSave() {
    if (activeSource !== 'online') return;
    if (!isDirty) return;
    handleSave();
  }

  async function switchSource(source) {
    if (source === activeSource) return;
    if (source === 'online') {
      if (!isLoggedIn) return;
      if (!onlineLoadouts.length) {
        await fetchOnlineLoadouts();
      }
    }
    setActiveSource(source);
  }

  $: sidebarLoadouts = activeSource === 'online'
    ? onlineLoadouts.map(record => ({ id: record.id, data: record.data }))
    : localLoadouts.map(item => ({ id: item.Id, data: item }));

  $: if (activeSource === 'online') {
    loadouts = onlineLoadouts.map(r => r.data);
  } else {
    loadouts = localLoadouts;
  }

  $: filteredLoadouts = sidebarLoadouts.filter(item => {
    const name = getLoadoutListLabel(item.data).toLowerCase();
    const query = loadoutSearch.trim().toLowerCase();
    return !query || name.includes(query);
  });

  $: if(loadout?.Gear.Weapon.Enhancers) {
    loadout.Gear.Weapon.Enhancers.Damage = clamp(loadout.Gear.Weapon.Enhancers.Damage, 0, 10);
    loadout.Gear.Weapon.Enhancers.Accuracy = clamp(loadout.Gear.Weapon.Enhancers.Accuracy, 0, 10);
    loadout.Gear.Weapon.Enhancers.Range = clamp(loadout.Gear.Weapon.Enhancers.Range, 0, 10);
    loadout.Gear.Weapon.Enhancers.Economy = clamp(loadout.Gear.Weapon.Enhancers.Economy, 0, 10);
    loadout.Gear.Weapon.Enhancers.SkillMod = clamp(loadout.Gear.Weapon.Enhancers.SkillMod, 0, 10);
  }

  $: if(loadout?.Gear.Armor.Enhancers) {
    loadout.Gear.Armor.Enhancers.Defense = clamp(loadout.Gear.Armor.Enhancers.Defense, 0, 10);
    loadout.Gear.Armor.Enhancers.Durability = clamp(loadout.Gear.Armor.Enhancers.Durability, 0, 10);
  }

  $: if (loadout && loadout.Markup == null) {
    resetMarkup();
  }
  $: if (loadout?.Markup) {
    if (loadout.Markup.ArmorSet == null) loadout.Markup.ArmorSet = 100;
    if (loadout.Markup.PlateSet == null) loadout.Markup.PlateSet = 100;
    if (!loadout.Markup.Armors) loadout.Markup.Armors = {};
    if (!loadout.Markup.Plates) loadout.Markup.Plates = {};
    armorSlots.forEach(slot => {
      if (loadout.Markup.Armors[slot] == null) loadout.Markup.Armors[slot] = 100;
      if (loadout.Markup.Plates[slot] == null) loadout.Markup.Plates[slot] = 100;
    });
  }

  function resetMarkup() {
    loadout.Markup = {
      Weapon: 100,
      Ammo: 100,
      Amplifier: 100,
      Absorber: 100,
      Scope: 100,
      Sight: 100,
      ScopeSight: 100,
      Matrix: 100,
      Implant: 100,
      ArmorSet: 100,
      PlateSet: 100,
      Armors: {
        Head: 100,
        Torso: 100,
        Arms: 100,
        Hands: 100,
        Legs: 100,
        Shins: 100,
        Feet: 100,
      },
      Plates: {
        Head: 100,
        Torso: 100,
        Arms: 100,
        Hands: 100,
        Legs: 100,
        Shins: 100,
        Feet: 100,
      },
    };
    touchLoadouts();
    markDirty();
  }

  $: if (loadout?.Gear?.Armor?.ManageIndividual === false && loadout?.Gear?.Armor?.SetName === null) {
    resetArmor();
  } else if (loadout?.Gear?.Armor?.ManageIndividual === true) {
    loadout.Gear.Armor.SetName = null;
    loadout.Gear.Armor.PlateName = null;
  }



  function getTotalDamage(item) {
    return (item.Properties?.Damage?.Impact
      + item.Properties?.Damage?.Cut
      + item.Properties?.Damage?.Stab
      + item.Properties?.Damage?.Penetration
      + item.Properties?.Damage?.Shrapnel
      + item.Properties?.Damage?.Burn
      + item.Properties?.Damage?.Cold
      + item.Properties?.Damage?.Acid
      + item.Properties?.Damage?.Electric) || null;
  }

  function getEffectiveDamage(item) {
    const totalDamage = getTotalDamage(item);

    return totalDamage != null
      ? totalDamage * (0.88*0.75 + 0.02*1.75)
      : null;
  }

  function getDps(item) {
    const reload = getReload(item);
    const effectiveDamage = getEffectiveDamage(item);

    return effectiveDamage != null && reload != null
      ? effectiveDamage / reload
      : null;
  }

  function getDpp(item) {
    const cost = getCost(item);
    const effectiveDamage = getEffectiveDamage(item);

    return effectiveDamage > 0 && cost != null
      ? effectiveDamage / cost
      : null;
  }

  function getCost(item) {
    return item.Properties?.Economy?.Decay != null && (item.Properties?.Economy?.AmmoBurn == undefined || item.Properties?.Economy?.AmmoBurn >= 0)
      ? (item.Properties?.Economy?.Decay + (item.Properties?.Economy?.AmmoBurn ?? 0) / 100)
      : null;
  }

  function getReload(item) {
    return item.Properties?.UsesPerMinute != null
      ? 60 / item.Properties?.UsesPerMinute
      : null;
  }

  function getTotalUses(item) {
    let maxTT = item.Properties?.Economy?.MaxTT || null;
    let minTT = item.Properties?.Economy?.MinTT ?? 0;
    let decay = item.Properties?.Economy?.Decay || null;

    return maxTT != null && decay != null
      ? Math.floor((maxTT - minTT) / (decay / 100))
      : null;
  }
  
  function getTotalAbsorberUses(absorber, weapon) {
    let maxTT = absorber.Properties?.Economy?.MaxTT || null;
    let minTT = absorber.Properties?.Economy?.MinTT ?? 0;
    let decay = absorber.Properties?.Economy?.Absorption != null 
      ? weapon.Properties?.Economy?.Decay * absorber.Properties?.Economy?.Absorption
      : null;

    return maxTT != null && decay != null
      ? Math.floor((maxTT - minTT) / (decay / 100))
      : null;
  }

  function getTotalDefense(item) {
    return (item.Properties?.Defense?.Impact ?? 0) + (item.Properties?.Defense?.Cut ?? 0) + (item.Properties?.Defense?.Stab ?? 0) + (item.Properties?.Defense?.Penetration ?? 0) + (item.Properties?.Defense?.Shrapnel ?? 0) + (item.Properties?.Defense?.Burn ?? 0) + (item.Properties?.Defense?.Cold ?? 0) + (item.Properties?.Defense?.Acid ?? 0) + (item.Properties?.Defense?.Electric ?? 0);
  }

  function getMaxArmorDecay(item) {
    return item.Properties?.Economy.Durability && getTotalDefense(item)
      ? getTotalDefense(item) * ((100000 - item.Properties?.Economy.Durability) / 100000) * 0.05
      : null;
  }

  function getTotalAbsorption(item) {
    return item.Properties?.Economy.MaxTT && getMaxArmorDecay(item)
      ? getTotalDefense(item) * ((item.Properties?.Economy.MaxTT - (item.Properties?.Economy.MinTT ?? 0)) / (getMaxArmorDecay(item) / 100))
      : null;
  }

  function getWeapon(name) {
    return weapons.find(x => x.Name === name);
  }

  function getAmplifier(name) {
    return amplifiers.find(x => x.Name === name);
  }

  function getAbsorber(name) {
    return absorbers.find(x => x.Name === name);
  }

  function getScope(name) {
    return scopes.find(x => x.Name === name);
  }

  function getSight(name) {
    return sights.find(x => x.Name === name);
  }

  function getMatrix(name) {
    return matrices.find(x => x.Name === name);
  }

  function getImplant(name) {
    return implants.find(x => x.Name === name);
  }

  function getArmorSet(name) {
    return armorsets.find(x => x.Name === name);
  }

  function getArmor(name) {
    return armors.find(x => x.Name === name);
  }

  function getArmorPlating(name) {
    return armorplatings.find(x => x.Name === name);
  }

  function getAttachmentCount() {
    let weapon = getWeapon();

    return 3 + (weapon?.Properties?.Class === 'Ranged'
      ? 2
      : weapon?.Properties?.Class === 'Melee'
      ? 1
      : weapon?.Properties?.Class === 'Mindforce'
      ? 1
      : 0);
  }

  function getClothingSlot(slotName, side = null) {
    const list = loadout?.Gear?.Clothing || [];
    if (isRingSlot(slotName)) {
      return list.find(item =>
        isRingSlot(item?.Slot)
        && (side ? item?.Side === side : !item?.Side)
      );
    }
    return list.find(item => item?.Slot === slotName && (side ? item?.Side === side : !item?.Side));
  }

  function getClothingItem(name) {
    return clothing.find(item => item.Name === name);
  }

  function getClothingWikiLink(name) {
    return `/items/clothing/${encodeURIComponentSafe(name)}`;
  }

  function formatEffectCount(count) {
    if (!count) return 'â€”';
    return count === 1 ? '1 effect' : `${count} effects`;
  }

  function getClothingItemSlot(item) {
    return item?.Properties?.Slot || item?.Slot || 'Unknown';
  }

  function hasClothingEffects(item) {
    const effectsCount = item?.EffectsOnEquip?.length
      || item?.Effects?.length
      || item?.Properties?.Effects?.length
      || item?.Properties?.EffectsOnEquip?.length
      || 0;
    const setEffectsCount = item?.Set?.EffectsOnSetEquip?.length
      || item?.EffectsOnSetEquip?.length
      || item?.SetEffects?.length
      || item?.Properties?.SetEffects?.length
      || item?.Properties?.Set?.EffectsOnSetEquip?.length
      || 0;
    return effectsCount > 0 || setEffectsCount > 0;
  }

  function getClothingEffectCount(item) {
    const equipCount = item?.EffectsOnEquip?.length
      || item?.Effects?.length
      || item?.Properties?.Effects?.length
      || item?.Properties?.EffectsOnEquip?.length
      || 0;
    const setCount = item?.Set?.EffectsOnSetEquip?.length
      || item?.EffectsOnSetEquip?.length
      || item?.SetEffects?.length
      || item?.Properties?.SetEffects?.length
      || item?.Properties?.Set?.EffectsOnSetEquip?.length
      || 0;
    return (equipCount || 0) + (setCount || 0);
  }

  function getClothingEffectLabel(item) {
    const count = getClothingEffectCount(item);
    return count > 0 ? `${count} effects` : 'â€”';
  }

  function addClothingItem(item) {
    if (!loadout?.Gear || !item) return;
    const slotName = getClothingItemSlot(item);
    if (!slotName || slotName === 'Unknown' || isRingSlot(slotName)) return;
    const list = [...(loadout.Gear.Clothing || [])];
    const existingIndex = list.findIndex(entry => !isRingSlot(entry?.Slot) && entry?.Slot === slotName);
    if (existingIndex >= 0) {
      const replaced = list[existingIndex];
      list.splice(existingIndex, 1);
      clothingReplaceNotice = `Replaced ${replaced?.Name || 'item'} in ${slotName}.`;
    } else {
      clothingReplaceNotice = '';
    }
    list.push({ Slot: slotName, Name: item.Name });
    loadout.Gear.Clothing = list;
    touchLoadouts();
    markDirty();
  }

  function removeClothingItem(name, slotName) {
    if (!loadout?.Gear) return;
    const list = [...(loadout.Gear.Clothing || [])];
    loadout.Gear.Clothing = list.filter(entry => !(entry?.Name === name && entry?.Slot === slotName));
    touchLoadouts();
    markDirty();
  }

  function getConsumableItem(name) {
    return stimulants.find(item => item.Name === name);
  }

  function hasConsumableEffects(item) {
    return (item?.EffectsOnConsume?.length || 0) > 0;
  }

  function getConsumableEffectCount(item) {
    return item?.EffectsOnConsume?.length || 0;
  }

  function addConsumableItem(item) {
    if (!loadout?.Gear || !item) return;
    const list = [...(loadout.Gear.Consumables || [])];
    if (!list.find(entry => entry?.Name === item.Name)) {
      list.push({ Name: item.Name });
      loadout.Gear.Consumables = list;
      touchLoadouts();
      markDirty();
    }
  }

  function removeConsumableItem(name) {
    if (!loadout?.Gear) return;
    const list = [...(loadout.Gear.Consumables || [])];
    loadout.Gear.Consumables = list.filter(entry => entry?.Name !== name);
    touchLoadouts();
    markDirty();
  }

  function getEffectStrength(effect) {
    const value = effect?.Values?.Strength
      ?? effect?.Values?.Value
      ?? effect?.Properties?.Strength
      ?? effect?.Properties?.Value
      ?? 0;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function matchesEffect(effect, names) {
    return names.includes(effect?.Name);
  }

  function sumEffectValues(effects, def) {
    return (effects || []).reduce((total, effect) => {
      if (matchesEffect(effect, def.positive)) {
        return total + getEffectStrength(effect);
      }
      if (matchesEffect(effect, def.negative)) {
        return total - Math.abs(getEffectStrength(effect));
      }
      return total;
    }, 0);
  }

  function maxConsumableEffectValue(consumablesList, def) {
    let bestPositive = { value: 0, source: null };
    let bestNegative = { value: 0, source: null };

    (consumablesList || []).forEach(entry => {
      const item = getConsumableItem(entry?.Name);
      (item?.EffectsOnConsume || []).forEach(effect => {
        const strength = getEffectStrength(effect);
        if (matchesEffect(effect, def.positive)) {
          if (strength > bestPositive.value) {
            bestPositive = { value: strength, source: item?.Name || null };
          }
        } else if (matchesEffect(effect, def.negative)) {
          const negativeValue = -Math.abs(strength);
          if (negativeValue < bestNegative.value) {
            bestNegative = { value: negativeValue, source: item?.Name || null };
          }
        }
      });
    });

    return {
      value: bestPositive.value + bestNegative.value,
      positive: bestPositive,
      negative: bestNegative
    };
  }

  function getPetEffectStrength(effect) {
    return effect?.Properties?.Strength ?? effect?.Values?.Strength ?? effect?.Values?.Value ?? 0;
  }

  function getPetEffectKey(effect) {
    const name = effect?.Name || '';
    const strength = getPetEffectStrength(effect);
    return `${name}::${strength}`;
  }

  function getActivePetEffect(loadout) {
    if (!loadout?.Gear?.Pet?.Name || !loadout.Gear.Pet.Effect) return null;
    const pet = pets.find(p => p.Name === loadout.Gear.Pet.Name);
    if (!pet?.Effects) return null;
    const target = loadout.Gear.Pet.Effect;
    const keyedMatch = pet.Effects.find(effect => getPetEffectKey(effect) === target);
    if (keyedMatch) return keyedMatch;
    return pet.Effects.find(effect => effect.Name === target) || null;
  }

  function getClothingEquipEffects(loadout) {
    const list = loadout?.Gear?.Clothing || [];
    return list.flatMap(entry => {
      const item = getClothingItem(entry?.Name);
      return item?.EffectsOnEquip ?? [];
    });
  }

  function getClothingSetEffects(loadout) {
    const list = loadout?.Gear?.Clothing || [];
    const bySet = new Map();
    list.forEach(entry => {
      const item = getClothingItem(entry?.Name);
      if (!item?.Set?.Name || !item?.Set?.EffectsOnSetEquip?.length) return;
      const setName = item.Set.Name;
      const existing = bySet.get(setName) || { items: [], effects: item.Set.EffectsOnSetEquip };
      existing.items.push(item);
      bySet.set(setName, existing);
    });

    const effects = [];
    bySet.forEach(({ items, effects: setEffects }) => {
      const pieceCount = items.length;
      const activeEffects = (setEffects || [])
        .filter(effect => effect?.Values?.MinSetPieces == null || effect.Values.MinSetPieces <= pieceCount)
        .sort((a, b) => (b?.Values?.MinSetPieces ?? 0) - (a?.Values?.MinSetPieces ?? 0))
        .filter((value, index, self) => self.findIndex(effect => effect.Name === value.Name) === index);
      effects.push(...activeEffects);
    });

    return effects;
  }

  function getAllEffectsSummary(loadout) {
    if (!loadout) return [];
    const weaponEquipEffects = getWeaponEquipEffects(loadout);
    const weaponUseEffects = getWeaponUseEffects(loadout);
    const armorEquipEffects = getArmorEquipEffects(loadout);
    const armorSetEffects = getArmorSetEffects(loadout) || [];
    const clothingEquipEffects = getClothingEquipEffects(loadout);
    const clothingSetEffects = getClothingSetEffects(loadout);

    // Bonus stats: count toward Total cap only (ignore Item/Action caps).
    const bonusEffects = [
      { Name: 'Increased Damage', Values: { Strength: Number(loadout?.Properties?.BonusDamage ?? 0) || 0 } },
      { Name: 'Added Critical Chance', Values: { Strength: Number(loadout?.Properties?.BonusCritChance ?? 0) || 0 } },
      { Name: 'Added Critical Damage', Values: { Strength: Number(loadout?.Properties?.BonusCritDamage ?? 0) || 0 } },
      { Name: 'Increased Reload Speed', Values: { Strength: Number(loadout?.Properties?.BonusReload ?? 0) || 0 } }
    ].filter(effect => Math.abs(getEffectStrength(effect)) > 0.0001);

    const itemEffects = [
      ...weaponEquipEffects,
      ...weaponUseEffects,
      ...armorEquipEffects,
      ...armorSetEffects,
      ...clothingEquipEffects,
      ...clothingSetEffects
    ];

    const getCatalogEffect = (name) => {
      if (!name || !effectsCatalog?.length) return null;
      return effectsCatalog.find(effect => effect?.Name === name) || null;
    };

    const getCatalogPolarity = (name) => {
      const catalog = getCatalogEffect(name);
      const isPositive = catalog?.Properties?.IsPositive;
      if (isPositive === true || isPositive === 1 || isPositive === 'true') return 'positive';
      if (isPositive === false || isPositive === 0 || isPositive === 'false') return 'negative';
      return null;
    };

    const getLimitsForName = (name) => effectCaps?.[name] || null;

    // Consumables: only the strongest instance per effect name counts (positive/negative separated by IsPositive).
    const consumableList = loadout?.Gear?.Consumables || [];
    const consumableBest = new Map();
    consumableList.forEach(entry => {
      const item = getConsumableItem(entry?.Name);
      (item?.EffectsOnConsume || []).forEach(effect => {
        const name = effect?.Name;
        if (!name) return;
        const strength = getEffectStrength(effect);
        const polarity = getCatalogPolarity(name) || 'positive';
        const current = consumableBest.get(name) || { positive: 0, negative: 0 };
        if (polarity === 'negative') {
          if (strength > current.negative) current.negative = strength;
        } else {
          if (strength > current.positive) current.positive = strength;
        }
        consumableBest.set(name, current);
      });
    });
    const consumableEffects = [];
    consumableBest.forEach((value, name) => {
      if (value.positive) consumableEffects.push({ Name: name, Values: { Strength: value.positive } });
      if (value.negative) consumableEffects.push({ Name: name, Values: { Strength: value.negative } });
    });

    const petEffect = getActivePetEffect(loadout);
    const actionEffects = [...consumableEffects];
    if (petEffect) actionEffects.push(petEffect);

    const parsePrefix = (name) => {
      if (!name) return null;
      for (const rule of PREFIX_RULES) {
        if (name.startsWith(`${rule.positive} `)) {
          return { type: rule.type, base: name.slice(rule.positive.length).trim(), direction: 1, rule };
        }
        if (name.startsWith(`${rule.negative} `)) {
          return { type: rule.type, base: name.slice(rule.negative.length).trim(), direction: -1, rule };
        }
      }
      return null;
    };

    const summaryMap = new Map();
    const prefixMap = new Map();

    const accumulate = (effect, source) => {
      const name = effect?.Name;
      if (!name) return;
      const value = getEffectStrength(effect);
      if (!Number.isFinite(value)) return;
      const unit = getEffectUnit(name, effect) || '';
      const prefix = parsePrefix(name);
      if (prefix) {
        const key = `${prefix.type}::${prefix.base}::${unit}`;
        const current = prefixMap.get(key) || {
          base: prefix.base,
          unit,
          itemPos: 0,
          itemNeg: 0,
          actionPos: 0,
          actionNeg: 0,
          bonusPos: 0,
          bonusNeg: 0,
          rule: prefix.rule
        };
        const posKey = source === 'action' ? 'actionPos' : source === 'bonus' ? 'bonusPos' : 'itemPos';
        const negKey = source === 'action' ? 'actionNeg' : source === 'bonus' ? 'bonusNeg' : 'itemNeg';
        if (prefix.direction > 0) current[posKey] += value;
        else current[negKey] += value;
        prefixMap.set(key, current);
        return;
      }

      const key = `${name}::${unit}`;
      const current = summaryMap.get(key) || { name, unit, item: 0, action: 0, bonus: 0 };
      if (source === 'action') current.action += value;
      else if (source === 'bonus') current.bonus += value;
      else current.item += value;
      summaryMap.set(key, current);
    };

    itemEffects.forEach(effect => accumulate(effect, 'item'));
    actionEffects.forEach(effect => accumulate(effect, 'action'));
    bonusEffects.forEach(effect => accumulate(effect, 'bonus'));

    prefixMap.forEach(entry => {
      // Cancel within each source, cap each source, then combine and apply total cap.
      const rawItem = (entry.itemPos || 0) - (entry.itemNeg || 0);
      const rawAction = (entry.actionPos || 0) - (entry.actionNeg || 0);
      const rawBonus = (entry.bonusPos || 0) - (entry.bonusNeg || 0);
      const basePositiveName = `${entry.rule.positive} ${entry.base}`.trim();
      const baseNegativeName = `${entry.rule.negative} ${entry.base}`.trim();
      const limits = getLimitsForName(basePositiveName) || getLimitsForName(baseNegativeName);
      const cappedItem = limits?.item != null ? clamp(rawItem, -limits.item, limits.item) : rawItem;
      const cappedAction = limits?.action != null ? clamp(rawAction, -limits.action, limits.action) : rawAction;
      const combined = cappedItem + cappedAction + rawBonus;
      const cappedTotal = limits?.total != null ? clamp(combined, -limits.total, limits.total) : combined;
      if (Math.abs(cappedTotal) <= 0.0001) return;
      const finalName = cappedTotal >= 0 ? basePositiveName : baseNegativeName;
      const polarity = getCatalogPolarity(finalName);
      summaryMap.set(`${finalName}::${entry.unit}`, {
        name: finalName,
        unit: entry.unit,
        prefix: { type: entry.rule.type, base: entry.base },
        rawItem,
        rawAction,
        rawBonus,
        cappedItem,
        cappedAction,
        signedTotal: cappedTotal,
        polarity,
        caps: limits || null,
        capped: {
          item: limits?.item != null && Math.abs(rawItem - cappedItem) > 0.0001,
          action: limits?.action != null && Math.abs(rawAction - cappedAction) > 0.0001,
          total: limits?.total != null && Math.abs((cappedItem + cappedAction + rawBonus) - cappedTotal) > 0.0001
        }
      });
    });

    return [...summaryMap.values()]
      .map(entry => {
        if (entry.signedTotal != null) return entry;
        const limits = getLimitsForName(entry.name);
        const rawItem = entry.item;
        const rawAction = entry.action;
        const rawBonus = entry.bonus || 0;
        const cappedItem = limits?.item != null ? clamp(rawItem, -limits.item, limits.item) : rawItem;
        const cappedAction = limits?.action != null ? clamp(rawAction, -limits.action, limits.action) : rawAction;
        const combined = cappedItem + cappedAction + rawBonus;
        const cappedTotal = limits?.total != null ? clamp(combined, -limits.total, limits.total) : combined;
        return {
          name: entry.name,
          unit: entry.unit,
          prefix: parsePrefix(entry.name),
          rawItem,
          rawAction,
          rawBonus,
          cappedItem,
          cappedAction,
          signedTotal: cappedTotal,
          polarity: getCatalogPolarity(entry.name),
          caps: limits || null,
          capped: {
            item: limits?.item != null && Math.abs(rawItem - cappedItem) > 0.0001,
            action: limits?.action != null && Math.abs(rawAction - cappedAction) > 0.0001,
            total: limits?.total != null && Math.abs((cappedItem + cappedAction + rawBonus) - cappedTotal) > 0.0001
          }
        };
      })
      .map(entry => {
        const cappedAny = !!(entry?.capped?.item || entry?.capped?.action || entry?.capped?.total);
        if (!cappedAny || !entry?.caps) {
          return { ...entry, cappedAny, capMessage: null };
        }

        const parts = [];
        if (entry.capped.item && entry.caps.item != null) {
          parts.push(`Item cap ${entry.caps.item}${entry.unit}: applied ${entry.cappedItem.toFixed(2)}${entry.unit} from ${entry.rawItem.toFixed(2)}${entry.unit}`);
        }
        if (entry.capped.action && entry.caps.action != null) {
          parts.push(`Action cap ${entry.caps.action}${entry.unit}: applied ${entry.cappedAction.toFixed(2)}${entry.unit} from ${entry.rawAction.toFixed(2)}${entry.unit}`);
        }
        if (entry.capped.total && entry.caps.total != null) {
          const rawCombined = entry.cappedItem + entry.cappedAction + (entry.rawBonus || 0);
          const bonusPart = entry.rawBonus ? ` (includes bonus ${entry.rawBonus.toFixed(2)}${entry.unit})` : '';
          parts.push(`Total cap ${entry.caps.total}${entry.unit}: applied ${entry.signedTotal.toFixed(2)}${entry.unit} from ${rawCombined.toFixed(2)}${entry.unit}${bonusPart}`);
        }

        return {
          ...entry,
          cappedAny,
          capMessage: parts.join(' • ')
        };
      })
      .filter(entry => Math.abs(entry.signedTotal) > 0.0001)
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  function formatSigned(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    const sign = value > 0 ? '+' : value < 0 ? '' : '';
    return `${sign}${value.toFixed(2)}${unit}`;
  }

  function formatSignedNoPlus(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 'N/A';
    const sign = numeric < 0 ? '-' : '';
    return `${sign}${Math.abs(numeric).toFixed(2)}${unit}`;
  }

  function formatMagnitude(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    return `${Math.abs(value).toFixed(2)}${unit}`;
  }

  function formatCapLimit(limit, unit, polarity) {
    if (limit == null || Number.isNaN(limit)) return 'N/A';
    const numeric = Number(limit);
    if (!Number.isFinite(numeric)) return 'N/A';
    const sign = polarity === 'negative' ? '-' : '';
    return `${sign}${Math.abs(numeric).toFixed(2)}${unit}`;
  }

  function getBuffSummary(loadout) {
    if (!loadout) return null;
    const weaponEquipEffects = getWeaponEquipEffects(loadout);
    const weaponUseEffects = getWeaponUseEffects(loadout);
    const armorEquipEffects = getArmorEquipEffects(loadout);
    const armorSetEffects = getArmorSetEffects(loadout) || [];
    const clothingEquipEffects = getClothingEquipEffects(loadout);
    const clothingSetEffects = getClothingSetEffects(loadout);
    const petEffect = getActivePetEffect(loadout);
    const consumableList = loadout?.Gear?.Consumables || [];
    const manual = {
      damage: Number(loadout?.Properties?.BonusDamage ?? 0) || 0,
      critChance: Number(loadout?.Properties?.BonusCritChance ?? 0) || 0,
      critDamage: Number(loadout?.Properties?.BonusCritDamage ?? 0) || 0,
      reload: Number(loadout?.Properties?.BonusReload ?? 0) || 0
    };

    const summary = {};
    Object.entries(BUFF_DEFS).forEach(([key, def]) => {
      const weaponValue = sumEffectValues([...weaponEquipEffects, ...weaponUseEffects], def);
      const armorValue = sumEffectValues(armorEquipEffects, def);
      const armorSetValue = sumEffectValues(armorSetEffects, def);
      const clothingValue = sumEffectValues([...clothingEquipEffects, ...clothingSetEffects], def);
      const petValue = petEffect ? sumEffectValues([petEffect], def) : 0;
      const consumableData = maxConsumableEffectValue(consumableList, def);
      const caps = getCapsForBuffKey(key);

      // Limits: Item (equipable + manual), Action (pets + consumables), Total (both combined).
      const itemValue = weaponValue + armorValue + armorSetValue + clothingValue + (manual[key] || 0);
      const actionValue = petValue + (consumableData.value || 0);
      const cappedItem = caps?.item != null ? clamp(itemValue, -caps.item, caps.item) : itemValue;
      const cappedAction = caps?.action != null ? clamp(actionValue, -caps.action, caps.action) : actionValue;
      const combined = cappedItem + cappedAction;
      const total = caps?.total != null ? clamp(combined, -caps.total, caps.total) : combined;

      summary[key] = {
        label: def.label,
        unit: def.unit,
        item: itemValue,
        itemCapped: cappedItem,
        action: actionValue,
        actionCapped: cappedAction,
        total,
        caps,
        manual: manual[key] || 0,
        consumableDetail: consumableData,
        equipmentBreakdown: {
          weapon: weaponValue,
          armor: armorValue,
          armorSet: armorSetValue,
          clothing: clothingValue,
          pet: petValue
        }
      };
    });

    return summary;
  }

  function togglePetEffect(effectKey) {
    if (!loadout?.Gear?.Pet) return;
    loadout.Gear.Pet.Effect = loadout.Gear.Pet.Effect === effectKey ? null : effectKey;
    touchLoadouts();
    markDirty();
  }

  function setClothingSlot(slotName, side, name) {
    if (!loadout?.Gear) return;
    const list = [...(loadout.Gear.Clothing || [])];
    const isRing = isRingSlot(slotName);
    const matchesSlot = (item) => {
      const slotMatches = isRing ? isRingSlot(item?.Slot) : item?.Slot === slotName;
      const sideMatches = side ? item?.Side === side : !item?.Side;
      return slotMatches && sideMatches;
    };
    const nextList = list.filter(item => !matchesSlot(item));
    if (!name) {
      loadout = {
        ...loadout,
        Gear: {
          ...loadout.Gear,
          Clothing: nextList
        }
      };
      touchLoadouts();
      markDirty();
      return;
    }
    const entry = { Slot: isRing ? 'Ring' : slotName, Name: name };
    if (side) entry.Side = side;
    nextList.push(entry);
    loadout = {
      ...loadout,
      Gear: {
        ...loadout.Gear,
        Clothing: nextList
      }
    };
    touchLoadouts();
    markDirty();
  }

  function clamp(value, min, max) {
    return LoadoutCalc.clamp(value, min, max);
  }

  function enforceEnhancerCap(group, key, value) {
    if (!loadout?.Gear) return;
    const target = group === 'weapon'
      ? loadout.Gear.Weapon?.Enhancers
      : loadout.Gear.Armor?.Enhancers;
    if (!target) return;
    const parsed = Number(value);
    const nextValue = Number.isFinite(parsed) ? Math.max(0, Math.min(10, parsed)) : 0;
    target[key] = nextValue;
    const total = Object.values(target).reduce((sum, val) => sum + (Number(val) || 0), 0);
    if (total > 10) {
      const excess = total - 10;
      target[key] = Math.max(0, (Number(target[key]) || 0) - excess);
    }
  }

  function resetArmor() {
    const newArmorObject = () => ({
      Name: null,
      Plate: null
    });

    loadout.Gear.Armor.SetName = null;
    loadout.Gear.Armor.PlateName = null;

    armorSlots.forEach(slot => {
      loadout.Gear.Armor[slot] = newArmorObject();
    });

    touchLoadouts();
    markDirty();
  }

  function clearSlot(e, slot) {
    e.preventDefault();

    if (slot === 'weapon') {
      loadout.Gear.Weapon.Name = null;
      loadout.Gear.Weapon.Amplifier = null;
      loadout.Gear.Weapon.Scope = null;
      loadout.Gear.Weapon.Sight = null;
      loadout.Gear.Weapon.Absorber = null;
      loadout.Gear.Weapon.Matrix = null;
      loadout.Gear.Weapon.Implant = null;
    } else if (slot === 'amplifier') {
      loadout.Gear.Weapon.Amplifier = null;
    } else if (slot === 'scope') {
      loadout.Gear.Weapon.Scope = null;
    } else if (slot === 'sight') {
      loadout.Gear.Weapon.Sight = null;
    } else if (slot === 'absorber') {
      loadout.Gear.Weapon.Absorber = null;
    } else if (slot === 'matrix') {
      loadout.Gear.Weapon.Matrix = null;
    } else if (slot === 'implant') {
      loadout.Gear.Weapon.Implant = null;
    } else if (slot === 'scope-sight') {
      loadout.Gear.Weapon.Scope.Sight = null;
    } else if (slot.startsWith('armor-')) {
      loadout.Gear.Armor[slot.split('-')[1]].Name = null;
      loadout.Gear.Armor[slot.split('-')[1]].Plate = null;
    } else if (slot.startsWith('armorplating-')) {
      loadout.Gear.Armor[slot.split('-')[1]].Plate = null;
    } else if (slot === 'armorplating') {
      loadout.Gear.Armor.PlateName = null;

      armorSlots.forEach(slot => {
        loadout.Gear.Armor[slot].Plate = null;
      });
    } else if (slot === 'armorset') {
      resetArmor();
      return;
    } else if (slot === 'pet') {
      loadout.Gear.Pet = { Name: null, Effect: null };
    } else if (slot === 'ring-left') {
      setClothingSlot('Ring', 'Left', null);
    } else if (slot === 'ring-right') {
      setClothingSlot('Ring', 'Right', null);
    } else if (slot.startsWith('clothing-')) {
      const slotName = slot.replace('clothing-', '');
      setClothingSlot(slotName, null, null);
    }

    touchLoadouts();
    markDirty();
  }

  function getLerpProgress(start, end, current) {
    return LoadoutCalc.getLerpProgress(start, end, current);
  }

  function calcTotalDamage(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);
    const bonusDamagePercent = offensiveTotals?.damage ?? 0;
    
    return LoadoutCalc.calculateTotalDamage(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      bonusDamagePercent,
      amplifier
    );
  }

  function calcEffectiveDamage(loadout) {
    const critChance = calcCritChance(loadout);
    const critDamage = calcCritDamage(loadout);
    const hitAbility = calcHitAbility(loadout);
    const damageInterval = calcDamageInterval(loadout);

    return LoadoutCalc.calculateEffectiveDamage(damageInterval, critChance, critDamage, hitAbility);
  }

  function calcDamageInterval(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const totalDamage = calcTotalDamage(loadout);
    
    return LoadoutCalc.calculateDamageInterval(
      weapon,
      loadout.Skill.Dmg,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0,
      totalDamage
    );
  }

  function calcHitAbility(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    
    return LoadoutCalc.calculateHitAbility(
      weapon,
      loadout.Skill.Hit,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0
    );
  }

  function calcCritChance(loadout) {
    const critAbility = calcCritAbility(loadout);
    const bonusCritChancePercent = offensiveTotals?.critChance ?? 0;
    
    return LoadoutCalc.calculateCritChance(
      critAbility,
      loadout.Gear.Weapon.Enhancers.Accuracy,
      bonusCritChancePercent
    );
  }

  function calcCritAbility(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    
    return LoadoutCalc.calculateCritAbility(
      weapon,
      loadout.Skill.Hit,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0
    );
  }

  function calcCritDamage(loadout) {
    const bonusCritDamagePercent = offensiveTotals?.critDamage ?? 0;
    return LoadoutCalc.calculateCritDamage(bonusCritDamagePercent);
  }

  function calcRange(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    
    return LoadoutCalc.calculateRange(
      weapon,
      loadout.Skill.Hit,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0,
      loadout.Gear.Weapon.Enhancers.Range
    );
  }

  function calcDecay(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const absorber = getAbsorber(loadout.Gear.Weapon.Absorber?.Name);
    const implant = getImplant(loadout.Gear.Weapon.Implant?.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);
    const scope = getScope(loadout.Gear.Weapon.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon.Sight?.Name);
    const matrix = getMatrix(loadout.Gear.Weapon.Matrix?.Name);
    
    return LoadoutCalc.calculateDecay(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy,
      absorber,
      implant,
      amplifier,
      scope,
      scopeSight,
      sight,
      matrix,
      loadout.Markup
    );
  }

  function calcAmmo(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);
    
    return LoadoutCalc.calculateAmmoBurn(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy,
      amplifier
    );
  }

  function calcCost(loadout) {
    const decay = calcDecay(loadout);
    const ammo = calcAmmo(loadout);

    return LoadoutCalc.calculateCost(decay, ammo, loadout.Markup.Ammo ?? 100);
  }

  function calcDpp(loadout) {
    const effectiveDamage = calcEffectiveDamage(loadout);
    const cost = calcCost(loadout);

    return LoadoutCalc.calculateDPP(effectiveDamage, cost);
  }

  function calcReload(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const bonusReloadPercent = offensiveTotals?.reload ?? 0;
    
    return LoadoutCalc.calculateReload(
      weapon,
      loadout.Skill.Hit,
      loadout.Gear.Weapon.Enhancers.SkillMod ?? 0,
      bonusReloadPercent
    );
  }

  function calcDps(loadout) {
    const effectiveDamage = calcEffectiveDamage(loadout);
    const reload = calcReload(loadout);

    return LoadoutCalc.calculateDPS(effectiveDamage, reload);
  }

  function calcWeaponCost(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);

    return LoadoutCalc.calculateWeaponCost(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy
    );
  }

  function calcEfficiency(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const weaponCost = calcWeaponCost(loadout);
    const absorber = getAbsorber(loadout.Gear.Weapon.Absorber?.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);
    const scope = getScope(loadout.Gear.Weapon.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon.Sight?.Name);
    const matrix = getMatrix(loadout.Gear.Weapon.Matrix?.Name);
    
    return LoadoutCalc.calculateEfficiency(
      weapon,
      weaponCost,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy,
      absorber,
      amplifier,
      scope,
      scopeSight,
      sight,
      matrix
    );
  }

  function weightedAverage(weightA, valueA, weightB, valueB) {
    return LoadoutCalc.weightedAverage(weightA, valueA, weightB, valueB);
  }

  function calcArmorDefense(loadout) {
    const armorPieces = armorSlots.map(slot => getArmor(loadout.Gear.Armor[slot].Name));
    
    return LoadoutCalc.calculateArmorDefense(
      armorPieces,
      loadout.Gear.Armor.Enhancers.Defense
    );
  }

  function calcPlateDefense(loadout) {
    const platePieces = armorSlots.map(slot => getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name));
    
    return LoadoutCalc.calculatePlateDefense(platePieces);
  }

  function calcTotalDefense(loadout) {
    const armorDefense = calcArmorDefense(loadout);
    const plateDefense = calcPlateDefense(loadout);
    
    return LoadoutCalc.calculateTotalDefense(armorDefense, plateDefense);
  }

  function calcArmorDurability(loadout) {
    const armorPieces = armorSlots.map(slot => getArmor(loadout.Gear.Armor[slot].Name));
    
    return LoadoutCalc.calculateArmorDurability(
      armorPieces,
      loadout.Gear.Armor.Enhancers.Durability
    );
  }

  function calcPlateDurability(loadout) {
    const platePieces = armorSlots.map(slot => getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name));
    
    return LoadoutCalc.calculatePlateDurability(platePieces);
  }

  function calcTotalAbsorption(loadout) {
    const armorPieces = armorSlots.map(slot => getArmor(loadout.Gear.Armor[slot].Name));
    const platePieces = armorSlots.map(slot => getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name));
    
    return LoadoutCalc.calculateTotalAbsorption(
      armorPieces,
      platePieces,
      loadout.Gear.Armor.Enhancers.Defense,
      loadout.Gear.Armor.Enhancers.Durability
    );
  }

  function getMarkupCost(item, markup) {
    const maxTT = item?.Properties?.Economy?.MaxTT;
    const minTT = item?.Properties?.Economy?.MinTT ?? 0;
    if (maxTT == null || maxTT <= minTT) return null;
    return (maxTT - minTT) * (markup ?? 100) / 100;
  }

  function calcArmorMarkupCost(loadout) {
    if (!loadout?.Markup) return null;
    let total = 0;
    let hasAny = false;
    armorSlots.forEach(slot => {
      const armorName = loadout.Gear.Armor[slot].Name;
      if (!armorName || !isLimitedName(armorName)) return;
      const armor = getArmor(armorName);
      const markup = loadout.Gear.Armor.ManageIndividual
        ? loadout.Markup.Armors[slot]
        : loadout.Markup.ArmorSet;
      const cost = getMarkupCost(armor, markup);
      if (cost == null) return;
      total += cost;
      hasAny = true;
    });
    return hasAny ? total : null;
  }

  function calcPlateMarkupCost(loadout) {
    if (!loadout?.Markup) return null;
    let total = 0;
    let hasAny = false;
    armorSlots.forEach(slot => {
      const plateName = loadout.Gear.Armor[slot].Plate?.Name;
      if (!plateName || !isLimitedName(plateName)) return;
      const plate = getArmorPlating(plateName);
      const markup = loadout.Gear.Armor.ManageIndividual
        ? loadout.Markup.Plates[slot]
        : loadout.Markup.PlateSet;
      const cost = getMarkupCost(plate, markup);
      if (cost == null) return;
      total += cost;
      hasAny = true;
    });
    return hasAny ? total : null;
  }

  function calcBlockChance(loadout) {
    const platePieces = armorSlots.map(slot => getArmorPlating(loadout.Gear.Armor[slot].Plate?.Name));
    
    return LoadoutCalc.calculateBlockChance(platePieces);
  }

  function calcSkillModification(loadout) {
    const scope = getScope(loadout.Gear.Weapon?.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon?.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon?.Sight?.Name);
    
    return LoadoutCalc.calculateSkillModification(scope, scopeSight, sight);
  }

  function calcSkillBonus(loadout) {
    const scope = getScope(loadout.Gear.Weapon?.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon?.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon?.Sight?.Name);
    
    return LoadoutCalc.calculateSkillBonus(scope, scopeSight, sight);
  }

  function calcLowestTotalUses(loadout) {
    const weapon = getWeapon(loadout.Gear.Weapon.Name);
    const absorber = getAbsorber(loadout.Gear.Weapon.Absorber?.Name);
    const implant = getImplant(loadout.Gear.Weapon.Implant?.Name);
    const amplifier = getAmplifier(loadout.Gear.Weapon.Amplifier?.Name);
    const scope = getScope(loadout.Gear.Weapon.Scope?.Name);
    const scopeSight = getSight(loadout.Gear.Weapon.Scope?.Sight?.Name);
    const sight = getSight(loadout.Gear.Weapon.Sight?.Name);
    const matrix = getMatrix(loadout.Gear.Weapon.Matrix?.Name);
    
    return LoadoutCalc.calculateLowestTotalUses(
      weapon,
      loadout.Gear.Weapon.Enhancers.Damage,
      loadout.Gear.Weapon.Enhancers.Economy,
      absorber,
      implant,
      amplifier,
      scope,
      scopeSight,
      sight,
      matrix
    );
  }

  function compareValue(loadout, getter, setter, newObject, valueFunction) {
    let loadoutCopy = JSON.parse(JSON.stringify(loadout));

    console.log(loadoutCopy);

    let currentValue = valueFunction(loadoutCopy);

    console.log('curr: ' + currentValue);

    if (currentValue == null) return null;

    let currentObject = getter(loadoutCopy);

    console.log(currentObject);

    setter(loadoutCopy, newObject);

    console.log(newObject);
    console.log(getter(loadoutCopy));

    let newValue = valueFunction(loadoutCopy);

    console.log('new: ' + newValue);

    if (newValue == null) return null;

    setter(loadoutCopy, currentObject);
    
    console.log(getter(loadoutCopy));

    let difference = newValue - currentValue;

    console.log('diff: ' + difference);

    return difference > 0
      ? `<span style='color: ${$darkMode ? 'lightgreen' : 'darkgreen'};'>+${difference.toFixed(2)}</span>`
      : difference < 0
      ? `<span style='color: ${$darkMode ? '#FF5555' : 'darkred'};'>${difference.toFixed(2)}</span>`
      : difference.toFixed(2);
  }

  function compareEfficiency(loadout, getter, setter, object) {
    return compareValue(loadout, getter, setter, object, calcEfficiency);
  }

  function compareDpp(loadout, getter, setter, object) {
    return compareValue(loadout, getter, setter, object, calcDpp);
  }

  function compareDps(loadout, getter, setter, object) {
    return compareValue(loadout, getter, setter, object, calcDps);
  }

  function buildPickerRows(items, mapper) {
    return (items || []).map(item => ({
      ...mapper(item),
      _item: item
    }));
  }

  function getFilteredAmplifiers() {
    const weapon = getWeapon(loadout?.Gear?.Weapon?.Name);
    if (!weapon) return [];
    return amplifiers.filter(x => {
      const ampDamage = getTotalDamage(x);
      const weaponDamage = getTotalDamage(weapon);

      if (!ampDamage) {
        return false;
      }

      if (2 * ampDamage > (1 + ((settings.overampCap ?? 0) / 100)) * weaponDamage && settings.onlyShowReasonableAmplifiers) {
        return false;
      }

      if (weapon.Properties.Class === 'Ranged') {
        return weapon.Properties.Type === 'BLP'
          ? x.Properties.Type === 'BLP'
          : x.Properties.Type === 'Energy';
      }

      if (weapon.Properties.Class === 'Melee') {
        return x.Properties.Type === 'Melee';
      }

      if (weapon.Properties.Class === 'Mindforce') {
        return x.Properties.Type === 'Mindforce';
      }

      return false;
    });
  }

  function getFilteredImplants() {
    const weapon = getWeapon(loadout?.Gear?.Weapon?.Name);
    return implants.filter(x => {
      return x.Properties.MaxProfessionLevel == null || (
        weapon?.Properties?.Skill?.Hit?.LearningIntervalStart <= x.Properties.MaxProfessionLevel
        && weapon?.Properties?.Skill?.Dmg?.LearningIntervalStart <= x.Properties.MaxProfessionLevel
      );
    });
  }

  function getPickerItemLink(kind, item) {
    if (!item?.Name) return null;
    const slug = encodeURIComponentSafe(item.Name);

    if (kind === 'weapon') return `/items/weapons/${slug}`;
    if (kind === 'pet') return `/items/pets/${slug}`;
    if (kind === 'consumable') return `/items/consumables/${slug}`;
    if (kind === 'armorset') return `/items/armorsets/${slug}`;
    if (kind?.startsWith('armor-')) return `/items/armors/${slug}`;
    if (kind?.startsWith('armorplating')) return `/items/attachments/armorplatings/${slug}`;
    if (kind === 'amplifier' || kind === 'matrix') return `/items/attachments/weaponamplifiers/${slug}`;
    if (kind === 'absorber') return `/items/attachments/absorbers/${slug}`;
    if (kind === 'scope' || kind === 'sight' || kind === 'scope-sight') return `/items/attachments/weaponvisionattachments/${slug}`;
    if (kind === 'implant') return `/items/attachments/mindforceimplants/${slug}`;
    if (kind === 'clothing' || kind?.startsWith('clothing-') || kind === 'ring-left' || kind === 'ring-right') {
      return `/items/clothing/${slug}`;
    }

    return null;
  }

  function getPickerMobileKeys() {
    return ['name'];
  }

  function finalizePickerColumns(kind, columns) {
    const mobileKeys = getPickerMobileKeys(kind);
    let finalized = columns;

    if (isMobileLayout) {
      finalized = columns.filter(column => mobileKeys.includes(column.key));
    } else {
      finalized = columns.map(column => ({
        ...column,
        hideOnMobile: column.hideOnMobile || !mobileKeys.includes(column.key)
      }));
    }

    if (!isMobileLayout) {
      finalized = [
        ...finalized,
        {
          key: 'link',
          header: '',
          width: '42px',
          sortable: false,
          searchable: false,
          formatter: (_value, row) => {
            const href = getPickerItemLink(kind, row?._item);
            if (!href) return '';
            return `<a class="picker-link-btn" href="${href}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" aria-label="Open item in new tab"><svg class="picker-link-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><use href="#icon-external"></use></svg></a>`;
          }
        }
      ];
    }

    return finalized;
  }

  function getPickerConfig(kind) {
    if (!kind) return null;

    if (kind === 'weapon') {
      return {
        title: 'Select Weapon',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'class', header: 'Class', width: '90px' },
          { key: 'type', header: 'Type', width: '90px' },
          { key: 'dps', header: 'DPS', width: '70px' },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(weapons, item => ({
          name: item.Name,
          class: item.Properties.Class,
          type: item.Properties.Type,
          dps: getDps(item) != null ? getDps(item).toFixed(2) : 'N/A',
          dpp: getDpp(item) != null ? getDpp(item).toFixed(2) : 'N/A',
          efficiency: item.Properties?.Economy?.Efficiency != null ? `${item.Properties.Economy.Efficiency.toFixed(1)}%` : 'N/A'
        }))
      };
    }

    if (kind === 'amplifier') {
      return {
        title: 'Select Amplifier',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'damage', header: 'Damage', width: '80px' },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(getFilteredAmplifiers(), item => ({
          name: item.Name,
          damage: compareDps(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, item) ?? 'N/A',
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Amplifier, (x, v) => x.Gear.Weapon.Amplifier = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'absorber') {
      const weapon = getWeapon(loadout?.Gear?.Weapon?.Name);
      return {
        title: 'Select Absorber',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'efficiency', header: 'Efficiency', width: '90px' },
          { key: 'decay', header: 'Decay', width: '90px' },
          { key: 'uses', header: 'Uses', width: '80px' }
        ]),
        rows: buildPickerRows(absorbers, item => ({
          name: item.Name,
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Absorber, (x, v) => x.Gear.Weapon.Absorber = v, item) ?? 'N/A',
          decay: item.Properties?.Economy?.Absorption != null && weapon?.Properties?.Economy?.Decay != null
            ? `${(weapon.Properties.Economy.Decay * item.Properties.Economy.Absorption).toFixed(4)} PEC`
            : 'N/A',
          uses: weapon ? (getTotalAbsorberUses(item, weapon) ?? 'N/A') : 'N/A'
        }))
      };
    }

    if (kind === 'scope') {
      return {
        title: 'Select Scope',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(scopes, item => ({
          name: item.Name,
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'scope-sight') {
      return {
        title: 'Select Scope Sight',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(sights, item => ({
          name: item.Name,
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Scope, (x, v) => x.Gear.Weapon.Scope = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'sight') {
      return {
        title: 'Select Sight',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(sights, item => ({
          name: item.Name,
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Sight, (x, v) => x.Gear.Weapon.Sight = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Sight, (x, v) => x.Gear.Weapon.Sight = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'matrix') {
      return {
        title: 'Select Matrix',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'dps', header: 'DPS', width: '70px' },
          { key: 'dpp', header: 'DPP', width: '70px' },
          { key: 'efficiency', header: 'Efficiency', width: '90px' }
        ]),
        rows: buildPickerRows(matrices, item => ({
          name: item.Name,
          dps: compareDps(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, item) ?? 'N/A',
          dpp: compareDpp(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, item) ?? 'N/A',
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Matrix, (x, v) => x.Gear.Weapon.Matrix = v, item) ?? 'N/A'
        }))
      };
    }

    if (kind === 'implant') {
      const weapon = getWeapon(loadout?.Gear?.Weapon?.Name);
      return {
        title: 'Select Implant',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'efficiency', header: 'Efficiency', width: '90px' },
          { key: 'decay', header: 'Decay', width: '90px' },
          { key: 'uses', header: 'Uses', width: '80px' }
        ]),
        rows: buildPickerRows(getFilteredImplants(), item => ({
          name: item.Name,
          efficiency: compareEfficiency(loadout, x => x.Gear.Weapon.Implant, (x, v) => x.Gear.Weapon.Implant = v, item) ?? 'N/A',
          decay: item.Properties?.Economy?.Absorption != null && weapon?.Properties?.Economy?.Decay != null
            ? `${(weapon.Properties.Economy.Decay * item.Properties.Economy.Absorption).toFixed(4)} PEC`
            : 'N/A',
          uses: weapon ? (getTotalAbsorberUses(item, weapon) ?? 'N/A') : 'N/A'
        }))
      };
    }

    if (kind === 'armorset') {
      return {
        title: 'Select Armor Set',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'total', header: 'Total Def', width: '90px' },
          { key: 'durability', header: 'Durability', width: '100px' }
        ]),
        rows: buildPickerRows(armorsets, item => ({
          name: item.Name,
          total: getTotalDefense(item) ?? 'N/A',
          durability: item.Properties.Economy.Durability ?? 'N/A'
        }))
      };
    }

    if (kind.startsWith('armor-')) {
      const slot = kind.split('-')[1];
      return {
        title: `Select ${slot} Armor`,
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'total', header: 'Total Def', width: '90px' },
          { key: 'durability', header: 'Durability', width: '100px' }
        ]),
        rows: buildPickerRows(armors.filter(x => x.Properties.Slot === slot), item => ({
          name: item.Name,
          total: getTotalDefense(item) ?? 'N/A',
          durability: item.Properties.Economy.Durability ?? 'N/A'
        }))
      };
    }

    if (kind.startsWith('armorplating')) {
      return {
        title: 'Select Armor Plating',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'total', header: 'Total Def', width: '90px' },
          { key: 'durability', header: 'Durability', width: '100px' }
        ]),
        rows: buildPickerRows(armorplatings, item => ({
          name: item.Name,
          total: getTotalDefense(item) ?? 'N/A',
          durability: item.Properties.Economy.Durability ?? 'N/A'
        }))
      };
    }

    if (kind === 'pet') {
      return {
        title: 'Select Pet',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'type', header: 'Type', width: '120px' },
          { key: 'level', header: 'Level', width: '70px' }
        ]),
        rows: buildPickerRows(pets, item => ({
          name: item.Name,
          type: item.Properties?.Type ?? 'N/A',
          level: item.Properties?.Level ?? 'N/A'
        }))
      };
    }

    if (kind === 'clothing') {
      const availableClothing = clothing.filter(item => {
        const slotName = getClothingItemSlot(item);
        return slotName
          && slotName !== 'Unknown'
          && !isRingSlot(slotName)
          && hasClothingEffects(item);
      });
      return {
        title: 'Select Clothing',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'slot', header: 'Slot', width: '120px' },
          { key: 'effects', header: 'Effects', width: '110px' }
        ]),
        rows: buildPickerRows(availableClothing, item => {
          const slotName = getClothingItemSlot(item);
          const effectCount = getClothingEffectCount(item);
          return {
            name: item.Name,
            slot: slotName,
            effects: formatEffectCount(effectCount)
          };
        })
      };
    }

    if (kind === 'consumable') {
      const availableConsumables = stimulants.filter(item => hasConsumableEffects(item));
      return {
        title: 'Select Consumable',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'type', header: 'Type', width: '140px' },
          { key: 'effects', header: 'Effects', width: '110px' }
        ]),
        rows: buildPickerRows(availableConsumables, item => ({
          name: item.Name,
          type: item.Properties?.Type ?? 'N/A',
          effects: formatEffectCount(getConsumableEffectCount(item))
        }))
      };
    }

    if (kind === 'ring-left' || kind === 'ring-right') {
      const side = kind === 'ring-left' ? 'Left' : 'Right';
      const filteredRings = ringItems.filter(item => getRingSide(getClothingItemSlot(item)) === side);
      return {
        title: 'Select Ring',
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'slot', header: 'Slot', width: '120px' },
          { key: 'type', header: 'Type', width: '120px' }
        ]),
        rows: buildPickerRows(filteredRings, item => ({
          name: item.Name,
          slot: item.Properties?.Slot ?? 'N/A',
          type: item.Properties?.Type ?? 'N/A'
        }))
      };
    }

    if (kind.startsWith('clothing-')) {
      const slotName = kind.replace('clothing-', '');
      return {
        title: `Select ${slotName}`,
        columns: finalizePickerColumns(kind, [
          { key: 'name', header: 'Name', main: true },
          { key: 'slot', header: 'Slot', width: '120px' },
          { key: 'type', header: 'Type', width: '120px' }
        ]),
        rows: buildPickerRows(clothing.filter(x => x.Properties?.Slot === slotName), item => ({
          name: item.Name,
          slot: item.Properties?.Slot ?? 'N/A',
          type: item.Properties?.Type ?? 'N/A'
        }))
      };
    }

    return null;
  }

  function stripHtml(value) {
    return String(value ?? '')
      .replace(/<[^>]*>/g, '')
      .replace(/&nbsp;/g, ' ')
      .trim();
  }

  function getPickerPreviewTitle(row) {
    if (!row) return '';
    const name = row.name ?? row.Name ?? row._item?.Name;
    return stripHtml(name) || 'Selected Item';
  }

  function formatStatValue(value, suffix = '') {
    if (value == null || value === 'N/A' || Number.isNaN(value)) return 'N/A';
    const numeric = typeof value === 'number';
    let base = value;
    if (numeric) {
      const rounded = Math.abs(value - Math.round(value)) < 0.01;
      base = rounded ? Math.round(value).toString() : value.toFixed(2);
    }
    return `${base}${suffix}`;
  }

  function getEffectUnit(effectName, currentEffect = null) {
    if (effectName && effectsCatalog?.length) {
      const match = effectsCatalog.find(effect => effect.Name === effectName);
      if (match?.Properties?.Unit) return match.Properties.Unit;
    }
    return currentEffect?.Values?.Unit || currentEffect?.Properties?.Unit || '';
  }

  function getItemEffectGroups(item) {
    if (!item) return [];
    const groups = [];
    const equip = item.EffectsOnEquip || item.Properties?.EffectsOnEquip || [];
    const use = item.EffectsOnUse || item.Properties?.EffectsOnUse || [];
    const consume = item.EffectsOnConsume || item.Properties?.EffectsOnConsume || [];
    const setEffects = item.EffectsOnSetEquip || item.Set?.EffectsOnSetEquip || item.Properties?.Set?.EffectsOnSetEquip || [];
    const generic = item.Effects || item.Properties?.Effects || [];

    if (equip.length) groups.push({ title: 'Effects on Equip', effects: equip, effectType: 'equip' });
    if (use.length) groups.push({ title: 'Effects on Use', effects: use, effectType: 'use' });
    if (consume.length) groups.push({ title: 'Effects on Consume', effects: consume, effectType: 'consume' });
    if (setEffects.length) groups.push({ title: 'Set Effects', effects: setEffects, effectType: 'equip' });
    if (generic.length) groups.push({ title: 'Effects', effects: generic, effectType: 'equip' });

    return groups;
  }

  function addPreviewRow(rows, label, value, suffix = '') {
    const formatted = formatStatValue(value, suffix);
    if (formatted === 'N/A') return;
    rows.push({ label, value: formatted });
  }

  function addPreviewTextRow(rows, label, value) {
    if (value == null || value === 'N/A' || value === '') return;
    rows.push({ label, value });
  }

  function formatNutrioValue(value, suffix) {
    if (value == null || Number.isNaN(value)) return null;
    return `${(value / 100).toFixed(2)} ${suffix}`;
  }

  function getDefenseBreakdownRows(item) {
    const defense = item?.Properties?.Defense || {};
    const mapping = [
      ['Impact', defense.Impact],
      ['Cut', defense.Cut],
      ['Stab', defense.Stab],
      ['Pen', defense.Penetration],
      ['Shr', defense.Shrapnel],
      ['Burn', defense.Burn],
      ['Cold', defense.Cold],
      ['Acid', defense.Acid],
      ['Elec', defense.Electric]
    ];
    return mapping
      .filter(([, value]) => value != null && value !== 0)
      .map(([label, value]) => ({ label, value: formatStatValue(value) }));
  }

  function getPickerPreviewSections(kind, item, row) {
    const sections = [];
    if (!item) return sections;

    if (kind === 'weapon') {
      const rows = [];
      addPreviewRow(rows, 'Class', item.Properties?.Class);
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      addPreviewRow(rows, 'Total Damage', getTotalDamage(item));
      addPreviewRow(rows, 'DPS', getDps(item));
      addPreviewRow(rows, 'DPP', getDpp(item));
      addPreviewRow(rows, 'Efficiency', item.Properties?.Economy?.Efficiency, '%');
      addPreviewRow(rows, 'Range', item.Properties?.Range, 'm');
      addPreviewRow(rows, 'Uses', getTotalUses(item));
      sections.push({ title: 'Weapon Stats', rows });
    } else if (kind === 'amplifier' || kind === 'matrix' || kind === 'scope' || kind === 'sight' || kind === 'scope-sight' || kind === 'absorber' || kind === 'implant') {
      const rows = [];
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      addPreviewRow(rows, 'DPP', row?.dpp && stripHtml(row.dpp) !== 'N/A' ? parseFloat(stripHtml(row.dpp)) : null);
      addPreviewRow(rows, 'Efficiency', row?.efficiency && stripHtml(row.efficiency) !== 'N/A' ? parseFloat(stripHtml(row.efficiency)) : null, '%');
      if (row?.decay) addPreviewRow(rows, 'Decay', stripHtml(row.decay));
      if (row?.uses) addPreviewRow(rows, 'Uses', stripHtml(row.uses));
      sections.push({ title: 'Attachment Stats', rows });
    } else if (kind === 'armorset' || kind.startsWith('armor-') || kind.startsWith('armorplating')) {
      const rows = [];
      const defenseRows = getDefenseBreakdownRows(item);
      if (defenseRows.length > 0) {
        sections.push({ title: 'Defense Types', rows: defenseRows });
      }
      addPreviewRow(rows, 'Total Defense', getTotalDefense(item));
      addPreviewRow(rows, 'Block', item.Properties?.Defense?.Block, '%');
      addPreviewRow(rows, 'Durability', item.Properties?.Economy?.Durability);
      sections.push({ title: 'Armor Stats', rows });
    } else if (kind === 'pet') {
      const rows = [];
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      addPreviewRow(rows, 'Rarity', item.Properties?.Rarity);
      addPreviewRow(rows, 'Training', item.Properties?.TrainingDifficulty);
      addPreviewRow(rows, 'Taming Level', item.Properties?.TamingLevel);
      addPreviewRow(rows, 'Exportable', item.Properties?.ExportableLevel != null ? `Lv ${item.Properties.ExportableLevel}` : null);
      addPreviewTextRow(rows, 'Nutrio Capacity', formatNutrioValue(item.Properties?.NutrioCapacity, 'PED'));
      addPreviewTextRow(rows, 'Nutrio Consumption', formatNutrioValue(item.Properties?.NutrioConsumptionPerHour, 'PED/h'));
      sections.push({ title: 'Pet Stats', rows, compact: true });

      const skills = Array.isArray(item.Effects) ? item.Effects : [];
      const petEffects = skills
        .filter(skill => skill?.Name)
        .map(skill => ({
          Name: skill.Name,
          Values: {
            Strength: skill?.Properties?.Strength ?? skill?.Values?.Strength ?? skill?.Values?.Value ?? 0,
            Unit: getEffectUnit(skill.Name, skill)
          }
        }));

      if (petEffects.length > 0) {
        sections.push({
          title: 'Pet Skills',
          rows: [],
          effectsGroups: [{ title: '', effects: petEffects, effectType: 'equip' }],
          compact: true,
          hideEffectTitle: true
        });
      }
    } else if (kind === 'consumable') {
      const rows = [];
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      addPreviewRow(rows, 'Effects', getConsumableEffectCount(item));
      sections.push({ title: 'Consumable Stats', rows });
    } else if (kind === 'clothing' || kind === 'ring-left' || kind === 'ring-right' || kind?.startsWith('clothing-')) {
      const rows = [];
      addPreviewRow(rows, 'Slot', getClothingItemSlot(item));
      addPreviewRow(rows, 'Type', item.Properties?.Type);
      addPreviewRow(rows, 'Effects', getClothingEffectCount(item));
      sections.push({ title: 'Clothing Stats', rows });
    }

    if (kind !== 'pet') {
      const effectGroups = getItemEffectGroups(item);
      if (effectGroups.length > 0) {
        sections.push({ title: 'Effects', rows: [], effectsGroups: effectGroups });
      }
    }

    if (sections.length === 0 && row && pickerConfig) {
      const rows = pickerConfig.columns
        .filter(column => column.key !== 'name' && column.key !== 'link' && column.header)
        .map(column => {
          const rawValue = row[column.key];
          const value = stripHtml(rawValue);
          return {
            label: column.header,
            value: value || 'N/A'
          };
        });
      sections.push({ title: 'Details', rows });
    }

    return sections;
  }

  // Gets the set effects of all equipped armors
  function getArmorSetEffects(loadout) {
    if (!loadout.Gear.Armor.ManageIndividual && loadout.Gear.Armor.SetName) {
      return getActiveArmorSetEffects(loadout.Gear.Armor.SetName) || [];
    }
    else if (loadout.Gear.Armor.ManageIndividual) {
      let sets = [];

      armorSlots.forEach(slot => {
        let armor = getArmor(loadout.Gear.Armor[slot].Name);

        if (armor == null || armor.Set == null) return;

        sets.push(armor.Set);
      });

      return sets
        .filter((value, index, self) => self.indexOf(value) === index)
        .flatMap(set => getActiveArmorSetEffects(set.Name) || []);
    }
  }

  // Gets the amount of pieces equipped of a specific set
  function getArmorSetPieceCount(setName) {
    return armorSlots.reduce((acc, slot) => acc + (getArmor(loadout.Gear.Armor[slot].Name)?.Set.Name === setName ? 1 : 0), 0);
  }

  // Gets the active set effects of a specific set
  function getActiveArmorSetEffects(setName) {
    let set = getArmorSet(setName);
    let setPieceCount = getArmorSetPieceCount(setName);

    if (!set || !set.EffectsOnSetEquip) return [];

    // Get unique effects with the highest piece count that is less than or equal to the current piece count
    return set.EffectsOnSetEquip
      .filter(effect => (effect?.MinSetPieces ?? effect?.Values?.MinSetPieces ?? 0) <= setPieceCount)
      .sort((a, b) => (b?.MinSetPieces ?? b?.Values?.MinSetPieces ?? 0) - (a?.MinSetPieces ?? a?.Values?.MinSetPieces ?? 0))
      .filter((value, index, self) => self.findIndex(effect => effect.Name === value.Name) === index);
  }

  function getWeaponUseEffects(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return [];

    return [
      ...weapon.EffectsOnUse,
      ...(loadout.Gear.Weapon.Amplifier?.Name != null ? getAmplifier(loadout.Gear.Weapon.Amplifier.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Scope?.Name != null ? getScope(loadout.Gear.Weapon.Scope.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Scope?.Sight?.Name != null ? getSight(loadout.Gear.Weapon.Scope.Sight.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Sight?.Name != null ? getSight(loadout.Gear.Weapon.Sight.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Matrix?.Name != null ? getMatrix(loadout.Gear.Weapon.Matrix.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Implant?.Name != null ? getImplant(loadout.Gear.Weapon.Implant.Name).EffectsOnUse ?? [] : []),
      ...(loadout.Gear.Weapon.Absorber?.Name != null ? getAbsorber(loadout.Gear.Weapon.Absorber.Name).EffectsOnUse ?? [] : [])
    ];
  }

  function getWeaponEquipEffects(loadout) {
    let weapon = getWeapon(loadout.Gear.Weapon.Name);

    if (weapon == null) return [];

    return [
      ...(weapon.EffectsOnEquip ?? []),
      ...(loadout.Gear.Weapon.Amplifier?.Name != null ? getAmplifier(loadout.Gear.Weapon.Amplifier.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Scope?.Name != null ? getScope(loadout.Gear.Weapon.Scope.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Scope?.Sight?.Name != null ? getSight(loadout.Gear.Weapon.Scope.Sight.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Sight?.Name != null ? getSight(loadout.Gear.Weapon.Sight.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Matrix?.Name != null ? getMatrix(loadout.Gear.Weapon.Matrix.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Implant?.Name != null ? getImplant(loadout.Gear.Weapon.Implant.Name).EffectsOnEquip ?? [] : []),
      ...(loadout.Gear.Weapon.Absorber?.Name != null ? getAbsorber(loadout.Gear.Weapon.Absorber.Name).EffectsOnEquip ?? [] : [])
    ];
  }

  function getArmorEquipEffects(loadout) {
    return armorSlots.flatMap(slot => {
      let armor = getArmor(loadout.Gear.Armor[slot].Name);

      if (armor == null) return [];

      return [
        ...(armor.EffectsOnEquip ?? []),
        ...(loadout.Gear.Armor[slot].Plate?.Name != null ? getArmorPlating(loadout.Gear.Armor[slot].Plate.Name).EffectsOnEquip ?? [] : [])
      ];
    });
  }
</script>



<svelte:head>
  <title>Entropia Nexus - Loadout Manager</title>
  <meta name="description" content="Tool for managing and comparing different combinations of weapons, armor, clothing, pets and pills and comparing them to each other.">
  <meta name="keywords" content="Weapon Compare, Weapon, Compare, Calculator, Loadouts, Manager, Loadout Manager, Entropia Universe, Entropia, Entropia Nexus, EU, PE, Items, Mobs, Maps, Tools, MindArk, Wiki">
  <link rel="canonical" href="https://entropianexus.com/tools/loadouts" />
</svelte:head>

<svelte:window bind:innerWidth={windowWidth} />

<svg class="icon-sprite" aria-hidden="true">
  <symbol id="icon-plus" viewBox="0 0 24 24">
    <path d="M12 5v14M5 12h14" />
  </symbol>
  <symbol id="icon-compare" viewBox="0 0 24 24">
    <path d="M4 7h11l-3-3M20 17H9l3 3" />
    <path d="M14 4l-3 3 3 3M10 20l3-3-3-3" />
  </symbol>
  <symbol id="icon-cancel" viewBox="0 0 24 24">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </symbol>
  <symbol id="icon-save" viewBox="0 0 24 24">
    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
    <path d="M17 21V13H7v8" />
    <path d="M7 3v5h8" />
  </symbol>
  <symbol id="icon-share" viewBox="0 0 24 24">
    <path d="M4 12v7a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-7" />
    <path d="M12 3v12" />
    <path d="M8 7l4-4 4 4" />
  </symbol>
  <symbol id="icon-external" viewBox="0 0 24 24">
    <path d="M14 3h7v7" />
    <path d="M10 14L21 3" />
    <path d="M21 14v7h-7" />
    <path d="M3 10V3h7" />
  </symbol>
  <symbol id="icon-local" viewBox="0 0 24 24">
    <path d="M4 20h16" />
    <path d="M7 20V8l5-4 5 4v12" />
  </symbol>
  <symbol id="icon-info" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="9" />
    <path d="M12 10v6M12 7h.01" />
  </symbol>
  <symbol id="icon-stats" viewBox="0 0 24 24">
    <path d="M4 20V10" />
    <path d="M10 20V4" />
    <path d="M16 20v-6" />
    <path d="M2 20h20" />
  </symbol>
  <symbol id="icon-settings" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </symbol>
  <symbol id="icon-weapon" viewBox="0 0 24 24">
    <path d="M3 21l7-7M7 21l7-7" />
    <path d="M14 3l7 7M10 7l7 7" />
  </symbol>
  <symbol id="icon-armor" viewBox="0 0 24 24">
    <path d="M12 3l7 3v6c0 5-3.5 8-7 9-3.5-1-7-4-7-9V6l7-3z" />
  </symbol>
  <symbol id="icon-accessories" viewBox="0 0 24 24">
    <circle cx="12" cy="12" r="7" />
    <circle cx="12" cy="12" r="3" />
  </symbol>
</svg>

<WikiPage
  title="Loadouts"
  {breadcrumbs}
  entity={loadout || { Name: 'Loadouts' }}
  basePath="/tools/loadouts"
  navItems={[]}
  {user}
  editable={false}
  canEdit={false}
>
  <div slot="header-actions" class="loadout-header-actions">
    <button
      class="action-btn create"
      on:click={handleNewLoadout}
      disabled={entitiesLoading}
      aria-label="New loadout"
      title="New loadout"
    >
      <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <use href="#icon-plus"></use>
      </svg>
      <span class="action-label">New</span>
    </button>
    {#if activeSource === 'online'}
      <button
        class="action-btn save"
        class:dirty={isDirty}
        on:click={handleManualSave}
        disabled={!loadout || isSaving || !isDirty}
        aria-label={isSaving ? 'Saving...' : (isDirty ? 'Save loadout' : 'Saved')}
        title={isSaving ? 'Saving...' : (isDirty ? 'Save' : 'Saved')}
      >
        <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <use href="#icon-save"></use>
        </svg>
        <span class="action-label">Save</span>
        {#if autosaveSeconds != null && isDirty}
          <span class="save-countdown">{autosaveSeconds}s</span>
        {/if}
      </button>
    {:else}
      <button class="action-btn local" disabled title="Saved locally" aria-label="Saved locally">
        <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <use href="#icon-local"></use>
        </svg>
        <span class="action-label">Local</span>
      </button>
    {/if}
    {#if loadout}
      {#if compareMode}
        <button
          class="action-btn cancel"
          on:click={() => {
            compareMode = false;
            activeMobilePanel = 'weapons';
          }}
          aria-label="Stop comparing"
          title="Stop comparing"
        >
          <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <use href="#icon-cancel"></use>
          </svg>
          <span class="action-label">Stop</span>
        </button>
      {:else}
        <button
          class="action-btn"
          on:click={() => {
            compareMode = true;
            activeMobilePanel = 'weapons';
          }}
          aria-label="Compare loadouts"
          title="Compare"
        >
          <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <use href="#icon-compare"></use>
          </svg>
          <span class="action-label">Compare</span>
        </button>
      {/if}
    {/if}
    {#if activeSource === 'online'}
      <button
        class="action-btn share"
        class:public={isPublicLoadout && !!loadout}
        on:click={openShareDialog}
        disabled={!loadout}
        aria-label="Share loadout"
        title={isPublicLoadout ? 'Public link enabled' : 'Share'}
      >
        <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <use href="#icon-share"></use>
        </svg>
        <span class="action-label">Share</span>
      </button>
    {/if}
  </div>

  <div slot="sidebar" let:isMobile>
    <div class="loadout-sidebar" class:mobile={isMobile}>
      <div class="sidebar-header">
        <div class="sidebar-title">Loadouts</div>
        <div class="sidebar-toggle">
          <button
            class:active={activeSource === 'online'}
            disabled={!isLoggedIn}
            title={!isLoggedIn ? 'Log in to use online loadouts' : 'Online loadouts'}
            on:click={() => switchSource('online')}
          >Online</button>
          <button
            class:active={activeSource === 'local'}
            on:click={() => switchSource('local')}
          >Local</button>
        </div>
      </div>
      <div class="sidebar-search">
        <input type="text" placeholder="Search loadouts..." bind:value={loadoutSearch} />
      </div>
      <div class="sidebar-actions">
        <button class="sidebar-btn danger" on:click={deleteActiveLoadout} disabled={!loadout}>Delete</button>
        <button class="sidebar-btn neutral" on:click={exportActiveLoadout} disabled={!loadout}>Export</button>
        <button class="sidebar-btn accent" on:click={openImportSourceDialog}>Import</button>
      </div>
      <input type="file" bind:this={fileInput} on:change={handleFileChange} class="file-input-hidden" />
      {#if activeSource === 'online' && onlineLoading}
        <div class="sidebar-status">Loading online loadouts...</div>
      {:else if activeSource === 'online' && onlineError}
        <div class="sidebar-status error">{onlineError}</div>
      {/if}
      <div class="sidebar-list">
        {#if filteredLoadouts.length === 0}
          <div class="sidebar-empty">No loadouts found.</div>
        {:else}
          {#each filteredLoadouts as item}
            <button
              class="sidebar-item"
              class:active={item.id === activeLoadoutKey}
              on:click={() => setActiveLoadout(item.data)}
            >
              <span class="item-name">{getLoadoutListLabel(item.data)}</span>
              {#if activeSource === 'online'}
                {@const record = onlineLoadouts.find(r => r.id === item.id)}
                <span
                  class="item-visibility"
                  title={record?.public ? 'Public loadout' : 'Private loadout'}
                >
                  {#if record?.public}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M12 5c4.5 0 7.5 3.5 9 7-1.5 3.5-4.5 7-9 7s-7.5-3.5-9-7c1.5-3.5 4.5-7 9-7z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  {:else}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <rect x="4" y="11" width="16" height="9" rx="2" ry="2" />
                      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                    </svg>
                  {/if}
                </span>
              {/if}
            </button>
          {/each}
        {/if}
      </div>
    </div>
  </div>

  <div class="layout-a">
    {#if isMobileLayout}
      <div class="mobile-panel-overview">
        <div class="mobile-panel-track">
          {#each mobilePanelItems as panel, index}
            <button
              class="mobile-panel-button"
              class:active={activeMobilePanel === panel.key}
              class:disabled={compareMode && panel.key !== 'weapons'}
              on:click={() => setMobilePanelIndex(index)}
              disabled={compareMode && panel.key !== 'weapons'}
              aria-label={panel.label}
              title={panel.label}
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <use href={`#${panel.icon}`}></use>
              </svg>
              <span>{panel.label}</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}

    <div
      class="mobile-panels"
      bind:this={mobilePanelsEl}
      on:touchstart={handleTouchStart}
      on:touchmove={handleTouchMove}
      on:touchend={handleTouchEnd}
    >
      <div
        class="mobile-panels-track"
        class:swiping={swipeActive}
        style={`transform: ${mobilePanelTranslate};`}
      >
    <aside class="loadout-sidebar-float">
      <div class="mobile-panel" class:active={activeMobilePanel === 'info'}>
        <div class="loadout-infobox-card" on:input|capture={markDirty} on:change|capture={markDirty}>
        <div class="infobox-header">
          {#if loadout}
            <input class="infobox-name-input" type="text" bind:value={loadout.Name} placeholder="Loadout name" />
          {:else}
            <div class="infobox-title">Select a loadout</div>
          {/if}
        </div>
        {#if loadout}
          <div class="stats-section tier-1">
            <div class="stat-row primary">
              <span class="stat-label">Efficiency</span>
              <span class="stat-value">{calcEfficiency(loadout) != null ? `${calcEfficiency(loadout).toFixed(1)}%` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">DPS</span>
              <span class="stat-value">{calcDps(loadout) != null ? `${calcDps(loadout).toFixed(4)}` : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">DPP</span>
              <span class="stat-value">{calcDpp(loadout) != null ? `${calcDpp(loadout).toFixed(4)}` : 'N/A'}</span>
            </div>
          </div>
          <div class="stats-section buff-summary">
            <h4 class="section-title">Active Effects</h4>
            {#if offensiveEffects.length === 0 && defensiveEffects.length === 0 && utilityEffects.length === 0}
              <div class="buff-empty">No effects are active</div>
            {:else}
              {#if offensiveEffects.length > 0}
                <div class="buff-panel">
                  <div class="buff-panel-title">Offensive Effects</div>
                  <ul class="effects-list">
                    {#each offensiveEffects as effect}
                      {@const hasCaps = !!(effect?.caps?.item || effect?.caps?.action || effect?.caps?.total)}
                      {@const effectKey = `${effect.name}::${effect.unit}`}
                      {@const expanded = expandedEffectKeys.has(effectKey)}
                      {@const totalBase = (effect?.cappedItem ?? 0) + (effect?.cappedAction ?? 0) + (effect?.rawBonus ?? 0)}
                      {#if hasCaps}
                        <li>
                          <button type="button" class="effect-item equip effect-toggle" class:open={expanded} on:click={() => toggleEffectExpanded(effectKey)}>
                              <span class="effect-name">{effect.name}</span>
                              <span class="effect-details">
                                <span
                                  class="effect-value"
                                  class:positive={effect.polarity === 'positive'}
                                  class:negative={effect.polarity === 'negative'}
                                >
                                  {#if effect.cappedAny}[{/if}{formatMagnitude(effect.signedTotal, effect.unit)}{#if effect.cappedAny}]{/if}
                                </span>
                              </span>
                          </button>
                          {#if expanded}
                            <div class="cap-breakdown" in:slide={{ duration: 180 }} out:slide={{ duration: 160 }}>
                              <div class="cap-breakdown-inner">
                                {#if effect?.caps?.item}
                                  <div class="cap-row">
                                    <span class="cap-label">Item</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawItem ?? 0) > effect.caps.item}>{formatSignedNoPlus(effect.rawItem ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.item, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.action}
                                  <div class="cap-row">
                                    <span class="cap-label">Action</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawAction ?? 0) > effect.caps.action}>{formatSignedNoPlus(effect.rawAction ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.action, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.total}
                                  <div class="cap-row">
                                    <span class="cap-label">Total</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(totalBase) > effect.caps.total}>{formatSignedNoPlus(totalBase, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.total, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                              </div>
                            </div>
                          {/if}
                        </li>
                      {:else}
                        <li class="effect-item equip">
                          <span class="effect-name">{effect.name}</span>
                          <span class="effect-details">
                            <span
                              class="effect-value"
                              class:positive={effect.polarity === 'positive'}
                              class:negative={effect.polarity === 'negative'}
                            >
                              {formatMagnitude(effect.signedTotal, effect.unit)}
                            </span>
                          </span>
                        </li>
                      {/if}
                    {/each}
                  </ul>
                </div>
              {/if}
              {#if defensiveEffects.length > 0}
                <div class="buff-panel">
                  <div class="buff-panel-title">Defensive Effects</div>
                  <ul class="effects-list">
                    {#each defensiveEffects as effect}
                      {@const hasCaps = !!(effect?.caps?.item || effect?.caps?.action || effect?.caps?.total)}
                      {@const effectKey = `${effect.name}::${effect.unit}`}
                      {@const expanded = expandedEffectKeys.has(effectKey)}
                      {@const totalBase = (effect?.cappedItem ?? 0) + (effect?.cappedAction ?? 0) + (effect?.rawBonus ?? 0)}
                      {#if hasCaps}
                        <li>
                          <button type="button" class="effect-item equip effect-toggle" class:open={expanded} on:click={() => toggleEffectExpanded(effectKey)}>
                              <span class="effect-name">{effect.name}</span>
                              <span class="effect-details">
                                <span
                                  class="effect-value"
                                  class:positive={effect.polarity === 'positive'}
                                  class:negative={effect.polarity === 'negative'}
                                >
                                  {#if effect.cappedAny}[{/if}{formatMagnitude(effect.signedTotal, effect.unit)}{#if effect.cappedAny}]{/if}
                                </span>
                              </span>
                          </button>
                          {#if expanded}
                            <div class="cap-breakdown" in:slide={{ duration: 180 }} out:slide={{ duration: 160 }}>
                              <div class="cap-breakdown-inner">
                                {#if effect?.caps?.item}
                                  <div class="cap-row">
                                    <span class="cap-label">Item</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawItem ?? 0) > effect.caps.item}>{formatSignedNoPlus(effect.rawItem ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.item, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.action}
                                  <div class="cap-row">
                                    <span class="cap-label">Action</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawAction ?? 0) > effect.caps.action}>{formatSignedNoPlus(effect.rawAction ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.action, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.total}
                                  <div class="cap-row">
                                    <span class="cap-label">Total</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(totalBase) > effect.caps.total}>{formatSignedNoPlus(totalBase, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.total, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                              </div>
                            </div>
                          {/if}
                        </li>
                      {:else}
                        <li class="effect-item equip">
                          <span class="effect-name">{effect.name}</span>
                          <span class="effect-details">
                            <span
                              class="effect-value"
                              class:positive={effect.polarity === 'positive'}
                              class:negative={effect.polarity === 'negative'}
                            >
                              {formatMagnitude(effect.signedTotal, effect.unit)}
                            </span>
                          </span>
                        </li>
                      {/if}
                    {/each}
                  </ul>
                </div>
              {/if}
              {#if utilityEffects.length > 0}
                <div class="buff-panel">
                  <div class="buff-panel-title">Utility Effects</div>
                  <ul class="effects-list">
                    {#each utilityEffects as effect}
                      {@const hasCaps = !!(effect?.caps?.item || effect?.caps?.action || effect?.caps?.total)}
                      {@const effectKey = `${effect.name}::${effect.unit}`}
                      {@const expanded = expandedEffectKeys.has(effectKey)}
                      {@const totalBase = (effect?.cappedItem ?? 0) + (effect?.cappedAction ?? 0) + (effect?.rawBonus ?? 0)}
                      {#if hasCaps}
                        <li>
                          <button type="button" class="effect-item equip effect-toggle" class:open={expanded} on:click={() => toggleEffectExpanded(effectKey)}>
                              <span class="effect-name">{effect.name}</span>
                              <span class="effect-details">
                                <span
                                  class="effect-value"
                                  class:positive={effect.polarity === 'positive'}
                                  class:negative={effect.polarity === 'negative'}
                                >
                                  {#if effect.cappedAny}[{/if}{formatMagnitude(effect.signedTotal, effect.unit)}{#if effect.cappedAny}]{/if}
                                </span>
                              </span>
                          </button>
                          {#if expanded}
                            <div class="cap-breakdown" in:slide={{ duration: 180 }} out:slide={{ duration: 160 }}>
                              <div class="cap-breakdown-inner">
                                {#if effect?.caps?.item}
                                  <div class="cap-row">
                                    <span class="cap-label">Item</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawItem ?? 0) > effect.caps.item}>{formatSignedNoPlus(effect.rawItem ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.item, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.action}
                                  <div class="cap-row">
                                    <span class="cap-label">Action</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(effect.rawAction ?? 0) > effect.caps.action}>{formatSignedNoPlus(effect.rawAction ?? 0, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.action, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                                {#if effect?.caps?.total}
                                  <div class="cap-row">
                                    <span class="cap-label">Total</span>
                                    <span class="cap-metric">
                                      <span class:cap-over={Math.abs(totalBase) > effect.caps.total}>{formatSignedNoPlus(totalBase, effect.unit)}</span>/<span>{formatCapLimit(effect.caps.total, effect.unit, effect.polarity)}</span>
                                    </span>
                                  </div>
                                {/if}
                              </div>
                            </div>
                          {/if}
                        </li>
                      {:else}
                        <li class="effect-item equip">
                          <span class="effect-name">{effect.name}</span>
                          <span class="effect-details">
                            <span
                              class="effect-value"
                              class:positive={effect.polarity === 'positive'}
                              class:negative={effect.polarity === 'negative'}
                            >
                              {formatMagnitude(effect.signedTotal, effect.unit)}
                            </span>
                          </span>
                        </li>
                      {/if}
                    {/each}
                  </ul>
                </div>
              {/if}
            {/if}
          </div>
          <div class="stats-section">
            <h4 class="section-title">Offense</h4>
            <div class="stat-row"><span class="stat-label">Total Damage</span><span class="stat-value">{calcTotalDamage(loadout) != null ? `${calcTotalDamage(loadout).toFixed(2)}` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Range</span><span class="stat-value">{calcRange(loadout) != null ? `${calcRange(loadout).toFixed(1)}m` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Critical Chance</span><span class="stat-value">{calcCritChance(loadout) != null ? `${(calcCritChance(loadout) * 100).toFixed(1)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Critical Damage</span><span class="stat-value">{calcCritDamage(loadout) != null ? `${(calcCritDamage(loadout) * 100).toFixed(0)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Effective Damage</span><span class="stat-value">{calcEffectiveDamage(loadout) != null ? `${calcEffectiveDamage(loadout).toFixed(2)}` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Reload</span><span class="stat-value">{calcReload(loadout) != null ? `${calcReload(loadout).toFixed(2)}s` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Uses/min</span><span class="stat-value">{calcReload(loadout) != null ? `${clampDecimals(60 / calcReload(loadout), 0, 2)}` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Economy</h4>
            <div class="stat-row"><span class="stat-label">Decay</span><span class="stat-value">{calcDecay(loadout) != null ? `${calcDecay(loadout).toFixed(4)} PEC` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Ammo</span><span class="stat-value">{calcAmmo(loadout) != null ? Math.round(calcAmmo(loadout)) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Cost</span><span class="stat-value">{calcCost(loadout) != null ? `${calcCost(loadout).toFixed(4)} PEC` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Uses</span><span class="stat-value">{calcLowestTotalUses(loadout) != null ? calcLowestTotalUses(loadout) : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Defense</h4>
            <div class="stat-row"><span class="stat-label">Armor Defense</span><span class="stat-value">{calcArmorDefense(loadout) != null ? calcArmorDefense(loadout).toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Plate Defense</span><span class="stat-value">{calcPlateDefense(loadout) != null ? calcPlateDefense(loadout).toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Defense</span><span class="stat-value">{calcTotalDefense(loadout) != null ? calcTotalDefense(loadout).toFixed(2) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Block</span><span class="stat-value">{calcBlockChance(loadout) != null ? `${calcBlockChance(loadout).toFixed(1)}%` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Armor Economy</h4>
            <div class="stat-row"><span class="stat-label">Armor Durability</span><span class="stat-value">{calcArmorDurability(loadout) != null ? calcArmorDurability(loadout) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Plate Durability</span><span class="stat-value">{calcPlateDurability(loadout) != null ? calcPlateDurability(loadout) : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Total Absorption</span><span class="stat-value">{calcTotalAbsorption(loadout) != null ? `${calcTotalAbsorption(loadout).toFixed(0)} HP` : 'N/A'}</span></div>
          </div>
          <div class="stats-section">
            <h4 class="section-title">Skill</h4>
            <div class="stat-row"><span class="stat-label">Hit Ability</span><span class="stat-value">{calcHitAbility(loadout) != null ? `${calcHitAbility(loadout).toFixed(1)}/10.0` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Crit Ability</span><span class="stat-value">{calcCritAbility(loadout) != null ? `${calcCritAbility(loadout).toFixed(1)}/10.0` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Skill Modification</span><span class="stat-value">{calcSkillModification(loadout) != null ? `${calcSkillModification(loadout).toFixed(1)}%` : 'N/A'}</span></div>
            <div class="stat-row"><span class="stat-label">Skill Bonus</span><span class="stat-value">{calcSkillBonus(loadout) != null ? `${calcSkillBonus(loadout).toFixed(1)}%` : 'N/A'}</span></div>
          </div>
        {:else}
          <div class="stats-empty">Select a loadout to view stats.</div>
        {/if}
        </div>
      </div>
      {#if loadout}
        <div class="mobile-panel" class:active={activeMobilePanel === 'settings'}>
          <div class="loadout-settings-panel" on:input|capture={markDirty} on:change|capture={markDirty}>
            <DataSection title="Settings" collapsible={false}>
              <div class="settings-grid">
                <div class="settings-group-title">Profession Levels</div>
                <div class="settings-divider" aria-hidden="true"></div>
                <div class="setting-row">
                  <label>Hit Profession</label>
                  <input type="number" bind:value={loadout.Skill.Hit} />
                </div>
                <div class="setting-row">
                  <label>Dmg Profession</label>
                  <input type="number" bind:value={loadout.Skill.Dmg} />
                </div>
                <div class="settings-group-title">Bonus Stats</div>
                <div class="settings-divider" aria-hidden="true"></div>
                <div class="setting-row">
                  <label>% Damage</label>
                  <input type="number" bind:value={loadout.Properties.BonusDamage} />
                </div>
                <div class="setting-row">
                  <label>% Crit Chance</label>
                  <input type="number" bind:value={loadout.Properties.BonusCritChance} />
                </div>
                <div class="setting-row">
                  <label>% Crit Damage</label>
                  <input type="number" bind:value={loadout.Properties.BonusCritDamage} />
                </div>
                <div class="setting-row">
                  <label>% Reload</label>
                  <input type="number" bind:value={loadout.Properties.BonusReload} />
                </div>
              </div>
            </DataSection>
          </div>
        </div>
      {/if}
    </aside>

    <article class="wiki-article loadout-article" on:input|capture={markDirty} on:change|capture={markDirty}>
      {#if $loading || entitiesLoading}
        <div class="loading-text">Loading game data...</div>
      {:else if loadout != null}
        {#if saveError}
          <div class="save-status error">{saveError}</div>
        {/if}

        <div class="mobile-panel" class:active={activeMobilePanel === 'weapons'}>
          {#if compareMode}
          <DataSection title="Compare Loadouts" collapsible={false}>
            <div class="compare-table">
              <Table
                style="height: 360px; white-space: nowrap; text-overflow: ellipsis; overflow-x: auto;"
                header={{ 
                  values: [
                    'Name',
                    'DPS',
                    'Total Dmg',
                    'Effective Dmg',
                    'Reload',
                    'Range',
                    'Efficiency',
                    'Decay',
                    'Ammo',
                    'Cost',
                    'DPP',
                    'Skill Mod',
                    'Skill Bonus',
                    'Block',
                    'Tot. Defense',
                  ],
                  widths: ['1fr', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content', 'max-content']
                }}
                data={
                  loadouts.map(x => ({
                    values: [
                      x.Name,
                      calcDps(x) != null ? calcDps(x).toFixed(4) : null,
                      calcTotalDamage(x) != null ? calcTotalDamage(x).toFixed(2) : null,
                      calcEffectiveDamage(x) != null ? calcEffectiveDamage(x).toFixed(2) : null,
                      calcReload(x) != null ? `${calcReload(x).toFixed(2)}s` : null,
                      calcRange(x) != null ? `${calcRange(x).toFixed(2)}m` : null,
                      calcEfficiency(x) != null ? `${calcEfficiency(x).toFixed(1)}%` : null,
                      calcDecay(x) != null ? `${calcDecay(x).toFixed(2)} PEC` : null,
                      calcAmmo(x) != null ? calcAmmo(x).toFixed(2) : null,
                      calcCost(x) != null ? `${calcCost(x).toFixed(2)} PEC` : null,
                      calcDpp(x) != null ? calcDpp(x).toFixed(4) : null,
                      calcSkillModification(x) != null ? `${calcSkillModification(x).toFixed(1)}%` : null,
                      calcSkillBonus(x) != null ? `${calcSkillBonus(x).toFixed(1)}%` : null,
                      calcBlockChance(x) != null ? `${calcBlockChance(x).toFixed(1)}%` : null,
                      calcTotalDefense(x) != null ? calcTotalDefense(x).toFixed(0) : null,
                    ]
                  }))
                }
                options={{
                  searchable: true,
                  virtual: true
                }} />
            </div>
          </DataSection>
        {:else}
          <DataSection title="Weapons">
            <div class="panel-grid two-col">
              <div class="panel-block">
                <h3 class="panel-title">Weapon & Attachments</h3>
                <div class="form-grid">
                  <div class="form-label">Weapon</div>
                  <div class="control-row">
                    <button class="slot select-button" on:contextmenu={e => clearSlot(e, "weapon")} on:click={() => openPicker('weapon')}>
                      {#if loadout?.Gear.Weapon.Name != null}
                        {loadout.Gear.Weapon.Name}
                      {:else}
                        <span class="placeholder-text">Select a weapon...</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Weapon.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Weapon} />
                      </div>
                    {/if}
                  </div>
                  <div class="form-label">Amplifier</div>
                  <div class="control-row">
                    <button class="slot select-button" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "amplifier")} on:click={() => openPicker('amplifier')}>
                      {#if loadout?.Gear.Weapon.Name != null}
                        {#if loadout?.Gear.Weapon.Amplifier?.Name != null}
                          {loadout.Gear.Weapon.Amplifier.Name}
                        {:else}
                          <span class="placeholder-text">Select an amplifier...</span>
                        {/if}
                      {:else}
                        <span class="placeholder-muted">Choose a weapon first</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Weapon.Amplifier?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Amplifier} />
                      </div>
                    {/if}
                  </div>
                  <div class="form-label">Absorber</div>
                  <div class="control-row">
                    <button class="slot select-button" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "absorber")} on:click={() => openPicker('absorber')}>
                      {#if loadout?.Gear.Weapon.Name != null}
                        {#if loadout?.Gear.Weapon.Absorber?.Name != null}
                          {loadout.Gear.Weapon.Absorber.Name}
                        {:else}
                          <span class="placeholder-text">Select an absorber...</span>
                        {/if}
                      {:else}
                        <span class="placeholder-muted">Choose a weapon first</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Weapon.Absorber?.Name)}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Absorber} />
                      </div>
                    {/if}
                  </div>
                  {#if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Ranged'}
                    <div class="form-label">Scope</div>
                    <div class="control-row">
                      <button class="slot select-button" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "scope")} on:click={() => openPicker('scope')}>
                        {#if loadout?.Gear.Weapon.Scope?.Name != null}
                          {loadout.Gear.Weapon.Scope.Name}
                        {:else}
                          <span class="placeholder-text">Select a scope...</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Scope?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Scope} />
                        </div>
                      {/if}
                    </div>
                    <div class="form-label sub-label">
                      <span class="branch-icon" aria-hidden="true">
                        <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                          <path d="M2 2v4a2 2 0 0 0 2 2h6" />
                          <path d="M8 6l2 2-2 2" />
                        </svg>
                      </span>
                      <span>Scope Sight</span>
                    </div>
                    <div class="control-row scope-sight-row">
                      <button class="slot select-button" disabled={loadout?.Gear.Weapon.Scope == null} on:contextmenu={e => clearSlot(e, "scope-sight")} on:click={() => openPicker('scope-sight')}>
                        {#if loadout.Gear.Weapon.Scope != null}
                          {#if loadout?.Gear.Weapon.Scope?.Sight?.Name != null}
                            {loadout.Gear.Weapon.Scope.Sight.Name}
                          {:else}
                            <span class="placeholder-text">Select a sight...</span>
                          {/if}
                        {:else}
                          <span class="placeholder-muted">Add a scope first</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Scope?.Sight?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.ScopeSight} />
                        </div>
                      {/if}
                    </div>
                    <div class="form-label">Sight</div>
                    <div class="control-row">
                      <button class="slot select-button" disabled={loadout?.Gear.Weapon.Name == null} on:contextmenu={e => clearSlot(e, "sight")} on:click={() => openPicker('sight')}>
                        {#if loadout?.Gear.Weapon.Sight?.Name != null}
                          {loadout.Gear.Weapon.Sight.Name}
                        {:else}
                          <span class="placeholder-text">Select a sight...</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Sight?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Sight} />
                        </div>
                      {/if}
                    </div>
                  {:else if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Melee'}
                    <div class="form-label">Matrix</div>
                    <div class="control-row">
                      <button class="slot select-button" disabled={getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class !== 'Melee'} on:contextmenu={e => clearSlot(e, "matrix")} on:click={() => openPicker('matrix')}>
                        {#if loadout?.Gear.Weapon.Matrix?.Name != null}
                          {loadout.Gear.Weapon.Matrix.Name}
                        {:else}
                          <span class="placeholder-text">Select a matrix...</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Matrix?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Matrix} />
                        </div>
                      {/if}
                    </div>
                  {:else if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Mindforce'}
                    <div class="form-label">Implant</div>
                    <div class="control-row">
                      <button class="slot select-button" disabled={getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class !== 'Mindforce'} on:contextmenu={e => clearSlot(e, "weapon")} on:click={() => openPicker('implant')}>
                        {#if getWeapon(loadout.Gear.Weapon.Name)?.Properties?.Class === 'Mindforce'}
                          {#if loadout?.Gear.Weapon.Implant?.Name != null}
                            {loadout.Gear.Weapon.Implant.Name}
                          {:else}
                            <span class="placeholder-text">Select an implant...</span>
                          {/if}
                        {:else}
                          <span class="placeholder-muted">Choose a Mindforce weapon</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Weapon.Implant?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Implant} />
                        </div>
                      {/if}
                    </div>
                  {/if}
                  <div class="form-label">Ammo</div>
                  <div class="control-row">
                    {#if loadout?.Gear.Weapon.Name == null}
                      <span class="placeholder-muted">Choose a weapon first</span>
                    {:else}
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Ammo} />
                      </div>
                    {/if}
                  </div>
                </div>
                <button class="reset-btn compact" on:click={resetMarkup}>Reset all markup</button>
              </div>
              <div class="panel-block">
                <h3 class="panel-title">Enhancers & Options</h3>
                <div class="enhancer-grid">
                  <div class="enhancer-field">
                    <label>Damage</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.Damage}
                      on:input={(e) => enforceEnhancerCap('weapon', 'Damage', e.target.value)}
                    />
                  </div>
                  <div class="enhancer-field">
                    <label>Accuracy</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.Accuracy}
                      on:input={(e) => enforceEnhancerCap('weapon', 'Accuracy', e.target.value)}
                    />
                  </div>
                  <div class="enhancer-field">
                    <label>Range</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.Range}
                      on:input={(e) => enforceEnhancerCap('weapon', 'Range', e.target.value)}
                    />
                  </div>
                  <div class="enhancer-field">
                    <label>Economy</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.Economy}
                      on:input={(e) => enforceEnhancerCap('weapon', 'Economy', e.target.value)}
                    />
                  </div>
                  <div class="enhancer-field">
                    <label>Skill Mod</label>
                    <input
                      type="number"
                      min="0"
                      max="10"
                      bind:value={loadout.Gear.Weapon.Enhancers.SkillMod}
                      on:input={(e) => enforceEnhancerCap('weapon', 'SkillMod', e.target.value)}
                    />
                  </div>
                </div>
                <div class="panel-divider compact"></div>
                <div class="option-row">
                  <label class="checkbox-row">
                    <input type="checkbox" bind:checked={settings.onlyShowReasonableAmplifiers} />
                    <span>Include overcapped amplifiers up to</span>
                  </label>
                  <div class="option-input">
                    <input class="compact-input" type="number" min="0" max="100" bind:value={settings.overampCap} />
                    <span class="suffix">%</span>
                  </div>
                </div>
              </div>
            </div>
          </DataSection>
          {/if}
        </div>
        {#if !compareMode}
          <div class="mobile-panel" class:active={activeMobilePanel === 'armor'}>
            <DataSection title="Armor">
              <div class="panel-grid two-col">
              <div class="panel-block">
                <h3 class="panel-title">Armor Selection</h3>
                {#if loadout.Gear.Armor.ManageIndividual}
                  <div class="armor-grid">
                    <div class="armor-grid-header">Slot</div>
                    <div class="armor-grid-header">Armor</div>
                    <div class="armor-grid-header">Armor MU</div>
                    <div class="armor-grid-header">Plate</div>
                    <div class="armor-grid-header">Plate MU</div>
                    {#each armorSlots as slot}
                      <div class="armor-label">{slot}</div>
                      <button class="slot select-button" on:contextmenu={e => clearSlot(e, `armor-${slot}`)} on:click={() => openPicker(`armor-${slot}`)}>
                        {#if loadout?.Gear.Armor[slot].Name != null}
                          {loadout.Gear.Armor[slot].Name}
                        {:else}
                          <span class="placeholder-text">Select armor...</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Armor[slot].Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Armors[slot]} />
                        </div>
                      {:else}
                        <span class="placeholder-muted"></span>
                      {/if}
                      <button class="slot select-button" disabled={loadout?.Gear.Armor[slot].Name == null} on:contextmenu={e => clearSlot(e, `armorplating-${slot}`)} on:click={() => openPicker(`armorplating-${slot}`)}>
                        {#if loadout?.Gear.Armor[slot].Name != null}
                          {#if loadout?.Gear.Armor[slot].Plate?.Name != null}
                            {loadout.Gear.Armor[slot].Plate.Name}
                          {:else}
                            <span class="placeholder-text">Select plating...</span>
                          {/if}
                        {:else}
                          <span class="placeholder-muted">Choose armor first</span>
                        {/if}
                      </button>
                      {#if isLimitedName(loadout?.Gear.Armor[slot].Plate?.Name)}
                        <div class="markup-field">
                          <span class="markup-label">MU%</span>
                          <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.Plates[slot]} />
                        </div>
                      {:else}
                        <span class="placeholder-muted"></span>
                      {/if}
                    {/each}
                  </div>
                {:else}
                  <div class="form-grid">
                    <div class="form-label">Armor Set</div>
                    <button class="slot select-button" on:contextmenu={e => clearSlot(e, "armorset")} on:click={() => openPicker('armorset')}>
                      {#if loadout?.Gear.Armor.SetName != null}
                        {loadout.Gear.Armor.SetName}
                      {:else}
                        <span class="placeholder-text">Select an armor set...</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Armor.SetName)}
                      <div class="form-label">Armor Markup</div>
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.ArmorSet} />
                      </div>
                    {/if}
                    <div class="form-label">Plate Set</div>
                    <button class="slot select-button" disabled={loadout?.Gear.Armor.SetName == null} on:contextmenu={e => clearSlot(e, "armorplating")} on:click={() => openPicker('armorplating')}>
                      {#if loadout?.Gear.Armor.SetName != null}
                        {#if loadout?.Gear.Armor.PlateName != null}
                          {loadout.Gear.Armor.PlateName}
                        {:else}
                          <span class="placeholder-text">Select plating...</span>
                        {/if}
                      {:else}
                        <span class="placeholder-muted">Choose armor set first</span>
                      {/if}
                    </button>
                    {#if isLimitedName(loadout?.Gear.Armor.PlateName)}
                      <div class="form-label">Plate Markup</div>
                      <div class="markup-field">
                        <span class="markup-label">MU%</span>
                        <input class="markup-input" type="number" min="0" step="0.01" bind:value={loadout.Markup.PlateSet} />
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>
              <div class="panel-block">
                <h3 class="panel-title">Enhancers & Options</h3>
                <div class="enhancer-grid">
                <div class="enhancer-field">
                  <label>Defense</label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    bind:value={loadout.Gear.Armor.Enhancers.Defense}
                    on:input={(e) => enforceEnhancerCap('armor', 'Defense', e.target.value)}
                  />
                </div>
                <div class="enhancer-field">
                  <label>Durability</label>
                  <input
                    type="number"
                    min="0"
                    max="10"
                    bind:value={loadout.Gear.Armor.Enhancers.Durability}
                    on:input={(e) => enforceEnhancerCap('armor', 'Durability', e.target.value)}
                  />
                </div>
                </div>
                <label class="checkbox-row">
                  <input type="checkbox" bind:checked={loadout.Gear.Armor.ManageIndividual} />
                  <span>Manage armor pieces individually</span>
                </label>
              </div>
              </div>
            </DataSection>
          </div>
          <div class="mobile-panel" class:active={activeMobilePanel === 'accessories'}>
            <DataSection title="Accessories & Buffs">
              <div class="accessory-panel">
                <div class="accessory-section">
                  <h3 class="panel-title">Rings & Pet</h3>
                  <div class="accessory-grid rings-pet-grid">
                    <div class="accessory-item">
                      <div class="form-label">Left Ring</div>
                      <button class="slot select-button" on:contextmenu={e => clearSlot(e, 'ring-left')} on:click={() => openPicker('ring-left')}>
                        {#if leftRing?.Name}
                          {leftRing.Name}
                        {:else}
                          <span class="placeholder-text">Select ring...</span>
                        {/if}
                      </button>
                    </div>
                    <div class="accessory-item">
                      <div class="form-label">Right Ring</div>
                      <button class="slot select-button" on:contextmenu={e => clearSlot(e, 'ring-right')} on:click={() => openPicker('ring-right')}>
                        {#if rightRing?.Name}
                          {rightRing.Name}
                        {:else}
                          <span class="placeholder-text">Select ring...</span>
                        {/if}
                      </button>
                    </div>
                    <div class="accessory-item pet-select">
                      <div class="form-label">Pet</div>
                      <button
                        class="slot select-button"
                        class:pet-active={!!loadout?.Gear?.Pet?.Name}
                        on:contextmenu={e => clearSlot(e, 'pet')}
                        on:click={() => openPicker('pet')}
                      >
                        {#if loadout?.Gear?.Pet?.Name}
                          {loadout.Gear.Pet.Name}
                        {:else}
                          <span class="placeholder-text">Select pet...</span>
                        {/if}
                      </button>
                    </div>
                  </div>
                  <div class="pet-abilities">
                    {#if !loadout?.Gear?.Pet?.Name}
                      <div class="pet-abilities-empty">Select a pet to view abilities.</div>
                    {:else if activePetEffects.length === 0}
                      <div class="pet-abilities-empty">No abilities available for this pet.</div>
                    {:else}
                      <div class="pet-effect-grid">
                        {#each activePetEffects as effect, index}
                          {@const effectName = effect?.Name || `Effect ${index + 1}`}
                          {@const strength = getPetEffectStrength(effect)}
                          {@const unit = effect?.Properties?.Unit || ''}
                          {@const upkeep = effect?.Properties?.NutrioConsumptionPerHour}
                          {@const level = effect?.Properties?.Unlock?.Level}
                          {@const effectKey = `${effectName}::${strength ?? 0}`}
                          <button
                            class="pet-effect-card"
                            class:active={loadout?.Gear?.Pet?.Effect === effectKey || loadout?.Gear?.Pet?.Effect === effectName}
                            disabled={!loadout?.Gear?.Pet?.Name}
                            on:click={() => togglePetEffect(effectKey)}
                          >
                            <div class="pet-effect-name">{effectName}</div>
                            <div class="pet-effect-meta">
                              <div class="pet-effect-stat">
                                <span class="pet-effect-label">Strength</span>
                                <span class="pet-effect-value">{strength != null ? `${strength}${unit}` : '—'}</span>
                              </div>
                              <div class="pet-effect-stat">
                                <span class="pet-effect-label">Upkeep</span>
                                <span class="pet-effect-value">{upkeep != null ? `${upkeep}/h` : 'N/A'}</span>
                              </div>
                              <div class="pet-effect-stat">
                                <span class="pet-effect-label">Unlock</span>
                                <span class="pet-effect-value">{level != null ? `Lv ${level}` : '—'}</span>
                              </div>
                            </div>
                          </button>
                        {/each}
                      </div>
                    {/if}
                  </div>
                </div>
                <div class="accessory-section">
                  <div class="accessory-section-header">
                    <h3 class="panel-title">Clothing</h3>
                    <button class="add-accessory" on:click={() => openPicker('clothing')}>Add Clothing</button>
                  </div>
                  <div class="clothing-hint">Slots are unique. Picking a piece for an occupied slot replaces it.</div>
                  {#if clothingReplaceNotice}
                    <div class="clothing-warning">{clothingReplaceNotice}</div>
                  {/if}
                  {#if selectedClothing.length === 0}
                    <div class="clothing-empty">No clothing selected yet.</div>
                  {:else}
                    <div class="clothing-list">
                      {#each selectedClothing as entry}
                        {@const item = getClothingItem(entry.Name)}
                        <div class="clothing-item">
                          <div class="clothing-main">
                            <div class="clothing-name">{entry.Name}</div>
                            <div class="clothing-meta">
                              <span class="clothing-slot">{entry.Slot}</span>
                              <span class="clothing-effects">{getClothingEffectLabel(item)}</span>
                            </div>
                          </div>
                          <button class="clothing-remove" on:click={() => removeClothingItem(entry.Name, entry.Slot)}>Remove</button>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
                <div class="accessory-section">
                  <div class="accessory-section-header">
                    <h3 class="panel-title">Consumables</h3>
                    <button class="add-accessory" on:click={() => openPicker('consumable')}>Add Consumable</button>
                  </div>
                  <div class="clothing-hint">Only the strongest consumable effect per type is applied.</div>
                  {#if selectedConsumables.length === 0}
                    <div class="clothing-empty">No consumables selected yet.</div>
                  {:else}
                    <div class="clothing-list">
                      {#each selectedConsumables as entry}
                        {@const entryName = entry?.Name || entry}
                        {@const item = getConsumableItem(entryName)}
                        <div class="clothing-item">
                          <div class="clothing-main">
                            <div class="clothing-name">{entryName}</div>
                            <div class="clothing-meta">
                              <span class="clothing-slot">{item?.Properties?.Type ?? 'Consumable'}</span>
                              <span class="clothing-effects">{formatEffectCount(getConsumableEffectCount(item))}</span>
                            </div>
                          </div>
                          <button class="clothing-remove" on:click={() => removeConsumableItem(entryName)}>Remove</button>
                        </div>
                      {/each}
                    </div>
                  {/if}
                </div>
              </div>
            </DataSection>
          </div>
        {/if}

      {:else}
        <div class="info">
          <h2>Loadout Manager</h2>
          <p>Create or select an existing loadout on the left.</p>
          <p class="instructions">
            Instructions:<br />
            <br />
            - Click "New" to get started.<br />
            - Left-click to select gear.<br />
            - Right-click to clear a slot.<br />
            - Use the Settings panel to adjust skills and bonuses.<br />
            - Compare loadouts with the Compare button in Weapons.<br />
            <br />
            Local loadouts remain until you clear browser storage. Export them if you want a backup.
          </p>
        </div>
      {/if}
    </article>
      </div>
    </div>
  </div>
</WikiPage>

{#if showPickerDialog && pickerConfig}
  <div class="dialog-backdrop picker-backdrop" on:click={closePicker} on:keydown={(e) => e.key === 'Escape' && closePicker()}>
    <div class="dialog picker-dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="picker-dialog-title">
      <div class="dialog-header">
        <h3 id="picker-dialog-title">{pickerConfig.title}</h3>
        <button class="close-btn" on:click={closePicker} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="dialog-body picker-content">
        {#if showPickerPreview && pickerPreviewRow}
          {@const previewLink = getPickerItemLink(activePicker, pickerPreviewItem)}
          {@const previewSections = getPickerPreviewSections(activePicker, pickerPreviewItem, pickerPreviewRow)}
          <div class="picker-preview">
            <div class="picker-preview-header">
              <div class="picker-preview-title">{getPickerPreviewTitle(pickerPreviewRow)}</div>
              {#if previewLink && !isMobileLayout}
                <a class="picker-preview-link" href={previewLink} target="_blank" rel="noopener noreferrer">Open item</a>
              {/if}
            </div>
            <div class="picker-preview-sections">
              {#each previewSections as section}
                <div class="picker-preview-section" class:compact={section.compact}>
                  <div class="picker-preview-section-title">{section.title}</div>
                  {#if section.rows?.length}
                    <div class="picker-preview-grid">
                      {#each section.rows as info}
                      <div class="picker-preview-label stat-label">{info.label}</div>
                      <div class="picker-preview-value stat-value">{info.value}</div>
                      {/each}
                    </div>
                  {/if}
                  {#if section.effectsGroups?.length}
                    <div class:effects-compact={section.compact} class:effects-hide-title={section.hideEffectTitle}>
                      {#each section.effectsGroups as group}
                        <EffectsEditor
                          effects={group.effects}
                          availableEffects={effectsCatalog}
                          effectType={group.effectType}
                          title={group.title}
                          showEmpty={false}
                        />
                      {/each}
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {:else}
          <div class="picker-table">
            <FancyTable
              columns={pickerConfig.columns}
              data={pickerConfig.rows}
              rowHeight={pickerRowHeight}
              pageSize={60}
              searchable={true}
              sortable={true}
              stickyHeader={true}
              emptyMessage="No items found"
              on:rowClick={handlePickerRowClick}
            />
          </div>
        {/if}
      </div>
      {#if showPickerPreview && pickerPreviewRow}
        <div class="dialog-footer">
          <button class="dialog-btn secondary" on:click={returnToPickerList}>Back</button>
          <button class="dialog-btn" on:click={confirmPickerSelection}>Select</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

{#if showImportSourceDialog}
  <div class="dialog-backdrop" on:click={() => showImportSourceDialog = false} on:keydown={(e) => e.key === 'Escape' && (showImportSourceDialog = false)}>
    <div class="dialog dialog-compact" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="import-source-title">
      <div class="dialog-header">
        <h3 id="import-source-title">Import Loadout</h3>
        <button class="close-btn" on:click={() => showImportSourceDialog = false} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="dialog-body">
        <p class="share-hint">File imports are saved locally.</p>
        {#if !isLoggedIn}
          <p class="share-hint">Log in to import local loadouts to your account.</p>
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" on:click={() => showImportSourceDialog = false}>Close</button>
        {#if isLoggedIn}
          <button class="dialog-btn secondary" on:click={handleImportLocal} disabled={localLoadouts.length === 0}>
            Import local ({localLoadouts.length})
          </button>
        {/if}
        <button class="dialog-btn" on:click={handleImportFromFile}>Import from file</button>
      </div>
    </div>
  </div>
{/if}



{#if showShareDialog}
  <div class="dialog-backdrop" on:click={() => showShareDialog = false} on:keydown={(e) => e.key === 'Escape' && (showShareDialog = false)}>
    <div class="dialog dialog-compact" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="share-dialog-title">
      <div class="dialog-header">
        <h3 id="share-dialog-title">Share Loadout</h3>
        <button class="close-btn" on:click={() => showShareDialog = false} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="dialog-body">
        <label class="toggle-row">
          <input type="checkbox" bind:checked={sharePublic} on:change={handleShareToggle} />
          <span>Public link</span>
        </label>
        {#if sharePublic}
          <div class="share-link-row">
            <input type="text" readonly value={shareLink} />
            <button
              type="button"
              class="btn-copy"
              on:click={() => shareLink && navigator.clipboard?.writeText(shareLink)}
              disabled={!shareLink}
            >Copy</button>
          </div>
        {:else}
          <p class="share-hint">Enable public link to generate a shareable URL.</p>
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" on:click={() => showShareDialog = false}>Cancel</button>
        <button class="dialog-btn" on:click={applyShareSettings} disabled={!loadout}>Ok</button>
      </div>
    </div>
  </div>
{/if}

{#if showImportDialog}
  <div class="dialog-backdrop" on:click={() => showImportDialog = false} on:keydown={(e) => e.key === 'Escape' && (showImportDialog = false)}>
    <div class="dialog dialog-compact" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="import-dialog-title">
      <div class="dialog-header">
        <h3 id="import-dialog-title">Import Local Loadouts</h3>
        <button class="close-btn" on:click={() => showImportDialog = false} aria-label="Close dialog">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="dialog-body">
        {#if importSuccess}
          <p>Import completed. Your local loadouts have been moved online.</p>
        {:else}
          <p>Import {localLoadouts.length} local loadout(s) into your account?</p>
          <p class="share-hint">This will clear your local list after a successful import.</p>
          {#if importError}
            <p class="dialog-error">{importError}</p>
          {/if}
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" on:click={() => showImportDialog = false} disabled={importInProgress}>Close</button>
        {#if !importSuccess}
          <button class="dialog-btn" on:click={importLocalLoadouts} disabled={importInProgress || localLoadouts.length === 0}>
            {importInProgress ? 'Importing...' : 'Import'}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

