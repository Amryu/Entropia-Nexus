<!--
  @component Skills Calculator
  Import skill data, calculate profession levels and HP, and optimize skill progression.
  Uses WikiPage for consistent layout with mobile drawer support.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import '../../tools.css';
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import {
    calculateAllProfessionLevels,
    calculateHP,
    fetchAllSkillPEDValues,
    findCheapestPath,
    findCheapestHPPath,
    CHIP_OUT_LOSS_PERCENT
  } from '$lib/utils/skillCalculations.js';
  import { getCodexCategory, REWARD_DIVISORS } from '$lib/utils/codexUtils.js';
  import {
    detectAndParseImport,
    exportNexusFormat,
    exportExternalFormat,
    buildNameToKebabMap,
    computeSkillDiff
  } from '$lib/utils/skillImportUtils.js';
  import { fetchExchangeWapByName, fetchInventoryMarkups } from '$lib/markupSources.js';
  import { clickable } from '$lib/actions/clickable.js';

  export let data;

  const { skillsMetadata, professionsMetadata } = data;

  // ─── State ────────────────────────────────────────────────────────────
  const LOCAL_STORAGE_KEY = 'skills';

  // Current skill values: { "Agility": 0.0002, ... }
  let skillValues = {};
  let healthValue = null;

  // Online/Local mode
  let activeSource = 'local';
  let isLoggedIn = false;
  let isSaving = false;
  let saveError = null;
  let lastSavedAt = null;
  let showImportPrompt = false;

  // View state
  let activeView = 'skills'; // 'skills' | 'professions'
  let selectedSkill = null;
  let selectedProfession = null;
  let searchTerm = '';
  let categoryFilter = 'all';
  let showZero = true;

  // WikiPage integration
  let drawerOpen = false;
  let windowWidth = 0;
  $: isMobileLayout = windowWidth < 900;

  $: user = $page.data?.user;
  $: breadcrumbs = [
    { label: 'Tools', href: '/tools' },
    { label: 'Skills Calculator' }
  ];

  // Import dialog
  let showImportDialog = false;
  let importMode = 'paste'; // 'paste' | 'manual'
  let importText = '';
  let importPreview = null;
  let importError = null;
  let manualSearchTerm = '';
  let manualSkillEdits = {};

  // Import history
  let showHistoryPanel = false;
  let importHistory = [];
  let historyLoading = false;
  let expandedImportId = null;
  let expandedDeltas = [];

  // Unlocks view
  let showUnlocksView = false;

  // Optimizer
  let showOptimizer = false;
  let targetType = 'profession'; // 'profession' | 'hp'
  let targetProfession = '';
  let targetLevel = 0;
  let targetHPValue = 0;
  let optimizerResult = null;
  let methodOverrides = {};
  let implantWarnings = new Set();
  let optimizerMarkups = {};

  // Markup sources
  let markupSource = 'custom';
  let customMarkups = {};
  let wapByName = new Map();
  let nameToId = new Map();
  let inventoryMarkupMap = new Map();

  // PED value cache (fetched from server)
  let pedValueCache = {};
  let totalSkillValue = 0;
  let pedValuesLoading = false;
  let pedValueDebounceTimer = null;
  const PED_VALUE_DEBOUNCE_MS = 400;

  // ─── Derived data ─────────────────────────────────────────────────────

  $: skillLookup = new Map(skillsMetadata.map(s => [s.Name, s]));
  $: professionLookup = new Map(professionsMetadata.map(p => [p.Name, p]));

  $: skillCategories = [...new Set(skillsMetadata.map(s => s.Category).filter(Boolean))].sort();
  $: professionCategories = [...new Set(professionsMetadata.map(p => p.Category).filter(Boolean))].sort();

  $: professionLevels = calculateAllProfessionLevels(skillValues, professionsMetadata);
  $: totalHP = calculateHP(skillValues, skillsMetadata);
  $: nonZeroSkillCount = Object.values(skillValues).filter(v => v > 0).length;

  // Debounced PED value fetch from server
  $: if (skillValues) debouncedFetchPEDValues();

  function debouncedFetchPEDValues() {
    if (pedValueDebounceTimer) clearTimeout(pedValueDebounceTimer);
    pedValueDebounceTimer = setTimeout(() => fetchPEDValues(), PED_VALUE_DEBOUNCE_MS);
  }

  async function fetchPEDValues() {
    pedValuesLoading = true;
    try {
      const { pedBySkill, totalValue } = await fetchAllSkillPEDValues(skillValues);
      pedValueCache = pedBySkill;
      totalSkillValue = totalValue;
    } catch (err) {
      console.error('Failed to fetch PED values:', err);
    } finally {
      pedValuesLoading = false;
    }
  }
  $: totalSkillPoints = Object.values(skillValues).reduce((s, v) => s + (v > 0 ? v : 0), 0);

  $: unlocksRemaining = skillsMetadata.filter(s => s.IsHidden && (skillValues[s.Name] || 0) === 0).length;
  $: totalHiddenSkills = skillsMetadata.filter(s => s.IsHidden).length;

  // All hidden skill unlock info for the Unlocks view
  $: allUnlocks = skillsMetadata
    .filter(s => s.IsHidden)
    .map(skill => {
      const currentVal = skillValues[skill.Name] || 0;
      const isUnlocked = currentVal > 0;
      const unlockPaths = (skill.Unlocks || []).map(u => {
        const profLevel = professionLevels.get(u.Profession) || 0;
        return {
          profession: u.Profession,
          requiredLevel: u.Level,
          currentLevel: profLevel,
          progress: u.Level > 0 ? Math.min(profLevel / u.Level, 1) : 1,
          remaining: Math.max(u.Level - profLevel, 0)
        };
      });
      unlockPaths.sort((a, b) => b.progress - a.progress || a.remaining - b.remaining);
      return {
        name: skill.Name,
        category: skill.Category,
        isUnlocked,
        currentVal,
        closestPath: unlockPaths[0] || null,
        allPaths: unlockPaths
      };
    })
    .sort((a, b) => {
      if (a.isUnlocked !== b.isUnlocked) return a.isUnlocked ? 1 : -1;
      const pa = a.closestPath?.progress || 0;
      const pb = b.closestPath?.progress || 0;
      return pb - pa;
    });

  // Filtered skills list
  $: filteredSkills = skillsMetadata
    .filter(s => {
      if (categoryFilter !== 'all' && s.Category !== categoryFilter) return false;
      if (!showZero && (skillValues[s.Name] || 0) === 0) return false;
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        return s.Name.toLowerCase().includes(term);
      }
      return true;
    })
    .sort((a, b) => {
      const va = skillValues[a.Name] || 0;
      const vb = skillValues[b.Name] || 0;
      if (vb !== va) return vb - va;
      return a.Name.localeCompare(b.Name);
    });

  // Filtered professions list
  $: filteredProfessions = professionsMetadata
    .filter(p => {
      if (categoryFilter !== 'all' && p.Category !== categoryFilter) return false;
      if (!showZero && (professionLevels.get(p.Name) || 0) === 0) return false;
      if (searchTerm) {
        const term = searchTerm.toLowerCase();
        return p.Name.toLowerCase().includes(term);
      }
      return true;
    })
    .sort((a, b) => {
      const la = professionLevels.get(a.Name) || 0;
      const lb = professionLevels.get(b.Name) || 0;
      if (lb !== la) return lb - la;
      return a.Name.localeCompare(b.Name);
    });

  // Detail panel data
  $: selectedSkillData = selectedSkill ? skillLookup.get(selectedSkill) : null;
  $: selectedProfessionData = selectedProfession ? professionLookup.get(selectedProfession) : null;

  // Skills relevant to current optimizer target
  $: optimizerSkills = (() => {
    if (targetType === 'profession' && targetProfession) {
      const prof = professionLookup.get(targetProfession);
      return (prof?.Skills || [])
        .filter(s => skillLookup.get(s.Name)?.IsExtractable !== false)
        .map(s => ({ Name: s.Name, Weight: s.Weight }));
    } else if (targetType === 'hp') {
      return skillsMetadata
        .filter(s => s.HPIncrease != null && s.HPIncrease > 0 && s.IsExtractable !== false)
        .map(s => ({ Name: s.Name, HPIncrease: s.HPIncrease }));
    }
    return [];
  })();

  // Default all skills to 'chip' when optimizer skills change
  $: {
    const newOverrides = {};
    for (const s of optimizerSkills) {
      const existing = methodOverrides[s.Name];
      const meta = skillLookup.get(s.Name);
      if (existing) {
        // Keep existing override, but force non-extractable skills away from 'chip'
        newOverrides[s.Name] = (!meta?.IsExtractable && existing === 'chip') ? 'auto' : existing;
      } else {
        // Default: 'chip' for extractable, 'auto' for non-extractable
        newOverrides[s.Name] = meta?.IsExtractable ? 'chip' : 'auto';
      }
    }
    methodOverrides = newOverrides;
  }

  // Markups for optimizer and method table display
  $: {
    void markupSource; void customMarkups; void wapByName; void nameToId; void inventoryMarkupMap;
    if ((targetType === 'profession' && targetProfession) || targetType === 'hp') {
      const skillNames = targetType === 'profession'
        ? (professionLookup.get(targetProfession)?.Skills || []).map(s => s.Name)
        : skillsMetadata.filter(s => s.HPIncrease > 0).map(s => s.Name);
      const result = getMarkupsForSkills(skillNames);
      optimizerMarkups = result.markups;
      implantWarnings = result.warnings;
    } else {
      optimizerMarkups = {};
      implantWarnings = new Set();
    }
  }

  // Optimizer reactive
  $: {
    if (targetType === 'profession' && targetProfession && targetLevel > 0) {
      const prof = professionLookup.get(targetProfession);
      if (prof) {
        const currentLevel = professionLevels.get(targetProfession) || 0;
        optimizerResult = findCheapestPath(skillValues, prof.Skills, currentLevel, targetLevel, optimizerMarkups, methodOverrides);
      }
    } else if (targetType === 'hp' && targetHPValue > totalHP) {
      optimizerResult = findCheapestHPPath(skillValues, skillsMetadata, totalHP, targetHPValue, optimizerMarkups, methodOverrides);
    } else {
      optimizerResult = null;
    }
  }

  // ─── Functions ────────────────────────────────────────────────────────

  function getMarkupsForSkills(skillNames) {
    const markups = {};
    const warnings = new Set();
    for (const name of skillNames) {
      const meta = skillLookup.get(name);
      if (!meta?.IsExtractable) { markups[name] = Infinity; continue; }
      const implantName = `${name} Skill Implant (L)`;
      const wap = wapByName.get(implantName);
      const itemId = nameToId.get(implantName);
      const invMu = itemId != null ? inventoryMarkupMap.get(itemId) : undefined;
      if (markupSource === 'custom') {
        // Custom → Market → Inventory → 100
        markups[name] = customMarkups[name] ?? wap ?? invMu ?? 100;
      } else if (markupSource === 'market') {
        // Market → Inventory → 100
        markups[name] = wap ?? invMu ?? 100;
        if (wap == null && invMu == null) warnings.add(name);
      } else if (markupSource === 'inventory') {
        markups[name] = invMu ?? 100;
        if (invMu == null) warnings.add(name);
      }
    }
    return { markups, warnings };
  }

  function setMethodOverride(skillName, method) {
    methodOverrides = { ...methodOverrides, [skillName]: method };
  }

  function bulkSetMethod(method) {
    const newOverrides = { ...methodOverrides };
    for (const s of optimizerSkills) {
      if (method === 'codex' && !getCodexCategory(s.Name)) continue;
      if (method === 'chip' && !skillLookup.get(s.Name)?.IsExtractable) continue;
      newOverrides[s.Name] = method;
    }
    methodOverrides = newOverrides;
  }

  function readLocalSkills() {
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function writeLocalSkills(skills, health = null) {
    const data = { skills, health, updatedAt: new Date().toISOString() };
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(data));
  }

  async function fetchOnlineSkills() {
    try {
      const res = await fetch('/api/tools/skills');
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  async function saveOnlineSkills(skills, trackImport = true) {
    isSaving = true;
    saveError = null;
    try {
      const res = await fetch('/api/tools/skills', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skills, trackImport })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        saveError = data.error || 'Failed to save.';
        return null;
      }
      const result = await res.json();
      lastSavedAt = new Date().toISOString();
      return result;
    } catch (err) {
      saveError = 'Network error.';
      return null;
    } finally {
      isSaving = false;
    }
  }

  function setActiveSource(source) {
    activeSource = source;
    categoryFilter = 'all';
    searchTerm = '';
  }

  async function initialize() {
    isLoggedIn = !!$page.data?.user;

    const localData = readLocalSkills();

    if (isLoggedIn) {
      const onlineData = await fetchOnlineSkills();
      if (onlineData?.skills && Object.keys(onlineData.skills).length > 0) {
        skillValues = onlineData.skills;
        lastSavedAt = onlineData.updated_at;
        activeSource = 'online';

        if (localData?.skills && Object.keys(localData.skills).length > 0) {
          const localHasUnique = Object.entries(localData.skills).some(
            ([k, v]) => v > 0 && (onlineData.skills[k] || 0) === 0
          );
          if (localHasUnique) showImportPrompt = true;
        }
      } else if (localData?.skills) {
        skillValues = localData.skills;
        healthValue = localData.health ?? null;
        activeSource = 'online';
        await saveOnlineSkills(localData.skills);
      } else {
        activeSource = 'online';
      }
    } else {
      if (localData?.skills) {
        skillValues = localData.skills;
        healthValue = localData.health ?? null;
      }
      activeSource = 'local';
    }

    fetchExchangeWapByName().then(({ wapByName: w, nameToId: n }) => {
      wapByName = w;
      nameToId = n;
    });
    if (isLoggedIn) {
      fetchInventoryMarkups().then(m => { inventoryMarkupMap = m; });
    }
  }

  async function handleImportConfirm() {
    if (!importPreview?.skills) return;

    skillValues = { ...importPreview.skills };
    healthValue = importPreview.health ?? null;

    if (activeSource === 'online' && isLoggedIn) {
      await saveOnlineSkills(skillValues);
    } else {
      writeLocalSkills(skillValues, healthValue);
    }

    showImportDialog = false;
    importText = '';
    importPreview = null;
  }

  async function handleManualImport() {
    if (Object.keys(manualSkillEdits).length === 0) return;
    const merged = { ...skillValues };
    for (const [name, val] of Object.entries(manualSkillEdits)) {
      merged[name] = val;
    }
    skillValues = merged;
    if (activeSource === 'online' && isLoggedIn) {
      await saveOnlineSkills(skillValues);
    } else {
      writeLocalSkills(skillValues, healthValue);
    }
    showImportDialog = false;
    manualSkillEdits = {};
    manualSearchTerm = '';
  }

  function handleImportPreview() {
    importError = null;
    importPreview = null;

    if (!importText.trim()) {
      importError = 'Please paste skill data.';
      return;
    }

    const result = detectAndParseImport(importText, skillsMetadata);
    if (result.error) {
      importError = result.error;
      return;
    }

    const diff = computeSkillDiff(skillValues, result.skills);
    importPreview = {
      ...result,
      diff,
      skillCount: Object.keys(result.skills).filter(k => result.skills[k] > 0).length
    };
  }

  async function handleImportFromLocal() {
    const localData = readLocalSkills();
    if (!localData?.skills) return;

    const merged = { ...skillValues };
    for (const [k, v] of Object.entries(localData.skills)) {
      if (v > (merged[k] || 0)) merged[k] = v;
    }
    skillValues = merged;
    if (activeSource === 'online') {
      await saveOnlineSkills(skillValues);
    }
    showImportPrompt = false;
  }

  function handleExport(format = 'nexus') {
    let text;
    if (format === 'external') {
      const nameToKebab = buildNameToKebabMap(skillsMetadata);
      text = exportExternalFormat(skillValues, nameToKebab, healthValue);
    } else {
      text = exportNexusFormat(skillValues, { health: healthValue });
    }

    const blob = new Blob([text], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `skills-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function selectSkill(name) {
    activeView = 'skills';
    selectedSkill = name;
    selectedProfession = null;
  }

  function selectProfession(name) {
    activeView = 'professions';
    selectedProfession = name;
    selectedSkill = null;
  }

  function toggleSkillUnlock(name) {
    const current = skillValues[name] || 0;
    const newVal = current === 0 ? 1 : 0;
    skillValues = { ...skillValues, [name]: newVal };
    if (activeSource === 'online' && isLoggedIn) saveOnlineSkills(skillValues);
    else writeLocalSkills(skillValues, healthValue);
  }

  function targetUnlock(profName, level) {
    targetType = 'profession';
    targetProfession = profName;
    targetLevel = level;
    showOptimizer = true;
    showUnlocksView = false;
  }

  async function loadImportHistory() {
    if (!isLoggedIn || activeSource !== 'online') return;
    historyLoading = true;
    try {
      const res = await fetch('/api/tools/skills/imports?limit=20');
      if (res.ok) importHistory = await res.json();
    } catch { /* ignore */ }
    historyLoading = false;
  }

  async function toggleImportDeltas(importId) {
    if (expandedImportId === importId) {
      expandedImportId = null;
      expandedDeltas = [];
      return;
    }
    expandedImportId = importId;
    try {
      const res = await fetch(`/api/tools/skills/imports/${importId}/deltas`);
      if (res.ok) expandedDeltas = await res.json();
    } catch {
      expandedDeltas = [];
    }
  }

  function formatNumber(n, decimals = 4) {
    if (n == null || !Number.isFinite(n)) return '—';
    if (n === 0) return '0';
    if (n >= 1000) return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return n.toFixed(decimals).replace(/\.?0+$/, '') || '0';
  }

  function formatLevel(n) {
    if (n == null || !Number.isFinite(n) || n === 0) return '0.00';
    return n.toFixed(2);
  }

  function formatPED(n) {
    if (n == null || !Number.isFinite(n)) return '—';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'k';
    return n.toFixed(2);
  }

  onMount(initialize);
</script>

<svelte:head>
  <title>Skills Calculator - Entropia Nexus</title>
  <meta name="description" content="Calculate profession levels, HP, and optimize skill progression for Entropia Universe." />
  <link rel="canonical" href="https://entropianexus.com/tools/skills" />
</svelte:head>

<svelte:window bind:innerWidth={windowWidth} />

<WikiPage
  title="Skills Calculator"
  {breadcrumbs}
  entity={{ Name: 'Skills Calculator' }}
  basePath="/tools/skills"
  pageClass="tool-skills"
  navItems={[]}
  bind:drawerOpen
  {user}
  editable={false}
  canEdit={false}
>
  <!-- Header Actions -->
  <div slot="header-actions" class="tool-header-actions">
    <button class="action-btn" on:click={() => { showImportDialog = true; importMode = 'paste'; importText = ''; importPreview = null; importError = null; manualSkillEdits = {}; manualSearchTerm = ''; }} title="Import skills">
      <svg class="action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" />
      </svg>
      <span class="action-label">Import</span>
    </button>
    <button class="action-btn" on:click={() => handleExport('nexus')} title="Export skills">
      <svg class="action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
      </svg>
      <span class="action-label">Export</span>
    </button>
    <button class="action-btn" class:active={showUnlocksView} on:click={() => { showUnlocksView = !showUnlocksView; }} title="Skill unlocks overview">
      <svg class="action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 019.9-1"/>
      </svg>
      <span class="action-label">Unlocks</span>
    </button>
    {#if isLoggedIn && activeSource === 'online'}
      <button class="action-btn" on:click={() => { showHistoryPanel = !showHistoryPanel; if (showHistoryPanel) loadImportHistory(); }} title="Import history">
        <svg class="action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
        </svg>
        <span class="action-label">History</span>
      </button>
    {/if}
    {#if isLoggedIn}
      <div class="source-toggle">
        <button class="toggle-btn" class:active={activeSource === 'local'} on:click={() => setActiveSource('local')}>Local</button>
        <button class="toggle-btn" class:active={activeSource === 'online'} on:click={() => setActiveSource('online')}>Online</button>
      </div>
    {/if}
    {#if isSaving}
      <span class="save-indicator saving">Saving...</span>
    {:else if saveError}
      <span class="save-indicator error" title={saveError}>Error</span>
    {/if}
    {#if isMobileLayout}
      <button class="action-btn" class:active={showOptimizer} on:click={() => showOptimizer = !showOptimizer} title="Toggle optimizer">
        <svg class="action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 20V10" /><path d="M18 20V4" /><path d="M6 20v-4" />
        </svg>
        <span class="action-label">Optimizer</span>
      </button>
    {/if}
  </div>

  <!-- Sidebar -->
  <div slot="sidebar" let:isMobile class="sidebar-root">
    <div class="nav-header">
      <h2 class="nav-title">Skills</h2>
    </div>
    <div class="sidebar-body">
      <!-- Skills/Professions toggle -->
      <div class="sidebar-toggle">
        <button class:active={activeView === 'skills'} on:click={() => { activeView = 'skills'; categoryFilter = 'all'; searchTerm = ''; }}>Skills</button>
        <button class:active={activeView === 'professions'} on:click={() => { activeView = 'professions'; categoryFilter = 'all'; searchTerm = ''; }}>Professions</button>
      </div>

      <!-- Search -->
      <div class="sidebar-search">
        <input type="text" placeholder="Search {activeView}..." bind:value={searchTerm} />
      </div>

      <!-- Filters -->
      <div class="sidebar-filters">
        <select class="sidebar-select" bind:value={categoryFilter}>
          <option value="all">All Categories</option>
          {#each (activeView === 'skills' ? skillCategories : professionCategories) as cat}
            <option value={cat}>{cat}</option>
          {/each}
        </select>
        <label class="zero-toggle">
          <input type="checkbox" bind:checked={showZero} />
          <span>Show 0s</span>
        </label>
      </div>

      <!-- List -->
      <div class="sidebar-list">
        {#if activeView === 'skills'}
          {#each filteredSkills as skill (skill.Name)}
            {@const val = skillValues[skill.Name] || 0}
            <button
              class="sidebar-item"
              class:active={selectedSkill === skill.Name}
              class:hidden-skill={skill.IsHidden}
              on:click={() => { selectSkill(skill.Name); if (isMobile) drawerOpen = false; }}
            >
              <span class="item-name">{skill.Name}</span>
              {#if skill.IsHidden}
                <span class="unlock-btn sidebar-unlock" role="button" tabindex="-1" title={val > 0 ? 'Lock skill' : 'Unlock skill'} class:unlocked={val > 0} on:click|stopPropagation={() => toggleSkillUnlock(skill.Name)} use:clickable={{ tabindex: -1 }}>
                  {#if val > 0}
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
                  {:else}
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 019.9-1"/></svg>
                  {/if}
                </span>
              {/if}
              <span class="item-value">{formatNumber(val)}</span>
            </button>
          {:else}
            <div class="sidebar-empty">
              {#if !showZero && nonZeroSkillCount === 0}
                No skills imported yet.
              {:else}
                No matching skills.
              {/if}
            </div>
          {/each}
        {:else}
          {#each filteredProfessions as prof (prof.Name)}
            {@const level = professionLevels.get(prof.Name) || 0}
            <button
              class="sidebar-item"
              class:active={selectedProfession === prof.Name}
              on:click={() => { selectProfession(prof.Name); if (isMobile) drawerOpen = false; }}
            >
              <span class="item-name">{prof.Name}</span>
              <span class="item-value">{formatLevel(level)}</span>
            </button>
          {:else}
            <div class="sidebar-empty">
              {#if !showZero && nonZeroSkillCount === 0}
                Import skills to see profession levels.
              {:else}
                No matching professions.
              {/if}
            </div>
          {/each}
        {/if}
      </div>
    </div>
  </div>

  <!-- Main Content -->
  <div class="skills-content">
    <!-- Import from local prompt -->
    {#if showImportPrompt}
      <div class="import-prompt">
        <span>You have local skill data. Import it to your online account?</span>
        <button class="sidebar-btn accent" on:click={handleImportFromLocal}>Import</button>
        <button class="sidebar-btn neutral" on:click={() => showImportPrompt = false}>Dismiss</button>
      </div>
    {/if}

    <!-- Summary bar -->
    <div class="summary-bar">
      <div class="summary-item">
        <span class="summary-label">HP</span>
        <span class="summary-value">{Math.floor(totalHP)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Total Value</span>
        <span class="summary-value" class:ped-loading={pedValuesLoading}>
          {pedValuesLoading && totalSkillValue === 0 ? '...' : formatPED(totalSkillValue)}
        </span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Total Skill Points</span>
        <span class="summary-value">{formatNumber(totalSkillPoints, 2)}</span>
      </div>
      <div class="summary-item">
        <span class="summary-label">Unlocks remaining</span>
        <span class="summary-value">{unlocksRemaining}</span>
      </div>
    </div>

    <!-- Detail + Optimizer wrapper -->
    <div class="detail-optimizer-wrapper" class:optimizer-open={showOptimizer}>
      <div class="detail-area">
        {#if showUnlocksView}
          <div class="unlocks-view">
            <div class="unlocks-header">
              <h2>Skill Unlocks</h2>
              <span class="unlocks-count">{totalHiddenSkills - unlocksRemaining} / {totalHiddenSkills} unlocked</span>
            </div>
            <div class="unlocks-table">
              <div class="unlocks-table-header">
                <span>Skill</span>
                <span>Closest Profession</span>
                <span class="col-right">Progress</span>
                <span></span>
              </div>
              {#each allUnlocks as unlock (unlock.name)}
                <div class="unlock-row" class:unlocked={unlock.isUnlocked}>
                  <button class="unlock-skill-name" on:click={() => { showUnlocksView = false; selectSkill(unlock.name); }}>
                    {unlock.name}
                  </button>
                  <div class="unlock-prof-cell">
                    {#if unlock.closestPath}
                      <button class="unlock-prof-link" on:click={() => { showUnlocksView = false; selectProfession(unlock.closestPath.profession); }}>
                        {unlock.closestPath.profession}
                      </button>
                      <span class="unlock-prof-level">
                        {formatLevel(unlock.closestPath.currentLevel)} / {unlock.closestPath.requiredLevel}
                      </span>
                    {:else}
                      <span class="text-muted">—</span>
                    {/if}
                  </div>
                  <div class="unlock-progress-cell">
                    {#if unlock.isUnlocked}
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success-color)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    {:else if unlock.closestPath}
                      <div class="unlock-progress-bar">
                        <div class="unlock-progress-fill" style="width: {Math.round(unlock.closestPath.progress * 100)}%"></div>
                      </div>
                      <span class="unlock-progress-pct">{Math.round(unlock.closestPath.progress * 100)}%</span>
                    {:else}
                      <span class="text-muted">—</span>
                    {/if}
                  </div>
                  <div class="unlock-actions">
                    {#if !unlock.isUnlocked && unlock.closestPath}
                      <button class="target-btn" title="Target in optimizer" on:click={() => targetUnlock(unlock.closestPath.profession, unlock.closestPath.requiredLevel)}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
                      </button>
                    {/if}
                    <button class="unlock-btn" class:unlocked={unlock.isUnlocked} title={unlock.isUnlocked ? 'Lock skill' : 'Unlock skill'} on:click={() => toggleSkillUnlock(unlock.name)}>
                      {#if unlock.isUnlocked}
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
                      {:else}
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 019.9-1"/></svg>
                      {/if}
                    </button>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {:else if activeView === 'skills' && selectedSkillData}
          <div class="detail-header" class:hidden-skill-detail={selectedSkillData.IsHidden}>
            <div class="detail-title">
              <h2>{selectedSkillData.Name}</h2>
              <span class="detail-category">{selectedSkillData.Category || 'Unknown'}</span>
              {#if selectedSkillData.IsHidden}
                <span class="detail-badge is-hidden">Hidden</span>
              {/if}
            </div>
            <div class="detail-stats">
              <div class="stat">
                <span class="stat-label">Value</span>
                <span class="stat-value">{formatNumber(skillValues[selectedSkillData.Name] || 0)}</span>
              </div>
              {#if selectedSkillData.IsHidden}
                <div class="stat">
                  <button class="unlock-btn detail-unlock" class:unlocked={(skillValues[selectedSkillData.Name] || 0) > 0} on:click={() => toggleSkillUnlock(selectedSkillData.Name)} title={(skillValues[selectedSkillData.Name] || 0) > 0 ? 'Lock skill (set to 0)' : 'Unlock skill (set to 1)'}>
                    {#if (skillValues[selectedSkillData.Name] || 0) > 0}
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
                      <span>Locked</span>
                    {:else}
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 019.9-1"/></svg>
                      <span>Unlock</span>
                    {/if}
                  </button>
                </div>
              {/if}
              {#if selectedSkillData.HPIncrease}
                <div class="stat">
                  <span class="stat-label">Points/HP</span>
                  <span class="stat-value">{selectedSkillData.HPIncrease}</span>
                </div>
              {/if}
              <div class="stat">
                <span class="stat-label">Extractable</span>
                <span class="stat-value">{selectedSkillData.IsExtractable ? 'Yes' : 'No'}</span>
              </div>
              {#if getCodexCategory(selectedSkillData.Name)}
                {@const codexCat = getCodexCategory(selectedSkillData.Name)}
                <div class="stat">
                  <span class="stat-label">Codex</span>
                  <span class="stat-value">Cat {codexCat.slice(-1)} ({REWARD_DIVISORS[codexCat]}x)</span>
                </div>
              {/if}
            </div>
          </div>

          <div class="detail-columns">
            {#if selectedSkillData.Professions.length > 0}
              <div class="detail-section">
                <h3>Professions Affected</h3>
                <div class="detail-table">
                  <div class="detail-table-header">
                    <span>Profession</span>
                    <span class="col-right">Weight</span>
                    <span class="col-right">Contribution</span>
                  </div>
                  {#each selectedSkillData.Professions.sort((a, b) => b.Weight - a.Weight) as p}
                    {@const contribution = (skillValues[selectedSkillData.Name] || 0) * p.Weight / 10000}
                    <button class="detail-table-row clickable" on:click={() => selectProfession(p.Name)}>
                      <span class="prof-link">{p.Name}</span>
                      <span class="col-right">{p.Weight}</span>
                      <span class="col-right">{formatLevel(contribution)}</span>
                    </button>
                  {/each}
                </div>
              </div>
            {/if}

            {#if selectedSkillData.Unlocks?.length > 0}
              <div class="detail-section">
                <h3>Unlocked By</h3>
                <div class="detail-table cols-3">
                  <div class="detail-table-header">
                    <span>Level</span>
                    <span>Profession</span>
                    <span></span>
                  </div>
                  {#each selectedSkillData.Unlocks.sort((a, b) => a.Level - b.Level) as u}
                    <div class="detail-table-row unlock-row-actions">
                      <button class="clickable" on:click={() => selectProfession(u.Profession)}>
                        <span class="unlock-level">{u.Level}</span>
                      </button>
                      <button class="prof-link clickable" on:click={() => selectProfession(u.Profession)}>{u.Profession}</button>
                      <button class="target-btn" title="Target in optimizer" on:click={() => targetUnlock(u.Profession, u.Level)}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
                      </button>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>

        {:else if activeView === 'professions' && selectedProfessionData}
          {@const level = professionLevels.get(selectedProfessionData.Name) || 0}
          {@const totalWeight = selectedProfessionData.Skills.reduce((s, sk) => s + sk.Weight, 0)}
          <div class="detail-header">
            <div class="detail-title">
              <h2>{selectedProfessionData.Name}</h2>
              <span class="detail-category">{selectedProfessionData.Category || 'Unknown'}</span>
            </div>
            <div class="detail-stats">
              <div class="stat highlight">
                <span class="stat-label">Level</span>
                <span class="stat-value">{formatLevel(level)}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Weight</span>
                <span class="stat-value">{totalWeight}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Skills</span>
                <span class="stat-value">{selectedProfessionData.Skills.length}</span>
              </div>
            </div>
          </div>

          <div class="detail-columns">
            <div class="detail-section">
              <h3>Contributing Skills</h3>
              <div class="detail-table cols-4">
                <div class="detail-table-header">
                  <span>Skill</span>
                  <span class="col-right">Weight</span>
                  <span class="col-right">Value</span>
                  <span class="col-right">Levels</span>
                </div>
                {#each selectedProfessionData.Skills.sort((a, b) => b.Weight - a.Weight) as s}
                  {@const val = skillValues[s.Name] || 0}
                  {@const contrib = val * s.Weight / 10000}
                  {@const pct = totalWeight > 0 ? (s.Weight / totalWeight * 100) : 0}
                  <button class="detail-table-row clickable" on:click={() => selectSkill(s.Name)}>
                    <span class="skill-link">
                      {s.Name}
                      <span class="weight-bar-container">
                        <span class="weight-bar" style="width: {pct}%"></span>
                      </span>
                    </span>
                    <span class="col-right">{s.Weight}</span>
                    <span class="col-right">{formatNumber(val)}</span>
                    <span class="col-right">{formatLevel(contrib)}</span>
                  </button>
                {/each}
              </div>
            </div>

            {#if selectedProfessionData.Unlocks?.length > 0}
              <div class="detail-section">
                <h3>Skill Unlocks</h3>
                <div class="detail-table cols-3">
                  <div class="detail-table-header">
                    <span>Level</span>
                    <span>Skill</span>
                    <span></span>
                  </div>
                  {#each selectedProfessionData.Unlocks.sort((a, b) => a.Level - b.Level) as u}
                    {@const unlockSkillName = u.Skill?.Name || u.Name}
                    {@const unlockLevel = u.Level ?? 0}
                    <div class="detail-table-row unlock-row-actions">
                      <button class="clickable" on:click={() => selectSkill(unlockSkillName)}>
                        <span class="unlock-level">{unlockLevel}</span>
                      </button>
                      <button class="skill-link clickable" on:click={() => selectSkill(unlockSkillName)}>{unlockSkillName}</button>
                      <button class="target-btn" title="Target in optimizer" on:click={() => targetUnlock(selectedProfessionData.Name, unlockLevel)}>
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>
                      </button>
                    </div>
                  {/each}
                </div>
              </div>
            {/if}
          </div>

        {:else}
          <div class="detail-empty">
            <p>Select a {activeView === 'skills' ? 'skill' : 'profession'} to view details.</p>
            {#if nonZeroSkillCount === 0}
              <p class="detail-hint">Import your skills to get started.</p>
            {/if}
          </div>
        {/if}
      </div>

      <!-- Optimizer overlay -->
      <div class="optimizer-section" class:expanded={showOptimizer}>
        {#if !isMobileLayout || showOptimizer}
          <button class="optimizer-toggle" on:click={() => showOptimizer = !showOptimizer}>
            <span>Optimizer</span>
            <svg class="toggle-chevron" class:open={showOptimizer} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="18 15 12 9 6 15" />
            </svg>
          </button>
        {/if}

        <div class="optimizer-content-wrapper" class:visible={showOptimizer}>
        <div class="optimizer-content">
          <div class="optimizer-controls">
            <div class="control-group">
              <span class="control-label">Target</span>
              <div class="target-toggle">
                <button class="mu-btn" class:active={targetType === 'profession'} on:click={() => targetType = 'profession'}>Profession</button>
                <button class="mu-btn" class:active={targetType === 'hp'} on:click={() => targetType = 'hp'}>HP</button>
              </div>
            </div>

            {#if targetType === 'profession'}
              <div class="control-group">
                <label for="target-prof">Profession</label>
                <select id="target-prof" bind:value={targetProfession} on:change={() => {
                  const currentLvl = professionLevels.get(targetProfession) || 0;
                  targetLevel = Math.ceil(currentLvl) || 1;
                }}>
                  <option value="">Select...</option>
                  {#each professionsMetadata.sort((a, b) => a.Name.localeCompare(b.Name)) as p}
                    <option value={p.Name}>{p.Name} (Lv {formatLevel(professionLevels.get(p.Name) || 0)})</option>
                  {/each}
                </select>
              </div>
              <div class="control-group">
                <label for="target-level">Target Level</label>
                <input id="target-level" type="number" min="0" step="1" bind:value={targetLevel} placeholder="e.g. 50" />
              </div>
            {:else}
              <div class="control-group">
                <label for="target-hp">Target HP</label>
                <input id="target-hp" type="number" min={Math.ceil(totalHP)} step="1" bind:value={targetHPValue} placeholder="e.g. 200" />
              </div>
            {/if}

            <div class="control-group">
              <span class="control-label">MU Source</span>
              <div class="mu-buttons">
                <button class="mu-btn" class:active={markupSource === 'custom'} on:click={() => markupSource = 'custom'}>Custom</button>
                <button class="mu-btn" class:active={markupSource === 'market'} disabled={wapByName.size === 0} on:click={() => markupSource = 'market'}>Market</button>
                <button class="mu-btn" class:active={markupSource === 'inventory'} disabled={inventoryMarkupMap.size === 0} on:click={() => markupSource = 'inventory'}>Inventory</button>
              </div>
            </div>
          </div>

          <div class="optimizer-panels">
          <!-- Per-skill method overrides -->
          {#if optimizerSkills.length > 0}
            <div class="method-config">
              <div class="method-config-header">
                <h4>Skill Methods</h4>
                <div class="bulk-toggle">
                  <button class="mu-btn" on:click={() => bulkSetMethod('codex')} title="Set all to Codex">All Codex</button>
                  <button class="mu-btn" on:click={() => bulkSetMethod('chip')} title="Set all to Chip">All Chip</button>
                  <button class="mu-btn" on:click={() => bulkSetMethod('none')} title="Disable all">All None</button>
                </div>
              </div>
              <div class="method-table-header">
                <span>Skill</span>
                <span class="col-right">Value</span>
                <span class="col-right">MU%</span>
                <span class="col-right">Total</span>
                <span class="col-right">Method</span>
              </div>
              <div class="method-list">
                {#each optimizerSkills as skill}
                  {@const codexCat = getCodexCategory(skill.Name)}
                  {@const isExtractable = skillLookup.get(skill.Name)?.IsExtractable}
                  {@const currentMethod = methodOverrides[skill.Name] || 'auto'}
                  {@const skillVal = skillValues[skill.Name] || 0}
                  {@const mu = optimizerMarkups[skill.Name] ?? 100}
                  {@const ttValue = pedValueCache[skill.Name] ?? 0}
                  <div class="method-row">
                    <span class="method-skill-name" title={skill.Name}>
                      {skill.Name}
                      {#if implantWarnings.has(skill.Name)}
                        <span class="warning-icon" title="No markup data for {skill.Name} Skill Implant (L)">&#9888;</span>
                      {/if}
                    </span>
                    <span class="col-right method-cell">{formatNumber(skillVal)}</span>
                    <span class="col-right method-cell">
                      {#if markupSource === 'custom'}
                        <input
                          type="number"
                          class="mu-input"
                          value={customMarkups[skill.Name] ?? Math.round(mu)}
                          on:change={(e) => { customMarkups = { ...customMarkups, [skill.Name]: Number(e.target.value) || 100 }; }}
                          min="0"
                          step="1"
                        />
                      {:else}
                        {mu !== Infinity ? Math.round(mu) + '%' : '—'}
                      {/if}
                    </span>
                    <span class="col-right method-cell">{mu !== Infinity ? formatPED(ttValue * mu / 100) : '—'}</span>
                    <div class="method-buttons">
                      <button
                        class="method-btn"
                        class:active={currentMethod === 'codex'}
                        disabled={!codexCat}
                        title={!codexCat ? 'Not available via Codex' : `Codex Cat ${codexCat.slice(-1)}`}
                        on:click={() => setMethodOverride(skill.Name, currentMethod === 'codex' ? 'auto' : 'codex')}
                      >Codex</button>
                      <button
                        class="method-btn"
                        class:active={currentMethod === 'chip'}
                        disabled={!isExtractable}
                        title={!isExtractable ? 'Not extractable' : 'Chip in via ESI'}
                        on:click={() => setMethodOverride(skill.Name, currentMethod === 'chip' ? 'auto' : 'chip')}
                      >Chip</button>
                      <button
                        class="method-btn none"
                        class:active={currentMethod === 'none'}
                        on:click={() => setMethodOverride(skill.Name, currentMethod === 'none' ? 'auto' : 'none')}
                      >None</button>
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <div class="optimizer-results">
          {#if optimizerResult}
            {#if !optimizerResult.feasible}
              <div class="optimizer-warning">Cannot reach target with available skills.</div>
            {/if}
            <div class="optimizer-summary">
              <span>Estimated cost: <strong>{formatPED(optimizerResult.totalCost)} PED</strong></span>
              {#if targetType === 'profession' && targetProfession}
                {@const currentLvl = professionLevels.get(targetProfession) || 0}
                <span>Current: {formatLevel(currentLvl)} &rarr; Target: {formatLevel(targetLevel)}</span>
              {:else if targetType === 'hp'}
                <span>Current: {Math.floor(totalHP)} HP &rarr; Target: {targetHPValue} HP</span>
              {/if}
            </div>
            <div class="optimizer-table-scroll">
              <div class="optimizer-table">
                <div class="optimizer-table-header">
                  <span>Skill</span>
                  <span class="col-right">Start</span>
                  <span class="col-right">End</span>
                  <span class="col-right">MU%</span>
                  <span class="col-right">Method</span>
                  <span class="col-right">Cost</span>
                </div>
                {#each optimizerResult.allocations as alloc}
                  {@const mu = optimizerMarkups[alloc.skill]}
                  <div class="optimizer-table-row">
                    <span>
                      {alloc.skill}
                      {#if implantWarnings.has(alloc.skill)}
                        <span class="warning-icon" title="No markup data for {alloc.skill} Skill Implant (L)">&#9888;</span>
                      {/if}
                    </span>
                    <span class="col-right">{formatNumber(alloc.currentPoints)}</span>
                    <span class="col-right">{formatNumber(alloc.currentPoints + alloc.addedPoints)}</span>
                    <span class="col-right">{mu != null && mu !== Infinity ? Math.round(mu) + '%' : '—'}</span>
                    <span class="col-right method-badge" class:codex={alloc.method === 'codex'} class:chip={alloc.method === 'chip'}>
                      {alloc.method === 'codex' ? `Codex (Cat ${alloc.codexCategory?.slice(-1) || '?'})` : 'Chip'}
                    </span>
                    <span class="col-right">{formatPED(alloc.cost)}</span>
                  </div>
                {/each}
              </div>
            </div>
            <div class="optimizer-note">
              Cost estimates use placeholder conversion (1 skill point = 1 PED).
              Chip-out loss: {CHIP_OUT_LOSS_PERCENT}%.
            </div>
          {:else if (targetType === 'profession' && targetProfession) || (targetType === 'hp' && targetHPValue > 0)}
            <div class="optimizer-empty">Set a target {targetType === 'hp' ? 'HP' : 'level'} above the current value to see optimization.</div>
          {:else}
            <div class="optimizer-empty">Select a target to calculate the cheapest path.</div>
          {/if}
          </div>
          </div>
        </div>
        </div>
      </div>
    </div>
  </div>
</WikiPage>

<!-- Import Dialog -->
{#if showImportDialog}
  <div class="dialog-overlay" on:click|self={() => showImportDialog = false} on:keydown={(e) => e.key === 'Escape' && (showImportDialog = false)} role="presentation">
    <div class="dialog">
      <div class="dialog-header">
        <h2>Import Skills</h2>
        <button class="dialog-close" on:click={() => showImportDialog = false}>&times;</button>
      </div>
      <div class="dialog-body">
        {#if !importPreview}
          <div class="import-tabs">
            <button class="import-tab" class:active={importMode === 'paste'} on:click={() => importMode = 'paste'}>Paste JSON</button>
            <button class="import-tab" class:active={importMode === 'manual'} on:click={() => importMode = 'manual'}>Manual Entry</button>
          </div>

          {#if importMode === 'paste'}
            <p class="dialog-hint">Paste your skill data as JSON. Supports both Nexus format and external kebab-case format.</p>
            <textarea
              class="import-textarea"
              bind:value={importText}
              placeholder="Paste skill data as JSON..."
              rows="10"
            ></textarea>
            {#if importError}
              <div class="import-error">{importError}</div>
            {/if}
            <div class="dialog-actions">
              <button class="btn-secondary" on:click={() => showImportDialog = false}>Cancel</button>
              <button class="btn-primary" on:click={handleImportPreview}>Preview</button>
            </div>
          {:else}
            <p class="dialog-hint">Search and set individual skill values.</p>
            <div class="manual-search">
              <input type="text" bind:value={manualSearchTerm} placeholder="Search skills..." class="manual-search-input" />
            </div>
            <div class="manual-skill-list">
              {#each skillsMetadata.filter(s => !manualSearchTerm || s.Name.toLowerCase().includes(manualSearchTerm.toLowerCase())).slice(0, 50) as skill}
                <div class="manual-skill-row">
                  <span class="manual-skill-name" class:hidden-skill={skill.IsHidden}>{skill.Name}</span>
                  <input
                    type="number"
                    class="manual-skill-input"
                    value={manualSkillEdits[skill.Name] ?? skillValues[skill.Name] ?? 0}
                    on:change={(e) => { manualSkillEdits = { ...manualSkillEdits, [skill.Name]: Number(e.target.value) || 0 }; }}
                    min="0"
                    step="0.0001"
                  />
                </div>
              {/each}
            </div>
            {#if importError}
              <div class="import-error">{importError}</div>
            {/if}
            <div class="dialog-actions">
              <button class="btn-secondary" on:click={() => showImportDialog = false}>Cancel</button>
              <button class="btn-primary" on:click={handleManualImport} disabled={Object.keys(manualSkillEdits).length === 0}>
                Apply {Object.keys(manualSkillEdits).length} Change{Object.keys(manualSkillEdits).length !== 1 ? 's' : ''}
              </button>
            </div>
          {/if}
        {:else}
          <div class="import-preview">
            <div class="preview-stats">
              <span>Format: <strong>{importPreview.format}</strong></span>
              <span>Skills with values: <strong>{importPreview.skillCount}</strong></span>
              {#if importPreview.health != null}
                <span>Health: <strong>{importPreview.health}</strong></span>
              {/if}
            </div>
            {#if importPreview.unrecognized?.length > 0}
              <div class="preview-warning">
                {importPreview.unrecognized.length} unrecognized skill(s): {importPreview.unrecognized.slice(0, 5).join(', ')}{importPreview.unrecognized.length > 5 ? '...' : ''}
              </div>
            {/if}
            <div class="preview-diff">
              <span class="diff-changed">{importPreview.diff.changed.length} changed</span>
              <span class="diff-added">{importPreview.diff.added} new</span>
              <span class="diff-unchanged">{importPreview.diff.unchanged} unchanged</span>
            </div>
            {#if importPreview.diff.changed.length > 0}
              <div class="preview-changes">
                {#each importPreview.diff.changed.slice(0, 20) as ch}
                  <div class="change-row">
                    <span>{ch.name}</span>
                    <span class="change-values">{formatNumber(ch.oldValue)} &rarr; {formatNumber(ch.newValue)}</span>
                  </div>
                {/each}
                {#if importPreview.diff.changed.length > 20}
                  <div class="change-more">...and {importPreview.diff.changed.length - 20} more</div>
                {/if}
              </div>
            {/if}
          </div>
          <div class="dialog-actions">
            <button class="btn-secondary" on:click={() => { importPreview = null; }}>Back</button>
            <button class="btn-primary" on:click={handleImportConfirm}>Confirm Import</button>
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<!-- Import History Panel -->
{#if showHistoryPanel}
  <div class="dialog-overlay" on:click|self={() => showHistoryPanel = false} on:keydown={(e) => e.key === 'Escape' && (showHistoryPanel = false)} role="presentation">
    <div class="dialog dialog-wide">
      <div class="dialog-header">
        <h2>Import History</h2>
        <button class="dialog-close" on:click={() => showHistoryPanel = false}>&times;</button>
      </div>
      <div class="dialog-body">
        {#if historyLoading}
          <div class="history-loading">Loading...</div>
        {:else if importHistory.length === 0}
          <div class="history-empty">No import history yet.</div>
        {:else}
          <div class="history-list">
            {#each importHistory as imp}
              <button class="history-item" on:click={() => toggleImportDeltas(imp.id)}>
                <div class="history-row">
                  <span class="history-date">{new Date(imp.imported_at).toLocaleString()}</span>
                  <span class="history-count">{imp.skill_count} skills</span>
                  <span class="history-value">{formatPED(Number(imp.total_value))} total</span>
                  {#if imp.summary}
                    <span class="history-summary">
                      {#if imp.summary.changed > 0}<span class="diff-changed">{imp.summary.changed} changed</span>{/if}
                      {#if imp.summary.added > 0}<span class="diff-added">{imp.summary.added} new</span>{/if}
                    </span>
                  {/if}
                  <span class="history-expand">{expandedImportId === imp.id ? '▼' : '▶'}</span>
                </div>
                {#if expandedImportId === imp.id && expandedDeltas.length > 0}
                  <div class="history-deltas" on:click|stopPropagation on:keydown|stopPropagation role="presentation">
                    {#each expandedDeltas as d}
                      {@const change = Number(d.new_value) - Number(d.old_value)}
                      <div class="delta-row">
                        <span>{d.skill_name}</span>
                        <span class="delta-values">
                          {formatNumber(Number(d.old_value))} &rarr; {formatNumber(Number(d.new_value))}
                          <span class="delta-change" class:positive={change > 0} class:negative={change < 0}>
                            {change > 0 ? '+' : ''}{formatNumber(change)}
                          </span>
                        </span>
                      </div>
                    {/each}
                  </div>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  /* ─── Sidebar extras ─── */
  .sidebar-root {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .item-value {
    font-variant-numeric: tabular-nums;
    color: var(--text-muted);
    font-weight: 500;
    margin-left: 8px;
    flex-shrink: 0;
    font-size: 12px;
  }

  /* Hidden skills */
  .sidebar-item.hidden-skill .item-name {
    color: #b388ff;
  }

  .sidebar-item.hidden-skill.active .item-name {
    color: #ce93d8;
  }

  /* ─── Unlock buttons ─── */
  .unlock-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 2px 4px;
    border: 1px solid rgba(179, 136, 255, 0.3);
    border-radius: 4px;
    background: rgba(179, 136, 255, 0.1);
    color: #b388ff;
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .unlock-btn:hover {
    background: rgba(179, 136, 255, 0.25);
    border-color: #b388ff;
  }

  .unlock-btn.unlocked {
    background: rgba(76, 175, 80, 0.1);
    border-color: rgba(76, 175, 80, 0.3);
    color: var(--success-color);
  }

  .unlock-btn.unlocked:hover {
    background: rgba(76, 175, 80, 0.25);
    border-color: var(--success-color);
  }

  .sidebar-unlock {
    padding: 4px 5px;
    margin-left: 4px;
  }

  .detail-unlock {
    padding: 4px 8px;
    font-size: 12px;
  }

  .detail-unlock span {
    font-size: 11px;
    font-weight: 600;
  }

  /* ─── Target button ─── */
  .target-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .target-btn:hover {
    background: var(--accent-color);
    border-color: var(--accent-color);
    color: white;
  }

  /* Unlock row with actions in profession/skill detail */
  .unlock-row-actions {
    align-items: center;
  }

  .unlock-row-actions .clickable {
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: 0;
    font: inherit;
  }

  .unlock-row-actions .clickable:hover {
    color: var(--accent-color);
  }

  .detail-badge.is-hidden {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 3px;
    background: rgba(179, 136, 255, 0.2);
    color: #b388ff;
    text-transform: uppercase;
  }

  .hidden-skill-detail h2 {
    color: #ce93d8;
  }

  /* ─── Unlocks view ─── */
  .unlocks-view {
    padding: 0;
  }

  .unlocks-header {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px 20px 12px;
    border-bottom: 1px solid var(--border-color);
  }

  .unlocks-header h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .unlocks-count {
    font-size: 13px;
    color: var(--text-muted);
    padding: 2px 8px;
    background: var(--secondary-color);
    border-radius: 10px;
  }

  .unlocks-table {
    overflow-y: auto;
  }

  .unlocks-table-header {
    display: grid;
    grid-template-columns: 1fr 1fr 120px 60px;
    gap: 8px;
    padding: 8px 20px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-color);
    position: sticky;
    top: 0;
    background: var(--primary-color);
    z-index: 1;
  }

  .unlock-row {
    display: grid;
    grid-template-columns: 1fr 1fr 120px 60px;
    gap: 8px;
    padding: 6px 20px;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    transition: background 0.1s;
  }

  .unlock-row:hover {
    background: var(--hover-color);
  }

  .unlock-row.unlocked {
    opacity: 0.5;
  }

  .unlock-row.unlocked:hover {
    opacity: 0.8;
  }

  .unlock-skill-name {
    background: none;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    padding: 0;
    font: inherit;
    font-size: 13px;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .unlock-skill-name:hover {
    color: var(--accent-color);
  }

  .unlock-prof-cell {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .unlock-prof-link {
    background: none;
    border: none;
    color: var(--text-color);
    cursor: pointer;
    padding: 0;
    font: inherit;
    font-size: 12px;
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .unlock-prof-link:hover {
    color: var(--accent-color);
  }

  .unlock-prof-level {
    font-size: 11px;
    color: var(--text-muted);
  }

  .unlock-progress-cell {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .unlock-progress-bar {
    flex: 1;
    height: 6px;
    background: var(--secondary-color);
    border-radius: 3px;
    overflow: hidden;
  }

  .unlock-progress-fill {
    height: 100%;
    background: var(--accent-color);
    border-radius: 3px;
    transition: width 0.3s ease;
    min-width: 1px;
  }

  .unlock-progress-pct {
    font-size: 10px;
    color: var(--text-muted);
    min-width: 28px;
    text-align: right;
  }

  .unlock-actions {
    display: flex;
    align-items: center;
    gap: 4px;
    justify-content: flex-end;
  }

  .sidebar-filters {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .sidebar-select {
    flex: 1;
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--input-bg, var(--secondary-color));
    color: var(--text-color);
    font-size: 12px;
  }

  .zero-toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
    cursor: pointer;
    white-space: nowrap;
  }

  .zero-toggle input { margin: 0; }

  /* ─── Header extras ─── */
  :global(.tool-header-actions .action-btn.active) {
    background: var(--accent-color);
    color: white;
  }

  .source-toggle {
    display: flex;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .toggle-btn {
    padding: 4px 10px;
    border: none;
    background: var(--secondary-color);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 12px;
    transition: all 0.15s;
  }

  .toggle-btn:hover { color: var(--text-color); }
  .toggle-btn.active { background: var(--accent-color); color: white; }

  .save-indicator { font-size: 11px; padding: 2px 6px; border-radius: 3px; }
  .save-indicator.saving { color: var(--text-muted); }
  .save-indicator.error { color: var(--error-color); }

  /* ─── Import Prompt ─── */
  .import-prompt {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--warning-bg);
    border: 1px solid var(--warning-color);
    border-radius: 6px;
    font-size: 13px;
    color: var(--text-color);
    flex-shrink: 0;
  }

  .import-prompt span { flex: 1; }

  /* ─── Main Content Layout ─── */
  .skills-content {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    padding: 12px;
    gap: 12px;
    box-sizing: border-box;
  }

  /* ─── Summary ─── */
  .summary-bar {
    display: flex;
    gap: 16px;
    padding: 8px 12px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    align-items: center;
    flex-wrap: wrap;
    flex-shrink: 0;
  }

  .summary-item {
    display: flex;
    align-items: baseline;
    gap: 6px;
  }

  .summary-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
  .summary-value { font-size: 16px; font-weight: 700; color: var(--text-color); font-variant-numeric: tabular-nums; }

  /* ─── Detail + Optimizer wrapper ─── */
  .detail-optimizer-wrapper {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    transition: gap 0.3s ease;
  }

  .detail-optimizer-wrapper.optimizer-open {
    gap: 0;
  }

  /* ─── Detail Area ─── */
  .detail-area {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 16px;
    transition: flex 0.3s ease, opacity 0.3s ease, padding 0.3s ease, border-width 0.3s ease;
  }

  .optimizer-open .detail-area {
    flex: 0 0 0px;
    opacity: 0;
    overflow: hidden;
    padding: 0;
    border-width: 0;
  }

  .detail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }

  .detail-title {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .detail-header h2 { margin: 0; font-size: 1.25rem; color: var(--text-color); }

  .detail-category {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 3px;
    background: var(--hover-color);
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .detail-stats {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    align-items: flex-start;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .stat-label { font-size: 10px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; }
  .stat-value { font-size: 18px; font-weight: 700; color: var(--text-color); font-variant-numeric: tabular-nums; }
  .stat.highlight .stat-value { color: var(--accent-color); }

  .detail-columns {
    display: flex;
    gap: 16px;
  }

  .detail-columns .detail-section {
    flex: 1;
    min-width: 0;
  }

  .detail-section { margin-bottom: 16px; }
  .detail-section h3 {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    margin: 0 0 8px 0;
    letter-spacing: 0.5px;
  }

  .detail-table { display: flex; flex-direction: column; }

  .detail-table-header {
    display: grid;
    grid-template-columns: 1fr 60px 80px;
    gap: 8px;
    padding: 4px 8px;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    border-bottom: 1px solid var(--border-color);
  }

  .detail-table-row {
    display: grid;
    grid-template-columns: 1fr 60px 80px;
    gap: 8px;
    padding: 5px 8px;
    font-size: 12px;
    align-items: center;
    border: none;
    border-bottom: 1px solid var(--border-color);
    background: transparent;
    color: var(--text-color);
    width: 100%;
    text-align: left;
  }

  .detail-table.cols-4 .detail-table-header,
  .detail-table.cols-4 .detail-table-row {
    grid-template-columns: 1fr 55px 65px 65px;
  }

  .detail-table.cols-2 .detail-table-header,
  .detail-table.cols-2 .detail-table-row {
    grid-template-columns: 50px 1fr;
  }

  .detail-table.cols-3 .detail-table-header,
  .detail-table.cols-3 .detail-table-row {
    grid-template-columns: 60px 1fr 30px;
  }

  .detail-table-row.clickable { cursor: pointer; }
  .detail-table-row.clickable:hover { background: var(--hover-color); }

  .col-right { text-align: right; font-variant-numeric: tabular-nums; }

  .prof-link, .skill-link { color: var(--accent-color); }
  .prof-link:hover, .skill-link:hover { text-decoration: underline; }

  .weight-bar-container {
    display: block;
    height: 3px;
    background: var(--border-color);
    border-radius: 2px;
    margin-top: 3px;
    overflow: hidden;
  }

  .weight-bar {
    display: block;
    height: 100%;
    background: var(--accent-color);
    border-radius: 2px;
    transition: width 0.3s;
  }

  .unlock-level {
    display: inline-block;
    padding: 1px 6px;
    background: var(--accent-color);
    color: white;
    border-radius: 3px;
    font-size: 11px;
    font-weight: 600;
    min-width: 30px;
    text-align: center;
  }

  .detail-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    text-align: center;
    gap: 8px;
  }

  .detail-empty p { margin: 0; }
  .detail-hint { font-size: 13px; }

  /* ─── Optimizer ─── */
  .optimizer-section {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
    flex-shrink: 0;
    transition: flex 0.3s ease;
  }

  .optimizer-section.expanded {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .optimizer-toggle {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    border: none;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    width: 100%;
    font-size: 14px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .optimizer-toggle:hover { background: var(--hover-color); }

  .toggle-chevron {
    transition: transform 0.25s ease;
    color: var(--text-muted);
  }

  .toggle-chevron.open { transform: rotate(180deg); }

  .optimizer-content-wrapper {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows 0.3s ease;
  }

  .optimizer-content-wrapper.visible {
    grid-template-rows: 1fr;
    flex: 1;
    min-height: 0;
  }

  .optimizer-content {
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
  }

  .optimizer-content-wrapper.visible .optimizer-content {
    padding: 12px 14px;
    border-top: 1px solid var(--border-color);
    overflow-y: auto;
  }

  .optimizer-controls {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    align-items: flex-end;
  }

  .control-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .control-group label, .control-label {
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .control-group select, .control-group input {
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 13px;
    height: 32px;
    box-sizing: border-box;
  }

  .control-group select { min-width: 220px; }
  .control-group input[type="number"] { width: 80px; }

  .target-toggle, .mu-buttons {
    display: flex;
    gap: 2px;
    height: 32px;
    align-items: stretch;
  }

  .mu-btn {
    padding: 4px 8px;
    font-size: 11px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
  }

  .mu-btn:hover { color: var(--text-color); }
  .mu-btn.active { background: var(--accent-color); color: white; border-color: var(--accent-color); }
  .mu-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ─── Optimizer Panels (side-by-side on wide screens) ─── */
  .optimizer-panels {
    display: flex;
    flex-direction: column;
    gap: 12px;
    flex: 1;
    min-height: 0;
  }

  .optimizer-panels > .method-config {
    flex: 1;
    min-width: 0;
  }

  .optimizer-results {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
  }

  /* ─── Method Config ─── */
  .method-config {
    border: 1px solid var(--border-color);
    border-radius: 4px;
    overflow: hidden;
  }

  .method-config-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 10px;
    background: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
  }

  .method-config-header h4 {
    margin: 0;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .bulk-toggle {
    display: flex;
    gap: 2px;
  }

  .method-table-header {
    display: grid;
    grid-template-columns: 1fr 60px 50px 55px auto;
    gap: 6px;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    border-bottom: 1px solid var(--border-color);
  }

  .method-list {
    max-height: 240px;
    overflow-y: auto;
  }

  .method-row {
    display: grid;
    grid-template-columns: 1fr 60px 50px 55px auto;
    gap: 6px;
    align-items: center;
    padding: 4px 10px;
    border-bottom: 1px solid var(--border-color);
    font-size: 12px;
  }

  .method-row:last-child { border-bottom: none; }

  .method-skill-name {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .method-cell {
    font-size: 11px;
    font-variant-numeric: tabular-nums;
  }

  .mu-input {
    width: 100%;
    padding: 2px 4px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 11px;
    text-align: right;
    box-sizing: border-box;
  }

  .method-buttons {
    display: flex;
    gap: 2px;
    flex-shrink: 0;
  }

  .method-btn {
    padding: 2px 6px;
    font-size: 10px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s;
  }

  .method-btn:hover:not(:disabled) { color: var(--text-color); }
  .method-btn.active { background: var(--accent-color); color: white; border-color: var(--accent-color); }
  .method-btn.none.active { background: var(--text-muted); color: white; border-color: var(--text-muted); }
  .method-btn:disabled { opacity: 0.3; cursor: not-allowed; }

  .warning-icon {
    color: var(--warning-color);
    font-size: 12px;
    margin-left: 4px;
    cursor: help;
  }

  .optimizer-summary {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    background: var(--hover-color);
    border-radius: 4px;
    font-size: 13px;
    color: var(--text-color);
    flex-wrap: wrap;
    gap: 8px;
  }

  .optimizer-summary strong { color: var(--accent-color); }

  .optimizer-warning {
    padding: 6px 10px;
    background: var(--warning-bg);
    color: var(--warning-color);
    border-radius: 4px;
    font-size: 12px;
  }

  .optimizer-table-scroll { overflow-x: auto; }
  .optimizer-table { display: flex; flex-direction: column; min-width: 540px; }

  .optimizer-table-header {
    display: grid;
    grid-template-columns: 1fr 70px 70px 50px 120px 70px;
    gap: 8px;
    padding: 4px 8px;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    border-bottom: 1px solid var(--border-color);
  }

  .optimizer-table-row {
    display: grid;
    grid-template-columns: 1fr 70px 70px 50px 120px 70px;
    gap: 8px;
    padding: 5px 8px;
    font-size: 12px;
    border-bottom: 1px solid var(--border-color);
    align-items: center;
  }

  .method-badge {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 3px;
  }

  .method-badge.codex { background: rgba(60, 179, 113, 0.2); color: var(--success-color); }
  .method-badge.chip { background: rgba(74, 158, 255, 0.15); color: var(--accent-color); }

  .optimizer-empty, .optimizer-note {
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    padding: 8px;
  }

  .optimizer-note { font-style: italic; }

  /* ─── Dialog ─── */
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1100;
    padding: 20px;
  }

  .dialog {
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 100%;
    max-width: 540px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
  }

  .dialog-wide { max-width: 700px; }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .dialog-header h2 { margin: 0; font-size: 1.1rem; color: var(--text-color); }

  .dialog-close {
    border: none;
    background: transparent;
    font-size: 1.5rem;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0 4px;
    line-height: 1;
  }

  .dialog-close:hover { color: var(--text-color); }

  .dialog-body {
    padding: 16px;
    overflow-y: auto;
    flex: 1;
    min-height: 0;
  }

  .dialog-hint { font-size: 13px; color: var(--text-muted); margin: 0 0 12px 0; }

  .import-textarea {
    width: 100%;
    padding: 10px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
    color: var(--text-color);
    font-family: monospace;
    font-size: 12px;
    resize: vertical;
    box-sizing: border-box;
  }

  .import-error {
    margin-top: 8px;
    padding: 6px 10px;
    background: rgba(239, 68, 68, 0.1);
    color: var(--error-color);
    border-radius: 4px;
    font-size: 12px;
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
  }

  .btn-primary {
    background: var(--accent-color);
    color: white;
    border: 1px solid var(--accent-color);
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .btn-primary:hover:not(:disabled) { background: var(--button-accent-hover, #3a8eef); }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

  .btn-secondary {
    background: transparent;
    color: var(--text-color);
    border: 1px solid var(--border-color);
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: background 0.15s;
  }

  .btn-secondary:hover { background: var(--hover-color); }

  /* Import Tabs */
  .import-tabs {
    display: flex;
    gap: 2px;
    margin-bottom: 12px;
    border-bottom: 1px solid var(--border-color);
  }

  .import-tab {
    padding: 8px 16px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: all 0.15s;
  }

  .import-tab:hover { color: var(--text-color); }
  .import-tab.active { color: var(--accent-color); border-bottom-color: var(--accent-color); }

  /* Manual Entry */
  .manual-search { margin-bottom: 8px; }

  .manual-search-input {
    width: 100%;
    padding: 8px 10px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
    color: var(--text-color);
    font-size: 13px;
    box-sizing: border-box;
  }

  .manual-search-input:focus { outline: none; border-color: var(--accent-color); }

  .manual-skill-list {
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .manual-skill-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 10px;
    border-bottom: 1px solid var(--border-color);
    font-size: 13px;
  }

  .manual-skill-row:last-child { border-bottom: none; }

  .manual-skill-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-right: 8px;
    color: var(--text-color);
  }

  .manual-skill-name.hidden-skill { color: #b388ff; }

  .manual-skill-input {
    width: 90px;
    padding: 4px 6px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 12px;
    text-align: right;
    flex-shrink: 0;
    box-sizing: border-box;
  }

  .manual-skill-input:focus { outline: none; border-color: var(--accent-color); }

  /* ─── Import Preview ─── */
  .import-preview { display: flex; flex-direction: column; gap: 10px; }

  .preview-stats {
    display: flex;
    gap: 16px;
    font-size: 13px;
    color: var(--text-color);
    flex-wrap: wrap;
  }

  .preview-warning {
    padding: 6px 10px;
    background: var(--warning-bg);
    color: var(--warning-color);
    border-radius: 4px;
    font-size: 12px;
  }

  .preview-diff {
    display: flex;
    gap: 12px;
    font-size: 13px;
  }

  .diff-changed { color: var(--warning-color); }
  .diff-added { color: var(--success-color); }
  .diff-unchanged { color: var(--text-muted); }

  .preview-changes {
    max-height: 200px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .change-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 8px;
    font-size: 12px;
    border-bottom: 1px solid var(--border-color);
  }

  .change-values { font-variant-numeric: tabular-nums; color: var(--text-muted); }
  .change-more { padding: 4px 8px; font-size: 12px; color: var(--text-muted); text-align: center; }

  /* ─── History ─── */
  .history-loading, .history-empty { padding: 20px; text-align: center; color: var(--text-muted); }

  .history-list { display: flex; flex-direction: column; }

  .history-item {
    border: none;
    background: transparent;
    color: var(--text-color);
    cursor: pointer;
    width: 100%;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
    padding: 0;
  }

  .history-item:hover { background: var(--hover-color); }

  .history-row {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 8px 10px;
    font-size: 12px;
    flex-wrap: wrap;
  }

  .history-date { font-weight: 500; }
  .history-count, .history-value { color: var(--text-muted); }
  .history-summary { display: flex; gap: 8px; }
  .history-expand { margin-left: auto; color: var(--text-muted); font-size: 10px; }

  .history-deltas {
    padding: 4px 10px 8px 10px;
    background: var(--hover-color);
  }

  .delta-row {
    display: flex;
    justify-content: space-between;
    padding: 3px 0;
    font-size: 11px;
    border-bottom: 1px solid var(--border-color);
  }

  .delta-values { font-variant-numeric: tabular-nums; color: var(--text-muted); display: flex; gap: 6px; }
  .delta-change.positive { color: var(--success-color); }
  .delta-change.negative { color: var(--error-color); }

  /* ─── Side-by-side optimizer panels on wide screens ─── */
  @media (min-width: 1100px) {
    .optimizer-panels {
      flex-direction: row;
    }

    .optimizer-panels > .method-config,
    .optimizer-results {
      min-width: 340px;
    }

    .method-list {
      max-height: none;
    }
  }

  /* ─── Responsive ─── */
  @media (max-width: 900px) {
    .skills-content { padding: 8px; gap: 8px; }
    .summary-bar { gap: 10px; padding: 6px 10px; }
    .summary-label { font-size: 10px; }
    .summary-value { font-size: 14px; }
    .detail-header { flex-direction: column; gap: 8px; }
    .detail-columns { flex-direction: column; }
    .optimizer-controls { flex-direction: column; align-items: stretch; gap: 8px; }
    .control-group select { min-width: 0; width: 100%; }
    .control-group input[type="number"] { width: 100%; }
    .target-toggle .mu-btn, .mu-buttons .mu-btn { flex: 1; justify-content: center; }

    /* On mobile, hide collapsed optimizer (toggle is in header bar) */
    .optimizer-section:not(.expanded) { display: none; }
  }
</style>
