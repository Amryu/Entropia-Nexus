<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import HealingServicesList from '$lib/components/services/HealingServicesList.svelte';
  import DPSServicesList from '$lib/components/services/DPSServicesList.svelte';
  import TransportationServicesList from '$lib/components/services/TransportationServicesList.svelte';
  import NavList from "$lib/components/NavList.svelte";
  import AvailabilityCalendar from "$lib/components/services/AvailabilityCalendar.svelte";
  import TicketOfferCard from '$lib/components/services/TicketOfferCard.svelte';
  import LocationManager from '$lib/components/services/LocationManager.svelte';
  import PilotManager from '$lib/components/services/PilotManager.svelte';
  import LoginToCreateButton from '$lib/components/LoginToCreateButton.svelte';
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount, onDestroy, untrack } from 'svelte';
  import { getTypeLink, apiPost, encodeURIComponentSafe } from '$lib/util';
  import { addToast } from '$lib/stores/toasts';
  import { sanitizeMarketHtml } from '$lib/sanitize';
  import {
    canRestoreFlight,
    formatFlightTime,
    canCheckIn
  } from '$lib/utils/flightUtils';
  import {
    getHealingReloadSpeedBonus,
    getEstimatedHealingHPS,
    getMaxHealingDecayPerHour,
    getHealingCostLabel,
    getClothingSlot,
    getLocationDisplay,
    getHealingEnhancerBonus,
    getDPSReloadSpeedBonus,
    getDPSDamageBonus,
    getDPSCritChanceBonus,
    getDPSCritDamageBonus,
    getTotalHP,
    getProtectionStats,
    getEstimatedDPS,
    getMaxCostPerHour
  } from '$lib/components/services/serviceCalculations';
  import * as LoadoutCalc from '$lib/utils/loadoutCalculations';
  import { loadAllServiceEntities, loadServiceTypeEntities } from '$lib/utils/entityLoader';

  let { data } = $props();


  // Entity data - lazy loaded on client
  let clothingItems = $state([]);
  let medicalTools = $state([]);
  let medicalChips = $state([]);
  let armorSets = $state([]);
  let consumables = $state([]);
  let weapons = $state([]);
  let pets = $state([]);
  let armors = $state([]);
  let armorPlatings = $state([]);
  let weaponAmplifiers = $state([]);
  let absorbers = $state([]);
  let weaponVisionAttachments = $state([]);
  let mindforceImplants = $state([]);
  let entitiesLoading = $state(true);


  // Ticket offers for transportation services
  let ticketOffers = $state([]);
  let upcomingFlights = $state([]);
  let purchasingTicket = false;
  let mounted = $state(false);
  let showAllFlights = $state(false); // For expandable flight list
  let flightUpdateInterval = $state(null);


  // Load entity data on mount
  async function loadEntities() {
    entitiesLoading = true;
    try {
      const entities = await loadAllServiceEntities();
      clothingItems = entities.clothings || [];
      medicalTools = entities.medicalTools || [];
      medicalChips = entities.medicalChips || [];
      armorSets = entities.armorSets || [];
      consumables = entities.consumables || [];
      weapons = entities.weapons || [];
      pets = entities.pets || [];
      armors = entities.armors || [];
      armorPlatings = entities.armorPlatings || [];
      weaponAmplifiers = entities.weaponAmplifiers || [];
      absorbers = entities.absorbers || [];
      weaponVisionAttachments = entities.weaponVisionAttachments || [];
      mindforceImplants = entities.mindforceImplants || [];
    } catch (error) {
      console.error('Failed to load entity data:', error);
    } finally {
      entitiesLoading = false;
    }
  }

  onMount(() => {
    mounted = true;
    loadEntities();
  });

  onDestroy(() => {
    // Clear flight update interval when component is destroyed
    if (flightUpdateInterval) {
      clearInterval(flightUpdateInterval);
      flightUpdateInterval = null;
    }
  });

  function getProfileUrl(user) {
    if (!user) return null;
    return `/users/${encodeURIComponentSafe(String(user.eu_name || user.id))}`;
  }

  // Function to fetch upcoming flights
  async function fetchUpcomingFlights() {
    if (!selectedService?.id || selectedService?.type !== 'transportation') {
      return;
    }

    try {
      const response = await fetch(`/api/services/${selectedService.id}/flights?upcoming=true`);
      const flights = await response.json();
      upcomingFlights = Array.isArray(flights) ? flights : [];
    } catch (e) {
      // Silently fail for polling updates
      console.error('Failed to fetch flights:', e);
    }
  }



  // Restore a cancelled flight
  async function restoreFlight(flightId) {
    const flight = upcomingFlights.find(f => f.id === flightId);
    if (!flight) return;

    // Check if can restore (grace period and overlap validation)
    if (!canRestoreFlight(flight, activeFlights)) {
      addToast('Cannot restore this flight - it overlaps within 15 minutes of another active flight.', { type: 'error' });
      return;
    }

    if (!confirm('Restore this cancelled flight?')) return;

    try {
      const response = await fetch(`/api/services/${selectedService.id}/flights/${flightId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'restore' })
      });

      const result = await response.json();
      if (result.error) {
        addToast(result.error, { type: 'error' });
      } else {
        addToast('Flight restored successfully!', { type: 'success' });
        // Refresh flights list immediately
        await fetchUpcomingFlights();
      }
    } catch (e) {
      addToast('Failed to restore flight. Please try again.', { type: 'error' });
    }
  }

  // Check if user already has a ticket for this service
  async function checkExistingTicket() {
    try {
      const response = await fetch(`/api/services/${selectedService.id}/tickets/my`);
      const result = await response.json();
      return result && result.ticket ? result.ticket : null;
    } catch (e) {
      return null;
    }
  }

  async function handlePurchaseTicket(offer) {
    if (!user) {
      goto('/discord/login?redirect=/market/services/' + selectedService.id);
      return;
    }

    // Check if user already has a ticket for this service
    const existingTicket = await checkExistingTicket();
    if (existingTicket && !user.grants?.includes('admin.panel')) {
      addToast('You already have a ticket for this service. You can only have one active ticket at a time.', { type: 'warning' });
      return;
    }

    // Confirmation dialog
    let confirmMessage = `Purchase "${offer.name}" for ${parseFloat(offer.price).toFixed(2)} PED?`;
    if (user.grants?.includes('admin.panel') && selectedService.user_id === user.id) {
      confirmMessage += '\n\nNote: You are purchasing a ticket for your own service as an administrator (for testing purposes).';
    }

    if (!confirm(confirmMessage)) {
      return;
    }

    purchasingTicket = true;
    try {
      const result = await apiPost(fetch, `/api/services/${selectedService.id}/tickets/purchase`, {
        offer_id: offer.id
      });
      if (result.error) {
        addToast(result.error, { type: 'error' });
      } else {
        addToast('Ticket purchased successfully! It will be activated when the provider accepts your first check-in.', { type: 'success' });
      }
    } catch (e) {
      addToast('Failed to purchase ticket. Please try again.', { type: 'error' });
    } finally {
      purchasingTicket = false;
    }
  }

  function handleEditTicketOffer() {
    goto(`/market/services/${selectedService.id}/ticket-offers`);
  }

  // Check-in dialog state
  let showCheckinDialog = $state(false);
  let checkinFlight = $state(null);
  let checkinLocation = $state('');
  let checkinPlanetId = $state(null);
  let checkinExitLocation = $state('');
  let checkinExitPlanetId = $state(null);
  let checkinSubmitting = $state(false);

  function openCheckinDialog(flight) {
    if (!user) {
      goto('/discord/login?redirect=/market/services/' + selectedService.id);
      return;
    }
    checkinFlight = flight;
    checkinLocation = '';
    checkinPlanetId = null;
    checkinExitLocation = '';
    checkinExitPlanetId = null;
    showCheckinDialog = true;
  }

  function closeCheckinDialog() {
    showCheckinDialog = false;
    checkinFlight = null;
    checkinLocation = '';
    checkinPlanetId = null;
    checkinExitLocation = '';
    checkinExitPlanetId = null;
    checkinSubmitting = false;
  }

  // Get current state description for running flight
  function getFlightCurrentState(flight) {
    if (!flight || flight.status !== 'running') return '';

    const routeStops = typeof flight.route_stops === 'string'
      ? JSON.parse(flight.route_stops)
      : (flight.route_stops || []);

    if (flight.current_state === 'departing') {
      return 'Departing from start';
    }

    if (flight.current_state?.startsWith('at_stop_')) {
      const stopNum = parseInt(flight.current_state.split('_')[2]);
      const stop = routeStops[stopNum];
      return `Currently at ${stop?.name || 'Unknown'}`;
    }

    if (flight.current_state?.startsWith('warp_to_')) {
      const stopNum = parseInt(flight.current_state.split('_')[2]);
      const stop = routeStops[stopNum];
      return `In warp to ${stop?.name || 'Unknown'}`;
    }

    return 'In transit';
  }

  async function submitCheckin() {
    if (!checkinFlight) return;

    // Check if user has a ticket
    const ticket = await checkExistingTicket();
    if (!ticket) {
      addToast('You need a ticket to check in. Please purchase a ticket first.', { type: 'warning' });
      return;
    }

    checkinSubmitting = true;
    try {
      const response = await fetch(`/api/flights/${checkinFlight.id}/checkin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket_id: ticket.id,
          join_location: checkinLocation,
          join_planet_id: checkinPlanetId,
          exit_location: checkinExitLocation || null,
          exit_planet_id: checkinExitPlanetId || null
        })
      });

      const result = await response.json();
      if (result.error) {
        addToast(result.error, { type: 'error' });
      } else {
        addToast('Check-in submitted! The provider will review your request.', { type: 'success' });
        closeCheckinDialog();
      }
    } catch (e) {
      addToast('Failed to submit check-in. Please try again.', { type: 'error' });
    } finally {
      checkinSubmitting = false;
    }
  }

  // State for active medical tool and consumable toggles
  let activeMedicalEquipment = $state(null);
  let enabledConsumables = $state({}); // Track each consumable individually by item_name
  let enabledTierEnhancers = $state({}); // Track tier enhancer slots for equipment with tiers

  // State for DPS services
  let activeWeapon = $state(null);
  let selectedAmplifier = $state(null);
  let selectedAbsorber = $state(null);
  let selectedScope = $state(null);
  let selectedScopeSight = $state(null);
  let selectedSight = $state(null);
  let selectedMatrix = $state(null);
  let selectedImplant = $state(null);
  let activePet = null; // Only one pet can be active
  let activePetEffects = $state({}); // Map of pet names to active state
  let playerHP = 150; // Player's configured base HP


  // Helper to check if equipment is active in calculations
  function isEquipmentActive(equip) {
    if (equip.item_type === 'medicaltools' || equip.item_type === 'medicalchips') {
      // Medical is active if it's the selected tool
      const isMedicalActive = activeMedicalEquipment?.item_name === equip.item_name;
      return isMedicalActive;
    }
    if (equip.item_type === 'consumables') {
      return enabledConsumables[equip.item_name] === true;
    }
    // Armor and clothing are active if primary AND tier enhancers enabled (if has tiers)
    if (equip.is_primary !== false) {
      if (equip.tier && equip.tier > 0) {
        return enabledTierEnhancers[equip.item_name] === true;
      }
      return true;
    }
    return false;
  }

  const CATEGORY_SLUGS = ['healing', 'dps', 'transportation', 'custom'];

  let currentType = $state('healing');
  let selectedPlanetId = $state(null);

  // Initialize from URL slug or localStorage
  if (typeof window !== 'undefined') {
    const slug = $page.params.slug;
    if (slug && CATEGORY_SLUGS.includes(slug)) {
      // URL has a category slug — use it and save to localStorage
      currentType = slug;
      localStorage.setItem('lastServiceType', slug);
    } else if (!slug) {
      // No slug — redirect to saved or default category
      const saved = localStorage.getItem('lastServiceType');
      const cat = (saved && CATEGORY_SLUGS.includes(saved)) ? saved : 'healing';
      goto(`/market/services/${cat}`, { replaceState: true });
    }
    // If slug is a number (service detail), currentType stays at default (detail view renders instead)

    const savedPlanet = localStorage.getItem('lastServicePlanet');
    if (savedPlanet) {
      selectedPlanetId = savedPlanet === 'all' ? null : parseInt(savedPlanet);
    }
  }

  let showRequestModal = $state(false);
  let requestMessage = $state('');
  let selectedDate = '';
  let selectedTime = '';
  let requestPlanetId = $state(null);
  let requestDestinationPlanetId = $state(null);
  let requestError = $state('');
  let requestSubmitting = $state(false);
  let requestFormTab = $state('request'); // 'request' or 'question'
  let questionMessage = $state('');

  const serviceTypeOptions = [
    { value: 'healing', label: 'Healing' },
    { value: 'dps', label: 'DPS' },
    { value: 'transportation', label: 'Taxi/Warp' },
    { value: 'custom', label: 'Custom' }
  ];





  // Check if user has a ticket or single-use option available
  let userHasTicket = $state(false);
  let hasSingleUseOffer = $state(false);


  async function openRequestModal(tab = 'request') {
    if (!user) {
      goto(`/discord/login?redirect=${encodeURIComponent($page.url.pathname + $page.url.search)}`);
      return;
    }

    // For transportation services, check if user has a ticket (but don't block opening)
    if (selectedService?.type === 'transportation' && tab === 'request') {
      const existingTicket = await checkExistingTicket();
      userHasTicket = !!existingTicket;
    } else {
      userHasTicket = true; // Not transportation or asking question
    }

    showRequestModal = true;
    requestMessage = '';
    selectedDate = '';
    selectedTime = '';
    requestPlanetId = selectedService?.planet_id || null;
    requestError = '';
    requestFormTab = tab;
    questionMessage = '';
  }

  function closeRequestModal() {
    showRequestModal = false;
    requestMessage = '';
    selectedDate = '';
    requestPlanetId = null;
    requestDestinationPlanetId = null;
    requestFormTab = 'request';
    questionMessage = '';
    selectedTime = '';
    requestError = '';
    requestSubmitting = false;
  }

  async function submitRequest() {
    // Only transportation services support request submission now
    if (selectedService?.type !== 'transportation') {
      requestError = 'Only transportation services support flight requests. Use "Ask a Question" for other inquiries.';
      return;
    }

    // Allow admins to request their own services for testing
    if (user.id === selectedService.user_id && !user.grants?.includes('admin.panel')) {
      requestError = 'You cannot request your own service. This is a preview of how customers see your service.';
      return;
    }

    // Validation for transportation services
    if (!requestPlanetId || !requestDestinationPlanetId) {
      requestError = 'Both pickup and destination planets are required for flight requests.';
      return;
    }
    if (requestPlanetId === requestDestinationPlanetId) {
      requestError = 'Pickup and destination planets must be different.';
      return;
    }

    requestError = '';
    requestSubmitting = true;

    try {
      const response = await apiPost(fetch, `/api/services/${selectedService.id}/on-demand-request`, {
        customer_planet_id: requestPlanetId,
        dropoff_location: requestDestinationPlanetId?.toString(),
        requested_start: selectedDate && selectedTime ? `${selectedDate}T${selectedTime}:00` : null,
        message: requestMessage
      });

      if (response.error) {
        requestError = response.error;
        return;
      }

      closeRequestModal();
      goto('/market/services/my/requests');
    } catch (e) {
      requestError = 'Failed to submit request. Please try again.';
    } finally {
      requestSubmitting = false;
    }
  }

  async function submitQuestion() {
    requestError = '';
    requestSubmitting = true;

    try {
      const response = await apiPost(fetch, `/api/services/${selectedService.id}/question`, {
        message: questionMessage
      });

      if (response.error) {
        requestError = response.error;
        return;
      }

      closeRequestModal();
      // Redirect to the new request so user can see the Discord thread when it's created
      goto(`/market/services/my/requests/${response.request.id}`);
    } catch (e) {
      requestError = 'Failed to send question. Please try again.';
    } finally {
      requestSubmitting = false;
    }
  }
  
  function getItemTypeLabel(type) {
    const labels = {
      medicaltools: 'Medical Tool',
      medicalchips: 'Medical Chip',
      clothings: 'Clothing/Accessory',
      consumables: 'Consumable',
      weapons: 'Weapon',
      armors: 'Armor',
      armorsets: 'Armor Set'
    };
    return labels[type] || type;
  }

  function getServiceTypeLabel(type) {
    const labels = {
      healing: 'Healing',
      dps: 'DPS',
      transportation: 'Transportation',
      custom: 'Custom'
    };
    return labels[type] || type;
  }
  
  function getItemInternalUrl(itemType, itemName) {
    if (!itemName) return '#';

    // Remove tier info from name
    const cleanName = itemName.replace(/\s*Tier\s*\d+/i, '').trim();

    // Map service item types to internal property types
    const typeMap = {
      'weapons': 'Weapon',
      'armorsets': 'Armor',
      'medicaltools': 'MedicalTool',
      'medicalchips': 'MedicalChip',
      'clothings': 'Clothing',
      'consumables': 'Consumable',
      'pets': 'Pet'
    };

    const propertyType = typeMap[itemType];
    if (!propertyType) return '#';

    return getTypeLink(cleanName, propertyType);
  }

  // Helper to generate URLs for attachment types
  function getAttachmentUrl(attachmentType, attachmentName) {
    if (!attachmentName) return '#';
    const cleanName = attachmentName.replace(/\s*Tier\s*\d+/i, '').trim();

    const attachmentTypeMap = {
      'amplifier': 'WeaponAmplifier',
      'absorber': 'Absorber',
      'scope': 'WeaponVisionAttachment',
      'sight': 'WeaponVisionAttachment',
      'scope_sight': 'WeaponVisionAttachment',
      'matrix': 'WeaponAmplifier',
      'implant': 'MindforceImplant',
      'plate': 'ArmorPlating'
    };

    const type = attachmentTypeMap[attachmentType];
    if (!type) return '#';

    return getTypeLink(cleanName, type);
  }

  // State for attachment details dialog
  let showAttachmentDialog = $state(false);
  let attachmentDialogData = $state(null);

  function openAttachmentDialog(equip) {
    attachmentDialogData = {
      item: equip,
      attachments: equip.attachments || {}
    };
    showAttachmentDialog = true;
  }

  function closeAttachmentDialog() {
    showAttachmentDialog = false;
    attachmentDialogData = null;
  }

  // Check if equipment has any attachments worth showing
  function hasAttachments(equip) {
    const att = equip.attachments;
    if (!att) return false;

    // Check for ranged weapon attachments
    if (att.amplifier_name || att.scope_name || att.sight_name || att.absorber_name || att.scope_sight_name) return true;
    // Check for melee weapon attachments
    if (att.matrix_name) return true;
    // Check for mindforce attachments
    if (att.implant_name) return true;
    // Check for armor attachments
    if (att.plate_name) return true;

    return false;
  }

  // Count number of attachments on equipment
  function countAttachments(equip) {
    const att = equip.attachments;
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
  
  function importAsLoadout(weaponEquipment) {
    if (typeof localStorage === 'undefined') {
      addToast('Loadout manager requires browser storage.', { type: 'warning' });
      return;
    }
    
    // Get existing loadouts
    let loadouts = localStorage.getItem('loadouts') ? JSON.parse(localStorage.getItem('loadouts')) : [];
    
    // Helper to create armor object
    let newArmorObject = () => ({
      Name: null,
      Plate: null
    });
    
    // Get primary armor and clothing from service equipment
    const primaryArmorSet = selectedService.equipment.find(e => e.item_type === 'armorsets' && e.is_primary);
    const primaryClothing = selectedService.equipment.filter(e => e.item_type === 'clothings' && e.is_primary);
    
    // Create new loadout
    const newLoadout = {
      Id: Math.random().toString(16).slice(3),
      Name: `${selectedService.title} - ${weaponEquipment.item_name}`,
      Properties: {
        BonusDamage: 0,
        BonusCritChance: 0,
        BonusCritDamage: 0,
        BonusReload: 0
      },
      Gear: {
        Weapon: {
          Name: weaponEquipment.item_name,
          Amplifier: null,
          Scope: null,
          Sight: null,
          Absorber: null,
          Implant: null,
          Enhancers: {
            Damage: 0,
            Accuracy: 0,
            Range: 0,
            Economy: 0,
            SkillMod: 0,
          }
        },
        Armor: {
          SetName: primaryArmorSet ? primaryArmorSet.item_name : null,
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
        Clothing: primaryClothing.map(c => ({
          Name: c.item_name,
          Effect: null // Will be populated based on item properties
        })),
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
    
    // Add to loadouts
    loadouts.push(newLoadout);
    localStorage.setItem('loadouts', JSON.stringify(loadouts));
    
    // Redirect to loadout manager
    goto('/tools/loadouts');
  }
  let services = $derived(data.services || []);
  let servicesByType = $derived(data.servicesByType || { healing: [], dps: [], transportation: [], custom: [] });
  let planets = $derived(data.planets || []);
  let selectedService = $derived(data.service);
  let availability = $derived(data.availability || []);
  let activeRequest = $derived(data.activeRequest);
  let user = $derived(data.session?.user);
  let isOwner = $derived(user && selectedService && (user.id === selectedService.user_id || user.id === selectedService.owner_user_id || user.grants?.includes('admin.panel')));
  let pilots = $derived(data.pilots || []);
  // Check if user can manage flights (owner, pilot, or admin)
  let canManageFlights = $derived(isOwner || (user && selectedService && pilots.some(p => p.user_id === user.id)));
  // Filter to main planets only for transportation services
  let mainPlanets = $derived(planets.filter(p => p.Id >= 1 && p.Id <= 7));
  // Fetch ticket offers when a transportation service is selected (client-side only)
  $effect(() => {
    if (mounted && selectedService?.type === 'transportation' && selectedService?.id) {
      fetch(`/api/services/${selectedService.id}/ticket-offers`)
        .then(r => r.json())
        .then(offers => { ticketOffers = Array.isArray(offers) ? offers : []; })
        .catch(() => { ticketOffers = []; });

      // Fetch upcoming flights immediately
      fetchUpcomingFlights();

      // Clear any existing interval
      if (untrack(() => flightUpdateInterval)) {
        clearInterval(untrack(() => flightUpdateInterval));
      }

      // Set up polling to update flights every 15 seconds
      flightUpdateInterval = setInterval(() => {
        fetchUpcomingFlights();
      }, 15000);
    } else {
      ticketOffers = [];
      upcomingFlights = [];

      // Clear interval when not viewing transportation service
      if (untrack(() => flightUpdateInterval)) {
        clearInterval(untrack(() => flightUpdateInterval));
        flightUpdateInterval = null;
      }
    }
  });
  // Computed: separate running, scheduled, and cancelled flights
  let runningFlights = $derived(upcomingFlights.filter(f => f.status === 'running'));
  let scheduledFlights = $derived(upcomingFlights.filter(f => (f.status === 'scheduled' || f.status === 'boarding') && f.status !== 'cancelled'));
  let activeFlights = $derived(upcomingFlights.filter(f => f.status !== 'cancelled'));
  let cancelledFlights = $derived(upcomingFlights.filter(f => f.status === 'cancelled'));
  let nextActiveFlight = $derived(activeFlights[0] || null);
  // Reset active tool and consumables when service changes
  $effect(() => {
    if (selectedService) {
      const medicalEquipment = selectedService.equipment?.filter(e => 
        e.is_primary !== false && (e.item_type === 'medicaltools' || e.item_type === 'medicalchips')
      ) || [];
      
      // Set active to primary or first available
      const primary = medicalEquipment.find(e => e.is_primary);
      activeMedicalEquipment = primary || medicalEquipment[0] || null;

      // Initialize consumables state - enhancers ON, others OFF
      enabledConsumables = {};
      const allConsumables = selectedService.equipment?.filter(e => e.item_type === 'consumables') || [];
      for (const consumable of allConsumables) {
        const consumableData = consumables.find(item => item.Name === consumable.item_name);
        const isEnhancer = consumableData?.Properties?.Type === 'Enhancer';
        enabledConsumables[consumable.item_name] = isEnhancer;
      }
      
      // Initialize tier enhancers state - ON by default for all equipment with tier > 0
      enabledTierEnhancers = {};
      const allEquipment = selectedService.equipment || [];
      for (const equip of allEquipment) {
        if (equip.tier && equip.tier > 0) {
          enabledTierEnhancers[equip.item_name] = true;
        }
      }
      
      // Initialize DPS-specific state if DPS service
      if (selectedService.type === 'dps') {
        // Find primary weapon equipment entry
        const weaponEquipment = selectedService.equipment?.filter(e => 
          e.is_primary !== false && e.item_type === 'weapons'
        ) || [];
        const primaryWeaponEquip = weaponEquipment.find(e => e.is_primary) || weaponEquipment[0] || null;
        
        // Look up the actual weapon data from the weapons array
        if (primaryWeaponEquip?.item_name && weapons.length > 0) {
          const weaponData = weapons.find(w => w.Name === primaryWeaponEquip.item_name);
          if (weaponData) {
            activeWeapon = weaponData;
          } else {
            activeWeapon = null;
          }
        } else {
          activeWeapon = null;
        }
        
        // Initialize weapon attachments from saved data
        const attachments = primaryWeaponEquip?.attachments || {};
        
        selectedAmplifier = attachments.amplifier_id 
          ? weaponAmplifiers.find(a => a.ItemId === attachments.amplifier_id) || null
          : null;
        
        selectedAbsorber = attachments.absorber_id
          ? absorbers.find(a => a.ItemId === attachments.absorber_id) || null
          : null;
        
        selectedScope = attachments.scope_id
          ? weaponVisionAttachments.find(v => v.ItemId === attachments.scope_id) || null
          : null;
        
        selectedSight = attachments.sight_id
          ? weaponVisionAttachments.find(v => v.ItemId === attachments.sight_id) || null
          : null;

        // Load scope sight (nested attachment on scope)
        selectedScopeSight = attachments.scope_sight_id
          ? weaponVisionAttachments.find(v => v.ItemId === attachments.scope_sight_id) || null
          : null;

        // Load matrix (melee weapon amplifier)
        selectedMatrix = attachments.matrix_id
          ? weaponAmplifiers.find(a => a.ItemId === attachments.matrix_id && a.Properties?.Type === 'Matrix') || null
          : null;

        // Load implant (mindforce weapon attachment)
        selectedImplant = attachments.implant_id
          ? mindforceImplants.find(i => i.ItemId === attachments.implant_id) || null
          : null;
        
        // Initialize pet state - all OFF by default
        activePetEffects = {};
        const allPets = selectedService.equipment?.filter(e => e.item_type === 'pets') || [];
        for (const pet of allPets) {
          activePetEffects[pet.item_name] = false;
        }
      }
    }
  });
  // Update currentType reactively when navigating between category slugs
  $effect(() => {
    const slug = $page.params.slug;
    if (slug && CATEGORY_SLUGS.includes(slug)) {
      currentType = slug;
    }
  });
  // Save selected service type and planet to localStorage
  $effect(() => {
    if (typeof localStorage !== 'undefined' && currentType) {
      localStorage.setItem('lastServiceType', currentType);
    }
  });
  $effect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('lastServicePlanet', selectedPlanetId === null ? 'all' : selectedPlanetId.toString());
    }
  });
  // Filter services by planet
  let currentServices = $derived((() => {
    let list = servicesByType[currentType] || [];
    
    // Apply planet filter
    if (selectedPlanetId !== null) {
      list = list.filter(s => 
        s.planet_id === selectedPlanetId || s.willing_to_travel
      );
    }
    
    return list;
  })());
  $effect(() => {
    if (selectedService?.type === 'transportation' && ticketOffers) {
      hasSingleUseOffer = ticketOffers.some(offer => offer.uses_count === 1);
    }
  });
</script>

<svelte:head>
  <title>{selectedService ? `${selectedService.title} - ` : ''}Services - Market - Entropia Nexus</title>
  <meta name="description" content="Find healing, DPS, and transportation services from other players in Entropia Universe." />
</svelte:head>

<div class="scroll-container">
  <div class="page-container">
    <div class="breadcrumb">
      <a href="/market">Market</a>
      <span>/</span>
      {#if selectedService}
        <a href="/market/services">Services</a>
        <span>/</span>
        <span>{selectedService.title}</span>
      {:else}
        <span>Services</span>
      {/if}
    </div>

    <div class="page-header">
      <div class="header-left">
        <h1>{selectedService ? selectedService.title : 'Services'}</h1>
        {#if selectedService}
          <div class="header-badges">
            <span class="service-type-badge">{getServiceTypeLabel(selectedService.type)}</span>
            {#if !selectedService.is_active}
              <span class="inactive-badge">Inactive</span>
            {:else if selectedService.is_busy}
              <span class="busy-badge">Busy</span>
            {/if}
          </div>
        {:else}
          <p class="subtitle">Find healing, DPS, and transportation services</p>
        {/if}
      </div>
      <div class="header-actions">
        {#if !selectedService}
          {#if user?.verified}
            <a href="/market/services/my" class="btn-secondary">My Services</a>
            <a href="/market/services/create" class="btn-primary">Create Service</a>
          {:else}
            <LoginToCreateButton {user} label="Login to create service" createUrl="/market/services/create" />
          {/if}
        {/if}
        {#if selectedService && user}
          {#if isOwner}
            <a href="/market/services/{selectedService.id}/edit" class="btn-secondary">Edit Service</a>
          {/if}
          <button class="btn-secondary" onclick={() => openRequestModal('question')}>Ask a Question</button>
          {#if selectedService.type === 'transportation' && !(selectedService.transportation_details?.service_mode === 'scheduled')}
            {#if activeRequest && !isOwner}
              <a href="/market/services/my/requests/{activeRequest.id}" class="btn-success">
                View Active Request
              </a>
            {:else}
              <button class="btn-primary" onclick={() => openRequestModal('request')}>
                {#if isOwner && user.id === selectedService.user_id}
                  Preview Flight Request
                {:else}
                  Request Flight
                {/if}
              </button>
            {/if}
          {/if}
        {/if}
      </div>
    </div>

  {#if !selectedService}
    <!-- List View -->
    <div class="filters">
      <div class="filter-group tab-group">
        {#each serviceTypeOptions as option}
          <button
            class="tab-btn"
            class:active={currentType === option.value}
            onclick={() => goto(`/market/services/${option.value}`)}
          >
            {option.label}
            <span class="tab-count">({servicesByType[option.value]?.length || 0})</span>
          </button>
        {/each}
      </div>
      <div class="filter-group">
        <select bind:value={selectedPlanetId}>
          <option value={null}>All Planets</option>
          {#each planets as planet}
            <option value={planet.Id}>{planet.Name}</option>
          {/each}
        </select>
      </div>
    </div>

    {#if currentType === 'healing'}
      <HealingServicesList
        services={currentServices}
        {medicalTools}
        {medicalChips}
        {clothingItems}
        {armorSets}
        {consumables}
        loading={entitiesLoading}
      />
    {:else if currentType === 'dps'}
      <DPSServicesList
        services={currentServices}
        {weapons}
        {pets}
        {clothingItems}
        {armorSets}
        {consumables}
        loading={entitiesLoading}
      />
    {:else if currentType === 'transportation'}
      <TransportationServicesList services={currentServices} loading={entitiesLoading} />
    {:else if currentType === 'custom'}
      <div class="empty-state">
        <p>Custom services coming soon!</p>
      </div>
    {/if}
  {:else}
    <!-- Detail View -->
    {#if !selectedService.is_active && isOwner}
      <div class="inactive-banner">
        <strong>This service is currently deactivated.</strong>
        <p>Only you can see this page. <a href="/market/services/{selectedService.id}/edit">Edit this service</a> to activate it.</p>
      </div>
    {/if}

    {#if activeRequest && !isOwner}
      <div class="active-request-banner">
        <div class="banner-content">
          <span class="banner-title">You have an active request for this service</span>
          <span class="banner-text">
            Status: {activeRequest.status}
            {#if activeRequest.discord_thread_id}
              - A Discord thread is open for communication with the provider.
            {/if}
          </span>
        </div>
        <a href="/market/services/my/requests/{activeRequest.id}" class="banner-link">View Request</a>
      </div>
    {/if}

    <div class="service-detail">
      <div class="service-info">
        <div class="info-section">
          <h3>Provider</h3>
          {#if selectedService.manager_name && selectedService.manager_name !== selectedService.owner_name}
            <p>
              <strong>Manager:</strong>
              <a class="provider-link" href={getProfileUrl({ id: selectedService.manager_id || selectedService.user_id, eu_name: selectedService.manager_name })}>
                {selectedService.manager_name}
              </a>
            </p>
            <p>
              <strong>Owner:</strong>
              {#if selectedService.owner_user_id}
                <a class="provider-link" href={getProfileUrl({ id: selectedService.owner_user_id, eu_name: selectedService.owner_name })}>
                  {selectedService.owner_name || 'Unknown'}
                </a>
              {:else}
                {selectedService.owner_name || 'Unknown'}
              {/if}
            </p>
          {:else}
            <p>
              <strong>Owner & Manager:</strong>
              {#if selectedService?.owner_id}
                <a class="provider-link" href={getProfileUrl({ id: selectedService.owner_id, eu_name: selectedService.owner_name })}>
                  {selectedService.owner_name || 'Unknown'}
                </a>
              {:else}
                {selectedService.owner_name || 'Unknown'}
              {/if}
            </p>
          {/if}
          {#if selectedService.type === 'transportation' && pilots.length > 0}
            <p class="pilots-list">
              <strong>Pilots:</strong>
              {#each pilots as pilot, index}
                {#if index > 0}, {/if}
                {#if pilot.user_id}
                  <a class="provider-link" href={getProfileUrl({ id: pilot.user_id, eu_name: pilot.eu_name })}>
                    {pilot.username}
                  </a>
                {:else}
                  {pilot.username}
                {/if}
              {/each}
            </p>
          {/if}
          {#if selectedService.type === 'transportation' && selectedService.transportation_details?.discord_code}
            <p>
              <strong>Discord:</strong>
              <a class="provider-link" href="https://discord.gg/{selectedService.transportation_details.discord_code}" target="_blank" rel="noopener noreferrer">
                discord.gg/{selectedService.transportation_details.discord_code}
              </a>
            </p>
          {/if}
        </div>

        {#if selectedService.description}
          <div class="info-section">
            <h3>Description</h3>
            <div class="description-content">{@html sanitizeMarketHtml(selectedService.description)}</div>
          </div>
        {/if}

        <div class="info-section">
          <h3>Location</h3>
          <p>
            {#if canManageFlights && selectedService.type === 'transportation' && selectedService.transportation_details}
              <LocationManager
                serviceId={selectedService.id}
                currentPlanetId={selectedService.transportation_details.current_planet_id}
                locationDisplay={getLocationDisplay(selectedService, planets)}
                {planets}
              />
            {:else}
              {getLocationDisplay(selectedService, planets)}
            {/if}
          </p>
        </div>

        {#if selectedService.type === 'healing' && selectedService.healing_details}
          {@const medicalEquipment = selectedService.equipment?.filter(e => e.is_primary !== false && (e.item_type === 'medicaltools' || e.item_type === 'medicalchips')) || []}
          {@const hps = getEstimatedHealingHPS(selectedService, medicalTools, medicalChips, clothingItems, armorSets, consumables, activeMedicalEquipment, enabledConsumables, enabledTierEnhancers)}
          {@const maxDecay = getMaxHealingDecayPerHour(selectedService, medicalTools, medicalChips, clothingItems, armorSets, consumables, activeMedicalEquipment, enabledConsumables, enabledTierEnhancers)}
          {@const reloadBonus = getHealingReloadSpeedBonus(selectedService, clothingItems, armorSets, consumables, enabledConsumables)}
          {@const enhancerBonus = getHealingEnhancerBonus(selectedService, consumables, enabledConsumables, enabledTierEnhancers)}
          {@const costLabel = getHealingCostLabel(selectedService, medicalTools, medicalChips)}
          {@const activeMedicalItem = activeMedicalEquipment ? [...medicalTools, ...medicalChips].find(item => item.Name === activeMedicalEquipment.item_name) : null}
          {@const tier = activeMedicalEquipment?.tier || 0}
          {@const tierEnabled = enabledTierEnhancers[activeMedicalEquipment?.item_name] !== false}
          {@const avgHeal = activeMedicalItem?.Properties ? ((activeMedicalItem.Properties.MinHeal || 0) + (activeMedicalItem.Properties.MaxHeal || 0)) / 2 : null}
          {@const effectiveHeal = avgHeal !== null ? avgHeal * (1 + (enhancerBonus || 0) / 100) * (tierEnabled && tier > 0 ? 1 + tier * 0.05 : 1) : null}
          {@const baseCostPerHeal = activeMedicalItem?.Properties?.Economy?.Decay || null}
          {@const costPerHeal = baseCostPerHeal !== null ? baseCostPerHeal * (tierEnabled && tier > 0 ? 1 + tier * 0.05 : 1) : null}
          {@const healingHPP = (effectiveHeal !== null && costPerHeal !== null) ? effectiveHeal / costPerHeal : null}
          {@const extraCost = (selectedService.equipment || []).filter(e => {
            if (e.item_type === 'consumables') return enabledConsumables[e.item_name];
            if (e.item_type === 'medicaltools' || e.item_type === 'medicalchips') return activeMedicalEquipment?.item_name === e.item_name && e.extra_price;
            if (e.tier && e.tier > 0) return enabledTierEnhancers[e.item_name] && e.extra_price;
            return e.is_primary !== false && e.extra_price;
          }).reduce((sum, e) => sum + (parseFloat(e.extra_price) || 0), 0)}
          {@const healReload = activeMedicalItem?.Properties?.UsesPerMinute ? (60 / activeMedicalItem.Properties.UsesPerMinute) / (1 + reloadBonus.total / 100) : null}
          <div class="info-section">
            <h3>Healing Service Details</h3>
            {#if selectedService.healing_details.paramedic_level}
              <p>Paramedic Level: {selectedService.healing_details.paramedic_level}</p>
            {/if}
            
            <p>Reload Speed: <strong>{healReload !== null ? healReload.toFixed(2) + ' s/heal' : 'TBD'}</strong>
              {#if activeMedicalItem?.Properties?.UsesPerMinute}
                <span class="formula-text">
                  ({(60 / activeMedicalItem.Properties.UsesPerMinute).toFixed(2)} s base{#if reloadBonus.equipment > 0} × {(1 / (1 + reloadBonus.equipment / 100)).toFixed(3)} equipment{/if}{#if reloadBonus.consumables > 0} × {(1 / (1 + reloadBonus.consumables / 100)).toFixed(3)} consumable{/if})
                </span>
              {/if}
            </p>
            <p>Maximum HPS: <strong>{hps.base}</strong>
              {#if activeMedicalItem?.Properties && avgHeal !== null}
                {@const usesPerMin = activeMedicalItem.Properties.UsesPerMinute || 0}
                <span class="formula-text">
                  ({avgHeal.toFixed(1)} avg heal{#if enhancerBonus > 0} × {(1 + enhancerBonus / 100).toFixed(2)} enhancer{/if}{#if tierEnabled && tier > 0} × {(1 + tier * 0.05).toFixed(2)} tier {tier}{/if} × {(usesPerMin / 60).toFixed(2)} uses/s{#if reloadBonus.total > 0} × {(1 + reloadBonus.total / 100).toFixed(2)} reload{/if})
                </span>
              {/if}
            </p>
            <p>HPP (Heal per PEC): <strong>{healingHPP !== null ? healingHPP.toFixed(2) : 'TBD'}</strong>
              {#if effectiveHeal !== null && baseCostPerHeal !== null}
                <span class="formula-text">
                  ({effectiveHeal.toFixed(2)} eff heal ÷ {baseCostPerHeal.toFixed(4)} PEC/heal{#if tierEnabled && tier > 0} × {(1 + tier * 0.05).toFixed(2)} tier {tier}{/if})
                </span>
              {/if}
            </p>
            <p>{costLabel}: <strong>{maxDecay.base} PED</strong>
              {#if activeMedicalItem?.Properties?.Economy?.Decay}
                {@const decayPerUse = activeMedicalItem.Properties.Economy.Decay}
                {@const usesPerMin = activeMedicalItem.Properties.UsesPerMinute || 0}
                <span class="formula-text">
                  ({decayPerUse} PEC/use × {usesPerMin} uses/min × 60 min/h{#if tierEnabled && tier > 0} × {(1 + tier * 0.05).toFixed(2)} tier {tier}{/if}{#if reloadBonus.total > 0} × {(1 + reloadBonus.total / 100).toFixed(2)} reload{/if} ÷ 100)
                </span>
              {/if}
            </p>
          </div>
          
          <div class="info-section">
            <h3>Pricing</h3>
            
            <p>
              {#if selectedService.healing_details.accepts_time_billing && selectedService.healing_details.rate_per_hour}
                {parseFloat(selectedService.healing_details.rate_per_hour).toFixed(2)} PED/h
              {/if}
              {#if selectedService.healing_details.accepts_time_billing && selectedService.healing_details.rate_per_hour && selectedService.healing_details.accepts_decay_billing}
                {' + '}
              {/if}
              {#if selectedService.healing_details.accepts_decay_billing}
                Decay
              {/if}
              {#if !selectedService.healing_details.accepts_time_billing && !selectedService.healing_details.accepts_decay_billing}
                Free
              {/if}
              {#if extraCost > 0}
                {' + '}{extraCost.toFixed(2)} PED/h extras
              {/if}
            </p>
          </div>
        {/if}

        {#if selectedService.type === 'dps' && selectedService.dps_details}
          {@const weaponAttachments = {
            amplifier: selectedAmplifier,
            absorber: selectedAbsorber,
            scope: selectedScope,
            scopeSight: selectedScopeSight,
            sight: selectedSight,
            matrix: selectedMatrix,
            implant: selectedImplant
          }}
          {@const activeWeaponEquip = selectedService.equipment?.find(e => 
            e.is_primary !== false && e.item_type === 'weapons'
          )}
          {@const activeWeaponAttachments = activeWeaponEquip?.attachments}
          {@const tierEnabled = activeWeaponEquip?.tier > 0 && enabledTierEnhancers[activeWeaponEquip?.item_name] !== false}
          {@const weaponEnhancerType = tierEnabled ? (activeWeaponAttachments?.enhancerType || 'Damage') : ''}
          {@const weaponEnhancerTiers = tierEnabled && weaponEnhancerType ? Array.from({ length: activeWeaponEquip.tier }, (_, i) => i + 1) : []}
          {@const dpsValue = getEstimatedDPS(
            selectedService,
            activeWeapon,
            weaponAttachments,
            weaponEnhancerType,
            weaponEnhancerTiers,
            consumables,
            pets,
            clothingItems,
            armorSets,
            enabledConsumables,
            activePetEffects
          )}
          {@const reloadBonus = getDPSReloadSpeedBonus(
            selectedService,
            clothingItems,
            armorSets,
            consumables,
            pets,
            enabledConsumables,
            activePetEffects
          )}
          {@const damageBonus = getDPSDamageBonus(
            selectedService,
            consumables,
            pets,
            enabledConsumables,
            activePetEffects
          )}
          {@const critChanceBonus = getDPSCritChanceBonus(
            selectedService,
            clothingItems,
            armorSets,
            consumables,
            pets,
            enabledConsumables,
            activePetEffects
          )}
          {@const critDamageBonus = getDPSCritDamageBonus(
            selectedService,
            clothingItems,
            armorSets,
            consumables,
            pets,
            enabledConsumables,
            activePetEffects
          )}
          {@const hpStats = getTotalHP(
            playerHP,
            selectedService,
            clothingItems,
            armorSets,
            consumables,
            pets,
            enabledConsumables,
            activePetEffects
          )}
          {@const protectionStats = getProtectionStats(
            selectedService,
            armors,
            armorPlatings,
            [], // defenseEnhancers
            [], // durabilityEnhancers
            {}, // enabledDefenseEnhancers
            {} // enabledDurabilityEnhancers
          )}
          {@const costPerHour = getMaxCostPerHour(
            selectedService,
            activeWeapon,
            weaponAttachments,
            weaponEnhancerType,
            weaponEnhancerTiers,
            consumables,
            pets,
            clothingItems,
            armorSets,
            enabledConsumables,
            activePetEffects,
            { ammo: 100, weapon: 100 } // markups
          )}
          {@const damageEnhancers = weaponEnhancerType === 'Damage' ? weaponEnhancerTiers.length : 0}
          {@const economyEnhancers = weaponEnhancerType === 'Economy' ? weaponEnhancerTiers.length : 0}
          {@const weaponCost = activeWeapon ? LoadoutCalc.calculateWeaponCost(activeWeapon, damageEnhancers, economyEnhancers) : null}
          {@const efficiency = activeWeapon ? LoadoutCalc.calculateEfficiency(
            activeWeapon,
            weaponCost,
            damageEnhancers,
            economyEnhancers,
            selectedAbsorber,
            selectedAmplifier,
            selectedScope,
            selectedScopeSight,
            selectedSight,
            selectedMatrix
          ) : null}
          {@const decay = activeWeapon ? LoadoutCalc.calculateDecay(
            activeWeapon,
            damageEnhancers,
            economyEnhancers,
            selectedAbsorber,
            selectedImplant,
            selectedAmplifier,
            selectedScope,
            selectedScopeSight,
            selectedSight,
            selectedMatrix,
            { ammo: 100, weapon: 100 }
          ) : null}
          {@const ammoBurn = activeWeapon ? LoadoutCalc.calculateAmmoBurn(
            activeWeapon,
            damageEnhancers,
            economyEnhancers,
            selectedAmplifier
          ) : null}
          {@const costPerShot = (decay !== null && ammoBurn !== null) ? LoadoutCalc.calculateCost(decay, ammoBurn, 100) : null}
          {@const hitSkill = 1000}
          {@const dmgSkill = 1000}
          {@const skillModEnhancers = weaponEnhancerType === 'Accuracy' ? weaponEnhancerTiers.length : 0}
          {@const totalDamage = activeWeapon ? LoadoutCalc.calculateTotalDamage(
            activeWeapon,
            damageEnhancers,
            damageBonus.total,
            selectedAmplifier
          ) : null}
          {@const damageInterval = (activeWeapon && totalDamage) ? LoadoutCalc.calculateDamageInterval(
            activeWeapon,
            dmgSkill,
            skillModEnhancers,
            totalDamage
          ) : null}
          {@const hitAbility = activeWeapon ? LoadoutCalc.calculateHitAbility(activeWeapon, hitSkill, skillModEnhancers) : null}
          {@const critAbility = activeWeapon ? LoadoutCalc.calculateCritAbility(activeWeapon, hitSkill, skillModEnhancers) : null}
          {@const accuracyEnhancers = weaponEnhancerType === 'Accuracy' ? weaponEnhancerTiers.length : 0}
          {@const critChance = (critAbility !== null) ? LoadoutCalc.calculateCritChance(critAbility, accuracyEnhancers, critChanceBonus.total) : null}
          {@const critDamage = LoadoutCalc.calculateCritDamage(critDamageBonus.total)}
          {@const effectiveDamage = (damageInterval && critChance !== null && critDamage !== null && hitAbility !== null) ? LoadoutCalc.calculateEffectiveDamage(
            damageInterval,
            critChance,
            critDamage,
            hitAbility
          ) : null}
          {@const dpp = (effectiveDamage !== null && costPerShot !== null) ? LoadoutCalc.calculateDPP(effectiveDamage, costPerShot) : null}
          {@const rangeEnhancers = weaponEnhancerType === 'Range' ? weaponEnhancerTiers.length : 0}
          {@const weaponRange = activeWeapon ? LoadoutCalc.calculateRange(activeWeapon, hitSkill, skillModEnhancers, rangeEnhancers) : null}
          {@const reload = activeWeapon ? LoadoutCalc.calculateReload(activeWeapon, hitSkill, skillModEnhancers, reloadBonus.total) : null}
          {@const dps = (effectiveDamage !== null && reload !== null) ? LoadoutCalc.calculateDPS(effectiveDamage, reload) : null}
          {@const baseDamage = activeWeapon ? (
            (activeWeapon.Properties?.Damage?.Impact || 0) +
            (activeWeapon.Properties?.Damage?.Cut || 0) +
            (activeWeapon.Properties?.Damage?.Stab || 0) +
            (activeWeapon.Properties?.Damage?.Penetration || 0) +
            (activeWeapon.Properties?.Damage?.Shrapnel || 0) +
            (activeWeapon.Properties?.Damage?.Burn || 0) +
            (activeWeapon.Properties?.Damage?.Cold || 0) +
            (activeWeapon.Properties?.Damage?.Acid || 0) +
            (activeWeapon.Properties?.Damage?.Electric || 0)
          ) : null}
          {@const amplifierDamage = selectedAmplifier ? (
            (selectedAmplifier.Properties?.Damage?.Impact || 0) +
            (selectedAmplifier.Properties?.Damage?.Cut || 0) +
            (selectedAmplifier.Properties?.Damage?.Stab || 0) +
            (selectedAmplifier.Properties?.Damage?.Penetration || 0) +
            (selectedAmplifier.Properties?.Damage?.Shrapnel || 0) +
            (selectedAmplifier.Properties?.Damage?.Burn || 0) +
            (selectedAmplifier.Properties?.Damage?.Cold || 0) +
            (selectedAmplifier.Properties?.Damage?.Acid || 0) +
            (selectedAmplifier.Properties?.Damage?.Electric || 0)
          ) : null}
          {@const amplifierBonus = (selectedAmplifier && baseDamage && amplifierDamage) ? Math.min(baseDamage / 2, amplifierDamage) : 0}
          {@const hitChance = hitAbility !== null ? (0.8 + hitAbility / 100) : null}
          {@const avgDamageInterval = damageInterval ? (damageInterval.min + damageInterval.max) / 2 : null}
          {@const extraCost = (selectedService.equipment || []).filter(e => {
            if (e.item_type === 'consumables') return enabledConsumables[e.item_name];
            if (e.item_type === 'weapons') return activeWeapon?.Name === e.item_name && e.extra_price;
            if (e.tier && e.tier > 0) return e.extra_price;
            return e.is_primary !== false && e.extra_price;
          }).reduce((sum, e) => sum + (parseFloat(e.extra_price) || 0), 0)}
          <div class="info-section">
            <h3>DPS Service Details</h3>
            {#if selectedService.dps_details.notes}
              <p class="service-notes">{selectedService.dps_details.notes}</p>
            {/if}
            
            {#if activeWeapon}
              <p>Active Weapon: <strong>{activeWeapon.Name}</strong>
                {#if weaponEnhancerType}
                  <span class="formula-text">({weaponEnhancerType} Enhancers)</span>
                {/if}
              </p>
            {:else}
              <p>Active Weapon: <strong>None selected</strong></p>
            {/if}
            
            <p>HP: <strong>{hpStats.total}</strong>
              <span class="formula-text">
                ({playerHP} base{#if hpStats.equipment > 0} + {hpStats.equipment} equipment{/if}{#if hpStats.consumables > 0} + {hpStats.consumables} consumable{/if}{#if hpStats.pets > 0} + {hpStats.pets} pet{/if})
              </span>
            </p>
            
            <h4 style="margin-top: 15px;">Combat</h4>
            
            
            <p>Effective DPS: <strong>{dpsValue > 0 ? dpsValue.toFixed(2) : 'TBD'}</strong>
              {#if activeWeapon && effectiveDamage !== null && reload !== null}
                <span class="formula-text">
                  ({effectiveDamage.toFixed(2)} eff dmg ÷ {reload.toFixed(2)} s/shot)
                </span>
              {/if}
            </p>

            <p>Reload Speed: <strong>{reload !== null ? reload.toFixed(2) + ' s/shot' : 'TBD'}</strong>
              {#if activeWeapon?.Properties?.UsesPerMinute}
                <span class="formula-text">
                  ({(60 / activeWeapon.Properties.UsesPerMinute).toFixed(2)} s base{#if reloadBonus.equipment > 0} × {(1 / (1 + reloadBonus.equipment / 100)).toFixed(3)} equipment{/if}{#if reloadBonus.consumables > 0} × {(1 / (1 + reloadBonus.consumables / 100)).toFixed(3)} consumable{/if}{#if reloadBonus.pets > 0} × {(1 / (1 + reloadBonus.pets / 100)).toFixed(3)} pet{/if})
                </span>
              {/if}
            </p>
            <p>Range: <strong>{weaponRange !== null ? weaponRange.toFixed(2) + ' m' : 'TBD'}</strong>
              {#if activeWeapon?.Properties?.Range}
                <span class="formula-text">
                  ({activeWeapon.Properties.Range} base{#if rangeEnhancers > 0} × {(1 + rangeEnhancers * 0.05).toFixed(2)} range enh{/if})
                </span>
              {/if}
            </p>
            <p>Critical Chance: <strong>{critChance !== null ? (critChance * 100).toFixed(1) + '%' : 'TBD'}</strong>
              {#if critChance !== null}
                <span class="formula-text">
                  (1% base + {(critChance * 100 - 1).toFixed(1)}% from skill/enhancers/buffs)
                </span>
              {/if}
            </p>
            <p>Critical Damage: <strong>{critDamage !== null ? (critDamage * 100).toFixed(0) + '%' : 'TBD'}</strong>
              {#if critDamage !== null}
                <span class="formula-text">
                  (100% base + {((critDamage - 1) * 100).toFixed(0)}% from buffs)
                </span>
              {/if}
            </p>
            
            <h4 style="margin-top: 15px;">Economy</h4>
            
            <p>Efficiency: <strong>{efficiency !== null ? efficiency.toFixed(2) + '%' : 'TBD'}</strong>
              {#if activeWeapon?.Properties?.Economy?.Efficiency}
                <span class="formula-text">
                  (weighted avg of weapon and attachments {activeWeapon.Properties.Economy.Efficiency.toFixed(1)}%{#if selectedAmplifier?.Properties?.Economy?.Efficiency} + amp {selectedAmplifier.Properties.Economy.Efficiency.toFixed(1)}%{/if}{#if selectedAbsorber?.Properties?.Economy?.Efficiency} + abs {selectedAbsorber.Properties.Economy.Efficiency.toFixed(1)}%{/if})
                </span>
              {/if}
            </p>
            <p>DPP (Damage per PEC): <strong>{dpp !== null ? dpp.toFixed(2) : 'TBD'}</strong>
              {#if effectiveDamage !== null && costPerShot !== null}
                <span class="formula-text">
                  ({effectiveDamage.toFixed(2)} eff dmg ÷ {costPerShot.toFixed(4)} PEC/shot)
                </span>
              {/if}
            </p>
            <p>Maximum Cost/h: <strong>{costPerHour > 0 ? costPerHour.toFixed(2) : 'TBD'} PED</strong>
              {#if activeWeapon && decay !== null && ammoBurn !== null && reload !== null}
                <span class="formula-text">
                  (({decay.toFixed(4)} decay + {Math.round(ammoBurn)} ammo ÷ 100) × 3600 ÷ {reload.toFixed(2)} s/shot ÷ 100)
                </span>
              {/if}
            </p>
            
            {#if protectionStats.blockChance > 0 || Object.values(protectionStats).some(stat => typeof stat === 'object' && stat != null && (stat.defense > 0 || stat.absorption > 0))}
              <div class="protection-stats">
                <h4>Protection</h4>
                {#if protectionStats.blockChance > 0}
                  <p>Block Chance: <strong>{protectionStats.blockChance.toFixed(1)}%</strong></p>
                {/if}
                <div class="damage-type-grid">
                  {#if protectionStats.burn && (protectionStats.burn.defense > 0 || protectionStats.burn.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Burn:</span>
                      <span class="damage-values">
                        {protectionStats.burn.defense.toFixed(1)} def / {protectionStats.burn.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                  {#if protectionStats.cold && (protectionStats.cold.defense > 0 || protectionStats.cold.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Cold:</span>
                      <span class="damage-values">
                        {protectionStats.cold.defense.toFixed(1)} def / {protectionStats.cold.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                  {#if protectionStats.acid && (protectionStats.acid.defense > 0 || protectionStats.acid.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Acid:</span>
                      <span class="damage-values">
                        {protectionStats.acid.defense.toFixed(1)} def / {protectionStats.acid.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                  {#if protectionStats.electric && (protectionStats.electric.defense > 0 || protectionStats.electric.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Electric:</span>
                      <span class="damage-values">
                        {protectionStats.electric.defense.toFixed(1)} def / {protectionStats.electric.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                  {#if protectionStats.cut && (protectionStats.cut.defense > 0 || protectionStats.cut.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Cut:</span>
                      <span class="damage-values">
                        {protectionStats.cut.defense.toFixed(1)} def / {protectionStats.cut.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                  {#if protectionStats.impact && (protectionStats.impact.defense > 0 || protectionStats.impact.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Impact:</span>
                      <span class="damage-values">
                        {protectionStats.impact.defense.toFixed(1)} def / {protectionStats.impact.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                  {#if protectionStats.penetration && (protectionStats.penetration.defense > 0 || protectionStats.penetration.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Penetration:</span>
                      <span class="damage-values">
                        {protectionStats.penetration.defense.toFixed(1)} def / {protectionStats.penetration.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                  {#if protectionStats.shrapnel && (protectionStats.shrapnel.defense > 0 || protectionStats.shrapnel.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Shrapnel:</span>
                      <span class="damage-values">
                        {protectionStats.shrapnel.defense.toFixed(1)} def / {protectionStats.shrapnel.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                  {#if protectionStats.stab && (protectionStats.stab.defense > 0 || protectionStats.stab.absorption > 0)}
                    <div class="damage-type">
                      <span class="damage-label">Stab:</span>
                      <span class="damage-values">
                        {protectionStats.stab.defense.toFixed(1)} def / {protectionStats.stab.absorption.toFixed(1)}% abs
                      </span>
                    </div>
                  {/if}
                </div>
              </div>
            {/if}
          </div>
          
          <div class="info-section">
            <h3>Pricing</h3>
            
            <p>
              {#if selectedService.dps_details.accepts_time_billing && selectedService.dps_details.rate_per_hour}
                {parseFloat(selectedService.dps_details.rate_per_hour).toFixed(2)} PED/h
              {/if}
              {#if selectedService.dps_details.accepts_time_billing && selectedService.dps_details.rate_per_hour && selectedService.dps_details.accepts_decay_billing}
                {' + '}
              {/if}
              {#if selectedService.dps_details.accepts_decay_billing}
                Decay
              {/if}
              {#if !selectedService.dps_details.accepts_time_billing && !selectedService.dps_details.accepts_decay_billing}
                Free
              {/if}
              {#if extraCost > 0}
                {' + '}{extraCost.toFixed(2)} PED/h extras
              {/if}
            </p>
          </div>
        {/if}

        {#if selectedService.type === 'transportation' && selectedService.transportation_details}
          {@const td = selectedService.transportation_details}
          {@const typeLabels = { regular: 'Regular', warp_equus: 'Warp (Equus)', warp_privateer: 'Warp (Privateer/Mothership)' }}
          {@const modeLabels = { on_demand: 'On Demand', scheduled: 'Scheduled', both: 'On Demand & Scheduled' }}
          <div class="info-section">
            <h3>Transportation Details</h3>
            <p>Transportation Type: <strong>{typeLabels[td.transportation_type] || td.transportation_type || 'Not specified'}</strong></p>
            {#if td.ship_name}
              <p>Ship: <strong>{td.ship_name}</strong></p>
            {/if}
            <p>Service Type: <strong>{modeLabels[td.service_mode] || 'On Demand'}</strong></p>
          </div>

          <!-- Service Mode Explanation -->
          <div class="info-section">
            <h3>How This Service Works</h3>
            {#if td.service_mode === 'on_demand' || !td.service_mode}
              <p class="service-mode-explanation">
                <strong>On Demand:</strong> This service operates like a VIP Warp in-game. Contact the provider anytime during their available hours to arrange immediate transportation to your destination.
              </p>
            {:else}
              <p class="service-mode-explanation">
                <strong>Scheduled Flights:</strong> This service offers pre-scheduled flights at specific departure times. Check in for an upcoming flight below, and the provider will transport all checked-in passengers along the route.
              </p>
            {/if}
          </div>

          <div class="info-section">
            <div class="section-header-with-action">
              <h3>Ticket Offers</h3>
              {#if isOwner}
                <a href="/market/services/{selectedService.id}/ticket-offers" class="manage-btn">Manage Ticket Offers</a>
              {/if}
            </div>
            {#if ticketOffers && ticketOffers.length > 0}
              {#if !isOwner && user?.administrator}
                <p class="admin-note">
                  <em>Note: As an administrator, you can purchase tickets for testing purposes.</em>
                </p>
              {/if}
              <div class="ticket-offers-grid">
                {#each ticketOffers as offer (offer.id)}
                  <TicketOfferCard
                    {offer}
                    {isOwner}
                    showAsSingleOption={ticketOffers.length === 1 && !isOwner}
                    onpurchase={handlePurchaseTicket}
                    onrequestFlight={() => openRequestModal('request')}
                  />
                {/each}
              </div>
            {:else if !isOwner}
              <p class="muted-text">No ticket offers available yet.</p>
            {:else}
              <p class="muted-text">No ticket offers configured yet. Use the "Manage Ticket Offers" button above to create them.</p>
            {/if}
          </div>

          <!-- Upcoming Flights -->
          {#if (td.service_mode === 'scheduled' || td.service_mode === 'both')}
            {#if canManageFlights}
              <!-- Flight Dashboard link - always visible for owners -->
              <div class="flight-dashboard-section">
                <span class="flight-dashboard-label">Flight Management</span>
                <a href="/market/services/{selectedService.id}/flights" class="manage-btn primary">Open Flight Dashboard</a>
              </div>
            {/if}

            {#if nextActiveFlight && !isOwner}
              {@const routeStops = typeof nextActiveFlight.route_stops === 'string' ? JSON.parse(nextActiveFlight.route_stops) : nextActiveFlight.route_stops}
              {@const canCheckInNow = canCheckIn(nextActiveFlight)}
              <!-- Next Flight (for customers) -->
              <div class="info-section">
                <h3>Next Scheduled Flight</h3>
                <div class="flight-card highlighted-flight">
                  <div class="flight-header">
                    <span class="flight-status {nextActiveFlight.status}">{nextActiveFlight.status}</span>
                    <span class="flight-type">{nextActiveFlight.route_type === 'flexible' ? 'Flexible Route' : 'Fixed Route'}</span>
                  </div>
                  <div class="flight-time">
                    <strong>{formatFlightTime(nextActiveFlight.scheduled_departure)}</strong>
                  </div>
                  {#if nextActiveFlight.status === 'running'}
                    <div class="flight-current-state">
                      {getFlightCurrentState(nextActiveFlight)}
                    </div>
                  {/if}
                  <div class="flight-route">
                    {#if routeStops && routeStops.length > 0}
                      <span class="route-label">Route:</span>
                      {#if nextActiveFlight.status === 'running'}
                        {@const currentStopIndex = nextActiveFlight.current_stop_index || 0}
                        {#each routeStops as stop, i}
                          {@const isInWarpToThisStop = nextActiveFlight.current_state?.startsWith('warp_to_') && parseInt(nextActiveFlight.current_state.split('_')[2]) === i}
                          {@const isCurrentStop = i === currentStopIndex && !nextActiveFlight.current_state?.startsWith('warp_to_')}
                          {@const isPastStop = i < currentStopIndex || (i === currentStopIndex && nextActiveFlight.current_state?.startsWith('warp_to_'))}
                          <span class="route-planet {isPastStop ? 'visited' : ''} {isCurrentStop ? 'current' : ''}">{stop.name || `Planet ${stop.planet_id}`}</span>{#if i < routeStops.length - 1}{@const isArrowInWarp = nextActiveFlight.current_state?.startsWith('warp_to_') && parseInt(nextActiveFlight.current_state.split('_')[2]) === i + 1}{@const isArrowCompleted = i + 1 <= currentStopIndex}<span class="route-arrow {isArrowCompleted ? 'completed' : ''} {isArrowInWarp ? 'in-warp' : ''}">→</span>{/if}
                        {/each}
                      {:else}
                        {#each routeStops as stop, i}
                          <span class="route-planet">{stop.name || `Planet ${stop.planet_id}`}</span>{#if i < routeStops.length - 1}<span class="route-arrow">→</span>{/if}
                        {/each}
                      {/if}
                    {/if}
                  </div>
                  {#if canCheckInNow}
                    <button onclick={() => openCheckinDialog(nextActiveFlight)} class="check-in-btn">Check In Now</button>
                  {/if}
                </div>
              </div>
            {/if}

            {#if runningFlights.length > 0}
              <!-- Running Flights -->
              <div class="info-section">
                <h3>Running Flights ({runningFlights.length})</h3>

                <div class="upcoming-flights">
                  {#each runningFlights as flight (flight.id)}
                    {@const routeStops = typeof flight.route_stops === 'string' ? JSON.parse(flight.route_stops) : flight.route_stops}
                    {@const canCheckInNow = canCheckIn(flight)}
                    <div class="flight-card">
                      <div class="flight-header">
                        <span class="flight-status {flight.status}">{flight.status}</span>
                        <span class="flight-type">{flight.route_type === 'flexible' ? 'Flexible Route' : 'Fixed Route'}</span>
                      </div>
                      <div class="flight-time">
                        <strong>{formatFlightTime(flight.scheduled_departure)}</strong>
                      </div>
                      <div class="flight-current-state">
                        {getFlightCurrentState(flight)}
                      </div>
                      <div class="flight-route">
                        {#if routeStops && routeStops.length > 0}
                          <span class="route-label">Route:</span>
                          {@const currentStopIndex = flight.current_stop_index || 0}
                          {#each routeStops as stop, i}
                            {@const isInWarpToThisStop = flight.current_state?.startsWith('warp_to_') && parseInt(flight.current_state.split('_')[2]) === i}
                            {@const isCurrentStop = i === currentStopIndex && !flight.current_state?.startsWith('warp_to_')}
                            {@const isPastStop = i < currentStopIndex || (i === currentStopIndex && flight.current_state?.startsWith('warp_to_'))}
                            <span class="route-planet {isPastStop ? 'visited' : ''} {isCurrentStop ? 'current' : ''}">{stop.name || `Planet ${stop.planet_id}`}</span>{#if i < routeStops.length - 1}{@const isArrowInWarp = flight.current_state?.startsWith('warp_to_') && parseInt(flight.current_state.split('_')[2]) === i + 1}{@const isArrowCompleted = i + 1 <= currentStopIndex}<span class="route-arrow {isArrowCompleted ? 'completed' : ''} {isArrowInWarp ? 'in-warp' : ''}">→</span>{/if}
                          {/each}
                        {/if}
                      </div>
                      {#if canCheckInNow && !isOwner}
                        <button onclick={() => openCheckinDialog(flight)} class="check-in-btn">Check In Now</button>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            {#if scheduledFlights.length > 0}
              <!-- Scheduled Flights (expandable for customers, always visible for owners) -->
              <div class="info-section">
                {#if !isOwner && scheduledFlights.length > 1}
                  <button onclick={() => showAllFlights = !showAllFlights} class="expand-flights-btn">
                    {showAllFlights ? '▼' : '►'} {showAllFlights ? 'Hide' : 'Show'} All Scheduled Flights ({scheduledFlights.length})
                  </button>
                {:else}
                  <h3>Scheduled Flights ({scheduledFlights.length})</h3>
                {/if}

                {#if showAllFlights || canManageFlights || isOwner}
                  <div class="upcoming-flights">
                    {#each scheduledFlights as flight (flight.id)}
                      {@const routeStops = typeof flight.route_stops === 'string' ? JSON.parse(flight.route_stops) : flight.route_stops}
                      {@const canCheckInNow = canCheckIn(flight)}
                      <div class="flight-card">
                        <div class="flight-header">
                          <span class="flight-status {flight.status}">{flight.status}</span>
                          <span class="flight-type">{flight.route_type === 'flexible' ? 'Flexible Route' : 'Fixed Route'}</span>
                        </div>
                        <div class="flight-time">
                          <strong>{formatFlightTime(flight.scheduled_departure)}</strong>
                        </div>
                        <div class="flight-route">
                          {#if routeStops && routeStops.length > 0}
                            <span class="route-label">Route:</span>
                            {#each routeStops as stop, i}
                              <span class="route-planet">{stop.name || `Planet ${stop.planet_id}`}</span>{#if i < routeStops.length - 1}<span class="route-arrow">→</span>{/if}
                            {/each}
                          {/if}
                        </div>
                        {#if canCheckInNow && !isOwner}
                          <button onclick={() => openCheckinDialog(flight)} class="check-in-btn">Check In Now</button>
                        {/if}
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}

            {#if cancelledFlights.length > 0 && isOwner}
              <!-- Cancelled Flights (owners only) -->
              <div class="info-section">
                <h3>Recently Cancelled Flights ({cancelledFlights.length})</h3>
                <p class="muted-text">Can be restored within 2 hours of scheduled departure.</p>
                <div class="upcoming-flights">
                  {#each cancelledFlights as flight (flight.id)}
                    {@const routeStops = typeof flight.route_stops === 'string' ? JSON.parse(flight.route_stops) : flight.route_stops}
                    {@const canRestoreNow = canRestoreFlight(flight, activeFlights)}
                    <div class="flight-card cancelled-flight">
                      <div class="flight-header">
                        <span class="flight-status {flight.status}">{flight.status}</span>
                        <span class="flight-type">{flight.route_type === 'flexible' ? 'Flexible Route' : 'Fixed Route'}</span>
                      </div>
                      <div class="flight-time">
                        <strong>{formatFlightTime(flight.scheduled_departure)}</strong>
                      </div>
                      <div class="flight-route">
                        {#if routeStops && routeStops.length > 0}
                          <span class="route-label">Route:</span>
                          {#each routeStops as stop, i}
                            <span class="route-planet">{stop.name || `Planet ${stop.planet_id}`}</span>{#if i < routeStops.length - 1}<span class="route-arrow">→</span>{/if}
                          {/each}
                        {/if}
                      </div>
                      {#if canRestoreNow}
                        <button onclick={() => restoreFlight(flight.id)} class="restore-btn">Restore Flight</button>
                      {/if}
                    </div>
                  {/each}
                </div>
              </div>
            {/if}

            {#if runningFlights.length === 0 && scheduledFlights.length === 0 && cancelledFlights.length === 0 && !canManageFlights}
              <!-- Only show empty state for non-owners (owners have the Flight Management section above) -->
              <div class="info-section">
                <h3>Upcoming Scheduled Flights</h3>
                <p class="muted-text">No flights scheduled for the next 7 days.</p>
              </div>
            {/if}
          {/if}
        {/if}

        {#if selectedService.equipment && selectedService.equipment.length > 0}
          {@const medicalEquipment = selectedService.equipment.filter(e => e.item_type === 'medicaltools' || e.item_type === 'medicalchips').sort((a, b) => {
            if (a.is_primary && !b.is_primary) return -1;
            if (!a.is_primary && b.is_primary) return 1;
            return a.item_name?.localeCompare(b.item_name);
          })}
          {@const armorEquipment = selectedService.equipment.filter(e => e.item_type === 'armorsets').sort((a, b) => {
            if (a.is_primary && !b.is_primary) return -1;
            if (!a.is_primary && b.is_primary) return 1;
            return a.item_name?.localeCompare(b.item_name);
          })}
          {@const clothingEquipment = selectedService.equipment.filter(e => e.item_type === 'clothings').sort((a, b) => {
            if (a.is_primary && !b.is_primary) return -1;
            if (!a.is_primary && b.is_primary) return 1;
            return a.item_name?.localeCompare(b.item_name);
          })}
          {@const consumableEquipment = selectedService.equipment.filter(e => e.item_type === 'consumables').sort((a, b) => a.item_name?.localeCompare(b.item_name))}
          {@const weaponEquipment = selectedService.equipment.filter(e => e.item_type === 'weapons').sort((a, b) => {
            if (a.is_primary && !b.is_primary) return -1;
            if (!a.is_primary && b.is_primary) return 1;
            return a.item_name?.localeCompare(b.item_name);
          })}
          {@const petEquipment = selectedService.equipment.filter(e => e.item_type === 'pets').sort((a, b) => a.item_name?.localeCompare(b.item_name))}
          {@const activePet = petEquipment.find(p => activePetEffects[p.item_name] && activePetEffects[p.item_name] !== false)}
          {@const activePetData = activePet ? pets.find(p => p.Name === activePet.item_name) : null}
          {@const activeAbilityKey = activePet ? activePetEffects[activePet.item_name] : null}
          {@const activeAbility = activePetData?.Effects?.find((e, i) => {
            const key = `${e.Id}-${e.Properties?.Strength || 0}-${i}`;
            return key === activeAbilityKey;
          })}
          {@const basePetConsumption = activePetData?.Properties?.NutrioConsumptionPerHour || 0}
          {@const abilityConsumption = activeAbility?.Properties?.NutrioConsumptionPerHour || 0}
          {@const totalNutrioConsumption = basePetConsumption + abilityConsumption}
          
          <div class="info-section">
            <h3>Pet</h3>
            {#if petEquipment.length > 0}
              <p>Active Pet: <strong>{activePet?.item_name || 'N/A'}</strong></p>
              <p>Active Ability: <strong>{activeAbility ? activeAbility.Name : 'N/A'}</strong>
                {#if activeAbility?.Properties?.Strength}
                  <span class="formula-text">(+{activeAbility.Properties.Strength}{activeAbility.Properties?.Unit || ''})</span>
                {/if}
              </p>
              <p>Nutrio Consumption: <strong>{activeAbility ? `${totalNutrioConsumption.toFixed(1)}/h` : 'N/A'}</strong>
                {#if activeAbility}
                  <span class="formula-text">
                    ({basePetConsumption.toFixed(1)} base{#if abilityConsumption > 0} + {abilityConsumption.toFixed(1)} ability{/if})
                  </span>
                {/if}
              </p>
            {:else}
              <p><strong>No Pet Available</strong></p>
            {/if}
          </div>
          
          <div class="info-section">
            <h3>Equipment</h3>
            
            {#if weaponEquipment.length > 0}
              <div class="equipment-category">
                <h4>Weapons</h4>
                <ul class="equipment-list">
                  {#each weaponEquipment as equip (equip.item_name)}
                    {@const weaponData = weapons.find(w => w.Name === equip.item_name)}
                    <li class:active={activeWeapon?.Name === equip.item_name}>
                      <div class="equipment-item-header">
                        <div class="equipment-item-main">
                          <div class="equipment-item-name-text">
                            {#if equip.item_name}
                              <a href={getItemInternalUrl(equip.item_type, equip.item_name)} class="equipment-item-link">
                                <strong>{equip.item_name}</strong>
                              </a>
                            {:else}
                              <strong class="unnamed-item">Item ID: {equip.item_id}</strong>
                            {/if}
                          </div>
                          <div class="equipment-item-badges">
                            {#if equip.tier !== null && equip.tier !== undefined}
                              <span class="tier-badge">T{equip.tier}</span>
                            {/if}
                            {#if equip.tier > 0}
                              {@const validEnhancerType = ['Damage', 'Range', 'Economy', 'Accuracy'].includes(equip.attachments?.enhancerType) ? equip.attachments.enhancerType : 'Damage'}
                              <span class="enhancer-badge">{validEnhancerType} Enhancers</span>
                            {/if}
                            {#if equip.is_primary}
                              <span class="primary-badge">Primary</span>
                            {/if}
                            {#if hasAttachments(equip)}
                              <button class="attachments-badge" onclick={(e) => { e.stopPropagation(); openAttachmentDialog(equip); }} title="View attachments">
                                {countAttachments(equip)} attachment{countAttachments(equip) > 1 ? 's' : ''}
                              </button>
                            {/if}
                            {#if equip.extra_price}
                              <span class="extra-price">+{parseFloat(equip.extra_price).toFixed(2)} PED/h</span>
                            {/if}
                          </div>
                          <div class="equipment-item-details">
                            {getItemTypeLabel(equip.item_type)}
                          </div>
                        </div>
                        <div class="button-group">
                          {#if equip.tier && equip.tier > 0}
                            <button 
                              class="toggle-btn tier-toggle" 
                              class:active={enabledTierEnhancers[equip.item_name]}
                              disabled={activeWeapon?.Name !== equip.item_name}
                              onclick={() => enabledTierEnhancers[equip.item_name] = !enabledTierEnhancers[equip.item_name]}
                            >
                              {enabledTierEnhancers[equip.item_name] ? 'Tiers ON' : 'Tiers OFF'}
                            </button>
                          {/if}
                          <button 
                            class="use-btn" 
                            class:active={activeWeapon?.Name === equip.item_name}
                            onclick={() => activeWeapon = weaponData}
                          >
                            {activeWeapon?.Name === equip.item_name ? 'Active' : 'Use'}
                          </button>
                        </div>
                      </div>
                      {#if equip.notes}
                        <div class="equipment-notes">{equip.notes}</div>
                      {/if}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
            
            {#if petEquipment.length > 0}
              <div class="equipment-category">
                <h4>Pets</h4>
                <ul class="equipment-list">
                  {#each petEquipment as equip (equip.item_name)}
                    {@const petData = pets.find(p => p.Name === equip.item_name)}
                    {@const activePetAbility = activePetEffects[equip.item_name]}
                    {@const allEffects = petData?.Effects || []}
                    {@const enabledAbilityKeys = equip.attachments?.enabledAbilities || allEffects.map((e, i) => `${e.Id}-${e.Properties?.Strength || 0}-${i}`)}
                    {@const relevantEffects = allEffects.filter((e, i) => {
                      const key = `${e.Id}-${e.Properties?.Strength || 0}-${i}`;
                      return enabledAbilityKeys.includes(key);
                    })}
                    {@const isPetActive = activePetAbility && activePetAbility !== false}
                    <li class:active={isPetActive}>
                      <div class="equipment-item-header">
                        <div class="equipment-item-main">
                          <div class="equipment-item-name-text">
                            {#if equip.item_name}
                              <a href={getItemInternalUrl(equip.item_type, equip.item_name)} class="equipment-item-link">
                                <strong>{equip.item_name}</strong>
                              </a>
                            {:else}
                              <strong class="unnamed-item">Item ID: {equip.item_id}</strong>
                            {/if}
                          </div>
                          <div class="equipment-item-badges">
                            {#if equip.extra_price}
                              <span class="extra-price">+{parseFloat(equip.extra_price).toFixed(2)} PED/h</span>
                            {/if}
                          </div>
                          <div class="equipment-item-details">
                            {getItemTypeLabel(equip.item_type)}
                          </div>
                        </div>
                        <div class="button-group">
                          {#if relevantEffects.length > 0}
                            {#each relevantEffects as effect, effectIndex}
                              {@const effectKey = `${effect.Id}-${effect.Properties?.Strength || 0}-${allEffects.findIndex(e => e === effect)}`}
                              {@const isThisAbilityActive = activePetAbility === effectKey}
                              {@const effectConsumption = effect.Properties?.NutrioConsumptionPerHour || 0}
                              {@const tooltipParts = []}
                              {#if effect.Properties?.Strength}
                                {@const _ = tooltipParts.push(`${effect.Name}: +${effect.Properties.Strength}${effect.Properties?.Unit || ''}`)}
                              {:else}
                                {@const _ = tooltipParts.push(effect.Name)}
                              {/if}
                              {#if effectConsumption > 0}
                                {@const _ = tooltipParts.push(`Consumption: +${effectConsumption.toFixed(1)}/h`)}
                              {/if}
                              {@const effectTooltip = tooltipParts.join(' | ')}
                              {@const skillName = effect.Name.replace(/ Increased$/, '').replace(/ Added$/, '')}
                              {@const sameSkillCount = relevantEffects.filter(e => e.Name.replace(/ Increased$/, '').replace(/ Added$/, '') === skillName).length}
                              <button 
                                class="toggle-btn" 
                                class:active={isThisAbilityActive}
                                onclick={() => {
                                  if (isThisAbilityActive) {
                                    // Turn off this ability (deactivate pet)
                                    activePetEffects[equip.item_name] = false;
                                  } else {
                                    // Turn off all other pets and activate this ability
                                    Object.keys(activePetEffects).forEach(key => {
                                      activePetEffects[key] = false;
                                    });
                                    activePetEffects[equip.item_name] = effectKey;
                                  }
                                  activePetEffects = {...activePetEffects}; // Trigger reactivity
                                }}
                                title={effectTooltip}
                              >
                                {#if sameSkillCount === 1 && effect.Properties?.Strength}
                                  {skillName} {effect.Properties.Strength}{effect.Properties?.Unit || ''}
                                {:else}
                                  {skillName}
                                {/if}
                              </button>
                            {/each}
                          {/if}
                        </div>
                      </div>
                      {#if equip.notes}
                        <div class="equipment-notes">{equip.notes}</div>
                      {/if}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
            
            {#if medicalEquipment.length > 0}
              <div class="equipment-category">
                <h4>Medical Tools/Chips</h4>
                <ul class="equipment-list">
                  {#each medicalEquipment as equip (equip.item_name)}
                    <li class:active={activeMedicalEquipment?.item_name === equip.item_name}>
                      <div class="equipment-item-header">
                        <div class="equipment-item-main">
                          <div class="equipment-item-name-text">
                            {#if equip.item_name}
                              <a href={getItemInternalUrl(equip.item_type, equip.item_name)} class="equipment-item-link">
                                <strong>{equip.item_name}</strong>
                              </a>
                            {:else}
                              <strong class="unnamed-item">Item ID: {equip.item_id}</strong>
                            {/if}
                          </div>
                          <div class="equipment-item-badges">
                            {#if equip.tier !== null && equip.tier !== undefined}
                              <span class="tier-badge">T{equip.tier}</span>
                            {/if}
                            {#if equip.is_primary}
                              <span class="primary-badge">Primary</span>
                            {/if}
                            {#if equip.extra_price}
                              <span class="extra-price">+{parseFloat(equip.extra_price).toFixed(2)} PED/h</span>
                            {/if}
                          </div>
                          <div class="equipment-item-details">
                            {getItemTypeLabel(equip.item_type)}
                          </div>
                        </div>
                        <div class="button-group">
                          {#if equip.tier && equip.tier > 0}
                            <button 
                              class="toggle-btn tier-toggle" 
                              class:active={enabledTierEnhancers[equip.item_name]}
                              disabled={activeMedicalEquipment?.item_name !== equip.item_name}
                              onclick={() => enabledTierEnhancers[equip.item_name] = !enabledTierEnhancers[equip.item_name]}
                            >
                              {enabledTierEnhancers[equip.item_name] ? 'Tiers ON' : 'Tiers OFF'}
                            </button>
                          {/if}
                          <button 
                            class="use-btn" 
                            class:active={activeMedicalEquipment?.item_name === equip.item_name}
                            onclick={() => activeMedicalEquipment = equip}
                          >
                            {activeMedicalEquipment?.item_name === equip.item_name ? 'Active' : 'Use'}
                          </button>
                        </div>
                      </div>
                      {#if equip.notes}
                        <div class="equipment-notes">{equip.notes}</div>
                      {/if}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
            
            {#if armorEquipment.length > 0}
              <div class="equipment-category">
                <h4>Armor</h4>
                <ul class="equipment-list">
                  {#each armorEquipment as equip (equip.item_name)}
                    <li class:active={equip.tier && equip.tier > 0 ? enabledTierEnhancers[equip.item_name] === true : true}>
                      <div class="equipment-item-header">
                        <div class="equipment-item-main">
                          <div class="equipment-item-name-text">
                            {#if equip.item_name}
                              <a href={getItemInternalUrl(equip.item_type, equip.item_name)} class="equipment-item-link">
                                <strong>{equip.item_name}</strong>
                              </a>
                            {:else}
                              <strong class="unnamed-item">Item ID: {equip.item_id}</strong>
                            {/if}
                          </div>
                          <div class="equipment-item-badges">
                            {#if equip.tier !== null && equip.tier !== undefined}
                              <span class="tier-badge">T{equip.tier}</span>
                            {/if}
                            {#if equip.is_primary}
                              <span class="primary-badge">Primary</span>
                            {/if}
                            {#if hasAttachments(equip)}
                              <button class="attachments-badge" onclick={(e) => { e.stopPropagation(); openAttachmentDialog(equip); }} title="View attachments">
                                {countAttachments(equip)} attachment{countAttachments(equip) > 1 ? 's' : ''}
                              </button>
                            {/if}
                            {#if equip.extra_price}
                              <span class="extra-price">+{parseFloat(equip.extra_price).toFixed(2)} PED/h</span>
                            {/if}
                          </div>
                          <div class="equipment-item-details">
                            {getItemTypeLabel(equip.item_type)}
                          </div>
                        </div>
                        {#if equip.tier && equip.tier > 0}
                          <div class="button-group">
                            <button 
                              class="toggle-btn tier-toggle" 
                              class:active={enabledTierEnhancers[equip.item_name]}
                              onclick={() => enabledTierEnhancers[equip.item_name] = !enabledTierEnhancers[equip.item_name]}
                            >
                              {enabledTierEnhancers[equip.item_name] ? 'Tiers ON' : 'Tiers OFF'}
                            </button>
                          </div>
                        {/if}
                      </div>
                      {#if equip.notes}
                        <div class="equipment-notes">{equip.notes}</div>
                      {/if}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
            
            {#if clothingEquipment.length > 0}
              <div class="equipment-category">
                <h4>Clothing/Accessories</h4>
                <ul class="equipment-list">
                  {#each clothingEquipment as equip (equip.item_name)}
                    {@const slot = getClothingSlot(equip.item_name, clothingItems)}
                    <li class:active={equip.tier && equip.tier > 0 ? enabledTierEnhancers[equip.item_name] === true : true}>
                      <div class="equipment-item-header">
                        <div class="equipment-item-main">
                          <div class="equipment-item-name-text">
                            {#if equip.item_name}
                              <a href={getItemInternalUrl(equip.item_type, equip.item_name)} class="equipment-item-link">
                                <strong>{equip.item_name}</strong>
                              </a>
                            {:else}
                              <strong class="unnamed-item">Item ID: {equip.item_id}</strong>
                            {/if}
                          </div>
                          <div class="equipment-item-badges">
                            {#if equip.tier !== null && equip.tier !== undefined}
                              <span class="tier-badge">T{equip.tier}</span>
                            {/if}
                            {#if equip.is_primary}
                              <span class="primary-badge">Primary</span>
                            {/if}
                            {#if slot}
                              <span class="slot-badge">{slot.replace(/_/g, ' ')}</span>
                            {/if}
                            {#if equip.extra_price}
                              <span class="extra-price">+{parseFloat(equip.extra_price).toFixed(2)} PED/h</span>
                            {/if}
                          </div>
                          <div class="equipment-item-details">
                            {getItemTypeLabel(equip.item_type)}
                          </div>
                        </div>
                        {#if equip.tier && equip.tier > 0}
                          <div class="button-group">
                            <button 
                              class="toggle-btn tier-toggle" 
                              class:active={enabledTierEnhancers[equip.item_name]}
                              onclick={() => enabledTierEnhancers[equip.item_name] = !enabledTierEnhancers[equip.item_name]}
                            >
                              {enabledTierEnhancers[equip.item_name] ? 'Tiers ON' : 'Tiers OFF'}
                            </button>
                          </div>
                        {/if}
                      </div>
                      {#if equip.notes}
                        <div class="equipment-notes">{equip.notes}</div>
                      {/if}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
            
            {#if consumableEquipment.length > 0}
              <div class="equipment-category">
                <h4>Consumables</h4>
                <ul class="equipment-list">
                  {#each consumableEquipment as equip (equip.item_name)}
                    {@const consumableData = consumables.find(item => item.Name === equip.item_name)}
                    {@const isEnhancer = consumableData?.Properties?.Type === 'Enhancer'}
                    <li class:active={enabledConsumables[equip.item_name] === true}>
                      <div class="equipment-item-header">
                        <div class="equipment-item-main">
                          <div class="equipment-item-name-text">
                            {#if equip.item_name}
                              <a href={getItemInternalUrl(equip.item_type, equip.item_name)} class="equipment-item-link">
                                <strong>{equip.item_name}</strong>
                              </a>
                            {:else}
                              <strong class="unnamed-item">Item ID: {equip.item_id}</strong>
                            {/if}
                          </div>
                          <div class="equipment-item-badges">
                            {#if isEnhancer}
                              <span class="enhancer-badge">Enhancer</span>
                            {/if}
                            {#if equip.extra_price}
                              <span class="extra-price">+{parseFloat(equip.extra_price).toFixed(2)} PED/h</span>
                            {/if}
                          </div>
                          <div class="equipment-item-details">
                            {getItemTypeLabel(equip.item_type)}
                          </div>
                        </div>
                        <button 
                          class="toggle-btn" 
                          class:active={enabledConsumables[equip.item_name]}
                          onclick={() => enabledConsumables[equip.item_name] = !enabledConsumables[equip.item_name]}
                        >
                          {enabledConsumables[equip.item_name] ? 'Enabled' : 'Disabled'}
                        </button>
                      </div>
                      {#if equip.notes}
                        <div class="equipment-notes">{equip.notes}</div>
                      {/if}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
          </div>
        {/if}

        {#if selectedService.review_stats}
          <div class="info-section">
            <h3>Reviews</h3>
            <p>
              Average: {selectedService.review_stats.average}/10
              ({selectedService.review_stats.count} reviews)
            </p>
          </div>
        {/if}
      </div>

      <!-- Availability Section (only for non-scheduled services) -->
      {#if !(selectedService.type === 'transportation' && selectedService.transportation_details?.service_mode === 'scheduled')}
        <div class="availability-section">
          <div class="availability-header">
            <h3>Availability</h3>
            {#if isOwner}
              <a href="/market/services/{selectedService.id}/availability" class="edit-availability-link">Edit Availability</a>
            {/if}
          </div>
          {#if availability.length > 0}
            <AvailabilityCalendar {availability} readonly={true} />
          {:else}
            <p class="no-availability">No availability schedule set.</p>
          {/if}
        </div>
      {/if}

    </div>
  {/if}
  </div>
</div>

{#if showRequestModal}
  <div class="modal-backdrop" onclick={closeRequestModal}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <h2>{selectedService.title}</h2>
        <button class="modal-close" onclick={closeRequestModal}>&times;</button>
      </div>

      {#if selectedService.type === 'transportation'}
        <div class="modal-tabs">
          <button
            class="modal-tab"
            class:active={requestFormTab === 'request'}
            onclick={() => requestFormTab = 'request'}
          >
            Request Flight
          </button>
          <button
            class="modal-tab"
            class:active={requestFormTab === 'question'}
            onclick={() => requestFormTab = 'question'}
          >
            Ask a Question
          </button>
        </div>
      {/if}

      <div class="modal-body">
        {#if user.id === selectedService.user_id && !user.grants?.includes('admin.panel')}
          <div class="owner-preview-notice">
            <strong>Owner Preview Mode</strong>
            <p>This is how customers see the request form. You cannot submit requests for your own service.</p>
          </div>
        {:else if user.id === selectedService.user_id && user.grants?.includes('admin.panel')}
          <div class="admin-notice">
            <strong>Admin Mode</strong>
            <p>As an admin, you can submit requests for your own service for testing purposes.</p>
          </div>
        {/if}

        {#if requestFormTab === 'request' && selectedService?.type === 'transportation'}
          {@const needsTicket = !userHasTicket && !hasSingleUseOffer}
          {@const formDisabled = needsTicket || (user.id === selectedService.user_id && !user.grants?.includes('admin.panel'))}

          {#if needsTicket}
            <div class="ticket-required-notice">
              <strong>Ticket Required</strong>
              <p>You need to purchase a multi-use ticket before requesting a flight. Please visit the "Ticket Offers" section below to purchase a ticket.</p>
              <p class="muted-text">Note: Single-use tickets are purchased automatically when requesting, but none are currently available.</p>
            </div>
          {:else if !userHasTicket && hasSingleUseOffer}
            <div class="ticket-info-notice">
              <strong>Automatic Ticket Purchase</strong>
              <p>A single-use ticket will be automatically purchased when you submit this request.</p>
            </div>
          {/if}

          <!-- Transportation: Pickup and Destination (required) -->
          <div class="form-group">
            <label for="request-pickup-planet">Pickup Planet *</label>
            <select id="request-pickup-planet" bind:value={requestPlanetId} disabled={formDisabled}>
              <option value={null}>-- Select pickup planet --</option>
              {#each mainPlanets as planet}
                <option value={planet.Id}>{planet.Name}</option>
              {/each}
            </select>
            <small>The planet where you want to be picked up</small>
          </div>

          <div class="form-group">
            <label for="request-destination-planet">Destination Planet *</label>
            <select id="request-destination-planet" bind:value={requestDestinationPlanetId} disabled={formDisabled}>
              <option value={null}>-- Select destination planet --</option>
              {#each mainPlanets as planet}
                <option value={planet.Id}>{planet.Name}</option>
              {/each}
            </select>
            <small>The planet where you want to be dropped off</small>
          </div>

          <div class="form-group">
            <label for="request-message">Message to Provider (optional)</label>
            <textarea
              id="request-message"
              bind:value={requestMessage}
              placeholder="Any additional notes for the pilot (optional)"
              rows="3"
              disabled={formDisabled}
            ></textarea>
          </div>
        {:else}
          {#if activeRequest && activeRequest.discord_thread_id && !isOwner}
            <div class="discord-thread-notice">
              <strong>A Discord thread already exists for your active request.</strong>
              <p>You can ask questions directly in the thread where the provider can see and respond to them.</p>
              <a href="/market/services/my/requests/{activeRequest.id}" class="thread-link-btn">View Your Request</a>
            </div>
          {:else}
            <div class="form-group">
              <label for="question-message">Your Question *</label>
              <textarea
                id="question-message"
                bind:value={questionMessage}
                placeholder="Ask the provider a question about their service..."
                rows="5"
              ></textarea>
            </div>
            <p class="form-hint">The provider will receive your question and can respond via Discord or in-game.</p>
          {/if}
        {/if}

        {#if requestError}
          <div class="modal-error">{requestError}</div>
        {/if}
      </div>

      <div class="modal-footer">
        <button class="modal-btn cancel-btn" onclick={closeRequestModal} disabled={requestSubmitting}>
          Cancel
        </button>
        {#if requestFormTab === 'request'}
          {@const needsTicket = selectedService?.type === 'transportation' && !userHasTicket && !hasSingleUseOffer}
          {@const missingFlightInfo = selectedService?.type === 'transportation' && (!requestPlanetId || !requestDestinationPlanetId)}
          <button
            class="modal-btn submit-btn"
            onclick={submitRequest}
            disabled={requestSubmitting || needsTicket || missingFlightInfo || (user.id === selectedService.user_id && !user.grants?.includes('admin.panel'))}
          >
            {requestSubmitting ? 'Submitting...' : 'Submit Request'}
          </button>
        {:else}
          {#if !(activeRequest && activeRequest.discord_thread_id && !isOwner)}
            <button
              class="modal-btn submit-btn"
              onclick={submitQuestion}
              disabled={requestSubmitting || !questionMessage.trim()}
            >
              {requestSubmitting ? 'Sending...' : 'Send Question'}
            </button>
          {/if}
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Attachment Details Dialog -->
{#if showAttachmentDialog && attachmentDialogData}
  {@const att = attachmentDialogData.attachments}
  {@const item = attachmentDialogData.item}
  {@const weaponClass = att.weaponClass}
  <div class="modal-backdrop" onclick={closeAttachmentDialog}>
    <div class="attachment-dialog" onclick={(e) => e.stopPropagation()}>
      <div class="dialog-header">
        <h3>Attachments for {item.item_name}</h3>
        <button class="modal-close" onclick={closeAttachmentDialog}>&times;</button>
      </div>
      <div class="dialog-body">
        {#if weaponClass}
          <div class="weapon-class-indicator">{weaponClass} Weapon</div>
        {/if}

        <!-- Common attachments for ALL weapon types -->
        {#if weaponClass && (weaponClass === 'Ranged' || weaponClass === 'Melee' || weaponClass === 'Mindforce')}
          {#if att.amplifier_name}
            {@const ampData = weaponAmplifiers.find(a => a.ItemId === att.amplifier_id)}
            <div class="attachment-item">
              <div class="attachment-row">
                <span class="attachment-type">Amplifier</span>
                <a href={getAttachmentUrl('amplifier', att.amplifier_name)} class="attachment-link">{att.amplifier_name}</a>
              </div>
              {#if ampData}
                <div class="attachment-stats">
                  {#if ampData.Properties?.Damage}
                    {@const totalDmg = (ampData.Properties.Damage.Impact || 0) + (ampData.Properties.Damage.Cut || 0) + (ampData.Properties.Damage.Stab || 0) + (ampData.Properties.Damage.Penetration || 0) + (ampData.Properties.Damage.Shrapnel || 0) + (ampData.Properties.Damage.Burn || 0) + (ampData.Properties.Damage.Cold || 0) + (ampData.Properties.Damage.Acid || 0) + (ampData.Properties.Damage.Electric || 0)}
                    <span class="stat">Damage: +{totalDmg.toFixed(1)}</span>
                  {/if}
                  {#if ampData.Properties?.Economy?.Decay}
                    <span class="stat">Decay: {ampData.Properties.Economy.Decay.toFixed(4)} PEC</span>
                  {/if}
                  {#if ampData.Properties?.Economy?.Efficiency}
                    <span class="stat">Efficiency: {ampData.Properties.Economy.Efficiency.toFixed(1)}%</span>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}

          {#if att.absorber_name}
            {@const absData = absorbers.find(a => a.ItemId === att.absorber_id)}
            <div class="attachment-item">
              <div class="attachment-row">
                <span class="attachment-type">Absorber</span>
                <a href={getAttachmentUrl('absorber', att.absorber_name)} class="attachment-link">{att.absorber_name}</a>
              </div>
              {#if absData}
                <div class="attachment-stats">
                  {#if absData.Properties?.Economy?.Absorption}
                    <span class="stat">Absorption: {(absData.Properties.Economy.Absorption * 100).toFixed(1)}%</span>
                  {/if}
                  {#if absData.Properties?.Economy?.Efficiency}
                    <span class="stat">Efficiency: {absData.Properties.Economy.Efficiency.toFixed(1)}%</span>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        {/if}

        <!-- Class-specific attachments -->
        {#if weaponClass === 'Ranged'}
          {#if att.scope_name}
            {@const scopeData = weaponVisionAttachments.find(v => v.ItemId === att.scope_id)}
            <div class="attachment-item">
              <div class="attachment-row">
                <span class="attachment-type">Scope</span>
                <a href={getAttachmentUrl('scope', att.scope_name)} class="attachment-link">{att.scope_name}</a>
              </div>
              {#if scopeData}
                <div class="attachment-stats">
                  {#if scopeData.Properties?.SkillModification}
                    <span class="stat">Skill Mod: +{scopeData.Properties.SkillModification.toFixed(1)}</span>
                  {/if}
                  {#if scopeData.Properties?.Economy?.Decay}
                    <span class="stat">Decay: {scopeData.Properties.Economy.Decay.toFixed(4)} PEC</span>
                  {/if}
                </div>
              {/if}
            </div>

            {#if att.scope_sight_name}
              {@const scopeSightData = weaponVisionAttachments.find(v => v.ItemId === att.scope_sight_id)}
              <div class="attachment-item nested">
                <div class="attachment-row">
                  <span class="attachment-type"><span class="nested-arrow">↳</span> Scope Sight</span>
                  <a href={getAttachmentUrl('sight', att.scope_sight_name)} class="attachment-link">{att.scope_sight_name}</a>
                </div>
                {#if scopeSightData}
                  <div class="attachment-stats">
                    {#if scopeSightData.Properties?.SkillModification}
                      <span class="stat">Skill Mod: +{scopeSightData.Properties.SkillModification.toFixed(1)}</span>
                    {/if}
                    {#if scopeSightData.Properties?.Economy?.Decay}
                      <span class="stat">Decay: {scopeSightData.Properties.Economy.Decay.toFixed(4)} PEC</span>
                    {/if}
                  </div>
                {/if}
              </div>
            {/if}
          {/if}

          {#if att.sight_name}
            {@const sightData = weaponVisionAttachments.find(v => v.ItemId === att.sight_id)}
            <div class="attachment-item">
              <div class="attachment-row">
                <span class="attachment-type">Sight</span>
                <a href={getAttachmentUrl('sight', att.sight_name)} class="attachment-link">{att.sight_name}</a>
              </div>
              {#if sightData}
                <div class="attachment-stats">
                  {#if sightData.Properties?.SkillModification}
                    <span class="stat">Skill Mod: +{sightData.Properties.SkillModification.toFixed(1)}</span>
                  {/if}
                  {#if sightData.Properties?.Economy?.Decay}
                    <span class="stat">Decay: {sightData.Properties.Economy.Decay.toFixed(4)} PEC</span>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}

        {:else if weaponClass === 'Melee'}
          <!-- Melee weapon attachments -->
          {#if att.matrix_name}
            {@const matrixData = weaponAmplifiers.find(a => a.ItemId === att.matrix_id)}
            <div class="attachment-item">
              <div class="attachment-row">
                <span class="attachment-type">Matrix</span>
                <a href={getAttachmentUrl('matrix', att.matrix_name)} class="attachment-link">{att.matrix_name}</a>
              </div>
              {#if matrixData}
                <div class="attachment-stats">
                  {#if matrixData.Properties?.Damage}
                    {@const totalDmg = (matrixData.Properties.Damage.Impact || 0) + (matrixData.Properties.Damage.Cut || 0) + (matrixData.Properties.Damage.Stab || 0) + (matrixData.Properties.Damage.Penetration || 0) + (matrixData.Properties.Damage.Shrapnel || 0) + (matrixData.Properties.Damage.Burn || 0) + (matrixData.Properties.Damage.Cold || 0) + (matrixData.Properties.Damage.Acid || 0) + (matrixData.Properties.Damage.Electric || 0)}
                    <span class="stat">Damage: +{totalDmg.toFixed(1)}</span>
                  {/if}
                  {#if matrixData.Properties?.Economy?.Decay}
                    <span class="stat">Decay: {matrixData.Properties.Economy.Decay.toFixed(4)} PEC</span>
                  {/if}
                  {#if matrixData.Properties?.Economy?.Efficiency}
                    <span class="stat">Efficiency: {matrixData.Properties.Economy.Efficiency.toFixed(1)}%</span>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}

        {:else if weaponClass === 'Mindforce'}
          <!-- Mindforce weapon attachments -->
          {#if att.implant_name}
            {@const implantData = mindforceImplants.find(i => i.ItemId === att.implant_id)}
            <div class="attachment-item">
              <div class="attachment-row">
                <span class="attachment-type">Implant</span>
                <a href={getAttachmentUrl('implant', att.implant_name)} class="attachment-link">{att.implant_name}</a>
              </div>
              {#if implantData}
                <div class="attachment-stats">
                  {#if implantData.Properties?.Economy?.Absorption}
                    <span class="stat">Absorption: {(implantData.Properties.Economy.Absorption * 100).toFixed(1)}%</span>
                  {/if}
                  {#if implantData.Properties?.Economy?.Efficiency}
                    <span class="stat">Efficiency: {implantData.Properties.Economy.Efficiency.toFixed(1)}%</span>
                  {/if}
                </div>
              {/if}
            </div>
          {/if}
        {/if}

        <!-- Armor plating (no weapon class) -->
        {#if att.plate_name}
          {@const plateData = armorPlatings.find(p => p.Name === att.plate_name)}
          <div class="attachment-item">
            <div class="attachment-row">
              <span class="attachment-type">Plating</span>
              <a href={getAttachmentUrl('plate', att.plate_name)} class="attachment-link">{att.plate_name}</a>
            </div>
            {#if plateData}
              <div class="attachment-stats">
                {#if plateData.Properties?.Defense}
                  {@const totalDef = (plateData.Properties.Defense.Impact || 0) + (plateData.Properties.Defense.Cut || 0) + (plateData.Properties.Defense.Stab || 0) + (plateData.Properties.Defense.Penetration || 0) + (plateData.Properties.Defense.Shrapnel || 0) + (plateData.Properties.Defense.Burn || 0) + (plateData.Properties.Defense.Cold || 0) + (plateData.Properties.Defense.Acid || 0) + (plateData.Properties.Defense.Electric || 0)}
                  <span class="stat">Defense: +{totalDef.toFixed(1)}</span>
                {/if}
                {#if plateData.Properties?.Defense?.Block}
                  <span class="stat">Block: {plateData.Properties.Defense.Block.toFixed(1)}%</span>
                {/if}
                {#if plateData.Properties?.Economy?.Durability}
                  <span class="stat">Durability: {plateData.Properties.Economy.Durability.toFixed(0)}</span>
                {/if}
              </div>
            {/if}
          </div>
        {/if}

        {#if !hasAttachments(item)}
          <p class="no-attachments">No attachments configured.</p>
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="btn secondary" onclick={closeAttachmentDialog}>Close</button>
      </div>
    </div>
  </div>
{/if}

<!-- Check-in Dialog -->
{#if showCheckinDialog && checkinFlight}
  <div class="modal-backdrop" onclick={closeCheckinDialog}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <h2>Check In to Flight</h2>
        <button class="modal-close" onclick={closeCheckinDialog}>&times;</button>
      </div>

      <div class="modal-body">
        <p><strong>Scheduled Departure:</strong> {new Date(checkinFlight.scheduled_departure).toLocaleString()}</p>

        {#if checkinFlight.route_type === 'flexible'}
          <p class="form-hint">This is a flexible route flight. Please specify where you want to be picked up and dropped off.</p>

          <div class="form-group">
            <label for="checkin-location">Pickup Location *</label>
            <input
              type="text"
              id="checkin-location"
              bind:value={checkinLocation}
              placeholder="e.g., Port Atlantis, Twin Peaks"
              required
            />
          </div>

          <div class="form-group">
            <label for="checkin-planet">Pickup Planet *</label>
            <select id="checkin-planet" bind:value={checkinPlanetId} required>
              <option value={null}>-- Select planet --</option>
              {#each planets as planet}
                <option value={planet.id}>{planet.Name}</option>
              {/each}
            </select>
          </div>

          <div class="form-group">
            <label for="checkin-exit-location">Dropoff Location *</label>
            <input
              type="text"
              id="checkin-exit-location"
              bind:value={checkinExitLocation}
              placeholder="e.g., Crystal Palace, Minopolis"
              required
            />
          </div>

          <div class="form-group">
            <label for="checkin-exit-planet">Dropoff Planet *</label>
            <select id="checkin-exit-planet" bind:value={checkinExitPlanetId} required>
              <option value={null}>-- Select planet --</option>
              {#each planets as planet}
                <option value={planet.id}>{planet.Name}</option>
              {/each}
            </select>
          </div>
        {:else}
          {@const routeStops = typeof checkinFlight.route_stops === 'string' ? JSON.parse(checkinFlight.route_stops) : checkinFlight.route_stops}
          <div class="form-group">
            <label>Fixed Route</label>
            <p class="route-display">
              {#each routeStops as stop, i}
                {stop.name || `Planet ${stop.planet_id}`}{#if i < routeStops.length - 1} → {/if}
              {/each}
            </p>
          </div>

          <div class="form-group">
            <label for="checkin-location">Boarding Location *</label>
            <input
              type="text"
              id="checkin-location"
              bind:value={checkinLocation}
              placeholder="e.g., Port Atlantis, Twin Peaks"
              required
            />
          </div>

          <div class="form-group">
            <label for="checkin-planet">Boarding Planet *</label>
            <select id="checkin-planet" bind:value={checkinPlanetId} required>
              <option value={null}>-- Select planet --</option>
              {#each planets as planet}
                <option value={planet.id}>{planet.Name}</option>
              {/each}
            </select>
          </div>
        {/if}

        <p class="form-hint">You can cancel your check-in anytime before the flight enters warp.</p>
      </div>

      <div class="modal-footer">
        <button class="modal-btn cancel-btn" onclick={closeCheckinDialog} disabled={checkinSubmitting}>
          Cancel
        </button>
        <button
          class="modal-btn submit-btn"
          onclick={submitCheckin}
          disabled={checkinSubmitting || !checkinLocation.trim() || !checkinPlanetId || (checkinFlight.route_type === 'flexible' && (!checkinExitLocation.trim() || !checkinExitPlanetId))}
        >
          {checkinSubmitting ? 'Checking In...' : 'Check In'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    padding: 1rem;
    padding-bottom: 2rem;
    max-width: 1200px;
    margin: 0 auto;
    box-sizing: border-box;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 1.5rem;
    gap: 1rem;
  }

  .header-left h1 {
    margin: 0 0 0.25rem;
    font-size: 1.75rem;
  }

  .subtitle {
    margin: 0;
    color: var(--text-muted);
    font-size: 0.95rem;
  }

  .header-actions {
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
    flex-wrap: wrap;
  }

  .btn-primary, .btn-secondary {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    text-decoration: none;
    white-space: nowrap;
    border: none;
    cursor: pointer;
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
  }

  .btn-primary:hover {
    background: var(--accent-color-hover);
  }

  .btn-secondary {
    background: transparent;
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }

  .btn-secondary:hover {
    background: var(--hover-color);
  }

  .btn-success {
    padding: 0.5rem 1rem;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    text-decoration: none;
    white-space: nowrap;
    background: var(--success-color);
    color: white;
    border: none;
    cursor: pointer;
  }

  .btn-success:hover {
    background: var(--success-color-hover);
  }

  .active-request-banner {
    background: var(--success-bg);
    border: 1px solid var(--success-color);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .active-request-banner .banner-content {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .active-request-banner .banner-title {
    font-weight: 600;
    color: var(--success-color-hover);
  }

  .active-request-banner .banner-text {
    font-size: 0.9rem;
    color: var(--text-muted);
  }

  .active-request-banner .banner-link {
    background: var(--success-color);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-size: 0.9rem;
    white-space: nowrap;
  }

  .active-request-banner .banner-link:hover {
    background: var(--success-color-hover);
  }

  .filters {
    display: flex;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .filter-group select {
    padding: 0.5rem 0.75rem;
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    font-size: 0.9rem;
    min-width: 150px;
    box-sizing: border-box;
  }

  .filter-group select:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .tab-group {
    display: flex;
    gap: 0.25rem;
  }

  .tab-btn {
    padding: 0.5rem 1rem;
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-muted);
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
  }

  .tab-btn:hover {
    background: var(--hover-color);
    color: var(--text-color);
  }

  .tab-btn.active {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .tab-count {
    font-size: 0.8rem;
    font-weight: 400;
    opacity: 0.8;
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .service-detail {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1.5rem;
  }

  .header-badges {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  .service-type-badge {
    background: var(--accent-color);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }

  .busy-badge {
    background: var(--error-color);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }

  .inactive-badge {
    background: var(--text-muted);
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }

  .inactive-banner {
    background: var(--warning-bg);
    border: 1px solid var(--warning-color);
    color: var(--warning-color);
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
  }

  .inactive-banner strong {
    display: block;
    margin-bottom: 0.5rem;
  }

  .inactive-banner p {
    margin: 0;
    font-size: 0.9rem;
  }

  .inactive-banner a {
    color: var(--accent-color);
  }

  .service-info {
    display: grid;
    gap: 1rem;
  }

  .info-section h3 {
    margin: 0 0 0.5rem 0;
    font-size: 0.9rem;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .info-section p {
    margin: 0;
  }

  .pilots-list {
    margin-top: 0.5rem;
    font-size: 0.95rem;
    color: var(--text-muted);
  }

  .provider-link {
    color: var(--accent-color);
    text-decoration: none;
  }

  .provider-link:hover {
    text-decoration: underline;
  }

  .equipment-list {
    margin: 0;
    padding-left: 1.5rem;
  }

  .equipment-list li {
    margin-bottom: 0.25rem;
  }

  .availability-section {
    margin-top: 1.5rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border-color);
  }

  .availability-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .availability-header h3 {
    margin: 0;
    font-size: 1rem;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .edit-availability-link {
    color: var(--accent-color);
    text-decoration: none;
    font-size: 0.9rem;
  }

  .edit-availability-link:hover {
    text-decoration: underline;
  }

  .no-availability {
    color: var(--text-muted);
    font-style: italic;
    margin: 0;
  }

  @media (max-width: 768px) {
    .page-container {
      padding: 0.75rem;
    }

    .page-header {
      flex-direction: column;
    }

    .header-actions {
      width: 100%;
    }

    .btn-primary, .btn-secondary, .btn-success {
      flex: 1;
      text-align: center;
    }

    .filters {
      flex-direction: column;
    }

    .tab-group {
      width: 100%;
      flex-wrap: wrap;
    }

    .tab-btn {
      flex: 1;
      text-align: center;
    }

    .filter-group select {
      width: 100%;
      min-width: unset;
    }

    .service-detail {
      padding: 1rem;
    }
  }

  /* Modal Styles */
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
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 100%;
    max-width: 600px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid var(--border-color);
  }

  .modal-header h2 {
    margin: 0;
    font-size: 1.25rem;
    color: var(--text-color);
  }

  .modal-tabs {
    display: flex;
    border-bottom: 1px solid var(--border-color);
  }

  .modal-tab {
    flex: 1;
    padding: 0.75rem 1rem;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.95rem;
    transition: all 0.2s ease;
  }

  .modal-tab:hover {
    color: var(--text-color);
  }

  .modal-tab.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
  }

  .admin-notice {
    background: var(--accent-color-bg);
    border: 1px solid var(--accent-color);
    color: var(--accent-color);
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
  }

  .admin-notice strong {
    display: block;
    margin-bottom: 0.5rem;
  }

  .admin-notice p {
    margin: 0;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  @media (max-width: 500px) {
    .form-row {
      grid-template-columns: 1fr;
    }
  }

  .form-hint {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0;
  }

  .modal-close {
    background: none;
    border: none;
    color: var(--text-color);
    font-size: 2rem;
    cursor: pointer;
    line-height: 1;
    padding: 0;
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-close:hover {
    color: var(--accent-color);
  }

  .modal-body {
    padding: 1.5rem;
  }

  .owner-preview-notice {
    background: var(--warning-bg);
    border: 1px solid var(--warning-color);
    color: var(--warning-color);
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
  }

  .owner-preview-notice strong {
    display: block;
    margin-bottom: 0.5rem;
  }

  .owner-preview-notice p {
    margin: 0;
  }

  .ticket-required-notice {
    background: var(--error-bg);
    border: 1px solid var(--error-color);
    color: var(--text-color);
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
  }

  .ticket-required-notice strong {
    display: block;
    margin-bottom: 0.5rem;
    color: var(--error-color);
  }

  .ticket-required-notice p {
    margin: 0.5rem 0;
  }

  .ticket-info-notice {
    background: var(--accent-color-bg);
    border: 1px solid var(--accent-color);
    color: var(--text-color);
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
  }

  .ticket-info-notice strong {
    display: block;
    margin-bottom: 0.5rem;
    color: var(--accent-color);
  }

  .ticket-info-notice p {
    margin: 0.5rem 0;
  }

  .form-group {
    margin-bottom: 1.5rem;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.75rem;
    color: var(--text-color);
    font-weight: 500;
  }

  .form-group input,
  .form-group textarea,
  .form-group select {
    width: 100%;
    padding: 0.75rem;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    font-family: inherit;
    font-size: 1rem;
    box-sizing: border-box;
  }

  .form-group select {
    cursor: pointer;
  }

  .form-group select:hover {
    background: var(--hover-color);
  }

  .form-group select option {
    background: var(--secondary-color);
    color: var(--text-color);
  }

  .form-group input:focus,
  .form-group textarea:focus,
  .form-group select:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .form-group input:disabled,
  .form-group textarea:disabled,
  .form-group select:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .form-group textarea {
    resize: none;
    min-height: 100px;
  }

  .form-group small {
    display: block;
    margin-top: 0.375rem;
    font-size: 0.85rem;
    color: var(--text-muted);
  }

  .modal-error {
    background: var(--error-bg);
    border: 1px solid var(--error-color);
    color: var(--error-color);
    padding: 0.75rem;
    border-radius: 4px;
    margin-top: 1rem;
  }

  .discord-thread-notice {
    background: var(--success-bg);
    border: 1px solid var(--success-color);
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
  }

  .discord-thread-notice strong {
    color: var(--success-color-hover);
    display: block;
    margin-bottom: 0.5rem;
  }

  .discord-thread-notice p {
    color: var(--text-muted);
    font-size: 0.9rem;
    margin: 0 0 1rem 0;
  }

  .discord-thread-notice .thread-link-btn {
    display: inline-block;
    background: var(--success-color);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-size: 0.9rem;
  }

  .discord-thread-notice .thread-link-btn:hover {
    background: var(--success-color-hover);
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    padding: 1.5rem;
    border-top: 1px solid var(--border-color);
  }

  .modal-btn {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 4px;
    font-size: 1rem;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .cancel-btn {
    background: var(--secondary-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }

  .cancel-btn:hover:not(:disabled) {
    background: var(--hover-color);
  }

  .submit-btn {
    background: var(--accent-color);
    color: white;
  }

  .submit-btn:hover:not(:disabled) {
    background: var(--accent-color-hover);
  }

  .modal-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .equipment-category {
    margin-bottom: 1.5rem;
  }

  .equipment-category h4 {
    color: var(--accent-color);
    margin-bottom: 0.75rem;
    font-size: 1rem;
    font-weight: 600;
  }

  .equipment-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .equipment-list li {
    background: var(--main-color);
    border: 1px solid var(--border-color);
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    border-radius: 4px;
  }

  .equipment-list li.active {
    background: linear-gradient(to right, rgba(74, 158, 255, 0.25), rgba(74, 158, 255, 0.12));
    border-color: var(--accent-color);
    box-shadow: inset 0 0 0 1px rgba(74, 158, 255, 0.3);
  }
  
  .equipment-item-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .equipment-item-main {
    flex: 1;
    display: grid;
    grid-template-columns: auto 1fr;
    grid-template-rows: auto auto;
    gap: 0.25rem 0.5rem;
    min-width: 0;
  }

  .equipment-item-name-text {
    font-weight: 500;
    grid-column: 1;
    grid-row: 1;
  }

  .equipment-item-badges {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    grid-column: 2;
    grid-row: 1 / 3;
    align-content: flex-start;
  }

  .equipment-item-details {
    font-size: 0.9rem;
    color: var(--text-muted);
    grid-column: 1;
    grid-row: 2;
  }
  
  .equipment-category:first-child .equipment-list li {
    border-color: var(--accent-color);
    background: linear-gradient(to right, rgba(74, 158, 255, 0.15), var(--main-color));
  }

  .use-btn,
  .toggle-btn {
    margin-left: auto;
    padding: 0.35rem 0.75rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s;
    border: 1px solid var(--border-color);
  }

  .use-btn {
    background: var(--main-color);
    color: var(--text-muted);
  }

  .use-btn:hover {
    background: var(--hover-color);
    border-color: var(--accent-color);
  }

  .use-btn.active {
    background: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .toggle-btn {
    background: var(--main-color);
    color: var(--text-muted);
  }

  .toggle-btn:hover {
    background: var(--hover-color);
    border-color: var(--success-color);
  }

  .toggle-btn.active {
    background: var(--success-color);
    color: white;
    border-color: var(--success-color);
  }

  .toggle-btn.tier-toggle {
    margin-left: auto;
    background: var(--main-color);
    color: var(--text-muted);
  }

  .toggle-btn.tier-toggle:hover {
    background: var(--hover-color);
    border-color: #764ba2;
  }

  .toggle-btn.tier-toggle.active {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border-color: #667eea;
  }

  .toggle-btn.tier-toggle:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    background: var(--main-color);
    color: var(--text-muted);
    border-color: var(--border-color);
  }

  .toggle-btn.tier-toggle:disabled:hover {
    background: var(--main-color);
    border-color: var(--border-color);
  }

  .enhancer-badge {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .equipment-list li strong {
    color: var(--text-color);
    margin-right: 0.5rem;
  }
  
  .equipment-item-link {
    color: var(--accent-color);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
  }
  
  .equipment-item-link:hover {
    text-decoration: underline;
  }
  
  .equipment-item-link strong {
    color: var(--accent-color);
  }
  
  .import-loadout-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    padding: 0.35rem 0.75rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.2s, box-shadow 0.2s;
    margin-left: auto;
  }
  
  .import-loadout-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
  }
  
  .import-loadout-btn:active {
    transform: translateY(0);
  }

  .tier-badge {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .primary-badge {
    background: linear-gradient(135deg, #ffa500 0%, #ff8c00 100%);
    color: white;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
    border: 1px solid var(--accent-color);
  }

  .attachments-badge {
    background: linear-gradient(135deg, #2d9cdb 0%, #56ccf2 100%);
    color: white;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: transform 0.1s, box-shadow 0.1s;
  }

  .attachments-badge:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(45, 156, 219, 0.4);
  }

  .button-group {
    margin-left: auto;
    display: flex;
    gap: 0.5rem;
  }

  .slot-badge {
    background: var(--main-color);
    color: var(--text-muted);
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    text-transform: capitalize;
  }

  .item-type-badge {
    background: var(--main-color);
    color: var(--text-muted);
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    text-transform: capitalize;
  }

  .extra-price {
    color: var(--accent-color);
    font-weight: 600;
    font-size: 0.85rem;
  }

  .formula-text {
    color: var(--text-muted);
    font-size: 0.8rem;
    font-weight: normal;
    font-style: italic;
    margin-left: 0.5rem;
  }

  .equipment-notes {
    width: 100%;
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid var(--border-color);
    color: var(--text-muted);
    font-size: 0.85rem;
    font-style: italic;
  }
  
  .unnamed-item {
    color: var(--text-muted);
    font-style: italic;
  }

  .protection-stats {
    margin-top: 1.5rem;
    padding: 1rem;
    background: var(--hover-color);
    border-radius: 4px;
  }

  .protection-stats h4 {
    margin: 0 0 1rem 0;
    color: var(--text-color);
  }

  .damage-type-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 0.5rem;
  }

  .damage-type {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem;
    background: var(--secondary-color);
    border-radius: 4px;
    font-size: 0.9rem;
  }

  .damage-label {
    font-weight: 600;
    color: var(--text-color);
  }

  .damage-values {
    color: var(--accent-color);
    font-family: monospace;
  }

  .pet-effects {
    margin-top: 0.75rem;
    padding: 0.75rem;
    background: var(--hover-color);
    border-radius: 4px;
    font-size: 0.85rem;
  }

  @media (max-width: 600px) {
    .modal-header {
      padding: 1rem;
    }

    .modal-body {
      padding: 1rem;
    }

    .modal-footer {
      padding: 1rem;
      flex-direction: column;
    }

    .modal-btn {
      width: 100%;
    }
  }

  /* Attachment Dialog Styles */
  .attachment-dialog {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 90%;
    max-width: 500px;
    max-height: 80vh;
    overflow-y: auto;
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    border-bottom: 1px solid var(--border-color);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 1.1rem;
    color: var(--text-color);
  }

  .dialog-body {
    padding: 1rem;
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    padding: 1rem;
    border-top: 1px solid var(--border-color);
  }

  .weapon-class-indicator {
    background: var(--accent-color);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 4px;
    font-size: 0.85rem;
    font-weight: 500;
    display: inline-block;
    margin-bottom: 1rem;
  }

  .attachment-item {
    background: var(--main-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 0.75rem;
    margin-bottom: 0.75rem;
  }

  .attachment-item.nested {
    margin-left: 1.5rem;
    border-left: 3px solid var(--accent-color);
  }

  .attachment-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .attachment-type {
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .attachment-type .nested-arrow {
    color: var(--accent-color);
    margin-right: 0.25rem;
  }

  .attachment-link {
    color: var(--accent-color);
    text-decoration: none;
    font-weight: 500;
  }

  .attachment-link:hover {
    text-decoration: underline;
  }

  .attachment-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .attachment-stats .stat {
    background: var(--secondary-color);
    color: var(--text-color);
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
    font-size: 0.8rem;
  }

  .no-attachments {
    color: var(--text-muted);
    font-style: italic;
    text-align: center;
    padding: 1rem;
  }

  .section-header-with-action {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
  }

  .section-header-with-action h3 {
    margin: 0;
  }

  .manage-btn {
    background: var(--accent-color);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-weight: 500;
    font-size: 0.875rem;
  }

  .manage-btn:hover {
    background: var(--accent-color-hover);
    text-decoration: none;
  }

  .manage-btn.primary {
    background: var(--success-color);
  }

  .manage-btn.primary:hover {
    background: var(--success-color-hover);
  }

  .flight-dashboard-section {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(16, 185, 129, 0.05) 100%);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
  }

  .flight-dashboard-label {
    font-weight: 600;
    color: var(--success-color);
  }

  .admin-note {
    background: var(--accent-color-bg);
    color: var(--accent-color);
    padding: 0.75rem;
    border-radius: 4px;
    margin-bottom: 0.75rem;
    font-size: 0.875rem;
  }

  .admin-note em {
    font-style: normal;
  }

  .ticket-offers-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1rem;
    margin-top: 0.75rem;
  }

  .muted-text {
    color: var(--text-muted);
  }

  .manage-link {
    display: inline-block;
    margin-top: 0.5rem;
    color: var(--accent-color);
    text-decoration: none;
  }

  .manage-link:hover {
    text-decoration: underline;
  }

  .flight-dashboard-link {
    background: var(--accent-color);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-weight: 500;
  }

  .flight-dashboard-link:hover {
    background: var(--accent-color-hover);
    text-decoration: none;
  }

  .service-mode-explanation {
    background: var(--main-color);
    padding: 0.75rem;
    border-radius: 4px;
    border-left: 3px solid var(--accent-color);
    line-height: 1.5;
  }

  .upcoming-flights {
    display: grid;
    gap: 0.75rem;
    margin-top: 0.75rem;
  }

  .flight-card {
    background: var(--main-color);
    padding: 1rem;
    border-radius: 4px;
    border: 1px solid var(--border-color);
  }

  .flight-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .flight-status {
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
  }

  .flight-status.scheduled {
    background: #2a5a3a;
    color: #6fdc8c;
  }

  .flight-status.boarding {
    background: #5a4a2a;
    color: #ffc107;
  }

  .flight-status.running {
    background: var(--accent-color-bg);
    color: var(--accent-color);
  }

  .flight-type {
    font-size: 0.75rem;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .flight-time {
    font-size: 1rem;
    margin-bottom: 0.5rem;
  }

  .flight-current-state {
    font-size: 0.95rem;
    color: var(--accent-color);
    font-weight: 600;
    padding: 0.5rem;
    background: var(--accent-color-bg);
    border-radius: 4px;
    margin-bottom: 0.5rem;
    border-left: 3px solid var(--accent-color);
  }

  .flight-route {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 0.75rem;
  }

  .route-label {
    color: var(--text-muted);
    margin-right: 0.5rem;
  }

  .route-planet {
    display: inline-block;
    opacity: 0.6;
    transition: opacity 0.3s;
  }

  .route-planet.visited {
    color: var(--success-color);
    opacity: 1;
    font-weight: 500;
  }

  .route-planet.current {
    color: var(--accent-color);
    opacity: 1;
    font-weight: 600;
    animation: pulse 2s infinite;
  }

  .route-planet.in-warp {
    color: var(--accent-color);
    opacity: 1;
    font-weight: 600;
    animation: warp-pulse 1.5s infinite;
  }

  .route-arrow {
    display: inline-block;
    margin: 0 0.4rem;
    color: var(--text-muted);
    opacity: 0.6;
  }

  .route-arrow.completed {
    color: var(--success-color);
    opacity: 1;
  }

  .route-arrow.in-warp {
    color: var(--accent-color);
    opacity: 1;
    animation: warp-pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }

  @keyframes warp-pulse {
    0%, 100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.7;
      transform: scale(1.05);
    }
  }

  .check-in-btn {
    display: inline-block;
    background: var(--success-color);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-weight: 500;
    font-size: 0.9rem;
    border: none;
    cursor: pointer;
  }

  .check-in-btn:hover {
    background: var(--success-color-hover);
    text-decoration: none;
  }

  .restore-btn {
    display: inline-block;
    background: var(--warning-color);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    border: none;
    font-weight: 500;
    font-size: 0.9rem;
    cursor: pointer;
  }

  .restore-btn:hover {
    background: var(--warning-color-hover);
  }

  .cancelled-flight {
    opacity: 0.7;
    border-color: var(--error-color);
  }

  .flight-status.cancelled {
    background: var(--error-bg);
    color: var(--error-color);
  }

  .highlighted-flight {
    border: 2px solid var(--accent-color);
    box-shadow: 0 0 8px rgba(74, 158, 255, 0.3);
  }

  .expand-flights-btn {
    background: none;
    border: none;
    color: var(--accent-color);
    cursor: pointer;
    font-size: 1rem;
    font-weight: 600;
    padding: 0.5rem 0;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .expand-flights-btn:hover {
    color: var(--accent-color-hover);
  }

  .route-display {
    background: var(--main-color);
    padding: 0.75rem;
    border-radius: 4px;
    margin: 0.5rem 0;
    font-size: 0.9rem;
  }
</style>
