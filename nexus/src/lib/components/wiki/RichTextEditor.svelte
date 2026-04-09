<!--
  @component RichTextEditor
  TipTap-based rich text editor for wiki descriptions and market listings.
  Lazy-loaded only when editing is active.

  Features (all enabled by default, configurable via props):
  - Basic formatting (bold, italic, strikethrough)
  - Headings (H2, H3, H4) — showHeadings
  - Lists (bullet, ordered)
  - Blockquotes
  - Code blocks — showCodeBlock
  - Horizontal rules
  - Links (with relative link support)
  - YouTube/Vimeo video embeds (resizable) — showVideo
  - Image upload with hash deduplication (resizable) — showImages

  Market usage: showHeadings={false} showCodeBlock={false} showVideo={false} showImages={false}
-->
<script>
  // @ts-nocheck
  import { onMount, onDestroy, tick } from 'svelte';
  import { Editor, Node, mergeAttributes } from '@tiptap/core';
  import StarterKit from '@tiptap/starter-kit';
  import Link from '@tiptap/extension-link';
  import { page } from '$app/stores';

  /** Suppress the initial onUpdate that TipTap fires when normalizing empty content */
  let initialized = $state(false);

  

  

  

  

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {string} [content]
   * @property {string} [placeholder]
   * @property {boolean} [disabled]
   * @property {boolean} [showHeadings]
   * @property {boolean} [showCodeBlock]
   * @property {boolean} [showVideo]
   * @property {boolean} [showImages]
   * @property {boolean} [showWaypoints]
   * @property {boolean} [handleMarkdownPaste]
   */

  /** @type {Props} */
  let {
    content = $bindable(''),
    placeholder = 'Enter description...',
    disabled = false,
    showHeadings = true,
    showCodeBlock = true,
    showVideo = true,
    showImages = true,
    showWaypoints = false,
    handleMarkdownPaste = false,
    onchange
  } = $props();

  /** @type {Editor|null} */
  let editor = $state(null);

  /** @type {HTMLElement} */
  let editorElement = $state();

  /** @type {boolean} */
  let isLinkModalOpen = $state(false);

  /** @type {string} */
  let linkUrl = $state('');

  /** @type {string} */
  let linkText = $state('');

  /** @type {boolean} */
  let isVideoModalOpen = $state(false);

  /** @type {string} */
  let videoUrl = $state('');

  /** @type {string} */
  let videoWidth = $state('');

  /** @type {boolean} */
  let isUploading = $state(false);

  /** @type {HTMLInputElement} */
  let fileInput = $state();

  // Resize toolbar state
  let showResizeToolbar = $state(false);
  let resizeToolbarPos = $state({ top: 0, left: 0 });
  let activeResizeNodeType = null;
  let customWidth = $state('');

  // User state from session (read internally, no props needed)
  let user = $derived($page.data?.session?.user);
  let canUploadImages = $derived(!!user?.verified);
  let canAutoApprove = $derived(user?.grants?.includes('wiki.approve') || user?.grants?.includes('guide.edit') || false);

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

  // Inline waypoint element — clickable chip that copies /wp <waypoint> to clipboard
  const WaypointInline = Node.create({
    name: 'waypointInline',
    inline: true,
    group: 'inline',
    atom: true,

    addAttributes() {
      return {
        waypoint: { default: '' },
        label: { default: null }
      };
    },

    parseHTML() {
      return [{
        tag: 'span[data-waypoint]',
        getAttrs: dom => ({
          waypoint: dom.getAttribute('data-waypoint') || '',
          label: dom.getAttribute('data-label') || null
        })
      }];
    },

    renderHTML({ HTMLAttributes }) {
      const { waypoint, label } = HTMLAttributes;
      return ['span', mergeAttributes({
        'data-waypoint': waypoint,
        ...(label ? { 'data-label': label } : {}),
        class: 'waypoint-inline',
        title: `Click to copy waypoint: /wp ${waypoint}`
      }), label || waypoint];
    },

    addCommands() {
      return {
        setWaypointInline: (options) => ({ commands }) => {
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

  // Markdown paste detection patterns
  const MD_PATTERNS = [
    /^#{1,6}\s/m,           // headings
    /\*\*.+?\*\*/,          // bold
    /^[-*+]\s/m,            // unordered list
    /^\d+\.\s/m,            // ordered list
    /\[.+?\]\(.+?\)/,       // links
    /^```/m,                // code fences
    /^>\s/m,                // blockquotes
    /^---+$/m               // horizontal rules
  ];

  function looksLikeMarkdown(text) {
    if (!text) return false;
    let matches = 0;
    for (const pattern of MD_PATTERNS) {
      if (pattern.test(text)) matches++;
      if (matches >= 2) return true;
    }
    return false;
  }

  /** @type {any} Lazily loaded markdown-it instance */
  let mdInstance = null;

  async function convertMarkdownToHtml(markdown) {
    if (!mdInstance) {
      const { default: MarkdownIt } = await import('markdown-it');
      mdInstance = new MarkdownIt({ html: false, linkify: true, breaks: true });
    }
    return mdInstance.render(markdown);
  }

  onMount(async () => {
    const extensions = [
      StarterKit.configure({
        // Disable link from StarterKit since we're adding it separately with custom config
        link: false,
        heading: showHeadings ? { levels: [2, 3, 4] } : false,
        codeBlock: showCodeBlock ? { HTMLAttributes: { class: 'code-block' } } : false,
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
          class: 'editor-link',
          rel: 'noopener noreferrer'
        }
      })
    ];

    if (showVideo) extensions.push(VideoEmbed);
    if (showImages) extensions.push(ResizableImage);
    if (showWaypoints) extensions.push(WaypointInline);

    editor = new Editor({
      element: editorElement,
      extensions,
      content: content || '',
      editable: !disabled,
      onUpdate: ({ editor }) => {
        if (!initialized) return;
        const html = editor.getHTML();
        // Skip if this is just TipTap normalizing prop content (e.g. '' -> '<p></p>')
        if (html === lastExternalHtml) return;
        lastExternalHtml = '';
        content = html;
        onchange?.(html);
      },
      onSelectionUpdate: () => {
        updateResizeToolbar();
      },
      editorProps: {
        attributes: {
          class: 'tiptap-content',
          'data-placeholder': placeholder
        },
        handleClick: (view, pos, event) => {
          if (disabled) return false;
          const docSize = view.state.doc.content.size;
          if (pos < 0 || pos > docSize) return false;
          // Click on a link -> open link edit modal
          const resolvedPos = view.state.doc.resolve(pos);
          const linkMark = resolvedPos.marks().find(m => m.type.name === 'link');
          if (linkMark) {
            event.preventDefault();
            // Select the full link range so the modal can update/remove it
            let linkFrom = pos, linkTo = pos;
            const searchFrom = Math.max(0, pos - 500);
            const searchTo = Math.min(docSize, pos + 500);
            view.state.doc.nodesBetween(searchFrom, searchTo, (node, nodePos) => {
              if (node.isText) {
                const mark = node.marks.find(m => m.type.name === 'link' && m.attrs.href === linkMark.attrs.href);
                if (mark) {
                  const nodeEnd = nodePos + node.nodeSize;
                  if (nodePos <= pos && nodeEnd >= pos) {
                    linkFrom = nodePos;
                    linkTo = nodeEnd;
                  }
                }
              }
            });
            editor.commands.setTextSelection({ from: linkFrom, to: linkTo });
            linkText = view.state.doc.textBetween(linkFrom, linkTo);
            linkUrl = linkMark.attrs.href || '';
            isLinkModalOpen = true;
            return true;
          }
          // Click on a waypoint -> open waypoint edit modal
          if (showWaypoints) {
            const nodeAtPos = view.state.doc.nodeAt(pos);
            if (nodeAtPos?.type.name === 'waypointInline') {
              event.preventDefault();
              // Select the waypoint node so updateAttributes/deleteSelection targets it
              editor.commands.setNodeSelection(pos);
              waypointString = normalizeWaypointString(nodeAtPos.attrs.waypoint || '');
              waypointLabel = nodeAtPos.attrs.label || '';
              waypointError = '';
              isEditingWaypoint = true;
              isWaypointModalOpen = true;
              loadWaypointPlanets();
              return true;
            }
          }
          return false;
        },
        handlePaste: handleMarkdownPaste ? (view, event) => {
          const plainText = event.clipboardData?.getData('text/plain');
          if (plainText && looksLikeMarkdown(plainText)) {
            event.preventDefault();
            convertMarkdownToHtml(plainText).then(html => {
              editor?.commands.insertContent(html);
            });
            return true;
          }
          return false;
        } : undefined
      }
    });

    // Allow TipTap's initial content normalization to complete before accepting changes
    await tick();
    lastExternalHtml = editor.getHTML();
    initialized = true;

    // Click-to-copy for inline waypoints is handled by the global handler in +layout.svelte
  });

  onDestroy(() => {
    if (editor) {
      editor.destroy();
    }
  });

  // Update content when prop changes externally (suppress onUpdate echo).
  // lastExternalHtml tracks the TipTap-normalized HTML after a prop-driven setContent,
  // so onUpdate can distinguish user edits from TipTap normalization (e.g. '' -> '<p></p>').
  let lastExternalHtml = '';
  $effect(() => {
    if (!editor) return;
    const incoming = content || '';
    if (incoming !== editor.getHTML()) {
      initialized = false;
      editor.commands.setContent(incoming);
      lastExternalHtml = editor.getHTML();
      tick().then(() => { initialized = true; });
    }
  });

  // Update editable state
  $effect(() => {
    if (editor) {
      editor.setEditable(!disabled);
    }
  });

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

  /** Convert same-site URLs to relative paths */
  function normalizeLink(url) {
    if (!url) return url;
    try {
      const domain = import.meta.env.VITE_DOMAIN;
      const parsed = new URL(url, `https://${domain}`);
      if (parsed.hostname === domain || parsed.hostname === `www.${domain}` || parsed.hostname === `dev.${domain}`) {
        return parsed.pathname + parsed.search + parsed.hash;
      }
    } catch { /* not a valid URL, return as-is */ }
    return url;
  }

  function insertLink() {
    if (!linkUrl) {
      editor?.chain().focus().unsetLink().run();
    } else {
      const href = normalizeLink(linkUrl);
      const { from, to } = editor.state.selection;
      const hasSelection = from !== to;

      if (hasSelection) {
        editor?.chain().focus().extendMarkRange('link').setLink({ href }).run();
      } else if (linkText) {
        editor?.chain().focus()
          .insertContent({
            type: 'text',
            text: linkText,
            marks: [{ type: 'link', attrs: { href } }]
          })
          .run();
      } else {
        editor?.chain().focus()
          .insertContent({
            type: 'text',
            text: linkUrl,
            marks: [{ type: 'link', attrs: { href } }]
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

  // Waypoint modal state
  let isWaypointModalOpen = $state(false);
  let waypointString = $state('');
  let waypointLabel = $state('');
  let isEditingWaypoint = $state(false);
  let waypointError = $state('');

  // Planet data for waypoint validation (fetched lazily when waypoints are enabled)
  const TILE_SIZE = 8192;
  let waypointPlanets = [];

  async function loadWaypointPlanets() {
    if (waypointPlanets.length || !showWaypoints) return;
    try {
      const res = await fetch(import.meta.env.VITE_API_URL + '/planets');
      const data = await res.json();
      waypointPlanets = (data || []).filter(p => p.Id > 0);
    } catch { waypointPlanets = []; }
  }

  /** Parse waypoint string, stripping optional /wp prefix */
  function parseWaypointString(str) {
    if (!str) return null;
    let s = str.trim();
    // Strip /wp prefix
    if (s.toLowerCase().startsWith('/wp ')) s = s.slice(4).trim();
    const match = s.match(/\[([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,\]]+)(?:,\s*([^\]]*))?\]/);
    if (!match) return null;
    return {
      planet: match[1].trim(),
      x: parseFloat(match[2]),
      y: parseFloat(match[3]),
      z: parseFloat(match[4]),
      name: match[5]?.trim() || ''
    };
  }

  /** Validate a waypoint string and return an error message or '' if valid */
  function validateWaypoint(str) {
    const parsed = parseWaypointString(str);
    if (!parsed) return 'Invalid format. Use [Planet, x, y, z, Name]';
    if (isNaN(parsed.x) || isNaN(parsed.y) || isNaN(parsed.z)) return 'Coordinates must be numbers';
    // Validate planet name (case-insensitive against TechnicalName or Name)
    const planetMatch = waypointPlanets.find(p =>
      p.Name.toLowerCase() === parsed.planet.toLowerCase() ||
      p.Properties?.TechnicalName?.toLowerCase() === parsed.planet.toLowerCase()
    );
    if (!planetMatch) return `Unknown planet: ${parsed.planet}`;
    // Validate coordinate bounds
    const map = planetMatch.Properties?.Map;
    if (map) {
      const minX = map.X * TILE_SIZE;
      const maxX = (map.X + map.Width) * TILE_SIZE;
      const minY = map.Y * TILE_SIZE;
      const maxY = (map.Y + map.Height) * TILE_SIZE;
      if (parsed.x < minX || parsed.x > maxX || parsed.y < minY || parsed.y > maxY) {
        return `Coordinates out of bounds for ${planetMatch.Name} (x: ${minX}-${maxX}, y: ${minY}-${maxY})`;
      }
    }
    // Validate name length
    if (parsed.name && parsed.name.length > 50) return 'Waypoint name must be 50 characters or less';
    return '';
  }

  /** Normalize waypoint string: strip /wp prefix, keep the bracket content */
  function normalizeWaypointString(str) {
    if (!str) return str;
    let s = str.trim();
    if (s.toLowerCase().startsWith('/wp ')) s = s.slice(4).trim();
    return s;
  }

  function openWaypointModal() {
    waypointString = '';
    waypointLabel = '';
    waypointError = '';
    isEditingWaypoint = false;
    isWaypointModalOpen = true;
    loadWaypointPlanets();
  }

  function insertWaypoint() {
    const normalized = normalizeWaypointString(waypointString);
    const error = validateWaypoint(normalized);
    if (error) {
      waypointError = error;
      return;
    }
    if (isEditingWaypoint) {
      editor?.chain().focus().updateAttributes('waypointInline', {
        waypoint: normalized,
        label: waypointLabel.trim() || null
      }).run();
    } else {
      editor?.chain().focus().setWaypointInline({
        waypoint: normalized,
        label: waypointLabel.trim() || null
      }).run();
    }
    closeWaypointModal();
  }

  function removeWaypoint() {
    editor?.chain().focus().deleteSelection().run();
    closeWaypointModal();
  }

  function closeWaypointModal() {
    isWaypointModalOpen = false;
    waypointString = '';
    waypointLabel = '';
    waypointError = '';
    isEditingWaypoint = false;
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
          onclick={toggleBold}
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
          onclick={toggleItalic}
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
          onclick={toggleStrike}
          title="Strikethrough"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="4" y1="12" x2="20" y2="12"/>
            <path d="M17.5 7.5c-.8-1.5-2.7-2.5-5-2.5-3 0-5.5 1.5-5.5 4 0 1.5 1 2.5 2.5 3"/>
            <path d="M8 16.5c.8 1.5 2.7 2.5 5 2.5 3 0 5.5-1.5 5.5-4 0-1-.3-1.7-.8-2.3"/>
          </svg>
        </button>
      </div>

      {#if showHeadings}
        <div class="toolbar-separator"></div>

        <!-- Headings -->
        <div class="toolbar-group">
          <button
            type="button"
            class="toolbar-btn"
            class:active={isActive('heading', { level: 2 })}
            onclick={() => toggleHeading(2)}
            title="Heading 2"
          >
            H2
          </button>
          <button
            type="button"
            class="toolbar-btn"
            class:active={isActive('heading', { level: 3 })}
            onclick={() => toggleHeading(3)}
            title="Heading 3"
          >
            H3
          </button>
          <button
            type="button"
            class="toolbar-btn"
            class:active={isActive('heading', { level: 4 })}
            onclick={() => toggleHeading(4)}
            title="Heading 4"
          >
            H4
          </button>
        </div>
      {/if}

      <div class="toolbar-separator"></div>

      <!-- Lists -->
      <div class="toolbar-group">
        <button
          type="button"
          class="toolbar-btn"
          class:active={isActive('bulletList')}
          onclick={toggleBulletList}
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
          onclick={toggleOrderedList}
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
          onclick={toggleBlockquote}
          title="Blockquote"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21z"/>
            <path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3z"/>
          </svg>
        </button>
        {#if showCodeBlock}
          <button
            type="button"
            class="toolbar-btn"
            class:active={isActive('codeBlock')}
            onclick={toggleCodeBlock}
            title="Code Block"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="16,18 22,12 16,6"/>
              <polyline points="8,6 2,12 8,18"/>
            </svg>
          </button>
        {/if}
        <button
          type="button"
          class="toolbar-btn"
          onclick={insertHorizontalRule}
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
          onclick={openLinkModal}
          title="Insert Link"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
          </svg>
        </button>
        {#if showVideo}
          <button
            type="button"
            class="toolbar-btn"
            onclick={openVideoModal}
            title="Embed Video (YouTube/Vimeo)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="4" width="20" height="16" rx="2"/>
              <polygon points="10,8 16,12 10,16" fill="currentColor" stroke="none"/>
            </svg>
          </button>
        {/if}
        {#if showImages && canUploadImages}
          <button
            type="button"
            class="toolbar-btn"
            class:uploading={isUploading}
            onclick={triggerImageUpload}
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
        {#if showWaypoints}
          <button
            type="button"
            class="toolbar-btn"
            onclick={openWaypointModal}
            title="Insert Waypoint"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
              <circle cx="12" cy="10" r="3"/>
            </svg>
          </button>
        {/if}
      </div>
    </div>
  {/if}

  <div class="editor-container" class:has-toolbar={!disabled}>
    <div bind:this={editorElement} class="editor-element"></div>

    {#if showResizeToolbar && !disabled && (showVideo || showImages)}
      <div class="resize-toolbar" style="top: {resizeToolbarPos.top}px; left: {resizeToolbarPos.left}px;">
        <button type="button" class="resize-btn" onclick={() => setMediaWidth(null)} title="Reset to full width">Full</button>
        <div class="resize-width-input">
          <input
            type="number"
            bind:value={customWidth}
            onkeydown={handleWidthKeydown}
            onblur={applyCustomWidth}
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
  {#if showImages}
    <input
      bind:this={fileInput}
      type="file"
      accept="image/jpeg,image/png,image/webp,image/gif"
      style="display:none"
      onchange={handleImageUpload}
    />
  {/if}

  {#if isLinkModalOpen}
    <div class="link-modal-overlay" role="presentation" onclick={closeLinkModal} onkeydown={(e) => e.key === 'Escape' && closeLinkModal()}>
      <div class="link-modal" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <h4>{isActive('link') ? 'Edit' : 'Insert'} Link</h4>
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
            type="text"
            bind:value={linkUrl}
            placeholder="https://example.com or /relative/path"
          />
        </div>
        <div class="link-actions">
          <button type="button" class="btn-secondary" onclick={closeLinkModal}>Cancel</button>
          {#if isActive('link')}
            <button type="button" class="btn-danger" onclick={removeLink}>Remove Link</button>
          {/if}
          <button type="button" class="btn-primary" onclick={insertLink}>
            {isActive('link') ? 'Update' : 'Insert'}
          </button>
        </div>
      </div>
    </div>
  {/if}

  {#if showVideo && isVideoModalOpen}
    <div class="link-modal-overlay" role="presentation" onclick={closeVideoModal} onkeydown={(e) => e.key === 'Escape' && closeVideoModal()}>
      <div class="link-modal" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
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
          <button type="button" class="btn-secondary" onclick={closeVideoModal}>Cancel</button>
          <button
            type="button"
            class="btn-primary"
            onclick={insertVideo}
            disabled={!detectVideoProvider(videoUrl)}
          >
            Embed Video
          </button>
        </div>
      </div>
    </div>
  {/if}

  {#if showWaypoints && isWaypointModalOpen}
    <div class="link-modal-overlay" role="presentation" onclick={closeWaypointModal} onkeydown={(e) => e.key === 'Escape' && closeWaypointModal()}>
      <div class="link-modal" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <h4>{isEditingWaypoint ? 'Edit' : 'Insert'} Waypoint</h4>
        <div class="link-field">
          <label for="waypoint-string">Waypoint</label>
          <input
            id="waypoint-string"
            type="text"
            bind:value={waypointString}
            oninput={() => waypointError = ''}
            placeholder="[Calypso, 123, 456, 100, Name]"
          />
          {#if waypointError}
            <p class="field-error">{waypointError}</p>
          {:else}
            <p class="field-hint">Paste a full waypoint string (with or without /wp prefix)</p>
          {/if}
        </div>
        <div class="link-field">
          <label for="waypoint-label">Label (optional)</label>
          <input
            id="waypoint-label"
            type="text"
            bind:value={waypointLabel}
            placeholder="Display text for this waypoint"
          />
          <p class="field-hint">Leave empty to show the coordinates</p>
        </div>
        <div class="link-actions">
          <button type="button" class="btn-secondary" onclick={closeWaypointModal}>Cancel</button>
          {#if isEditingWaypoint}
            <button type="button" class="btn-danger" onclick={removeWaypoint}>Remove</button>
          {/if}
          <button
            type="button"
            class="btn-primary"
            onclick={insertWaypoint}
            disabled={!waypointString.trim()}
          >
            {isEditingWaypoint ? 'Update' : 'Insert'}
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

  /* Inline waypoint chip */
  :global(.tiptap-content .waypoint-inline) {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    background-color: rgba(74, 158, 255, 0.12);
    border: 1px solid var(--accent-color, #4a9eff);
    border-radius: 3px;
    padding: 1px 5px;
    font-size: 0.85em;
    font-family: 'Cascadia Code', 'Fira Code', monospace;
    color: var(--accent-color, #4a9eff);
    cursor: pointer;
    vertical-align: baseline;
    line-height: inherit;
    white-space: nowrap;
    transition: background-color 0.15s, color 0.15s, border-color 0.15s;
  }

  /* Copy icon */
  :global(.tiptap-content .waypoint-inline::before) {
    content: '';
    display: inline-block;
    width: 12px;
    height: 12px;
    flex-shrink: 0;
    background-color: currentColor;
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Crect x='9' y='9' width='13' height='13' rx='2' ry='2'/%3E%3Cpath d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'/%3E%3C/svg%3E");
    mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Crect x='9' y='9' width='13' height='13' rx='2' ry='2'/%3E%3Cpath d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'/%3E%3C/svg%3E");
    -webkit-mask-size: contain;
    mask-size: contain;
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
  }

  :global(.tiptap-content .waypoint-inline:hover) {
    background-color: var(--accent-color, #4a9eff);
    color: white;
  }

  :global(.tiptap-content .waypoint-inline.ProseMirror-selectednode) {
    outline: 2px solid var(--accent-color, #4a9eff);
    outline-offset: 1px;
  }

  /* Checkmark icon on copy */
  :global(.tiptap-content .waypoint-inline.copied::before) {
    -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E");
    mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E");
  }

  :global(.tiptap-content .waypoint-inline.copied) {
    background-color: var(--success-color, #28a745);
    border-color: var(--success-color, #28a745);
    color: white;
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

  .field-hint,
  .field-error {
    font-size: 11px;
    margin: 4px 0 0 0;
  }

  .field-hint {
    color: var(--text-muted, #999);
  }

  .field-error {
    color: var(--danger-color, #dc3545);
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
