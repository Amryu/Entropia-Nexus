<script>
  // @ts-nocheck
  import '$lib/style.css';
  import '../construction.css';

  import { onMount, onDestroy, tick } from 'svelte';
  import { browser } from '$app/environment';
  import { goto } from '$app/navigation';

  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSearchInput from '$lib/components/wiki/SearchInput.svelte';
  import CraftingTreeNode from '$lib/components/tools/CraftingTreeNode.svelte';
  import MassBuyDialog from '../MassBuyDialog.svelte';
  import { loading } from '../../../../stores.js';
  import { hasItemTag, getItemLink, getTypeLink, clampDecimals } from '$lib/util.js';
  import { hasCondition } from '$lib/shopUtils.js';
  import {
    buildCraftingTree,
    generateCraftingSteps,
    generateShoppingList,
    getAllBlueprintsInTree,
    createEmptyPlan,
    isLimitedBlueprint,
    hasSiB,
    getMaxNonFailChance,
    calculateSuccessRates,
    buildProductToBlueprintMap,
    getMaterialCraftInfo,
    getAllMaterialBlueprints,
    DEFAULT_CONFIG,
    MAX_NON_FAIL_SIB,
    MAX_NON_FAIL_NON_SIB,
    getHotspotBreakdown,
    HOTSPOTS,
    HIGH_SUCCESS_WEIGHT,
    HIGH_SUCCESS_OUTPUT_RANGE,
    HOTSPOT_VARIANCE,
    SPLIT_NEAR_SUCCESS_FRACTION,
    SUCCESS_THRESHOLD,
    MAX_OUTPUT_MULTIPLIER,
    CONDITION_MIN,
    CONDITION_MAX,
    findOptimalCondition,
    findOptimalOutputCondition,
  } from '$lib/utils/constructionCalculator.js';

  export let data;
  $: user = data?.session?.user;
  $: isLoggedIn = !!user;

  const LOCAL_STORAGE_PLANS_KEY = 'construction.plans';
  const LOCAL_STORAGE_OWNERSHIP_KEY = 'construction.ownership';
  const LOCAL_STORAGE_ACTIVE_KEY = 'construction.activePlan';
  const LOCAL_STORAGE_VIEW_KEY = 'construction.view';

  // Blueprint IDs in Items table are offset by 6,000,000 from Blueprints table IDs
  const BLUEPRINT_ID_OFFSET = 6000000;

  const SECONDS_PER_ATTEMPT = 4.25;

  function formatCraftTime(seconds) {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
    const h = Math.floor(seconds / 3600);
    const m = Math.round((seconds % 3600) / 60);
    return m > 0 ? `${h}h ${m}m` : `${h}h`;
  }

  function getNodeTotalTime(node) {
    if (!node.owned) return 0;
    let time = (node.estimatedAttempts || 0) * SECONDS_PER_ATTEMPT;
    for (const child of node.materialChildren || []) {
      time += getNodeTotalTime(child);
    }
    return time;
  }

  // Hotspot model rates at max non-fail for SiB and non-SiB
  const ratesNonSiB = calculateSuccessRates(MAX_NON_FAIL_NON_SIB);
  const ratesSiB = calculateSuccessRates(MAX_NON_FAIL_SIB);

  // State
  let blueprintsLoading = true;
  let blueprintCache = new Map();
  let allBlueprints = [];

  let localPlans = [];
  let onlinePlans = [];
  let plans = [];
  let activePlan = null;
  let activePlanId = null;
  let activeSource = 'local';
  let planSearch = '';

  let globalOwnership = {}; // { blueprintId: false } for not-owned
  let ownershipLoading = false;

  let currentView = 'planning'; // 'planning' | 'steps' | 'tree' | 'shopping'
  let showOwnershipPanel = false;
  let showSidebar = true;
  let drawerOpen = false;
  let windowWidth = browser ? window.innerWidth : 0;
  $: isMobileLayout = windowWidth < 900;

  let onlineLoading = false;
  let onlineError = null;
  let isSaving = false;
  let saveError = null;
  let isDirty = false;

  // Debounced auto-save
  let saveTimeout = null;
  const SAVE_DEBOUNCE_MS = 2000;

  let hasLocalData = false;
  let showImportPrompt = false;
  let dataLoaded = false;

  // Delete confirmation dialog
  let showDeleteDialog = false;
  let planToDelete = null;

  // Import/Export
  let fileInput = null;
  let showImportSourceDialog = false;

  // Hotspot debug dialog
  let showHotspotDialog = false;
  let showConditionInfoDialog = false;

  // Markup state: { materialName: markup%, blueprintId: markup% }
  let markupValues = {};
  const DEFAULT_MARKUP = 100;

  // Steps state
  let checkedSteps = new Set();
  let collapsedSteps = new Set();

  // Shopping state
  let checkedShoppingMaterials = new Set();
  let checkedShoppingProducts = new Set();

  // Mass Buy dialog state
  let showMassBuy = false;
  let massBuyItems = [];

  // Exchange data for WAP, sell order counts, and inventory import
  let exchangeWapMap = new Map(); // itemId → wap markup %
  let exchangeSellCounts = new Map(); // itemId → sell order count
  let exchangeSlimItems = []; // flat array for InventoryImportDialog

  // Track targets for resetting checked state
  let previousTargetsKey = '';

  // Calculator configuration
  let rollChance = DEFAULT_CONFIG.rollChance; // % chance each material wins refund roll
  let certainty = DEFAULT_CONFIG.certainty; // % confidence level for attempt estimation
  let nonFailChances = {}; // { blueprintId: nonFailChance% }
  let conditionPercents = {}; // { blueprintId: conditionPercent (0-20) }
  let materialCraftConfig = {}; // { materialName: { craft: bool, preferLimited: bool } }

  // Configuration panel
  let showConfigPanel = false;

  // Blueprint picker popover for steps view
  let bpPickerMaterial = null; // materialName of the open picker, or null
  let bpPickerPos = { top: 0, left: 0 }; // fixed position for the popover

  function openBpPicker(materialName, event) {
    if (bpPickerMaterial === materialName) {
      closeBpPicker();
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    bpPickerPos = { top: rect.bottom + 4, left: rect.left };
    bpPickerMaterial = materialName;
  }

  function closeBpPicker() {
    bpPickerMaterial = null;
  }

  function selectBpFromPicker(materialName, bpId) {
    selectMaterialBlueprint(materialName, bpId);
    closeBpPicker();
  }

  // Product to blueprint map (for material crafting)
  $: productToBlueprintMap = blueprintCache.size > 0 ? buildProductToBlueprintMap(blueprintCache) : new Map();

  // Compute effective ownership: combines actual ownership with buy preferences
  // A BP is "effectively not owned" if: not owned OR (owned but user prefers to buy)
  $: effectiveOwnership = (() => {
    const effective = { ...globalOwnership };
    // Add buy preferences - if owned but buying, treat as not owned
    for (const bpId of Object.keys(buyPreferences)) {
      if (buyPreferences[bpId] === true && globalOwnership[bpId] !== false) {
        effective[bpId] = false; // Treat as not owned for calculation
      }
    }
    return effective;
  })();

  // Sync calculator config into plan data for persistence
  $: if (activePlan) {
    const config = {};
    if (Object.keys(nonFailChances).length > 0) config.nonFailChances = nonFailChances;
    if (Object.keys(conditionPercents).length > 0) config.conditionPercents = conditionPercents;
    if (Object.keys(materialCraftConfig).length > 0) config.materialCraftConfig = materialCraftConfig;
    activePlan.data.config = Object.keys(config).length > 0 ? config : undefined;
  }

  // Computed - pass configuration to buildCraftingTree
  $: craftingConfig = { rollChance, certainty, nonFailChances, materialCraftConfig, conditionPercents };
  $: craftingTree = activePlan && blueprintCache.size > 0
    ? buildCraftingTree(activePlan.data?.targets || [], effectiveOwnership, blueprintCache, craftingConfig)
    : [];
  $: craftingSteps = generateCraftingSteps(craftingTree);
  $: shoppingList = generateShoppingList(craftingTree);
  $: blueprintsInTree = getAllBlueprintsInTree(craftingTree);

  // Set of product names that have their own crafting step (i.e. are being crafted, not bought)
  $: craftedProductNames = new Set(craftingSteps.filter(s => s.owned).map(s => s.blueprint?.Product?.Name).filter(Boolean));

  $: filteredPlans = plans.filter(p =>
    !planSearch || p.name.toLowerCase().includes(planSearch.toLowerCase())
  );

  $: breadcrumbs = [
    { label: 'Tools', href: '/tools' },
    { label: 'Construction Calculator', href: '/tools/construction' },
    ...(activePlan?.name ? [{ label: activePlan.name }] : [])
  ];

  // Reset checked states when targets or ownership changes
  $: {
    const targets = activePlan?.data?.targets || [];
    const currentKey = JSON.stringify(targets.map(t => `${t.blueprintId}:${t.quantity}`)) + JSON.stringify(globalOwnership);
    if (currentKey !== previousTargetsKey && previousTargetsKey !== '') {
      // Targets or ownership changed - reset checked states
      checkedSteps = new Set();
      collapsedSteps = new Set();
      checkedShoppingMaterials = new Set();
      checkedShoppingProducts = new Set();
    }
    previousTargetsKey = currentKey;
  }

  function getApiBase() {
    return browser
      ? (import.meta.env.VITE_API_URL || 'https://api.entropianexus.com')
      : (process.env.INTERNAL_API_URL || 'http://api:3000');
  }

  // Blueprint-specific link helper
  function getBlueprintLink(blueprint) {
    if (!blueprint?.Name) return null;
    return getTypeLink(blueprint.Name, 'Blueprint');
  }

  // Cost calculation helpers
  function getMaterialTT(material) {
    return (material.Item?.Properties?.Economy?.MaxTT || 0) * (material.Amount || 0);
  }

  function getMarkup(key) {
    if (markupValues[key] != null) return markupValues[key];
    return shoppingItemWapMap[key] ?? DEFAULT_MARKUP;
  }

  function hasCustomMarkup(key) {
    return markupValues[key] != null;
  }

  function getWapMarkup(key) {
    return shoppingItemWapMap[key] ?? null;
  }

  function setMarkup(key, value) {
    const num = parseFloat(value);
    if (!isNaN(num) && num >= 0) {
      markupValues[key] = Math.min(100000, num);
      markupValues = markupValues; // trigger reactivity
    }
  }

  function resetMarkup(key) {
    delete markupValues[key];
    markupValues = markupValues; // trigger reactivity
  }

  // Exchange data helpers
  function flattenExchangeItems(obj) {
    const items = [];
    function traverse(current) {
      if (Array.isArray(current)) items.push(...current);
      else if (typeof current === 'object' && current !== null) Object.values(current).forEach(traverse);
    }
    traverse(obj);
    return items;
  }

  async function fetchExchangeData() {
    try {
      const res = await fetch('/api/market/exchange');
      if (!res.ok) return;
      const data = await res.json();
      const items = flattenExchangeItems(data);
      exchangeSlimItems = items;
      const wapMap = new Map();
      const sellMap = new Map();
      for (const item of items) {
        if (item.i) {
          if (item.w) wapMap.set(item.i, item.w);
          if (item.s != null) sellMap.set(item.i, item.s);
        }
      }
      exchangeWapMap = wapMap;
      exchangeSellCounts = sellMap;
    } catch {
      // Non-critical — WAP fallback simply won't be available
    }
  }

  function getBlueprintCostPerClick(blueprint, _markupValues) {
    if (!blueprint?.Materials) return { ttCost: 0, muCost: 0 };
    let ttCost = 0;
    let muCost = 0;
    for (const mat of blueprint.Materials) {
      const tt = getMaterialTT(mat);
      const mu = getMarkup(`mat:${mat.Item?.Name}`);
      ttCost += tt;
      muCost += tt * mu / 100;
    }
    return { ttCost, muCost };
  }

  function getStepTotalCost(step) {
    if (step.owned) {
      let ttCost = 0;
      let muCost = 0;
      for (const mat of step.materials) {
        const matTT = (mat.item?.Properties?.Economy?.MaxTT || 0) * mat.totalAmount;
        const mu = getMarkup(`mat:${mat.item?.Name}`);
        ttCost += matTT;
        muCost += matTT * mu / 100;
      }
      return { ttCost, muCost };
    } else {
      const product = step.blueprint.Product;
      const productTT = (product?.Properties?.Economy?.MaxTT || 0) * step.quantityWanted;
      const mu = getMarkup(`prod:${product?.Name || step.blueprint.Name}`);
      return { ttCost: productTT, muCost: productTT * mu / 100 };
    }
  }

  function getCostPerClick(step) {
    if (!step.owned || step.estimatedAttempts === 0) return { ttCost: 0, muCost: 0 };
    const total = getStepTotalCost(step);
    return {
      ttCost: total.ttCost / step.estimatedAttempts,
      muCost: total.muCost / step.estimatedAttempts
    };
  }

  // Step interaction helpers
  function toggleStepChecked(stepIndex) {
    if (checkedSteps.has(stepIndex)) {
      checkedSteps.delete(stepIndex);
    } else {
      checkedSteps.add(stepIndex);
      // Auto-collapse when checking off a step
      collapsedSteps.add(stepIndex);
      collapsedSteps = new Set(collapsedSteps);
    }
    checkedSteps = new Set(checkedSteps); // trigger reactivity
  }

  function toggleStepCollapsed(stepIndex) {
    if (collapsedSteps.has(stepIndex)) {
      collapsedSteps.delete(stepIndex);
    } else {
      collapsedSteps.add(stepIndex);
    }
    collapsedSteps = new Set(collapsedSteps); // trigger reactivity
  }

  // Global condition preset helpers
  function stepSupportsOutputOptimization(step) {
    if (!step.owned) return false;
    const product = step.blueprint?.Product;
    if (product && hasCondition(product)) return false;
    const maxCraft = step.blueprint?.Properties?.MaximumCraftAmount;
    if (maxCraft === 1) return false;
    return true;
  }

  function applyGlobalCondition(mode) {
    const newConditions = {};
    for (const step of craftingSteps) {
      if (!step.owned) continue;
      const bpId = step.blueprint.Id;
      if (mode === 'stability') {
        newConditions[bpId] = 0;
      } else if (mode === 'attempts') {
        newConditions[bpId] = findOptimalCondition(step.blueprint, step.quantityWanted, nonFailChances[bpId], certainty);
      } else if (mode === 'output') {
        newConditions[bpId] = findOptimalOutputCondition(step.blueprint, nonFailChances[bpId], certainty);
      }
    }
    conditionPercents = newConditions;
    markDirty();
  }

  $: anyStepSupportsOutput = craftingSteps.some(s => stepSupportsOutputOptimization(s));

  // Shopping list toggle helpers
  function toggleShoppingMaterial(materialName) {
    if (checkedShoppingMaterials.has(materialName)) {
      checkedShoppingMaterials.delete(materialName);
    } else {
      checkedShoppingMaterials.add(materialName);
    }
    checkedShoppingMaterials = new Set(checkedShoppingMaterials);
  }

  function toggleShoppingProduct(productName) {
    if (checkedShoppingProducts.has(productName)) {
      checkedShoppingProducts.delete(productName);
    } else {
      checkedShoppingProducts.add(productName);
    }
    checkedShoppingProducts = new Set(checkedShoppingProducts);
  }

  // Mass Buy helpers
  function openMassBuy(items) {
    massBuyItems = items;
    showMassBuy = true;
  }

  function openMassBuyAll() {
    const items = [];
    for (const mat of shoppingList.materials) {
      if (checkedShoppingMaterials.has(mat.item.Name)) continue;
      if (!mat.item?.Id) continue;
      items.push({
        itemId: mat.item.Id,
        name: mat.item.Name,
        quantity: Math.ceil(mat.adjustedAmount || mat.totalAmount),
        markup: getMarkup(`mat:${mat.item?.Name}`)
      });
    }
    for (const bp of shoppingList.limitedBlueprints || []) {
      if (checkedShoppingProducts.has(bp.blueprint.Name)) continue;
      items.push({
        itemId: bp.blueprint.Id + BLUEPRINT_ID_OFFSET,
        name: bp.blueprint.Name,
        quantity: Math.ceil(bp.totalAmount),
        markup: getMarkup(`bp:${bp.blueprint.Id}`)
      });
    }
    for (const prod of shoppingList.productsToBuy) {
      if (checkedShoppingProducts.has(prod.item.Name)) continue;
      if (!prod.item?.Id) continue;
      items.push({
        itemId: prod.item.Id,
        name: prod.item.Name,
        quantity: Math.ceil(prod.totalAmount),
        markup: getMarkup(`prod:${prod.item?.Name}`)
      });
    }
    if (items.length > 0) {
      massBuyItems = items;
      showMassBuy = true;
    }
  }

  $: allShoppingItemsChecked = (() => {
    if (!shoppingList) return true;
    const matUnchecked = shoppingList.materials.some(m => !checkedShoppingMaterials.has(m.item.Name));
    const bpUnchecked = (shoppingList.limitedBlueprints || []).some(b => !checkedShoppingProducts.has(b.blueprint.Name));
    const prodUnchecked = shoppingList.productsToBuy.some(p => !checkedShoppingProducts.has(p.item.Name));
    return !matUnchecked && !bpUnchecked && !prodUnchecked;
  })();

  // Build WAP lookup keyed by markup key (mat:Name, bp:Id, prod:Name)
  // Used by getMarkup() as fallback when no custom value is set
  $: shoppingItemWapMap = (() => {
    const map = {};
    if (exchangeWapMap.size === 0) return map;
    // Materials from crafting steps
    for (const step of craftingSteps) {
      if (!step.owned) continue;
      for (const mat of step.materials) {
        if (mat.item?.Id && mat.item?.Name) {
          const wap = exchangeWapMap.get(mat.item.Id);
          if (wap != null) map[`mat:${mat.item.Name}`] = wap;
        }
      }
    }
    // Limited blueprints
    for (const step of craftingSteps) {
      if (step.isLimited && step.owned && step.blueprint?.Id) {
        const wap = exchangeWapMap.get(step.blueprint.Id + BLUEPRINT_ID_OFFSET);
        if (wap != null) map[`bp:${step.blueprint.Id}`] = wap;
      }
    }
    // Products from shopping list
    if (shoppingList) {
      for (const prod of shoppingList.productsToBuy) {
        if (prod.item?.Id && prod.item?.Name) {
          const wap = exchangeWapMap.get(prod.item.Id);
          if (wap != null) map[`prod:${prod.item.Name}`] = wap;
        }
      }
    }
    return map;
  })();

  // Get all unique materials needing markup (for the markup section)
  $: allMaterialsForMarkup = (() => {
    const materials = new Map();
    for (const step of craftingSteps) {
      if (!step.owned) continue;
      for (const mat of step.materials) {
        // Skip materials that are being crafted - they have their own step costs
        if (craftedProductNames.has(mat.item?.Name)) continue;
        if (!materials.has(mat.item?.Name)) {
          materials.set(mat.item?.Name, mat.item);
        }
      }
    }
    return Array.from(materials.entries()).map(([name, item]) => ({ name, item }));
  })();

  // Get (L) blueprints that need markup (when we need to buy them)
  $: limitedBlueprintsForMarkup = craftingSteps
    .filter(s => s.isLimited && s.owned)
    .map(s => s.blueprint);

  // Get products that need to be bought (unowned blueprints)
  $: productsToBuyForMarkup = (() => {
    const products = new Map();
    for (const step of craftingSteps) {
      if (step.owned) continue;
      const product = step.blueprint.Product;
      const name = product?.Name || step.blueprint.Name;
      if (!products.has(name)) {
        products.set(name, product || { Name: name });
      }
    }
    return Array.from(products.entries()).map(([name, item]) => ({ name, item }));
  })();

  // Check if any steps require residue
  $: needsResidue = craftingSteps.some(s => s.owned && s.totalResidue > 0);

  // Mark plan as dirty (needs saving)
  function markDirty() {
    if (!activePlan) return;
    isDirty = true;
  }

  // Debounced auto-save: trigger save after delay when isDirty changes
  $: if (browser && isDirty && activePlan) {
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      handleSavePlan();
    }, SAVE_DEBOUNCE_MS);
  }

  // Save on page unload
  function handleBeforeUnload() {
    if (isDirty && activePlan) {
      // Synchronous save for local, async for online (may not complete)
      if (activeSource === 'local') {
        const idx = localPlans.findIndex(p => p.id === activePlanId);
        if (idx >= 0) {
          localPlans[idx] = { ...activePlan, last_update: new Date().toISOString() };
          localStorage.setItem(LOCAL_STORAGE_PLANS_KEY, JSON.stringify(localPlans));
        }
      }
      // Note: Online save may not complete during unload, but debounce should have saved recently
    }
  }

  // URL slug helpers
  function updateUrlSlug(planId) {
    if (!browser) return;
    const newPath = planId ? `/tools/construction/${planId}` : '/tools/construction';
    if (window.location.pathname !== newPath) {
      goto(newPath, { replaceState: true, keepFocus: true, noScroll: true });
    }
  }

  // Initialize
  onMount(async () => {
    // Load blueprints
    await loadBlueprints();

    // Load local data first (always available)
    loadLocalData();

    // Load online data if logged in and set as default source
    if (isLoggedIn) {
      activeSource = 'online';
      await loadOnlineData();
      checkForImportableData();
    }

    // Update the plans list based on source
    updatePlansList();

    // Mark data loading as complete
    dataLoaded = true;

    // Select plan from URL if present (must be done after all data is loaded)
    if (data.additional?.planId) {
      const matchingPlan = plans.find(p => p.id === data.additional.planId);
      if (matchingPlan) {
        await selectPlan(data.additional.planId);
      } else {
        // Plan not found - remove invalid slug from URL
        updateUrlSlug(null);
      }
    }

    // Handle addBlueprint query param (from blueprint page "Create a construction plan" link)
    if (data.additional?.addBlueprint && !data.additional?.planId) {
      const bpId = data.additional.addBlueprint;
      const blueprint = blueprintCache.get(bpId);
      if (blueprint) {
        await handleNewPlan();
        handleAddTarget(blueprint);
        currentView = 'planning';
        // Clean the URL to remove query param
        if (activePlanId) {
          goto(`/tools/construction/${activePlanId}`, { replaceState: true });
        }
      }
    }

    // Fetch exchange data for WAP markup fallback (non-blocking)
    fetchExchangeData();

    // Add beforeunload handler
    if (browser) {
      window.addEventListener('beforeunload', handleBeforeUnload);
    }
  });

  onDestroy(() => {
    // Cleanup
    if (saveTimeout) clearTimeout(saveTimeout);
    if (browser) {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    }
  });

  async function loadBlueprints() {
    blueprintsLoading = true;
    try {
      const response = await fetch(getApiBase() + '/blueprints');
      if (response.ok) {
        allBlueprints = await response.json();
        blueprintCache = new Map(allBlueprints.map(bp => [bp.Id, bp]));
      }
    } catch (error) {
      console.error('Failed to load blueprints:', error);
    } finally {
      blueprintsLoading = false;
    }
  }

  function loadLocalData() {
    if (!browser) return;

    try {
      const storedPlans = localStorage.getItem(LOCAL_STORAGE_PLANS_KEY);
      if (storedPlans) {
        localPlans = JSON.parse(storedPlans);
      }

      const storedOwnership = localStorage.getItem(LOCAL_STORAGE_OWNERSHIP_KEY);
      if (storedOwnership && !isLoggedIn) {
        globalOwnership = JSON.parse(storedOwnership);
      }

      const storedView = localStorage.getItem(LOCAL_STORAGE_VIEW_KEY);
      if (storedView) {
        currentView = storedView;
      }

      hasLocalData = localPlans.length > 0 || Object.keys(globalOwnership).length > 0;
    } catch (e) {
      console.error('Failed to load local data:', e);
    }

    updatePlansList();
  }

  function saveLocalData() {
    if (!browser) return;

    try {
      localStorage.setItem(LOCAL_STORAGE_PLANS_KEY, JSON.stringify(localPlans));
      if (!isLoggedIn) {
        localStorage.setItem(LOCAL_STORAGE_OWNERSHIP_KEY, JSON.stringify(globalOwnership));
      }
      localStorage.setItem(LOCAL_STORAGE_VIEW_KEY, currentView);
    } catch (e) {
      console.error('Failed to save local data:', e);
    }
  }

  async function loadOnlineData() {
    if (!isLoggedIn) return;

    onlineLoading = true;
    onlineError = null;

    try {
      // Load plans
      const plansResponse = await fetch('/api/tools/construction/plans');
      if (plansResponse.ok) {
        onlinePlans = await plansResponse.json();
      } else {
        throw new Error('Failed to load plans');
      }

      // Load ownership
      const ownershipResponse = await fetch('/api/tools/construction/ownership');
      if (ownershipResponse.ok) {
        globalOwnership = await ownershipResponse.json();
      }
    } catch (error) {
      console.error('Failed to load online data:', error);
      onlineError = error.message;
    } finally {
      onlineLoading = false;
    }

    updatePlansList();
  }

  function updatePlansList() {
    if (activeSource === 'online' && isLoggedIn) {
      plans = onlinePlans;
    } else {
      activeSource = 'local';
      plans = localPlans;
    }
  }

  function switchSource(source) {
    if (source === 'online' && !isLoggedIn) return;
    activeSource = source;
    activePlan = null;
    activePlanId = null;
    isDirty = false;
    updatePlansList();
    updateUrlSlug(null);
  }

  function checkForImportableData() {
    if (!isLoggedIn || !browser) return;

    try {
      const storedPlans = localStorage.getItem(LOCAL_STORAGE_PLANS_KEY);
      const storedOwnership = localStorage.getItem(LOCAL_STORAGE_OWNERSHIP_KEY);

      if (storedPlans || storedOwnership) {
        const plans = storedPlans ? JSON.parse(storedPlans) : [];
        const ownership = storedOwnership ? JSON.parse(storedOwnership) : {};

        if (plans.length > 0 || Object.keys(ownership).length > 0) {
          hasLocalData = true;
          showImportPrompt = true;
        }
      }
    } catch (e) {
      // Ignore
    }
  }

  async function handleImportFromLocal() {
    if (!isLoggedIn || !browser) return;

    try {
      const storedPlans = localStorage.getItem(LOCAL_STORAGE_PLANS_KEY);
      const storedOwnership = localStorage.getItem(LOCAL_STORAGE_OWNERSHIP_KEY);

      const plans = storedPlans ? JSON.parse(storedPlans) : [];
      const ownership = storedOwnership ? JSON.parse(storedOwnership) : {};

      const response = await fetch('/api/tools/construction/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plans, ownership })
      });

      if (response.ok) {
        // Clear local storage
        localStorage.removeItem(LOCAL_STORAGE_PLANS_KEY);
        localStorage.removeItem(LOCAL_STORAGE_OWNERSHIP_KEY);
        hasLocalData = false;
        showImportPrompt = false;

        // Reload online data
        await loadOnlineData();
      }
    } catch (error) {
      console.error('Failed to import data:', error);
    }
  }

  async function selectPlan(planId) {
    // Save current plan before switching if dirty
    if (isDirty && activePlan) {
      await handleSavePlan();
    }

    const plan = plans.find(p => p.id === planId);
    if (plan) {
      // Deep clone to ensure reactivity for nested data
      activePlan = {
        ...plan,
        data: plan.data ? { ...plan.data, targets: [...(plan.data.targets || [])] } : { targets: [] }
      };
      activePlanId = planId;

      // Restore calculator config from plan data
      const savedConfig = activePlan.data.config;
      nonFailChances = savedConfig?.nonFailChances ? { ...savedConfig.nonFailChances } : {};
      conditionPercents = savedConfig?.conditionPercents ? { ...savedConfig.conditionPercents } : {};
      materialCraftConfig = savedConfig?.materialCraftConfig ? { ...savedConfig.materialCraftConfig } : {};

      isDirty = false;
      if (saveTimeout) clearTimeout(saveTimeout);

      // Force Svelte to process reactive updates (needed when called from reactive statements)
      await tick();

      updateUrlSlug(planId);
      // Close drawer on mobile after selecting a plan
      if (isMobileLayout) {
        drawerOpen = false;
      }
    }
  }

  function deselectPlan() {
    activePlan = null;
    activePlanId = null;
    nonFailChances = {};
    conditionPercents = {};
    materialCraftConfig = {};
    isDirty = false;
    if (saveTimeout) clearTimeout(saveTimeout);
    updateUrlSlug(null);
  }

  async function handleNewPlan() {
    const newPlan = createEmptyPlan('New Plan');

    if (activeSource === 'online' && isLoggedIn) {
      try {
        const response = await fetch('/api/tools/construction/plans', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newPlan.name, data: newPlan.data })
        });

        if (response.ok) {
          const created = await response.json();
          onlinePlans = [created, ...onlinePlans];
          updatePlansList();
          selectPlan(created.id);
        }
      } catch (error) {
        console.error('Failed to create plan:', error);
      }
    } else {
      localPlans = [newPlan, ...localPlans];
      saveLocalData();
      updatePlansList();
      selectPlan(newPlan.id);
    }
  }

  async function handleSavePlan() {
    if (!activePlan) return;

    isSaving = true;
    saveError = null;

    try {
      if (activeSource === 'online' && isLoggedIn) {
        const response = await fetch(`/api/tools/construction/plans/${activePlanId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: activePlan.name, data: activePlan.data })
        });

        if (response.ok) {
          const updated = await response.json();
          const idx = onlinePlans.findIndex(p => p.id === activePlanId);
          if (idx >= 0) {
            onlinePlans[idx] = updated;
            onlinePlans = onlinePlans;
          }
          isDirty = false;
        } else {
          throw new Error('Failed to save');
        }
      } else {
        const idx = localPlans.findIndex(p => p.id === activePlanId);
        if (idx >= 0) {
          localPlans[idx] = { ...activePlan, last_update: new Date().toISOString() };
          localPlans = localPlans;
          saveLocalData();
        }
        isDirty = false;
      }
    } catch (error) {
      console.error('Failed to save plan:', error);
      saveError = error.message;
    } finally {
      isSaving = false;
    }

    updatePlansList();
  }

  function confirmDeletePlan(planId) {
    planToDelete = planId;
    showDeleteDialog = true;
  }

  function cancelDelete() {
    showDeleteDialog = false;
    planToDelete = null;
  }

  async function handleDeletePlan() {
    if (!planToDelete) return;
    const planId = planToDelete;
    showDeleteDialog = false;
    planToDelete = null;

    if (activeSource === 'online' && isLoggedIn) {
      try {
        const response = await fetch(`/api/tools/construction/plans/${planId}`, {
          method: 'DELETE'
        });

        if (response.ok) {
          onlinePlans = onlinePlans.filter(p => p.id !== planId);
          updatePlansList();

          if (activePlanId === planId) {
            activePlan = null;
            activePlanId = null;
            isDirty = false;
            if (saveTimeout) clearTimeout(saveTimeout);
            updateUrlSlug(null);
          }
        }
      } catch (error) {
        console.error('Failed to delete plan:', error);
      }
    } else {
      localPlans = localPlans.filter(p => p.id !== planId);
      saveLocalData();
      updatePlansList();

      if (activePlanId === planId) {
        activePlan = null;
        activePlanId = null;
        isDirty = false;
        if (saveTimeout) clearTimeout(saveTimeout);
        updateUrlSlug(null);
      }
    }
  }

  function handlePlanNameChange(event) {
    if (!activePlan) return;
    activePlan.name = event.target.value;
    isDirty = true;
  }

  function handleAddTarget(blueprint) {
    if (!activePlan || !blueprint) return;

    // Check if already added
    const existing = activePlan.data.targets.find(t => t.blueprintId === blueprint.Id);
    if (existing) return;

    // Auto-name plan after first blueprint (if still default name)
    if (activePlan.data.targets.length === 0 && activePlan.name === 'New Plan') {
      // Use product name from blueprint (remove " Blueprint" suffix if present)
      const productName = blueprint.Name.replace(/ Blueprint$/, '');
      activePlan.name = productName;
    }

    activePlan.data.targets = [
      ...activePlan.data.targets,
      { blueprintId: blueprint.Id, quantity: 1 }
    ];
    isDirty = true;
  }

  function handleRemoveTarget(blueprintId) {
    if (!activePlan) return;
    activePlan.data.targets = activePlan.data.targets.filter(t => t.blueprintId !== blueprintId);
    isDirty = true;
  }

  function handleQuantityChange(blueprintId, quantity) {
    if (!activePlan) return;
    const target = activePlan.data.targets.find(t => t.blueprintId === blueprintId);
    if (target) {
      target.quantity = Math.max(1, parseInt(quantity) || 1);
      activePlan.data.targets = [...activePlan.data.targets];
      isDirty = true;
    }
  }

  function toggleOwnership(blueprintId) {
    const isOwned = globalOwnership[blueprintId] !== false;
    if (isOwned) {
      globalOwnership[blueprintId] = false;
    } else {
      delete globalOwnership[blueprintId];
    }
    globalOwnership = { ...globalOwnership };
    saveOwnership();
  }

  // Buy preference - separate from ownership
  // buyPreferences[blueprintId] = true means "prefer to buy even if owned"
  let buyPreferences = {};

  function toggleBuyPreference(blueprintId) {
    if (buyPreferences[blueprintId]) {
      delete buyPreferences[blueprintId];
    } else {
      buyPreferences[blueprintId] = true;
    }
    buyPreferences = { ...buyPreferences };
  }

  function isBuying(blueprintId) {
    // If not owned, always buying
    if (globalOwnership[blueprintId] === false) return true;
    // If owned, check buy preference
    return buyPreferences[blueprintId] === true;
  }

  function isOwned(blueprintId) {
    return globalOwnership[blueprintId] !== false;
  }

  // Check if a blueprint is a target (not toggleable from tree)
  function isTargetBlueprint(blueprintId) {
    return activePlan?.data?.targets?.some(t => t.blueprintId === blueprintId) || false;
  }

  async function saveOwnership() {
    if (isLoggedIn) {
      try {
        await fetch('/api/tools/construction/ownership', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(globalOwnership)
        });
      } catch (error) {
        console.error('Failed to save ownership:', error);
      }
    } else {
      saveLocalData();
    }
  }

  function setView(view) {
    currentView = view;
    if (browser) {
      try {
        localStorage.setItem(LOCAL_STORAGE_VIEW_KEY, view);
      } catch (e) {}
    }
  }

  // Configuration functions
  function setRollChance(value) {
    const parsed = parseInt(value, 10);
    if (!isNaN(parsed)) {
      rollChance = Math.max(0, Math.min(100, parsed));
    }
  }

  function setCertainty(value) {
    const parsed = parseInt(value, 10);
    if (!isNaN(parsed)) {
      certainty = Math.max(50, Math.min(99, parsed));
    }
  }

  function setNonFailChance(blueprintId, value) {
    const blueprint = blueprintCache.get(blueprintId);
    const maxNonFail = blueprint ? getMaxNonFailChance(blueprint) : MAX_NON_FAIL_SIB;
    const parsed = parseFloat(value);

    if (!isNaN(parsed)) {
      const clamped = Math.max(0, Math.min(maxNonFail, parsed));
      // Only store if different from max (to keep object small)
      if (clamped === maxNonFail) {
        delete nonFailChances[blueprintId];
      } else {
        nonFailChances[blueprintId] = clamped;
      }
      nonFailChances = { ...nonFailChances }; // Trigger reactivity
      markDirty();
    }
  }

  function getNonFailChance(blueprintId) {
    if (nonFailChances[blueprintId] !== undefined) {
      return nonFailChances[blueprintId];
    }
    const blueprint = blueprintCache.get(blueprintId);
    return blueprint ? getMaxNonFailChance(blueprint) : MAX_NON_FAIL_SIB;
  }

  function resetNonFailChances() {
    nonFailChances = {};
    markDirty();
  }

  function setConditionPercent(blueprintId, value) {
    conditionPercents = { ...conditionPercents, [blueprintId]: parseInt(value) };
    markDirty();
  }

  // Material crafting configuration functions
  function toggleMaterialCraft(materialName) {
    const current = materialCraftConfig[materialName] || {};
    if (current.craft === true) {
      // Disable crafting
      materialCraftConfig[materialName] = { ...current, craft: false };
    } else {
      // Enable crafting (default to non-L)
      materialCraftConfig[materialName] = { craft: true, preferLimited: false };
    }
    materialCraftConfig = { ...materialCraftConfig };
    markDirty();
  }

  function toggleMaterialLimited(materialName) {
    const current = materialCraftConfig[materialName] || {};
    if (current.craft !== true) return; // Only toggle if crafting is enabled

    materialCraftConfig[materialName] = {
      ...current,
      preferLimited: !current.preferLimited
    };
    materialCraftConfig = { ...materialCraftConfig };
    markDirty();
  }

  function selectMaterialBlueprint(materialName, blueprintId) {
    const current = materialCraftConfig[materialName] || {};
    materialCraftConfig[materialName] = {
      ...current,
      craft: true,
      selectedBlueprintId: blueprintId
    };
    materialCraftConfig = { ...materialCraftConfig };
    markDirty();
  }

  function isMaterialCraftEnabled(materialName) {
    return materialCraftConfig[materialName]?.craft === true;
  }

  function isMaterialLimited(materialName) {
    return materialCraftConfig[materialName]?.preferLimited === true;
  }

  function getSelectedBlueprintId(materialName) {
    return materialCraftConfig[materialName]?.selectedBlueprintId ?? null;
  }

  function getMaterialBlueprintOptions(materialName) {
    return getAllMaterialBlueprints(materialName, productToBlueprintMap);
  }

  function getMaterialCraftOptions(materialName) {
    return getMaterialCraftInfo(materialName, productToBlueprintMap);
  }

  // Export/Import functions
  function exportActivePlan() {
    if (!activePlan) return;
    const data = JSON.stringify(activePlan);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${activePlan.name || 'construction-plan'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function openImportDialog() {
    showImportSourceDialog = true;
  }

  function handleImportFromFile() {
    showImportSourceDialog = false;
    if (fileInput) fileInput.click();
  }

  async function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const imported = JSON.parse(text);

      // Validate structure
      if (!imported.name || !imported.data || !Array.isArray(imported.data.targets)) {
        throw new Error('Invalid plan format');
      }

      // Create new plan from imported data
      const newPlan = {
        id: crypto.randomUUID(),
        name: imported.name,
        data: imported.data,
        created_at: new Date().toISOString(),
        last_update: new Date().toISOString()
      };

      if (activeSource === 'online' && isLoggedIn) {
        const response = await fetch('/api/tools/construction/plans', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newPlan.name, data: newPlan.data })
        });

        if (response.ok) {
          const created = await response.json();
          onlinePlans = [created, ...onlinePlans];
          updatePlansList();
          selectPlan(created.id);
        }
      } else {
        localPlans = [newPlan, ...localPlans];
        saveLocalData();
        updatePlansList();
        selectPlan(newPlan.id);
      }
    } catch (error) {
      console.error('Failed to import plan:', error);
    }

    // Reset file input
    if (fileInput) fileInput.value = '';
  }
</script>

<svelte:head>
  <title>Entropia Nexus - Construction Calculator</title>
  <meta name="description" content="Plan and calculate crafting requirements for blueprints. Build crafting trees, generate shopping lists, and track blueprint ownership.">
</svelte:head>

<svelte:window bind:innerWidth={windowWidth} />

<WikiPage
  title="Construction Calculator"
  {breadcrumbs}
  entity={{ Name: 'Construction Calculator' }}
  basePath="/tools/construction"
  pageClass="tool-construction"
  navItems={[]}
  bind:drawerOpen
  {user}
  editable={false}
  canEdit={false}
>
  <div slot="header-actions" class="construction-header-actions">
    <div class="view-tabs">
      <button
        class:active={currentView === 'planning'}
        on:click={() => setView('planning')}
        title="Plan Setup"
      >Planning</button>
      <button
        class:active={currentView === 'steps'}
        on:click={() => setView('steps')}
        title="Step by Step"
      >Steps</button>
      <button
        class:active={currentView === 'tree'}
        on:click={() => setView('tree')}
        title="Tree View"
      >Tree</button>
      <button
        class:active={currentView === 'shopping'}
        on:click={() => setView('shopping')}
        title="Shopping List"
      >Shopping</button>
    </div>
    {#if activeSource === 'online'}
      <button
        class="action-btn save"
        class:dirty={isDirty}
        on:click={handleSavePlan}
        disabled={!activePlan || isSaving || !isDirty}
        aria-label={isSaving ? 'Saving...' : (isDirty ? 'Save plan' : 'Saved')}
        title={isSaving ? 'Saving...' : (isDirty ? 'Save' : 'Saved')}
      >
        <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
          <polyline points="17 21 17 13 7 13 7 21"/>
          <polyline points="7 3 7 8 15 8"/>
        </svg>
        <span class="action-label">{isSaving ? 'Saving...' : 'Save'}</span>
      </button>
    {:else}
      <button class="action-btn local" disabled title="Saved locally" aria-label="Saved locally">
        <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="2" y="4" width="20" height="16" rx="2"/>
          <path d="M6 8h.01M6 12h.01M6 16h.01"/>
        </svg>
        <span class="action-label">Local</span>
      </button>
    {/if}
    <button
      class="action-btn"
      class:active={showConfigPanel}
      on:click={() => showConfigPanel = !showConfigPanel}
      title="Calculator Settings"
    >
      <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
      <span class="action-label">Settings</span>
    </button>
    <button
      class="action-btn"
      on:click={() => showOwnershipPanel = !showOwnershipPanel}
      title="Blueprint Ownership"
    >
      <svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9 12l2 2 4-4"/>
        <rect x="3" y="3" width="18" height="18" rx="2"/>
      </svg>
      <span class="action-label">Ownership</span>
    </button>
  </div>

  <div slot="sidebar" let:isMobile>
    <div class="construction-sidebar" class:mobile={isMobile}>
      <div class="nav-header">
        <h2 class="nav-title">Construction Plans <span class="wip-badge">WIP</span></h2>
      </div>
      <div class="sidebar-body">
        <div class="sidebar-toggle">
          <button
            class:active={activeSource === 'online'}
            disabled={!isLoggedIn}
            title={!isLoggedIn ? 'Log in to use online plans' : 'Online plans'}
            on:click={() => switchSource('online')}
          >Online</button>
          <button
            class:active={activeSource === 'local'}
            on:click={() => switchSource('local')}
          >Local</button>
        </div>
        <div class="sidebar-search">
          <input type="text" placeholder="Search plans..." bind:value={planSearch} />
        </div>
        <div class="sidebar-actions">
          <button class="sidebar-btn create" on:click={handleNewPlan}>New</button>
          <button class="sidebar-btn danger" on:click={() => activePlan && confirmDeletePlan(activePlanId)} disabled={!activePlan}>Delete</button>
          <button class="sidebar-btn neutral" on:click={exportActivePlan} disabled={!activePlan}>Export</button>
          <button class="sidebar-btn neutral" on:click={openImportDialog}>Import</button>
        </div>
        <input type="file" bind:this={fileInput} on:change={handleFileChange} accept=".json" class="file-input-hidden" />
        {#if hasLocalData && isLoggedIn && activeSource === 'online' && showImportPrompt}
          <div class="import-prompt">
            <span>Import data from browser?</span>
            <div class="import-actions">
              <button class="sidebar-btn accent" on:click={handleImportFromLocal}>Import</button>
              <button class="sidebar-btn neutral" on:click={() => showImportPrompt = false}>Dismiss</button>
            </div>
          </div>
        {/if}
        {#if activeSource === 'online' && onlineLoading}
          <div class="sidebar-status">Loading plans...</div>
        {:else if activeSource === 'online' && onlineError}
          <div class="sidebar-status error">{onlineError}</div>
        {/if}
        <div class="sidebar-list">
          {#if filteredPlans.length === 0}
            <div class="sidebar-empty">No plans found.</div>
          {:else}
            {#each filteredPlans as plan}
              <button
                class="sidebar-item"
                class:active={activePlanId === plan.id}
                on:click={() => selectPlan(plan.id)}
              >
                <span class="item-name">{plan.name}</span>
              </button>
            {/each}
          {/if}
        </div>
      </div>
    </div>
  </div>

  <!-- Empty state when no plan selected -->
  {#if isMobileLayout && !activePlan}
    <div class="mobile-empty-state">
      <p>Create a new construction plan or select an existing one.</p>
      <div class="mobile-empty-actions">
        <button class="mobile-empty-btn create" on:click={handleNewPlan}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          New Plan
        </button>
        {#if plans.length > 0}
        <button class="mobile-empty-btn browse" on:click={() => drawerOpen = true}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          Browse Plans
        </button>
        {/if}
      </div>
    </div>
  {:else}
  <!-- Main Content -->
  <div class="construction-content">
    {#if blueprintsLoading}
      <div class="loading-state">
        <div class="spinner"></div>
        <p>Loading blueprints...</p>
      </div>
    {:else if !activePlan}
      <div class="empty-state">
        <p>Select or create a construction plan to get started.</p>
      </div>
    {:else}
      <!-- Planning View -->
      {#if currentView === 'planning'}
        <div class="plan-editor">
          <div class="plan-editor-header">
            <input
              type="text"
              class="plan-name-input"
              value={activePlan.name}
              on:input={handlePlanNameChange}
              placeholder="Plan name"
            />
          </div>

          <div class="targets-section">
            <div class="targets-header">
              <h3>Target Blueprints</h3>
              <div class="target-search">
                <WikiSearchInput
                  placeholder="Add blueprint..."
                  apiEndpoint="/search/items"
                  typeFilter="Blueprint"
                  limit={20}
                  clearOnSelect={true}
                  on:select={(e) => {
                    // Search returns Items.Id, but cache uses Blueprints.Id (offset by 6M)
                    const itemId = e.detail.data?.Id;
                    const blueprintId = itemId ? itemId - BLUEPRINT_ID_OFFSET : null;
                    handleAddTarget(blueprintCache.get(blueprintId));
                  }}
                />
              </div>
            </div>

            {#if activePlan.data.targets.length === 0}
              <div class="targets-empty">
                <p>No target blueprints yet. Search and add blueprints above.</p>
              </div>
            {:else}
              <div class="targets-list">
                {#each activePlan.data.targets as target}
                  {@const blueprint = blueprintCache.get(target.blueprintId)}
                  {#if blueprint}
                    {@const costs = getBlueprintCostPerClick(blueprint, markupValues)}
                    {@const treeRoot = craftingTree.find(r => r.blueprint.Id === target.blueprintId)}
                    {@const totalTime = treeRoot ? getNodeTotalTime(treeRoot) : 0}
                    <div class="target-item-expanded">
                      <div class="target-item-header">
                        <a href={getBlueprintLink(blueprint)} class="target-name" title={blueprint.Name}>
                          {blueprint.Name}
                        </a>
                        <div class="target-controls">
                          <input
                            type="number"
                            class="target-quantity"
                            min="1"
                            value={target.quantity}
                            on:input={(e) => handleQuantityChange(target.blueprintId, e.target.value)}
                          />
                          <button
                            class="btn-remove"
                            on:click={() => handleRemoveTarget(target.blueprintId)}
                            title="Remove"
                          >×</button>
                        </div>
                      </div>
                      <div class="target-cost-info">
                        <span class="cost-label">Cost/click:</span>
                        <span class="cost-tt">{clampDecimals(costs.ttCost, 2, 4)} TT</span>
                        <span class="cost-mu">{clampDecimals(costs.muCost, 2, 4)} PED</span>
                        {#if totalTime > 0}
                          <span class="cost-time">{formatCraftTime(totalTime)}</span>
                        {/if}
                      </div>
                    </div>
                  {/if}
                {/each}
              </div>
            {/if}
          </div>

          <!-- Markup Section -->
          {#if allMaterialsForMarkup.length > 0 || limitedBlueprintsForMarkup.length > 0 || productsToBuyForMarkup.length > 0 || needsResidue}
            <div class="markup-section">
              <h3>Markup Settings</h3>
              <p class="markup-info">Set markup % for materials, residue, products, and limited blueprints that need to be purchased.</p>

              {#if allMaterialsForMarkup.length > 0 || needsResidue}
                <div class="markup-group">
                  <h4>Materials</h4>
                  <div class="markup-grid">
                    {#each allMaterialsForMarkup as { name, item }}
                      {@const markupKey = `mat:${name}`}
                      {@const isCustom = markupValues[markupKey] != null}
                      {@const wap = shoppingItemWapMap[markupKey] ?? null}
                      <div class="markup-item">
                        <a href={getItemLink(item)} class="markup-name">{name}</a>
                        <div class="markup-input-wrapper">
                          <input
                            type="number"
                            class="markup-input"
                            class:is-custom={isCustom}
                            value={markupValues[markupKey] ?? shoppingItemWapMap[markupKey] ?? DEFAULT_MARKUP}
                            on:change={(e) => setMarkup(markupKey, e.target.value)}
                            min="0"
                            step="1"
                          />
                          <span class="markup-suffix">%</span>
                          {#if isCustom}
                            <button class="markup-reset" title="Reset to market value" on:click={() => resetMarkup(markupKey)}>&times;</button>
                          {:else if wap != null}
                            <span class="markup-wap-badge" title="Weighted Average Price from exchange">WAP</span>
                          {/if}
                        </div>
                      </div>
                    {/each}
                    {#if needsResidue}
                      <div class="markup-item residue-markup">
                        <span class="markup-name residue-name">Residue</span>
                        <div class="markup-input-wrapper">
                          <input
                            type="number"
                            class="markup-input"
                            value={markupValues['residue'] ?? DEFAULT_MARKUP}
                            on:change={(e) => setMarkup('residue', e.target.value)}
                            min="0"
                            step="1"
                          />
                          <span class="markup-suffix">%</span>
                        </div>
                      </div>
                    {/if}
                  </div>
                </div>
              {/if}

              {#if limitedBlueprintsForMarkup.length > 0}
                <div class="markup-group">
                  <h4>Limited Blueprints</h4>
                  <div class="markup-grid">
                    {#each limitedBlueprintsForMarkup as bp}
                      {@const markupKey = `bp:${bp.Id}`}
                      {@const isCustom = markupValues[markupKey] != null}
                      {@const wap = shoppingItemWapMap[markupKey] ?? null}
                      <div class="markup-item">
                        <a href={getBlueprintLink(bp)} class="markup-name">{bp.Name}</a>
                        <div class="markup-input-wrapper">
                          <input
                            type="number"
                            class="markup-input"
                            class:is-custom={isCustom}
                            value={markupValues[markupKey] ?? shoppingItemWapMap[markupKey] ?? DEFAULT_MARKUP}
                            on:change={(e) => setMarkup(markupKey, e.target.value)}
                            min="0"
                            step="1"
                          />
                          <span class="markup-suffix">%</span>
                          {#if isCustom}
                            <button class="markup-reset" title="Reset to market value" on:click={() => resetMarkup(markupKey)}>&times;</button>
                          {:else if wap != null}
                            <span class="markup-wap-badge" title="Weighted Average Price from exchange">WAP</span>
                          {/if}
                        </div>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}

              {#if productsToBuyForMarkup.length > 0}
                <div class="markup-group">
                  <h4>Products to Buy</h4>
                  <div class="markup-grid">
                    {#each productsToBuyForMarkup as { name, item }}
                      {@const markupKey = `prod:${name}`}
                      {@const isCustom = markupValues[markupKey] != null}
                      {@const wap = shoppingItemWapMap[markupKey] ?? null}
                      <div class="markup-item">
                        <a href={getItemLink(item)} class="markup-name">{name}</a>
                        <div class="markup-input-wrapper">
                          <input
                            type="number"
                            class="markup-input"
                            class:is-custom={isCustom}
                            value={markupValues[markupKey] ?? shoppingItemWapMap[markupKey] ?? DEFAULT_MARKUP}
                            on:change={(e) => setMarkup(markupKey, e.target.value)}
                            min="0"
                            step="1"
                          />
                          <span class="markup-suffix">%</span>
                          {#if isCustom}
                            <button class="markup-reset" title="Reset to market value" on:click={() => resetMarkup(markupKey)}>&times;</button>
                          {:else if wap != null}
                            <span class="markup-wap-badge" title="Weighted Average Price from exchange">WAP</span>
                          {/if}
                        </div>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {:else if activePlan.data.targets.length === 0}
        <div class="empty-state">
          <p>Add target blueprints in the Planning view to see results here.</p>
          <button class="btn-switch-view" on:click={() => setView('planning')}>Go to Planning</button>
        </div>
      {:else if currentView === 'steps'}
        <div class="steps-view">
          <div class="steps-header">
            <h2>Step by Step</h2>
            {#if craftingSteps.length > 0}
              <div class="global-condition-controls">
                <div class="global-condition-presets">
                  <button
                    class="global-condition-preset"
                    on:click={() => applyGlobalCondition('stability')}
                    title="Set all steps to 0% condition — highest success rate"
                  >Stability</button>
                  <button
                    class="global-condition-preset"
                    on:click={() => applyGlobalCondition('attempts')}
                    title="Set each step to its optimal condition for fewest attempts"
                  >Attempts</button>
                  <button
                    class="global-condition-preset"
                    disabled={!anyStepSupportsOutput}
                    on:click={() => applyGlobalCondition('output')}
                    title={anyStepSupportsOutput ? 'Set each step to its optimal condition for best output per attempt' : 'No steps benefit from output optimization (all produce single items)'}
                  >Output</button>
                </div>
                <button
                  class="condition-info-btn"
                  on:click={() => showConditionInfoDialog = true}
                  title="What is condition?"
                >?</button>
              </div>
            {/if}
          </div>
          {#if craftingSteps.length === 0}
            <p class="empty">No construction steps needed.</p>
          {:else}
            <ol class="steps-list">
              {#each craftingSteps as step, i}
                {@const totalCost = getStepTotalCost(step)}
                {@const costPerClick = getCostPerClick(step)}
                {@const isChecked = checkedSteps.has(i)}
                {@const isCollapsed = collapsedSteps.has(i)}
                <li class="step-item" class:not-owned={!step.owned} class:checked={isChecked} class:collapsed={isCollapsed}>
                  <div class="step-header" on:click={() => toggleStepCollapsed(i)} role="button" tabindex="0" on:keypress={(e) => e.key === 'Enter' && toggleStepCollapsed(i)}>
                    <label class="step-checkbox" on:click|stopPropagation>
                      <input type="checkbox" checked={isChecked} on:change={() => toggleStepChecked(i)} />
                    </label>
                    <span class="step-number">{i + 1}</span>
                    <span class="step-title">
                      {#if step.isMaterialChild}
                        <span class="step-type-badge material">Material</span>
                      {/if}
                      <a href={getBlueprintLink(step.blueprint)} class="step-blueprint" on:click|stopPropagation>
                        {step.blueprint.Name}
                      </a>
                      {#if step.isSiB}<span class="sib-badge">SiB</span>{/if}
                    </span>
                    <span class="step-toggle">{isCollapsed ? '▶' : '▼'}</span>
                  </div>
                  {#if !isCollapsed}
                    <div class="step-details">
                      {#if step.owned}
                        <p class="step-action">
                          Craft until you have <strong>{step.quantityWanted}</strong>
                          <a href={getItemLink(step.blueprint.Product)}>{step.blueprint.Product?.Name || 'result'}</a>
                          <span class="step-rates-inline">
                            (~{step.estimatedAttempts} attempts, {formatCraftTime(step.estimatedAttempts * SECONDS_PER_ATTEMPT)} @ {certainty}% confidence,
                            <span class="rate-success" title="Success: produces items">{(step.successRate * 100).toFixed(1)}%</span> success,
                            <span class="rate-near" title="Near-success: refund only">{(step.nearSuccessRate * 100).toFixed(1)}%</span> near,
                            <span class="rate-fail" title="Fail: no output">{(step.failRate * 100).toFixed(1)}%</span> fail,
                            avg {step.avgOutput.toFixed(1)}/success)
                          </span>
                        </p>

                        {@const optAttempts = findOptimalCondition(step.blueprint, step.quantityWanted, nonFailChances[step.blueprint.Id], certainty)}
                        {@const optOutput = findOptimalOutputCondition(step.blueprint, nonFailChances[step.blueprint.Id], certainty)}
                        <div class="condition-slider">
                          <label class="condition-label">
                            <span>Condition</span>
                            <input
                              type="range"
                              min={CONDITION_MIN}
                              max={CONDITION_MAX}
                              step="1"
                              value={step.conditionPercent}
                              on:input={(e) => setConditionPercent(step.blueprint.Id, e.target.value)}
                            />
                            <span class="condition-value">{step.conditionPercent}%{#if step.conditionPercent > 0} ({step.conditionMultiplier.toFixed(2)}x){/if}</span>
                          </label>
                          <div class="condition-presets">
                            <button
                              class="condition-preset"
                              class:active={step.conditionPercent === 0}
                              on:click={() => setConditionPercent(step.blueprint.Id, 0)}
                              title="0% condition — highest success rate, lowest output per success"
                            >Stability</button>
                            <button
                              class="condition-preset"
                              class:active={step.conditionPercent === optAttempts}
                              on:click={() => setConditionPercent(step.blueprint.Id, optAttempts)}
                              title="{optAttempts}% condition — fewest craft attempts needed"
                            >Attempts ({optAttempts}%)</button>
                            <button
                              class="condition-preset"
                              class:active={step.conditionPercent === optOutput}
                              on:click={() => setConditionPercent(step.blueprint.Id, optOutput)}
                              title="{optOutput}% condition — best output per attempt ratio"
                            >Output ({optOutput}%)</button>
                          </div>
                        </div>

                        {#if step.materials.length > 0 || step.adjustedResidue > 0}
                          {@const residueMU = markupValues['residue'] ?? DEFAULT_MARKUP}
                          {@const adjustedResidueCost = (step.adjustedResidue || 0) * residueMU / 100}
                          {@const adjustedTotalCost = step.materials.reduce((sum, mat) => {
                            // Skip materials being crafted - they have their own cost
                            if (craftedProductNames.has(mat.item?.Name)) return sum;
                            const matTT = mat.item?.Properties?.Economy?.MaxTT || 0;
                            const key = `mat:${mat.item?.Name}`;
                            const mu = markupValues[key] ?? shoppingItemWapMap[key] ?? DEFAULT_MARKUP;
                            return sum + (matTT * (mat.adjustedAmount || mat.totalAmount) * mu / 100);
                          }, 0) + adjustedResidueCost}
                          {@const costPerClick = step.materials.reduce((sum, mat) => {
                            if (craftedProductNames.has(mat.item?.Name)) return sum;
                            const matTT = mat.item?.Properties?.Economy?.MaxTT || 0;
                            const key = `mat:${mat.item?.Name}`;
                            const mu = markupValues[key] ?? shoppingItemWapMap[key] ?? DEFAULT_MARKUP;
                            return sum + (matTT * mat.amountPerAttempt * mu / 100);
                          }, 0) + (step.residuePerClick || 0) * residueMU / 100}
                          <div class="step-materials-table">
                            <table class="materials-table">
                              <thead>
                                <tr>
                                  <th>Material</th>
                                  <th class="text-right">Per Click</th>
                                  <th class="text-right">Est. Total</th>
                                  <th class="text-right">Exp. Refund</th>
                                  <th class="text-right">MU%</th>
                                  <th class="text-right">Cost</th>
                                </tr>
                              </thead>
                              <tbody>
                                {#each step.materials as mat}
                                  {@const matTT = (mat.item?.Properties?.Economy?.MaxTT || 0)}
                                  {@const adjustedAmount = mat.adjustedAmount || mat.totalAmount}
                                  {@const expectedRefund = mat.totalAmount - adjustedAmount}
                                  {@const refundPct = mat.totalAmount > 0 ? (expectedRefund / mat.totalAmount * 100) : 0}
                                  {@const lineTT = matTT * adjustedAmount}
                                  {@const stepMatKey = `mat:${mat.item?.Name}`}
                                  {@const mu = markupValues[stepMatKey] ?? shoppingItemWapMap[stepMatKey] ?? DEFAULT_MARKUP}
                                  {@const lineCost = lineTT * mu / 100}
                                  {@const isCrafting = craftedProductNames.has(mat.item?.Name)}
                                  {@const bpOptions = mat.hasCraftableBlueprint ? getMaterialBlueprintOptions(mat.item?.Name) : null}
                                  {@const hasMultipleBPs = bpOptions && bpOptions.length > 1}
                                  <tr class:crafting-material={isCrafting}>
                                    <td>
                                      <a href={getItemLink(mat.item)}>{mat.item.Name}</a>
                                      {#if hasMultipleBPs}
                                        {@const selectedId = getSelectedBlueprintId(mat.item?.Name) ?? bpOptions[0]?.Id}
                                        {@const selectedBp = bpOptions.find(bp => bp.Id === selectedId) || bpOptions[0]}
                                        <button
                                          class="mat-bp-badge"
                                          class:active={bpPickerMaterial === mat.item?.Name}
                                          title="Using: {selectedBp?.Name} — Click to change"
                                          on:click|stopPropagation={(e) => openBpPicker(mat.item?.Name, e)}
                                        >
                                          {bpOptions.length} BPs
                                        </button>
                                      {/if}
                                    </td>
                                    <td class="text-right">{mat.amountPerAttempt}</td>
                                    <td class="text-right">{adjustedAmount}</td>
                                    <td class="text-right refund-cell" title="Expected refund: {expectedRefund} units ({clampDecimals(refundPct, 0, 1)}%)">
                                      {expectedRefund > 0 ? `-${expectedRefund}` : '0'} <span class="refund-pct">({clampDecimals(refundPct, 0, 1)}%)</span>
                                    </td>
                                    <td class="text-right">{#if isCrafting}—{:else}<span class="markup-cell"><input type="number" class="markup-input-inline" class:is-custom={markupValues[stepMatKey] != null} value={mu} min="0" step="1" on:change={(e) => setMarkup(stepMatKey, e.target.value)} />%{#if markupValues[stepMatKey] != null}<button class="markup-reset" title="Reset to market value" on:click={() => resetMarkup(stepMatKey)}>&times;</button>{:else if shoppingItemWapMap[stepMatKey] != null}<span class="markup-wap-badge" title="WAP">WAP</span>{/if}</span>{/if}</td>
                                    <td class="text-right">{isCrafting ? '—' : `${clampDecimals(lineCost, 2, 4)} PED`}</td>
                                  </tr>
                                {/each}
                                {#if step.adjustedResidue > 0}
                                  {@const residueRefund = step.totalResidue - step.adjustedResidue}
                                  {@const residueRefundPct = step.totalResidue > 0 ? (residueRefund / step.totalResidue * 100) : 0}
                                  <tr class="residue-row">
                                    <td><span class="residue-name">Residue</span> <span class="residue-note">(est.)</span></td>
                                    <td class="text-right">{clampDecimals(step.residuePerClick, 2, 4)}</td>
                                    <td class="text-right">{clampDecimals(step.adjustedResidue, 2, 4)}</td>
                                    <td class="text-right refund-cell">
                                      {residueRefund > 0 ? `-${clampDecimals(residueRefund, 2)}` : '0'} <span class="refund-pct">({clampDecimals(residueRefundPct, 0, 1)}%)</span>
                                    </td>
                                    <td class="text-right"><input type="number" class="markup-input-inline" value={residueMU} min="0" step="1" on:change={(e) => setMarkup('residue', e.target.value)} />%</td>
                                    <td class="text-right">{clampDecimals(adjustedResidueCost, 2, 4)} PED</td>
                                  </tr>
                                {/if}
                              </tbody>
                              <tfoot>
                                <tr>
                                  <td colspan="4"><strong>Est. Totals</strong></td>
                                  <td class="text-right"></td>
                                  <td class="text-right"><strong>{clampDecimals(adjustedTotalCost, 2, 4)} PED</strong></td>
                                </tr>
                                <tr>
                                  <td colspan="4"><strong>Cost per click</strong></td>
                                  <td class="text-right"></td>
                                  <td class="text-right"><strong>{clampDecimals(costPerClick, 2, 4)} PED</strong></td>
                                </tr>
                              </tfoot>
                            </table>
                          </div>
                        {/if}
                      {:else}
                        {@const product = step.blueprint.Product}
                        {@const productName = product?.Name || step.blueprint.Name}
                        {@const productUnitTT = product?.Properties?.Economy?.MaxTT || 0}
                        {@const productTotalTT = productUnitTT * step.quantityWanted}
                        {@const stepProdKey = `prod:${productName}`}
                        {@const productMU = markupValues[stepProdKey] ?? shoppingItemWapMap[stepProdKey] ?? DEFAULT_MARKUP}
                        {@const productCost = productTotalTT * productMU / 100}
                        <p class="step-action buy">
                          Buy <strong>{step.quantityWanted}</strong>
                          <a href={getItemLink(product)}>{productName}</a>
                          <span class="step-reason-inline">({isOwned(step.blueprint.Id) ? 'Set to buy' : 'Blueprint not owned'})</span>
                        </p>
                        {#if productUnitTT > 0}
                          <div class="step-materials-table">
                            <table class="materials-table">
                              <thead>
                                <tr>
                                  <th>Product</th>
                                  <th class="text-right">Qty</th>
                                  <th class="text-right">TT</th>
                                  <th class="text-right">MU%</th>
                                  <th class="text-right">Cost</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr>
                                  <td><a href={getItemLink(product)}>{productName}</a></td>
                                  <td class="text-right">{step.quantityWanted}</td>
                                  <td class="text-right">{clampDecimals(productTotalTT, 2, 4)} PED</td>
                                  <td class="text-right"><span class="markup-cell"><input type="number" class="markup-input-inline" class:is-custom={markupValues[stepProdKey] != null} value={productMU} min="0" step="1" on:change={(e) => setMarkup(stepProdKey, e.target.value)} />%{#if markupValues[stepProdKey] != null}<button class="markup-reset" title="Reset to market value" on:click={() => resetMarkup(stepProdKey)}>&times;</button>{:else if shoppingItemWapMap[stepProdKey] != null}<span class="markup-wap-badge" title="WAP">WAP</span>{/if}</span></td>
                                  <td class="text-right">{clampDecimals(productCost, 2, 4)} PED</td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        {/if}
                      {/if}
                    </div>
                  {/if}
                </li>
              {/each}
            </ol>
          {/if}
        </div>
      {:else if currentView === 'tree'}
        <div class="tree-view">
          <h2>Construction Tree</h2>
          <p class="tree-info">Use "Own/Don't Own" to toggle ownership. Use "Buy/Craft" to choose how to obtain items you own. For materials with craftable blueprints, click "Craft" to expand the tree.</p>
          {#if craftingTree.length === 0}
            <p class="empty">No construction tree to display.</p>
          {:else}
            <ul class="tree-root">
              {#each craftingTree as node (node.blueprint.Id)}
                <CraftingTreeNode
                  {node}
                  depth={0}
                  isTarget={true}
                  {getBlueprintLink}
                  {isTargetBlueprint}
                  {isOwned}
                  {isBuying}
                  {toggleBuyPreference}
                  {toggleOwnership}
                  {setNonFailChance}
                  {getNonFailChance}
                  {getMaterialBlueprintOptions}
                  {getSelectedBlueprintId}
                  {selectMaterialBlueprint}
                  {getNodeTotalTime}
                  {formatCraftTime}
                />
              {/each}
            </ul>
          {/if}
        </div>
      {:else if currentView === 'shopping'}
        <div class="shopping-view">
          <div class="shopping-header">
            <h2>Shopping List</h2>
            {#if isLoggedIn}
              <button class="btn-order-all" on:click={openMassBuyAll} disabled={allShoppingItemsChecked}>
                Order All
              </button>
            {/if}
          </div>
          <p class="shopping-list-info">Estimated amounts at {certainty}% confidence, accounting for {rollChance}% material roll chance.</p>

          {#if shoppingList.materials.length === 0 && shoppingList.productsToBuy.length === 0 && (!shoppingList.limitedBlueprints || shoppingList.limitedBlueprints.length === 0) && (!shoppingList.adjustedTotalResidue || shoppingList.adjustedTotalResidue === 0)}
            <p class="empty">No items needed.</p>
          {:else}
            {@const adjustedMaterialsTotalMU = shoppingList.materials.reduce((sum, item) => {
              const key = `mat:${item.item?.Name}`;
              const mu = markupValues[key] ?? shoppingItemWapMap[key] ?? DEFAULT_MARKUP;
              return sum + ((item.adjustedTTValue || item.ttValue) * mu / 100);
            }, 0)}
            {@const residueMU = markupValues['residue'] ?? DEFAULT_MARKUP}
            {@const adjustedResidueCost = (shoppingList.adjustedTotalResidue || 0) * residueMU / 100}
            {@const limitedBpTotalMU = (shoppingList.limitedBlueprints || []).reduce((sum, item) => {
              const key = `bp:${item.blueprint.Id}`;
              const mu = markupValues[key] ?? shoppingItemWapMap[key] ?? DEFAULT_MARKUP;
              return sum + ((item.ttValue || 0) * mu / 100);
            }, 0)}
            {@const productsTotalTT = (shoppingList.productsToBuy || []).reduce((sum, item) => sum + (item.ttValue || 0), 0)}
            {@const productsTotalMU = (shoppingList.productsToBuy || []).reduce((sum, item) => {
              const key = `prod:${item.item?.Name}`;
              const mu = markupValues[key] ?? shoppingItemWapMap[key] ?? DEFAULT_MARKUP;
              return sum + ((item.ttValue || 0) * mu / 100);
            }, 0)}
            {@const grandTotalTT = (shoppingList.adjustedTotalTT || shoppingList.totalTT) + (shoppingList.adjustedTotalResidue || 0) + (shoppingList.limitedBlueprints || []).reduce((sum, item) => sum + (item.ttValue || 0), 0) + productsTotalTT}
            {@const grandTotalMU = adjustedMaterialsTotalMU + adjustedResidueCost + limitedBpTotalMU + productsTotalMU}
            <table class="shopping-table unified">
              <thead>
                <tr>
                  <th class="col-check"></th>
                  <th>Type</th>
                  <th>Item</th>
                  <th class="text-right">Est. TT</th>
                  <th class="text-right">MU%</th>
                  <th class="text-right">Cost</th>
                  <th class="col-actions hide-mobile"></th>
                </tr>
              </thead>
              <tbody>
                <!-- Materials -->
                {#each shoppingList.materials as item}
                  {@const isChecked = checkedShoppingMaterials.has(item.item.Name)}
                  {@const markupKey = `mat:${item.item?.Name}`}
                  {@const mu = markupValues[markupKey] ?? shoppingItemWapMap[markupKey] ?? DEFAULT_MARKUP}
                  {@const isCustomMU = markupValues[markupKey] != null}
                  {@const wapMU = shoppingItemWapMap[markupKey] ?? null}
                  {@const adjustedTT = item.adjustedTTValue || item.ttValue}
                  {@const cost = adjustedTT * mu / 100}
                  <tr class:checked={isChecked}>
                    <td class="col-check">
                      <input type="checkbox" checked={isChecked} on:change={() => toggleShoppingMaterial(item.item.Name)} />
                    </td>
                    <td><span class="type-badge material">Material</span></td>
                    <td>{item.adjustedAmount || item.totalAmount} x <a href={getItemLink(item.item)}>{item.item.Name}</a></td>
                    <td class="text-right">{clampDecimals(adjustedTT, 2, 4)} PED</td>
                    <td class="text-right markup-cell">
                      <input
                        type="number"
                        class="markup-input-inline"
                        class:is-custom={isCustomMU}
                        value={mu}
                        min="0"
                        step="1"
                        on:change={(e) => setMarkup(markupKey, e.target.value)}
                      />%
                      {#if isCustomMU}<button class="markup-reset" title="Reset to market value" on:click={() => resetMarkup(markupKey)}>&times;</button>{:else if wapMU != null}<span class="markup-wap-badge" title="WAP">WAP</span>{/if}
                    </td>
                    <td class="text-right">{clampDecimals(cost, 2, 4)} PED</td>
                    <td class="col-actions hide-mobile">
                      {#if item.item?.Id}
                        <div class="shopping-actions">
                          {#if isLoggedIn}
                            <button class="btn-shop-action btn-order" title="Create buy order" on:click={() => openMassBuy([{ itemId: item.item.Id, name: item.item.Name, quantity: Math.ceil(item.adjustedAmount || item.totalAmount), markup: mu }])}>Order</button>
                          {/if}
                          <a href="/market/exchange/listings/{item.item.Id}" target="_blank" rel="noopener" class="btn-shop-action btn-buy" class:no-orders={!exchangeSellCounts.get(item.item.Id)} title="{exchangeSellCounts.get(item.item.Id) || 0} sell order{(exchangeSellCounts.get(item.item.Id) || 0) !== 1 ? 's' : ''} available">Buy{#if exchangeSellCounts.get(item.item.Id)} ({exchangeSellCounts.get(item.item.Id)}){/if}</a>
                        </div>
                      {/if}
                    </td>
                  </tr>
                {/each}
                <!-- Residue -->
                {#if shoppingList.adjustedTotalResidue && shoppingList.adjustedTotalResidue > 0}
                  {@const isResidueChecked = checkedShoppingMaterials.has('Residue')}
                  <tr class="residue-row" class:checked={isResidueChecked}>
                    <td class="col-check">
                      <input type="checkbox" checked={isResidueChecked} on:change={() => toggleShoppingMaterial('Residue')} />
                    </td>
                    <td><span class="type-badge material">Material</span></td>
                    <td><span class="residue-name">Residue</span> <span class="residue-note">(est.)</span></td>
                    <td class="text-right">{clampDecimals(shoppingList.adjustedTotalResidue, 2, 4)} PED</td>
                    <td class="text-right">
                      <input
                        type="number"
                        class="markup-input-inline"
                        value={residueMU}
                        min="0"
                        step="1"
                        on:change={(e) => setMarkup('residue', e.target.value)}
                      />%
                    </td>
                    <td class="text-right">{clampDecimals(adjustedResidueCost, 2, 4)} PED</td>
                    <td class="col-actions hide-mobile"></td>
                  </tr>
                {/if}
                <!-- Limited Blueprints -->
                {#each shoppingList.limitedBlueprints || [] as item}
                  {@const isChecked = checkedShoppingProducts.has(item.blueprint.Name)}
                  {@const bpMarkupKey = `bp:${item.blueprint.Id}`}
                  {@const mu = markupValues[bpMarkupKey] ?? shoppingItemWapMap[bpMarkupKey] ?? DEFAULT_MARKUP}
                  {@const isCustomMU = markupValues[bpMarkupKey] != null}
                  {@const wapMU = shoppingItemWapMap[bpMarkupKey] ?? null}
                  {@const ttValue = item.ttValue || 0}
                  {@const cost = ttValue * mu / 100}
                  <tr class:checked={isChecked}>
                    <td class="col-check">
                      <input type="checkbox" checked={isChecked} on:change={() => toggleShoppingProduct(item.blueprint.Name)} />
                    </td>
                    <td><span class="type-badge limited">BP (L)</span></td>
                    <td>
                      {item.totalAmount} x <a href={getBlueprintLink(item.blueprint)}>{item.blueprint.Name}</a>
                      <span class="shopping-note">(est. attempts needed)</span>
                    </td>
                    <td class="text-right">{clampDecimals(ttValue, 2, 4)} PED</td>
                    <td class="text-right markup-cell">
                      <input
                        type="number"
                        class="markup-input-inline"
                        class:is-custom={isCustomMU}
                        value={mu}
                        min="0"
                        step="1"
                        on:change={(e) => setMarkup(bpMarkupKey, e.target.value)}
                      />%
                      {#if isCustomMU}<button class="markup-reset" title="Reset to market value" on:click={() => resetMarkup(bpMarkupKey)}>&times;</button>{:else if wapMU != null}<span class="markup-wap-badge" title="WAP">WAP</span>{/if}
                    </td>
                    <td class="text-right">{clampDecimals(cost, 2, 4)} PED</td>
                    <td class="col-actions hide-mobile">
                      <div class="shopping-actions">
                        {#if isLoggedIn}
                          <button class="btn-shop-action btn-order" title="Create buy order" on:click={() => openMassBuy([{ itemId: item.blueprint.Id + BLUEPRINT_ID_OFFSET, name: item.blueprint.Name, quantity: Math.ceil(item.totalAmount), markup: mu }])}>Order</button>
                        {/if}
                        <a href="/market/exchange/listings/{item.blueprint.Id + BLUEPRINT_ID_OFFSET}" target="_blank" rel="noopener" class="btn-shop-action btn-buy" class:no-orders={!exchangeSellCounts.get(item.blueprint.Id + BLUEPRINT_ID_OFFSET)} title="{exchangeSellCounts.get(item.blueprint.Id + BLUEPRINT_ID_OFFSET) || 0} sell order{(exchangeSellCounts.get(item.blueprint.Id + BLUEPRINT_ID_OFFSET) || 0) !== 1 ? 's' : ''} available">Buy{#if exchangeSellCounts.get(item.blueprint.Id + BLUEPRINT_ID_OFFSET)} ({exchangeSellCounts.get(item.blueprint.Id + BLUEPRINT_ID_OFFSET)}){/if}</a>
                      </div>
                    </td>
                  </tr>
                {/each}
                <!-- Products to Buy (from unowned BPs) -->
                {#each shoppingList.productsToBuy as item}
                  {@const isChecked = checkedShoppingProducts.has(item.item.Name)}
                  {@const prodMarkupKey = `prod:${item.item?.Name}`}
                  {@const prodMU = markupValues[prodMarkupKey] ?? shoppingItemWapMap[prodMarkupKey] ?? DEFAULT_MARKUP}
                  {@const isCustomProdMU = markupValues[prodMarkupKey] != null}
                  {@const wapProdMU = shoppingItemWapMap[prodMarkupKey] ?? null}
                  {@const prodTT = item.ttValue || 0}
                  {@const prodCost = prodTT * prodMU / 100}
                  <tr class="product-row" class:checked={isChecked}>
                    <td class="col-check">
                      <input type="checkbox" checked={isChecked} on:change={() => toggleShoppingProduct(item.item.Name)} />
                    </td>
                    <td><span class="type-badge product">Product</span></td>
                    <td>
                      {item.totalAmount} x <a href={getItemLink(item.item)}>{item.item.Name}</a>
                      <span class="shopping-note muted">(from {item.blueprintName})</span>
                    </td>
                    <td class="text-right">{clampDecimals(prodTT, 2, 4)} PED</td>
                    <td class="text-right markup-cell">
                      <input
                        type="number"
                        class="markup-input-inline"
                        class:is-custom={isCustomProdMU}
                        value={prodMU}
                        min="0"
                        step="1"
                        on:change={(e) => setMarkup(prodMarkupKey, e.target.value)}
                      />%
                      {#if isCustomProdMU}<button class="markup-reset" title="Reset to market value" on:click={() => resetMarkup(prodMarkupKey)}>&times;</button>{:else if wapProdMU != null}<span class="markup-wap-badge" title="WAP">WAP</span>{/if}
                    </td>
                    <td class="text-right">{clampDecimals(prodCost, 2, 4)} PED</td>
                    <td class="col-actions hide-mobile">
                      {#if item.item?.Id}
                        <div class="shopping-actions">
                          {#if isLoggedIn}
                            <button class="btn-shop-action btn-order" title="Create buy order" on:click={() => openMassBuy([{ itemId: item.item.Id, name: item.item.Name, quantity: Math.ceil(item.totalAmount), markup: prodMU }])}>Order</button>
                          {/if}
                          <a href="/market/exchange/listings/{item.item.Id}" target="_blank" rel="noopener" class="btn-shop-action btn-buy" class:no-orders={!exchangeSellCounts.get(item.item.Id)} title="{exchangeSellCounts.get(item.item.Id) || 0} sell order{(exchangeSellCounts.get(item.item.Id) || 0) !== 1 ? 's' : ''} available">Buy{#if exchangeSellCounts.get(item.item.Id)} ({exchangeSellCounts.get(item.item.Id)}){/if}</a>
                        </div>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
              <tfoot>
                <tr>
                  <td></td>
                  <td></td>
                  <td><strong>Est. Totals</strong></td>
                  <td class="text-right"><strong>{clampDecimals(grandTotalTT, 2, 4)} PED</strong></td>
                  <td></td>
                  <td class="text-right"><strong>{clampDecimals(grandTotalMU, 2, 4)} PED</strong></td>
                  <td class="col-actions hide-mobile"></td>
                </tr>
              </tfoot>
            </table>
          {/if}
        </div>
      {/if}
    {/if}
  </div>
  {/if}
</WikiPage>

<!-- Modals: wrapped in .tool-construction for CSS scoping -->
<div class="tool-construction">
{#if bpPickerMaterial}
  {@const bpOptions = getMaterialBlueprintOptions(bpPickerMaterial)}
  {@const selectedId = getSelectedBlueprintId(bpPickerMaterial) ?? bpOptions?.[0]?.Id}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="bp-picker-backdrop" on:click={closeBpPicker}></div>
  <div class="bp-picker-popover" style="top: {bpPickerPos.top}px; left: {bpPickerPos.left}px;">
    <div class="bp-picker-header">Select Blueprint</div>
    {#each bpOptions || [] as bp}
      <button
        class="bp-picker-option"
        class:selected={bp.Id === selectedId}
        on:click|stopPropagation={() => selectBpFromPicker(bpPickerMaterial, bp.Id)}
      >
        <span class="bp-picker-radio">{bp.Id === selectedId ? '●' : '○'}</span>
        <span class="bp-picker-name">{bp.Name}</span>
        {#if isLimitedBlueprint(bp)}<span class="limited-badge">(L)</span>{/if}
      </button>
    {/each}
  </div>
{/if}
<!-- Ownership Panel Modal -->
{#if showConfigPanel}
  <div class="ownership-overlay" on:click={() => showConfigPanel = false} on:keydown={(e) => e.key === 'Escape' && (showConfigPanel = false)}>
    <div class="ownership-panel config-panel" on:click|stopPropagation role="dialog" aria-modal="true">
      <div class="panel-header">
        <h2>Calculator Settings</h2>
        <button class="btn-close" on:click={() => showConfigPanel = false}>×</button>
      </div>
      <div class="panel-content">
        <div class="config-section">
          <h3>Success Rates</h3>
          <p class="config-info">
            <strong>Only full SUCCESS produces output items.</strong> Near-success only gives partial material refund.
          </p>
          <p class="config-info">
            Non-SiB ({MAX_NON_FAIL_NON_SIB}% non-fail):
            <span class="rate-success">{(ratesNonSiB.successRate * 100).toFixed(1)}%</span> success,
            <span class="rate-near">{(ratesNonSiB.nearSuccessRate * 100).toFixed(1)}%</span> near,
            <span class="rate-fail">{(ratesNonSiB.failRate * 100).toFixed(1)}%</span> fail
            <br/>SiB ({MAX_NON_FAIL_SIB}% non-fail):
            <span class="rate-success">{(ratesSiB.successRate * 100).toFixed(1)}%</span> success,
            <span class="rate-near">{(ratesSiB.nearSuccessRate * 100).toFixed(1)}%</span> near,
            <span class="rate-fail">{(ratesSiB.failRate * 100).toFixed(1)}%</span> fail
          </p>
          <button class="sidebar-btn" on:click={() => { showConfigPanel = false; showHotspotDialog = true; }}>
            View hotspot model details
          </button>
        </div>

        <div class="config-section">
          <label class="config-label">
            <span class="config-label-text">Certainty level:</span>
            <div class="config-input-row">
              <input
                type="number"
                class="config-input"
                value={certainty}
                min="50"
                max="99"
                step="5"
                on:change={(e) => setCertainty(e.target.value)}
              />
              <span class="config-unit">%</span>
            </div>
          </label>
          <p class="config-hint">Confidence level for having enough materials (50% = average, 90% = safer estimate)</p>
        </div>

        <div class="config-section">
          <label class="config-label">
            <span class="config-label-text">Material roll chance:</span>
            <div class="config-input-row">
              <input
                type="number"
                class="config-input"
                value={rollChance}
                min="0"
                max="100"
                step="1"
                on:change={(e) => setRollChance(e.target.value)}
              />
              <span class="config-unit">%</span>
            </div>
          </label>
          <p class="config-hint">Chance each material gets refunded on near-success (default: {DEFAULT_CONFIG.rollChance}%). Materials compete for the refund pool, which varies by hotspot.</p>
        </div>

        <div class="config-section">
          <h3>Per-Blueprint Non-Fail Chances</h3>
          <p class="config-info">
            You can set custom non-fail chances for each blueprint in the Tree view.
            Click the % value next to any non-target blueprint to edit it.
          </p>
          {#if Object.keys(nonFailChances).length > 0}
            <button class="sidebar-btn" on:click={resetNonFailChances}>
              Reset all to defaults
            </button>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}

{#if showOwnershipPanel}
  <div class="ownership-overlay" on:click={() => showOwnershipPanel = false} on:keydown={(e) => e.key === 'Escape' && (showOwnershipPanel = false)}>
    <div class="ownership-panel" on:click|stopPropagation role="dialog" aria-modal="true">
      <div class="panel-header">
        <h2>Blueprint Ownership</h2>
        <button class="btn-close" on:click={() => showOwnershipPanel = false}>×</button>
      </div>
      <div class="panel-content">
        {#if blueprintsInTree.length === 0}
          <p class="empty">Add blueprints to your plan to manage ownership.</p>
        {:else}
          <p class="panel-info">Toggle which blueprints you own. Unowned blueprints will show as "buy product" in steps.</p>
          <ul class="ownership-list">
            {#each blueprintsInTree as { blueprint, owned, isLimited }}
              <li class="ownership-item">
                <label class="ownership-label">
                  <input
                    type="checkbox"
                    checked={owned}
                    on:change={() => toggleOwnership(blueprint.Id)}
                  />
                  <span class="ownership-name">
                    {blueprint.Name}
                    {#if isLimited}
                      <span class="limited-note">(consumed per attempt)</span>
                    {/if}
                  </span>
                </label>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
  </div>
{/if}

{#if showDeleteDialog}
<div class="dialog-backdrop" on:click={cancelDelete} on:keydown={(e) => e.key === 'Escape' && cancelDelete()}>
  <div class="dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="delete-dialog-title">
    <div class="dialog-header">
      <h3 id="delete-dialog-title">Delete Plan</h3>
    </div>
    <div class="dialog-body">
      <p>Are you sure you want to delete this construction plan? This action cannot be undone.</p>
    </div>
    <div class="dialog-footer">
      <button class="dialog-btn secondary" on:click={cancelDelete}>Cancel</button>
      <button class="dialog-btn danger" on:click={handleDeletePlan}>Delete</button>
    </div>
  </div>
</div>
{/if}

{#if showImportSourceDialog}
<div class="dialog-backdrop" on:click={() => showImportSourceDialog = false} on:keydown={(e) => e.key === 'Escape' && (showImportSourceDialog = false)}>
  <div class="dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="import-dialog-title">
    <div class="dialog-header">
      <h3 id="import-dialog-title">Import Plan</h3>
    </div>
    <div class="dialog-body">
      <p>Choose import source:</p>
    </div>
    <div class="dialog-footer">
      <button class="dialog-btn secondary" on:click={() => showImportSourceDialog = false}>Close</button>
      {#if isLoggedIn && hasLocalData}
        <button class="dialog-btn secondary" on:click={() => { showImportSourceDialog = false; handleImportFromLocal(); }}>
          Import local ({localPlans.length})
        </button>
      {/if}
      <button class="dialog-btn" on:click={handleImportFromFile}>Import from file</button>
    </div>
  </div>
</div>
{/if}

{#if showHotspotDialog}
{@const breakdown = getHotspotBreakdown()}
<div class="dialog-backdrop" on:click={() => showHotspotDialog = false} on:keydown={(e) => e.key === 'Escape' && (showHotspotDialog = false)}>
  <div class="dialog hotspot-dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="hotspot-dialog-title">
    <div class="dialog-header">
      <h3 id="hotspot-dialog-title">Hotspot Model</h3>
    </div>
    <div class="dialog-body">
      <p class="hotspot-intro">Crafting outcomes are modeled using empirically-derived value hotspots from KDE lognormal analysis. Each non-fail craft hits one of these hotspots.</p>

      <h4>Hotspot Definitions</h4>
      <table class="hotspot-table">
        <thead>
          <tr>
            <th>Multiplier</th>
            <th>Weight</th>
            <th>Category</th>
            <th>Output Range</th>
          </tr>
        </thead>
        <tbody>
          {#each HOTSPOTS as hotspot}
            {@const isSplit = hotspot.multiplier >= SUCCESS_THRESHOLD && hotspot.multiplier * (1 - HOTSPOT_VARIANCE) < SUCCESS_THRESHOLD}
            <tr>
              <td>{hotspot.multiplier}x</td>
              <td>{(hotspot.weight * 100).toFixed(1)}%</td>
              <td>
                {#if isSplit}
                  <span class="rate-near">Near</span> / <span class="rate-success">Success</span>
                {:else if hotspot.outputRange}
                  <span class="rate-success">Success</span>
                {:else}
                  <span class="rate-near">Near-success</span>
                {/if}
              </td>
              <td>{hotspot.outputRange ? `[${hotspot.outputRange[0]}, ${hotspot.outputRange[1]}]` : '—'}</td>
            </tr>
          {/each}
          <tr>
            <td>&gt;10x</td>
            <td>{(HIGH_SUCCESS_WEIGHT * 100).toFixed(1)}%</td>
            <td><span class="rate-success">Success</span></td>
            <td>[{HIGH_SUCCESS_OUTPUT_RANGE[0]}, {HIGH_SUCCESS_OUTPUT_RANGE[1]}]</td>
          </tr>
        </tbody>
      </table>

      <h4>Parameters</h4>
      <table class="hotspot-params">
        <tbody>
          <tr><td>Variance</td><td>±{(HOTSPOT_VARIANCE * 100).toFixed(0)}% (Beta(2,2) distribution)</td></tr>
          <tr><td>Success threshold</td><td>{SUCCESS_THRESHOLD}x blueprint cost</td></tr>
          <tr><td>Max output multiplier</td><td>{MAX_OUTPUT_MULTIPLIER}x</td></tr>
          <tr><td>1.10x split fraction</td><td>{(SPLIT_NEAR_SUCCESS_FRACTION * 100).toFixed(1)}% near-success</td></tr>
          <tr><td>Default roll chance</td><td>{DEFAULT_CONFIG.rollChance}%</td></tr>
        </tbody>
      </table>

      <h4>Computed Breakdown</h4>
      <p class="hotspot-subtitle">Near-success hotspots (refund only):</p>
      <table class="hotspot-table compact">
        <thead>
          <tr><th>Source</th><th>Weight</th><th>Pool</th></tr>
        </thead>
        <tbody>
          {#each breakdown.nearSuccess as ns}
            <tr>
              <td>{ns.multiplier}x</td>
              <td>{(ns.weight * 100).toFixed(2)}%</td>
              <td>{ns.poolMultiplier.toFixed(3)}x cost</td>
            </tr>
          {/each}
          <tr class="total-row">
            <td>Total</td>
            <td>{(breakdown.totalNearSuccessWeight * 100).toFixed(2)}%</td>
            <td></td>
          </tr>
        </tbody>
      </table>

      <p class="hotspot-subtitle">Success hotspots (product output):</p>
      <table class="hotspot-table compact">
        <thead>
          <tr><th>Weight</th><th>Output Range</th></tr>
        </thead>
        <tbody>
          {#each breakdown.success as s}
            <tr>
              <td>{(s.weight * 100).toFixed(2)}%</td>
              <td>[{s.outputRange[0]}, {s.outputRange[1]}]</td>
            </tr>
          {/each}
          <tr class="total-row">
            <td>{(breakdown.totalSuccessWeight * 100).toFixed(2)}%</td>
            <td></td>
          </tr>
        </tbody>
      </table>

      <p class="hotspot-summary">
        Normalized: <span class="rate-near">{(breakdown.totalNearSuccessWeight / breakdown.totalWeight * 100).toFixed(1)}%</span> near-success,
        <span class="rate-success">{(breakdown.totalSuccessWeight / breakdown.totalWeight * 100).toFixed(1)}%</span> success
        (of non-fail outcomes)
      </p>
    </div>
    <div class="dialog-footer">
      <button class="dialog-btn secondary" on:click={() => showHotspotDialog = false}>Close</button>
    </div>
  </div>
</div>
{/if}

{#if showConditionInfoDialog}
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="dialog-backdrop" on:click={() => showConditionInfoDialog = false} on:keydown={(e) => e.key === 'Escape' && (showConditionInfoDialog = false)}>
  <div class="dialog condition-info-dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="condition-info-title">
    <div class="dialog-header">
      <h3 id="condition-info-title">Condition</h3>
    </div>
    <div class="dialog-body">
      <p>Adding condition to blueprints increases the value multiplier of each craft attempt, which affects output quantity and material refunds but comes at a cost of more failures. The multiplier ranges linearly from 1x (0%) to 7.5x (100%).</p>
      <h4>What condition affects</h4>
      <ul class="condition-effects-list">
        <li><strong>Output per success</strong> — higher condition increases the output range, producing more items per success (up to hard caps)</li>
        <li><strong>Material refund pool</strong> — near-success refund pools scale with condition, returning more materials</li>
        <li><strong>Max refund per material</strong> — each material can be refunded up to amount x condition multiplier</li>
        <li><strong>Non-fail chance</strong> — divided by condition multiplier, meaning more failures</li>
      </ul>
      <h4>Presets</h4>
      <ul class="condition-effects-list">
        <li><strong>Stability</strong> — 0% condition. Highest success rate, lowest output per success.</li>
        <li><strong>Attempts</strong> — minimizes total craft attempts needed. Balances output gains against increased fail rate.</li>
        <li><strong>Output</strong> (default) — maximizes average output per attempt. Best throughput efficiency.</li>
      </ul>
    </div>
    <div class="dialog-footer">
      <button class="dialog-btn secondary" on:click={() => showConditionInfoDialog = false}>Close</button>
    </div>
  </div>
</div>
{/if}

<MassBuyDialog
  show={showMassBuy}
  items={massBuyItems}
  allItems={exchangeSlimItems}
  {isLoggedIn}
  on:close={() => { showMassBuy = false; massBuyItems = []; }}
  on:complete={() => { showMassBuy = false; massBuyItems = []; }}
/>
</div>
