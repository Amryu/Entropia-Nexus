<!--
  @component RichTextEditor
  TipTap-based rich text editor for wiki descriptions.
  Lazy-loaded only when editing is active.
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { Editor } from '@tiptap/core';
  import StarterKit from '@tiptap/starter-kit';
  import Link from '@tiptap/extension-link';

  const dispatch = createEventDispatcher();

  /** @type {string} Initial HTML content */
  export let content = '';

  /** @type {string} Placeholder text when empty */
  export let placeholder = 'Enter description...';

  /** @type {boolean} Whether the editor is disabled */
  export let disabled = false;

  /** @type {Editor|null} */
  let editor = null;

  /** @type {HTMLElement} */
  let editorElement;

  /** @type {boolean} */
  let isLinkModalOpen = false;

  /** @type {string} */
  let linkUrl = '';

  /** @type {string} */
  let linkText = '';

  onMount(() => {
    editor = new Editor({
      element: editorElement,
      extensions: [
        StarterKit.configure({
          heading: {
            levels: [2, 3, 4]
          }
        }),
        Link.configure({
          openOnClick: false,
          HTMLAttributes: {
            class: 'editor-link'
          }
        })
      ],
      content: content || '',
      editable: !disabled,
      onUpdate: ({ editor }) => {
        const html = editor.getHTML();
        dispatch('change', html);
      },
      editorProps: {
        attributes: {
          class: 'tiptap-content',
          'data-placeholder': placeholder
        }
      }
    });
  });

  onDestroy(() => {
    if (editor) {
      editor.destroy();
    }
  });

  // Update content when prop changes externally
  $: if (editor && content !== editor.getHTML()) {
    editor.commands.setContent(content || '');
  }

  // Update editable state
  $: if (editor) {
    editor.setEditable(!disabled);
  }

  function toggleBold() {
    editor?.chain().focus().toggleBold().run();
  }

  function toggleItalic() {
    editor?.chain().focus().toggleItalic().run();
  }

  function toggleHeading(level) {
    editor?.chain().focus().toggleHeading({ level }).run();
  }

  function toggleBulletList() {
    editor?.chain().focus().toggleBulletList().run();
  }

  function toggleOrderedList() {
    editor?.chain().focus().toggleOrderedList().run();
  }

  function openLinkModal() {
    const { from, to } = editor.state.selection;
    const selectedText = editor.state.doc.textBetween(from, to);
    linkText = selectedText;
    linkUrl = editor.getAttributes('link').href || '';
    isLinkModalOpen = true;
  }

  function insertLink() {
    if (!linkUrl) {
      editor?.chain().focus().unsetLink().run();
    } else {
      editor?.chain().focus().extendMarkRange('link').setLink({ href: linkUrl }).run();
    }
    closeLinkModal();
  }

  function removeLink() {
    editor?.chain().focus().unsetLink().run();
    closeLinkModal();
  }

  function closeLinkModal() {
    isLinkModalOpen = false;
    linkUrl = '';
    linkText = '';
  }

  function isActive(name, attrs = {}) {
    return editor?.isActive(name, attrs) || false;
  }
</script>

<div class="rich-text-editor" class:disabled>
  {#if !disabled}
    <div class="toolbar">
      <div class="toolbar-group">
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('bold')}
          on:click={toggleBold}
          title="Bold (Ctrl+B)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <path d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/>
            <path d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/>
          </svg>
        </button>
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('italic')}
          on:click={toggleItalic}
          title="Italic (Ctrl+I)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="19" y1="4" x2="10" y2="4"/>
            <line x1="14" y1="20" x2="5" y2="20"/>
            <line x1="15" y1="4" x2="9" y2="20"/>
          </svg>
        </button>
      </div>

      <div class="toolbar-separator"></div>

      <div class="toolbar-group">
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('heading', { level: 2 })}
          on:click={() => toggleHeading(2)}
          title="Heading 2"
        >
          H2
        </button>
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('heading', { level: 3 })}
          on:click={() => toggleHeading(3)}
          title="Heading 3"
        >
          H3
        </button>
      </div>

      <div class="toolbar-separator"></div>

      <div class="toolbar-group">
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('bulletList')}
          on:click={toggleBulletList}
          title="Bullet List"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="9" y1="6" x2="20" y2="6"/>
            <line x1="9" y1="12" x2="20" y2="12"/>
            <line x1="9" y1="18" x2="20" y2="18"/>
            <circle cx="4" cy="6" r="1.5" fill="currentColor"/>
            <circle cx="4" cy="12" r="1.5" fill="currentColor"/>
            <circle cx="4" cy="18" r="1.5" fill="currentColor"/>
          </svg>
        </button>
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('orderedList')}
          on:click={toggleOrderedList}
          title="Numbered List"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="10" y1="6" x2="21" y2="6"/>
            <line x1="10" y1="12" x2="21" y2="12"/>
            <line x1="10" y1="18" x2="21" y2="18"/>
            <text x="3" y="8" font-size="8" fill="currentColor">1</text>
            <text x="3" y="14" font-size="8" fill="currentColor">2</text>
            <text x="3" y="20" font-size="8" fill="currentColor">3</text>
          </svg>
        </button>
      </div>

      <div class="toolbar-separator"></div>

      <div class="toolbar-group">
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('link')}
          on:click={openLinkModal}
          title="Insert Link"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
          </svg>
        </button>
      </div>
    </div>
  {/if}

  <div class="editor-container" class:has-toolbar={!disabled}>
    <div bind:this={editorElement} class="editor-element"></div>
  </div>

  {#if isLinkModalOpen}
    <div class="link-modal-overlay" on:click={closeLinkModal} on:keydown={(e) => e.key === 'Escape' && closeLinkModal()}>
      <div class="link-modal" on:click|stopPropagation>
        <h4>Insert Link</h4>
        <div class="link-field">
          <label for="link-url">URL</label>
          <input
            id="link-url"
            type="url"
            bind:value={linkUrl}
            placeholder="https://example.com"
          />
        </div>
        <div class="link-actions">
          <button type="button" class="btn-secondary" on:click={closeLinkModal}>Cancel</button>
          {#if isActive('link')}
            <button type="button" class="btn-danger" on:click={removeLink}>Remove Link</button>
          {/if}
          <button type="button" class="btn-primary" on:click={insertLink}>
            {isActive('link') ? 'Update' : 'Insert'}
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .rich-text-editor {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    background-color: var(--secondary-color, #2a2a2a);
    overflow: hidden;
  }

  .rich-text-editor.disabled {
    border-color: transparent;
    background-color: transparent;
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px;
    background-color: var(--tertiary-color, #333);
    border-bottom: 1px solid var(--border-color, #555);
    flex-wrap: wrap;
  }

  .toolbar-group {
    display: flex;
    gap: 2px;
  }

  .toolbar-separator {
    width: 1px;
    height: 20px;
    background-color: var(--border-color, #555);
    margin: 0 4px;
  }

  .toolbar-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    color: var(--text-color, #fff);
    cursor: pointer;
    font-size: 12px;
    font-weight: 600;
    transition: all 0.15s;
  }

  .toolbar-btn:hover {
    background-color: var(--hover-color, #444);
    border-color: var(--border-color, #555);
  }

  .toolbar-btn.active {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .editor-container {
    min-height: 150px;
    max-height: 400px;
    overflow-y: auto;
  }

  .editor-container.has-toolbar {
    padding: 12px;
  }

  :global(.tiptap-content) {
    outline: none;
    min-height: 120px;
    color: var(--text-color, #fff);
    font-size: 14px;
    line-height: 1.6;
  }

  :global(.tiptap-content:empty::before) {
    content: attr(data-placeholder);
    color: var(--text-muted, #999);
    pointer-events: none;
    position: absolute;
  }

  :global(.tiptap-content p) {
    margin: 0 0 0.75em 0;
  }

  :global(.tiptap-content p:last-child) {
    margin-bottom: 0;
  }

  :global(.tiptap-content h2) {
    font-size: 1.5em;
    font-weight: 600;
    margin: 1em 0 0.5em 0;
    color: var(--text-color, #fff);
  }

  :global(.tiptap-content h3) {
    font-size: 1.25em;
    font-weight: 600;
    margin: 1em 0 0.5em 0;
    color: var(--text-color, #fff);
  }

  :global(.tiptap-content h4) {
    font-size: 1.1em;
    font-weight: 600;
    margin: 1em 0 0.5em 0;
    color: var(--text-color, #fff);
  }

  :global(.tiptap-content ul),
  :global(.tiptap-content ol) {
    padding-left: 1.5em;
    margin: 0.5em 0;
  }

  :global(.tiptap-content li) {
    margin: 0.25em 0;
  }

  :global(.tiptap-content a),
  :global(.tiptap-content .editor-link) {
    color: var(--accent-color, #4a9eff);
    text-decoration: underline;
    cursor: pointer;
  }

  :global(.tiptap-content strong) {
    font-weight: 600;
  }

  :global(.tiptap-content em) {
    font-style: italic;
  }

  /* Link Modal */
  .link-modal-overlay {
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

  .link-modal {
    background-color: var(--secondary-color, #2a2a2a);
    border: 1px solid var(--border-color, #555);
    border-radius: 8px;
    padding: 20px;
    min-width: 300px;
    max-width: 400px;
  }

  .link-modal h4 {
    margin: 0 0 16px 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color, #fff);
  }

  .link-field {
    margin-bottom: 16px;
  }

  .link-field label {
    display: block;
    font-size: 13px;
    color: var(--text-muted, #999);
    margin-bottom: 4px;
  }

  .link-field input {
    width: 100%;
    padding: 8px 12px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--primary-color, #1a1a1a);
    color: var(--text-color, #fff);
    font-size: 14px;
  }

  .link-field input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .link-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .link-actions button {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }

  .btn-primary {
    background-color: var(--accent-color, #4a9eff);
    border: none;
    color: white;
  }

  .btn-primary:hover {
    filter: brightness(1.1);
  }

  .btn-secondary {
    background-color: transparent;
    border: 1px solid var(--border-color, #555);
    color: var(--text-color, #fff);
  }

  .btn-secondary:hover {
    background-color: var(--hover-color, #444);
  }

  .btn-danger {
    background-color: var(--error-color, #ef4444);
    border: none;
    color: white;
  }

  .btn-danger:hover {
    filter: brightness(1.1);
  }

  @media (max-width: 767px) {
    .toolbar {
      padding: 6px;
      gap: 2px;
    }

    .toolbar-btn {
      width: 28px;
      height: 28px;
    }

    .toolbar-separator {
      height: 16px;
    }

    .link-modal {
      margin: 16px;
      min-width: auto;
      width: calc(100% - 32px);
    }
  }
</style>
