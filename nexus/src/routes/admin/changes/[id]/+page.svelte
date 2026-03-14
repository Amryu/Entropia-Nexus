<script>
  // @ts-nocheck
  import { onMount, untrack } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { getTypeLink, encodeURIComponentSafe } from '$lib/util.js';
  import ChangeDataViewer from '$lib/components/ChangeDataViewer.svelte';
  import JsonCompareDialog from '$lib/components/JsonCompareDialog.svelte';
  import { addToast } from '$lib/stores/toasts.js';

  const DISCORD_GUILD_ID = import.meta.env.VITE_DISCORD_GUILD_ID;

  // Map change entity types to getTypeLink types
  const entityTypeToLinkType = {
    'Weapon': 'Weapon',
    'ArmorSet': 'Armor',
    'MedicalTool': 'MedicalTool',
    'MedicalChip': 'MedicalChip',
    'Refiner': 'Refiner',
    'Scanner': 'Scanner',
    'Finder': 'Finder',
    'Excavator': 'Excavator',
    'TeleportChip': 'TeleportationChip',
    'EffectChip': 'EffectChip',
    'MiscTool': 'MiscTool',
    'WeaponAmplifier': 'WeaponAmplifier',
    'WeaponVisionAttachment': 'WeaponVisionAttachment',
    'Absorber': 'Absorber',
    'FinderAmplifier': 'FinderAmplifier',
    'ArmorPlating': 'ArmorPlating',
    'MindforceImplant': 'MindforceImplant',
    'Blueprint': 'Blueprint',
    'Material': 'Material',
    'Pet': 'Pet',
    'Consumable': 'Consumable',
    'CreatureControlCapsule': 'CreatureControlCapsule',
    'Vehicle': 'Vehicle',
    'Furniture': 'Furniture',
    'Decoration': 'Decoration',
    'StorageContainer': 'StorageContainer',
    'Sign': 'Sign',
    'Clothing': 'Clothing',
    'Mob': 'Mob',
    'Vendor': 'Vendor'
  };

  function getEditUrl(change) {
    if (!change?.data?.Name) return null;
    const linkType = entityTypeToLinkType[change.entity];
    if (!linkType) return null;
    const baseUrl = getTypeLink(change.data.Name, linkType);
    if (!baseUrl) return null;
    // Use mode=create for Create type changes, mode=edit for Updates
    const mode = change.type === 'Create' ? 'create' : 'edit';
    return `${baseUrl}?mode=${mode}&change=${change.id}`;
  }

  function getWikiUrl(change) {
    if (!change?.data?.Name) return null;
    const linkType = entityTypeToLinkType[change.entity];
    if (!linkType) return null;
    return getTypeLink(change.data.Name, linkType);
  }

  let change = $state(null);
  let history = $state([]);
  let relatedChanges = $state([]); // Other approved changes for the same entity
  let originalVersion = $state(null);
  let isLoading = $state(true);
  let error = $state(null);

  // Diff view state
  let showDiff = $state(false);
  let showChangesOnly = $state(false);
  let showRawJson = $state(false);
  let showCompareDialog = $state(false);
  let selectedVersionType = $state(null); // 'original', 'history-{index}', 'related-{index}'
  let shouldAutoSelectDiff = false;

  // Reward state
  let changeReward = $state(null);
  let matchingRules = $state([]);
  let rewardForm = $state({ rule_id: '', amount: '', contribution_score: '', note: '' });
  let isAssigningReward = $state(false);


  onMount(() => {
    loadChange();
  });

  async function loadChange() {
    isLoading = true;
    error = null;

    try {
      const response = await fetch(`/api/admin/changes/${changeId}`);
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Change not found');
        }
        throw new Error('Failed to load change');
      }

      const data = await response.json();
      change = data.change;
      history = data.history || [];
      relatedChanges = data.relatedChanges || [];

      // Try to load original version from audit API
      // Only if this is an Update type with an entity ID
      if (change?.type === 'Update' && change?.data?.Id) {
        const auditResponse = await fetch(`/api/admin/audit/${change.entity}/${change.data.Id}/original`);
        const auditData = auditResponse.ok ? await auditResponse.json() : null;
        if (auditData?.original) {
          originalVersion = auditData.original;
        }

        // Auto-enable diff will happen after combinedVersions is computed
        // We set a flag to trigger selection on next tick
        shouldAutoSelectDiff = true;
      }

      // Load reward data for approved changes
      loadRewardData();
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  }

  async function loadRewardData() {
    if (!change || change.state !== 'Approved') return;
    try {
      const [rewardRes, matchRes] = await Promise.all([
        fetch(`/api/admin/rewards/assign?change_id=${changeId}`),
        fetch(`/api/admin/rewards/match/${changeId}`)
      ]);

      if (rewardRes.ok) {
        const data = await rewardRes.json();
        changeReward = data.reward || null;
      }
      if (matchRes.ok) {
        const data = await matchRes.json();
        matchingRules = data.rules || [];
        if (matchingRules.length === 1 && !changeReward) {
          const rule = matchingRules[0];
          rewardForm.rule_id = String(rule.id);
          rewardForm.amount = rule.min_amount === rule.max_amount ? rule.min_amount : '';
          rewardForm.contribution_score = rule.contribution_score ?? '';
        }
      }
    } catch {}
  }

  async function assignReward() {
    if (!rewardForm.amount || parseFloat(rewardForm.amount) <= 0) return;
    isAssigningReward = true;
    try {
      const res = await fetch('/api/admin/rewards/assign', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          change_id: parseInt(changeId),
          user_id: change.author_id,
          rule_id: rewardForm.rule_id ? parseInt(rewardForm.rule_id) : null,
          amount: parseFloat(rewardForm.amount),
          contribution_score: rewardForm.contribution_score !== '' ? parseFloat(rewardForm.contribution_score) : null,
          note: rewardForm.note || null
        })
      });
      if (res.ok) {
        changeReward = await res.json();
      } else {
        const err = await res.json();
        addToast(err.error || 'Failed to assign reward');
      }
    } catch (e) {
      addToast('Failed to assign reward');
    } finally {
      isAssigningReward = false;
    }
  }

  async function removeReward() {
    if (!changeReward || !confirm('Remove this reward?')) return;
    try {
      const res = await fetch(`/api/admin/rewards/assign/${changeReward.id}`, { method: 'DELETE' });
      if (res.ok) {
        changeReward = null;
        rewardForm = { rule_id: '', amount: '', contribution_score: '', note: '' };
      }
    } catch {}
  }

  function onRuleSelect() {
    const rule = matchingRules.find(r => String(r.id) === rewardForm.rule_id);
    if (rule) {
      if (rule.min_amount === rule.max_amount) rewardForm.amount = rule.min_amount;
      rewardForm.contribution_score = rule.contribution_score ?? '';
    }
  }

  function getStateClass(state) {
    switch (state) {
      case 'Pending': return 'state-pending';
      case 'DirectApply': return 'state-pending';
      case 'Approved': return 'state-approved';
      case 'Denied': return 'state-denied';
      case 'ApplyFailed': return 'state-denied';
      case 'Draft': return 'state-draft';
      case 'Deleted': return 'state-deleted';
      default: return '';
    }
  }

  function getTypeClass(type) {
    switch (type) {
      case 'Create': return 'type-create';
      case 'Update': return 'type-update';
      case 'Delete': return 'type-delete';
      default: return '';
    }
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  }





  // Infer Type from ScanningProfession for Mob entities (matches bot logic)
  // Type is a simple string value, not a reference object
  function inferMobType(scanningProfessionName) {
    if (scanningProfessionName === 'Animal Investigator') return 'Animal';
    if (scanningProfessionName === 'Mutant Investigator') return 'Mutant';
    if (scanningProfessionName === 'Robot Investigator') return 'Robot';
    return null;
  }

  /**
   * Infer generated fields for consistent comparison.
   * - Mobs: infer IsTaming from TamingLevel in Maturities
   * - Mobs: infer IsTameable from TamingLevel in Taming
   * Audit data is already schema-validated (extra properties stripped by proxy).
   */
  function inferGeneratedFields(obj, parentKey = null) {
    if (obj === null || obj === undefined) return obj;
    if (typeof obj !== 'object') return obj;

    if (Array.isArray(obj)) {
      return obj.map(item => inferGeneratedFields(item, parentKey));
    }

    const result = {};

    for (const key of Object.keys(obj)) {
      const value = obj[key];

      // Infer IsTaming from TamingLevel in Maturities array items
      if (parentKey === 'Maturities' && key === 'TamingLevel') {
        result[key] = value;
        if (obj.IsTaming === undefined && value !== undefined) {
          result.IsTaming = value > 0;
        }
        continue;
      }
      if (parentKey === 'Maturities' && key === 'IsTaming') {
        result[key] = obj.TamingLevel !== undefined ? obj.TamingLevel > 0 : value;
        continue;
      }

      // Infer IsTameable from TamingLevel in Taming object
      if (parentKey === 'Taming' && key === 'TamingLevel') {
        result[key] = value;
        if (obj.IsTameable === undefined && value !== undefined) {
          result.IsTameable = value > 0;
        }
        continue;
      }
      if (parentKey === 'Taming' && key === 'IsTameable') {
        result[key] = obj.TamingLevel !== undefined ? obj.TamingLevel > 0 : value;
        continue;
      }

      result[key] = inferGeneratedFields(value, key);
    }

    return result;
  }

  /**
   * Normalize change/audit data for comparison.
   * Infers generated fields (Mob Type, IsTaming/IsTameable) for consistent diffs.
   */
  function normalizeChangeData(data, entityType) {
    if (!data) return data;
    const clone = JSON.parse(JSON.stringify(data));

    // For Mobs, infer Type from ScanningProfession if Type is missing
    if (entityType === 'Mob' && !clone.Type && clone.ScanningProfession?.Name) {
      clone.Type = inferMobType(clone.ScanningProfession.Name);
    }

    return inferGeneratedFields(clone);
  }


  let changeId = $derived($page.params.id);
  // Normalize current data (e.g., infer Type for Mobs)
  let currentData = $derived(normalizeChangeData(change?.data || {}, change?.entity));
  // Filter history to exclude entries identical to current change data
  // This prevents showing "Current Change" and "Edit #1" as duplicates
  let filteredHistory = $derived(history.filter(h => {
    const historyDataStr = JSON.stringify(normalizeChangeData(h.data, change?.entity));
    const currentDataStr = JSON.stringify(currentData);
    return historyDataStr !== currentDataStr;
  }));
  // Combined and sorted list of all versions including current (newest to oldest)
  let combinedVersions = $derived((() => {
    const versions = [];

    // Add current change being viewed
    if (change) {
      versions.push({
        key: 'current',
        type: 'current',
        title: `Change #${change.id} (${change.type})`,
        subtitle: change.author_name || 'Unknown',
        date: new Date(change.last_update),
        changeId: change.id,
        isCurrent: true
      });
    }

    // Add original version
    if (originalVersion) {
      versions.push({
        key: 'original',
        type: 'original',
        title: 'Original Version',
        subtitle: 'From database',
        date: new Date(originalVersion.Timestamp)
      });
    }

    // Add edit history entries
    filteredHistory.forEach((h, i) => {
      versions.push({
        key: `history-${i}`,
        type: 'history',
        title: `Edit #${i + 1}`,
        subtitle: h.author_name || 'Unknown',
        date: new Date(h.created_at)
      });
    });

    // Add previous approved changes
    relatedChanges.forEach((rc, i) => {
      versions.push({
        key: `related-${i}`,
        type: 'related',
        title: `Change #${rc.id} (${rc.type})`,
        subtitle: rc.author_name || 'Unknown',
        date: new Date(rc.last_update),
        changeId: rc.id
      });
    });

    // Sort by date (newest first), with changeId as fallback for equal dates
    versions.sort((a, b) => {
      const dateA = a.date?.getTime() || 0;
      const dateB = b.date?.getTime() || 0;
      if (dateB !== dateA) return dateB - dateA;
      // Fallback: sort by changeId (higher = newer)
      return (b.changeId || 0) - (a.changeId || 0);
    });

    return versions;
  })());
  // Auto-select the newest non-current version for diff when flag is set
  $effect(() => {
    if (untrack(() => shouldAutoSelectDiff) && combinedVersions.length > 0) {
      // Find the first version that isn't the current change (can't compare against itself)
      const firstComparable = combinedVersions.find(v => !v.isCurrent);
      if (firstComparable) {
        selectedVersionType = firstComparable.key;
        showDiff = true;
      }
      shouldAutoSelectDiff = false;
    }
  });
  // Compute the comparison data based on selection
  let comparisonData = $derived((() => {
    if (!showDiff || !selectedVersionType) return null;
    if (selectedVersionType === 'original' && originalVersion) {
      return normalizeChangeData(originalVersion.Data, change?.entity);
    }
    if (selectedVersionType.startsWith('history-')) {
      const index = parseInt(selectedVersionType.split('-')[1], 10);
      return normalizeChangeData(filteredHistory[index]?.data, change?.entity) || null;
    }
    if (selectedVersionType.startsWith('related-')) {
      const index = parseInt(selectedVersionType.split('-')[1], 10);
      return normalizeChangeData(relatedChanges[index]?.data, change?.entity) || null;
    }
    return null;
  })());
  let hasComparisonOptions = $derived(originalVersion || filteredHistory.length > 0 || relatedChanges.length > 0);
</script>

<svelte:head>
  <title>Change #{changeId} | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .change-detail {
    max-width: 1200px;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .breadcrumb span {
    color: var(--text-muted);
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 24px;
  }

  .header-left h1 {
    margin: 0 0 8px 0;
    font-size: 24px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-badges {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }

  .back-btn {
    padding: 8px 16px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--hover-color);
    color: var(--text-color);
    font-size: 14px;
    cursor: pointer;
    text-decoration: none;
    transition: all 0.15s ease;
  }

  .back-btn:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    line-height: 1;
    white-space: nowrap;
  }

  .state-pending { background-color: rgba(245, 158, 11, 0.2); color: var(--warning-color); }
  .state-approved { background-color: rgba(16, 185, 129, 0.2); color: var(--success-color); }
  .state-denied { background-color: rgba(239, 68, 68, 0.2); color: var(--error-color); }
  .state-draft { background-color: var(--hover-color); color: var(--text-muted); }
  .state-deleted { background-color: rgba(107, 114, 128, 0.2); color: #6b7280; }
  .type-create { background-color: rgba(34, 197, 94, 0.2); color: #22c55e; }
  .type-update { background-color: rgba(59, 130, 246, 0.2); color: var(--accent-color); }
  .type-delete { background-color: rgba(239, 68, 68, 0.2); color: var(--error-color); }

  .content-grid {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 24px;
  }

  .main-content {
    min-width: 0;
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .card {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    overflow: hidden;
  }

  .card-header {
    padding: 12px 16px;
    background-color: var(--hover-color);
    border-bottom: 1px solid var(--border-color);
    font-weight: 600;
    font-size: 14px;
    color: var(--text-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .card-body {
    padding: 16px;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border-color);
    font-size: 14px;
  }

  .info-row:last-child {
    border-bottom: none;
  }

  .info-label {
    color: var(--text-muted);
  }

  .info-value {
    color: var(--text-color);
    text-align: right;
  }

  .data-viewer {
    max-height: 600px;
    overflow-y: auto;
  }

  .raw-json {
    margin: 0;
    padding: 16px;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 12px;
    line-height: 1.5;
    background-color: var(--primary-color);
    color: var(--text-color);
    white-space: pre-wrap;
    word-wrap: break-word;
  }

  .header-controls {
    display: flex;
    gap: 8px;
  }

  .toggle-btn {
    padding: 4px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--hover-color);
    color: var(--text-color);
    font-size: 12px;
    cursor: pointer;
  }

  .toggle-btn.active {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .history-list {
    max-height: 200px;
    overflow-y: auto;
  }

  .history-item {
    padding: 10px 16px;
    border-bottom: 1px solid var(--border-color);
    cursor: pointer;
    font-size: 13px;
    transition: background-color 0.15s ease;
  }

  .history-item:last-child {
    border-bottom: none;
  }

  .history-item:hover {
    background-color: var(--hover-color);
  }

  .history-item.selected {
    background-color: rgba(59, 130, 246, 0.15);
    border-left: 3px solid var(--accent-color);
  }

  .history-item.current {
    background-color: rgba(34, 197, 94, 0.15);
    border-left: 3px solid var(--success-color);
  }

  .current-badge {
    display: inline-block;
    padding: 1px 6px;
    background-color: rgba(34, 197, 94, 0.2);
    color: var(--success-color);
    border-radius: 3px;
    font-size: 10px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .history-date {
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .view-change-link {
    font-size: 12px;
    color: var(--accent-color);
    text-decoration: none;
    padding: 2px 6px;
    border-radius: 3px;
    background-color: rgba(59, 130, 246, 0.1);
    transition: all 0.15s ease;
  }

  .view-change-link:hover {
    background-color: var(--accent-color);
    color: white;
  }

  .history-author {
    color: var(--text-muted);
    font-size: 12px;
  }

  .loading, .error {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
  }

  .error {
    color: var(--error-color);
  }

  .reward-form { display: flex; flex-direction: column; gap: 8px; }
  .reward-field { display: flex; flex-direction: column; gap: 3px; }
  .reward-field label { font-size: 12px; color: var(--text-muted); }
  .reward-field input, .reward-field select {
    padding: 6px 8px; border: 1px solid var(--border-color); border-radius: 4px;
    background: var(--primary-color); color: var(--text-color); font-size: 13px;
  }
  .reward-remove-btn {
    margin-top: 10px; padding: 6px 10px; border: 1px solid var(--error-color);
    border-radius: 4px; background: transparent; color: var(--error-color);
    font-size: 12px; cursor: pointer; text-align: center;
  }
  .reward-remove-btn:hover { background: var(--error-color); color: white; }

  .thread-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--accent-color);
    text-decoration: none;
    font-size: 13px;
  }

  .thread-link:hover {
    text-decoration: underline;
  }

  .quick-actions-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .action-link {
    display: block;
    padding: 8px 12px;
    background-color: var(--hover-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    text-decoration: none;
    font-size: 13px;
    text-align: center;
    transition: all 0.15s ease;
  }

  .action-link:hover {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .action-link-primary {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .action-link-primary:hover {
    background-color: var(--accent-hover-color, #2563eb);
    border-color: var(--accent-hover-color, #2563eb);
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .page-header {
      flex-direction: column;
      gap: 12px;
    }

    .header-left h1 {
      font-size: 18px;
      flex-wrap: wrap;
    }

    .header-badges {
      margin-top: 4px;
    }

    .back-btn {
      align-self: flex-start;
      padding: 6px 12px;
      font-size: 13px;
    }

    .content-grid {
      grid-template-columns: 1fr;
      gap: 16px;
    }

    .sidebar {
      order: -1;
    }

    .card-header {
      padding: 10px 12px;
      font-size: 13px;
    }

    .card-body {
      padding: 12px;
    }

    .info-row {
      font-size: 13px;
      flex-wrap: wrap;
      gap: 4px;
    }

    .info-value {
      text-align: left;
    }

    .breadcrumb {
      font-size: 12px;
      flex-wrap: wrap;
    }

    .data-viewer {
      max-height: none;
    }
  }
</style>

<div class="change-detail">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <a href="/admin/changes">Changes</a>
    <span>/</span>
    <span>#{changeId}</span>
  </div>

  {#if isLoading}
    <div class="loading">Loading change details...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if change}
    <div class="page-header">
      <div class="header-left">
        <h1>
          {change.data?.Name || 'Unknown Entity'}
          <div class="header-badges">
            <span class="badge {getStateClass(change.state)}">{change.state}</span>
            <span class="badge {getTypeClass(change.type)}">{change.type}</span>
          </div>
        </h1>
        <div style="color: var(--text-muted); font-size: 14px;">
          {change.entity} &bull; Change #{change.id}
        </div>
      </div>
      <a href="/admin/changes" class="back-btn">← Back to Changes</a>
    </div>

    <div class="content-grid">
      <div class="main-content">
        <div class="card">
          <div class="card-header">
            <span>Change Data</span>
            <div class="header-controls">
              <button
                class="toggle-btn"
                class:active={showRawJson}
                onclick={() => { showRawJson = !showRawJson; if (showRawJson) showDiff = false; }}
              >
                {showRawJson ? 'Formatted' : 'Raw JSON'}
              </button>
              {#if !showRawJson && showDiff && comparisonData}
                <button
                  class="toggle-btn"
                  class:active={showChangesOnly}
                  onclick={() => showChangesOnly = !showChangesOnly}
                >
                  {showChangesOnly ? 'Show All' : 'Changes Only'}
                </button>
                <button
                  class="toggle-btn"
                  onclick={() => showCompareDialog = true}
                >
                  Side by Side
                </button>
              {/if}
              {#if !showRawJson && hasComparisonOptions}
                <button
                  class="toggle-btn"
                  class:active={showDiff}
                  onclick={() => showDiff = !showDiff}
                >
                  {showDiff ? 'Hide Diff' : 'Show Diff'}
                </button>
              {/if}
            </div>
          </div>
          <div class="data-viewer">
            {#if showRawJson}
              <pre class="raw-json">{JSON.stringify(currentData, null, 2)}</pre>
            {:else}
              <ChangeDataViewer
                data={currentData}
                previousData={showDiff ? comparisonData : null}
                entity={change.entity}
                showChangesOnly={showDiff && showChangesOnly}
              />
            {/if}
          </div>
        </div>
      </div>

      <div class="sidebar">
        <div class="card">
          <div class="card-header">Details</div>
          <div class="card-body">
            <div class="info-row">
              <span class="info-label">Author</span>
              <span class="info-value">{change.author_name || 'Unknown'}</span>
            </div>
            {#if change.author_eu_name}
              <div class="info-row">
                <span class="info-label">EU Name</span>
                <span class="info-value">{change.author_eu_name}</span>
              </div>
            {/if}
            <div class="info-row">
              <span class="info-label">Created</span>
              <span class="info-value">{formatDate(change.created_at || change.last_update)}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Last Update</span>
              <span class="info-value">{formatDate(change.last_update)}</span>
            </div>
            {#if change.reviewed_at}
              <div class="info-row">
                <span class="info-label">Reviewed By</span>
                <span class="info-value">{change.reviewer_name || 'Unknown'}</span>
              </div>
              <div class="info-row">
                <span class="info-label">Reviewed At</span>
                <span class="info-value">{formatDate(change.reviewed_at)}</span>
              </div>
            {/if}
            {#if change.denial_reason}
              <div class="info-row">
                <span class="info-label">Denial Reason</span>
                <span class="info-value">{change.denial_reason}</span>
              </div>
            {/if}
            {#if change.thread_id && DISCORD_GUILD_ID}
              <div class="info-row">
                <span class="info-label">Discord</span>
                <a
                  href="https://discord.com/channels/{DISCORD_GUILD_ID}/{change.thread_id}"
                  target="_blank"
                  rel="noopener"
                  class="thread-link"
                >
                  View Thread →
                </a>
              </div>
            {/if}
          </div>
        </div>

        <div class="card">
          <div class="card-header">Compare Against</div>
          {#if hasComparisonOptions}
            <div class="history-list">
              <!-- Combined list of all versions, sorted newest to oldest -->
              {#each combinedVersions as version (version.key)}
                {#if version.isCurrent}
                  <!-- Current change being viewed - not selectable -->
                  <div class="history-item current">
                    <div class="history-date">
                      {version.title}
                      <span class="current-badge">Viewing</span>
                    </div>
                    <div class="history-author">{version.subtitle} ({formatDate(version.date)})</div>
                  </div>
                {:else}
                  <div
                    class="history-item"
                    class:selected={selectedVersionType === version.key}
                    role="button"
                    tabindex="0"
                    onclick={() => {
                      selectedVersionType = selectedVersionType === version.key ? null : version.key;
                      showDiff = selectedVersionType !== null;
                    }}
                    onkeydown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        selectedVersionType = selectedVersionType === version.key ? null : version.key;
                        showDiff = selectedVersionType !== null;
                      }
                    }}
                  >
                    <div class="history-date">
                      {version.title}
                      {#if version.type === 'related' && version.changeId}
                        <a
                          href="/admin/changes/{version.changeId}"
                          class="view-change-link"
                          title="View this change"
                          onclick={(e) => e.stopPropagation()}
                        >→</a>
                      {/if}
                    </div>
                    <div class="history-author">{version.subtitle} ({formatDate(version.date)})</div>
                  </div>
                {/if}
              {/each}
            </div>
          {:else}
            <div class="card-body" style="color: var(--text-muted); font-size: 13px;">
              {#if change.type === 'Create'}
                This is a new entity creation - no previous version to compare against.
              {:else}
                No comparison data available.
              {/if}
            </div>
          {/if}
        </div>

        <div class="card">
          <div class="card-header">Quick Actions</div>
          <div class="card-body quick-actions-list">
            {#if getWikiUrl(change)}
              <a
                href={getWikiUrl(change)}
                class="action-link"
                target="_blank"
                rel="noopener"
              >
                View on Wiki →
              </a>
            {/if}
            {#if change.state === 'Pending' || change.state === 'Draft' || change.state === 'DirectApply' || change.state === 'ApplyFailed'}
              {@const editUrl = getEditUrl(change)}
              {#if editUrl}
                <a
                  href={editUrl}
                  class="action-link action-link-primary"
                >
                  Edit Change
                </a>
              {/if}
            {/if}
            <a
              href="/admin/users/{change.author_id}"
              class="action-link"
            >
              View Author Profile
            </a>
            {#if change.data?.Id}
              <a
                href="/admin/history/{change.entity}/{change.data.Id}"
                class="action-link"
              >
                View Full Entity History
              </a>
            {/if}
          </div>
        </div>

        {#if change.state === 'Approved'}
          <div class="card">
            <div class="card-header">Reward</div>
            <div class="card-body">
              {#if changeReward}
                <div class="reward-info">
                  <div class="info-row">
                    <span class="info-label">Amount</span>
                    <span class="info-value" style="color: var(--success-color); font-weight: 600;">{parseFloat(changeReward.amount).toFixed(2)} PED</span>
                  </div>
                  {#if changeReward.contribution_score != null}
                    <div class="info-row">
                      <span class="info-label">Score</span>
                      <span class="info-value">{parseFloat(changeReward.contribution_score).toFixed(2)}</span>
                    </div>
                  {/if}
                  <div class="info-row">
                    <span class="info-label">Rule</span>
                    <span class="info-value">{changeReward.rule_name || 'Custom'}</span>
                  </div>
                  {#if changeReward.note}
                    <div class="info-row">
                      <span class="info-label">Note</span>
                      <span class="info-value">{changeReward.note}</span>
                    </div>
                  {/if}
                  <div class="info-row">
                    <span class="info-label">Assigned by</span>
                    <span class="info-value">{changeReward.assigned_by_name || 'Unknown'}</span>
                  </div>
                  <div class="info-row">
                    <span class="info-label">Date</span>
                    <span class="info-value">{formatDate(changeReward.created_at)}</span>
                  </div>
                  <button class="reward-remove-btn" onclick={removeReward}>Remove Reward</button>
                </div>
              {:else}
                <div class="reward-form">
                  {#if matchingRules.length > 0}
                    <div class="reward-field">
                      <label>Rule
                      <select bind:value={rewardForm.rule_id} onchange={onRuleSelect}>
                        <option value="">Custom (no rule)</option>
                        {#each matchingRules as rule}
                          <option value={String(rule.id)}>
                            {rule.name} ({rule.min_amount === rule.max_amount ? `${parseFloat(rule.min_amount).toFixed(2)}` : `${parseFloat(rule.min_amount).toFixed(2)}-${parseFloat(rule.max_amount).toFixed(2)}`} PED)
                          </option>
                        {/each}
                      </select>
                      </label>
                    </div>
                  {/if}
                  <div class="reward-field">
                    <label>Amount (PED)
                    <input type="number" step="0.01" min="0.01" bind:value={rewardForm.amount} placeholder="0.00" />
                    </label>
                  </div>
                  <div class="reward-field">
                    <label>Score
                    <input type="number" step="0.01" min="0" bind:value={rewardForm.contribution_score} placeholder="Optional" />
                    </label>
                  </div>
                  <div class="reward-field">
                    <label>Note
                    <input type="text" bind:value={rewardForm.note} placeholder="Optional" />
                    </label>
                  </div>
                  <button class="action-link action-link-primary" style="margin-top: 8px;" onclick={assignReward} disabled={isAssigningReward}>
                    {isAssigningReward ? 'Assigning...' : 'Assign Reward'}
                  </button>
                </div>
              {/if}
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<JsonCompareDialog
  show={showCompareDialog}
  title="Compare: {change?.data?.Name || 'Entity'}"
  oldData={comparisonData}
  newData={currentData}
  oldLabel={selectedVersionType === 'original' ? 'Original Version' : selectedVersionType?.startsWith('related-') ? 'Previous Approved Change' : 'Previous Edit'}
  newLabel="Current Change"
  onclose={() => showCompareDialog = false}
/>
