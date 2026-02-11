<!--
  @component MissionRewardsEditor
  Editor for mission rewards.
  Supports choices mode: Rewards can be a single package (object) or array of choices (player picks one).
  Choice mode is implicit - detected by checking if Rewards is an array.
  Toggle checkbox allows switching between flat/choices format.
-->
<script>
  // @ts-nocheck
  import { updateField } from '$lib/stores/wikiEditState.js';
  import SearchInput from '$lib/components/wiki/SearchInput.svelte';

  export let rewards = null;
  export let fieldPath = 'Rewards';
  export let itemsIndex = {};

  let itemNameDrafts = {};
  let skillNameDrafts = {};

  // Check if Rewards is in choices format (Items column contains choice packages)
  function isChoicesFormat(data) {
    const items = data?.Items;
    return Array.isArray(items) && items.length > 0 && items[0]?.Items !== undefined;
  }

  // Get empty reward package
  function emptyPackage() {
    return { Items: [], Skills: [], Unlocks: [] };
  }

  // Convert flat rewards to choices format
  function toChoicesFormat(data) {
    if (!data) return { Items: [emptyPackage()], Skills: [], Unlocks: [] };
    if (isChoicesFormat(data)) return data;
    // Wrap current flat items/skills/unlocks as a single choice package
    return {
      Items: [{ Items: data.Items || [], Skills: data.Skills || [], Unlocks: data.Unlocks || [] }],
      Skills: [],
      Unlocks: []
    };
  }

  // Convert choices format to flat (take first choice)
  function toFlatFormat(data) {
    if (!data) return emptyPackage();
    if (!isChoicesFormat(data)) return data;
    const first = data.Items[0] || emptyPackage();
    return {
      Items: first.Items || [],
      Skills: first.Skills || [],
      Unlocks: first.Unlocks || []
    };
  }

  const SKILL_IMPLANT_SUFFIX = ' Skill Implant (L)';

  // Filter for skill implants
  function skillImplantFilter(item) {
    const name = item?.Name || '';
    return name.endsWith(SKILL_IMPLANT_SUFFIX) && name !== 'Empty Skill Implant (L)';
  }

  // Display just the skill name (without " Skill Implant (L)")
  function skillDisplayFn(item) {
    const name = item?.Name || '';
    if (name.endsWith(SKILL_IMPLANT_SUFFIX)) {
      return name.slice(0, -SKILL_IMPLANT_SUFFIX.length);
    }
    return name;
  }

  // Get skill display name from ID
  function getSkillDisplayName(itemId, draftMap, draftKey) {
    if (Object.prototype.hasOwnProperty.call(draftMap, draftKey)) {
      return draftMap[draftKey];
    }
    if (itemId != null && itemsIndex && itemsIndex[itemId]) {
      const fullName = itemsIndex[itemId];
      if (fullName.endsWith(SKILL_IMPLANT_SUFFIX)) {
        return fullName.slice(0, -SKILL_IMPLANT_SUFFIX.length);
      }
      return fullName;
    }
    return itemId != null ? `#${itemId}` : '';
  }

  // Reactive: detect choices mode
  $: hasChoices = isChoicesFormat(rewards);

  // Normalize rewards data for consistent access
  // For choices: rewardsData is the array of packages (from Items column)
  // For flat: rewardsData is the {Items, Skills, Unlocks} object
  $: rewardsData = hasChoices
    ? (rewards?.Items || [emptyPackage()])
    : (rewards || emptyPackage());

  function updateRewards(next) {
    // If given an array of packages (choices mode updates), wrap in consistent format
    if (Array.isArray(next)) {
      updateField(fieldPath, { Items: next, Skills: [], Unlocks: [] });
    } else {
      updateField(fieldPath, next);
    }
  }

  // Toggle choices mode
  function toggleChoices() {
    if (!hasChoices) {
      // Enable choices: convert to array
      updateRewards(toChoicesFormat(rewards));
    } else {
      // Disable choices: flatten to single package
      updateRewards(toFlatFormat(rewards));
    }
  }

  // Add a new choice group
  function addChoiceGroup() {
    if (!hasChoices) return;
    updateRewards([...rewardsData, emptyPackage()]);
  }

  // Remove a choice group
  function removeChoiceGroup(choiceIndex) {
    if (!hasChoices || rewardsData.length <= 1) return;
    updateRewards(rewardsData.filter((_, i) => i !== choiceIndex));
  }

  // --- Item functions ---
  function addItem(choiceIndex = null) {
    const newItem = { itemId: null, quantity: null, pedValue: null };
    if (hasChoices && choiceIndex !== null) {
      const updated = rewardsData.map((pkg, i) =>
        i === choiceIndex ? { ...pkg, Items: [...(pkg.Items || []), newItem] } : pkg
      );
      updateRewards(updated);
    } else if (!hasChoices) {
      updateRewards({ ...rewardsData, Items: [...(rewardsData.Items || []), newItem] });
    }
  }

  function updateItem(choiceIndex, itemIndex, key, value) {
    if (hasChoices) {
      const updated = rewardsData.map((pkg, cIdx) => {
        if (cIdx !== choiceIndex) return pkg;
        const items = (pkg.Items || []).map((item, iIdx) =>
          iIdx === itemIndex ? { ...item, [key]: value === '' ? null : value } : item
        );
        return { ...pkg, Items: items };
      });
      updateRewards(updated);
    } else {
      const items = (rewardsData.Items || []).map((item, iIdx) =>
        iIdx === itemIndex ? { ...item, [key]: value === '' ? null : value } : item
      );
      updateRewards({ ...rewardsData, Items: items });
    }
  }

  function removeItem(choiceIndex, itemIndex) {
    if (hasChoices) {
      const updated = rewardsData.map((pkg, cIdx) => {
        if (cIdx !== choiceIndex) return pkg;
        return { ...pkg, Items: (pkg.Items || []).filter((_, i) => i !== itemIndex) };
      });
      updateRewards(updated);
    } else {
      updateRewards({ ...rewardsData, Items: (rewardsData.Items || []).filter((_, i) => i !== itemIndex) });
    }
  }

  // --- Skill functions ---
  function addSkill(choiceIndex = null) {
    const newSkill = { skillItemId: null, pedValue: null };
    if (hasChoices && choiceIndex !== null) {
      const updated = rewardsData.map((pkg, i) =>
        i === choiceIndex ? { ...pkg, Skills: [...(pkg.Skills || []), newSkill] } : pkg
      );
      updateRewards(updated);
    } else if (!hasChoices) {
      updateRewards({ ...rewardsData, Skills: [...(rewardsData.Skills || []), newSkill] });
    }
  }

  function updateSkill(choiceIndex, skillIndex, key, value) {
    if (hasChoices) {
      const updated = rewardsData.map((pkg, cIdx) => {
        if (cIdx !== choiceIndex) return pkg;
        const skills = (pkg.Skills || []).map((skill, sIdx) =>
          sIdx === skillIndex ? { ...skill, [key]: value === '' ? null : value } : skill
        );
        return { ...pkg, Skills: skills };
      });
      updateRewards(updated);
    } else {
      const skills = (rewardsData.Skills || []).map((skill, sIdx) =>
        sIdx === skillIndex ? { ...skill, [key]: value === '' ? null : value } : skill
      );
      updateRewards({ ...rewardsData, Skills: skills });
    }
  }

  function removeSkill(choiceIndex, skillIndex) {
    if (hasChoices) {
      const updated = rewardsData.map((pkg, cIdx) => {
        if (cIdx !== choiceIndex) return pkg;
        return { ...pkg, Skills: (pkg.Skills || []).filter((_, i) => i !== skillIndex) };
      });
      updateRewards(updated);
    } else {
      updateRewards({ ...rewardsData, Skills: (rewardsData.Skills || []).filter((_, i) => i !== skillIndex) });
    }
  }

  // --- Unlock functions ---
  function addUnlock(choiceIndex = null) {
    if (hasChoices && choiceIndex !== null) {
      const updated = rewardsData.map((pkg, i) =>
        i === choiceIndex ? { ...pkg, Unlocks: [...(pkg.Unlocks || []), ''] } : pkg
      );
      updateRewards(updated);
    } else if (!hasChoices) {
      updateRewards({ ...rewardsData, Unlocks: [...(rewardsData.Unlocks || []), ''] });
    }
  }

  function updateUnlock(choiceIndex, unlockIndex, value) {
    if (hasChoices) {
      const updated = rewardsData.map((pkg, cIdx) => {
        if (cIdx !== choiceIndex) return pkg;
        const unlocks = (pkg.Unlocks || []).map((u, uIdx) => uIdx === unlockIndex ? value : u);
        return { ...pkg, Unlocks: unlocks };
      });
      updateRewards(updated);
    } else {
      const unlocks = (rewardsData.Unlocks || []).map((u, uIdx) => uIdx === unlockIndex ? value : u);
      updateRewards({ ...rewardsData, Unlocks: unlocks });
    }
  }

  function removeUnlock(choiceIndex, unlockIndex) {
    if (hasChoices) {
      const updated = rewardsData.map((pkg, cIdx) => {
        if (cIdx !== choiceIndex) return pkg;
        return { ...pkg, Unlocks: (pkg.Unlocks || []).filter((_, i) => i !== unlockIndex) };
      });
      updateRewards(updated);
    } else {
      updateRewards({ ...rewardsData, Unlocks: (rewardsData.Unlocks || []).filter((_, i) => i !== unlockIndex) });
    }
  }

  // --- Draft helpers ---
  function getDraftKey(prefix, choiceIndex, index) {
    return hasChoices ? `${prefix}-${choiceIndex}-${index}` : `${prefix}-${index}`;
  }

  function getDisplayName(itemId, draftMap, draftKey) {
    if (Object.prototype.hasOwnProperty.call(draftMap, draftKey)) {
      return draftMap[draftKey];
    }
    if (itemId != null && itemsIndex && itemsIndex[itemId]) {
      return itemsIndex[itemId];
    }
    return itemId != null ? `#${itemId}` : '';
  }

  function setDraft(map, key, value) {
    return { ...map, [key]: value };
  }

  function handleItemSearchChange(choiceIndex, itemIndex, value) {
    const key = getDraftKey('item', choiceIndex, itemIndex);
    itemNameDrafts = setDraft(itemNameDrafts, key, value);
    updateItem(choiceIndex, itemIndex, 'itemId', null);
  }

  function handleItemSearchSelect(choiceIndex, itemIndex, item) {
    const key = getDraftKey('item', choiceIndex, itemIndex);
    itemNameDrafts = setDraft(itemNameDrafts, key, item?.Name || '');
    updateItem(choiceIndex, itemIndex, 'itemId', item?.Id ?? null);
  }

  function handleSkillSearchChange(choiceIndex, skillIndex, value) {
    const key = getDraftKey('skill', choiceIndex, skillIndex);
    skillNameDrafts = setDraft(skillNameDrafts, key, value);
    updateSkill(choiceIndex, skillIndex, 'skillItemId', null);
  }

  function handleSkillSearchSelect(choiceIndex, skillIndex, item) {
    const key = getDraftKey('skill', choiceIndex, skillIndex);
    const displayName = skillDisplayFn(item);
    skillNameDrafts = setDraft(skillNameDrafts, key, displayName);
    updateSkill(choiceIndex, skillIndex, 'skillItemId', item?.Id ?? null);
  }
</script>

<div class="mission-rewards-editor">
  <div class="rewards-header">
    <label class="choices-toggle">
      <input type="checkbox" checked={hasChoices} on:change={toggleChoices} />
      <span>Enable Choices</span>
    </label>
  </div>

  {#if hasChoices}
    <!-- Choices mode: array of reward packages -->
    {#each rewardsData as pkg, choiceIndex (choiceIndex)}
      <div class="choice-group">
        <div class="choice-header">
          <span class="choice-label">Choice {choiceIndex + 1}</span>
          {#if rewardsData.length > 1}
            <button type="button" class="btn-icon danger small" on:click={() => removeChoiceGroup(choiceIndex)} title="Remove choice">×</button>
          {/if}
        </div>

        <!-- Items section -->
        <div class="reward-section">
          <div class="section-header"><h4>Items</h4></div>
          {#if !pkg.Items?.length}
            <div class="editor-empty">No items.</div>
          {:else}
            {#each pkg.Items as item, itemIndex (itemIndex)}
              {@const draftKey = getDraftKey('item', choiceIndex, itemIndex)}
              <div class="reward-entry">
                <div class="reward-row">
                  <div class="search-delete-row">
                    <SearchInput
                      value={getDisplayName(item.itemId, itemNameDrafts, draftKey)}
                      placeholder="Search item..."
                      apiEndpoint="/search/items"
                      displayFn={(item) => item?.Name || ''}
                      on:change={(e) => handleItemSearchChange(choiceIndex, itemIndex, e.detail.value)}
                      on:select={(e) => handleItemSearchSelect(choiceIndex, itemIndex, e.detail.data)}
                    />
                    <button type="button" class="btn-icon danger" on:click={() => removeItem(choiceIndex, itemIndex)} title="Remove">×</button>
                  </div>
                  <input type="number" min="0" step="1" placeholder="Qty" value={item.quantity ?? ''}
                    on:input={(e) => updateItem(choiceIndex, itemIndex, 'quantity', e.target.value ? Number(e.target.value) : null)} />
                  <input type="number" min="0" step="0.01" placeholder="TT (opt)" value={item.pedValue ?? ''}
                    on:input={(e) => updateItem(choiceIndex, itemIndex, 'pedValue', e.target.value ? Number(e.target.value) : null)} />
                </div>
              </div>
            {/each}
          {/if}
          <button type="button" class="btn-add small" on:click={() => addItem(choiceIndex)}><span>+</span> Add Item</button>
        </div>

        <!-- Skills section -->
        <div class="reward-section">
          <div class="section-header"><h4>Skills</h4></div>
          {#if !pkg.Skills?.length}
            <div class="editor-empty">No skills.</div>
          {:else}
            {#each pkg.Skills as skill, skillIndex (skillIndex)}
              {@const draftKey = getDraftKey('skill', choiceIndex, skillIndex)}
              <div class="reward-entry">
                <div class="reward-row skill-row">
                  <div class="search-delete-row">
                    <SearchInput
                      value={getSkillDisplayName(skill.skillItemId, skillNameDrafts, draftKey)}
                      placeholder="Search skill..."
                      apiEndpoint="/search/items"
                      minChars={1}
                      filterFn={skillImplantFilter}
                      displayFn={skillDisplayFn}
                      emptyMessage="No skills found"
                      on:change={(e) => handleSkillSearchChange(choiceIndex, skillIndex, e.detail.value)}
                      on:select={(e) => handleSkillSearchSelect(choiceIndex, skillIndex, e.detail.data)}
                    />
                    <button type="button" class="btn-icon danger" on:click={() => removeSkill(choiceIndex, skillIndex)} title="Remove">×</button>
                  </div>
                  <input type="number" min="0" step="0.01" placeholder="PED Value" value={skill.pedValue ?? ''}
                    on:input={(e) => updateSkill(choiceIndex, skillIndex, 'pedValue', e.target.value ? Number(e.target.value) : null)} />
                </div>
              </div>
            {/each}
          {/if}
          <button type="button" class="btn-add small" on:click={() => addSkill(choiceIndex)}><span>+</span> Add Skill</button>
        </div>

        <!-- Unlocks section -->
        <div class="reward-section">
          <div class="section-header"><h4>Unlocks</h4></div>
          {#if !pkg.Unlocks?.length}
            <div class="editor-empty">No unlocks.</div>
          {:else}
            {#each pkg.Unlocks as unlock, unlockIndex (unlockIndex)}
              <div class="reward-entry">
                <div class="reward-row unlock-row">
                  <div class="search-delete-row">
                    <input type="text" placeholder="Unlock description" value={unlock ?? ''}
                      on:input={(e) => updateUnlock(choiceIndex, unlockIndex, e.target.value)} />
                    <button type="button" class="btn-icon danger" on:click={() => removeUnlock(choiceIndex, unlockIndex)} title="Remove">×</button>
                  </div>
                </div>
              </div>
            {/each}
          {/if}
          <button type="button" class="btn-add small" on:click={() => addUnlock(choiceIndex)}><span>+</span> Add Unlock</button>
        </div>
      </div>
    {/each}
    <button type="button" class="btn-add choice-add" on:click={addChoiceGroup}><span>+</span> Add Choice</button>

  {:else}
    <!-- Flat mode: single reward package -->
    <div class="reward-section">
      <div class="section-header"><h4>Item Rewards</h4></div>
      {#if !rewardsData.Items?.length}
        <div class="editor-empty">No item rewards.</div>
      {:else}
        {#each rewardsData.Items as item, itemIndex (itemIndex)}
          {@const draftKey = getDraftKey('item', 0, itemIndex)}
          <div class="reward-entry">
            <div class="reward-row">
              <div class="search-delete-row">
                <SearchInput
                  value={getDisplayName(item.itemId, itemNameDrafts, draftKey)}
                  placeholder="Search item..."
                  apiEndpoint="/search/items"
                  displayFn={(item) => item?.Name || ''}
                  on:change={(e) => handleItemSearchChange(0, itemIndex, e.detail.value)}
                  on:select={(e) => handleItemSearchSelect(0, itemIndex, e.detail.data)}
                />
                <button type="button" class="btn-icon danger" on:click={() => removeItem(0, itemIndex)} title="Remove">×</button>
              </div>
              <input type="number" min="0" step="1" placeholder="Quantity" value={item.quantity ?? ''}
                on:input={(e) => updateItem(0, itemIndex, 'quantity', e.target.value ? Number(e.target.value) : null)} />
              <input type="number" min="0" step="0.01" placeholder="Remaining TT (optional)" value={item.pedValue ?? ''}
                on:input={(e) => updateItem(0, itemIndex, 'pedValue', e.target.value ? Number(e.target.value) : null)} />
            </div>
          </div>
        {/each}
      {/if}
      <button type="button" class="btn-add" on:click={() => addItem(0)}><span>+</span> Add Item</button>
    </div>

    <div class="reward-section">
      <div class="section-header"><h4>Skill Rewards</h4></div>
      {#if !rewardsData.Skills?.length}
        <div class="editor-empty">No skill rewards.</div>
      {:else}
        {#each rewardsData.Skills as skill, skillIndex (skillIndex)}
          {@const draftKey = getDraftKey('skill', 0, skillIndex)}
          <div class="reward-entry">
            <div class="reward-row skill-row">
              <div class="search-delete-row">
                <SearchInput
                  value={getSkillDisplayName(skill.skillItemId, skillNameDrafts, draftKey)}
                  placeholder="Search skill..."
                  apiEndpoint="/search/items"
                  minChars={1}
                  filterFn={skillImplantFilter}
                  displayFn={skillDisplayFn}
                  emptyMessage="No skills found"
                  on:change={(e) => handleSkillSearchChange(0, skillIndex, e.detail.value)}
                  on:select={(e) => handleSkillSearchSelect(0, skillIndex, e.detail.data)}
                />
                <button type="button" class="btn-icon danger" on:click={() => removeSkill(0, skillIndex)} title="Remove">×</button>
              </div>
              <input type="number" min="0" step="0.01" placeholder="PED Value" value={skill.pedValue ?? ''}
                on:input={(e) => updateSkill(0, skillIndex, 'pedValue', e.target.value ? Number(e.target.value) : null)} />
            </div>
          </div>
        {/each}
      {/if}
      <button type="button" class="btn-add" on:click={() => addSkill(0)}><span>+</span> Add Skill</button>
    </div>

    <div class="reward-section">
      <div class="section-header"><h4>Unlocks</h4></div>
      {#if !rewardsData.Unlocks?.length}
        <div class="editor-empty">No unlocks.</div>
      {:else}
        {#each rewardsData.Unlocks as unlock, unlockIndex (unlockIndex)}
          <div class="reward-entry">
            <div class="reward-row unlock-row">
              <div class="search-delete-row">
                <input type="text" placeholder="Unlock description" value={unlock ?? ''}
                  on:input={(e) => updateUnlock(0, unlockIndex, e.target.value)} />
                <button type="button" class="btn-icon danger" on:click={() => removeUnlock(0, unlockIndex)} title="Remove">×</button>
              </div>
            </div>
          </div>
        {/each}
      {/if}
      <button type="button" class="btn-add" on:click={() => addUnlock(0)}><span>+</span> Add Unlock</button>
    </div>
  {/if}
</div>

<style>
  .mission-rewards-editor {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .rewards-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .choices-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-muted, #999);
    cursor: pointer;
  }

  .choices-toggle input[type="checkbox"] {
    margin: 0;
    cursor: pointer;
  }

  .choice-group {
    border: 2px solid var(--accent-color, #4a9eff);
    border-radius: 6px;
    padding: 12px;
    background: var(--secondary-color);
  }

  .choice-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .choice-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--accent-color, #4a9eff);
  }

  .reward-section {
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    padding: 12px;
    background: var(--secondary-color);
    margin-bottom: 12px;
  }

  .choice-group .reward-section {
    background: var(--bg-color);
    margin-bottom: 10px;
  }

  .choice-group .reward-section:last-of-type {
    margin-bottom: 0;
  }

  .section-header {
    margin-bottom: 8px;
  }

  .section-header h4 {
    margin: 0;
    font-size: 13px;
    color: var(--text-color);
  }

  .btn-add {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 12px;
    font-size: 12px;
    line-height: 1;
    background-color: transparent;
    border: 1px dashed var(--border-color, #555);
    color: var(--text-muted, #999);
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.15s;
    width: 100%;
    margin-top: 4px;
  }

  .btn-add:hover {
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
    background-color: var(--hover-color);
  }

  .btn-add.small {
    padding: 6px 10px;
    font-size: 11px;
  }

  .btn-add.choice-add {
    margin-top: 8px;
    border-style: dashed;
    border-width: 2px;
    border-color: var(--accent-color, #4a9eff);
    color: var(--accent-color, #4a9eff);
  }

  .reward-entry {
    margin-bottom: 8px;
  }

  .reward-row {
    display: grid;
    grid-template-columns: minmax(180px, 2fr) repeat(2, minmax(80px, 1fr));
    gap: 8px;
    align-items: center;
  }

  .reward-row.skill-row {
    grid-template-columns: minmax(180px, 2fr) minmax(80px, 1fr);
  }

  .reward-row.unlock-row {
    display: block;
  }

  .search-delete-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .search-delete-row :global(.item-search) {
    flex: 1;
    min-width: 0;
  }

  .search-delete-row input[type="text"] {
    flex: 1;
    min-width: 0;
  }

  .reward-row input {
    background: var(--input-bg, var(--bg-color));
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    padding: 4px 6px;
    color: var(--text-color);
    font-size: 12px;
    height: 28px;
    box-sizing: border-box;
  }

  .editor-empty {
    font-size: 12px;
    color: var(--text-muted, #999);
    font-style: italic;
    margin-bottom: 8px;
  }

  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    background: none;
    border: 1px solid var(--border-color, #555);
    border-radius: 3px;
    color: var(--text-muted, #999);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .btn-icon:hover:not(:disabled) {
    background-color: var(--hover-color);
    color: var(--text-color);
    border-color: var(--text-color);
  }

  .btn-icon.danger:hover:not(:disabled) {
    background-color: var(--error-color, #ff6b6b);
    color: white;
    border-color: var(--error-color, #ff6b6b);
  }

  .btn-icon.small {
    width: 18px;
    height: 18px;
    font-size: 11px;
  }

  @media (max-width: 700px) {
    .reward-entry {
      background: var(--bg-color);
      border: 1px solid var(--border-color, #555);
      border-radius: 4px;
      padding: 8px;
    }

    .reward-row {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .search-delete-row {
      width: 100%;
    }

    .reward-row input[type="number"] {
      width: 100%;
    }
  }
</style>
