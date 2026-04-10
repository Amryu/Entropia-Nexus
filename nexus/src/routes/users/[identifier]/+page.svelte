<script>
  // @ts-nocheck
  import { untrack } from 'svelte';
  import { browser } from '$app/environment';
  import { slide } from 'svelte/transition';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import DefenseGridEdit from '$lib/components/wiki/DefenseGridEdit.svelte';
  import ImageUploadDialog from '$lib/components/wiki/ImageUploadDialog.svelte';
  import LoadoutCompactEmbed from '$lib/components/LoadoutCompactEmbed.svelte';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { clampDecimals, encodeURIComponentSafe, getTypeLink } from '$lib/util';
  import { isPercentMarkupType, PLATE_SET_SIZE } from '$lib/common/itemTypes.js';
  import { PROFILE_TABS } from '$lib/constants.js';
  import { formatMarkupValue } from '../../market/exchange/orderUtils';
  import { getItemCategoryPath } from '$lib/market/categorize.js';
  import { loadLoadoutEntities } from '$lib/utils/entityLoader';
  import { evaluateLoadout } from '$lib/utils/loadoutEvaluator';
  import { buildEffectCaps } from '$lib/utils/loadoutEffects';
  import { TYPE_FILTERS } from '$lib/data/globals-constants.js';
  import { formatPed, formatPedShort, timeAgo, sortedData, toggleSort, sortIcon } from '$lib/utils/globalsFormat.js';


  let { data } = $props();

  // Track the profile ID to detect when we navigate to a different profile
  let currentProfileId = $state(null);



  let isEditing = $state(false);
  let saveError = $state('');
  let saveStatus = $state('');
  let tabInitialized = $state(false);
  let imageFailed = $state(false);
  let bannerFailed = $state(false);
  let backgroundFailed = $state(false);
  let showImageDialog = $state(false);
  let showBannerDialog = $state(false);
  let showBackgroundDialog = $state(false);
  let showSocietyDialog = $state(false);
  let societyMode = $state('join');
  let societySearchQuery = $state('');
  let societySearchResults = $state([]);
  let societySearchLoading = $state(false);
  let societySearchError = $state('');
  let societyCreateName = $state('');
  let societyCreateAbbr = $state('');
  let societyCreateDescription = $state('');
  let societyCreateDiscord = $state('');
  let societyActionError = $state('');
  let societyActionStatus = $state('');
  let societySearchTimeout = null;

  let discordFlash = $state(false);
  function copyDiscordName() {
    if (!profile?.socialDiscord) return;
    navigator.clipboard.writeText(profile.socialDiscord);
    discordFlash = true;
    setTimeout(() => { discordFlash = false; }, 600);
  }

  function youtubeUrl(name) {
    if (!name) return '';
    // Channel IDs start with UC
    if (name.startsWith('UC') && name.length >= 20) return `https://youtube.com/channel/${name}`;
    return `https://youtube.com/@${name}`;
  }

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const isRingSlot = (slot) => /ring|finger/i.test(slot || '');

  let avatarDetailTab = $state('Stats');
  let avatarTabsInitialized = $state(false);
  let referenceLoading = $state(false);
  let referenceError = $state('');
  let referenceReady = $state(false);
  let showcaseRecord = $derived(avatar?.showcaseLoadout || null);
  let showcaseLoadout = $state(null);
  let showcaseShareCode = $derived(showcaseRecord?.share_code || showcaseRecord?.shareCode || null);
  let showcaseName = $derived(showcaseRecord?.name || showcaseLoadout?.Name || 'Showcase Loadout');
  const avatarSubTabs = [
    { id: 'Stats', label: 'Detailed Stats' },
    { id: 'Weapons', label: 'Weapons' },
    { id: 'Armor', label: 'Armor' },
    { id: 'Healing', label: 'Healing' },
    { id: 'Accessories', label: 'Rings, Clothing & Pet' }
  ];
  let clothingEntries = $derived((showcaseLoadout?.Gear?.Clothing || []).map(entry => (
    typeof entry === 'string' ? { Name: entry } : entry
  )));
  let leftRing = $derived(clothingEntries.length ? getClothingSlot('Ring', 'Left') : null);
  let rightRing = $derived(clothingEntries.length ? getClothingSlot('Ring', 'Right') : null);
  let selectedClothing = $derived(clothingEntries.filter(item => !isRingSlot(item?.Slot)));
  let evaluation = $state(null);
  let stats = $derived(evaluation?.stats || {});
  let effectsAll = $derived(evaluation?.effects?.all || []);
  let expandedEffectKeys = $state(new Set());
  let isHydratingShowcase = $state(false);

  let weapons = $state([]);
  let amplifiers = $state([]);
  let scopes = $state([]);
  let sights = $state([]);
  let absorbers = $state([]);
  let matrices = $state([]);
  let implants = $state([]);
  let armorsets = $state([]);
  let armors = $state([]);
  let armorplatings = $state([]);
  let clothing = $state([]);
  let pets = $state([]);
  let stimulants = $state([]);
  let medicalTools = $state([]);
  let effectsCatalog = $state([]);
  let effectCaps = $state({});

  let form = $state({
    biographyHtml: '',
    defaultTab: 'General',
    showcaseLoadoutCode: '',
    socialDiscord: '',
    socialYoutube: '',
    socialTwitch: ''
  });

  // Reset UI state when navigating to a different profile
  function resetUIState() {
    isEditing = false;
    saveError = '';
    saveStatus = '';
    tabInitialized = false;
    imageFailed = false;
    bannerFailed = false;
    backgroundFailed = false;
    showImageDialog = false;
    showBannerDialog = false;
    showBackgroundDialog = false;
    showSocietyDialog = false;
    avatarTabsInitialized = false;
    referenceReady = false;
    referenceLoading = false;
    referenceError = '';
    isHydratingShowcase = false;
    expandedEffectKeys = new Set();
    globalsData = null;
    globalsLoading = false;
    globalsLoaded = false;
    globalsTypeFilter = '';
    globalsSpaceFilter = '';
    globalsSort = { col: 'total_value', asc: false };
    globalsPage = 0;
    // Reset form to new profile data
    form = {
      biographyHtml: profile?.biographyHtml || '',
      defaultTab: profile?.defaultTab || 'General',
      showcaseLoadoutCode: profile?.showcaseLoadoutCode || '',
      socialDiscord: profile?.socialDiscord || '',
      socialYoutube: profile?.socialYoutube || '',
      socialTwitch: profile?.socialTwitch || ''
    };
  }


  // Globals tab state (lazy-loaded)
  let globalsData = $state(null);
  let globalsLoading = $state(false);
  let globalsLoaded = $state(false);
  let globalsTypeFilter = $state('');
  let globalsSpaceFilter = $state('');
  let globalsSort = $state({ col: 'total_value', asc: false });
  let globalsPage = $state(0);
  let globalsAthMode = $state('best'); // 'best' | 'total' | 'bestTarget' | 'totalTarget'
  const GLOBALS_PAGE_SIZE = 10;
  const GLOBALS_TYPE_FILTERS = TYPE_FILTERS.filter(tf => tf.value !== 'examine');

  async function loadGlobalsData() {
    if (globalsLoaded || globalsLoading || !profile.euName) return;
    globalsLoading = true;
    try {
      const res = await fetch(`/api/globals/player/${encodeURIComponent(profile.euName)}`);
      if (res.ok) {
        globalsData = await res.json();
      }
    } catch { /* ignore */ }
    globalsLoading = false;
    globalsLoaded = true;
  }


  function onGlobalsSort(col) {
    globalsSort = toggleSort(globalsSort, col);
    globalsPage = 0;
  }




  function sortOrdersByCategory(orderList) {
    return orderList
      .map(o => ({ ...o, category: getItemCategoryPath(o.item_type, o.item_sub_type) }))
      .sort((a, b) => {
        const catCmp = a.category.localeCompare(b.category);
        if (catCmp !== 0) return catCmp;
        const nameA = a.details?.item_name || '';
        const nameB = b.details?.item_name || '';
        return nameA.localeCompare(nameB);
      });
  }

  function formatRentalAvailability(offer) {
    if (offer.status === 'available') return null;
    if (!offer.rented_until) return 'Currently rented';
    const until = new Date(offer.rented_until);
    const now = new Date();
    if (until <= now) return 'Currently rented';
    return `Available ${until.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
  }

  function getBestRentalDiscount(discounts) {
    if (!Array.isArray(discounts) || discounts.length === 0) return null;
    let best = null;
    for (const d of discounts) {
      if (d.percent > 0 && d.minDays > 0) {
        if (!best || d.percent > best.percent) best = d;
      }
    }
    return best;
  }


  let activeTab = $state('General');











  // -- Offer table columns for the Orders tab --
  function formatOfferAge(dateStr) {
    if (!dateStr) return 'N/A';
    const diff = Math.max(0, Date.now() - new Date(dateStr).getTime());
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  const offerColumns = [
    {
      key: 'details', header: 'Item', main: true, sortable: true, searchable: true,
      formatter: (v, row) => {
        const itemName = v?.item_name;
        if (!itemName) return 'Unknown';
        const href = row?.item_type ? getTypeLink(itemName, row.item_type, row.item_sub_type || null) : null;
        const label = escapeHtml(itemName);
        const setBadge = row.item_type === 'ArmorPlating' && Number(row.quantity) === PLATE_SET_SIZE ? ' <span class="badge badge-subtle badge-accent">Set</span>' : '';
        return href
          ? `<a class="order-item-link" href="${escapeHtml(href)}">${label}</a>${setBadge}`
          : `${label}${setBadge}`;
      }
    },
    {
      key: 'category', header: 'Category', width: '140px',
      hideOnMobile: true, sortable: false, searchable: false,
      formatter: (v) => `<span class="category-label">${v || ''}</span>`
    },
    { key: 'quantity', header: 'Qty', width: '70px', sortable: true, searchable: false },
    {
      key: 'markup', header: 'MU', width: '90px', sortable: true, searchable: false,
      formatter: (v, row) => {
        const type = row?.item_type;
        const name = row?.details?.item_name || '';
        const subType = row?.item_sub_type || null;
        const isPercent = type ? isPercentMarkupType(type, name, subType) : true;
        return formatMarkupValue(v, !isPercent);
      }
    },
    { key: 'planet', header: 'Planet', width: '100px', sortable: true, searchable: false },
    {
      key: 'computed_state', header: 'Status', width: '80px', sortable: true, searchable: false,
      formatter: (v) => {
        const s = v || 'active';
        const cls = s === 'active' ? 'badge-success' : s === 'stale' ? 'badge-warning' : 'badge-error';
        return `<span class="badge badge-subtle ${cls}">${s}</span>`;
      }
    },
    {
      key: 'bumped_at', header: 'Updated', width: '80px', sortable: true, searchable: false,
      formatter: (v) => formatOfferAge(v)
    }
  ];


  function startEdit() {
    isEditing = true;
    saveError = '';
    saveStatus = '';
  }

  function cancelEdit() {
    isEditing = false;
    saveError = '';
    saveStatus = '';
    form = {
      biographyHtml: profile.biographyHtml || '',
      defaultTab: profile.defaultTab || 'General',
      showcaseLoadoutCode: profile.showcaseLoadoutCode || '',
      socialDiscord: profile.socialDiscord || '',
      socialYoutube: profile.socialYoutube || '',
      socialTwitch: profile.socialTwitch || ''
    };
  }

  async function saveProfile() {
    saveError = '';
    saveStatus = '';
    try {
      const response = await fetch(`/api/users/profiles/${profileSlug}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          biographyHtml: form.biographyHtml,
          defaultTab: form.defaultTab,
          showcaseLoadoutCode: form.showcaseLoadoutCode || null,
          socialDiscord: form.socialDiscord || null,
          socialYoutube: form.socialYoutube || null,
          socialTwitch: form.socialTwitch || null
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Failed to update profile');
      }
      profile = {
        ...profile,
        biographyHtml: payload.profile.biographyHtml,
        defaultTab: payload.profile.defaultTab,
        showcaseLoadoutCode: payload.profile.showcaseLoadoutCode,
        socialDiscord: payload.profile.socialDiscord,
        socialYoutube: payload.profile.socialYoutube,
        socialTwitch: payload.profile.socialTwitch
      };
      let nextShowcase = null;
      if (payload.profile.showcaseLoadoutCode) {
        try {
          const loadoutResponse = await fetch(`/api/tools/loadout/share/${payload.profile.showcaseLoadoutCode}`);
          if (loadoutResponse.ok) {
            nextShowcase = await loadoutResponse.json();
          } else if (avatar?.publicLoadouts) {
            nextShowcase = avatar.publicLoadouts.find(l => l.share_code === payload.profile.showcaseLoadoutCode) || null;
          }
        } catch (error) {
          console.error('Failed to fetch showcase loadout:', error);
        }
      }
      avatar = { ...avatar, showcaseLoadout: nextShowcase };
      isEditing = false;
      saveStatus = 'Profile updated.';
      tabInitialized = false;
    } catch (err) {
      saveError = err.message || 'Failed to update profile.';
    }
  }


  async function searchSocieties(query) {
    societySearchLoading = true;
    societySearchError = '';
    try {
      const response = await fetch(`/api/societies?query=${encodeURIComponent(query)}`);
      if (!response.ok) {
        throw new Error('Failed to load societies.');
      }
      societySearchResults = await response.json();
    } catch (err) {
      societySearchError = err.message || 'Failed to load societies.';
    } finally {
      societySearchLoading = false;
    }
  }

  function handleSocietySearchInput(value) {
    societySearchQuery = value;
    if (societySearchTimeout) {
      clearTimeout(societySearchTimeout);
    }
    societySearchTimeout = setTimeout(() => {
      searchSocieties(societySearchQuery.trim());
    }, 250);
  }

  async function handleJoinSociety(target) {
    societyActionError = '';
    societyActionStatus = '';
    try {
      const response = await fetch('/api/societies/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ societyId: target.id })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Failed to request join.');
      }
      pendingSocietyRequest = payload.request;
      society = payload.society;
      profile = { ...profile, societyId: -1 };
      societyActionStatus = 'Join request sent.';
    } catch (err) {
      societyActionError = err.message || 'Failed to request join.';
    }
  }

  async function handleCreateSociety() {
    societyActionError = '';
    societyActionStatus = '';
    try {
      const response = await fetch('/api/societies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: societyCreateName,
          abbreviation: societyCreateAbbr,
          description: societyCreateDescription,
          discord: societyCreateDiscord
        })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Failed to create society.');
      }
      society = payload.society;
      pendingSocietyRequest = null;
      profile = { ...profile, societyId: payload.society.id };
      societyActionStatus = 'Society created.';
      showSocietyDialog = false;
    } catch (err) {
      societyActionError = err.message || 'Failed to create society.';
    }
  }

  function openImageDialog() {
    if (!isOwner || !isEditing) return;
    saveError = '';
    saveStatus = '';
    showImageDialog = true;
  }

  function openBannerDialog() {
    if (!isOwner || !isEditing) return;
    saveError = '';
    saveStatus = '';
    showBannerDialog = true;
  }

  function openBackgroundDialog() {
    if (!isOwner || !isEditing) return;
    saveError = '';
    saveStatus = '';
    showBackgroundDialog = true;
  }

  function getApiBase() {
    return browser
      ? (import.meta.env.VITE_API_URL || 'https://api.entropianexus.com')
      : (process.env.INTERNAL_API_URL || 'http://api:3000');
  }

  function alphabeticalSort(a, b) {
    if (a?.Name === null) return 1;
    if (b?.Name === null) return -1;
    return a.Name.localeCompare(b.Name, undefined, { numeric: true });
  }

  function resolveDefaultSets(loadoutData) {
    if (!loadoutData) return null;
    if (!loadoutData.Sets) return loadoutData;
    // Deep clone so we don't mutate the original record data
    const resolved = JSON.parse(JSON.stringify(loadoutData));
    const sections = ['Weapon', 'Armor', 'Healing', 'Accessories'];
    for (const section of sections) {
      const sectionSets = resolved.Sets?.[section];
      if (!Array.isArray(sectionSets) || sectionSets.length === 0) continue;
      const defaultSet = sectionSets.find(s => s.isDefault) || sectionSets[0];
      if (!defaultSet?.gear) continue;
      // Apply default set gear/markup into Gear/Markup
      if (section === 'Weapon') {
        resolved.Gear.Weapon = defaultSet.gear;
        if (defaultSet.markup) Object.assign(resolved.Markup, defaultSet.markup);
      } else if (section === 'Armor') {
        resolved.Gear.Armor = defaultSet.gear;
        if (defaultSet.markup) {
          resolved.Markup.ArmorSet = defaultSet.markup.ArmorSet;
          resolved.Markup.PlateSet = defaultSet.markup.PlateSet;
          resolved.Markup.Armors = defaultSet.markup.Armors;
          resolved.Markup.Plates = defaultSet.markup.Plates;
        }
      } else if (section === 'Healing') {
        resolved.Gear.Healing = defaultSet.gear;
        if (defaultSet.markup) resolved.Markup.HealingTool = defaultSet.markup.HealingTool;
      } else if (section === 'Accessories') {
        resolved.Gear.Clothing = defaultSet.gear.Clothing || [];
        resolved.Gear.Consumables = defaultSet.gear.Consumables || [];
        resolved.Gear.Pet = defaultSet.gear.Pet || { Name: null, Effect: null };
      }
    }
    return resolved;
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
    clothing = (entities.clothings || []).sort(alphabeticalSort);
    pets = (entities.pets || []).sort(alphabeticalSort);
    stimulants = (entities.consumables || []).sort(alphabeticalSort);
    medicalTools = (entities.medicalTools || []).sort(alphabeticalSort);
  }

  function getClothingSlot(slotName, side = null) {
    const list = clothingEntries || [];
    if (isRingSlot(slotName)) {
      return list.find(item =>
        isRingSlot(item?.Slot)
        && (side ? item?.Side === side : !item?.Side)
      );
    }
    return list.find(item => item?.Slot === slotName && (side ? item?.Side === side : !item?.Side));
  }

  function getArmorPieces() {
    if (!showcaseLoadout?.Gear?.Armor) return [];
    return armorSlots
      .map(slot => showcaseLoadout?.Gear?.Armor?.[slot]?.Name)
      .filter(Boolean);
  }

  function getArmorSummary() {
    if (!showcaseLoadout?.Gear?.Armor) return '-';
    if (!showcaseLoadout.Gear.Armor.ManageIndividual && showcaseLoadout.Gear.Armor.SetName) {
      return showcaseLoadout.Gear.Armor.SetName;
    }
    const pieces = getArmorPieces();
    if (pieces.length === 0) return '-';
    if (pieces.length <= 2) return pieces.join(', ');
    return `${pieces[0]}, ${pieces[1]} +${pieces.length - 2}`;
  }

  async function loadAvatarReferences() {
    referenceLoading = true;
    referenceError = '';
    try {
      const entities = await loadLoadoutEntities();
      processEntityData(entities);
    } catch (error) {
      console.error('Failed to load loadout entities:', error);
      referenceError = 'Failed to load loadout references.';
    }

    try {
      const response = await fetch(`${getApiBase()}/effects`);
      if (response.ok) {
        effectsCatalog = await response.json();
        effectCaps = buildEffectCaps(effectsCatalog);
      }
    } catch (error) {
      console.error('Failed to load effects catalog:', error);
    } finally {
      referenceLoading = false;
      referenceReady = true;
    }
  }

  function getEquipmentLink(kind, name) {
    if (!name) return null;
    switch (kind) {
      case 'weapon':
        return getTypeLink(name, 'Weapon');
      case 'amplifier':
        return getTypeLink(name, 'WeaponAmplifier');
      case 'scope':
      case 'sight':
      case 'scope-sight':
        return getTypeLink(name, 'WeaponVisionAttachment');
      case 'absorber':
        return getTypeLink(name, 'Absorber');
      case 'matrix':
        return getTypeLink(name, 'WeaponAmplifier');
      case 'implant':
        return getTypeLink(name, 'MindforceImplant');
      case 'armorset':
        return getTypeLink(name, 'Armor');
      case 'armor':
        return `/items/armors/${encodeURIComponentSafe(name)}`;
      case 'armorplating':
        return getTypeLink(name, 'ArmorPlating');
      case 'clothing':
        return getTypeLink(name, 'Clothing');
      case 'pet':
        return getTypeLink(name, 'Pet');
      case 'healingtool':
        return getTypeLink(name, 'MedicalTool');
      default:
        return null;
    }
  }

  function formatEffectValue(effect) {
    if (!effect) return 'N/A';
    const value = effect.signedTotal ?? effect.value ?? 0;
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 'N/A';
    const unit = effect.unit || '';
    return `${numeric.toFixed(2)}${unit}`;
  }

  function formatMagnitude(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    return `${Math.abs(value).toFixed(2)}${unit}`;
  }

  function formatSignedNoPlus(value, unit = '%') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return 'N/A';
    const sign = numeric < 0 ? '-' : '';
    return `${sign}${Math.abs(numeric).toFixed(2)}${unit}`;
  }

  function formatCapLimit(limit, unit, polarity) {
    if (limit == null || Number.isNaN(limit)) return 'N/A';
    const numeric = Number(limit);
    if (!Number.isFinite(numeric)) return 'N/A';
    const sign = polarity === 'negative' ? '-' : '';
    return `${sign}${Math.abs(numeric).toFixed(2)}${unit}`;
  }

  function toggleEffectExpanded(effectKey) {
    if (expandedEffectKeys.has(effectKey)) {
      expandedEffectKeys.delete(effectKey);
    } else {
      expandedEffectKeys.add(effectKey);
    }
    expandedEffectKeys = new Set(expandedEffectKeys);
  }

  async function hydrateShowcaseLoadout(shareCode) {
    if (!shareCode || isHydratingShowcase) return;
    isHydratingShowcase = true;
    try {
      const response = await fetch(`/api/tools/loadout/share/${shareCode}`);
      if (response.ok) {
        const record = await response.json();
        avatar = { ...avatar, showcaseLoadout: record };
      }
    } catch (error) {
      console.error('Failed to hydrate showcase loadout:', error);
    } finally {
      isHydratingShowcase = false;
    }
  }
  // Make data-derived state reactive so it updates when navigating between profiles
  let profile = $derived(data.profileData.profile);
  let scores = $derived(data.profileData.scores);
  let services = $derived(data.profileData.services || []);
  let shops = $derived(data.profileData.shops || []);
  let orders = $derived(data.profileData.orders || []);
  let rentals = $derived(data.profileData.rentals || []);
  let avatar = $derived(data.profileData.avatar || {});
  let isOwner = $derived(data.profileData.permissions?.isOwner);
  let society = $derived(profile?.society || null);
  let pendingSocietyRequest = $derived(profile?.pendingSocietyRequest || null);
  // Reset UI state when profile changes
  $effect(() => {
    if (profile?.id && profile.id !== currentProfileId) {
      currentProfileId = profile.id;
      resetUIState();
    }
  });
  let hasAvatarData = $derived(!!(form.showcaseLoadoutCode || avatar?.showcaseLoadout));
  let hasServices = $derived(services.length > 0);
  let hasShops = $derived(shops.length > 0);
  let hasOrders = $derived(orders.length > 0);
  let hasRentals = $derived(rentals.length > 0);
  const tabAvailability = {
    Avatar: () => hasAvatarData || (isOwner && isEditing),
    Globals: () => !!profile.euName,
    Services: () => hasServices,
    Rentals: () => hasRentals,
    Shops: () => hasShops,
    Orders: () => hasOrders
  };
  let availableTabs = $derived(PROFILE_TABS
    .map(id => ({ id, label: id, available: tabAvailability[id]?.() ?? true }))
    .filter(tab => tab.available));
  $effect(() => {
    if (!untrack(() => tabInitialized) && availableTabs.length > 0) {
      const desired = profile.defaultTab || 'General';
      activeTab = availableTabs.find(tab => tab.id === desired)?.id || availableTabs[0].id;
      tabInitialized = true;
    }
  });
  $effect(() => {
    if (tabInitialized && !availableTabs.find(tab => tab.id === untrack(() => activeTab))) {
      activeTab = availableTabs[0]?.id || 'General';
    }
  });
  $effect(() => {
    if (activeTab === 'Globals' && !globalsLoaded) {
      loadGlobalsData();
    }
  });
  // Merge hunting/mining/crafting into a unified table
  let globalsUnifiedRows = $derived((() => {
    if (!globalsData) return [];
    const rows = [];
    for (const mob of (globalsData.hunting || [])) {
      rows.push({ target: mob.target, type: 'hunting', typeLabel: 'Hunting', count: mob.kills, total_value: mob.total_value, avg_value: mob.avg_value || 0, best_value: mob.best_value });
    }
    for (const res of (globalsData.mining?.resources || [])) {
      rows.push({ target: res.target, type: 'mining', typeLabel: 'Mining', count: res.finds, total_value: res.total_value, avg_value: res.avg_value || 0, best_value: res.best_value });
    }
    for (const mob of (globalsData.space_mining || [])) {
      rows.push({ target: mob.target, type: 'space_mining', typeLabel: 'Space Mining', count: mob.finds, total_value: mob.total_value, avg_value: mob.avg_value || 0, best_value: mob.best_value });
    }
    for (const item of (globalsData.crafting?.items || [])) {
      rows.push({ target: item.target, type: 'crafting', typeLabel: 'Crafting', count: item.crafts, total_value: item.total_value, avg_value: item.avg_value || 0, best_value: item.best_value });
    }
    return rows;
  })());
  let globalsFilteredRows = $derived((() => {
    if (!globalsTypeFilter) return globalsUnifiedRows;
    if (globalsTypeFilter === 'kill,team_kill') return globalsUnifiedRows.filter(r => r.type === 'hunting');
    if (globalsTypeFilter === 'deposit' && globalsSpaceFilter === 'only') return globalsUnifiedRows.filter(r => r.type === 'space_mining');
    if (globalsTypeFilter === 'deposit') return globalsUnifiedRows.filter(r => r.type === 'mining');
    if (globalsTypeFilter === 'craft') return globalsUnifiedRows.filter(r => r.type === 'crafting');
    return globalsUnifiedRows;
  })());
  let globalsSortedRows = $derived(sortedData(globalsFilteredRows, globalsSort));
  let globalsTotalPages = $derived(Math.ceil(globalsSortedRows.length / GLOBALS_PAGE_SIZE));
  let globalsDisplayRows = $derived(globalsSortedRows.slice(globalsPage * GLOBALS_PAGE_SIZE, (globalsPage + 1) * GLOBALS_PAGE_SIZE));
  // ATH rankings data
  let globalsAthRankings = $derived(globalsData?.ath_rankings || { hunting: [], mining: [], crafting: [], space_mining: [], pvp: [] });
  let globalsCategoryRanks = $derived(globalsData?.category_ranks || null);
  let globalsActivityByType = $derived(globalsData?.activity_by_type || { hunting: [], mining: [], crafting: [], space_mining: [] });
  let globalsSpaceMining = $derived(globalsData?.space_mining || []);
  const SPARK_MONTHS = 12; // last 365 days ≈ 12 monthly buckets
  let globalsSummary = $derived(globalsData?.summary || null);

  /** Smoothed SVG sparkline path from an array of numbers. */
  function sparklinePath(data, width, height) {
    if (!data || data.length < 2) return '';
    const max = Math.max(...data) || 1;
    const step = width / (data.length - 1);
    const y = (v) => height - (v / max) * height * 0.85;
    const t = 0.5;
    let d = `M0,${height}`;
    let inCurve = false;
    for (let i = 0; i < data.length; i++) {
      const x = i * step;
      if (data[i] === 0) {
        if (inCurve) { d += ` L${x},${height}`; inCurve = false; }
        continue;
      }
      if (!inCurve) { d += ` L${x},${height} L${x},${y(data[i])}`; inCurve = true; continue; }
      const i0 = Math.max(i - 2, 0), i1 = i - 1, i2 = i, i3 = Math.min(i + 1, data.length - 1);
      const p1 = [i1 * step, y(data[i1])], p2 = [x, y(data[i])];
      const p0 = [i0 * step, y(data[i0])], p3 = [i3 * step, y(data[i3])];
      d += ` C${p1[0] + (p2[0] - p0[0]) * t / 3},${p1[1] + (p2[1] - p0[1]) * t / 3} ${p2[0] - (p3[0] - p1[0]) * t / 3},${p2[1] - (p3[1] - p1[1]) * t / 3} ${p2[0]},${p2[1]}`;
    }
    if (inCurve) d += ` L${(data.length - 1) * step},${height}`;
    d += ` Z`;
    return d;
  }

  // Rare items and discoveries
  let globalsRareItems = $derived((globalsData?.rare_items || []).slice(0, 5));
  let globalsDiscoveries = $derived((globalsData?.achievements || []).filter(a => a.type === 'discovery').slice(0, 5));
  let buyOrders = $derived(sortOrdersByCategory(orders.filter(o => o.type === 'BUY')));
  let sellOrders = $derived(sortOrdersByCategory(orders.filter(o => o.type === 'SELL')));
  let showcaseLoadoutRaw = $derived(showcaseRecord?.data || null);
  $effect(() => {
    showcaseLoadout = resolveDefaultSets(showcaseLoadoutRaw);
  });
  $effect(() => {
    if (!avatarTabsInitialized) {
      avatarDetailTab = 'Stats';
      avatarTabsInitialized = true;
    }
  });
  let profileSlug = $derived(profile.euName ? encodeURIComponentSafe(profile.euName) : profile.id);
  let displayImageUrl = $derived(imageFailed
    ? profile.discordAvatarUrl
    : (profile.profileImageUrl || profile.discordAvatarUrl));
  let displayBannerUrl = $derived(!bannerFailed && profile?.profileBannerUrl ? profile.profileBannerUrl : null);
  let displayBackgroundUrl = $derived(!backgroundFailed && profile?.profileBackgroundUrl ? profile.profileBackgroundUrl : null);
  $effect(() => {
    evaluation = showcaseLoadout
      ? evaluateLoadout(
          showcaseLoadout,
          {
            armorSlots,
            weapons,
            amplifiers,
            scopes,
            sights,
            absorbers,
            matrices,
            implants,
            armors,
            armorPlatings: armorplatings,
            armorSets: armorsets,
            clothing,
            pets,
            stimulants,
            medicalTools
          },
          { effectsCatalog, effectCaps }
        )
      : null;
  });
  let defenseBreakdown = $derived({
    ...(stats.totalDefenseByType || {}),
    Block: stats.blockChance ?? 0
  });
  $effect(() => {
    if (showcaseLoadout && browser && !referenceReady && !referenceLoading) {
      loadAvatarReferences();
    }
  });
  $effect(() => {
    if (browser && showcaseRecord && !showcaseRecord?.data && showcaseShareCode && !isHydratingShowcase) {
      hydrateShowcaseLoadout(showcaseShareCode);
    }
  });
  let ordersPageUrl = $derived(profile?.euName
    ? `/market/exchange/orders/${encodeURIComponentSafe(profile.euName)}`
    : null);
</script>

<svelte:head>
  <title>{profile.euName || profile.discordName} | User Profile</title>
  <meta name="description" content="User profile for {profile.euName || profile.discordName} on Entropia Nexus." />
  <link rel="canonical" href="https://entropianexus.com/users/{encodeURIComponentSafe(profile?.euName || profile?.discordName || '')}" />
</svelte:head>

<div class="profile-page" class:has-background={!!displayBackgroundUrl}>
  {#if displayBackgroundUrl}
    <div
      class="profile-page-background"
      style="background-image: url('{displayBackgroundUrl}');"
    ></div>
    <div class="profile-page-background-overlay"></div>
    <img
      src={displayBackgroundUrl}
      alt=""
      class="profile-page-background-probe"
      onerror={() => (backgroundFailed = true)}
    />
  {/if}
  <div class="profile-header" class:has-banner={!!displayBannerUrl}>
    {#if displayBannerUrl || (isOwner && isEditing)}
      <div class="profile-header-banner">
        {#if displayBannerUrl}
          <img
            src={displayBannerUrl}
            alt=""
            class="profile-banner-img"
            onerror={() => (bannerFailed = true)}
          />
        {/if}
        {#if isOwner && isEditing}
          <button
            type="button"
            class="banner-edit-btn"
            onclick={openBannerDialog}
            title="Change banner"
          >{displayBannerUrl ? 'Change banner' : 'Add banner'}</button>
        {/if}
      </div>
    {/if}
    <div class="profile-header-content">
    <div class="profile-image">
      <button class="profile-image-button" type="button" onclick={openImageDialog} class:editable={isOwner && isEditing}>
        {#if displayImageUrl}
          <img src={displayImageUrl} alt={profile.euName || profile.discordName} onerror={() => (imageFailed = true)} />
        {:else}
          <div class="profile-image-placeholder">No Image</div>
        {/if}
        {#if isOwner && isEditing}
          <div class="image-overlay">Change</div>
        {/if}
      </button>
    </div>

    <div class="profile-info">
      <div class="profile-names">
        <h1>{profile.euName || profile.discordName}</h1>
        {#if profile.socialDiscord || profile.socialYoutube || profile.socialTwitch}
          <div class="social-icons">
            {#if profile.socialDiscord}
              <button class="social-link social-discord" class:discord-copied={discordFlash} title="Copy Discord: {profile.socialDiscord}" onclick={copyDiscordName}>
                <svg viewBox="0 0 127.14 96.36" width="23" height="23"><path fill="currentColor" d="M107.7 8.07A105.15 105.15 0 0 0 81.47 0a72.06 72.06 0 0 0-3.36 6.83 97.68 97.68 0 0 0-29.11 0A72.37 72.37 0 0 0 45.64 0 105.89 105.89 0 0 0 19.39 8.09C2.79 32.65-1.71 56.6.54 80.21a105.73 105.73 0 0 0 32.17 16.15 77.7 77.7 0 0 0 6.89-11.11 68.42 68.42 0 0 1-10.85-5.18c.91-.66 1.8-1.34 2.66-2.03a75.57 75.57 0 0 0 64.32 0c.87.71 1.76 1.39 2.66 2.03a68.68 68.68 0 0 1-10.87 5.19 77 77 0 0 0 6.89 11.1 105.25 105.25 0 0 0 32.19-16.14c2.64-27.38-4.51-51.11-18.9-72.15ZM42.45 65.69C36.18 65.69 31 60 31 53.05s5-12.68 11.45-12.68S54 46.07 53.89 53.05 48.84 65.69 42.45 65.69Zm42.24 0C78.41 65.69 73.25 60 73.25 53.05s5-12.68 11.44-12.68S96.23 46.07 96.12 53.05 91.08 65.69 84.69 65.69Z"/></svg>
              </button>
            {/if}
            {#if profile.socialYoutube}
              <a href={youtubeUrl(profile.socialYoutube)} target="_blank" rel="noopener noreferrer" class="social-link social-youtube" title="YouTube: {profile.socialYoutube}">
                <svg viewBox="0 0 24 24" width="22" height="22"><path fill="#FF0000" d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
              </a>
            {/if}
            {#if profile.socialTwitch}
              <a href={`https://twitch.tv/${profile.socialTwitch}`} target="_blank" rel="noopener noreferrer" class="social-link social-twitch" title="Twitch: {profile.socialTwitch}">
                <svg viewBox="0 0 24 24" width="21" height="21"><path fill="#9146FF" d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z"/></svg>
              </a>
            {/if}
          </div>
        {/if}
      </div>
      <div class="profile-meta">
        <div class="meta-row">
          <span class="meta-label">Discord</span>
          <span class="meta-value">@{profile.discordName}</span>
        </div>
        <div class="meta-row">
          <span class="meta-label">Society</span>
          {#if profile.societyId === -1 && pendingSocietyRequest}
            <span class="meta-value">Join request pending</span>
          {:else if society}
            <a class="meta-value society-link" href={`/societies/${encodeURIComponentSafe(society.name)}`}>{society.name}{society.abbreviation ? ` (${society.abbreviation})` : ''}</a>
          {:else if !isOwner}
            <span class="meta-value">—</span>
          {/if}
          {#if isOwner && (!profile.societyId || profile.societyId <= 0)}
            <button class="btn btn-secondary btn-small society-action" onclick={() => { showSocietyDialog = true; societyActionError = ''; societyActionStatus = ''; }}>
              Join / Create
            </button>
          {/if}
        </div>
      </div>
      {#if saveError}
        <div class="error-text">{saveError}</div>
      {:else if saveStatus}
        <div class="success-text">{saveStatus}</div>
      {/if}
    </div>
    {#if isOwner}
      <div class="profile-actions">
        {#if isEditing}
          <button class="btn btn-secondary btn-small" onclick={openBackgroundDialog} title="Change page background">Background</button>
          <button class="btn btn-primary" onclick={saveProfile}>Save</button>
          <button class="btn btn-secondary" onclick={cancelEdit}>Cancel</button>
        {:else}
          <button class="btn btn-primary edit-icon-btn" onclick={startEdit} title="Edit Profile" aria-label="Edit Profile">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
            </svg>
          </button>
        {/if}
      </div>
    {/if}
    </div>
  </div>

  <div class="profile-tabs" role="tablist">
    {#each availableTabs as tab}
      <button class:active={activeTab === tab.id} onclick={() => activeTab = tab.id}>{tab.label}</button>
    {/each}
  </div>

  <div class="profile-tab-panel">
    {#if activeTab === 'General'}
      <section class="panel-section">
        <h2>Contribution Score</h2>
        <div class="score-grid">
          <div class="score-card">
            <div class="score-label">Total</div>
            <div class="score-value">{scores.total}</div>
            <div class="score-rank">Rank #{scores.totalRank}</div>
          </div>
          <div class="score-card">
            <div class="score-label">This Month</div>
            <div class="score-value">{scores.monthly}</div>
            <div class="score-rank">Rank #{scores.monthlyRank}</div>
          </div>
          {#if profile.rewardScore > 0}
            <div class="score-card">
              <div class="score-label">Reward Score</div>
              <div class="score-value">{profile.rewardScore}</div>
            </div>
          {/if}
        </div>
      </section>

      <section class="panel-section">
        <h2>Biography</h2>
        {#if isEditing}
          <RichTextEditor bind:content={form.biographyHtml} placeholder="Write a short bio..." />
        {:else if profile.biographyHtml}
          <div class="bio-content">{@html profile.biographyHtml}</div>
        {:else}
          <div class="empty-state">No biography yet.</div>
        {/if}
      </section>

      {#if isEditing}
        <section class="panel-section">
          <h2>Social Links</h2>
          <div class="social-edit-grid">
            <div class="social-edit-row">
              <label class="social-edit-label" for="social-discord">
                <svg viewBox="0 0 127.14 96.36" width="16" height="16"><path fill="#5865F2" d="M107.7 8.07A105.15 105.15 0 0 0 81.47 0a72.06 72.06 0 0 0-3.36 6.83 97.68 97.68 0 0 0-29.11 0A72.37 72.37 0 0 0 45.64 0 105.89 105.89 0 0 0 19.39 8.09C2.79 32.65-1.71 56.6.54 80.21a105.73 105.73 0 0 0 32.17 16.15 77.7 77.7 0 0 0 6.89-11.11 68.42 68.42 0 0 1-10.85-5.18c.91-.66 1.8-1.34 2.66-2.03a75.57 75.57 0 0 0 64.32 0c.87.71 1.76 1.39 2.66 2.03a68.68 68.68 0 0 1-10.87 5.19 77 77 0 0 0 6.89 11.1 105.25 105.25 0 0 0 32.19-16.14c2.64-27.38-4.51-51.11-18.9-72.15ZM42.45 65.69C36.18 65.69 31 60 31 53.05s5-12.68 11.45-12.68S54 46.07 53.89 53.05 48.84 65.69 42.45 65.69Zm42.24 0C78.41 65.69 73.25 60 73.25 53.05s5-12.68 11.44-12.68S96.23 46.07 96.12 53.05 91.08 65.69 84.69 65.69Z"/></svg>
                Discord
              </label>
              <input id="social-discord" type="text" bind:value={form.socialDiscord} placeholder="username" maxlength="200" />
            </div>
            <div class="social-edit-row">
              <label class="social-edit-label" for="social-youtube">
                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="#FF0000" d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/></svg>
                YouTube
              </label>
              <input id="social-youtube" type="text" bind:value={form.socialYoutube} placeholder="channel name or URL" maxlength="200" />
            </div>
            <div class="social-edit-row">
              <label class="social-edit-label" for="social-twitch">
                <svg viewBox="0 0 24 24" width="16" height="16"><path fill="#9146FF" d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z"/></svg>
                Twitch
              </label>
              <input id="social-twitch" type="text" bind:value={form.socialTwitch} placeholder="username or URL" maxlength="200" />
            </div>
          </div>
          <p class="hint">Discord username is copied to clipboard when clicked. YouTube and Twitch accept usernames or channel URLs.</p>
        </section>

        <section class="panel-section">
          <h2>Default Tab</h2>
          <select bind:value={form.defaultTab}>
            {#each availableTabs as tab}
              <option value={tab.id}>{tab.label}</option>
            {/each}
          </select>
          <p class="hint">This controls which tab opens by default for other users viewing your profile.</p>
        </section>
      {/if}
    {/if}

    {#if activeTab === 'Avatar'}
      <section class="panel-section avatar-panel">
        <h2>Avatar</h2>
        {#if isEditing}
          <div class="field-group">
            <label for="showcase-loadout">Showcase Loadout</label>
            <select id="showcase-loadout" bind:value={form.showcaseLoadoutCode}>
              <option value="">None</option>
              {#each avatar.publicLoadouts || [] as loadout}
                <option value={loadout.share_code}>{loadout.name}</option>
              {/each}
            </select>
            <p class="hint">Only public loadouts can be showcased.</p>
          </div>
        {/if}

        {#if !showcaseRecord && !isEditing}
          <div class="empty-state">No avatar data yet.</div>
        {:else if !showcaseRecord}
          <div class="empty-state">Select a public loadout to preview.</div>
        {:else if !showcaseLoadout}
          <div class="empty-state">Loading loadout preview...</div>
        {:else}
          <div class="avatar-layout">
            <aside class="avatar-summary">
              <LoadoutCompactEmbed
                loadout={showcaseLoadout}
                stats={stats}
                shareCode={showcaseShareCode}
                title={showcaseName}
              />
            </aside>

            <div class="avatar-details">
              <div class="avatar-subtabs">
                {#each avatarSubTabs as tab}
                  <button class:active={avatarDetailTab === tab.id} onclick={() => avatarDetailTab = tab.id}>
                    {tab.label}
                  </button>
                {/each}
              </div>

              <div class="avatar-tab-panel">
                {#if referenceLoading}
                  <div class="empty-state">Loading loadout details...</div>
                {:else if referenceError}
                  <div class="error-text">{referenceError}</div>
                {:else}
                  {#if avatarDetailTab === 'Stats'}
                    <div class="stats-layout">
                      <div class="stats-left">
                        <div class="stats-section stats-offense">
                          <h3>Offense</h3>
                          <div class="stat-row"><span class="stat-label">Total Damage</span><span class="stat-value">{stats.totalDamage != null ? `${stats.totalDamage.toFixed(2)}` : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Range</span><span class="stat-value">{stats.range != null ? `${stats.range.toFixed(1)}m` : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Critical Chance</span><span class="stat-value">{stats.critChance != null ? `${(stats.critChance * 100).toFixed(1)}%` : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Critical Damage</span><span class="stat-value">{stats.critDamage != null ? `${(stats.critDamage * 100).toFixed(0)}%` : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Effective Damage</span><span class="stat-value">{stats.effectiveDamage != null ? `${stats.effectiveDamage.toFixed(2)}` : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Reload</span><span class="stat-value">{stats.reload != null ? `${stats.reload.toFixed(2)}s` : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Uses/min</span><span class="stat-value">{stats.reload != null ? `${clampDecimals(60 / stats.reload, 0, 2)}` : 'N/A'}</span></div>
                        </div>
                        <div class="stats-section stats-defense">
                          <h3>Defense</h3>
                          <div class="stat-row"><span class="stat-label">Armor Defense</span><span class="stat-value">{stats.armorDefense != null ? stats.armorDefense.toFixed(2) : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Plate Defense</span><span class="stat-value">{stats.plateDefense != null ? stats.plateDefense.toFixed(2) : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Total Defense</span><span class="stat-value">{stats.totalDefense != null ? stats.totalDefense.toFixed(2) : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Block</span><span class="stat-value">{stats.blockChance != null ? `${stats.blockChance.toFixed(1)}%` : 'N/A'}</span></div>
                        </div>
                        <div class="stats-section stats-economy">
                          <h3>Economy</h3>
                          <div class="stat-row"><span class="stat-label">Decay</span><span class="stat-value">{stats.decay != null ? `${stats.decay.toFixed(4)} PEC` : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Ammo</span><span class="stat-value">{stats.ammo != null ? Math.round(stats.ammo) : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Cost</span><span class="stat-value">{stats.cost != null ? `${stats.cost.toFixed(4)} PEC` : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Total Uses</span><span class="stat-value">{stats.lowestTotalUses != null ? stats.lowestTotalUses : 'N/A'}</span></div>
                        </div>
                        <div class="stats-section stats-armor-economy">
                          <h3>Armor Economy</h3>
                          <div class="stat-row"><span class="stat-label">Armor Durability</span><span class="stat-value">{stats.armorDurability != null ? stats.armorDurability : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Plate Durability</span><span class="stat-value">{stats.plateDurability != null ? stats.plateDurability : 'N/A'}</span></div>
                          <div class="stat-row"><span class="stat-label">Total Absorption</span><span class="stat-value">{stats.totalAbsorption != null ? `${stats.totalAbsorption.toFixed(0)} HP` : 'N/A'}</span></div>
                        </div>
                      </div>
                      <div class="stats-section effects-section stats-effects">
                        <h3>Effects</h3>
                        {#if effectsAll.length === 0}
                          <div class="empty-state">No active effects.</div>
                        {:else}
                          <div class="effects-list">
                            {#each effectsAll as effect}
                              {@const hasCaps = !!(effect?.caps?.item || effect?.caps?.action || effect?.caps?.total)}
                              {@const effectKey = `${effect.name}::${effect.unit}`}
                              {@const expanded = expandedEffectKeys.has(effectKey)}
                              {@const totalBase = (effect?.cappedItem ?? 0) + (effect?.cappedAction ?? 0) + (effect?.rawBonus ?? 0)}
                              {#if hasCaps}
                                <button type="button" class="effect-item equip effect-toggle" class:open={expanded} onclick={() => toggleEffectExpanded(effectKey)}>
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
                              {:else}
                                <div class="effect-item equip">
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
                                </div>
                              {/if}
                            {/each}
                          </div>
                        {/if}
                      </div>
                    </div>
                  {/if}

                  {#if avatarDetailTab === 'Weapons'}
                    <div class="gear-panel">
                      <div class="gear-section">
                        <h3>Weapon & Attachments</h3>
                        <div class="gear-list">
                          <div class="gear-item">
                            <span class="gear-label">Weapon</span>
                            {#if showcaseLoadout?.Gear?.Weapon?.Name}
                              <a class="gear-link" href={getEquipmentLink('weapon', showcaseLoadout.Gear.Weapon.Name)}>{showcaseLoadout.Gear.Weapon.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Amplifier</span>
                            {#if showcaseLoadout?.Gear?.Weapon?.Amplifier?.Name}
                              <a class="gear-link" href={getEquipmentLink('amplifier', showcaseLoadout.Gear.Weapon.Amplifier.Name)}>{showcaseLoadout.Gear.Weapon.Amplifier.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Scope</span>
                            {#if showcaseLoadout?.Gear?.Weapon?.Scope?.Name}
                              <a class="gear-link" href={getEquipmentLink('scope', showcaseLoadout.Gear.Weapon.Scope.Name)}>{showcaseLoadout.Gear.Weapon.Scope.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Scope Sight</span>
                            {#if showcaseLoadout?.Gear?.Weapon?.Scope?.Sight?.Name}
                              <a class="gear-link" href={getEquipmentLink('scope-sight', showcaseLoadout.Gear.Weapon.Scope.Sight.Name)}>{showcaseLoadout.Gear.Weapon.Scope.Sight.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Sight</span>
                            {#if showcaseLoadout?.Gear?.Weapon?.Sight?.Name}
                              <a class="gear-link" href={getEquipmentLink('sight', showcaseLoadout.Gear.Weapon.Sight.Name)}>{showcaseLoadout.Gear.Weapon.Sight.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Absorber</span>
                            {#if showcaseLoadout?.Gear?.Weapon?.Absorber?.Name}
                              <a class="gear-link" href={getEquipmentLink('absorber', showcaseLoadout.Gear.Weapon.Absorber.Name)}>{showcaseLoadout.Gear.Weapon.Absorber.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Matrix</span>
                            {#if showcaseLoadout?.Gear?.Weapon?.Matrix?.Name}
                              <a class="gear-link" href={getEquipmentLink('matrix', showcaseLoadout.Gear.Weapon.Matrix.Name)}>{showcaseLoadout.Gear.Weapon.Matrix.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Implant</span>
                            {#if showcaseLoadout?.Gear?.Weapon?.Implant?.Name}
                              <a class="gear-link" href={getEquipmentLink('implant', showcaseLoadout.Gear.Weapon.Implant.Name)}>{showcaseLoadout.Gear.Weapon.Implant.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                        </div>
                      </div>
                      <div class="gear-section">
                        <h3>Enhancers</h3>
                        <div class="enhancer-grid">
                          <div class="enhancer-item">
                            <span class="enhancer-label">Damage</span>
                            <span class="enhancer-value">{showcaseLoadout?.Gear?.Weapon?.Enhancers?.Damage ?? 0}</span>
                          </div>
                          <div class="enhancer-item">
                            <span class="enhancer-label">Accuracy</span>
                            <span class="enhancer-value">{showcaseLoadout?.Gear?.Weapon?.Enhancers?.Accuracy ?? 0}</span>
                          </div>
                          <div class="enhancer-item">
                            <span class="enhancer-label">Range</span>
                            <span class="enhancer-value">{showcaseLoadout?.Gear?.Weapon?.Enhancers?.Range ?? 0}</span>
                          </div>
                          <div class="enhancer-item">
                            <span class="enhancer-label">Economy</span>
                            <span class="enhancer-value">{showcaseLoadout?.Gear?.Weapon?.Enhancers?.Economy ?? 0}</span>
                          </div>
                          <div class="enhancer-item">
                            <span class="enhancer-label">Skill Mod</span>
                            <span class="enhancer-value">{showcaseLoadout?.Gear?.Weapon?.Enhancers?.SkillMod ?? 0}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  {/if}

                  {#if avatarDetailTab === 'Armor'}
                    <div class="gear-panel">
                      <div class="gear-column">
                        <div class="gear-section">
                          <h3>Armor & Plates</h3>
                          {#if showcaseLoadout?.Gear?.Armor?.ManageIndividual}
                            <div class="armor-grid">
                              <div class="armor-grid-header">Slot</div>
                              <div class="armor-grid-header">Armor</div>
                              <div class="armor-grid-header">Plate</div>
                              {#each armorSlots as slot}
                                <div class="armor-grid-cell">{slot}</div>
                                <div class="armor-grid-cell">
                                  {#if showcaseLoadout?.Gear?.Armor?.[slot]?.Name}
                                    <a class="gear-link" href={getEquipmentLink('armor', showcaseLoadout.Gear.Armor[slot].Name)}>{showcaseLoadout.Gear.Armor[slot].Name}</a>
                                  {:else}
                                    <span>-</span>
                                  {/if}
                                </div>
                                <div class="armor-grid-cell">
                                  {#if showcaseLoadout?.Gear?.Armor?.[slot]?.Plate?.Name}
                                    <a class="gear-link" href={getEquipmentLink('armorplating', showcaseLoadout.Gear.Armor[slot].Plate.Name)}>{showcaseLoadout.Gear.Armor[slot].Plate.Name}</a>
                                  {:else}
                                    <span>-</span>
                                  {/if}
                                </div>
                              {/each}
                            </div>
                          {:else}
                            <div class="gear-list">
                              <div class="gear-item">
                                <span class="gear-label">Armor Set</span>
                                {#if showcaseLoadout?.Gear?.Armor?.SetName}
                                  <a class="gear-link" href={getEquipmentLink('armorset', showcaseLoadout.Gear.Armor.SetName)}>{showcaseLoadout.Gear.Armor.SetName}</a>
                                {:else}
                                  <span>-</span>
                                {/if}
                              </div>
                              <div class="gear-item">
                                <span class="gear-label">Plate Set</span>
                                {#if showcaseLoadout?.Gear?.Armor?.PlateName}
                                  <a class="gear-link" href={getEquipmentLink('armorplating', showcaseLoadout.Gear.Armor.PlateName)}>{showcaseLoadout.Gear.Armor.PlateName}</a>
                                {:else}
                                  <span>-</span>
                                {/if}
                              </div>
                            </div>
                          {/if}
                        </div>
                        <div class="gear-section">
                          <h3>Enhancers</h3>
                          <div class="enhancer-grid">
                            <div class="enhancer-item">
                              <span class="enhancer-label">Defense</span>
                              <span class="enhancer-value">{showcaseLoadout?.Gear?.Armor?.Enhancers?.Defense ?? 0}</span>
                            </div>
                            <div class="enhancer-item">
                              <span class="enhancer-label">Durability</span>
                              <span class="enhancer-value">{showcaseLoadout?.Gear?.Armor?.Enhancers?.Durability ?? 0}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                      <div class="gear-section">
                        <h3>Defense Breakdown</h3>
                        {#if !stats.totalDefenseByType && !(stats.blockChance > 0)}
                          <div class="empty-state">No defense data.</div>
                        {:else}
                          <DefenseGridEdit
                            defense={defenseBreakdown}
                            title="Defense Breakdown"
                            compact={true}
                            showBlockSeparately={true}
                          />
                        {/if}
                      </div>
                    </div>
                  {/if}

                  {#if avatarDetailTab === 'Healing'}
                    <div class="gear-panel">
                      <div class="gear-section">
                        <h3>Healing Tool</h3>
                        <div class="gear-list">
                          <div class="gear-item">
                            <span class="gear-label">Healing Tool</span>
                            {#if showcaseLoadout?.Gear?.Healing?.Name}
                              <a class="gear-link" href={getEquipmentLink('healingtool', showcaseLoadout.Gear.Healing.Name)}>{showcaseLoadout.Gear.Healing.Name}</a>
                            {:else}
                              <span class="gear-empty">-</span>
                            {/if}
                          </div>
                        </div>
                      </div>
                      <div class="gear-section">
                        <h3>Enhancers</h3>
                        <div class="enhancer-grid">
                          <div class="enhancer-item">
                            <span class="enhancer-label">Heal</span>
                            <span class="enhancer-value">{showcaseLoadout?.Gear?.Healing?.Enhancers?.Heal ?? 0}</span>
                          </div>
                          <div class="enhancer-item">
                            <span class="enhancer-label">Economy</span>
                            <span class="enhancer-value">{showcaseLoadout?.Gear?.Healing?.Enhancers?.Economy ?? 0}</span>
                          </div>
                          <div class="enhancer-item">
                            <span class="enhancer-label">Skill Mod</span>
                            <span class="enhancer-value">{showcaseLoadout?.Gear?.Healing?.Enhancers?.SkillMod ?? 0}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  {/if}

                  {#if avatarDetailTab === 'Accessories'}
                    <div class="gear-panel">
                      <div class="gear-section">
                        <h3>Rings & Pet</h3>
                        <div class="gear-list">
                          <div class="gear-item">
                            <span class="gear-label">Left Ring</span>
                            {#if leftRing?.Name}
                              <a class="gear-link" href={getEquipmentLink('clothing', leftRing.Name)}>{leftRing.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Right Ring</span>
                            {#if rightRing?.Name}
                              <a class="gear-link" href={getEquipmentLink('clothing', rightRing.Name)}>{rightRing.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                          <div class="gear-item">
                            <span class="gear-label">Pet</span>
                            {#if showcaseLoadout?.Gear?.Pet?.Name}
                              <a class="gear-link" href={getEquipmentLink('pet', showcaseLoadout.Gear.Pet.Name)}>{showcaseLoadout.Gear.Pet.Name}</a>
                            {:else}
                              <span>-</span>
                            {/if}
                          </div>
                        </div>
                      </div>
                      <div class="gear-section">
                        <h3>Clothing</h3>
                        {#if selectedClothing.length === 0}
                          <div class="empty-state">No clothing selected.</div>
                        {:else}
                          <div class="clothing-list">
                            {#each selectedClothing as entry}
                              <div class="clothing-item">
                                <a class="clothing-name gear-link" href={getEquipmentLink('clothing', entry.Name)}>{entry.Name}</a>
                                <div class="clothing-slot">{entry.Slot || 'Unknown'}</div>
                              </div>
                            {/each}
                          </div>
                        {/if}
                      </div>
                    </div>
                  {/if}
                {/if}
              </div>
            </div>
          </div>
        {/if}
      </section>
    {/if}

    {#if activeTab === 'Services'}
      <section class="panel-section">
        <h2>Services</h2>
        {#if services.length === 0}
          <div class="empty-state">No services listed.</div>
        {:else}
          <div class="list-grid">
            {#each services as service}
              <div class="list-card">
                <div class="list-title">{service.title}</div>
                <div class="list-meta">{service.type}</div>
                <a class="list-link" href={`/market/services/${service.id}`}>View service</a>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    {#if activeTab === 'Rentals'}
      <section class="panel-section">
        <h2>Item Rentals</h2>
        {#if rentals.length === 0}
          <div class="empty-state">No rental offers listed.</div>
        {:else}
          <div class="list-grid">
            {#each rentals as offer}
              {@const availability = formatRentalAvailability(offer)}
              {@const bestDiscount = getBestRentalDiscount(offer.discounts)}
              <a href="/market/rental/{offer.id}" class="list-card rental-card">
                <div class="rental-card-header">
                  <div class="list-title">{offer.title}</div>
                  <span class="rental-status-dot" class:available={offer.status === 'available'} class:rented={offer.status === 'rented'}
                    title={offer.status === 'available' ? 'Available now' : (availability || 'Rented')}
                  ></span>
                </div>
                <div class="rental-card-info">
                  <span class="rental-price">{parseFloat(offer.price_per_day).toFixed(2)} PED/day</span>
                  {#if bestDiscount}
                    <span class="rental-discount">-{bestDiscount.percent}% @ {bestDiscount.minDays}+ days</span>
                  {/if}
                </div>
                {#if availability}
                  <div class="rental-availability">{availability}</div>
                {/if}
                {#if offer.item_count > 0}
                  <div class="list-meta">{offer.item_count} item{offer.item_count !== 1 ? 's' : ''}</div>
                {/if}
              </a>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    {#if activeTab === 'Shops'}
      <section class="panel-section">
        <h2>Shops</h2>
        {#if shops.length === 0}
          <div class="empty-state">No shops listed.</div>
        {:else}
          <div class="list-grid">
            {#each shops as shop}
              <div class="list-card">
                <div class="list-title">{shop.name}</div>
                <div class="list-meta">{shop.planet_name || 'Unknown planet'}</div>
                <a class="list-link" href={`/market/shops/${encodeURIComponentSafe(shop.name || shop.id)}`}>View shop</a>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    {/if}

    {#if activeTab === 'Globals'}
      <section class="panel-section">
        {#if globalsLoading}
          <div class="empty-state">Loading globals...</div>
        {:else if !globalsData || globalsData.summary?.total_count === 0}
          <div class="empty-state">No globals recorded yet</div>
        {:else}
          <!-- Summary stat cards -->
          <div class="globals-compact-stats">
            <div class="globals-compact-stat">
              <svg class="globals-stat-icon" viewBox="0 0 24 24" fill="none" stroke="#60b0ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
              <strong>{globalsData.summary.total_count.toLocaleString()}</strong>
              <span>Globals</span>
            </div>
            <div class="globals-compact-stat">
              <svg class="globals-stat-icon" viewBox="0 0 24 24" fill="none" stroke="#2ecc71" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
              <strong>{formatPedShort(globalsData.summary.total_value)} PED</strong>
              <span>Total Value</span>
            </div>
            <div class="globals-compact-stat">
              <svg class="globals-stat-icon" viewBox="0 0 24 24" fill="none" stroke="#f39c12" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>
              <strong>{formatPedShort(globalsData.summary.avg_value)} PED</strong>
              <span>Avg Value</span>
            </div>
            <div class="globals-compact-stat">
              <svg class="globals-stat-icon" viewBox="0 0 24 24" fill="none" stroke="#e74c3c" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
              <strong>{formatPedShort(globalsData.summary.max_value)} PED</strong>
              <span>Best Loot</span>
            </div>
            <div class="globals-compact-stat">
              <svg class="globals-stat-icon" viewBox="0 0 24 24" fill="none" stroke="#eab308" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              <strong>{globalsData.summary.hof_count.toLocaleString()}</strong>
              <span>HoF</span>
            </div>
          </div>

          <!-- Category rankings -->
          <div class="globals-rankings">
            <div class="globals-rankings-header">
              <h3>Personal All Time Rankings</h3>
              <div class="globals-ath-toggle">
                <button class="globals-ath-btn" class:active={globalsAthMode === 'best'} onclick={() => globalsAthMode = 'best'}>Best</button>
                <button class="globals-ath-btn" class:active={globalsAthMode === 'total'} onclick={() => globalsAthMode = 'total'}>Total</button>
                <button class="globals-ath-btn" class:active={globalsAthMode === 'bestTarget'} onclick={() => globalsAthMode = 'bestTarget'}>Best (Target)</button>
                <button class="globals-ath-btn" class:active={globalsAthMode === 'totalTarget'} onclick={() => globalsAthMode = 'totalTarget'}>Total (Target)</button>
              </div>
            </div>
            {#if globalsSummary}
              <div class="globals-category-cards">
                {#each [
                  { key: 'hunting', label: 'Hunting', colorClass: 'hunting-color', count: (globalsSummary.kill_count || 0) + (globalsSummary.team_kill_count || 0), value: globalsSummary.hunting_value || 0 },
                  { key: 'mining', label: 'Mining', colorClass: 'mining-color', count: globalsSummary.deposit_count || 0, value: globalsSummary.mining_value || 0 },
                  { key: 'space_mining', label: 'Space Mining', colorClass: 'space-mining-color', count: globalsSpaceMining.reduce((s, m) => s + m.finds, 0), value: globalsSpaceMining.reduce((s, m) => s + m.total_value, 0) },
                  { key: 'crafting', label: 'Crafting', colorClass: 'crafting-color', count: globalsSummary.craft_count || 0, value: globalsSummary.crafting_value || 0 },
                ] as cat}
                  {@const cr = globalsCategoryRanks?.[cat.key]}
                  {@const rawSpark = globalsActivityByType[cat.key] || []}
                  {@const sparkData = rawSpark.length >= SPARK_MONTHS
                    ? rawSpark.slice(-SPARK_MONTHS)
                    : [...Array(SPARK_MONTHS - rawSpark.length).fill(0), ...rawSpark]}
                  <div class="globals-category-card {cat.colorClass}">
                    {#if sparkData.length >= 2}
                      <svg class="globals-cat-sparkline" viewBox="0 0 200 60" preserveAspectRatio="none">
                        <path d={sparklinePath(sparkData, 200, 60)} />
                      </svg>
                    {/if}
                    <div class="globals-cat-card-inner">
                      <div class="globals-cat-card-stats">
                        <span class="globals-cat-value {cat.colorClass}">{cat.count.toLocaleString()}</span>
                        <span class="globals-cat-label">{cat.label}</span>
                        <span class="globals-cat-sub">{formatPed(cat.value)} PED</span>
                      </div>
                      {#if cr}
                        <div class="globals-cat-card-ranks">
                          <div class="globals-cat-rank-item">
                            <span class="globals-cat-rank-label">Value</span>
                            <span class="ranking-badge" title="Rank by total value" class:rank-ruby={cr.value_rank <= 1} class:rank-diamond={cr.value_rank > 1 && cr.value_rank <= 10} class:rank-gold={cr.value_rank > 10 && cr.value_rank <= 50} class:rank-silver={cr.value_rank > 50 && cr.value_rank <= 200} class:rank-bronze={cr.value_rank > 200 && cr.value_rank <= 500}>#{cr.value_rank}</span>
                          </div>
                          <div class="globals-cat-rank-item">
                            <span class="globals-cat-rank-label">Count</span>
                            <span class="ranking-badge ranking-badge-count" title="Rank by global count" class:rank-ruby={cr.count_rank <= 1} class:rank-diamond={cr.count_rank > 1 && cr.count_rank <= 10} class:rank-gold={cr.count_rank > 10 && cr.count_rank <= 50} class:rank-silver={cr.count_rank > 50 && cr.count_rank <= 200} class:rank-bronze={cr.count_rank > 200 && cr.count_rank <= 500}>#{cr.count_rank}</span>
                          </div>
                        </div>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
            <div class="globals-rankings-grid">
              {#each [
                { key: 'hunting', label: 'Hunting', colorClass: 'hunting-color' },
                { key: 'mining', label: 'Mining', colorClass: 'mining-color' },
                { key: 'space_mining', label: 'Space Mining', colorClass: 'space-mining-color' },
                { key: 'crafting', label: 'Crafting', colorClass: 'crafting-color' }
              ] as category}
                {@const entries = (globalsAthRankings[category.key] || [])
                  .filter(e => globalsAthMode === 'best' || globalsAthMode === 'bestTarget' ? e.best_rank <= 500
                    : e.total_rank <= 500)
                  .sort((a, b) => {
                    if (globalsAthMode === 'best') return b.best_value - a.best_value;
                    if (globalsAthMode === 'total') return b.total_value - a.total_value;
                    if (globalsAthMode === 'bestTarget') return a.best_rank - b.best_rank || b.best_value - a.best_value;
                    return a.total_rank - b.total_rank || b.total_value - a.total_value;
                  })
                  .slice(0, 10)}
                <div class="globals-ranking-card">
                  <div class="ranking-card-header {category.colorClass}">{category.label}</div>
                  {#each entries as entry}
                    <div class="ranking-entry">
                      <span class="ranking-target">{entry.target}</span>
                      {#if globalsAthMode === 'best' || globalsAthMode === 'bestTarget'}
                        {@const r = entry.best_rank}
                        <span class="ranking-value">{formatPedShort(entry.best_value)} PED</span>
                        <span class="ranking-badge" title="Rank by best loot" class:rank-ruby={r <= 1} class:rank-diamond={r > 1 && r <= 10} class:rank-gold={r > 10 && r <= 50} class:rank-silver={r > 50 && r <= 200} class:rank-bronze={r > 200 && r <= 500}>#{r}</span>
                      {:else}
                        {@const r = entry.total_rank}
                        <span class="ranking-value">{formatPedShort(entry.total_value)} PED</span>
                        <span class="ranking-badge" title="Rank by total value" class:rank-ruby={r <= 1} class:rank-diamond={r > 1 && r <= 10} class:rank-gold={r > 10 && r <= 50} class:rank-silver={r > 50 && r <= 200} class:rank-bronze={r > 200 && r <= 500}>#{r}</span>
                      {/if}
                    </div>
                  {:else}
                    <div class="ranking-empty">No rankings yet</div>
                  {/each}
                </div>
              {/each}
            </div>
          </div>

          <!-- Rare Items & Discoveries -->
          <div class="globals-highlights">
            <div class="globals-highlight-card">
              <h3>Rare Items</h3>
              {#if globalsRareItems.length > 0}
                {#each globalsRareItems as item}
                  <div class="highlight-row">
                    <span class="highlight-name">{item.target}</span>
                    <span class="highlight-value">{formatPedShort(item.value)} PED</span>
                    {#if item.ath}<span class="highlight-badge ath">ATH</span>{:else if item.hof}<span class="highlight-badge hof">HoF</span>{/if}
                    <span class="highlight-time">{timeAgo(item.timestamp)}</span>
                  </div>
                {/each}
              {:else}
                <div class="ranking-empty">None recorded</div>
              {/if}
            </div>
            <div class="globals-highlight-card">
              <h3>Discoveries</h3>
              {#if globalsDiscoveries.length > 0}
                {#each globalsDiscoveries as ach}
                  <div class="highlight-row">
                    <span class="highlight-name">{ach.target}</span>
                    {#if ach.ath}<span class="highlight-badge ath">ATH</span>{:else if ach.hof}<span class="highlight-badge hof">HoF</span>{/if}
                    <span class="highlight-time">{timeAgo(ach.timestamp)}</span>
                  </div>
                {/each}
              {:else}
                <div class="ranking-empty">None recorded</div>
              {/if}
            </div>
          </div>

          <!-- Type filter buttons -->
          <div class="globals-compact-filters">
            {#each GLOBALS_TYPE_FILTERS as tf}
              <button
                class="globals-type-btn"
                class:active={globalsTypeFilter === tf.value && globalsSpaceFilter === (tf.space || '')}
                onclick={() => { globalsTypeFilter = tf.value; globalsSpaceFilter = tf.space || ''; globalsPage = 0; }}
              >
                {tf.label}
              </button>
            {/each}
          </div>

          <!-- Unified data table -->
          {#if globalsDisplayRows.length > 0}
            <div class="globals-compact-table-wrap">
              <table class="globals-compact-table">
                <thead>
                  <tr>
                    <th class="col-target sortable" role="columnheader" tabindex="0" onclick={() => onGlobalsSort('target')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onGlobalsSort('target'))}>Target{sortIcon(globalsSort, 'target')}</th>
                    <th class="col-type">Type</th>
                    <th class="col-num right sortable" role="columnheader" tabindex="0" onclick={() => onGlobalsSort('count')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onGlobalsSort('count'))}>Count{sortIcon(globalsSort, 'count')}</th>
                    <th class="col-num right sortable" role="columnheader" tabindex="0" onclick={() => onGlobalsSort('total_value')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onGlobalsSort('total_value'))}>Total Value{sortIcon(globalsSort, 'total_value')}</th>
                    <th class="col-num right sortable" role="columnheader" tabindex="0" onclick={() => onGlobalsSort('avg_value')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onGlobalsSort('avg_value'))}>Avg{sortIcon(globalsSort, 'avg_value')}</th>
                    <th class="col-num right sortable" role="columnheader" tabindex="0" onclick={() => onGlobalsSort('best_value')} onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), onGlobalsSort('best_value'))}>Best{sortIcon(globalsSort, 'best_value')}</th>
                  </tr>
                </thead>
                <tbody>
                  {#each globalsDisplayRows as row}
                    <tr>
                      <td class="col-target"><a href="/globals/target/{encodeURIComponent(row.target)}" class="globals-target-link">{row.target}</a></td>
                      <td class="col-type"><span class="globals-type-badge globals-type-{row.type}">{row.typeLabel}</span></td>
                      <td class="col-num right">{row.count.toLocaleString()}</td>
                      <td class="col-num right font-mono">{formatPedShort(row.total_value)} PED</td>
                      <td class="col-num right font-mono">{formatPedShort(row.avg_value)} PED</td>
                      <td class="col-num right font-mono">{formatPedShort(row.best_value)} PED</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
            {#if globalsTotalPages > 1}
              <div class="globals-pagination">
                <button class="page-btn" disabled={globalsPage <= 0} onclick={() => globalsPage--}>Previous</button>
                <span class="page-info">Page {globalsPage + 1} of {globalsTotalPages}</span>
                <button class="page-btn" disabled={globalsPage >= globalsTotalPages - 1} onclick={() => globalsPage++}>Next</button>
              </div>
            {/if}
          {:else}
            <div class="empty-state">No targets match this filter</div>
          {/if}

          <a href="/globals/player/{encodeURIComponent(profile.euName)}" class="globals-detail-link">View full details &rarr;</a>
        {/if}
      </section>
    {/if}

    {#if activeTab === 'Orders'}
      <section class="panel-section">
        {#if ordersPageUrl}
          <a class="orders-exchange-btn" href={ordersPageUrl}>View all orders on exchange</a>
        {/if}
        {#if orders.length === 0}
          <div class="empty-state">No active orders.</div>
        {:else}
          <div class="orders-stacked">
            <div class="orders-side">
              <h3 class="orders-side-title sell">Sell Orders</h3>
              {#if sellOrders.length === 0}
                <div class="orders-empty">No sell orders</div>
              {:else}
                <div class="orders-table-wrap">
                  <FancyTable
                    columns={offerColumns}
                    data={sellOrders}
                    rowHeight={32}
                    compact={true}
                    sortable={true}
                    searchable={false}
                    emptyMessage="No sell orders"
                  />
                </div>
              {/if}
            </div>
            <div class="orders-side">
              <h3 class="orders-side-title buy">Buy Orders</h3>
              {#if buyOrders.length === 0}
                <div class="orders-empty">No buy orders</div>
              {:else}
                <div class="orders-table-wrap">
                  <FancyTable
                    columns={offerColumns}
                    data={buyOrders}
                    rowHeight={32}
                    compact={true}
                    sortable={true}
                    searchable={false}
                    emptyMessage="No buy orders"
                  />
                </div>
              {/if}
            </div>
          </div>
        {/if}
      </section>
    {/if}
  </div>
</div>

{#if showSocietyDialog}
  <div class="dialog-backdrop" role="presentation" onclick={() => showSocietyDialog = false} onkeydown={(e) => e.key === 'Escape' && (showSocietyDialog = false)}>
    <div class="dialog dialog-compact" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} role="dialog" tabindex="-1" aria-modal="true" aria-labelledby="society-dialog-title">
      <div class="dialog-header">
        <h3 id="society-dialog-title">{societyMode === 'join' ? 'Join a Society' : 'Create a Society'}</h3>
        <button class="close-btn" onclick={() => showSocietyDialog = false} aria-label="Close dialog">&#10005;</button>
      </div>
      <div class="dialog-body">
        <div class="mode-toggle">
          <button class:active={societyMode === 'join'} onclick={() => societyMode = 'join'}>Join</button>
          <button class:active={societyMode === 'create'} onclick={() => societyMode = 'create'}>Create</button>
        </div>

        {#if societyMode === 'join'}
          <div class="field-group">
            <label for="society-search">Search Societies</label>
            <input id="society-search" type="text" placeholder="Type to search..." value={societySearchQuery} oninput={(e) => handleSocietySearchInput(e.target.value)} />
            {#if societySearchLoading}
              <div class="hint">Searching...</div>
            {:else if societySearchError}
              <div class="dialog-error">{societySearchError}</div>
            {:else if societySearchResults.length === 0}
              <div class="hint">No societies found.</div>
            {:else}
              <div class="society-list">
                {#each societySearchResults as item}
                  <div class="society-row">
                    <div>
                      <div class="society-name">{item.name}</div>
                      {#if item.abbreviation}
                        <div class="society-meta">{item.abbreviation}</div>
                      {/if}
                    </div>
                    <button class="dialog-btn" onclick={() => handleJoinSociety(item)}>Request Join</button>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          <div class="field-group">
            <label for="society-name">Society Name</label>
            <input id="society-name" type="text" bind:value={societyCreateName} placeholder="Society name" />
          </div>
          <div class="field-group">
            <label for="society-abbr">Abbreviation</label>
            <input id="society-abbr" type="text" bind:value={societyCreateAbbr} placeholder="Short tag (optional)" />
          </div>
            <div class="field-group">
              <span class="field-label">Description</span>
              <RichTextEditor bind:content={societyCreateDescription} placeholder="Short description" />
            </div>
            <div class="field-group">
              <label for="society-discord">Discord</label>
              <input id="society-discord" type="text" bind:value={societyCreateDiscord} placeholder="Invite link or code (optional)" />
              <div class="helper-text">Only the invite code is stored.</div>
            </div>
        {/if}

        {#if societyActionError}
          <div class="dialog-error">{societyActionError}</div>
        {:else if societyActionStatus}
          <div class="success-text">{societyActionStatus}</div>
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" onclick={() => showSocietyDialog = false}>Close</button>
        {#if societyMode === 'create'}
          <button class="dialog-btn" onclick={handleCreateSociety} disabled={!societyCreateName.trim()}>Create Society</button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<ImageUploadDialog
  open={showImageDialog}
  entityType="user"
  entityId={profile.id}
  entityName={profile.euName || profile.discordName}
  showDelete={true}
  hasImage={!!profile.hasCustomImage}
  onclose={() => (showImageDialog = false)}
  onuploaded={(data) => {
    if (data?.imageUrl) {
      profile = { ...profile, profileImageUrl: data.imageUrl, hasCustomImage: true };
      imageFailed = false;
      saveStatus = 'Profile image updated.';
    }
  }}
  ondeleted={() => {
    profile = { ...profile, profileImageUrl: null, hasCustomImage: false };
    imageFailed = false;
    saveStatus = 'Profile image removed.';
  }}
/>

<ImageUploadDialog
  open={showBannerDialog}
  entityType="user-banner"
  entityId={profile.id}
  entityName={profile.euName || profile.discordName}
  showDelete={true}
  hasImage={!!profile.hasCustomBanner}
  aspect={6}
  maxWidth={1200}
  maxHeight={200}
  onclose={() => (showBannerDialog = false)}
  onuploaded={(data) => {
    if (data?.imageUrl) {
      profile = { ...profile, profileBannerUrl: data.imageUrl, hasCustomBanner: true };
      bannerFailed = false;
      saveStatus = 'Banner updated.';
    }
  }}
  ondeleted={() => {
    profile = { ...profile, profileBannerUrl: null, hasCustomBanner: false };
    bannerFailed = false;
    saveStatus = 'Banner removed.';
  }}
/>

<ImageUploadDialog
  open={showBackgroundDialog}
  entityType="user-background"
  entityId={profile.id}
  entityName={profile.euName || profile.discordName}
  showDelete={true}
  hasImage={!!profile.hasCustomBackground}
  aspect={16 / 9}
  maxWidth={1920}
  maxHeight={1080}
  onclose={() => (showBackgroundDialog = false)}
  onuploaded={(data) => {
    if (data?.imageUrl) {
      profile = { ...profile, profileBackgroundUrl: data.imageUrl, hasCustomBackground: true };
      backgroundFailed = false;
      saveStatus = 'Background updated.';
    }
  }}
  ondeleted={() => {
    profile = { ...profile, profileBackgroundUrl: null, hasCustomBackground: false };
    backgroundFailed = false;
    saveStatus = 'Background removed.';
  }}
/>

<style>
  .profile-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px 20px 60px;
    display: flex;
    flex-direction: column;
    gap: 0;
    position: relative;
  }

  .profile-page-background,
  .profile-page-background-overlay {
    position: fixed;
    inset: 0;
    z-index: -1;
    pointer-events: none;
  }

  .profile-page-background {
    background-size: cover;
    background-position: center center;
    background-repeat: no-repeat;
  }

  .profile-page-background-overlay {
    background: linear-gradient(180deg, rgba(0, 0, 0, 0.5) 0%, rgba(0, 0, 0, 0.72) 100%);
  }

  .profile-page-background-probe {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }

  .profile-header {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #444);
    border-radius: 16px 16px 0 0;
    position: relative;
    overflow: hidden;
    margin-bottom: 0;
  }

  .profile-header-banner {
    position: relative;
    width: 100%;
    height: 200px;
    background: linear-gradient(135deg, var(--bg-color, #111), var(--secondary-color));
    overflow: hidden;
  }

  .profile-header.has-banner .profile-header-banner {
    background: transparent;
  }

  .profile-banner-img {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .banner-edit-btn {
    position: absolute;
    right: 12px;
    bottom: 12px;
    padding: 6px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.3);
    background: rgba(0, 0, 0, 0.55);
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    backdrop-filter: blur(4px);
  }

  .banner-edit-btn:hover {
    background: rgba(0, 0, 0, 0.75);
  }

  .profile-header-content {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 24px;
    padding: 20px;
    position: relative;
  }

  .profile-image {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: center;
  }

  .profile-image img,
  .profile-image-placeholder {
    width: 140px;
    height: 140px;
    border-radius: 12px;
    object-fit: cover;
    background: var(--bg-color, #111);
    border: 1px solid var(--border-color, #444);
  }

  .profile-image-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted, #888);
    font-size: 12px;
  }

  .profile-image-button {
    border: none;
    background: transparent;
    padding: 0;
    position: relative;
    cursor: default;
    border-radius: 12px;
    overflow: hidden;
  }

  .profile-image-button.editable {
    cursor: pointer;
  }

  .image-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 600;
    opacity: 0;
    border-radius: 12px;
    transition: opacity 0.15s ease;
  }

  .profile-image-button.editable:hover .image-overlay {
    opacity: 1;
  }

  .profile-info {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .profile-names {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .profile-names h1 {
    margin: 0;
    font-size: 26px;
  }

  .social-icons {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .social-link {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    opacity: 0.85;
    transition: opacity 0.15s ease, transform 0.15s ease;
    cursor: pointer;
  }

  .social-link:hover {
    opacity: 1;
    transform: scale(1.15);
  }

  button.social-link {
    background: none;
    border: none;
    padding: 0;
  }

  .social-discord {
    margin-right: 2px;
    color: #5865F2;
  }

  .social-discord:hover {
    background: none;
  }

  .social-discord.discord-copied {
    animation: discord-flash 0.6s ease;
  }

  @keyframes discord-flash {
    0% { color: #5865F2; }
    20% { color: #16a34a; transform: scale(1.2); }
    100% { color: #5865F2; transform: scale(1); }
  }

  .social-edit-grid {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .social-edit-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .social-edit-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    min-width: 100px;
    color: var(--text-muted, #999);
  }

  .social-edit-row input {
    flex: 1;
    background: var(--bg-color, #111);
    border: 1px solid var(--border-color, #444);
    color: var(--text-color);
    border-radius: 8px;
    padding: 8px 10px;
  }

  .society-link {
    color: var(--accent-color, #4a9eff);
  }

  .society-link:hover {
    text-decoration: underline;
  }

  .profile-meta {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .meta-row {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .meta-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-muted, #999);
    min-width: 80px;
    text-align: left;
  }

  .meta-value {
    font-size: 14px;
  }

  .btn {
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #444);
    cursor: pointer;
    background: var(--bg-color, #111);
    color: var(--text-color);
    font-size: 13px;
    font-weight: 600;
  }

  .btn-primary {
    background: var(--accent-color, #4a9eff);
    border-color: transparent;
    color: #fff;
  }

  .btn-secondary {
    background: transparent;
  }

  .btn-small {
    padding: 6px 10px;
    font-size: 12px;
  }

  .edit-icon-btn {
    padding: 6px;
    width: 34px;
    height: 34px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .edit-icon-btn svg {
    width: 16px;
    height: 16px;
  }

  .profile-actions {
    position: absolute;
    top: 20px;
    right: 20px;
    display: flex;
    gap: 10px;
  }

  .error-text {
    color: #ff6b6b;
    font-size: 12px;
  }

  .success-text {
    color: #4ade80;
    font-size: 12px;
  }

  .profile-tabs {
    display: flex;
    flex-wrap: nowrap;
    overflow-x: auto;
    background: var(--bg-color, #111);
    border: 1px solid var(--border-color, #444);
    border-bottom: none;
    border-radius: 16px 16px 0 0;
    margin-top: 16px;
  }

  .profile-tabs button {
    flex: 1 1 auto;
    padding: 14px 22px;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
    transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
    white-space: nowrap;
  }

  .profile-tabs button:hover {
    color: var(--text-color);
    background: rgba(255, 255, 255, 0.04);
  }

  .profile-tabs button.active {
    color: var(--text-color);
    background: var(--secondary-color);
    border-bottom-color: var(--accent-color, #4a9eff);
  }

  .profile-tab-panel {
    background: var(--secondary-color);
    border-radius: 0 0 16px 16px;
    border: 1px solid var(--border-color, #444);
    border-top: none;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 18px;
  }

  .panel-section h2 {
    margin: 0 0 12px;
    font-size: 18px;
  }

  .score-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
  }

  .score-card {
    background: var(--bg-color, #111);
    border: 1px solid var(--border-color, #444);
    border-radius: 12px;
    padding: 12px;
  }

  .score-label {
    color: var(--text-muted, #999);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .score-value {
    font-size: 20px;
    font-weight: 600;
    margin-top: 6px;
  }

  .score-rank {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 4px;
  }

  .bio-content {
    line-height: 1.6;
  }

  .empty-state {
    color: var(--text-muted, #999);
    font-size: 13px;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field-group select,
  .field-group input,
  .panel-section select {
    background: var(--bg-color, #111);
    border: 1px solid var(--border-color, #444);
    color: var(--text-color);
    border-radius: 8px;
    padding: 8px 10px;
    max-width: 320px;
  }

  .hint {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .list-grid {
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .list-card {
    background: var(--bg-color, #111);
    border: 1px solid var(--border-color, #444);
    border-radius: 12px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .list-title {
    font-weight: 600;
  }

  .list-meta {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .list-link {
    font-size: 12px;
    color: var(--accent-color, #4a9eff);
  }

  a.rental-card {
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.15s;
  }

  a.rental-card:hover {
    border-color: var(--accent-color);
  }

  .rental-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .rental-status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    background: var(--text-muted);
  }

  .rental-status-dot.available {
    background: var(--success-color);
  }

  .rental-status-dot.rented {
    background: var(--accent-color);
  }

  .rental-card-info {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .rental-price {
    font-size: 13px;
    font-weight: 600;
    color: var(--accent-color);
  }

  .rental-discount {
    font-size: 11px;
    color: var(--success-color);
    background: var(--success-bg);
    padding: 1px 6px;
    border-radius: 4px;
  }

  .rental-availability {
    font-size: 12px;
    color: var(--accent-color);
    font-style: italic;
  }

  .dialog-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 80;
    padding: 20px;
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 10px;
    width: min(520px, 92vw);
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }

  .dialog.dialog-compact {
    width: min(520px, 92vw);
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
  }

  .close-btn {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--text-muted, #999);
    border-radius: 4px;
  }

  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px 18px;
    font-size: 13px;
    color: var(--text-color);
    flex: 1;
    min-height: 0;
    overflow: auto;
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 12px 18px 16px;
    border-top: 1px solid var(--border-color, #555);
  }

  .dialog-btn {
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #555);
    background: var(--accent-color, #4a9eff);
    color: #fff;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
  }

  .dialog-btn.secondary {
    background: transparent;
    color: var(--text-color);
  }

  .dialog-error {
    color: #ff6b6b;
    font-size: 12px;
  }

  .mode-toggle {
    display: inline-flex;
    gap: 8px;
  }

  .mode-toggle button {
    padding: 6px 12px;
    border-radius: 999px;
    border: 1px solid var(--border-color, #444);
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    font-size: 12px;
  }

  .mode-toggle button.active {
    background: var(--accent-color, #4a9eff);
    border-color: transparent;
    color: #fff;
  }

  .society-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .society-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 8px 10px;
    border: 1px solid var(--border-color, #444);
    border-radius: 8px;
    background: var(--bg-color, #111);
  }

  .society-name {
    font-weight: 600;
  }

  .society-meta {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .avatar-panel {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .avatar-layout {
    display: grid;
    grid-template-columns: minmax(240px, 300px) 1fr;
    gap: 18px;
    align-items: start;
  }

  .avatar-summary {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .avatar-details {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .avatar-subtabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .avatar-subtabs button {
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid var(--border-color, #444);
    background: var(--bg-color, #111);
    color: var(--text-color);
    font-size: 12px;
    cursor: pointer;
  }

  .avatar-subtabs button.active {
    background: var(--accent-color, #4a9eff);
    border-color: transparent;
    color: #fff;
  }

  .avatar-tab-panel {
    background: var(--bg-color, #111);
    border: 1px solid var(--border-color, #333);
    border-radius: 14px;
    padding: 14px;
  }

  .stats-layout {
    display: grid;
    grid-template-columns: minmax(360px, 2fr) minmax(240px, 1fr);
    gap: 14px;
    align-items: start;
  }

  .stats-left {
    display: grid;
    grid-template-columns: repeat(2, minmax(220px, 1fr));
    gap: 14px;
    align-items: start;
  }

  .stats-section h3 {
    margin: 0 0 8px;
    font-size: 14px;
  }

  .stats-section {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
    align-self: start;
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    font-size: 12px;
    margin-bottom: 6px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    text-align: right;
  }

  .effects-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .effect-item {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 8px 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 4px;
    font-size: 13px;
    border-left: 3px solid transparent;
    margin-top: 4px;
  }

  .effects-list > :first-child {
    margin-top: 0;
  }

  .effect-item.equip {
    border-left-color: var(--success-color, #4ade80);
  }

  .effect-toggle {
    width: 100%;
    text-align: left;
    cursor: pointer;
    font: inherit;
    color: inherit;
    background: inherit;
    border: none;
    border-left: 3px solid transparent;
    appearance: none;
    -webkit-appearance: none;
    font-size: 13px;
    line-height: 1.2;
  }

  .effect-toggle.open {
    background-color: var(--hover-color);
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }

  .effect-toggle:hover {
    background-color: var(--hover-color);
  }

  .effect-name {
    font-weight: 500;
    color: var(--text-color);
  }

  .effect-details {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted, #999);
    font-size: 12px;
  }

  .effect-value.positive {
    color: #4ade80;
  }

  .effect-value.negative {
    color: #f87171;
  }

  .cap-breakdown {
    border: 1px solid var(--border-color, #555);
    border-top: none;
    border-left: 3px solid var(--success-color, #4ade80);
    border-bottom-left-radius: 4px;
    border-bottom-right-radius: 4px;
    background-color: var(--bg-color, var(--primary-color));
    padding: 8px 12px 10px;
    display: grid;
    margin-top: -1px;
  }

  .cap-breakdown-inner {
    display: grid;
    gap: 6px;
    font-size: 12px;
  }

  .cap-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    font-size: 12px;
    color: var(--text-color);
  }

  .cap-label {
    color: var(--text-muted, #999);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    font-size: 10px;
  }

  .cap-metric {
    font-weight: 600;
    color: var(--text-color);
    text-align: right;
    white-space: nowrap;
  }

  .cap-over {
    color: #f87171;
    font-weight: 600;
  }

  .gear-panel {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 16px;
  }

  .gear-column {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .gear-section {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .gear-section h3 {
    margin: 0;
    font-size: 14px;
  }

  .gear-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .gear-item {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    font-size: 12px;
  }

  .gear-item span:last-child {
    text-align: right;
  }

  .gear-label {
    color: var(--text-muted, #999);
  }

  .gear-link {
    color: var(--accent-color, #4a9eff);
  }

  .enhancer-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 10px;
  }

  .enhancer-item {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border-color, #333);
    border-radius: 10px;
    padding: 8px;
    text-align: center;
    font-size: 12px;
  }

  .enhancer-label {
    display: block;
    color: var(--text-muted, #999);
    font-size: 11px;
  }

  .enhancer-value {
    font-weight: 600;
    margin-top: 4px;
    display: block;
  }

  .armor-grid {
    display: grid;
    grid-template-columns: 80px 1fr 1fr;
    gap: 6px;
    font-size: 12px;
  }

  .armor-grid-header {
    font-size: 11px;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.4px;
  }

  .armor-grid-cell {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--border-color, #333);
    border-radius: 8px;
    padding: 6px 8px;
  }


  .clothing-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .clothing-item {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--border-color, #333);
    border-radius: 10px;
    padding: 8px 10px;
    display: flex;
    justify-content: space-between;
    gap: 10px;
    font-size: 12px;
  }

  .clothing-name {
    font-weight: 600;
  }

  .clothing-slot {
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    font-size: 10px;
  }

  @media (max-width: 720px) {
    .profile-header {
      grid-template-columns: 1fr;
      text-align: center;
    }

    .profile-actions {
      position: absolute;
      top: 16px;
      right: 16px;
      justify-content: flex-end;
    }

    .profile-names {
      justify-content: center;
    }

    .social-icons {
      justify-content: center;
    }

    .meta-row {
      justify-content: center;
    }

    .avatar-layout {
      grid-template-columns: 1fr;
    }

    .stats-layout {
      grid-template-columns: 1fr;
    }

    .stats-left {
      grid-template-columns: 1fr;
    }

  }

  /* -- Orders tab -- */
  .orders-exchange-btn {
    display: block;
    width: 100%;
    padding: 0.5rem 1rem;
    margin-bottom: 12px;
    background: transparent;
    border: 1px solid var(--accent-color);
    border-radius: 6px;
    color: var(--accent-color);
    font-size: 0.9rem;
    font-weight: 500;
    text-align: center;
    text-decoration: none;
    box-sizing: border-box;
    transition: background-color 0.15s, color 0.15s;
  }
  .orders-exchange-btn:hover {
    background: var(--accent-color);
    color: white;
  }
  .orders-stacked {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .orders-side {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .orders-side-title {
    margin: 0 0 8px 0;
    font-size: 13px;
    font-weight: 600;
  }
  .orders-side-title.buy { color: var(--success-color, #16a34a); }
  .orders-side-title.sell { color: var(--error-color, #ef4444); }
  .orders-table-wrap {
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
    height: 400px;
  }
  .orders-empty {
    padding: 24px;
    text-align: center;
    font-size: 13px;
    color: var(--text-muted);
    border: 1px solid var(--border-color);
    border-radius: 8px;
  }
  :global(.order-item-link) {
    color: var(--accent-color);
    text-decoration: none;
  }
  :global(.order-item-link:hover) {
    text-decoration: underline;
  }
  :global(.category-label) {
    color: var(--text-muted, #999);
    font-size: 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* Globals tab — compact stats */
  .globals-compact-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 16px;
  }

  .globals-compact-stat {
    flex: 1;
    min-width: 100px;
    padding: 10px 14px;
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    text-align: center;
    font-size: 0.8125rem;
  }

  .globals-stat-icon {
    width: 20px;
    height: 20px;
    margin-bottom: 4px;
  }

  .globals-compact-stat strong {
    display: block;
    font-size: 1.125rem;
    font-variant-numeric: tabular-nums;
  }

  .globals-compact-stat span {
    color: var(--text-muted);
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  /* Globals tab — ATH rankings */
  .globals-rankings {
    margin-bottom: 16px;
  }

  .globals-rankings-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    gap: 12px;
  }
  .globals-rankings-header h3 {
    margin: 0;
    font-size: 0.9375rem;
    font-weight: 600;
  }
  .globals-ath-toggle {
    display: flex;
    gap: 2px;
    background: var(--secondary-color);
    border-radius: 4px;
    padding: 2px;
  }
  .globals-ath-btn {
    padding: 3px 10px;
    font-size: 0.6875rem;
    font-weight: 600;
    border: none;
    border-radius: 3px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: background 0.15s, color 0.15s;
  }
  .globals-ath-btn:hover { color: var(--text-color); }
  .globals-ath-btn.active {
    background: var(--accent-color);
    color: white;
  }

  .globals-rankings-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }

  .globals-ranking-card {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
    background: var(--primary-color);
  }

  .ranking-card-header {
    padding: 6px 12px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .ranking-card-header.hunting-color { background: rgba(239, 68, 68, 0.12); color: #ef4444; }
  .ranking-card-header.mining-color  { background: rgba(96, 176, 255, 0.12); color: #60b0ff; }
  .ranking-card-header.crafting-color { background: rgba(249, 115, 22, 0.12); color: #f97316; }
  .ranking-card-header.space-mining-color { background: rgba(167, 139, 250, 0.12); color: #a78bfa; }

  .ranking-entry {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    font-size: 0.8125rem;
    border-top: 1px solid var(--border-color);
  }

  .ranking-empty {
    padding: 10px 12px;
    font-size: 0.8125rem;
    color: var(--text-muted);
    border-top: 1px solid var(--border-color);
  }

  .ranking-target {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 500;
  }

  .ranking-value {
    flex-shrink: 0;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  .ranking-badge {
    display: inline-block;
    flex-shrink: 0;
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.625rem;
    font-weight: 700;
    background: rgba(128, 128, 128, 0.15);
    color: var(--text-muted);
    white-space: nowrap;
  }

  .ranking-badge.rank-ruby,
  .ranking-badge.rank-diamond {
    position: relative;
    overflow: hidden;
  }

  .ranking-badge.rank-ruby {
    background: rgba(224, 17, 95, 0.15); color: #e0115f;
    text-shadow: 0 0 4px rgba(224, 17, 95, 0.3);
  }

  .ranking-badge.rank-diamond {
    background: rgba(185, 242, 255, 0.15); color: #b9f2ff;
    text-shadow: 0 0 4px rgba(185, 242, 255, 0.3);
  }

  .ranking-badge.rank-ruby::after,
  .ranking-badge.rank-diamond::after {
    content: '';
    position: absolute;
    top: -50%;
    left: -100%;
    width: 40%;
    height: 200%;
    transform: rotate(25deg);
    pointer-events: none;
  }

  .ranking-badge.rank-ruby::after {
    background: linear-gradient(90deg, transparent, rgba(255, 77, 141, 0.5), transparent);
    animation: rank-swipe 3s ease-in-out infinite;
  }

  .ranking-badge.rank-diamond::after {
    background: linear-gradient(90deg, transparent, rgba(224, 249, 255, 0.5), transparent);
    animation: rank-swipe 3s ease-in-out infinite 0.5s;
  }

  @keyframes rank-swipe {
    0%, 100% { left: -100%; }
    40%, 60% { left: 200%; }
  }

  .ranking-badge.rank-gold { background: rgba(234, 179, 8, 0.15); color: #eab308; }
  .ranking-badge.rank-silver { background: rgba(192, 192, 192, 0.15); color: #c0c0c0; }
  .ranking-badge.rank-bronze { background: rgba(205, 127, 50, 0.15); color: #cd7f32; }

  /* Globals tab — rare items & discoveries */
  .globals-highlights {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }

  .globals-highlight-card {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--primary-color);
    padding: 12px;
  }

  .globals-highlight-card h3 {
    margin: 0 0 8px 0;
    font-size: 0.875rem;
    font-weight: 600;
  }

  .highlight-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    font-size: 0.8125rem;
  }

  .highlight-row + .highlight-row {
    border-top: 1px solid var(--border-color);
    padding-top: 6px;
  }

  .highlight-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 500;
  }

  .highlight-value {
    flex-shrink: 0;
    font-variant-numeric: tabular-nums;
    color: var(--text-muted);
    font-size: 0.75rem;
  }

  .highlight-badge {
    flex-shrink: 0;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 0.5625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .highlight-badge.hof { background: rgba(234, 179, 8, 0.15); color: #eab308; }
  .highlight-badge.ath { background: rgba(239, 68, 68, 0.15); color: #ef4444; }

  .highlight-time {
    flex-shrink: 0;
    font-size: 0.6875rem;
    color: var(--text-muted);
    white-space: nowrap;
  }

  /* Globals tab — type filter buttons */
  .globals-compact-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 14px;
  }

  .globals-type-btn {
    padding: 5px 12px;
    font-size: 0.8125rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .globals-type-btn:hover {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .globals-type-btn.active {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: #fff;
  }

  /* Globals tab — data table */
  .globals-compact-table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: var(--secondary-color);
  }

  .globals-compact-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8125rem;
    table-layout: fixed;
  }

  .globals-compact-table .col-target { width: 35%; }
  .globals-compact-table .col-type { width: 13%; }
  .globals-compact-table .col-num { width: 13%; }

  .globals-compact-table th {
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    cursor: pointer;
    user-select: none;
  }

  .globals-compact-table th:hover {
    color: var(--text-color);
  }

  .globals-compact-table th.col-type {
    cursor: default;
  }

  .globals-compact-table td {
    padding: 8px 14px;
    border-bottom: 1px solid var(--border-color);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .globals-compact-table tr:last-child td { border-bottom: none; }

  .globals-compact-table tbody tr:nth-child(even) {
    background-color: var(--table-alt-row, rgba(255, 255, 255, 0.02));
  }

  .globals-compact-table tbody tr:hover {
    background-color: var(--hover-color);
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: -2px;
  }

  .globals-compact-table th.right,
  .globals-compact-table td.right {
    text-align: right;
  }

  .globals-compact-table .font-mono {
    font-variant-numeric: tabular-nums;
  }

  .globals-target-link {
    color: var(--text-color);
    text-decoration: none;
    font-weight: 600;
  }

  .globals-target-link:hover {
    color: var(--accent-color);
    text-decoration: underline;
  }

  /* Globals tab — type badges */
  .globals-type-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.6875rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  .globals-type-hunting       { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
  .globals-type-mining        { background: rgba(96, 176, 255, 0.15); color: #60b0ff; }
  .globals-type-space_mining  { background: rgba(167, 139, 250, 0.15); color: #a78bfa; }
  .globals-type-crafting      { background: rgba(249, 115, 22, 0.15); color: #f97316; }

  /* Globals tab — pagination */
  .globals-pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    margin-top: 12px;
  }

  .globals-pagination .page-btn {
    padding: 5px 14px;
    font-size: 0.8125rem;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .globals-pagination .page-btn:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--text-color);
  }

  .globals-pagination .page-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .globals-pagination .page-info {
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  .globals-detail-link {
    display: inline-block;
    margin-top: 12px;
    font-size: 0.8125rem;
    color: var(--accent-color);
    text-decoration: none;
  }

  .globals-detail-link:hover {
    text-decoration: underline;
  }

  .hunting-color { color: #ef4444; }
  .mining-color { color: #60b0ff; }
  .space-mining-color { color: #a78bfa; }
  .crafting-color { color: #f97316; }

  .globals-category-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 16px;
  }

  .globals-category-card {
    position: relative;
    overflow: hidden;
    padding: 12px;
    border-radius: 8px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-left: 3px solid currentColor;
  }

  .globals-category-card.hunting-color { background: rgba(239, 68, 68, 0.06); }
  .globals-category-card.mining-color { background: rgba(96, 176, 255, 0.06); }
  .globals-category-card.space-mining-color { background: rgba(167, 139, 250, 0.06); }
  .globals-category-card.crafting-color { background: rgba(249, 115, 22, 0.06); }

  .globals-cat-sparkline {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 60%;
    pointer-events: none;
    z-index: 0;
  }

  .globals-cat-sparkline path {
    fill: currentColor;
    opacity: 0.15;
  }

  .globals-cat-card-inner {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    position: relative;
    z-index: 1;
  }

  .globals-cat-card-stats { flex: 1; min-width: 0; }

  .globals-cat-value {
    display: block;
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
  }

  .globals-cat-label {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 2px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    font-weight: 600;
  }

  .globals-cat-sub {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 1px;
    font-variant-numeric: tabular-nums;
  }

  .globals-cat-card-ranks {
    display: flex;
    flex-direction: column;
    gap: 3px;
    flex-shrink: 0;
  }

  .globals-cat-rank-item {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .globals-cat-rank-item .ranking-badge {
    font-size: 0.75rem;
    padding: 2px 7px;
  }

  .globals-cat-rank-label {
    font-size: 0.6875rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    width: 36px;
  }

  .ranking-badge-count {
    opacity: 0.7;
  }

  @media (max-width: 599px) {
    .globals-compact-stats { gap: 8px; }
    .globals-compact-stat { min-width: 80px; padding: 8px 10px; }
    .globals-compact-stat strong { font-size: 1rem; }
    .globals-compact-table th,
    .globals-compact-table td { padding: 6px 8px; }
    .globals-rankings-grid { grid-template-columns: repeat(2, 1fr); }
    .globals-category-cards { grid-template-columns: repeat(2, 1fr); }
    .globals-highlights { grid-template-columns: 1fr; }
  }
</style>
