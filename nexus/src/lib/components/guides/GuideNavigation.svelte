<!--
  @component GuideNavigation
  Tree-structured sidebar for navigating guide content.
  Expandable categories and chapters with lesson items as leaf nodes.
-->
<script>
  export let tree = [];
  export let currentSlug = null;
  export let canEdit = false;

  let expandedCategories = new Set();
  let expandedChapters = new Set();

  // Auto-expand to show current lesson
  $: if (currentSlug && tree.length > 0) {
    for (const cat of tree) {
      for (const ch of cat.chapters || []) {
        if ((ch.lessons || []).some(l => l.slug === currentSlug)) {
          expandedCategories.add(cat.id);
          expandedChapters.add(ch.id);
          expandedCategories = expandedCategories;
          expandedChapters = expandedChapters;
        }
      }
    }
  }

  function toggleCategory(catId) {
    if (expandedCategories.has(catId)) {
      expandedCategories.delete(catId);
    } else {
      expandedCategories.add(catId);
    }
    expandedCategories = expandedCategories;
  }

  function toggleChapter(chId) {
    if (expandedChapters.has(chId)) {
      expandedChapters.delete(chId);
    } else {
      expandedChapters.add(chId);
    }
    expandedChapters = expandedChapters;
  }
</script>

<nav class="guide-nav">
  <a href="/information/guides" class="nav-header">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
    <span>Guides</span>
  </a>

  {#if tree.length === 0}
    <div class="nav-empty">No guides yet</div>
  {/if}

  <div class="nav-tree">
    {#each tree as category}
      <div class="tree-category">
        <button
          class="tree-toggle"
          class:expanded={expandedCategories.has(category.id)}
          on:click={() => toggleCategory(category.id)}
        >
          <svg class="chevron" width="12" height="12" viewBox="0 0 12 12">
            <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" />
          </svg>
          <span class="tree-label">{category.title}</span>
        </button>

        {#if expandedCategories.has(category.id)}
          <div class="tree-children">
            {#each category.chapters || [] as chapter}
              <div class="tree-chapter">
                <button
                  class="tree-toggle chapter-toggle"
                  class:expanded={expandedChapters.has(chapter.id)}
                  on:click={() => toggleChapter(chapter.id)}
                >
                  <svg class="chevron" width="10" height="10" viewBox="0 0 12 12">
                    <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" />
                  </svg>
                  <span class="tree-label">{chapter.title}</span>
                </button>

                {#if expandedChapters.has(chapter.id)}
                  <div class="tree-lessons">
                    {#each chapter.lessons || [] as lesson}
                      <a
                        href="/information/guides/{lesson.slug}"
                        class="tree-lesson"
                        class:active={currentSlug === lesson.slug}
                      >
                        {lesson.title}
                      </a>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </div>
</nav>

<style>
  .guide-nav {
    padding: 12px 0;
  }

  .nav-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    margin-bottom: 8px;
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-color);
    text-decoration: none;
  }

  .nav-header:hover {
    color: var(--accent-color);
  }

  .nav-empty {
    padding: 12px 16px;
    font-size: 0.8125rem;
    color: var(--text-muted);
    font-style: italic;
  }

  .nav-tree {
    display: flex;
    flex-direction: column;
  }

  .tree-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 6px 16px;
    border: none;
    background: none;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-color);
    text-align: left;
  }

  .tree-toggle:hover {
    background-color: var(--hover-color);
  }

  .chapter-toggle {
    padding-left: 28px;
    font-weight: 500;
    font-size: 0.8125rem;
  }

  .chevron {
    flex-shrink: 0;
    transition: transform 0.15s ease;
  }

  .tree-toggle.expanded .chevron {
    transform: rotate(90deg);
  }

  .tree-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tree-children {
    display: flex;
    flex-direction: column;
  }

  .tree-lessons {
    display: flex;
    flex-direction: column;
  }

  .tree-lesson {
    display: block;
    padding: 5px 16px 5px 46px;
    font-size: 0.8125rem;
    color: var(--text-muted);
    text-decoration: none;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    border-radius: 0;
    transition: background-color 0.1s ease;
  }

  .tree-lesson:hover {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .tree-lesson.active {
    background-color: var(--hover-color);
    color: var(--accent-color);
    font-weight: 500;
  }
</style>
