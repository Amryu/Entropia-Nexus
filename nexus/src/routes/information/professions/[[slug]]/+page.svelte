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
  import { sanitizeHtml } from '$lib/sanitize';

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

  export let data;

  $: profession = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: isCreateMode = data.isCreateMode || false;
  $: canCreateNew = data.canCreateNew ?? true;
  $: userPendingCreates = data.userPendingCreates || [];

  $: userPendingUpdates = data.userPendingUpdates || [];
  $: professionEntityId = profession?.Id ?? profession?.ItemId;
  $: userPendingUpdate = getLatestPendingUpdate(userPendingUpdates, professionEntityId);
  $: resolvedPendingChange = userPendingUpdate || pendingChange;
  $: canUsePendingChange = !!(resolvedPendingChange && user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve')));
  // Can edit if user is verified or admin
  $: canEdit = user?.verified || user?.grants?.includes('wiki.edit');

  // Build navigation items from professions
  $: navItems = allItems;

  // Empty entity template for create mode
  const emptyEntity = {
    Name: '',
    Description: '',
    Category: null,
    Skills: [],
    Unlocks: []
  };

  // Initialize edit state when entity or user changes
  $: if (user) {
    const entity = isCreateMode ? (existingChange?.data || emptyEntity) : profession;
    if (entity) {
      const editChange = isCreateMode ? existingChange : (canUsePendingChange ? resolvedPendingChange : null);
      initEditState(entity, 'Profession', isCreateMode, editChange);
    }
  }

  // Set existing pending change when data loads
  $: if (resolvedPendingChange) {
    setExistingPendingChange(resolvedPendingChange);
    // Auto-enable viewing pending change for author or admin
    if (user && (resolvedPendingChange.author_id === user.id || user?.grants?.includes('wiki.approve'))) {
      setViewingPendingChange(true);
    }
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Active entity: what we display (edit mode → currentEntity, pending view → pending data, default → profession)
  $: activeEntity = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.changes)
      ? applyChangesToEntity(profession, $existingPendingChange.changes)
      : profession;

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

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Information', href: '/information' },
    { label: 'Professions', href: '/information/professions' },
    ...(activeEntity ? [{ label: activeEntity.Name || 'New Profession' }] : [])
  ];

  // SEO
  $: seoDescription = activeEntity?.Description ||
    `${activeEntity?.Name || 'Profession'} - ${activeEntity?.Category?.Name || ''} profession in Entropia Universe.`;

  $: canonicalUrl = profession
    ? `https://entropianexus.com/information/professions/${encodeURIComponentSafe(profession.Name)}`
    : 'https://entropianexus.com/information/professions';

  // Image URL for SEO
  $: entityImageUrl = profession?.Id ? `/api/img/profession/${profession.Id}` : null;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    skills: true,
    unlocks: true
  };

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

  // Reactive calculations
  $: skillCount = getSkillCount(activeEntity);
  $: unlockCount = getUnlockCount(activeEntity);
  $: totalWeight = getTotalWeight(activeEntity);
  $: topSkill = getTopSkill(activeEntity);
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
        <div class="stats-section tier-1">
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
              on:change={(e) => updateField('Description', e.detail)}
              placeholder="Enter profession description..."
            />
          {:else if activeEntity?.Description}
            <div class="description-content">{@html sanitizeHtml(activeEntity.Description)}</div>
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
          on:toggle={savePanelStates}
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
            on:toggle={savePanelStates}
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
  .pending-change-banner {
    background: linear-gradient(135deg, #f59e0b22 0%, #f59e0b11 100%);
    border: 1px solid #f59e0b44;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .banner-icon {
    font-size: 18px;
  }

  .banner-text {
    flex: 1;
    color: var(--text-color);
    font-size: 14px;
  }

  .banner-toggle {
    padding: 6px 12px;
    font-size: 12px;
    background: var(--accent-color);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: opacity 0.2s;
  }

  .banner-toggle:hover {
    opacity: 0.9;
  }

  .layout-a {
    position: relative;
    width: 100%;
  }

  /* Clearfix to ensure spacing after floated infobox */
  .layout-a::after {
    content: '';
    display: block;
    clear: both;
  }

  /* Floating infobox - Wikipedia style */
  .wiki-infobox-float {
    float: right;
    width: 300px;
    margin: 0 0 0 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
  }

  .infobox-header {
    text-align: center;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .infobox-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-color);
  }

  .infobox-subtitle {
    font-size: 12px;
    color: var(--text-muted, #999);
    margin-top: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .category-badge {
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border-radius: 4px;
    text-transform: uppercase;
  }

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

  /* Stats sections */
  .stats-section {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .stats-section.tier-1 {
    background: linear-gradient(135deg, #3a6d99 0%, #2d5577 100%);
    padding: 14px;
  }

  .stats-section.tier-1 .stat-row.primary {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    padding: 8px 12px;
    margin-bottom: 6px;
  }

  .stats-section.tier-1 .stat-row.primary:last-child {
    margin-bottom: 0;
  }

  .stats-section.tier-1 .stat-label {
    color: rgba(255, 255, 255, 0.9);
    font-size: 13px;
    text-transform: uppercase;
    font-weight: 500;
  }

  .stats-section.tier-1 .stat-value {
    color: #e8f4ff;
    font-size: 18px;
    font-weight: 700;
  }

  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted, #999);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 0 0 10px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .stat-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 4px 0;
    font-size: 13px;
  }

  .stat-label {
    color: var(--text-muted, #999);
  }

  .stat-value {
    font-weight: 500;
    color: var(--text-color);
  }

  .skill-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .skill-link:hover {
    text-decoration: underline;
  }

  .wiki-article {
    overflow: hidden; /* Contains floated infobox */
  }

  .article-title {
    font-size: 32px;
    font-weight: 600;
    margin: 0 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--accent-color, #4a9eff);
  }

  .description-panel {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .description-content {
    font-size: 15px;
    line-height: 1.6;
    color: var(--text-color);
  }

  .description-content.placeholder {
    color: var(--text-muted, #999);
    font-style: italic;
  }

  .no-selection {
    text-align: center;
    padding: 60px 20px;
  }

  .no-selection h2 {
    font-size: 28px;
    margin-bottom: 12px;
  }

  .no-selection p {
    color: var(--text-muted, #999);
    margin: 8px 0;
  }

  .no-selection .hint {
    font-size: 14px;
    margin-top: 16px;
  }

  /* Tablet adjustments */
  @media (max-width: 1023px) {
    .wiki-infobox-float {
      width: 260px;
      margin-left: 16px;
      padding: 14px;
    }
  }

  /* Mobile adjustments */
  @media (max-width: 767px) {
    .layout-a {
      max-width: 100%;
    }

    .wiki-infobox-float {
      float: none;
      width: auto;
      margin: 0 0 16px 0;
    }

    /* Hide article title on mobile - redundant with infobox */
    .article-title {
      display: none;
    }

    .infobox-title {
      font-size: 16px;
    }
  }
</style>
