<!--
  @component RichTextEditor
  TipTap-based rich text editor for wiki descriptions.
  Lazy-loaded only when editing is active.

  Features:
  - Basic formatting (bold, italic, strikethrough)
  - Headings (H2, H3, H4)
  - Lists (bullet, ordered)
  - Blockquotes
  - Code blocks
  - Horizontal rules
  - Links
  - YouTube/Vimeo video embeds (resizable)
  - Image upload with hash deduplication (resizable)
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { Editor, Node, mergeAttributes } from '@tiptap/core';
  import StarterKit from '@tiptap/starter-kit';
  import Link from '@tiptap/extension-link';
  import { page } from '$app/stores';

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

  /** @type {boolean} */
  let isVideoModalOpen = false;

  /** @type {string} */
  let videoUrl = '';

  /** @type {string} */
  let videoWidth = '';

  /** @type {boolean} */
  let isUploading = false;

  /** @type {HTMLInputElement} */
  let fileInput;

  // Resize toolbar state
  let showResizeToolbar = false;
  let resizeToolbarPos = { top: 0, left: 0 };
  let activeResizeNodeType = null;
  let customWidth = '';

  // User state from session (read internally, no props needed)
  $: user = $page.data?.session?.user;
  $: canUploadImages = !!user?.verified;
  $: canAutoApprove = user?.grants?.includes('wiki.approve') || user?.grants?.includes('guide.edit') || false;

  // Custom YouTube/Vimeo video embed extension with resizable width
  const VideoEmbed = Node.create({
    name: 'videoEmbed',
    group: 'block',
    atom: true,

    addAttributes() {
      return {
        src: { default: null },
        provider: { default: 'youtube' },
        width: { default: null }
      };
    },

    parseHTML() {
      return [
        {
          tag: 'div[data-video-embed]',
          getAttrs: dom => ({
            src: dom.getAttribute('data-src'),
            provider: dom.getAttribute('data-provider') || 'youtube',
            width: dom.getAttribute('data-width') ? parseInt(dom.getAttribute('data-width')) : null
          })
        }
      ];
    },

    renderHTML({ HTMLAttributes }) {
      const { src, provider, width } = HTMLAttributes;
      let embedUrl = src;

      if (provider === 'youtube' && src) {
        const videoId = extractYouTubeId(src);
        if (videoId) {
          embedUrl = `https://www.youtube.com/embed/${videoId}`;
        }
      } else if (provider === 'vimeo' && src) {
        const videoId = extractVimeoId(src);
        if (videoId) {
          embedUrl = `https://player.vimeo.com/video/${videoId}`;
        }
      }

      const wrapperAttrs = {
        'data-video-embed': '',
        'data-src': src,
        'data-provider': provider,
        class: 'video-embed-wrapper'
      };

      if (width) {
        wrapperAttrs['data-width'] = String(width);
        wrapperAttrs.style = `width: ${width}px; max-width: 100%;`;
      }

      return ['div', mergeAttributes(wrapperAttrs), [
        'iframe', {
          src: embedUrl,
          frameborder: '0',
          allowfullscreen: 'true',
          allow: 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture',
          class: 'video-embed-iframe'
        }
      ]];
    },

    addCommands() {
      return {
        setVideoEmbed: (options) => ({ commands }) => {
          return commands.insertContent({
            type: this.name,
            attrs: options
          });
        }
      };
    }
  });

  // Custom resizable image node
  const ResizableImage = Node.create({
    name: 'resizableImage',
    group: 'block',
    atom: true,

    addAttributes() {
      return {
        src: { default: null },
        alt: { default: null },
        width: { default: null },
        pending: { default: false }
      };
    },

    parseHTML() {
      return [
        {
          tag: 'img[src]',
          getAttrs: dom => ({
            src: dom.getAttribute('src'),
            alt: dom.getAttribute('alt'),
            width: dom.getAttribute('data-width') ? parseInt(dom.getAttribute('data-width')) : null,
            pending: dom.getAttribute('data-pending') === 'true'
          })
        },
        {
          tag: 'div.pending-image-placeholder',
          getAttrs: dom => ({
            src: dom.getAttribute('data-src'),
            alt: dom.getAttribute('data-alt') || null,
            width: dom.getAttribute('data-width') ? parseInt(dom.getAttribute('data-width')) : null,
            pending: true
          })
        }
      ];
    },

    renderHTML({ HTMLAttributes }) {
      const { src, alt, width, pending } = HTMLAttributes;

      if (pending) {
        const attrs = {
          class: 'pending-image-placeholder',
          'data-src': src,
          'data-pending': 'true'
        };
        if (alt) attrs['data-alt'] = alt;
        if (width) {
          attrs['data-width'] = String(width);
          attrs.style = `width: ${width}px; max-width: 100%;`;
        }
        return ['div', mergeAttributes(attrs), 'Image pending approval'];
      }

      const imgAttrs = { src };
      if (alt) imgAttrs.alt = alt;
      if (width) {
        imgAttrs['data-width'] = String(width);
        imgAttrs.style = `width: ${width}px; max-width: 100%;`;
      }
      return ['img', mergeAttributes(imgAttrs)];
    },

    addCommands() {
      return {
        setResizableImage: (options) => ({ commands }) => {
          return commands.insertContent({
            type: this.name,
            attrs: options
          });
        }
      };
    }
  });

  // Extract YouTube video ID from various URL formats
  function extractYouTubeId(url) {
    if (!url) return null;
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
      /^([a-zA-Z0-9_-]{11})$/  // Just the ID
    ];
    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match) return match[1];
    }
    return null;
  }

  // Extract Vimeo video ID from URL
  function extractVimeoId(url) {
    if (!url) return null;
    const match = url.match(/(?:vimeo\.com\/|player\.vimeo\.com\/video\/)(\d+)/);
    return match ? match[1] : null;
  }

  // Detect video provider from URL
  function detectVideoProvider(url) {
    if (!url) return null;
    if (url.includes('youtube.com') || url.includes('youtu.be')) return 'youtube';
    if (url.includes('vimeo.com')) return 'vimeo';
    return null;
  }

  function updateResizeToolbar() {
    if (!editor || disabled) {
      showResizeToolbar = false;
      return;
    }

    const isVideo = editor.isActive('videoEmbed');
    const isImage = editor.isActive('resizableImage');

    if (!isVideo && !isImage) {
      showResizeToolbar = false;
      return;
    }

    activeResizeNodeType = isVideo ? 'videoEmbed' : 'resizableImage';

    // Find the selected DOM node
    const { node } = editor.state.selection;
    if (!node) {
      showResizeToolbar = false;
      return;
    }

    // Populate custom width input with current node width
    customWidth = node.attrs?.width ? String(node.attrs.width) : '';

    // Get the DOM element for the selected node
    const domPos = editor.view.nodeDOM(editor.state.selection.from);
    if (!domPos) {
      showResizeToolbar = false;
      return;
    }

    const editorRect = editorElement.getBoundingClientRect();
    const nodeRect = domPos.getBoundingClientRect();

    resizeToolbarPos = {
      top: nodeRect.bottom - editorRect.top + editorElement.scrollTop + 4,
      left: nodeRect.left - editorRect.left
    };

    showResizeToolbar = true;
  }

  function setMediaWidth(width) {
    if (!editor || !activeResizeNodeType) return;
    editor.chain().focus().updateAttributes(activeResizeNodeType, { width: width || null }).run();
    customWidth = width ? String(width) : '';
    // Toolbar stays visible; re-position after DOM update
    setTimeout(updateResizeToolbar, 50);
  }

  function applyCustomWidth() {
    const w = parseInt(customWidth);
    if (w && w >= 50) {
      setMediaWidth(w);
    }
  }

  function handleWidthKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      applyCustomWidth();
    }
  }

  onMount(() => {
    editor = new Editor({
      element: editorElement,
      extensions: [
        StarterKit.configure({
          // Disable link from StarterKit since we're adding it separately with custom config
          link: false,
          heading: {
            levels: [2, 3, 4]
          },
          codeBlock: {
            HTMLAttributes: {
              class: 'code-block'
            }
          },
          blockquote: {
            HTMLAttributes: {
              class: 'blockquote'
            }
          },
          horizontalRule: {
            HTMLAttributes: {
              class: 'horizontal-rule'
            }
          }
        }),
        Link.configure({
          openOnClick: false,
          HTMLAttributes: {
            class: 'editor-link'
          }
        }),
        VideoEmbed,
        ResizableImage
      ],
      content: content || '',
      editable: !disabled,
      onUpdate: ({ editor }) => {
        const html = editor.getHTML();
        dispatch('change', html);
      },
      onSelectionUpdate: () => {
        updateResizeToolbar();
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

  function toggleStrike() {
    editor?.chain().focus().toggleStrike().run();
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

  function toggleBlockquote() {
    editor?.chain().focus().toggleBlockquote().run();
  }

  function toggleCodeBlock() {
    editor?.chain().focus().toggleCodeBlock().run();
  }

  function insertHorizontalRule() {
    editor?.chain().focus().setHorizontalRule().run();
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
      const { from, to } = editor.state.selection;
      const hasSelection = from !== to;

      if (hasSelection) {
        editor?.chain().focus().extendMarkRange('link').setLink({ href: linkUrl }).run();
      } else if (linkText) {
        editor?.chain().focus()
          .insertContent({
            type: 'text',
            text: linkText,
            marks: [{ type: 'link', attrs: { href: linkUrl } }]
          })
          .run();
      } else {
        editor?.chain().focus()
          .insertContent({
            type: 'text',
            text: linkUrl,
            marks: [{ type: 'link', attrs: { href: linkUrl } }]
          })
          .run();
      }
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

  function openVideoModal() {
    videoUrl = '';
    videoWidth = '';
    isVideoModalOpen = true;
  }

  function insertVideo() {
    const provider = detectVideoProvider(videoUrl);
    if (provider) {
      const width = videoWidth ? parseInt(videoWidth) : null;
      editor?.chain().focus().setVideoEmbed({ src: videoUrl, provider, width }).run();
    }
    closeVideoModal();
  }

  function closeVideoModal() {
    isVideoModalOpen = false;
    videoUrl = '';
    videoWidth = '';
  }

  function triggerImageUpload() {
    fileInput?.click();
  }

  async function handleImageUpload(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    // Reset file input so same file can be re-selected
    event.target.value = '';

    isUploading = true;
    try {
      const formData = new FormData();
      formData.append('image', file);
      formData.append('entityType', 'richtext');
      formData.append('entityId', 'pending');
      if (canAutoApprove) {
        formData.append('autoApprove', 'true');
      }

      const res = await fetch('/api/uploads/entity-image', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        console.error('Image upload failed:', data.error || res.statusText);
        return;
      }

      const data = await res.json();

      if (data.approved && data.imageUrl) {
        editor?.chain().focus().setResizableImage({
          src: data.imageUrl,
          alt: file.name,
          pending: false
        }).run();
      } else if (data.hash && data.imageUrl) {
        editor?.chain().focus().setResizableImage({
          src: data.imageUrl,
          alt: file.name,
          pending: true
        }).run();
      } else {
        // No hash returned (shouldn't happen for richtext), use preview
        editor?.chain().focus().setResizableImage({
          src: data.previewUrl || '',
          alt: file.name,
          pending: true
        }).run();
      }
    } catch (err) {
      console.error('Image upload error:', err);
    } finally {
      isUploading = false;
    }
  }

  function isActive(name, attrs = {}) {
    return editor?.isActive(name, attrs) || false;
  }
</script>

<div class="rich-text-editor" class:disabled>
  {#if !disabled}
    <div class="toolbar">
      <!-- Text formatting -->
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
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('strike')}
          on:click={toggleStrike}
          title="Strikethrough"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="4" y1="12" x2="20" y2="12"/>
            <path d="M17.5 7.5c-.8-1.5-2.7-2.5-5-2.5-3 0-5.5 1.5-5.5 4 0 1.5 1 2.5 2.5 3"/>
            <path d="M8 16.5c.8 1.5 2.7 2.5 5 2.5 3 0 5.5-1.5 5.5-4 0-1-.3-1.7-.8-2.3"/>
          </svg>
        </button>
      </div>

      <div class="toolbar-separator"></div>

      <!-- Headings -->
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
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('heading', { level: 4 })}
          on:click={() => toggleHeading(4)}
          title="Heading 4"
        >
          H4
        </button>
      </div>

      <div class="toolbar-separator"></div>

      <!-- Lists -->
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

      <!-- Block elements -->
      <div class="toolbar-group">
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('blockquote')}
          on:click={toggleBlockquote}
          title="Blockquote"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21z"/>
            <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3z"/>
          </svg>
        </button>
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('codeBlock')}
          on:click={toggleCodeBlock}
          title="Code Block"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="16,18 22,12 16,6"/>
            <polyline points="8,6 2,12 8,18"/>
          </svg>
        </button>
        <button
          type="button"
          class="toolbar-btn"
          on:click={insertHorizontalRule}
          title="Horizontal Rule"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="2" y1="12" x2="22" y2="12"/>
          </svg>
        </button>
      </div>

      <div class="toolbar-separator"></div>

      <!-- Links and media -->
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
        <button
          type="button"
          class="toolbar-btn"
          on:click={openVideoModal}
          title="Embed Video (YouTube/Vimeo)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="2" y="4" width="20" height="16" rx="2"/>
            <polygon points="10,8 16,12 10,16" fill="currentColor" stroke="none"/>
          </svg>
        </button>
        {#if canUploadImages}
          <button
            type="button"
            class="toolbar-btn"
            class:uploading={isUploading}
            on:click={triggerImageUpload}
            disabled={isUploading}
            title="Upload Image"
          >
            {#if isUploading}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
                <path d="M12 2v4m0 12v4m-7.07-3.93l2.83-2.83m8.49-8.49l2.83-2.83M2 12h4m12 0h4M4.93 4.93l2.83 2.83m8.49 8.49l2.83 2.83"/>
              </svg>
            {:else}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <circle cx="8.5" cy="8.5" r="1.5"/>
                <path d="M21 15l-5-5L5 21"/>
              </svg>
            {/if}
          </button>
        {/if}
      </div>
    </div>
  {/if}

  <div class="editor-container" class:has-toolbar={!disabled}>
    <div bind:this={editorElement} class="editor-element"></div>

    {#if showResizeToolbar && !disabled}
      <div class="resize-toolbar" style="top: {resizeToolbarPos.top}px; left: {resizeToolbarPos.left}px;">
        <button type="button" class="resize-btn" on:click={() => setMediaWidth(null)} title="Reset to full width">Full</button>
        <div class="resize-width-input">
          <input
            type="number"
            bind:value={customWidth}
            on:keydown={handleWidthKeydown}
            on:blur={applyCustomWidth}
            placeholder="Width"
            min="50"
            max="1920"
          />
          <span class="resize-unit">px</span>
        </div>
      </div>
    {/if}
  </div>

  <!-- Hidden file input for image upload -->
  <input
    bind:this={fileInput}
    type="file"
    accept="image/jpeg,image/png,image/webp,image/gif"
    style="display:none"
    on:change={handleImageUpload}
  />

  {#if isLinkModalOpen}
    <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
    <div class="link-modal-overlay" role="dialog" on:click={closeLinkModal} on:keydown={(e) => e.key === 'Escape' && closeLinkModal()}>
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="link-modal" on:click|stopPropagation>
        <h4>Insert Link</h4>
        <div class="link-field">
          <label for="link-text">Link Text</label>
          <input
            id="link-text"
            type="text"
            bind:value={linkText}
            placeholder="Display text for the link"
          />
          <p class="field-hint">Leave empty to use the URL as text</p>
        </div>
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

  {#if isVideoModalOpen}
    <!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
    <div class="link-modal-overlay" role="dialog" on:click={closeVideoModal} on:keydown={(e) => e.key === 'Escape' && closeVideoModal()}>
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="link-modal" on:click|stopPropagation>
        <h4>Embed Video</h4>
        <div class="link-field">
          <label for="video-url">YouTube or Vimeo URL</label>
          <input
            id="video-url"
            type="url"
            bind:value={videoUrl}
            placeholder="https://www.youtube.com/watch?v=..."
          />
          <p class="field-hint">Supported: YouTube, Vimeo</p>
        </div>
        <div class="link-field">
          <label for="video-width">Width (px)</label>
          <input
            id="video-width"
            type="number"
            bind:value={videoWidth}
            placeholder="Leave empty for full width"
            min="200"
            max="1920"
          />
          <p class="field-hint">Leave empty for 100% width</p>
        </div>
        <div class="link-actions">
          <button type="button" class="btn-secondary" on:click={closeVideoModal}>Cancel</button>
          <button
            type="button"
            class="btn-primary"
            on:click={insertVideo}
            disabled={!detectVideoProvider(videoUrl)}
          >
            Embed Video
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

  .toolbar-btn.uploading {
    opacity: 0.6;
    cursor: wait;
  }

  .toolbar-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  :global(.spin) {
    animation: spin 1s linear infinite;
  }

  .editor-container {
    position: relative;
    min-height: 150px;
    max-height: 400px;
    overflow-y: auto;
  }

  .editor-container.has-toolbar {
    padding: 12px;
  }

  /* Resize toolbar */
  .resize-toolbar {
    position: absolute;
    display: flex;
    gap: 4px;
    padding: 4px 6px;
    background-color: var(--tertiary-color, #333);
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    z-index: 10;
  }

  .resize-btn {
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background: transparent;
    color: var(--text-color, #fff);
    cursor: pointer;
    transition: all 0.15s;
  }

  .resize-btn:hover {
    background-color: var(--accent-color, #4a9eff);
    border-color: var(--accent-color, #4a9eff);
    color: white;
  }

  .resize-width-input {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .resize-width-input input {
    width: 60px;
    padding: 2px 6px;
    font-size: 11px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background: var(--primary-color, #1a1a1a);
    color: var(--text-color, #fff);
    text-align: right;
    appearance: textfield;
    -moz-appearance: textfield;
  }

  .resize-width-input input::-webkit-inner-spin-button,
  .resize-width-input input::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }

  .resize-width-input input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .resize-unit {
    font-size: 11px;
    color: var(--text-muted, #999);
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

  :global(.tiptap-content s) {
    text-decoration: line-through;
    color: var(--text-muted, #999);
  }

  :global(.tiptap-content blockquote),
  :global(.tiptap-content .blockquote) {
    border-left: 4px solid var(--accent-color, #4a9eff);
    padding-left: 16px;
    margin: 1em 0;
    color: var(--text-muted, #999);
    font-style: italic;
  }

  :global(.tiptap-content pre),
  :global(.tiptap-content .code-block) {
    background-color: var(--tertiary-color, #333);
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    padding: 12px 16px;
    margin: 0.75em 0;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    overflow-x: auto;
  }

  :global(.tiptap-content code) {
    background-color: var(--tertiary-color, #333);
    border-radius: 3px;
    padding: 2px 6px;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
  }

  :global(.tiptap-content hr),
  :global(.tiptap-content .horizontal-rule) {
    border: none;
    border-top: 2px solid var(--border-color, #555);
    margin: 1.5em 0;
  }

  /* Video embed styles — resizable */
  :global(.tiptap-content .video-embed-wrapper) {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    margin: 1em 0;
    background-color: var(--tertiary-color, #333);
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
  }

  :global(.tiptap-content .video-embed-wrapper.ProseMirror-selectednode) {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: 2px;
  }

  :global(.tiptap-content .video-embed-iframe) {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border: none;
  }

  /* Image styles — resizable */
  :global(.tiptap-content img) {
    display: block;
    max-width: 100%;
    height: auto;
    border-radius: 6px;
    margin: 0.75em 0;
    cursor: pointer;
  }

  :global(.tiptap-content img.ProseMirror-selectednode) {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: 2px;
  }

  /* Pending image placeholder */
  :global(.tiptap-content .pending-image-placeholder),
  :global(.pending-image-placeholder) {
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--tertiary-color, #333);
    border: 2px dashed var(--border-color, #555);
    border-radius: 8px;
    color: var(--text-muted, #999);
    font-size: 0.875rem;
    min-height: 120px;
    max-width: 100%;
    margin: 0.75em 0;
    padding: 16px;
    cursor: pointer;
  }

  :global(.tiptap-content .pending-image-placeholder.ProseMirror-selectednode) {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: 2px;
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
    box-sizing: border-box;
    overflow: hidden;
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
    box-sizing: border-box;
  }

  .link-field input:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .field-hint {
    font-size: 11px;
    color: var(--text-muted, #999);
    margin: 4px 0 0 0;
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

  /* Mobile - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
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
