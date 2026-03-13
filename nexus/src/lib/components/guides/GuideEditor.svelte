<!--
  @component GuideEditor
  Inline editor for guide lesson paragraphs.
  Uses RichTextEditor (TipTap) for each paragraph with add/delete/reorder controls.
-->
<script>
  // @ts-nocheck
  import { onMount } from 'svelte';

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {{ id: number, content_html: string, sort_order: number }[]} [paragraphs]
   * @property {string} [apiBasePath]
   * @property {boolean} [canCreate]
   * @property {boolean} [canDelete]
   */

  /** @type {Props} */
  let {
    paragraphs = $bindable([]),
    apiBasePath = '',
    canCreate = false,
    canDelete = false
  } = $props();

  let RichTextEditor = $state(null);
  let editingId = $state(null);
  let editContent = $state('');
  let saving = $state(false);
  let error = $state('');
  let successMessage = $state('');

  onMount(async () => {
    const mod = await import('$lib/components/wiki/RichTextEditor.svelte');
    RichTextEditor = mod.default;
  });

  function clearMessages() {
    error = '';
    successMessage = '';
  }

  function startEdit(paragraph) {
    clearMessages();
    editingId = paragraph.id;
    editContent = paragraph.content_html;
  }

  function cancelEdit() {
    editingId = null;
    editContent = '';
    clearMessages();
  }

  function handleEditorChange(data) {
    editContent = data;
  }

  async function saveParagraph(paragraphId) {
    saving = true;
    clearMessages();
    try {
      const res = await fetch(`${apiBasePath}/${paragraphId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_html: editContent })
      });
      if (!res.ok) {
        const data = await res.json();
        error = data.error || 'Failed to save paragraph';
        return;
      }
      const updated = await res.json();
      paragraphs = paragraphs.map(p => p.id === paragraphId ? { ...p, content_html: updated.content_html } : p);
      editingId = null;
      editContent = '';
      successMessage = 'Paragraph saved';
      setTimeout(() => { if (successMessage === 'Paragraph saved') successMessage = ''; }, 2000);
    } catch (e) {
      error = 'Network error saving paragraph';
    } finally {
      saving = false;
    }
  }

  async function addParagraph() {
    saving = true;
    clearMessages();
    try {
      const sortOrder = paragraphs.length > 0
        ? Math.max(...paragraphs.map(p => p.sort_order)) + 1
        : 0;
      const res = await fetch(apiBasePath, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_html: '<p></p>', sort_order: sortOrder })
      });
      if (!res.ok) {
        const data = await res.json();
        error = data.error || 'Failed to create paragraph';
        return;
      }
      const newParagraph = await res.json();
      paragraphs = [...paragraphs, newParagraph];
      // Auto-start editing the new paragraph
      editingId = newParagraph.id;
      editContent = newParagraph.content_html;
    } catch (e) {
      error = 'Network error creating paragraph';
    } finally {
      saving = false;
    }
  }

  async function deleteParagraph(paragraphId) {
    if (!confirm('Delete this paragraph? This cannot be undone.')) return;
    saving = true;
    clearMessages();
    try {
      const res = await fetch(`${apiBasePath}/${paragraphId}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        error = data.error || 'Failed to delete paragraph';
        return;
      }
      paragraphs = paragraphs.filter(p => p.id !== paragraphId);
      if (editingId === paragraphId) {
        editingId = null;
        editContent = '';
      }
      successMessage = 'Paragraph deleted';
      setTimeout(() => { if (successMessage === 'Paragraph deleted') successMessage = ''; }, 2000);
    } catch (e) {
      error = 'Network error deleting paragraph';
    } finally {
      saving = false;
    }
  }

  async function moveParagraph(index, direction) {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= paragraphs.length) return;
    clearMessages();

    // Swap locally
    const reordered = [...paragraphs];
    [reordered[index], reordered[newIndex]] = [reordered[newIndex], reordered[index]];
    paragraphs = reordered;

    // Persist order
    try {
      const res = await fetch(apiBasePath, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orderedIds: reordered.map(p => p.id) })
      });
      if (!res.ok) {
        error = 'Failed to save paragraph order';
      }
    } catch (e) {
      error = 'Network error saving order';
    }
  }
</script>

<div class="guide-editor">
  {#if error}
    <div class="editor-message error">{error}</div>
  {/if}
  {#if successMessage}
    <div class="editor-message success">{successMessage}</div>
  {/if}

  {#each paragraphs as paragraph, i (paragraph.id)}
    <div class="paragraph-block" class:editing={editingId === paragraph.id}>
      <div class="paragraph-toolbar">
        <span class="paragraph-label">Paragraph {i + 1}</span>
        <div class="paragraph-actions">
          {#if editingId !== paragraph.id}
            <button class="action-btn" onclick={() => startEdit(paragraph)} title="Edit paragraph">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
          {/if}
          <button class="action-btn" onclick={() => moveParagraph(i, -1)} disabled={i === 0} title="Move up">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 15l-6-6-6 6"/></svg>
          </button>
          <button class="action-btn" onclick={() => moveParagraph(i, 1)} disabled={i === paragraphs.length - 1} title="Move down">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
          </button>
          {#if canDelete}
            <button class="action-btn danger" onclick={() => deleteParagraph(paragraph.id)} title="Delete paragraph">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          {/if}
        </div>
      </div>

      {#if editingId === paragraph.id && RichTextEditor}
        <div class="editor-wrapper">
          <RichTextEditor content={editContent} onchange={handleEditorChange} placeholder="Write paragraph content..." showWaypoints={true} />
          <div class="editor-actions">
            <button class="btn-cancel" onclick={cancelEdit} disabled={saving}>Cancel</button>
            <button class="btn-save" onclick={() => saveParagraph(paragraph.id)} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      {:else}
        <div class="paragraph-preview">
          {#if paragraph.content_html && paragraph.content_html !== '<p></p>'}
            {@html paragraph.content_html}
          {:else}
            <span class="empty-hint">Empty paragraph - click edit to add content</span>
          {/if}
        </div>
      {/if}
    </div>
  {/each}

  {#if canCreate}
    <button class="add-paragraph-btn" onclick={addParagraph} disabled={saving}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      Add Paragraph
    </button>
  {/if}
</div>

<style>
  .guide-editor {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .editor-message {
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 0.8125rem;
  }

  .editor-message.error {
    background-color: rgba(239, 68, 68, 0.1);
    color: var(--error-color, #ef4444);
    border: 1px solid rgba(239, 68, 68, 0.2);
  }

  .editor-message.success {
    background-color: rgba(34, 197, 94, 0.1);
    color: var(--success-color, #22c55e);
    border: 1px solid rgba(34, 197, 94, 0.2);
  }

  .paragraph-block {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    overflow: hidden;
    transition: border-color 0.15s ease;
  }

  .paragraph-block.editing {
    border-color: var(--accent-color);
  }

  .paragraph-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    background-color: var(--tertiary-color, var(--secondary-color));
    border-bottom: 1px solid var(--border-color);
    min-height: 32px;
  }

  .paragraph-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .paragraph-actions {
    display: flex;
    gap: 4px;
  }

  .action-btn {
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

  .action-btn:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  .action-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
  }

  .action-btn.danger:hover:not(:disabled) {
    background-color: rgba(239, 68, 68, 0.15);
    color: var(--error-color, #ef4444);
  }

  .editor-wrapper {
    padding: 0;
  }

  .editor-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 8px 12px;
    border-top: 1px solid var(--border-color);
    background-color: var(--secondary-color);
  }

  .btn-save, .btn-cancel {
    padding: 6px 16px;
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

  .btn-cancel:hover:not(:disabled) {
    background-color: var(--hover-color);
  }

  .paragraph-preview {
    padding: 16px;
    color: var(--text-color);
    font-size: 0.95rem;
    line-height: 1.7;
    cursor: pointer;
  }

  .paragraph-preview:hover {
    background-color: var(--hover-color);
  }

  .paragraph-preview :global(p) {
    margin: 0 0 8px 0;
  }

  .paragraph-preview :global(p:last-child) {
    margin-bottom: 0;
  }

  .paragraph-preview :global(h2),
  .paragraph-preview :global(h3),
  .paragraph-preview :global(h4) {
    margin: 16px 0 8px 0;
    color: var(--text-color);
  }

  .paragraph-preview :global(a) {
    color: var(--accent-color);
  }

  .paragraph-preview :global(blockquote) {
    border-left: 3px solid var(--accent-color);
    padding-left: 16px;
    margin: 12px 0;
    color: var(--text-muted);
  }

  .paragraph-preview :global(ul),
  .paragraph-preview :global(ol) {
    padding-left: 24px;
    margin: 8px 0;
  }

  .paragraph-preview :global(code) {
    background-color: var(--primary-color);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.875em;
  }

  .empty-hint {
    color: var(--text-muted);
    font-style: italic;
    font-size: 0.875rem;
  }

  .add-paragraph-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 12px;
    border: 2px dashed var(--border-color);
    border-radius: 6px;
    background: none;
    color: var(--text-muted);
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.15s;
  }

  .add-paragraph-btn:hover:not(:disabled) {
    border-color: var(--accent-color);
    color: var(--accent-color);
    background-color: rgba(var(--accent-rgb, 74, 158, 255), 0.05);
  }

  .add-paragraph-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (max-width: 900px) {
    .paragraph-toolbar {
      padding: 4px 8px;
    }

    .paragraph-preview {
      padding: 12px;
    }
  }
</style>
