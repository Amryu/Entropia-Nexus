<!--
  @component Skill Wiki Page
  Wikipedia-style layout with floating infobox on the right side.
  Infobox: Category, HP increase, hidden/extractable status
  Article: Description → Affected Professions → Unlocked By

  Supports full wiki editing with wikiEditState integration.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';
  import { encodeURIComponentSafe } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  // Wiki components
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import WikiSEO from '$lib/components/wiki/WikiSEO.svelte';
  import DataSection from '$lib/components/wiki/DataSection.svelte';
  import InlineEdit from '$lib/components/wiki/InlineEdit.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';

  // Edit state management
  import {
    editMode,
    isCreateMode,
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

  // Skill-specific components
  import SkillProfessions from '$lib/components/wiki/skills/SkillProfessions.svelte';
  import SkillUnlockedBy from '$lib/components/wiki/skills/SkillUnlockedBy.svelte';

  // Image upload
  import EntityImageUpload from '$lib/components/wiki/EntityImageUpload.svelte';

  export let data;

  $: skill = data.object;
  $: user = data.session?.user;
  $: allItems = data.allItems || [];
  $: pendingChange = data.pendingChange;
  $: existingChange = data.existingChange;
  $: userPendingCreates = data.userPendingCreates || [];
  $: userPendingUpdates = data.userPendingUpdates || [];
  $: canCreateNew = data.canCreateNew ?? true;

  // Permission check - verified users can edit
  $: canEdit = user?.verified === true;

  // Empty entity template for create mode
  const emptySkill = {
    Id: null,
    Name: '',
    Category: { Name: null },
    Properties: {
      Description: null,
      HpIncrease: 0,
      IsHidden: false,
      IsExtractable: false
    },
    Professions: [],
    Unlocks: []
  };

  // Category options for select dropdown
  const categoryOptions = [
    { value: 'Attributes', label: 'Attributes' },
    { value: 'Beauty', label: 'Beauty' },
    { value: 'Combat', label: 'Combat' },
    { value: 'Construction', label: 'Construction' },
    { value: 'Defense', label: 'Defense' },
    { value: 'Design', label: 'Design' },
    { value: 'General', label: 'General' },
    { value: 'Information', label: 'Information' },
    { value: 'Medical', label: 'Medical' },
    { value: 'Mindforce', label: 'Mindforce' },
    { value: 'Mining', label: 'Mining' },
    { value: 'Science', label: 'Science' },
    { value: 'Social', label: 'Social' }
  ];

  // Initialize edit state when entity/user changes
  $: if (user) {
    if (data.isCreateMode) {
      const initialData = existingChange?.data || emptySkill;
      initEditState(initialData, 'Skill', true, existingChange);
    } else if (skill) {
      initEditState(skill, 'Skill', false);
    }
  }

  // Handle pending changes from API
  $: if (pendingChange) {
    setExistingPendingChange(pendingChange);
    if (user && (pendingChange.author_id === user.id || user.isAdmin)) {
      setViewingPendingChange(true);
    }
  } else {
    setExistingPendingChange(null);
    setViewingPendingChange(false);
  }

  // Active entity - use this everywhere in templates
  $: activeSkill = $editMode
    ? $currentEntity
    : ($viewingPendingChange && $existingPendingChange?.data)
      ? $existingPendingChange.data
      : skill;

  // Cleanup on unmount
  onDestroy(() => {
    resetEditState();
  });

  // Build navigation items from skills
  $: navItems = allItems;

  // Navigation filters - filter by category and hidden status
  const navFilters = [
    {
      key: 'Category.Name',
      label: 'Category',
      values: [
        { value: 'Attributes', label: 'Attributes' },
        { value: 'Beauty', label: 'Beauty' },
        { value: 'Combat', label: 'Combat' },
        { value: 'Construction', label: 'Construction' },
        { value: 'Defense', label: 'Defense' },
        { value: 'Design', label: 'Design' },
        { value: 'General', label: 'General' },
        { value: 'Information', label: 'Information' },
        { value: 'Medical', label: 'Medical' },
        { value: 'Mindforce', label: 'Mindforce' },
        { value: 'Mining', label: 'Mining' },
        { value: 'Science', label: 'Science' },
        { value: 'Social', label: 'Social' },
      ]
    },
    {
      key: 'Properties.IsHidden',
      label: 'Visibility',
      values: [
        { value: false, label: 'Visible' },
        { value: true, label: 'Hidden' },
      ]
    }
  ];

  // Breadcrumbs
  $: breadcrumbs = [
    { label: 'Information', href: '/information' },
    { label: 'Skills', href: '/information/skills' },
    ...(activeSkill?.Name ? [{ label: activeSkill.Name }] : data.isCreateMode ? [{ label: 'New Skill' }] : [])
  ];

  // SEO
  $: seoDescription = activeSkill?.Properties?.Description ||
    `${activeSkill?.Name || 'Skill'} - ${activeSkill?.Category?.Name || ''} skill in Entropia Universe.`;

  $: canonicalUrl = activeSkill?.Name
    ? `https://entropianexus.com/information/skills/${encodeURIComponentSafe(activeSkill.Name)}`
    : 'https://entropianexus.com/information/skills';

  // SEO Image URL (if entity has an image)
  $: entityImageUrl = skill?.Id ? `/api/img/skill/${skill.Id}` : null;

  // ========== PANEL STATE PERSISTENCE ==========
  let panelStates = {
    professions: true,
    unlocks: true
  };

  onMount(() => {
    try {
      const stored = localStorage.getItem('wiki-skill-panels');
      if (stored) {
        panelStates = { ...panelStates, ...JSON.parse(stored) };
      }
    } catch (e) {
      // localStorage not available
    }
  });

  function savePanelStates() {
    try {
      localStorage.setItem('wiki-skill-panels', JSON.stringify(panelStates));
    } catch (e) {
      // localStorage not available
    }
  }

  // ========== SKILL CALCULATIONS ==========
  function getProfessionCount(sk) {
    return sk?.Professions?.length || 0;
  }

  function getUnlockCount(sk) {
    return sk?.Unlocks?.length || 0;
  }

  function getCategoryBadgeClass(categoryName) {
    if (!categoryName) return '';
    const lower = categoryName.toLowerCase().replace(/\s+/g, '-');
    return `category-${lower}`;
  }

  // Reactive calculations using activeSkill
  $: professionCount = getProfessionCount(activeSkill);
  $: unlockCount = getUnlockCount(activeSkill);
  $: isHidden = activeSkill?.Properties?.IsHidden ?? false;
  $: isExtractable = activeSkill?.Properties?.IsExtractable ?? false;
  $: hpIncrease = activeSkill?.Properties?.HpIncrease || 0;
</script>

<WikiSEO
  title={activeSkill?.Name || 'Skills'}
  description={seoDescription}
  entityType="skill"
  entity={activeSkill}
  imageUrl={entityImageUrl}
  {canonicalUrl}
  breadcrumbs={breadcrumbs.map(b => ({ name: b.label, url: b.href }))}
/>

<WikiPage
  title="Skills"
  {breadcrumbs}
  entity={data.isCreateMode ? $currentEntity : skill}
  entityType="Skill"
  basePath="/information/skills"
  {navItems}
  {navFilters}
  {user}
  editable={true}
  {canEdit}
  {canCreateNew}
  {userPendingCreates}
  {userPendingUpdates}
>
  <!-- Pending change banner -->
  {#if $existingPendingChange && !$editMode && !data.isCreateMode}
    <div class="pending-change-banner" class:viewing={$viewingPendingChange}>
      <div class="banner-content">
        <span class="banner-icon">⏳</span>
        <span class="banner-text">
          {#if $existingPendingChange.state === 'Pending'}
            This skill has changes pending review.
          {:else}
            This skill has a draft with unsaved changes.
          {/if}
        </span>
        <button
          class="banner-toggle"
          on:click={() => setViewingPendingChange(!$viewingPendingChange)}
        >
          {$viewingPendingChange ? 'View Original' : 'View Changes'}
        </button>
      </div>
    </div>
  {/if}

  {#if activeSkill || data.isCreateMode}
    <div class="layout-a">
      <!-- Wikipedia-style floating infobox (right panel) -->
      <aside class="wiki-infobox-float">
        <!-- Entity Header -->
        <div class="infobox-header">
          <EntityImageUpload
            entityId={activeSkill?.Id}
            entityName={activeSkill?.Name}
            entityType="skill"
            {user}
            isEditMode={$editMode}
            isCreateMode={data.isCreateMode}
          />
          <div class="infobox-title">
            {#if $editMode}
              <InlineEdit
                value={activeSkill?.Name || ''}
                path="Name"
                type="text"
                required={true}
                placeholder="Skill Name"
              />
            {:else}
              {activeSkill?.Name || 'New Skill'}
            {/if}
            </div>
            <div class="infobox-subtitle">
              <span class="category-badge {getCategoryBadgeClass(activeSkill?.Category?.Name)}">
                {activeSkill?.Category?.Name || 'Unknown'}
              </span>
              {#if isHidden && !$editMode}
                <span class="status-badge hidden">Hidden</span>
              {/if}
            </div>
        </div>

        <!-- Key Stats -->
          <div class="stats-section tier-1">
            <div class="stat-row primary">
              <span class="stat-label">Points/HP</span>
              <span class="stat-value">{hpIncrease > 0 ? hpIncrease : 'N/A'}</span>
            </div>
            <div class="stat-row primary">
              <span class="stat-label">Professions</span>
              <span class="stat-value">{professionCount}</span>
            </div>
        </div>

        <!-- Skill Properties -->
          <div class="stats-section">
            <h4 class="section-title">Properties</h4>
            <div class="stat-row">
              <span class="stat-label">Category</span>
              <span class="stat-value">
                {#if $editMode}
                  <InlineEdit
                    value={activeSkill?.Category?.Name || ''}
                    path="Category.Name"
                    type="select"
                    options={categoryOptions}
                    placeholder="Select Category"
                  />
                {:else}
                  {activeSkill?.Category?.Name || 'N/A'}
                {/if}
              </span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Visibility</span>
            <span class="stat-value" class:highlight-hidden={isHidden}>
              {#if $editMode}
                <InlineEdit
                  value={activeSkill?.Properties?.IsHidden}
                  path="Properties.IsHidden"
                  type="checkbox"
                />
                {activeSkill?.Properties?.IsHidden ? 'Hidden' : 'Visible'}
              {:else}
                {isHidden ? 'Hidden' : 'Visible'}
              {/if}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Extractable</span>
            <span class="stat-value" class:highlight-yes={isExtractable}>
              {#if $editMode}
                <InlineEdit
                  value={activeSkill?.Properties?.IsExtractable}
                  path="Properties.IsExtractable"
                  type="checkbox"
                />
                {activeSkill?.Properties?.IsExtractable ? 'Yes' : 'No'}
              {:else}
                {isExtractable ? 'Yes' : 'No'}
              {/if}
            </span>
          </div>
          {#if unlockCount > 0 && !$editMode}
            <div class="stat-row">
              <span class="stat-label">Unlock Required</span>
              <span class="stat-value highlight-warning">Yes</span>
            </div>
          {/if}
        </div>

        <!-- HP Information -->
        {#if (hpIncrease > 0 || $editMode) && !data.isCreateMode}
          <div class="stats-section">
            <h4 class="section-title">Health Points</h4>
            <div class="stat-row">
              <span class="stat-label">Points per HP</span>
              <span class="stat-value">
                {#if $editMode}
                  <InlineEdit
                    value={activeSkill?.Properties?.HpIncrease}
                    path="Properties.HpIncrease"
                    type="number"
                    min={0}
                    step={1}
                    placeholder="0"
                  />
                {:else}
                  {hpIncrease || 'N/A'}
                {/if}
              </span>
            </div>
            {#if hpIncrease > 0}
              <div class="hp-note">
                Every {hpIncrease} skill points increases your max HP by 1.
              </div>
            {/if}
          </div>
        {/if}
      </aside>

      <!-- Main content (center) -->
      <article class="wiki-article">
        <h1 class="article-title">
          {#if $editMode}
            <InlineEdit
              value={activeSkill?.Name || ''}
              path="Name"
              type="text"
              required={true}
              placeholder="Skill Name"
            />
          {:else}
            {activeSkill?.Name || 'New Skill'}
          {/if}
        </h1>

        <!-- Description Panel -->
        <div class="description-panel">
          {#if $editMode}
            <RichTextEditor
              content={activeSkill?.Properties?.Description || ''}
              on:change={(e) => updateField('Properties.Description', e.detail)}
              placeholder="Enter a description for this skill..."
            />
          {:else if activeSkill?.Properties?.Description}
            <div class="description-content">{@html sanitizeHtml(activeSkill.Properties.Description)}</div>
          {:else}
            <div class="description-content placeholder">
              {activeSkill?.Name || 'This skill'} is a {activeSkill?.Category?.Name?.toLowerCase() || ''} skill in Entropia Universe.
              {#if isHidden}
                This skill is hidden and must be unlocked before it becomes visible.
              {/if}
            </div>
          {/if}
        </div>

        <!-- Affected Professions Section -->
        {#if !data.isCreateMode}
          <DataSection
            title="Affected Professions"
            icon=""
            bind:expanded={panelStates.professions}
            subtitle="{professionCount} profession{professionCount !== 1 ? 's' : ''}"
            on:toggle={savePanelStates}
          >
            <SkillProfessions professions={activeSkill?.Professions} />
          </DataSection>
        {/if}

        <!-- Unlocked By Section -->
        {#if activeSkill?.Unlocks && activeSkill.Unlocks.length > 0 && !data.isCreateMode}
          <DataSection
            title="Unlocked By"
            icon=""
            bind:expanded={panelStates.unlocks}
            subtitle="{unlockCount} profession{unlockCount !== 1 ? 's' : ''}"
            on:toggle={savePanelStates}
          >
            <SkillUnlockedBy unlocks={activeSkill.Unlocks} />
          </DataSection>
        {/if}
      </article>
    </div>
  {:else}
    <div class="no-selection">
      <h2>Skills</h2>
      <p>Select a skill from the list to view details.</p>
      <p class="hint">Skills are trained by performing related activities and contribute to profession levels.</p>
    </div>
  {/if}
</WikiPage>

<style>
  .pending-change-banner {
    background: linear-gradient(135deg, #3d4a5c 0%, #2d3748 100%);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 16px;
  }

  .pending-change-banner.viewing {
    background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
    border-color: var(--accent-color, #4a9eff);
  }

  .banner-content {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .banner-icon {
    font-size: 20px;
  }

  .banner-text {
    flex: 1;
    min-width: 200px;
    color: var(--text-color);
  }

  .banner-toggle {
    padding: 6px 12px;
    background-color: var(--accent-color, #4a9eff);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
  }

  .banner-toggle:hover {
    filter: brightness(1.1);
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
  .category-badge.category-attributes {
    background-color: #8b5cf6;
  }

  .category-badge.category-combat {
    background-color: #ef4444;
  }

  .category-badge.category-defense {
    background-color: #3b82f6;
  }

  .category-badge.category-mindforce {
    background-color: #a855f7;
  }

  .category-badge.category-mining {
    background-color: #f59e0b;
  }

  .category-badge.category-construction {
    background-color: #84cc16;
  }

  .category-badge.category-medical {
    background-color: #ec4899;
  }

  .category-badge.category-science {
    background-color: #06b6d4;
  }

  .category-badge.category-general {
    background-color: #6b7280;
  }

  .category-badge.category-information {
    background-color: #14b8a6;
  }

  .category-badge.category-design {
    background-color: #f97316;
  }

  .category-badge.category-beauty {
    background-color: #ec4899;
  }

  .category-badge.category-social {
    background-color: #8b5cf6;
  }

  .status-badge {
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 600;
    border-radius: 4px;
  }

  .status-badge.hidden {
    background-color: var(--warning-bg, rgba(251, 191, 36, 0.15));
    color: var(--warning-color, #fbbf24);
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

  .stat-value.highlight-hidden {
    color: var(--warning-color, #fbbf24);
  }

  .stat-value.highlight-yes {
    color: var(--success-color, #4ade80);
  }

  .stat-value.highlight-warning {
    color: var(--warning-color, #fbbf24);
  }

  .hp-note {
    font-size: 12px;
    color: var(--text-muted, #999);
    font-style: italic;
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--border-color, #555);
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

    .banner-content {
      flex-direction: column;
      align-items: flex-start;
    }

    .banner-toggle {
      width: 100%;
      text-align: center;
    }
  }
</style>
