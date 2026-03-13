<!--
  @component Missions Wiki Page
  Wiki layout with sidebar toggle between missions and mission chains.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onDestroy, untrack } from 'svelte';
  import { encodeURIComponentSafe, getLatestPendingUpdate, loadEditDeps } from '$lib/util';
  import { getPlanetNavFilter } from '$lib/mapUtil';
  import { sanitizeHtml } from '$lib/sanitize';

  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiNavigation from '$lib/components/wiki/WikiNavigation.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';
  import MissionStepsEditor from '$lib/components/wiki/missions/MissionStepsEditor.svelte';
  import MissionRewardsEditor from '$lib/components/wiki/missions/MissionRewardsEditor.svelte';
  import ChainEditorDialog from '$lib/components/wiki/missions/ChainEditorDialog.svelte';
  import MissionMapEmbed from '$lib/components/wiki/missions/MissionMapEmbed.svelte';
  import WaypointCopyButton from '$lib/components/wiki/WaypointCopyButton.svelte';

  import {
    editMode,
    initEditState,
    resetEditState,
    currentEntity,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField
  } from '$lib/stores/wikiEditState.js';

  let { data = $bindable() } = $props();

  // Lazy-load edit dependencies when edit mode activates
  let editDepsLoading = $state(false);



  const emptyMission = {
    Id: null,
    Name: '',
    MissionChain: { Name: null },
    Planet: { Name: 'Calypso' },
    Event: null,
    Properties: {
      Type: 'One-Time',
      Description: ''
    },
    Steps: [],
    Rewards: { Items: [], Skills: [], Unlocks: [] },
    Dependencies: { Prerequisites: [], Dependents: [] }
  };

  const emptyChain = {
    Id: null,
    Name: '',
    Planet: { Name: 'Calypso' },
    Properties: {
      Type: '',
      Description: ''
    },
    Missions: [],
    Graph: { nodes: [], edges: [] }
  };

  // Track initialization to prevent re-init during editing
  let lastInitKey = null;




  onDestroy(() => {
    resetEditState();
  });

  // Mission repeatability type options (matches MissionType enum in database)
  const missionTypeOptions = [
    { value: 'One-Time', label: 'One-Time' },
    { value: 'Repeatable', label: 'Repeatable' },
    { value: 'Recurring', label: 'Recurring' }
  ];

  // Cooldown duration state for Recurring missions
  let cooldownValue = $state(1);
  let cooldownUnit = $state('days');
  let lastParsedMissionId = null;


  // Parse PostgreSQL INTERVAL format (e.g., "1 day", "2 hours", "30 minutes", "00:30:00")
  function parseCooldownDuration(duration) {
    if (!duration) return { value: 1, unit: 'days' };
    if (typeof duration !== 'string') duration = String(duration);

    // Handle "X days" format
    const daysMatch = duration.match(/(\d+)\s*day/i);
    if (daysMatch) return { value: parseInt(daysMatch[1]), unit: 'days' };

    // Handle "X hours" or "HH:MM:SS" format
    const hoursMatch = duration.match(/(\d+)\s*hour/i);
    if (hoursMatch) return { value: parseInt(hoursMatch[1]), unit: 'hours' };

    // Handle time format "HH:MM:SS"
    const timeMatch = duration.match(/^(\d+):(\d+):(\d+)$/);
    if (timeMatch) {
      const hours = parseInt(timeMatch[1]);
      const minutes = parseInt(timeMatch[2]);
      if (hours > 0) return { value: hours, unit: 'hours' };
      if (minutes > 0) return { value: minutes, unit: 'minutes' };
    }

    // Handle "X minutes" or "X mins"
    const minsMatch = duration.match(/(\d+)\s*min/i);
    if (minsMatch) return { value: parseInt(minsMatch[1]), unit: 'minutes' };

    return { value: 1, unit: 'days' };
  }

  // Format cooldown for display
  function formatCooldownDisplay(duration) {
    if (!duration) return 'Not set';
    const parsed = parseCooldownDuration(duration);
    const unitLabel = parsed.unit === 'minutes' ? 'minute' : parsed.unit === 'hours' ? 'hour' : 'day';
    return `${parsed.value} ${unitLabel}${parsed.value !== 1 ? 's' : ''}`;
  }

  // Update cooldown duration in ISO 8601 format for PostgreSQL INTERVAL
  function updateCooldownDuration() {
    let isoValue;
    if (cooldownUnit === 'minutes') {
      // Clamp to max 30 days in minutes (43200)
      cooldownValue = Math.min(cooldownValue, 43200);
      isoValue = `${cooldownValue} minutes`;
    } else if (cooldownUnit === 'hours') {
      // Clamp to max 30 days in hours (720)
      cooldownValue = Math.min(cooldownValue, 720);
      isoValue = `${cooldownValue} hours`;
    } else {
      // Clamp to max 30 days
      cooldownValue = Math.min(cooldownValue, 30);
      isoValue = `${cooldownValue} days`;
    }
    updateField('Properties.CooldownDuration', isoValue);
  }


  // Main planets only (excludes asteroids, etc.)
  const MAIN_PLANET_NAMES = new Set([
    'Calypso', 'Arkadia', 'Cyrene', 'Monria', 'ROCKtropia', 'Toulan', 'Next Island', 'Space'
  ]);




  // Track chain names that are trusted (from entity, pending change, or created via dialog)
  // These bypass validation since they will be created when the change is saved
  let trustedChainNames = new Set();










  // Get event name by ID for display
  function getEventName(eventId) {
    if (!eventId) return 'None';
    const event = (data.events || []).find(e => e.Id === Number(eventId));
    return event?.Name || 'Unknown';
  }

  // Get label from options array by value (for SearchInput display)
  function getOptionLabel(options, value) {
    if (!value) return '';
    const opt = options.find(o => o.value === String(value));
    return opt?.label || '';
  }

  // Check if HTML content has actual text (not just empty tags like <p></p>)
  function hasActualText(html) {
    if (!html) return false;
    // Strip HTML tags and check if there's non-whitespace content
    const text = html.replace(/<[^>]*>/g, '').trim();
    return text.length > 0;
  }




  function getSpeciesNameFromId(speciesId) {
    return mobSpeciesIdToName[speciesId] || `Species #${speciesId}`;
  }

  // Get mob name from ID
  function getMobNameFromId(mobId) {
    return mobIdToName[mobId] || `Mob #${mobId}`;
  }

  // Reward rarity display
  const RARITY_ORDER = ['guaranteed', 'uncommon', 'rare', 'very-rare'];
  const RARITY_LABELS = {
    'guaranteed': 'Guaranteed',
    'uncommon': 'Uncommon',
    'rare': 'Rare',
    'very-rare': 'Very Rare'
  };

  function groupItemsByRarity(items) {
    if (!items?.length) return [];
    const groups = {};
    const ungrouped = [];
    for (const item of items) {
      const r = item.rarity;
      if (r && RARITY_LABELS[r]) {
        (groups[r] = groups[r] || []).push(item);
      } else {
        ungrouped.push(item);
      }
    }
    const result = [];
    for (const r of RARITY_ORDER) {
      if (groups[r]) result.push({ rarity: r, label: RARITY_LABELS[r], items: groups[r] });
    }
    if (ungrouped.length) result.push({ rarity: null, label: null, items: ungrouped });
    return result;
  }

  function formatRewardQuantity(item) {
    if (item.minQuantity != null || item.maxQuantity != null) {
      if (item.minQuantity != null && item.maxQuantity != null) {
        return `${item.minQuantity}–${item.maxQuantity}×`;
      } else if (item.minQuantity != null) {
        return `${item.minQuantity}+×`;
      } else {
        return `up to ${item.maxQuantity}×`;
      }
    }
    return `${item.quantity ?? 1}×`;
  }

  // Format objective summary for display
  function formatObjectiveSummary(objective) {
    const { Type, Payload } = objective;

    if (Type === 'KillCount') {
      const mobs = Payload?.mobs || [];
      const total = Payload?.totalCountRequired || 0;
      const usePoints = Payload?.useKillPoints;

      // Get unique mob names (mobId is now a numeric ID)
      const mobNames = [...new Set(mobs.map(m => getMobNameFromId(m.mobId)))];
      const mobList = mobNames.length > 1
        ? mobNames.slice(0, -1).join(', ') + ' or ' + mobNames[mobNames.length - 1]
        : mobNames[0] || 'creatures';

      if (usePoints) {
        return `Kill ${total} points worth of ${mobList}`;
      }
      return `Kill ${total} ${mobList}`;
    }

    if (Type === 'Dialog') {
      const npc = Payload?.npcName || 'an NPC';
      return `Talk to ${npc}`;
    }

    if (Type === 'Travel') {
      const location = Payload?.locationName || 'a location';
      return `Travel to ${location}`;
    }

    if (Type === 'Collect') {
      const itemName = (Payload?.itemId && itemsIndex[Payload.itemId]) || 'items';
      const amount = Payload?.quantity ?? 1;
      return `Collect ${amount}\u00d7 ${itemName}`;
    }

    if (Type === 'CollectValue') {
      const itemName = (Payload?.itemId && itemsIndex[Payload.itemId]) || 'items';
      const ped = Payload?.pedValue;
      return ped ? `Collect ${ped} PED worth of ${itemName}` : `Collect ${itemName} (by value)`;
    }

    if (Type === 'CraftSuccess') {
      const total = Payload?.totalCountRequired;
      return total ? `Craft ${total} successfully` : 'Craft successfully';
    }

    if (Type === 'CraftAttempt') {
      const total = Payload?.totalCountRequired;
      return total ? `Attempt ${total} crafts` : 'Attempt crafting';
    }

    if (Type === 'CraftCycle') {
      const ped = Payload?.pedToCycle;
      return ped ? `Cycle ${ped} PED in crafting` : 'Cycle PED in crafting';
    }

    if (Type === 'Craft') {
      const item = Payload?.itemName || 'an item';
      const amount = Payload?.amount || 1;
      return `Craft ${amount}× ${item}`;
    }

    if (Type === 'MiningCycle') {
      const total = Payload?.totalCountRequired;
      return total ? `Complete ${total} mining drops` : 'Complete mining drops';
    }

    if (Type === 'MiningClaim') {
      const total = Payload?.totalCountRequired;
      const minValue = Payload?.minClaimValue;
      if (total && minValue) return `Find ${total} claims worth ${minValue}+ PED`;
      if (total) return `Find ${total} mining claims`;
      return 'Find mining claims';
    }

    if (Type === 'MiningPoints') {
      const total = Payload?.totalCountRequired;
      return total ? `Accumulate ${total} mining points` : 'Accumulate mining points';
    }

    if (Type === 'KillCycle') {
      const mobs = Payload?.mobs || [];
      const ped = Payload?.pedToCycle;
      const mobNames = [...new Set(mobs.map(m => getMobNameFromId(m.mobId)))];
      const mobList = mobNames.length > 0
        ? mobNames.length > 1
          ? mobNames.slice(0, -1).join(', ') + ' or ' + mobNames[mobNames.length - 1]
          : mobNames[0]
        : 'creatures';
      return ped ? `Cycle ${ped} PED killing ${mobList}` : `Kill cycle: ${mobList}`;
    }

    if (Type === 'AIKillCycle') {
      const species = Payload?.mobSpecies || [];
      const ped = Payload?.pedToCycle;
      const speciesNames = species.filter(id => id != null).map(id => getSpeciesNameFromId(id));
      const speciesList = speciesNames.length > 0
        ? speciesNames.length > 1
          ? speciesNames.slice(0, -1).join(', ') + ' or ' + speciesNames[speciesNames.length - 1]
          : speciesNames[0]
        : 'creatures';
      return ped ? `AI Daily: Cycle ~${ped} PED hunting ${speciesList}` : `AI Daily: Hunt ${speciesList}`;
    }

    if (Type === 'AIHandIn') {
      const items = Payload?.items || [];
      const itemNames = items.filter(i => i.itemId).map(i => {
        const name = itemsIndex[i.itemId] || `Item #${i.itemId}`;
        const range = (i.minQuantity != null && i.maxQuantity != null) ? ` (${i.minQuantity}–${i.maxQuantity})` : '';
        return name + range;
      });
      return itemNames.length > 0 ? `AI Daily: Hand in ${itemNames.join(', ')}` : 'AI Daily: Hand in items';
    }

    if (Type === 'Use') {
      const item = Payload?.itemName || 'an item';
      return `Use ${item}`;
    }

    // Fallback for unknown types
    return Type || 'Unknown objective';
  }

  // Get objective details for expandable view
  function getObjectiveDetails(objective) {
    const { Type, Payload } = objective;
    const details = [];

    if (Type === 'KillCount') {
      const mobs = Payload?.mobs || [];
      for (const mob of mobs) {
        const targets = mob.targets || [];
        const counts = mob.countsPerTarget || {};

        // Group maturities by points (0 or missing = unknown)
        const byPoints = {};
        for (const targetId of targets) {
          const maturity = mobMaturityMap[targetId];
          const maturityName = maturity?.Name || `#${targetId}`;
          const rawPoints = counts[targetId];
          // 0 or missing means unknown, use '?' as key
          const pointsKey = (rawPoints == null || rawPoints === 0) ? '?' : String(rawPoints);

          if (!byPoints[pointsKey]) byPoints[pointsKey] = [];
          byPoints[pointsKey].push(maturityName);
        }

        // Format as "X pts: Maturity1, Maturity2" (sort numerics first, '?' last)
        const pointGroups = Object.entries(byPoints)
          .sort((a, b) => {
            if (a[0] === '?') return 1;
            if (b[0] === '?') return -1;
            return Number(a[0]) - Number(b[0]);
          })
          .map(([pts, names]) => `${pts} pts: ${names.join(', ')}`);

        if (pointGroups.length > 0) {
          details.push({
            label: getMobNameFromId(mob.mobId),
            value: pointGroups.join(' | ')
          });
        }
      }
    }

    if (Type === 'AIKillCycle') {
      const species = Payload?.mobSpecies || [];
      for (const speciesId of species) {
        if (speciesId != null) {
          const speciesName = getSpeciesNameFromId(speciesId);
          details.push({ label: 'Species', value: speciesName, href: `/information/mobs?search=${encodeURIComponent(speciesName)}` });
        }
      }
      if (Payload?.pedToCycle) {
        details.push({ label: 'Est. PED to Cycle', value: `~${Payload.pedToCycle}` });
      }
    }

    if (Type === 'AIHandIn') {
      const items = Payload?.items || [];
      for (const item of items) {
        if (item.itemId) {
          const name = itemsIndex[item.itemId] || `Item #${item.itemId}`;
          const range = (item.minQuantity != null && item.maxQuantity != null)
            ? `${item.minQuantity}–${item.maxQuantity}`
            : item.minQuantity ?? item.maxQuantity ?? '?';
          details.push({ label: name, value: `Qty: ${range}` });
        }
      }
    }

    if (Type === 'Collect') {
      if (Payload?.itemId) {
        const name = itemsIndex[Payload.itemId] || `Item #${Payload.itemId}`;
        details.push({ label: 'Item', value: name });
      }
      if (Payload?.quantity != null) {
        details.push({ label: 'Quantity', value: String(Payload.quantity) });
      }
    }

    if (Type === 'CollectValue') {
      if (Payload?.itemId) {
        const name = itemsIndex[Payload.itemId] || `Item #${Payload.itemId}`;
        details.push({ label: 'Item', value: name });
      }
      if (Payload?.pedValue != null) {
        details.push({ label: 'Value', value: `${Payload.pedValue} PED` });
      }
    }

    return details;
  }

  // Format PED value with proper decimals (2 decimal places, or more to show first 2 non-zero digits)
  function formatPedValue(value) {
    if (value == null || value === 0) return '0.00';
    const absVal = Math.abs(value);
    if (absVal >= 0.01) {
      return value.toFixed(2);
    }
    // For very small values, find first 2 significant digits
    const str = absVal.toString();
    const match = str.match(/^0\.0*(\d{2})/);
    if (match) {
      const zerosAfterDecimal = str.indexOf(match[1]) - 2;
      return value.toFixed(zerosAfterDecimal + 2);
    }
    return value.toFixed(4);
  }


  // Build waypoint string for start location
  function getStartLocationWaypoint(startLocation) {
    if (!startLocation) return null;
    const { Planet, Coordinates, Name } = startLocation;
    if (!Coordinates?.Longitude && !Coordinates?.Latitude && !Coordinates?.Altitude) return null;
    const parts = [
      Planet?.Name || '?',
      Coordinates?.Longitude ?? '?',
      Coordinates?.Latitude ?? '?',
      Coordinates?.Altitude ?? '?',
      Name || 'Start Location'
    ];
    return `[${parts.join(', ')}]`;
  }



  const navFilters = [getPlanetNavFilter('Planet.Name')];

  function switchSidebar(mode) {
    if (mode === view) return;
    const next = mode === 'chains'
      ? '/information/missions?view=chains'
      : '/information/missions';
    goto(next);
  }

  function getSidebarHref(item, basePath) {
    const slug = encodeURIComponentSafe(item.Name);
    return view === 'chains'
      ? `${basePath}/${slug}?view=chains`
      : `${basePath}/${slug}`;
  }




  const seoColumns = [
    {
      key: 'Planet.Name',
      header: 'Planet'
    },
    {
      key: 'Properties.Type',
      header: 'Type'
    }
  ];

  // Table columns for mission sidebar (expanded/full-width views)
  const missionColumnDefs = {
    type: {
      key: 'type',
      header: 'Type',
      width: '80px',
      filterPlaceholder: 'Repeatable',
      getValue: (item) => item.Properties?.Type,
      format: (v) => v || '-'
    },
    planet: {
      key: 'planet',
      header: 'Planet',
      width: '75px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => item.Planet?.Name,
      format: (v) => v || '-'
    },
    chain: {
      key: 'chain',
      header: 'Chain',
      width: '100px',
      getValue: (item) => item.MissionChain?.Name,
      format: (v) => v || '-'
    },
    cooldown: {
      key: 'cooldown',
      header: 'Cooldown',
      width: '75px',
      getValue: (item) => item.Properties?.CooldownDuration,
      format: (v) => v ? formatCooldownDisplay(v) : '-'
    },
    steps: {
      key: 'steps',
      header: 'Steps',
      width: '50px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Steps?.length ?? null,
      format: (v) => v != null ? v : '-'
    },
    event: {
      key: 'event',
      header: 'Event',
      width: '80px',
      getValue: (item) => item.Event?.Name || (item.EventId ? getEventName(item.EventId) : null),
      format: (v) => v || '-'
    }
  };

  // Chain-specific columns
  const chainColumnDefs = {
    type: {
      key: 'type',
      header: 'Type',
      width: '80px',
      getValue: (item) => item.Properties?.Type,
      format: (v) => v || '-'
    },
    planet: {
      key: 'planet',
      header: 'Planet',
      width: '75px',
      filterPlaceholder: 'Calypso',
      getValue: (item) => item.Planet?.Name,
      format: (v) => v || '-'
    },
    missionCount: {
      key: 'missionCount',
      header: 'Missions',
      width: '65px',
      filterPlaceholder: '>1',
      getValue: (item) => item.Missions?.length ?? null,
      format: (v) => v != null ? v : '-'
    }
  };








  let showGraphDialog = $state(false);
  let showChainDialog = $state(false);
  let chainDialogMode = $state('edit'); // 'create' or 'edit'

  function openChainDialog(mode) {
    chainDialogMode = mode;
    showChainDialog = true;
  }

  function closeChainDialog() {
    showChainDialog = false;
  }

  function handleChainCreate(data) {
    const { name, planet } = data;
    // Add to trusted chain names so it doesn't show validation error
    trustedChainNames = new Set([...trustedChainNames, name]);
    // Set the chain name on the mission and close the dialog
    updateField('MissionChain.Name', name);
    // Note: The chain will be created when the mission is saved
    // The bot will handle creating the chain if it doesn't exist
    showChainDialog = false;
  }

  function handleChainSelect(data) {
    const { name } = data;
    updateField('MissionChain.Name', name);
    showChainDialog = false;
  }

  function handleChainUpdate(data) {
    const { field, value } = data;
    // Update the chain field on the mission's MissionChain object
    updateField(`MissionChain.${field}`, value);
  }

  function getGraphNodeMap(graph) {
    const map = new Map();
    if (!graph?.nodes) return map;
    for (const node of graph.nodes) {
      map.set(String(node.Id), node);
    }
    return map;
  }

  function getNeighborNodes(graph, startId, direction, maxDepth = 2) {
    if (!graph || !startId) return [];
    const nodeMap = getGraphNodeMap(graph);
    const edges = graph.edges || [];
    const adjacency = new Map();
    for (const edge of edges) {
      const from = String(edge.FromId);
      const to = String(edge.ToId);
      const key = direction === 'prev' ? to : from;
      const value = direction === 'prev' ? from : to;
      if (!adjacency.has(key)) adjacency.set(key, []);
      adjacency.get(key).push(value);
    }

    let results = [];
    let frontier = [String(startId)];
    let seen = new Set(frontier);

    for (let depth = 1; depth <= maxDepth; depth++) {
      const next = [];
      for (const id of frontier) {
        const neighbors = adjacency.get(id) || [];
        for (const neighbor of neighbors) {
          if (seen.has(neighbor)) continue;
          seen.add(neighbor);
          next.push(neighbor);
        }
      }
      if (!next.length) break;
      for (const id of next) {
        const node = nodeMap.get(id);
        if (node) results.push({ ...node, depth });
      }
      frontier = next;
    }
    return results.slice(0, 2);
  }


  function getNodeName(id) {
    if (!graphData?.nodes) return `#${id}`;
    const found = graphData.nodes.find(n => String(n.Id) === String(id));
    return found?.Name || `#${id}`;
  }

  function computeGraphLayers(graph) {
    if (!graph?.nodes?.length) return { layers: [], disconnected: [] };
    const nodes = graph.nodes;
    const edges = graph.edges || [];
    const nodeMap = new Map(nodes.map(n => [String(n.Id), n]));
    const nodeIds = new Set(nodes.map(n => String(n.Id)));

    // Build adjacency
    const next = new Map();
    const prev = new Map();
    for (const edge of edges) {
      const from = String(edge.FromId);
      const to = String(edge.ToId);
      if (!next.has(from)) next.set(from, []);
      next.get(from).push(to);
      if (!prev.has(to)) prev.set(to, []);
      prev.get(to).push(from);
    }

    // Topological sort by layers
    const inDegree = new Map();
    for (const n of nodes) {
      const id = String(n.Id);
      const prereqs = (prev.get(id) || []).filter(p => nodeIds.has(p));
      inDegree.set(id, prereqs.length);
    }

    const layers = [];
    const processed = new Set();

    while (processed.size < nodes.length) {
      const layer = [];
      for (const n of nodes) {
        const id = String(n.Id);
        if (!processed.has(id) && inDegree.get(id) === 0) {
          layer.push(n);
          processed.add(id);
        }
      }
      if (layer.length === 0) break;
      layers.push(layer);
      for (const n of layer) {
        const id = String(n.Id);
        for (const unlockId of (next.get(id) || []).filter(u => nodeIds.has(u))) {
          inDegree.set(unlockId, (inDegree.get(unlockId) || 1) - 1);
        }
      }
    }

    const disconnected = nodes.filter(n => !processed.has(String(n.Id)));
    return { layers, disconnected };
  }


  function addPrerequisite() {
    const current = activeMission?.Dependencies?.Prerequisites || [];
    updateField('Dependencies.Prerequisites', [...current, { Id: null, Name: null }]);
  }

  function updatePrerequisite(index, missionId) {
    const current = activeMission?.Dependencies?.Prerequisites || [];
    const selected = missionsList.find(m => String(m.Id) === String(missionId));
    const next = current.map((item, i) => {
      if (i !== index) return item;
      return selected ? { Id: selected.Id, Name: selected.Name } : { Id: null, Name: null };
    });
    updateField('Dependencies.Prerequisites', next);
  }

  function removePrerequisite(index) {
    const current = activeMission?.Dependencies?.Prerequisites || [];
    updateField('Dependencies.Prerequisites', current.filter((_, i) => i !== index));
  }

  // Dependent (unlock) handlers
  function addDependent() {
    const current = activeMission?.Dependencies?.Dependents || [];
    updateField('Dependencies.Dependents', [...current, { Id: null, Name: null }]);
  }

  function updateDependent(index, mission) {
    const current = activeMission?.Dependencies?.Dependents || [];
    const next = current.map((item, i) => {
      if (i !== index) return item;
      return mission ? { Id: mission.Id, Name: mission.Name } : { Id: null, Name: null };
    });
    updateField('Dependencies.Dependents', next);
  }

  function removeDependent(index) {
    const current = activeMission?.Dependencies?.Dependents || [];
    updateField('Dependencies.Dependents', current.filter((_, i) => i !== index));
  }

  // Dialog event handlers
  function handleDialogAddPrerequisite() {
    addPrerequisite();
  }

  function handleDialogUpdatePrerequisite(data) {
    const { index, mission } = data;
    if (mission) {
      updatePrerequisite(index, mission.Id);
    }
  }

  function handleDialogRemovePrerequisite(data) {
    removePrerequisite(data.index);
  }

  function handleDialogAddDependent() {
    addDependent();
  }

  function handleDialogUpdateDependent(data) {
    const { index, mission } = data;
    updateDependent(index, mission);
  }

  function handleDialogRemoveDependent(data) {
    removeDependent(data.index);
  }
  $effect(() => {
    if ($editMode && data.mobMaturities === null && !untrack(() => editDepsLoading)) {
      editDepsLoading = true;
      loadEditDeps([
        { key: 'mobMaturities', url: '/api/mobmaturities' },
        { key: 'locations', url: '/api/locations' },
        { key: 'events', url: '/api/events' }
      ]).then(deps => {
        data = { ...data, ...deps };
        editDepsLoading = false;
      });
    }
  });
  let view = $derived(data.view || 'missions');
  let isChainView = $derived(view === 'chains');
  let user = $derived(data.session?.user);
  let missionsList = $derived(data.missions || []);
  let missionChainsList = $derived(data.missionChains || []);
  let pendingChange = $derived(data.pendingChange);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let isCreateMode = $derived(data.isCreateMode || false);
  let graphData = $derived(isChainView ? data.object?.Graph : data.graph);
  let currentChangeId = $derived($page.url.searchParams.get('changeId'));
  let entityType = $derived(isChainView ? 'MissionChain' : 'Mission');
  let entity = $derived(data.object);
  let entityId = $derived(entity?.Id ?? null);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, entityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));
  $effect(() => {
    // Create a stable key for the current entity context
    const initKey = `${entityType}-${entity?.Id ?? 'new'}-${isCreateMode}-${data.existingChange?.id ?? 'none'}`;
    if (user && initKey !== untrack(() => lastInitKey)) {
      lastInitKey = initKey;
      const existingChange = data.existingChange || null;
      const initialEntity = isCreateMode
        ? (existingChange?.data || (isChainView ? emptyChain : emptyMission))
        : entity;
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(initialEntity, entityType, isCreateMode, editChange);
    }
  });
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });
  let activeEntity = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : entity);
  let activeMission = $derived(isChainView ? null : activeEntity);
  let activeChain = $derived(isChainView ? activeEntity : null);
  // Parse existing cooldown duration only when switching to a different mission
  // In create mode, use 'create' sentinel so the guard fires once (not on every activeMission change)
  $effect(() => {
    const missionIdentity = activeMission?.Id ?? (isCreateMode ? 'create' : null);
    if (missionIdentity !== untrack(() => lastParsedMissionId)) {
      lastParsedMissionId = missionIdentity;
      if (activeMission?.Properties?.CooldownDuration) {
        const parsed = parseCooldownDuration(activeMission.Properties.CooldownDuration);
        cooldownValue = parsed.value;
        cooldownUnit = parsed.unit;
      } else {
        // Default for new missions
        cooldownValue = 1;
        cooldownUnit = 'days';
      }
    }
  });
  // When type changes to Recurring and no cooldown is set yet, persist the default value
  $effect(() => {
    if ($editMode && activeMission?.Properties?.Type === 'Recurring' && !activeMission?.Properties?.CooldownDuration) {
      updateCooldownDuration();
    }
  });
  let planetOptions = $derived((data.planetsList || [])
    .filter(p => p.Id > 0 && MAIN_PLANET_NAMES.has(p.Name))
    .map(p => ({ value: p.Name, label: p.Name })));
  let planetIdOptions = $derived((data.planetsList || [])
    .filter(p => p.Id > 0 && MAIN_PLANET_NAMES.has(p.Name))
    .map(p => ({ value: String(p.Id), label: p.Name })));
  let chainOptions = $derived(missionChainsList.map(chain => ({
    value: chain.Name,
    label: chain.Name
  })));
  // Initialize trusted chain names when edit state changes
  $effect(() => {
    const newTrusted = new Set();
    // Trust the original entity's chain
    if (entity?.MissionChain?.Name) {
      newTrusted.add(entity.MissionChain.Name);
    }
    // Trust chain from existing pending change
    if (data.existingChange?.data?.MissionChain?.Name) {
      newTrusted.add(data.existingChange.data.MissionChain.Name);
    }
    // Keep any chains added via the dialog during this session
    for (const name of untrack(() => trustedChainNames)) {
      if (!chainOptions.some(opt => opt.value === name)) {
        // Only keep if it's not already in chainOptions (meaning it was created this session)
        newTrusted.add(name);
      }
    }
    trustedChainNames = newTrusted;
  });
  // Check if the current chain name is valid (exists in the list of chains OR is trusted)
  let currentChainName = $derived(activeMission?.MissionChain?.Name || '');
  let isValidChain = $derived(!currentChainName || chainOptions.some(opt => opt.value === currentChainName) || trustedChainNames.has(currentChainName));
  let hasValidChainSelected = $derived(currentChainName && isValidChain);
  let missionOptions = $derived(missionsList
    .filter(mission => mission?.Id && mission?.Name && mission?.Id !== activeMission?.Id)
    .map(mission => ({
      value: String(mission.Id),
      label: mission.Name
    })));
  let npcOptions = $derived((data.locations || [])
    .filter(location => location?.Properties?.Type === 'Npc')
    .map(location => {
      const planetName = location?.Planet?.Name;
      const suffix = planetName ? ` (${planetName})` : '';
      return {
        value: String(location.Id),
        label: `${location.Name}${suffix}`
      };
    }));
  let locationOptions = $derived((data.locations || []).map(location => {
    const type = location?.Properties?.Type;
    const planetName = location?.Planet?.Name;
    const suffixParts = [type, planetName].filter(Boolean);
    const suffix = suffixParts.length ? ` (${suffixParts.join(' · ')})` : '';
    return {
      value: String(location.Id),
      label: `${location?.Name || 'Unknown'}${suffix}`
    };
  }));
  let itemsIndex = $derived(Object.fromEntries(
    (data.itemsList || []).map(item => [item.Id, item.Name])
  ));
  // Full item info map for type checking (damageable vs stackable)
  let itemsMap = $derived(Object.fromEntries(
    (data.itemsList || []).map(item => [item.Id, { Name: item.Name, Type: item.Properties?.Type || '' }])
  ));
  // Resolve full planet object with Id for Explore objectives
  let missionPlanetResolved = $derived((() => {
    const planetName = activeMission?.Planet?.Name;
    if (!planetName) return null;
    const planet = (data.planetsList || []).find(p => p.Name === planetName);
    return planet ? { Id: planet.Id, Name: planet.Name } : { Id: null, Name: planetName };
  })());
  // Events for event-type missions
  let eventOptions = $derived([
    { value: '', label: 'None' },
    ...(data.events || []).map(event => ({
      value: String(event.Id),
      label: event.Name + (event.Properties?.IsActive ? ' (Active)' : '')
    }))
  ]);
  // Build mob maturity lookup map
  let mobMaturityMap = $derived((data.mobMaturities || []).reduce((acc, m) => {
    acc[m.Id] = m;
    return acc;
  }, {}));
  // Build mob ID to name lookup from maturities
  // API returns Mob: { Name, Links: { $Url: "/mobs/<id>" } } — extract MobId from URL
  let mobIdToName = $derived((data.mobMaturities || []).reduce((acc, m) => {
    const mobName = m.Mob?.Name;
    const mobUrl = m.Mob?.Links?.$Url;
    const mobId = mobUrl ? parseInt(mobUrl.split('/').pop(), 10) : null;
    if (mobId && mobName) {
      acc[mobId] = mobName;
    }
    return acc;
  }, {}));
  // Build mob species ID to name lookup
  let mobSpeciesIdToName = $derived((data.mobSpeciesList || []).reduce((acc, s) => {
    acc[s.Id] = s.Name;
    return acc;
  }, {}));
  // Start location options (reuses locationOptions with None option)
  let startLocationOptions = $derived([
    { value: '', label: 'None' },
    ...locationOptions
  ]);
  // Extract map-displayable objectives from mission steps
  let mapObjectives = $derived((() => {
    if (!activeMission?.Steps?.length) return [];
    const objectives = [];

    for (const step of activeMission.Steps) {
      const stepIndex = step.Index ?? 0;
      for (const obj of (step.Objectives || [])) {
        if (!obj?.Type || !obj?.Payload) continue;

        // Extract coordinates based on objective type
        if (obj.Type === 'Explore' && obj.Payload.longitude != null) {
          objectives.push({
            stepIndex,
            title: step.Title,
            type: obj.Type,
            coordinates: {
              Longitude: obj.Payload.longitude,
              Latitude: obj.Payload.latitude,
              Altitude: obj.Payload.altitude
            },
            planetId: obj.Payload.planetId
          });
        } else if ((obj.Type === 'Dialog' || obj.Type === 'Interact' || obj.Type === 'HandIn') && obj.Payload.targetLocationId) {
          // Look up location coordinates
          const locationId = Number(obj.Payload.targetLocationId) || Number(obj.Payload.npcLocationId);
          const location = (data.locations || []).find(l => l.Id === locationId);
          if (location?.Properties?.Coordinates) {
            objectives.push({
              stepIndex,
              title: step.Title,
              type: obj.Type,
              coordinates: location.Properties.Coordinates,
              planetId: location.Planet?.Id
            });
          }
        }
      }
    }

    return objectives;
  })());
  // Resolve mission planet with full data for map embed
  let mapPlanet = $derived((() => {
    const planetName = activeMission?.Planet?.Name;
    if (!planetName) return null;
    const planet = (data.planetsList || []).find(p => p.Name === planetName);
    if (!planet) return { Name: planetName };
    return {
      Id: planet.Id,
      Name: planet.Name,
      TechnicalName: planet.Properties?.TechnicalName,
      X: planet.Properties?.Map?.X,
      Y: planet.Properties?.Map?.Y,
      Width: planet.Properties?.Map?.Width,
      Height: planet.Properties?.Map?.Height
    };
  })());
  let breadcrumbs = $derived([
    { label: 'Information', href: '/information' },
    { label: 'Missions', href: '/information/missions' },
    ...(activeEntity?.Name
      ? [{ label: activeEntity.Name }]
      : isCreateMode
        ? [{ label: isChainView ? 'New Mission Chain' : 'New Mission' }]
        : [])
  ]);
  let seoDescription = $derived(activeMission?.Properties?.Description
    || activeChain?.Properties?.Description
    || `${activeEntity?.Name || 'Mission'} reference data for Entropia Universe.`);
  let canonicalUrl = $derived(activeEntity?.Name
    ? `https://entropianexus.com/information/missions/${encodeURIComponentSafe(activeEntity.Name)}${isChainView ? '?view=chains' : ''}`
    : 'https://entropianexus.com/information/missions');
  let missionNavTableColumns = $derived([
    missionColumnDefs.type,
    missionColumnDefs.planet,
    missionColumnDefs.chain
  ]);
  let missionNavFullWidthColumns = $derived([
    missionColumnDefs.type,
    missionColumnDefs.planet,
    missionColumnDefs.chain,
    missionColumnDefs.cooldown,
    missionColumnDefs.steps
  ]);
  let missionAllAvailableColumns = $derived(Object.values(missionColumnDefs));
  let chainNavTableColumns = $derived([
    chainColumnDefs.type,
    chainColumnDefs.planet,
    chainColumnDefs.missionCount
  ]);
  let chainNavFullWidthColumns = $derived([
    chainColumnDefs.type,
    chainColumnDefs.planet,
    chainColumnDefs.missionCount
  ]);
  let chainAllAvailableColumns = $derived(Object.values(chainColumnDefs));
  let activeNavTableColumns = $derived(isChainView ? chainNavTableColumns : missionNavTableColumns);
  let activeNavFullWidthColumns = $derived(isChainView ? chainNavFullWidthColumns : missionNavFullWidthColumns);
  let activeAllAvailableColumns = $derived(isChainView ? chainAllAvailableColumns : missionAllAvailableColumns);
  let activePageTypeId = $derived(isChainView ? 'missions-chains' : 'missions');
  let previewPrev = $derived((!isChainView && activeMission?.Id)
    ? getNeighborNodes(graphData, activeMission.Id, 'prev', 2)
    : []);
  let previewNext = $derived((!isChainView && activeMission?.Id)
    ? getNeighborNodes(graphData, activeMission.Id, 'next', 2)
    : []);
  let graphLayers = $derived(computeGraphLayers(graphData));
</script>

<WikiSEO
  title={activeEntity?.Name || (isChainView ? 'Mission Chains' : 'Missions')}
  description={seoDescription}
  entityType={isChainView ? 'mission-chain' : 'mission'}
  entity={activeEntity}
  imageUrl={null}
  sidebarColumns={seoColumns}
  sidebarEntity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Missions"
  {breadcrumbs}
  entity={activeEntity}
  basePath="/information/missions"
  {user}
  editable={true}
  canEdit={user?.verified || user?.grants?.includes('wiki.edit')}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
  {editDepsLoading}
>
  {#snippet sidebar()}
    <div  class="missions-sidebar">
      <WikiNavigation
        items={isChainView ? missionChainsList : missionsList}
        filters={navFilters}
        basePath="/information/missions"
        title="Missions"
        currentSlug={activeEntity?.Name}
        {currentChangeId}
        customGetItemHref={getSidebarHref}
        {userPendingCreates}
        {userPendingUpdates}
        tableColumns={activeNavTableColumns}
        fullWidthColumns={activeNavFullWidthColumns}
        allAvailableColumns={activeAllAvailableColumns}
        pageTypeId={activePageTypeId}
      >
        {#snippet afterHeader()}
          <div class="sidebar-toggle">
            <button class:active={!isChainView} onclick={() => switchSidebar('missions')}>Missions</button>
            <button class:active={isChainView} onclick={() => switchSidebar('chains')}>Mission Chains</button>
          </div>
        {/snippet}
      </WikiNavigation>
    </div>
  {/snippet}

  {#if activeEntity || isCreateMode}
    {#if $existingPendingChange && !$editMode && !isCreateMode}
      <div class="pending-change-banner">
        <div class="banner-content">
          <span class="banner-text">
            This {isChainView ? 'mission chain' : 'mission'} has a pending change by <strong>{$existingPendingChange.author_name || 'Unknown'}</strong>
            ({$existingPendingChange.state})
          </span>
        </div>
        <div class="banner-actions">
          {#if $viewingPendingChange}
            <button class="banner-btn" onclick={() => setViewingPendingChange(false)}>View Current</button>
          {:else}
            <button class="banner-btn primary" onclick={() => setViewingPendingChange(true)}>View Pending</button>
          {/if}
        </div>
      </div>
    {/if}

    <div class="layout-a">
      <aside class="wiki-infobox-float">
        <div class="infobox-header">
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name || ''}
              path="Name"
              type="text"
              placeholder={isChainView ? 'Mission chain name' : 'Mission name'}
            />
          </div>
          <div class="infobox-subtitle">
            <span>{isChainView ? 'Mission Chain' : activeMission?.Properties?.Type || 'Mission'}</span>
            <span>{activeEntity?.Planet?.Name || 'Calypso'}</span>
          </div>
        </div>

        <div class="stats-section details-grid">
          <h4 class="section-title">Details</h4>
          <div class="stat-row">
            <span class="stat-label">Planet</span>
            <span class="stat-value">
              <InlineEdit
                value={activeEntity?.Planet?.Name || 'Calypso'}
                path="Planet.Name"
                type="select"
                options={planetOptions}
              />
            </span>
          </div>
          {#if !isChainView}
            <div class="stat-row">
              <span class="stat-label">Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeMission?.Properties?.Type || 'One-Time'}
                  path="Properties.Type"
                  type="select"
                  options={missionTypeOptions}
                />
              </span>
            </div>
            {#if activeMission?.Properties?.Type === 'Recurring'}
              <div class="stat-row cooldown-row">
                <span class="stat-label">Cooldown</span>
                <span class="stat-value">
                  {#if $editMode}
                    <div class="cooldown-duration-row">
                      <input
                        type="number"
                        class="cooldown-value-input"
                        min="1"
                        max={cooldownUnit === 'minutes' ? 43200 : cooldownUnit === 'hours' ? 720 : 30}
                        value={cooldownValue}
                        oninput={(e) => {
                          cooldownValue = Math.max(1, parseInt(e.target.value) || 1);
                          updateCooldownDuration();
                        }}
                      />
                      <select
                        class="cooldown-unit-select"
                        bind:value={cooldownUnit}
                        onchange={updateCooldownDuration}
                      >
                        <option value="minutes">Minutes</option>
                        <option value="hours">Hours</option>
                        <option value="days">Days</option>
                      </select>
                    </div>
                  {:else}
                    {formatCooldownDisplay(activeMission?.Properties?.CooldownDuration)}
                  {/if}
                </span>
              </div>
              <div class="stat-row cooldown-row">
                <span class="stat-label">Starts on</span>
                <span class="stat-value">
                  {#if $editMode}
                    <select
                      class="cooldown-starts-select"
                      value={activeMission?.Properties?.CooldownStartsOn || 'Completion'}
                      onchange={(e) => updateField('Properties.CooldownStartsOn', e.target.value)}
                    >
                      <option value="Accept">Accept</option>
                      <option value="Completion">Completion</option>
                    </select>
                  {:else}
                    {activeMission?.Properties?.CooldownStartsOn || 'Completion'}
                  {/if}
                </span>
              </div>
            {/if}
            <div class="stat-row">
              <span class="stat-label">Chain</span>
              <span class="stat-value chain-value">
                {#if $editMode}
                  <div class="chain-input-row" class:has-error={!isValidChain}>
                    <SearchInput
                      value={activeMission?.MissionChain?.Name || ''}
                      placeholder="Chain..."
                      options={chainOptions}
                      onchange={(e) => updateField('MissionChain.Name', e.value || null)}
                      onselect={(e) => updateField('MissionChain.Name', e.value || null)}
                    />
                    <button
                      type="button"
                      class="chain-btn"
                      title="Create new chain"
                      onclick={() => openChainDialog('create')}
                    >+</button>
                    {#if hasValidChainSelected}
                      <button
                        type="button"
                        class="chain-btn"
                        title="Edit chain"
                        onclick={() => openChainDialog('edit')}
                      >&#9998;</button>
                    {/if}
                  </div>
                  {#if !isValidChain}
                    <div class="chain-error">Chain "{currentChainName}" does not exist. Select an existing chain or create a new one.</div>
                  {/if}
                {:else if activeMission?.MissionChain?.Name}
                  <a href="/information/missions?view=chains&chain={encodeURIComponentSafe(activeMission.MissionChain.Name)}" class="stat-link">{activeMission.MissionChain.Name}</a>
                {:else}
                  <span class="stat-none">None</span>
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Event</span>
              <span class="stat-value">
                {#if $editMode}
                  <SearchInput
                    value={getOptionLabel(eventOptions, activeMission?.Event?.Id)}
                    options={eventOptions}
                    placeholder="Select event (optional)"
                    onselect={(e) => {
                      const eventId = e.value ? Number(e.value) : null;
                      if (eventId) {
                        const event = (data.events || []).find(ev => ev.Id === eventId);
                        updateField('Event', event ? { Id: event.Id, Name: event.Name } : null);
                      } else {
                        updateField('Event', null);
                      }
                    }}
                  />
                {:else if activeMission?.Event?.Name}
                  {activeMission.Event.Name}
                {:else}
                  <span class="stat-none">None</span>
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Start Location</span>
              <span class="stat-value start-location-value">
                {#if $editMode}
                  <SearchInput
                    value={getOptionLabel(startLocationOptions, activeMission?.StartLocationId)}
                    options={startLocationOptions}
                    placeholder="Select location (optional)"
                    onselect={(e) => {
                      const locationId = e.value ? Number(e.value) : null;
                      updateField('StartLocationId', locationId);
                    }}
                  />
                {:else if activeMission?.StartLocation}
                  {@const waypoint = getStartLocationWaypoint(activeMission.StartLocation)}
                  <div class="start-location-display">
                    {#if waypoint}
                      <span class="waypoint-desktop"><WaypointCopyButton {waypoint} compact={true} /></span>
                    {/if}
                    <a href="/information/locations/{activeMission.StartLocationId}" class="stat-link">{activeMission.StartLocation.Name || 'Unknown'}</a>
                  </div>
                {:else}
                  <span class="stat-none">None</span>
                {/if}
              </span>
            </div>
          {:else}
            <div class="stat-row">
              <span class="stat-label">Type</span>
              <span class="stat-value">
                <InlineEdit
                  value={activeChain?.Properties?.Type || ''}
                  path="Properties.Type"
                  type="text"
                  placeholder="Chain type"
                />
              </span>
            </div>
          {/if}
        </div>

        {#if isChainView}
          <div class="stats-section">
            <h4 class="section-title">Missions</h4>
            <div class="stat-row">
              <span class="stat-label">Count</span>
              <span class="stat-value">{activeChain?.Missions?.length || 0}</span>
            </div>
          </div>
        {:else}
          <!-- Rewards Section - styled like set effects -->
          {@const rewards = activeMission?.Rewards || { Items: [], Skills: [], Unlocks: [] }}
          {@const hasRewardChoices = rewards.Items?.length > 0 && rewards.Items[0]?.Items !== undefined}
          {@const rewardPackages = hasRewardChoices ? rewards.Items : [rewards]}
          {@const hasAnyRewards = rewardPackages.some(pkg => (pkg?.Items?.length || 0) + (pkg?.Skills?.length || 0) + (pkg?.Unlocks?.length || 0) > 0)}
          {#if hasAnyRewards && !$editMode}
            <div class="stats-section rewards-section">
              <h4 class="section-title">Rewards</h4>
              <div class="rewards-display">
                {#each rewardPackages as pkg, choiceIdx (choiceIdx)}
                  {@const itemCount = pkg?.Items?.length || 0}
                  {@const skillCount = pkg?.Skills?.length || 0}
                  {@const unlockCount = pkg?.Unlocks?.length || 0}
                  {@const totalRewards = itemCount + skillCount + unlockCount}
                  {#if totalRewards > 0}
                    <div class="reward-group">
                      {#if hasRewardChoices && rewardPackages.length > 1}
                        <div class="reward-choice-label">Choice {choiceIdx + 1}</div>
                      {/if}
                      {#if itemCount > 0}
                        {@const rarityGroups = groupItemsByRarity(pkg.Items)}
                        {#each rarityGroups as group}
                          {#if group.label}
                            <div class="reward-rarity-header rarity-{group.rarity}">{group.label}</div>
                          {/if}
                          {#each group.items as item}
                            {@const itemDisplayName = item.itemName || itemsIndex[item.itemId] || `Item #${item.itemId}`}
                            <div class="reward-row">
                              <span class="reward-value">{formatRewardQuantity(item)}</span>
                              <span class="reward-name">
                                {#if item.itemId}
                                  <a href="/items/{item.itemId}" class="reward-link">{itemDisplayName}</a>
                                {:else}
                                  {itemDisplayName}
                                {/if}
                                {#if item.pedValue > 0}<span class="reward-ped">({formatPedValue(item.pedValue)} PED)</span>{/if}
                              </span>
                            </div>
                          {/each}
                        {/each}
                      {/if}
                      {#if skillCount > 0}
                        {#each pkg.Skills as skill}
                          {@const skillDisplayName = skill.skillName || itemsIndex[skill.skillItemId]?.replace(' Skill Implant (L)', '') || `Skill #${skill.skillItemId}`}
                          <div class="reward-row">
                            <span class="reward-name">
                              {#if skill.skillItemId}
                                <a href="/information/skills/{encodeURIComponent(skillDisplayName)}" class="reward-link">{skillDisplayName}</a>
                              {:else}
                                {skillDisplayName}
                              {/if}
                            </span>
                            {#if skill.pedValue > 0}
                              <span class="reward-value skill">+{formatPedValue(skill.pedValue)} PED</span>
                            {/if}
                          </div>
                        {/each}
                      {/if}
                      {#if unlockCount > 0}
                        {#each pkg.Unlocks as unlock}
                          <div class="reward-row">
                            <span class="reward-value unlock">&#10003;</span>
                            <span class="reward-name">{unlock}</span>
                          </div>
                        {/each}
                      {/if}
                    </div>
                  {/if}
                {/each}
              </div>
            </div>
          {/if}

          <!-- Show on Map button -->
          {#if activeMission?.StartLocation?.Id}
            {@const startLocPlanet = activeMission.StartLocation.Planet?.Name || activeMission.Planet?.Name || 'calypso'}
            {@const mapPlanetSlug = startLocPlanet.toLowerCase().replace(/[^a-z0-9]/g, '')}
            <a href="/maps/{mapPlanetSlug}/{activeMission.StartLocation.Id}" class="map-link-btn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon>
                <line x1="8" y1="2" x2="8" y2="18"></line>
                <line x1="16" y1="6" x2="16" y2="22"></line>
              </svg>
              <span>View on Map</span>
            </a>
          {/if}
        {/if}
      </aside>

      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name || ''}
            path="Name"
            type="text"
            placeholder={isChainView ? 'Mission chain name' : 'Mission name'}
          />
        </h1>

        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeEntity?.Properties?.Description || ''}
              onchange={(data) => updateField('Properties.Description', data)}
              placeholder={isChainView ? 'Describe this mission chain...' : 'Describe this mission...'}
              showWaypoints={true}
            />
          {:else if hasActualText(activeEntity?.Properties?.Description)}
            <div class="description-content">{@html sanitizeHtml(activeEntity.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || (isChainView ? 'This mission chain' : 'This mission')} has no description yet.
            </div>
          {/if}
        </div>

        {#if !isChainView && hasValidChainSelected}
          <DataSection title="Chain Preview" subtitle="Nearby missions" icon="">
            {#if previewPrev.length || previewNext.length}
              <div class="chain-preview">
                {#each [...previewPrev].reverse() as node, i}
                  <a class="chain-chip prev" href={`/information/missions/${encodeURIComponentSafe(node.Name)}`}>{node.Name}</a>
                  <span class="chain-arrow">→</span>
                {/each}
                <span class="chain-chip current">{activeMission?.Name}</span>
                {#each previewNext as node}
                  <span class="chain-arrow">→</span>
                  <a class="chain-chip next" href={`/information/missions/${encodeURIComponentSafe(node.Name)}`}>{node.Name}</a>
                {/each}
              </div>
            {:else}
              <div class="empty-text">No nearby missions in the graph.</div>
            {/if}
            <button class="graph-btn" onclick={() => showGraphDialog = true}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><line x1="12" y1="8" x2="5" y2="16"/><line x1="12" y1="8" x2="19" y2="16"/></svg>
              Full Graph
            </button>
          </DataSection>
        {/if}

        {#if !isChainView}
          <DataSection
            title="Steps & Objectives"
            subtitle="{activeMission?.Steps?.length || 0} step{(activeMission?.Steps?.length || 0) === 1 ? '' : 's'}"
            icon=""
          >
            {#if $editMode}
              <MissionStepsEditor
                steps={activeMission?.Steps || []}
                fieldPath="Steps"
                mobMaturities={data.mobMaturities || []}
                mobSpeciesList={data.mobSpeciesList || []}
                npcOptions={npcOptions}
                locationOptions={locationOptions}
                itemsIndex={itemsIndex}
                itemsMap={itemsMap}
                missionPlanet={missionPlanetResolved}
              />
            {:else if activeMission?.Steps?.length}
              <div class="steps-list">
                {#each activeMission.Steps as step}
                  <div class="step-block">
                    <div class="step-heading">
                      <span class="step-number">Step {step.Index}</span>
                      {#if step.Title}
                        <span class="step-title">{step.Title}</span>
                      {/if}
                    </div>
                    {#if step.Description}
                      <div class="step-description description-content">{@html sanitizeHtml(step.Description)}</div>
                    {/if}
                    {#if step.Objectives?.length}
                      <ul class="objective-list">
                        {#each step.Objectives as objective, objIdx}
                          {@const details = getObjectiveDetails(objective)}
                          {@const hasDetails = details.length > 0}
                          <li class="objective-item">
                            {#if hasDetails}
                              <details class="objective-details">
                                <summary class="objective-summary">
                                  <span class="objective-bullet">•</span>
                                  <span class="objective-text">{formatObjectiveSummary(objective)}</span>
                                  <span class="expand-hint">(details)</span>
                                </summary>
                                <div class="objective-expanded">
                                  {#each details as detail}
                                    <div class="detail-row">
                                      <span class="detail-label">{detail.label}:</span>
                                      <span class="detail-value">{#if detail.href}<a href={detail.href} class="detail-link">{detail.value}</a>{:else}{detail.value}{/if}</span>
                                    </div>
                                  {/each}
                                </div>
                              </details>
                            {:else}
                              <span class="objective-bullet">•</span>
                              <span class="objective-text">{formatObjectiveSummary(objective)}</span>
                            {/if}
                          </li>
                        {/each}
                      </ul>
                    {:else}
                      <div class="empty-text">No objectives defined.</div>
                    {/if}
                  </div>
                {/each}
              </div>
            {:else}
              <div class="empty-text">No steps yet.</div>
            {/if}
          </DataSection>

          <!-- Map Embed for objectives with coordinates -->
          {#if !isChainView && !$editMode && mapObjectives.length > 0}
            <DataSection title="Objectives Map" subtitle="Visual overview of mission locations" icon="">
              <MissionMapEmbed
                objectives={mapObjectives}
                planet={mapPlanet}
                showPath={true}
                height={300}
                title=""
              />
            </DataSection>
          {/if}

          {#if $editMode}
            <DataSection title="Rewards" subtitle="Items, skills, and unlocks" icon="">
              <MissionRewardsEditor
                rewards={activeMission?.Rewards}
                fieldPath="Rewards"
                itemsIndex={itemsIndex}
              />
            </DataSection>
          {/if}

          <DataSection title="Dependencies" subtitle="Prerequisites and follow-ups" icon="">
            {#if $editMode}
              <div class="dependency-editor">
                <div class="dependency-column">
                  <h4>Prerequisites</h4>
                  {#if activeMission?.Dependencies?.Prerequisites?.length}
                    {#each activeMission.Dependencies.Prerequisites as prereq, idx (idx)}
                      <div class="dependency-row">
                        <SearchInput
                          value={prereq?.Name || getOptionLabel(missionOptions, prereq?.Id)}
                          options={missionOptions}
                          placeholder="Select mission"
                          onselect={(e) => updatePrerequisite(idx, e.value)}
                        />
                        <button type="button" class="btn-icon danger" onclick={() => removePrerequisite(idx)} title="Remove prerequisite">×</button>
                      </div>
                    {/each}
                  {:else}
                    <div class="empty-text">None</div>
                  {/if}
                  <button type="button" class="btn-add" onclick={addPrerequisite}>
                    <span>+</span> Add Prerequisite
                  </button>
                </div>
                <div class="dependency-column">
                  <h4>Unlocks</h4>
                  {#if activeMission?.Dependencies?.Dependents?.length}
                    {#each activeMission.Dependencies.Dependents as dep, idx (idx)}
                      <div class="dependency-row">
                        <SearchInput
                          value={dep?.Name || getOptionLabel(missionOptions, dep?.Id)}
                          options={missionOptions}
                          placeholder="Select mission"
                          onselect={(e) => {
                            const mission = missionsList.find(m => String(m.Id) === e.value);
                            updateDependent(idx, mission);
                          }}
                        />
                        <button type="button" class="btn-icon danger" onclick={() => removeDependent(idx)} title="Remove unlock">×</button>
                      </div>
                    {/each}
                  {:else}
                    <div class="empty-text">None</div>
                  {/if}
                  <button type="button" class="btn-add" onclick={addDependent}>
                    <span>+</span> Add Unlock
                  </button>
                </div>
              </div>
            {:else if activeMission?.Dependencies?.Prerequisites?.length || activeMission?.Dependencies?.Dependents?.length}
              <div class="dependency-grid">
                <div>
                  <h4>Prerequisites</h4>
                  {#if activeMission?.Dependencies?.Prerequisites?.length}
                    <ul>
                      {#each activeMission.Dependencies.Prerequisites as prereq}
                        <li><a href={`/information/missions/${encodeURIComponentSafe(prereq.Name)}`}>{prereq.Name}</a></li>
                      {/each}
                    </ul>
                  {:else}
                    <div class="empty-text">None</div>
                  {/if}
                </div>
                <div>
                  <h4>Unlocks</h4>
                  {#if activeMission?.Dependencies?.Dependents?.length}
                    <ul>
                      {#each activeMission.Dependencies.Dependents as dep}
                        <li><a href={`/information/missions/${encodeURIComponentSafe(dep.Name)}`}>{dep.Name}</a></li>
                      {/each}
                    </ul>
                  {:else}
                    <div class="empty-text">None</div>
                  {/if}
                </div>
              </div>
            {:else}
              <div class="empty-text">No dependencies recorded.</div>
            {/if}
          </DataSection>
        {:else}
          <DataSection title="Missions in Chain" subtitle="{activeChain?.Missions?.length || 0} missions" icon="">
            {#if activeChain?.Missions?.length}
              <ul class="chain-mission-list">
                {#each activeChain.Missions as mission}
                  <li>
                    <a href={`/information/missions/${encodeURIComponentSafe(mission.Name)}`}>{mission.Name}</a>
                  </li>
                {/each}
              </ul>
            {:else}
              <div class="empty-text">No missions in this chain yet.</div>
            {/if}
            <button class="graph-btn" onclick={() => showGraphDialog = true}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="5" r="3"/><circle cx="5" cy="19" r="3"/><circle cx="19" cy="19" r="3"/><line x1="12" y1="8" x2="5" y2="16"/><line x1="12" y1="8" x2="19" y2="16"/></svg>
              Full Graph
            </button>
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>{isChainView ? 'Mission Chains' : 'Missions'}</h2>
      <p>Select a {isChainView ? 'mission chain' : 'mission'} from the list to view details.</p>
    </div>
  {/if}

  {#if showGraphDialog}
    <div class="dialog-overlay" role="presentation" onclick={() => showGraphDialog = false}>
      <div class="graph-dialog" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <div class="graph-dialog-header">
          <h3>{activeMission?.MissionChain?.Name || 'Mission Graph'}</h3>
          <span class="graph-dialog-count">{graphData?.nodes?.length || 0} missions</span>
          <button class="dialog-close" onclick={() => showGraphDialog = false}>×</button>
        </div>
        <div class="graph-flow">
          {#if graphLayers.layers.length}
            {#each graphLayers.layers as layer, layerIdx}
              {#if layerIdx > 0}
                <div class="graph-layer-arrow">↓</div>
              {/if}
              <div class="graph-layer">
                <span class="graph-layer-label">{layerIdx === 0 ? 'Start' : `Stage ${layerIdx + 1}`}</span>
                <div class="graph-layer-chips">
                  {#each layer as node}
                    {@const isCurrent = String(node.Id) === String(activeMission?.Id)}
                    {#if isCurrent}
                      <span class="graph-chip current">{node.Name}</span>
                    {:else}
                      <a
                        class="graph-chip"
                        href={`/information/missions/${encodeURIComponentSafe(node.Name)}`}
                        onclick={() => showGraphDialog = false}
                      >{node.Name}</a>
                    {/if}
                  {/each}
                </div>
              </div>
            {/each}
          {:else}
            <div class="empty-text">No missions in this graph.</div>
          {/if}
          {#if graphLayers.disconnected.length}
            <div class="graph-layer-arrow">⋯</div>
            <div class="graph-layer disconnected">
              <span class="graph-layer-label">Disconnected</span>
              <div class="graph-layer-chips">
                {#each graphLayers.disconnected as node}
                  {@const isCurrent = String(node.Id) === String(activeMission?.Id)}
                  {#if isCurrent}
                    <span class="graph-chip current">{node.Name}</span>
                  {:else}
                    <a
                      class="graph-chip disconnected"
                      href={`/information/missions/${encodeURIComponentSafe(node.Name)}`}
                      onclick={() => showGraphDialog = false}
                    >{node.Name}</a>
                  {/if}
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}

  {#if showChainDialog}
    <ChainEditorDialog
      chainName={activeMission?.MissionChain?.Name}
      chainDescription={activeMission?.MissionChain?.Description}
      chainPlanet={activeMission?.MissionChain?.Planet}
      isCreating={chainDialogMode === 'create'}
      allChains={missionChainsList}
      allMissions={missionsList}
      currentMission={activeMission}
      graphData={graphData}
      planetOptions={planetOptions}
      currentPlanetName={activeMission?.Planet?.Name || 'Calypso'}
      onclose={closeChainDialog}
      oncreate={handleChainCreate}
      onselect={handleChainSelect}
      onupdateChain={handleChainUpdate}
      onaddPrerequisite={handleDialogAddPrerequisite}
      onupdatePrerequisite={handleDialogUpdatePrerequisite}
      onremovePrerequisite={handleDialogRemovePrerequisite}
      onaddDependent={handleDialogAddDependent}
      onupdateDependent={handleDialogUpdateDependent}
      onremoveDependent={handleDialogRemoveDependent}
    />
  {/if}
</WikiPage>

<style>
  .missions-sidebar {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }

  .missions-sidebar :global(.wiki-nav) {
    flex: 1;
    min-height: 0;
  }

  .sidebar-toggle {
    display: flex;
    gap: 8px;
    padding: 8px;
  }

  .sidebar-toggle button {
    flex: 1;
    border: 1px solid var(--border-color, #555);
    background: var(--secondary-color);
    color: var(--text-color);
    padding: 6px 8px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
  }

  .sidebar-toggle button.active {
    background: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .pending-change-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background-color: var(--warning-bg, #fef3c7);
    border: 1px solid var(--warning-border, #f59e0b);
    border-radius: 8px;
    margin-bottom: 16px;
  }

  .banner-content {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .banner-text {
    font-size: 14px;
  }

  .banner-actions {
    display: flex;
    gap: 8px;
  }

  .banner-btn {
    padding: 6px 12px;
    font-size: 13px;
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    cursor: pointer;
  }

  .banner-btn.primary {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  /* Details grid: align labels and values into a consistent two-column grid */
  .details-grid :global(.stat-row) {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 8px;
    align-items: center;
  }

  .details-grid :global(.stat-value) {
    min-width: 0;
    text-align: right;
  }

  .details-grid :global(.stat-value) :global(.searchable-select),
  .details-grid :global(.stat-value) :global(.local-search-input) {
    width: 100%;
  }

  .start-location-display {
    display: flex;
    flex-direction: row;
    gap: 6px;
    align-items: baseline;
    justify-content: flex-end;
  }

  .start-location-display .stat-link {
    font-size: 12px;
  }

  .waypoint-desktop {
    display: inline-flex;
    align-items: baseline;
  }

  .start-location-display :global(.waypoint-btn) {
    font-size: 10px;
    padding: 4px 6px;
  }

  @media (max-width: 768px) {
    .waypoint-desktop {
      display: none;
    }
  }

  .chain-input-row {
    display: flex;
    align-items: center;
    gap: 4px;
    width: 100%;
  }

  .chain-input-row :global(.local-search-input) {
    flex: 1;
    min-width: 0;
  }

  .chain-btn {
    width: 24px;
    height: 24px;
    border-radius: 4px;
    border: 1px solid var(--border-color, #555);
    background: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    flex-shrink: 0;
    padding: 0;
  }

  .chain-btn:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .chain-input-row.has-error :global(.local-search-input input) {
    border-color: var(--error-color, #ef4444);
  }

  .chain-error {
    font-size: 11px;
    color: var(--error-color, #ef4444);
    margin-top: 4px;
  }

  /* Cooldown inputs for Recurring missions */
  .cooldown-duration-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .cooldown-value-input {
    width: 55px;
    padding: 4px 6px;
    font-size: 12px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    text-align: center;
  }

  .cooldown-unit-select {
    padding: 4px 6px;
    font-size: 12px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    cursor: pointer;
    flex: 1;
    min-width: 70px;
  }

  .cooldown-starts-select {
    width: 100%;
    padding: 4px 8px;
    font-size: 12px;
    background: var(--input-bg, var(--secondary-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    color: var(--text-color);
    cursor: pointer;
  }

  .cooldown-value-input:hover,
  .cooldown-value-input:focus,
  .cooldown-unit-select:hover,
  .cooldown-unit-select:focus,
  .cooldown-starts-select:hover,
  .cooldown-starts-select:focus {
    border-color: var(--accent-color, #4a9eff);
    outline: none;
  }

  .cooldown-value-input::-webkit-inner-spin-button,
  .cooldown-value-input::-webkit-outer-spin-button {
    opacity: 1;
  }

  .chain-preview {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    margin-bottom: 10px;
  }

  .chain-arrow {
    color: var(--text-muted, #999);
    font-size: 11px;
    user-select: none;
  }

  .chain-chip {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    padding: 5px 12px;
    border-radius: 999px;
    font-size: 12px;
    color: var(--text-color);
    text-decoration: none;
    transition: border-color 0.15s, background-color 0.15s;
  }

  a.chain-chip:hover {
    border-color: var(--accent-color, #4a9eff);
    background: var(--hover-color);
  }

  .chain-chip.current {
    background: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
    font-weight: 600;
  }

  .graph-btn {
    margin-top: 10px;
    padding: 6px 14px;
    border-radius: 4px;
    border: 1px solid var(--accent-color, #4a9eff);
    background: transparent;
    color: var(--accent-color, #4a9eff);
    cursor: pointer;
    font-size: 12px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background-color 0.15s, color 0.15s;
  }

  .graph-btn:hover {
    background: var(--accent-color, #4a9eff);
    color: white;
  }

  .steps-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .step-block {
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 12px;
    background: var(--secondary-color);
  }

  .step-heading {
    display: flex;
    gap: 8px;
    align-items: baseline;
  }

  .step-number {
    font-size: 12px;
    text-transform: uppercase;
    color: var(--text-muted, #999);
  }

  .step-title {
    font-weight: 600;
  }

  .step-description {
    margin: 6px 0 0;
  }

  .objective-list {
    margin: 8px 0 0;
    padding: 0;
    list-style: none;
    color: var(--text-color);
  }

  .objective-item {
    margin: 4px 0;
    line-height: 1.5;
  }

  .objective-bullet {
    color: var(--accent-color, #4a9eff);
    margin-right: 8px;
  }

  .objective-text {
    color: var(--text-color);
  }

  .objective-details {
    cursor: pointer;
  }

  .objective-summary {
    display: flex;
    align-items: baseline;
    gap: 0;
    list-style: none;
  }

  .objective-summary::-webkit-details-marker {
    display: none;
  }

  .expand-hint {
    font-size: 11px;
    color: var(--text-muted, #999);
    margin-left: 8px;
    opacity: 0.7;
  }

  .objective-details[open] .expand-hint {
    display: none;
  }

  .objective-expanded {
    margin: 8px 0 12px 18px;
    padding: 8px 12px;
    background: var(--bg-color-secondary, rgba(0, 0, 0, 0.2));
    border-radius: 4px;
    font-size: 12px;
  }

  .detail-row {
    display: flex;
    gap: 8px;
    margin: 4px 0;
    flex-wrap: wrap;
  }

  .detail-label {
    font-weight: 600;
    color: var(--text-color);
    flex-shrink: 0;
  }

  .detail-value {
    color: var(--text-muted, #999);
  }

  .detail-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .detail-link:hover {
    text-decoration: underline;
  }

  .dependency-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
  }

  .dependency-editor {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
  }

  .dependency-column {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .dependency-row {
    display: grid;
    grid-template-columns: minmax(180px, 1fr) auto;
    gap: 8px;
    align-items: center;
  }

  .dependency-row :global(.searchable-select) {
    width: 100%;
  }

  .btn-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    margin-top: 4px;
  }

  .btn-add:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

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

  .btn-icon.danger:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .chain-mission-list {
    padding-left: 18px;
  }

  .empty-text {
    font-size: 12px;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.65);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .graph-dialog {
    background: var(--primary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 10px;
    width: min(900px, 94vw);
    max-height: 85vh;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .graph-dialog-header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 18px;
    border-bottom: 2px solid var(--accent-color, #4a9eff);
  }

  .graph-dialog-header h3 {
    margin: 0;
    font-size: 16px;
    flex: 1;
  }

  .graph-dialog-count {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .dialog-close {
    background: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 4px;
    width: 28px;
    height: 28px;
    font-size: 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .dialog-close:hover {
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .graph-flow {
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .graph-layer {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    width: 100%;
  }

  .graph-layer-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted, #999);
    font-weight: 600;
  }

  .graph-layer-chips {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 8px;
  }

  .graph-layer-arrow {
    color: var(--text-muted, #999);
    font-size: 16px;
    line-height: 1;
    user-select: none;
    padding: 2px 0;
  }

  .graph-chip {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 13px;
    color: var(--text-color);
    text-decoration: none;
    transition: border-color 0.15s, background-color 0.15s, box-shadow 0.15s;
    min-height: 32px;
    display: inline-flex;
    align-items: center;
  }

  a.graph-chip:hover {
    border-color: var(--accent-color, #4a9eff);
    background: var(--hover-color);
  }

  .graph-chip.current {
    background: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
    font-weight: 600;
    box-shadow: 0 0 12px rgba(74, 158, 255, 0.3);
  }

  a.graph-chip.disconnected {
    border-style: dashed;
    color: var(--text-muted, #999);
  }

  a.graph-chip.disconnected:hover {
    border-color: var(--warning-color, #fbbf24);
    color: var(--text-color);
  }

  .graph-layer.disconnected .graph-layer-label {
    color: var(--warning-color, #fbbf24);
  }

  @media (max-width: 899px) {
    .graph-dialog {
      width: 100vw;
      max-height: 90vh;
      border-radius: 10px 10px 0 0;
    }

    .graph-chip {
      font-size: 12px;
      padding: 8px 12px;
      min-height: 36px;
    }

    .graph-flow {
      padding: 14px;
    }
  }

  /* Stat link styling */
  .stat-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .stat-link:hover {
    text-decoration: underline;
  }

  .stat-none {
    color: var(--text-muted, #999);
  }

  /* Rewards display - styled like set effects */
  .rewards-section {
    padding: 12px;
  }

  .rewards-display {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .reward-group {
    padding: 10px 12px;
    background-color: var(--secondary-color);
    border-radius: 6px;
    border-left: 3px solid var(--accent-color, #4a9eff);
  }

  .reward-choice-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
    text-transform: uppercase;
    margin-bottom: 6px;
  }

  .reward-rarity-header {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    margin-top: 8px;
    margin-bottom: 2px;
    padding: 2px 0;
  }

  .reward-rarity-header:first-child {
    margin-top: 0;
  }

  .reward-rarity-header.rarity-guaranteed {
    color: var(--success-color, #4ade80);
  }

  .reward-rarity-header.rarity-uncommon {
    color: var(--accent-color, #4a9eff);
  }

  .reward-rarity-header.rarity-rare {
    color: var(--warning-color, #fbbf24);
  }

  .reward-rarity-header.rarity-very-rare {
    color: var(--error-color, #ff6b6b);
  }

  .reward-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 3px 0;
    font-size: 13px;
  }

  .reward-value {
    font-weight: 600;
    color: var(--success-color, #4ade80);
    flex-shrink: 0;
    min-width: 40px;
  }

  .reward-value.skill {
    color: var(--info-color, #60a5fa);
  }

  .reward-value.unlock {
    color: var(--warning-color, #fbbf24);
  }

  .reward-name {
    color: var(--text-color);
    flex: 1;
    text-align: left;
  }

  /* For items: value is first, name is second - right-align the name */
  .reward-value + .reward-name {
    text-align: right;
  }

  .reward-link {
    color: var(--text-color);
    text-decoration: none;
  }

  .reward-link:hover {
    color: var(--accent-color, #4a9eff);
    text-decoration: underline;
  }

  .reward-ped {
    color: var(--text-muted, #999);
    font-size: 11px;
    margin-left: 4px;
  }

</style>

