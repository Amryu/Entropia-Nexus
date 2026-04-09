<script>
  //@ts-nocheck
  import { getTopCategory } from '../../market/exchange/orderUtils';
  import { hasItemTag } from '$lib/util.js';

  /**
   * @typedef {Object} Props
   * @property {boolean} [show]
   * @property {object|null} [node] - The container tree node being configured
   * @property {Array} [items] - All inventory items within this container
   * @property {Map} [itemLookup] - item_id -> slim item
   * @property {object|null} [existingFilter] - Current filter config for this node
   * @property {() => void} [onclose]
   * @property {(filter: object|null) => void} [onsave]
   */

  /** @type {Props} */
  let {
    show = false,
    node = null,
    items = [],
    itemLookup = new Map(),
    existingFilter = null,
    onclose,
    onsave,
  } = $props();

  const ALL_CATEGORIES = [
    'Weapons', 'Armor', 'Tools', 'Enhancers', 'Clothes',
    'Blueprints', 'Materials', 'Consumables', 'Vehicles', 'Pets',
    'Skill Implants', 'Furnishings', 'Strongboxes', 'Other'
  ];

  const ALL_TAGS = [
    { value: 'L', label: 'Limited' },
    { value: 'M', label: 'Male' },
    { value: 'F', label: 'Female' },
    { value: 'C', label: 'Customizable' },
  ];

  function createRule() {
    return { action: 'include', negate: false, substring: '', useRegex: false, itemTypes: [], tags: [] };
  }

  /**
   * Normalize legacy filter format to new rules-based format.
   */
  function normalizeFilter(filter) {
    if (!filter || typeof filter !== 'object') return [];
    if (Array.isArray(filter.filters)) return filter.filters.map(r => ({
      action: r.action || 'include',
      negate: !!r.negate,
      substring: r.substring || '',
      useRegex: !!r.useRegex,
      itemTypes: r.itemTypes || [],
      tags: r.tags || [],
      itemIds: r.itemIds || undefined,
    }));
    // Legacy formats
    if (filter.mode === 'whitelist') return [{ action: 'include', negate: false, substring: '', useRegex: false, itemTypes: [], tags: [], itemIds: filter.itemIds || [] }];
    if (filter.mode === 'blacklist') return [
      { action: 'exclude', negate: false, substring: '', useRegex: false, itemTypes: [], tags: [], itemIds: filter.itemIds || [] },
      { action: 'include', negate: false, substring: '', useRegex: false, itemTypes: [], tags: [] },
    ];
    if (filter.mode === 'match') return [{ action: 'include', negate: !!filter.negate, substring: filter.substring || '', useRegex: !!filter.useRegex, itemTypes: filter.itemTypes || [], tags: [] }];
    return [];
  }

  let rules = $state([]);
  let regexErrors = $state(new Map());

  // Initialize when modal opens
  $effect(() => {
    if (show) {
      rules = existingFilter ? normalizeFilter(existingFilter) : [];
      regexErrors = new Map();
    }
  });

  // Deduplicated items for preview (unique by item_id)
  let uniqueItems = $derived((() => {
    const seen = new Map();
    for (const item of items) {
      if (!item.item_id || item.item_id === 0) continue;
      const slim = itemLookup.get(item.item_id);
      if (slim?.ut) continue;
      if (!seen.has(item.item_id)) {
        seen.set(item.item_id, {
          item_id: item.item_id,
          item_name: slim?.n || item.item_name,
          type: slim?.t || null,
          category: getTopCategory(slim?.t),
          quantity: item.quantity || 1,
        });
      } else {
        seen.get(item.item_id).quantity += (item.quantity || 1);
      }
    }
    return [...seen.values()].sort((a, b) => a.item_name.localeCompare(b.item_name));
  })());

  // Check if a single rule's criteria match an item
  function matchesRuleCriteria(item, rule) {
    if (rule.itemIds?.length > 0 && !rule.itemIds.includes(item.item_id)) return false;

    let nameMatch = true;
    if (rule.substring) {
      if (rule.useRegex) {
        try { nameMatch = new RegExp(rule.substring, 'i').test(item.item_name); } catch { nameMatch = false; }
      } else {
        nameMatch = item.item_name.toLowerCase().includes(rule.substring.toLowerCase());
      }
    }

    let typeMatch = true;
    if (rule.itemTypes?.length > 0) {
      typeMatch = item.category ? rule.itemTypes.includes(item.category) : false;
    }

    let tagMatch = true;
    if (rule.tags?.length > 0) {
      tagMatch = rule.tags.every(tag => hasItemTag(item.item_name, tag));
    }

    const result = nameMatch && typeMatch && tagMatch;
    return rule.negate ? !result : result;
  }

  // Evaluate all rules for an item
  function evaluateItem(item) {
    if (rules.length === 0) return true; // no rules = include all
    for (const rule of rules) {
      if (matchesRuleCriteria(item, rule)) {
        if (rule.action === 'include') return true;
        if (rule.action === 'exclude') return false;
        // 'inherit' - continue to next rule
      }
    }
    return false; // no rule matched
  }

  let matchedItems = $derived(uniqueItems.filter(evaluateItem));
  let matchCount = $derived(matchedItems.length);

  // Validate regexes
  $effect(() => {
    const errors = new Map();
    for (let i = 0; i < rules.length; i++) {
      const rule = rules[i];
      if (rule.useRegex && rule.substring) {
        try { new RegExp(rule.substring); } catch (e) { errors.set(i, e.message); }
      }
    }
    regexErrors = errors;
  });

  let hasRegexError = $derived(regexErrors.size > 0);

  // Rule CRUD
  function addRule() {
    rules = [...rules, createRule()];
  }

  function removeRule(index) {
    rules = rules.filter((_, i) => i !== index);
  }

  function moveRule(index, direction) {
    const target = index + direction;
    if (target < 0 || target >= rules.length) return;
    const newRules = [...rules];
    [newRules[index], newRules[target]] = [newRules[target], newRules[index]];
    rules = newRules;
  }

  function updateRule(index, field, value) {
    const newRules = [...rules];
    newRules[index] = { ...newRules[index], [field]: value };
    rules = newRules;
  }

  function toggleType(ruleIndex, typeName) {
    const rule = rules[ruleIndex];
    const types = [...(rule.itemTypes || [])];
    const idx = types.indexOf(typeName);
    if (idx >= 0) types.splice(idx, 1);
    else types.push(typeName);
    updateRule(ruleIndex, 'itemTypes', types);
  }

  function toggleTag(ruleIndex, tag) {
    const rule = rules[ruleIndex];
    const tags = [...(rule.tags || [])];
    const idx = tags.indexOf(tag);
    if (idx >= 0) tags.splice(idx, 1);
    else tags.push(tag);
    updateRule(ruleIndex, 'tags', tags);
  }

  function save() {
    if (rules.length === 0) {
      onsave?.(null); // no rules = include all
      return;
    }
    onsave?.({
      filters: rules.map(rule => {
        const r = { action: rule.action };
        if (rule.negate) r.negate = true;
        const sub = (rule.substring || '').replace(/[\x00-\x1f]/g, '').trim().slice(0, 200);
        if (sub) {
          r.substring = sub;
          if (rule.useRegex) r.useRegex = true;
        }
        if (rule.itemTypes?.length > 0) r.itemTypes = rule.itemTypes.filter(t => ALL_CATEGORIES.includes(t));
        if (rule.tags?.length > 0) r.tags = rule.tags;
        if (rule.itemIds?.length > 0) r.itemIds = rule.itemIds;
        return r;
      }),
    });
  }

  function ruleDescription(rule) {
    const parts = [];
    if (rule.itemIds?.length > 0) parts.push(`${rule.itemIds.length} item IDs`);
    if (rule.substring) parts.push(`"${rule.substring}"${rule.useRegex ? ' (regex)' : ''}`);
    if (rule.itemTypes?.length > 0) parts.push(`${rule.itemTypes.length} type${rule.itemTypes.length > 1 ? 's' : ''}`);
    if (rule.tags?.length > 0) parts.push(`tags: ${rule.tags.join(', ')}`);
    if (parts.length === 0) return 'all items';
    const desc = parts.join(', ');
    return rule.negate ? `NOT (${desc})` : desc;
  }
</script>

{#if show}
  <div
    class="filter-overlay"
    role="button"
    tabindex="-1"
    onclick={(e) => e.target === e.currentTarget && onclose?.()}
    onkeydown={(e) => e.key === 'Escape' && onclose?.()}
  >
    <div class="filter-modal">
      <div class="filter-header">
        <h4>Configure Filter</h4>
        <span class="filter-preview">{matchCount} item{matchCount !== 1 ? 's' : ''} will be listed</span>
        <button class="close-btn" onclick={() => onclose?.()}>&times;</button>
      </div>

      <div class="filter-body">
        {#if rules.length === 0}
          <p class="info-text">All items will be listed. Add rules to filter.</p>
        {/if}

        <div class="rules-list">
          {#each rules as rule, index (index)}
            <div class="rule-card">
              <div class="rule-header">
                <select
                  class="action-select action-{rule.action}"
                  value={rule.action}
                  onchange={(e) => updateRule(index, 'action', e.target.value)}
                >
                  <option value="include">Include</option>
                  <option value="exclude">Exclude</option>
                  <option value="inherit">Inherit</option>
                </select>

                <span class="rule-desc">{ruleDescription(rule)}</span>

                <div class="rule-controls">
                  <button class="btn-sm" onclick={() => moveRule(index, -1)} disabled={index === 0} title="Move up">&#9650;</button>
                  <button class="btn-sm" onclick={() => moveRule(index, 1)} disabled={index === rules.length - 1} title="Move down">&#9660;</button>
                  <button class="btn-sm danger" onclick={() => removeRule(index)} title="Remove">&times;</button>
                </div>
              </div>

              <div class="rule-body">
                <label class="negate-toggle">
                  <input type="checkbox" checked={rule.negate} onchange={(e) => updateRule(index, 'negate', e.target.checked)} />
                  Negate match
                </label>

                <div class="match-row">
                  <label class="match-label">
                    Pattern
                    <input
                      type="text"
                      class="match-input"
                      placeholder="Substring or regex..."
                      value={rule.substring}
                      oninput={(e) => updateRule(index, 'substring', e.target.value)}
                      maxlength="200"
                    />
                  </label>
                  <label class="regex-toggle">
                    <input type="checkbox" checked={rule.useRegex} onchange={(e) => updateRule(index, 'useRegex', e.target.checked)} />
                    Regex
                  </label>
                </div>
                {#if regexErrors.has(index)}
                  <p class="error-text">{regexErrors.get(index)}</p>
                {/if}

                <div class="chip-section">
                  <span class="chip-label">Tags:</span>
                  <div class="chip-row">
                    {#each ALL_TAGS as tag}
                      <label class="chip" class:active={rule.tags?.includes(tag.value)}>
                        <input type="checkbox" checked={rule.tags?.includes(tag.value)} onchange={() => toggleTag(index, tag.value)} />
                        {tag.label}
                      </label>
                    {/each}
                  </div>
                </div>

                <div class="chip-section">
                  <span class="chip-label">Types:</span>
                  <div class="chip-row">
                    {#each ALL_CATEGORIES as cat}
                      <label class="chip" class:active={rule.itemTypes?.includes(cat)}>
                        <input type="checkbox" checked={rule.itemTypes?.includes(cat)} onchange={() => toggleType(index, cat)} />
                        {cat}
                      </label>
                    {/each}
                  </div>
                </div>
              </div>
            </div>
          {/each}
        </div>

        <button class="btn-add" onclick={addRule}>+ Add Rule</button>

        {#if rules.length > 0}
          <div class="default-hint">Items not matching any rule will not be listed.</div>
        {/if}

        <div class="match-preview">
          <span class="match-preview-label">{matchedItems.length} item{matchedItems.length !== 1 ? 's' : ''}</span>
          <div class="match-preview-list">
            {#each matchedItems as item (item.item_id)}
              <div class="match-preview-row">
                <span class="item-name">{item.item_name}</span>
                {#if item.category}
                  <span class="item-type-badge">{item.category}</span>
                {/if}
                <span class="item-qty">x{item.quantity.toLocaleString()}</span>
              </div>
            {/each}
            {#if matchedItems.length === 0 && rules.length > 0}
              <p class="empty-text">No items match the current rules</p>
            {/if}
          </div>
        </div>
      </div>

      <div class="filter-actions">
        <button class="btn btn-secondary" onclick={() => onclose?.()}>Cancel</button>
        <button class="btn btn-primary" onclick={save} disabled={hasRegexError}>
          Save Filter
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .filter-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1100;
  }

  .filter-modal {
    background: var(--primary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    width: 560px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
  }

  .filter-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border-color);
  }

  .filter-header h4 { margin: 0; font-size: 1rem; }

  .filter-preview {
    flex: 1;
    text-align: right;
    font-size: 0.8rem;
    color: var(--accent-color);
    font-weight: 500;
  }

  .close-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0 4px;
  }

  .close-btn:hover { color: var(--text-color); }

  .filter-body {
    padding: 0.75rem 1rem;
    overflow-y: auto;
    flex: 1;
  }

  .info-text {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin: 0 0 0.5rem 0;
    text-align: center;
  }

  /* Rules list */
  .rules-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .rule-card {
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--secondary-color);
    overflow: hidden;
  }

  .rule-header {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px;
    background: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
  }

  .action-select {
    padding: 2px 4px;
    font-size: 0.78rem;
    font-weight: 600;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--secondary-color);
    color: var(--text-color);
    cursor: pointer;
  }

  .action-select.action-include { color: var(--success-color, #22c55e); }
  .action-select.action-exclude { color: var(--error-color, #ef4444); }
  .action-select.action-inherit { color: var(--text-muted); }

  .action-select option { color: var(--text-color); }

  .rule-desc {
    flex: 1;
    font-size: 0.75rem;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .rule-controls {
    display: flex;
    gap: 2px;
    flex-shrink: 0;
  }

  .btn-sm {
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: none;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.65rem;
    padding: 0;
  }

  .btn-sm:hover:not(:disabled) {
    border-color: var(--text-color);
    color: var(--text-color);
  }

  .btn-sm:disabled { opacity: 0.3; cursor: default; }

  .btn-sm.danger:hover:not(:disabled) {
    border-color: var(--error-color);
    color: var(--error-color);
  }

  .rule-body {
    padding: 6px 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .negate-toggle {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.78rem;
    cursor: pointer;
    color: var(--text-muted);
  }

  .negate-toggle:has(input:checked) { color: var(--error-color, #ef4444); }

  .match-row {
    display: flex;
    gap: 0.5rem;
    align-items: flex-end;
  }

  .match-label {
    flex: 1;
    font-size: 0.78rem;
    display: flex;
    flex-direction: column;
    gap: 2px;
    color: var(--text-muted);
  }

  .match-input {
    width: 100%;
    padding: 3px 6px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--primary-color);
    color: var(--text-color);
    font-size: 0.8rem;
    box-sizing: border-box;
  }

  .match-input:focus { outline: none; border-color: var(--accent-color); }

  .regex-toggle {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    white-space: nowrap;
    padding-bottom: 3px;
    color: var(--text-muted);
  }

  .error-text {
    color: var(--error-color);
    font-size: 0.72rem;
    margin: 0;
  }

  /* Chip sections (tags, types) */
  .chip-section {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .chip-label {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
  }

  .chip {
    display: flex;
    align-items: center;
    gap: 0;
    font-size: 0.72rem;
    padding: 1px 5px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    cursor: pointer;
    user-select: none;
    transition: background 0.1s, border-color 0.1s;
  }

  .chip:hover { background: var(--hover-color); }

  .chip.active {
    border-color: var(--accent-color);
    background: var(--accent-color);
    color: #fff;
  }

  .chip input { display: none; }

  /* Add rule button */
  .btn-add {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    width: 100%;
    padding: 6px;
    font-size: 0.8rem;
    background: transparent;
    border: 1px dashed var(--border-color);
    color: var(--text-muted);
    border-radius: 4px;
    cursor: pointer;
    margin-top: 6px;
    transition: all 0.15s;
  }

  .btn-add:hover {
    border-color: var(--accent-color);
    color: var(--accent-color);
  }

  .default-hint {
    font-size: 0.72rem;
    color: var(--text-muted);
    font-style: italic;
    margin-top: 4px;
    text-align: center;
  }

  /* Preview */
  .match-preview {
    margin-top: 8px;
  }

  .match-preview-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    display: block;
    margin-bottom: 3px;
  }

  .match-preview-list {
    max-height: 180px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
  }

  .match-preview-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.2rem 0.6rem;
    font-size: 0.78rem;
  }

  .match-preview-row:hover { background: var(--hover-color); }

  .item-name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item-type-badge {
    font-size: 0.68rem;
    color: var(--text-muted);
    padding: 1px 4px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    white-space: nowrap;
  }

  .item-qty {
    font-size: 0.72rem;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .empty-text {
    text-align: center;
    color: var(--text-muted);
    padding: 0.75rem;
    margin: 0;
    font-size: 0.8rem;
  }

  /* Actions */
  .filter-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    border-top: 1px solid var(--border-color);
  }

  .btn {
    padding: 0.4rem 1rem;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .btn-secondary { background: var(--secondary-color); color: var(--text-color); }

  .btn-primary { background: var(--accent-color); color: #fff; border-color: var(--accent-color); }

  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
