<script>
  // @ts-nocheck
  import { browser } from '$app/environment';
  import { slide } from 'svelte/transition';
  import { sanitizeHtml } from '$lib/sanitize';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import DefenseGridEdit from '$lib/components/wiki/DefenseGridEdit.svelte';
  import ImageUploadDialog from '$lib/components/wiki/ImageUploadDialog.svelte';
  import LoadoutCompactEmbed from '$lib/components/LoadoutCompactEmbed.svelte';
  import FancyTable from '$lib/components/FancyTable.svelte';
  import { clampDecimals, encodeURIComponentSafe, getTypeLink } from '$lib/util';
  import { isPercentMarkupType } from '$lib/common/itemTypes.js';
  import { formatMarkupValue } from '../../market/exchange/orderUtils';
  import { getItemCategoryPath } from '$lib/market/categorize.js';
  import { loadLoadoutEntities } from '$lib/utils/entityLoader';
  import { evaluateLoadout } from '$lib/utils/loadoutEvaluator';
  import { buildEffectCaps } from '$lib/utils/loadoutEffects';

  export let data;

  // Track the profile ID to detect when we navigate to a different profile
  let currentProfileId = null;

  // Make data-derived state reactive so it updates when navigating between profiles
  $: profile = data.profileData.profile;
  $: scores = data.profileData.scores;
  $: services = data.profileData.services || [];
  $: shops = data.profileData.shops || [];
  $: orders = data.profileData.orders || [];
  $: rentals = data.profileData.rentals || [];
  $: avatar = data.profileData.avatar || {};
  $: isOwner = data.profileData.permissions?.isOwner;
  $: society = profile?.society || null;
  $: pendingSocietyRequest = profile?.pendingSocietyRequest || null;

  // Reset UI state when profile changes
  $: if (profile?.id && profile.id !== currentProfileId) {
    currentProfileId = profile.id;
    resetUIState();
  }

  let isEditing = false;
  let saveError = '';
  let saveStatus = '';
  let tabInitialized = false;
  let imageFailed = false;
  let showImageDialog = false;
  let showSocietyDialog = false;
  let societyMode = 'join';
  let societySearchQuery = '';
  let societySearchResults = [];
  let societySearchLoading = false;
  let societySearchError = '';
  let societyCreateName = '';
  let societyCreateAbbr = '';
  let societyCreateDescription = '';
  let societyCreateDiscord = '';
  let societyActionError = '';
  let societyActionStatus = '';
  let societySearchTimeout = null;

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const isRingSlot = (slot) => /ring|finger/i.test(slot || '');

  let avatarDetailTab = 'Stats';
  let avatarTabsInitialized = false;
  let referenceLoading = false;
  let referenceError = '';
  let referenceReady = false;
  let showcaseRecord = null;
  let showcaseLoadout = null;
  let showcaseShareCode = null;
  let showcaseName = 'Showcase Loadout';
  let avatarSubTabs = [];
  let leftRing = null;
  let rightRing = null;
  let selectedClothing = [];
  let clothingEntries = [];
  let evaluation = null;
  let stats = {};
  let effectsAll = [];
  let expandedEffectKeys = new Set();
  let isHydratingShowcase = false;

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
  let clothing = [];
  let pets = [];
  let stimulants = [];
  let medicalTools = [];
  let effectsCatalog = [];
  let effectCaps = {};

  let form = {
    biographyHtml: '',
    defaultTab: 'General',
    showcaseLoadoutCode: ''
  };

  // Reset UI state when navigating to a different profile
  function resetUIState() {
    isEditing = false;
    saveError = '';
    saveStatus = '';
    tabInitialized = false;
    imageFailed = false;
    showImageDialog = false;
    showSocietyDialog = false;
    avatarTabsInitialized = false;
    referenceReady = false;
    referenceLoading = false;
    referenceError = '';
    isHydratingShowcase = false;
    expandedEffectKeys = new Set();
    // Reset form to new profile data
    form = {
      biographyHtml: profile?.biographyHtml || '',
      defaultTab: profile?.defaultTab || 'General',
      showcaseLoadoutCode: profile?.showcaseLoadoutCode || ''
    };
  }

  $: hasAvatarData = !!(form.showcaseLoadoutCode || avatar?.showcaseLoadout);
  $: hasServices = services.length > 0;
  $: hasShops = shops.length > 0;
  $: hasOrders = orders.length > 0;
  $: hasRentals = rentals.length > 0;
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
  $: buyOrders = sortOrdersByCategory(orders.filter(o => o.type === 'BUY'));
  $: sellOrders = sortOrdersByCategory(orders.filter(o => o.type === 'SELL'));

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

  $: availableTabs = [
    { id: 'General', label: 'General', available: true },
    { id: 'Avatar', label: 'Avatar', available: hasAvatarData || (isOwner && isEditing) },
    { id: 'Services', label: 'Services', available: hasServices },
    { id: 'Rentals', label: 'Rentals', available: hasRentals },
    { id: 'Shops', label: 'Shops', available: hasShops },
    { id: 'Orders', label: 'Orders', available: hasOrders }
  ].filter(tab => tab.available);

  let activeTab = 'General';

  $: if (!tabInitialized && availableTabs.length > 0) {
    const desired = profile.defaultTab || 'General';
    activeTab = availableTabs.find(tab => tab.id === desired)?.id || availableTabs[0].id;
    tabInitialized = true;
  }

  $: if (tabInitialized && !availableTabs.find(tab => tab.id === activeTab)) {
    activeTab = availableTabs[0]?.id || 'General';
  }

  $: showcaseRecord = avatar?.showcaseLoadout || null;
  $: showcaseLoadoutRaw = showcaseRecord?.data || null;
  $: showcaseLoadout = resolveDefaultSets(showcaseLoadoutRaw);
  $: showcaseShareCode = showcaseRecord?.share_code || showcaseRecord?.shareCode || null;
  $: showcaseName = showcaseRecord?.name || showcaseLoadout?.Name || 'Showcase Loadout';

  $: avatarSubTabs = [
    { id: 'Stats', label: 'Detailed Stats' },
    { id: 'Weapons', label: 'Weapons' },
    { id: 'Armor', label: 'Armor' },
    { id: 'Healing', label: 'Healing' },
    { id: 'Accessories', label: 'Rings, Clothing & Pet' }
  ];

  $: if (!avatarTabsInitialized && avatarSubTabs.length > 0) {
    avatarDetailTab = 'Stats';
    avatarTabsInitialized = true;
  }

  $: if (avatarTabsInitialized && !avatarSubTabs.find(tab => tab.id === avatarDetailTab)) {
    avatarDetailTab = avatarSubTabs[0]?.id || 'Stats';
  }

  $: profileSlug = profile.euName ? encodeURIComponentSafe(profile.euName) : profile.id;
  $: displayImageUrl = imageFailed
    ? profile.discordAvatarUrl
    : (profile.profileImageUrl || profile.discordAvatarUrl);

  $: clothingEntries = (showcaseLoadout?.Gear?.Clothing || []).map(entry => (
    typeof entry === 'string' ? { Name: entry } : entry
  ));
  $: leftRing = clothingEntries.length ? getClothingSlot('Ring', 'Left') : null;
  $: rightRing = clothingEntries.length ? getClothingSlot('Ring', 'Right') : null;
  $: selectedClothing = clothingEntries.filter(item => !isRingSlot(item?.Slot));
  $: evaluation = showcaseLoadout
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
  $: stats = evaluation?.stats || {};
  $: effectsAll = evaluation?.effects?.all || [];
  $: defenseBreakdown = {
    ...(stats.totalDefenseByType || {}),
    Block: stats.blockChance ?? 0
  };

  $: if (showcaseLoadout && browser && !referenceReady && !referenceLoading) {
    loadAvatarReferences();
  }

  $: if (browser && showcaseRecord && !showcaseRecord?.data && showcaseShareCode && !isHydratingShowcase) {
    hydrateShowcaseLoadout(showcaseShareCode);
  }

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
        return href
          ? `<a class="order-item-link" href="${escapeHtml(href)}">${label}</a>`
          : label;
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

  $: ordersPageUrl = profile?.euName
    ? `/market/exchange/orders/${encodeURIComponentSafe(profile.euName)}`
    : null;

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
      showcaseLoadoutCode: profile.showcaseLoadoutCode || ''
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
          showcaseLoadoutCode: form.showcaseLoadoutCode || null
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
        showcaseLoadoutCode: payload.profile.showcaseLoadoutCode
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
</script>

<svelte:head>
  <title>{profile.euName || profile.discordName} | User Profile</title>
  <meta name="description" content="User profile for {profile.euName || profile.discordName} on Entropia Nexus." />
</svelte:head>

<div class="profile-page">
  <div class="profile-header">
    <div class="profile-image">
      <button class="profile-image-button" type="button" on:click={openImageDialog} class:editable={isOwner && isEditing}>
        {#if displayImageUrl}
          <img src={displayImageUrl} alt={profile.euName || profile.discordName} on:error={() => (imageFailed = true)} />
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
            <button class="btn btn-secondary btn-small society-action" on:click={() => { showSocietyDialog = true; societyActionError = ''; societyActionStatus = ''; }}>
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
          <button class="btn btn-primary" on:click={saveProfile}>Save</button>
          <button class="btn btn-secondary" on:click={cancelEdit}>Cancel</button>
        {:else}
          <button class="btn btn-primary edit-icon-btn" on:click={startEdit} title="Edit Profile" aria-label="Edit Profile">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
            </svg>
          </button>
        {/if}
      </div>
    {/if}
  </div>

  <div class="profile-tabs">
    {#each availableTabs as tab}
      <button class:active={activeTab === tab.id} on:click={() => activeTab = tab.id}>{tab.label}</button>
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
        </div>
      </section>

      <section class="panel-section">
        <h2>Biography</h2>
        {#if isEditing}
          <RichTextEditor bind:content={form.biographyHtml} placeholder="Write a short bio..." />
        {:else if profile.biographyHtml}
          <div class="bio-content">{@html sanitizeHtml(profile.biographyHtml)}</div>
        {:else}
          <div class="empty-state">No biography yet.</div>
        {/if}
      </section>

      {#if isEditing}
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
            <label>Showcase Loadout</label>
            <select bind:value={form.showcaseLoadoutCode}>
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
                  <button class:active={avatarDetailTab === tab.id} on:click={() => avatarDetailTab = tab.id}>
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
  <div class="dialog-backdrop" on:click={() => showSocietyDialog = false} on:keydown={(e) => e.key === 'Escape' && (showSocietyDialog = false)}>
    <div class="dialog dialog-compact" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="society-dialog-title">
      <div class="dialog-header">
        <h3 id="society-dialog-title">{societyMode === 'join' ? 'Join a Society' : 'Create a Society'}</h3>
        <button class="close-btn" on:click={() => showSocietyDialog = false} aria-label="Close dialog">&#10005;</button>
      </div>
      <div class="dialog-body">
        <div class="mode-toggle">
          <button class:active={societyMode === 'join'} on:click={() => societyMode = 'join'}>Join</button>
          <button class:active={societyMode === 'create'} on:click={() => societyMode = 'create'}>Create</button>
        </div>

        {#if societyMode === 'join'}
          <div class="field-group">
            <label>Search Societies</label>
            <input type="text" placeholder="Type to search..." value={societySearchQuery} on:input={(e) => handleSocietySearchInput(e.target.value)} />
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
                    <button class="dialog-btn" on:click={() => handleJoinSociety(item)}>Request Join</button>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {:else}
          <div class="field-group">
            <label>Society Name</label>
            <input type="text" bind:value={societyCreateName} placeholder="Society name" />
          </div>
          <div class="field-group">
            <label>Abbreviation</label>
            <input type="text" bind:value={societyCreateAbbr} placeholder="Short tag (optional)" />
          </div>
            <div class="field-group">
              <label>Description</label>
              <RichTextEditor bind:content={societyCreateDescription} placeholder="Short description" />
            </div>
            <div class="field-group">
              <label>Discord</label>
              <input type="text" bind:value={societyCreateDiscord} placeholder="Invite link or code (optional)" />
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
        <button class="dialog-btn secondary" on:click={() => showSocietyDialog = false}>Close</button>
        {#if societyMode === 'create'}
          <button class="dialog-btn" on:click={handleCreateSociety} disabled={!societyCreateName.trim()}>Create Society</button>
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
  on:close={() => (showImageDialog = false)}
  on:uploaded={(event) => {
    if (event.detail?.imageUrl) {
      profile = { ...profile, profileImageUrl: event.detail.imageUrl, hasCustomImage: true };
      imageFailed = false;
      saveStatus = 'Profile image updated.';
    }
  }}
  on:deleted={() => {
    profile = { ...profile, profileImageUrl: null, hasCustomImage: false };
    imageFailed = false;
    saveStatus = 'Profile image removed.';
  }}
/>

<style>
  .profile-page {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 20px 60px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .profile-header {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 24px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #444);
    border-radius: 16px;
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

  .profile-names h1 {
    margin: 0;
    font-size: 26px;
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
    flex-wrap: wrap;
    gap: 8px;
  }

  .profile-tabs button {
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #444);
    background: var(--bg-color, #111);
    color: var(--text-color);
    cursor: pointer;
  }

  .profile-tabs button.active {
    background: var(--accent-color, #4a9eff);
    border-color: transparent;
    color: #fff;
  }

  .profile-tab-panel {
    background: var(--secondary-color);
    border-radius: 16px;
    border: 1px solid var(--border-color, #444);
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
</style>
