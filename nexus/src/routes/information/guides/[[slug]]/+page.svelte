<!--
  @component Guide Page
  Handles both the guide overview (no slug) and individual lesson view (with slug).
  Uses a sidebar tree navigation for the lesson view.
  Includes inline management controls for users with guide grants.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import GuideNavigation from '$lib/components/guides/GuideNavigation.svelte';
  import GuideEditor from '$lib/components/guides/GuideEditor.svelte';
  import { sanitizeHtml } from '$lib/sanitize.js';
  import { goto, invalidateAll } from '$app/navigation';

  export let data;

  $: tree = Array.isArray(data.tree) ? data.tree : [];
  $: lesson = data.lesson;
  $: paragraphs = data.paragraphs || [];
  $: slug = data.slug;
  $: lessonApiPath = data.lessonApiPath || '';
  $: isOverview = !slug;

  $: session = data.session;
  $: user = session?.user;
  $: canCreate = user?.grants?.includes('guide.create');
  $: canEdit = user?.grants?.includes('guide.edit');
  $: canDelete = user?.grants?.includes('guide.delete');
  $: canManageGuides = canCreate || canEdit;

  // Edit mode for lesson view
  let editMode = false;

  // Dialog state
  let showDialog = false;
  let dialogType = ''; // 'category', 'chapter', 'lesson', 'edit-category', 'edit-chapter', 'edit-lesson'
  let dialogTitle = '';
  let dialogParentId = null; // categoryId for chapters, chapterId for lessons
  let dialogGrandparentId = null; // categoryId for lessons
  let dialogEditItem = null;

  // Dialog form fields
  let dialogName = '';
  let dialogDescription = '';
  let dialogSlug = '';
  let dialogError = '';
  let dialogSaving = false;

  // Banner upload state
  let bannerUploading = false;
  let bannerError = '';
  // Cache-busting version per category to force re-render after upload
  let bannerVersions = {};

  function bannerUrl(categoryId) {
    const v = bannerVersions[categoryId] || '';
    return `/api/img/guide-category/${categoryId}${v ? `?v=${v}` : ''}`;
  }

  async function uploadBanner(categoryId, file) {
    if (!file) return;
    bannerUploading = true;
    bannerError = '';
    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('entityType', 'guide-category');
      formData.append('entityId', String(categoryId));
      const res = await fetch('/api/uploads/entity-image', { method: 'POST', body: formData });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        bannerError = data.error || 'Failed to upload banner';
        return;
      }
      // Bust cache for this category
      bannerVersions = { ...bannerVersions, [categoryId]: Date.now() };
    } catch (e) {
      bannerError = 'Network error uploading banner';
    } finally {
      bannerUploading = false;
    }
  }

  function handleBannerFileSelect(categoryId, event) {
    const file = event.target.files?.[0];
    if (file) uploadBanner(categoryId, file);
    event.target.value = '';
  }

  // Find prev/next lessons for navigation
  $: allLessons = (() => {
    const list = [];
    for (const cat of tree) {
      for (const ch of cat.chapters || []) {
        for (const l of ch.lessons || []) {
          list.push({ ...l, categoryTitle: cat.title, chapterTitle: ch.title, categoryId: cat.id, chapterId: ch.id });
        }
      }
    }
    return list;
  })();

  $: currentIndex = allLessons.findIndex(l => l.slug === slug);
  $: prevLesson = currentIndex > 0 ? allLessons[currentIndex - 1] : null;
  $: nextLesson = currentIndex >= 0 && currentIndex < allLessons.length - 1 ? allLessons[currentIndex + 1] : null;
  $: currentCategoryId = currentIndex >= 0 ? allLessons[currentIndex].categoryId : null;

  // Breadcrumb data
  $: categoryTitle = lesson?.category_title;
  $: chapterTitle = lesson?.chapter_title;

  // Reset edit mode when navigating between lessons
  $: if (slug) editMode = false;

  async function toggleEditMode() {
    if (editMode) {
      // Leaving edit mode — refresh to show latest paragraph content
      editMode = false;
      await invalidateAll();
    } else {
      editMode = true;
    }
  }

  function openCreateCategory() {
    dialogType = 'category';
    dialogTitle = 'New Category';
    dialogName = '';
    dialogDescription = '';
    dialogError = '';
    showDialog = true;
  }

  function openEditCategory(cat) {
    dialogType = 'edit-category';
    dialogTitle = 'Edit Category';
    dialogEditItem = cat;
    dialogName = cat.title;
    dialogDescription = cat.description || '';
    dialogError = '';
    showDialog = true;
  }

  function openCreateChapter(categoryId) {
    dialogType = 'chapter';
    dialogTitle = 'New Chapter';
    dialogParentId = categoryId;
    dialogName = '';
    dialogDescription = '';
    dialogError = '';
    showDialog = true;
  }

  function openEditChapter(categoryId, chapter) {
    dialogType = 'edit-chapter';
    dialogTitle = 'Edit Chapter';
    dialogParentId = categoryId;
    dialogEditItem = chapter;
    dialogName = chapter.title;
    dialogDescription = chapter.description || '';
    dialogError = '';
    showDialog = true;
  }

  function openCreateLesson(categoryId, chapterId) {
    dialogType = 'lesson';
    dialogTitle = 'New Lesson';
    dialogParentId = chapterId;
    dialogGrandparentId = categoryId;
    dialogName = '';
    dialogSlug = '';
    dialogError = '';
    showDialog = true;
  }

  function openEditLesson() {
    if (!lesson) return;
    dialogType = 'edit-lesson';
    dialogTitle = 'Edit Lesson';
    dialogEditItem = lesson;
    dialogName = lesson.title;
    dialogSlug = lesson.slug;
    dialogError = '';
    showDialog = true;
  }

  function closeDialog() {
    showDialog = false;
    dialogType = '';
    dialogEditItem = null;
    dialogParentId = null;
    dialogGrandparentId = null;
    dialogError = '';
    dialogSaving = false;
  }

  function autoSlug(title) {
    return title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }

  // Auto-generate slug from title for new lessons
  $: if (dialogType === 'lesson' && dialogName) {
    dialogSlug = autoSlug(dialogName);
  }

  async function submitDialog() {
    dialogSaving = true;
    dialogError = '';

    try {
      if (dialogType === 'category') {
        const res = await fetch('/api/guides', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: dialogName, description: dialogDescription || null })
        });
        if (!res.ok) { dialogError = (await res.json()).error || 'Failed to create category'; return; }
      } else if (dialogType === 'edit-category') {
        const res = await fetch(`/api/guides/${dialogEditItem.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: dialogName, description: dialogDescription || null })
        });
        if (!res.ok) { dialogError = (await res.json()).error || 'Failed to update category'; return; }
      } else if (dialogType === 'chapter') {
        const res = await fetch(`/api/guides/${dialogParentId}/chapters`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: dialogName, description: dialogDescription || null })
        });
        if (!res.ok) { dialogError = (await res.json()).error || 'Failed to create chapter'; return; }
      } else if (dialogType === 'edit-chapter') {
        const res = await fetch(`/api/guides/${dialogParentId}/chapters/${dialogEditItem.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: dialogName, description: dialogDescription || null })
        });
        if (!res.ok) { dialogError = (await res.json()).error || 'Failed to update chapter'; return; }
      } else if (dialogType === 'lesson') {
        const res = await fetch(`/api/guides/${dialogGrandparentId}/chapters/${dialogParentId}/lessons`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: dialogName, slug: dialogSlug })
        });
        if (!res.ok) { dialogError = (await res.json()).error || 'Failed to create lesson'; return; }
        const newLesson = await res.json();
        closeDialog();
        await invalidateAll();
        goto(`/information/guides/${newLesson.slug}`);
        return;
      } else if (dialogType === 'edit-lesson') {
        // Find IDs from tree for the API path
        let catId, chId;
        for (const cat of tree) {
          for (const ch of cat.chapters || []) {
            if ((ch.lessons || []).some(l => l.id === dialogEditItem.id)) {
              catId = cat.id;
              chId = ch.id;
              break;
            }
          }
          if (catId) break;
        }
        const res = await fetch(`/api/guides/${catId}/chapters/${chId}/lessons/${dialogEditItem.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: dialogName, slug: dialogSlug })
        });
        if (!res.ok) { dialogError = (await res.json()).error || 'Failed to update lesson'; return; }
        const updated = await res.json();
        closeDialog();
        await invalidateAll();
        if (updated.slug !== slug) {
          goto(`/information/guides/${updated.slug}`);
        }
        return;
      }

      closeDialog();
      await invalidateAll();
    } catch (e) {
      dialogError = 'Network error';
    } finally {
      dialogSaving = false;
    }
  }

  async function deleteCategory(catId) {
    if (!confirm('Delete this category and all its chapters and lessons? This cannot be undone.')) return;
    const res = await fetch(`/api/guides/${catId}`, { method: 'DELETE' });
    if (res.ok) await invalidateAll();
  }

  async function deleteChapter(catId, chId) {
    if (!confirm('Delete this chapter and all its lessons? This cannot be undone.')) return;
    const res = await fetch(`/api/guides/${catId}/chapters/${chId}`, { method: 'DELETE' });
    if (res.ok) await invalidateAll();
  }

  async function deleteLesson(catId, chId, lessonId, lessonSlug) {
    if (!confirm('Delete this lesson? This cannot be undone.')) return;
    const res = await fetch(`/api/guides/${catId}/chapters/${chId}/lessons/${lessonId}`, { method: 'DELETE' });
    if (res.ok) {
      if (slug === lessonSlug) {
        goto('/information/guides');
      } else {
        await invalidateAll();
      }
    }
  }
</script>

<svelte:head>
  {#if isOverview}
    <title>Guides - Entropia Nexus</title>
    <meta name="description" content="Step-by-step guides and tutorials for Entropia Universe." />
    <link rel="canonical" href="https://entropianexus.com/information/guides" />
  {:else if lesson}
    <title>{lesson.title} - Guides - Entropia Nexus</title>
    <meta name="description" content="{lesson.title} - {categoryTitle} guide for Entropia Universe." />
  {/if}
</svelte:head>

{#if isOverview}
  <!-- OVERVIEW MODE: Show all categories, chapters, and lessons -->
  <div class="guides-overview">
    <nav class="breadcrumbs">
      <a href="/information">Information</a>
      <span class="sep">/</span>
      <span>Guides</span>
    </nav>

    <header class="page-header">
      <h1>Guides</h1>
      <p class="subtitle">Step-by-step guides and tutorials for Entropia Universe</p>
      {#if canCreate}
        <button class="header-action-btn" on:click={openCreateCategory}>+ New Category</button>
      {/if}
    </header>

    {#if tree.length === 0}
      <div class="empty-state">
        <p>No guides available yet.</p>
        {#if canCreate}
          <p class="muted">Click "New Category" above to get started.</p>
        {/if}
      </div>
    {:else}
      {#if bannerError}
        <div class="banner-error">{bannerError}</div>
      {/if}
      <div class="category-list">
        {#each tree as category}
          <section class="guide-category">
            <img class="category-banner" src={bannerUrl(category.id)} alt="" loading="lazy" on:error={(e) => e.target.style.display = 'none'} on:load={(e) => e.target.style.display = ''} />
            {#if canManageGuides}
              <div class="category-actions">
                {#if canEdit}
                  <button class="cat-action-btn" on:click={() => openEditCategory(category)} title="Edit category">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  </button>
                  <label class="cat-action-btn" title="Upload banner image" class:uploading={bannerUploading}>
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                    <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden on:change={(e) => handleBannerFileSelect(category.id, e)} disabled={bannerUploading} />
                  </label>
                {/if}
                {#if canCreate}
                  <button class="cat-action-btn" on:click={() => openCreateChapter(category.id)} title="Add chapter">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                  </button>
                {/if}
                {#if canDelete}
                  <button class="cat-action-btn danger" on:click={() => deleteCategory(category.id)} title="Delete category">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                  </button>
                {/if}
              </div>
            {/if}
            <div class="category-header">
              <div class="category-header-text">
                <h2 class="category-title">{category.title}</h2>
                {#if category.description}
                  <p class="category-description">{category.description}</p>
                {/if}
              </div>
            </div>

            {#if category.chapters?.length > 0}
              <div class="chapter-list">
                {#each category.chapters as chapter}
                  <div class="guide-chapter">
                    <div class="chapter-header">
                      <div>
                        <h3 class="chapter-title">{chapter.title}</h3>
                        {#if chapter.description}
                          <p class="chapter-description">{chapter.description}</p>
                        {/if}
                      </div>
                      {#if canManageGuides}
                        <div class="inline-actions">
                          {#if canEdit}
                            <button class="inline-btn" on:click={() => openEditChapter(category.id, chapter)} title="Edit chapter">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                            </button>
                          {/if}
                          {#if canCreate}
                            <button class="inline-btn" on:click={() => openCreateLesson(category.id, chapter.id)} title="Add lesson">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                            </button>
                          {/if}
                          {#if canDelete}
                            <button class="inline-btn danger" on:click={() => deleteChapter(category.id, chapter.id)} title="Delete chapter">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                            </button>
                          {/if}
                        </div>
                      {/if}
                    </div>
                    {#if chapter.lessons?.length > 0}
                      <ul class="lesson-list">
                        {#each chapter.lessons as lessonItem}
                          <li class="lesson-list-item">
                            <a href="/information/guides/{lessonItem.slug}" class="lesson-link">
                              {lessonItem.title}
                            </a>
                            {#if canDelete}
                              <button class="inline-btn-sm danger" on:click={() => deleteLesson(category.id, chapter.id, lessonItem.id, lessonItem.slug)} title="Delete lesson">
                                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                              </button>
                            {/if}
                          </li>
                        {/each}
                      </ul>
                    {:else}
                      <p class="no-items">No lessons in this chapter yet.</p>
                    {/if}
                  </div>
                {/each}
              </div>
            {:else}
              <p class="no-items">No chapters in this category yet.</p>
            {/if}
          </section>
        {/each}
      </div>
    {/if}
  </div>

{:else}
  <!-- LESSON MODE: Sidebar + lesson content -->
  <div class="guide-layout">
    <aside class="guide-sidebar">
      <GuideNavigation {tree} currentSlug={slug} />
    </aside>

    <main class="guide-content">
      <nav class="breadcrumbs">
        <a href="/information">Information</a>
        <span class="sep">/</span>
        <a href="/information/guides">Guides</a>
        {#if categoryTitle}
          <span class="sep">/</span>
          <span class="breadcrumb-muted">{categoryTitle}</span>
        {/if}
        {#if chapterTitle}
          <span class="sep">/</span>
          <span class="breadcrumb-muted">{chapterTitle}</span>
        {/if}
      </nav>

      {#if lesson}
        <article class="lesson-article">
          <div class="lesson-header">
            {#if currentCategoryId}
              <img class="lesson-header-banner" src={bannerUrl(currentCategoryId)} alt="" loading="lazy" on:error={(e) => e.target.style.display = 'none'} on:load={(e) => e.target.style.display = ''} />
            {/if}
            <h1 class="lesson-title">{lesson.title}</h1>
            {#if canManageGuides}
              <div class="lesson-actions">
                {#if canEdit}
                  <button class="lesson-action-btn" on:click={openEditLesson} title="Edit lesson title & slug">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  </button>
                {/if}
                <button class="lesson-action-btn" class:active={editMode} on:click={toggleEditMode} title={editMode ? 'Exit edit mode' : 'Edit paragraphs'}>
                  {#if editMode}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  {:else}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                  {/if}
                  <span>{editMode ? 'View' : 'Edit'}</span>
                </button>
              </div>
            {/if}
          </div>

          {#if editMode && canManageGuides}
            <GuideEditor
              {paragraphs}
              apiBasePath="{lessonApiPath}/paragraphs"
              canCreate={canCreate}
              canDelete={canDelete}
            />
          {:else if paragraphs.length === 0}
            <div class="empty-state">
              <p>This lesson has no content yet.</p>
              {#if canManageGuides}
                <p class="muted">Click "Edit" to add paragraphs.</p>
              {/if}
            </div>
          {:else}
            {#each paragraphs as paragraph}
              <div class="paragraph-content">
                {@html sanitizeHtml(paragraph.content_html)}
              </div>
            {/each}
          {/if}
        </article>

        <!-- Prev/Next navigation -->
        <nav class="lesson-nav">
          {#if prevLesson}
            <a href="/information/guides/{prevLesson.slug}" class="lesson-nav-link prev">
              <span class="nav-direction">&larr; Previous</span>
              <span class="nav-title">{prevLesson.title}</span>
            </a>
          {:else}
            <div></div>
          {/if}
          {#if nextLesson}
            <a href="/information/guides/{nextLesson.slug}" class="lesson-nav-link next">
              <span class="nav-direction">Next &rarr;</span>
              <span class="nav-title">{nextLesson.title}</span>
            </a>
          {/if}
        </nav>
      {:else}
        <div class="empty-state">
          <p>Lesson not found.</p>
          <a href="/information/guides">Back to Guides</a>
        </div>
      {/if}
    </main>
  </div>
{/if}

<!-- CREATE/EDIT DIALOG -->
{#if showDialog}
  <div class="dialog-overlay" role="dialog" on:click={closeDialog} on:keydown={(e) => e.key === 'Escape' && closeDialog()}>
    <div class="dialog" role="presentation" on:click|stopPropagation>
      <h3 class="dialog-title">{dialogTitle}</h3>

      {#if dialogError}
        <div class="dialog-error">{dialogError}</div>
      {/if}

      <form on:submit|preventDefault={submitDialog}>
        <div class="dialog-field">
          <label for="dialog-name">Title</label>
          <input id="dialog-name" type="text" bind:value={dialogName} required placeholder="Enter title..." />
        </div>

        {#if dialogType !== 'lesson' && dialogType !== 'edit-lesson'}
          <div class="dialog-field">
            <label for="dialog-desc">Description (optional)</label>
            <textarea id="dialog-desc" bind:value={dialogDescription} rows="2" placeholder="Brief description..."></textarea>
          </div>
        {/if}

        {#if dialogType === 'lesson' || dialogType === 'edit-lesson'}
          <div class="dialog-field">
            <label for="dialog-slug">URL Slug</label>
            <input id="dialog-slug" type="text" bind:value={dialogSlug} required placeholder="e.g. getting-started" pattern="[a-z0-9\-]+" />
            <span class="field-hint">/information/guides/{dialogSlug || '...'}</span>
          </div>
        {/if}

        <div class="dialog-actions">
          <button type="button" class="btn-cancel" on:click={closeDialog}>Cancel</button>
          <button type="submit" class="btn-save" disabled={dialogSaving || !dialogName.trim()}>
            {dialogSaving ? 'Saving...' : (dialogType.startsWith('edit') ? 'Save' : 'Create')}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  /* ===== OVERVIEW MODE ===== */
  .guides-overview {
    max-width: 900px;
    margin: 0 auto;
    padding: 24px;
  }

  .page-header {
    text-align: center;
    margin-bottom: 32px;
  }

  .page-header h1 {
    margin: 0 0 8px 0;
    color: var(--text-color);
    font-size: 2rem;
  }

  .subtitle {
    margin: 0 0 16px 0;
    color: var(--text-muted);
    font-size: 1.1rem;
  }

  .header-action-btn {
    padding: 6px 16px;
    border: 1px solid var(--accent-color);
    border-radius: 4px;
    background: none;
    color: var(--accent-color);
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .header-action-btn:hover {
    background-color: var(--accent-color);
    color: white;
  }

  .category-list {
    display: flex;
    flex-direction: column;
    gap: 32px;
  }

  .banner-error {
    padding: 8px 12px;
    margin-bottom: 12px;
    border-radius: 4px;
    background-color: rgba(239, 68, 68, 0.1);
    color: var(--error-color, #ef4444);
    border: 1px solid rgba(239, 68, 68, 0.2);
    font-size: 0.8125rem;
  }

  .guide-category {
    position: relative;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 24px;
    overflow: hidden;
  }

  .category-banner {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 60%;
    object-fit: cover;
    pointer-events: none;
    -webkit-mask-image: linear-gradient(to right, transparent, rgba(0,0,0,0.6));
    mask-image: linear-gradient(to right, transparent, rgba(0,0,0,0.6));
  }

  .category-actions {
    position: absolute;
    top: 8px;
    right: 8px;
    display: flex;
    gap: 2px;
    z-index: 2;
    opacity: 0;
    transition: opacity 0.15s;
  }

  .guide-category:hover .category-actions {
    opacity: 1;
  }

  .cat-action-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    padding: 0;
    border: none;
    background-color: var(--secondary-color);
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.15s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  }

  .cat-action-btn:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .cat-action-btn.danger:hover {
    background-color: rgba(239, 68, 68, 0.15);
    color: var(--error-color, #ef4444);
  }

  .cat-action-btn.uploading {
    opacity: 0.5;
    pointer-events: none;
  }

  .category-header {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
  }

  .category-header-text {
    flex: 1;
    min-width: 0;
  }

  .category-title {
    margin: 0;
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .category-description {
    margin: 4px 0 0 0;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .chapter-list {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .guide-chapter {
    padding: 16px;
    background-color: var(--primary-color);
    border-radius: 6px;
    border: 1px solid var(--border-color);
  }

  .chapter-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
  }

  .chapter-title {
    margin: 0 0 4px 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .chapter-description {
    margin: 0;
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  .lesson-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .lesson-list-item {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .lesson-link {
    display: block;
    flex: 1;
    padding: 8px 12px;
    border-radius: 4px;
    color: var(--text-color);
    text-decoration: none;
    font-size: 0.9rem;
    transition: background-color 0.15s ease;
  }

  .lesson-link:hover {
    background-color: var(--hover-color);
    color: var(--accent-color);
  }

  .no-items {
    position: relative;
    z-index: 1;
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin: 8px 0 0 0;
    font-style: italic;
  }

  /* ===== INLINE ACTION BUTTONS ===== */
  .inline-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }

  .inline-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    padding: 0;
    border: none;
    background: none;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.15s;
  }

  .inline-btn:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .inline-btn.danger:hover {
    background-color: rgba(239, 68, 68, 0.15);
    color: var(--error-color, #ef4444);
  }

  .inline-btn-sm {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    border: none;
    background: none;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 3px;
    opacity: 0;
    transition: all 0.15s;
  }

  .lesson-list-item:hover .inline-btn-sm {
    opacity: 1;
  }

  .inline-btn-sm.danger:hover {
    background-color: rgba(239, 68, 68, 0.15);
    color: var(--error-color, #ef4444);
  }

  /* ===== LESSON MODE ===== */
  .guide-layout {
    display: flex;
    max-width: 1200px;
    margin: 0 auto;
    min-height: calc(100vh - 60px);
  }

  .guide-sidebar {
    width: 280px;
    flex-shrink: 0;
    border-right: 1px solid var(--border-color);
    background-color: var(--secondary-color);
    overflow-y: auto;
    position: fixed;
    top: 57px;
    bottom: 0;
    left: 0;
    z-index: 10;
  }

  .guide-content {
    flex: 1;
    min-width: 0;
    padding: 24px 32px;
    margin-left: 280px;
  }

  .lesson-header {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 24px;
    padding: 16px 20px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .lesson-header-banner {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 60%;
    object-fit: cover;
    pointer-events: none;
    -webkit-mask-image: linear-gradient(to right, transparent, rgba(0,0,0,0.6));
    mask-image: linear-gradient(to right, transparent, rgba(0,0,0,0.6));
  }

  .lesson-title {
    position: relative;
    z-index: 1;
    margin: 0;
    font-size: 1.75rem;
    color: var(--text-color);
  }

  .lesson-actions {
    position: relative;
    z-index: 1;
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }

  .lesson-action-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border: none;
    border-radius: 4px;
    background-color: var(--secondary-color);
    color: var(--text-color);
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.15);
  }

  .lesson-action-btn:hover {
    background-color: var(--hover-color);
    color: var(--accent-color);
  }

  .lesson-action-btn.active {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  /* ===== SHARED ===== */
  .breadcrumbs {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 0.875rem;
    color: var(--text-muted);
    flex-wrap: wrap;
  }

  .breadcrumbs a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumbs a:hover {
    text-decoration: underline;
  }

  .breadcrumbs .sep {
    color: var(--text-muted);
  }

  .breadcrumb-muted {
    color: var(--text-muted);
  }

  .empty-state {
    text-align: center;
    padding: 48px 24px;
    color: var(--text-muted);
  }

  .empty-state .muted {
    font-size: 0.875rem;
    margin-top: 8px;
  }

  .empty-state a {
    color: var(--accent-color);
    text-decoration: none;
  }

  /* ===== LESSON ARTICLE ===== */
  .paragraph-content {
    margin-bottom: 16px;
    line-height: 1.7;
    color: var(--text-color);
    font-size: 0.95rem;
  }

  .paragraph-content :global(h1),
  .paragraph-content :global(h2),
  .paragraph-content :global(h3),
  .paragraph-content :global(h4) {
    color: var(--text-color);
    margin: 24px 0 8px 0;
  }

  .paragraph-content :global(p) {
    margin: 0 0 8px 0;
  }

  .paragraph-content :global(a) {
    color: var(--accent-color);
    text-decoration: none;
  }

  .paragraph-content :global(a:hover) {
    text-decoration: underline;
  }

  .paragraph-content :global(code) {
    background-color: var(--primary-color);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.875em;
  }

  .paragraph-content :global(blockquote) {
    border-left: 3px solid var(--accent-color);
    padding-left: 16px;
    margin: 12px 0;
    color: var(--text-muted);
  }

  .paragraph-content :global(ul),
  .paragraph-content :global(ol) {
    padding-left: 24px;
    margin: 8px 0;
  }

  /* ===== PREV/NEXT NAV ===== */
  .lesson-nav {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--border-color);
  }

  .lesson-nav-link {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 16px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    text-decoration: none;
    color: var(--text-color);
    transition: border-color 0.15s ease;
    max-width: 45%;
  }

  .lesson-nav-link:hover {
    border-color: var(--accent-color);
  }

  .lesson-nav-link.next {
    text-align: right;
    margin-left: auto;
  }

  .nav-direction {
    font-size: 0.75rem;
    color: var(--accent-color);
    font-weight: 500;
  }

  .nav-title {
    font-size: 0.875rem;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ===== DIALOG ===== */
  .dialog-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 24px;
    min-width: 340px;
    max-width: 440px;
    width: 100%;
    box-sizing: border-box;
  }

  .dialog-title {
    margin: 0 0 16px 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .dialog-error {
    padding: 8px 12px;
    margin-bottom: 12px;
    border-radius: 4px;
    background-color: rgba(239, 68, 68, 0.1);
    color: var(--error-color, #ef4444);
    border: 1px solid rgba(239, 68, 68, 0.2);
    font-size: 0.8125rem;
  }

  .dialog-field {
    margin-bottom: 16px;
  }

  .dialog-field label {
    display: block;
    font-size: 0.8125rem;
    color: var(--text-muted);
    margin-bottom: 4px;
    font-weight: 500;
  }

  .dialog-field input,
  .dialog-field textarea {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--primary-color);
    color: var(--text-color);
    font-size: 0.875rem;
    box-sizing: border-box;
    font-family: inherit;
  }

  .dialog-field input:focus,
  .dialog-field textarea:focus {
    outline: none;
    border-color: var(--accent-color);
  }

  .dialog-field textarea {
    resize: vertical;
    min-height: 60px;
  }

  .field-hint {
    display: block;
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 4px;
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 20px;
  }

  .btn-save, .btn-cancel {
    padding: 8px 18px;
    border-radius: 4px;
    font-size: 0.8125rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-save {
    background-color: var(--accent-color);
    border: none;
    color: white;
  }

  .btn-save:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-save:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-cancel {
    background: none;
    border: 1px solid var(--border-color);
    color: var(--text-color);
  }

  .btn-cancel:hover {
    background-color: var(--hover-color);
  }

  /* ===== MOBILE ===== */
  @media (max-width: 900px) {
    .guide-layout {
      flex-direction: column;
    }

    .guide-sidebar {
      width: 100%;
      position: static;
      max-height: none;
      border-left: none;
      border-right: none;
      border-bottom: 1px solid var(--border-color);
    }

    .guide-content {
      margin-left: 0;
    }

    .guide-content {
      padding: 16px;
    }

    .guides-overview {
      padding: 16px;
    }

    .page-header h1 {
      font-size: 1.5rem;
    }

    .lesson-title {
      font-size: 1.5rem;
    }

    .lesson-header {
      flex-direction: column;
      align-items: flex-start;
    }

    .lesson-header-banner {
      width: 50%;
      opacity: 0.5;
    }

    .lesson-nav {
      flex-direction: column;
    }

    .lesson-nav-link {
      max-width: 100%;
    }

    .lesson-nav-link.next {
      text-align: left;
    }

    .dialog {
      margin: 16px;
      min-width: auto;
    }

    .inline-actions {
      gap: 2px;
    }

    .category-banner {
      width: 50%;
      opacity: 0.5;
    }

    .category-actions {
      opacity: 1;
    }
  }
</style>
