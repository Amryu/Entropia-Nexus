<!--
  @component Profession Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Supports full wiki editing.
  Infobox: Category, skill count, unlock count
  Article: Description → Skill Components → Skill Unlocks
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe, getLatestPendingUpdate } from '$lib/util';
  import { hasVisibleText } from '$lib/sanitize.js';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import PendingChangeBanner from '$lib/components/wiki/PendingChangeBanner.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  // Profession-specific components
  import ProfessionSkills from '$lib/components/wiki/professions/ProfessionSkills.svelte';
  import ProfessionUnlocks from '$lib/components/wiki/professions/ProfessionUnlocks.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';
  // Wiki edit state
  import {
    editMode,
    isCreateMode as createModeStore,
    initEditState,
    resetEditState,
    currentEntity,
    existingPendingChange,
    viewingPendingChange,
    setExistingPendingChange,
    setViewingPendingChange,
    updateField,
    changeMetadata
  } from '$lib/stores/wikiEditState.js';

  let { data } = $props();




  // Empty entity template for create mode
  const emptyEntity = {
    Name: '',
    Description: '',
    Category: null,
    Skills: [],
    Unlocks: []
  };




  // Helper to apply pending changes to entity for display
  function applyChangesToEntity(entity, changes) {
    if (!entity || !changes) return entity;
    const result = JSON.parse(JSON.stringify(entity));
    for (const [path, value] of Object.entries(changes)) {
      setNestedValue(result, path, value);
    }
    return result;
  }

  function setNestedValue(obj, path, value) {
    const keys = path.split('.');
    let current = obj;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) current[keys[i]] = {};
      current = current[keys[i]];
    }
    current[keys[keys.length - 1]] = value;
  }

  // Cleanup on destroy
  onDestroy(() => {
    resetEditState();
  });

  // Navigation filters - filter by category
  const navFilters = [
    {
      key: 'Category.Name',
      label: 'Category',
      values: [
        { value: 'Combat', label: 'Combat' },
        { value: 'Mindforce', label: 'Mindforce' },
        { value: 'Resource Collecting', label: 'Resource Collecting' },
        { value: 'Manufacturing', label: 'Manufacturing' },
        { value: 'Miscellaneous', label: 'Miscellaneous' },
      ]
    }
  ];

  const profColumnDefs = {
    category: {
      key: 'category',
      header: 'Category',
      width: '110px',
      filterPlaceholder: 'Combat',
      getValue: (item) => item.Category?.Name,
      format: (v) => v || '-'
    },
    skills: {
      key: 'skills',
      header: 'Skills',
      width: '55px',
      filterPlaceholder: '>5',
      getValue: (item) => item.Skills?.length || 0,
      format: (v) => v != null ? v : '-'
    },
    totalWeight: {
      key: 'totalWeight',
      header: 'Weight',
      width: '65px',
      filterPlaceholder: '>100',
      getValue: (item) => item.Skills?.reduce((sum, s) => sum + (s.Weight || 0), 0) || 0,
      format: (v) => v != null ? v : '-'
    },
    unlocks: {
      key: 'unlocks',
      header: 'Unlocks',
      width: '65px',
      filterPlaceholder: '>0',
      getValue: (item) => item.Unlocks?.length || 0,
      format: (v) => v != null ? v : '-'
    }
  };

  const navTableColumns = [
    profColumnDefs.category,
    profColumnDefs.skills,
    profColumnDefs.totalWeight
  ];

  const navFullWidthColumns = [
    ...navTableColumns,
    profColumnDefs.unlocks
  ];

  const allAvailableColumns = Object.values(profColumnDefs);

  // Category options for editing
  const categoryOptions = [
    { value: 'Combat', label: 'Combat' },
    { value: 'Mindforce', label: 'Mindforce' },
    { value: 'Resource Collecting', label: 'Resource Collecting' },
    { value: 'Manufacturing', label: 'Manufacturing' },
    { value: 'Miscellaneous', label: 'Miscellaneous' }
  ];





  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = $state({
    skills: true,
    unlocks: true
  });

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-profession-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-profession-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== PROFESSION CALCULATIONS ==========
  function getSkillCount(prof) {
    return prof?.Skills?.length || 0;
  }

  function getUnlockCount(prof) {
    return prof?.Unlocks?.length || 0;
  }

  function getTotalWeight(prof) {
    if (!prof?.Skills) return 0;
    return prof.Skills.reduce((sum, s) => sum + (s.Weight || 0), 0);
  }

  function getTopSkill(prof) {
    if (!prof?.Skills || prof.Skills.length === 0) return null;
    const sorted = [...prof.Skills].sort((a, b) => b.Weight - a.Weight);
    return sorted[0];
  }

  function getCategoryBadgeClass(categoryName) {
    if (!categoryName) return '';
    const lower = categoryName.toLowerCase().replace(/\s+/g, '-');
    return `category-${lower}`;
  }

  let profession = $derived(data.object);
  let user = $derived(data.session?.user);
  let allItems = $derived(data.allItems || []);
  let pendingChange = $derived(data.pendingChange);
  let existingChange = $derived(data.existingChange);
  let isCreateMode = $derived(data.isCreateMode || false);
  let canCreateNew = $derived(data.canCreateNew ?? true);
  let userPendingCreates = $derived(data.userPendingCreates || []);
  let userPendingUpdates = $derived(data.userPendingUpdates || []);
  let professionEntityId = $derived(profession?.Id ?? profession?.ItemId);
  let userPendingUpdate = $derived(getLatestPendingUpdate(userPendingUpdates, professionEntityId));
  let resolvedPendingChange = $derived(userPendingUpdate || pendingChange);
  let canUsePendingChange = $derived(!!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))));
  // Can edit if user is verified or admin
  let canEdit = $derived(user?.verified || user?.grants?.includes('wiki.edit'));
  // Build navigation items from professions
  let navItems = $derived(allItems);
  // Initialize edit state when entity or user changes
  $effect(() => {
    if (user) {
      const entity = isCreateMode ? (existingChange?.data || emptyEntity) : profession;
      if (entity) {
        const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
        initEditState(entity, 'Profession', isCreateMode, editChange);
      }
    }
  });
  // Set existing pending change when data loads
  $effect(() => {
    if (resolvedPendingChange) {
      setExistingPendingChange(resolvedPendingChange);
    } else {
      setExistingPendingChange(null);
      setViewingPendingChange(false);
    }
  });
  // Active entity: what we display (edit mode → currentEntity, pending view → pending data, default → profession)
  let activeEntity = $derived($editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.changes)
      ? applyChangesToEntity(profession, $existingPendingChange.changes)
      : profession);
  // Breadcrumbs
  let breadcrumbs = $derived([
    { label: 'Information', href: '/information' },
    { label: 'Professions', href: '/information/professions' },
    ...(activeEntity ? [{ label: activeEntity.Name || 'New Profession' }] : [])
  ]);
  // SEO
  let seoDescription = $derived(activeEntity?.Description ||
    `${activeEntity?.Name || 'Profession'} - ${activeEntity?.Category?.Name || ''} profession in Entropia Universe.`);
  let canonicalUrl = $derived(profession
    ? `https://entropianexus.com/information/professions/${encodeURIComponentSafe(profession.Name)}`
    : 'https://entropianexus.com/information/professions');
  // Image URL for SEO
  let entityImageUrl = $derived(profession?.Id ? `/api/img/profession/${profession.Id}` : null);
  // Reactive calculations
  let skillCount = $derived(getSkillCount(activeEntity));
  let unlockCount = $derived(getUnlockCount(activeEntity));
  let totalWeight = $derived(getTotalWeight(activeEntity));
  let topSkill = $derived(getTopSkill(activeEntity));
</script>

<WikiSEO
  title={activeEntity?.Name || 'Professions'}
  description={seoDescription}
  entityType="Profession"
  entity={activeEntity}
  imageUrl={entityImageUrl}
  sidebarColumns={navTableColumns}
  sidebarEntity={activeEntity}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

  <WikiPage
    title="Professions"
    {breadcrumbs}
    entity={activeEntity}
    basePath="/information/professions"
    {navItems}
    {navFilters}
    {navTableColumns}
    {navFullWidthColumns}
    navAllAvailableColumns={allAvailableColumns}
    navPageTypeId="professions"
    {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  {#if activeEntity || isCreateMode}
    <!-- Pending Change Banner -->
    {#if $existingPendingChange && !$editMode}
      <PendingChangeBanner
        pendingChange={$existingPendingChange}
        viewing={$viewingPendingChange}
        onToggle={() => setViewingPendingChange(!$viewingPendingChange)}
        entityLabel="profession"
      />
    {/if}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeEntity?.Id}
            entityName={activeEntity?.Name}
            entityType="profession"
            {user}
            isEditMode={$editMode}
            {isCreateMode}
          />
          <div class="infobox-title">
            <InlineEdit
              value={activeEntity?.Name}
              path="Name"
              type="text"
              placeholder="Profession Name"
            />
          </div>
          <div class="infobox-subtitle">
            <span class="category-badge {getCategoryBadgeClass(activeEntity?.Category?.Name)}">
              {activeEntity?.Category?.Name || 'Unknown'}
            </span>
          </div>
        </div>

        <!-- Key Stats -->
        <div class="stats-section tier-1 tier-blue">
          <div class="stat-row primary">
            <span class="stat-label">Skills</span>
            <span class="stat-value">{skillCount}</span>
          </div>
          <div class="stat-row primary">
            <span class="stat-label">Total Weight</span>
            <span class="stat-value">{totalWeight}</span>
          </div>
          {#if unlockCount > 0}
            <div class="stat-row primary">
              <span class="stat-label">Unlocks</span>
              <span class="stat-value">{unlockCount} skill{unlockCount > 1 ? 's' : ''}</span>
            </div>
          {/if}
        </div>

        <!-- Top Skill -->
        {#if topSkill}
          <div class="stats-section">
            <h4 class="section-title">Top Contributor</h4>
            <div class="stat-row">
              <span class="stat-label">Skill</span>
              <span class="stat-value">
                <a href="/information/skills/{encodeURIComponentSafe(topSkill.Skill.Name)}" class="skill-link">
                  {topSkill.Skill.Name}
                </a>
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Weight</span>
              <span class="stat-value">{topSkill.Weight} ({((topSkill.Weight / totalWeight) * 100).toFixed(1)}%)</span>
            </div>
          </div>
        {/if}

        <!-- General Info -->
        <div class="stats-section">
          <h4 class="section-title">General</h4>
          <div class="stat-row">
            <span class="stat-label">Category</span>
            <span class="stat-value">
              {#if $editMode}
                <InlineEdit
                  value={activeEntity?.Category?.Name || ''}
                  path="Category.Name"
                  type="select"
                  options={categoryOptions}
                  placeholder="Select category"
                  required={true}
                />
              {:else}
                {activeEntity?.Category?.Name || 'N/A'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Hidden Skills</span>
            <span class="stat-value">
              {activeEntity?.Skills?.filter(s => s.Skill?.Properties?.IsHidden).length || 0}
            </span>
          </div>
        </div>
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          <InlineEdit
            value={activeEntity?.Name}
            path="Name"
            type="text"
            placeholder="Profession Name"
          />
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeEntity?.Description || ''}
              onchange={(data) => updateField('Description', data)}
              placeholder="Enter profession description..."
              showWaypoints={true}
            />
          {:else if hasVisibleText(activeEntity?.Description)}
            <div class="description-content">{@html activeEntity.Description}</div>
          {:else}
            <div class="description-content placeholder">
              {activeEntity?.Name || 'This profession'} is a {activeEntity?.Category?.Name?.toLowerCase() || ''} profession in Entropia Universe.
            </div>
          {/if}
        </div>
        <!-- Skill Components Section -->
        <DataSection
          title="Skill Components"
          icon=""
          bind:expanded={panelStates.skills}
          subtitle="{skillCount} skill{skillCount > 1 ? 's' : ''}"
          ontoggle={savePanelStates}
        >
          <ProfessionSkills skills={activeEntity?.Skills} />
        </DataSection>

        <!-- Skill Unlocks Section -->
        {#if activeEntity?.Unlocks && activeEntity.Unlocks.length > 0}
          <DataSection
            title="Skill Unlocks"
            icon=""
            bind:expanded={panelStates.unlocks}
            subtitle="{unlockCount} unlock{unlockCount > 1 ? 's' : ''}"
            ontoggle={savePanelStates}
          >
            <ProfessionUnlocks unlocks={activeEntity.Unlocks} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Professions</h2>
      <p>Select a profession from the list to view details.</p>
      <p class="hint">Professions are leveled by training their component skills.</p>
    </div>
  {/if}
</WikiPage>

<style>
  /* Category-specific colors */
  .category-badge.category-combat {
    background-color: #ef4444;
  }

  .category-badge.category-mindforce {
    background-color: #a855f7;
  }

  .category-badge.category-resource-collecting {
    background-color: #22c55e;
  }

  .category-badge.category-manufacturing {
    background-color: #f59e0b;
  }

  .category-badge.category-miscellaneous {
    background-color: #6b7280;
  }

</style>
