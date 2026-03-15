<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { addToast } from '$lib/stores/toasts.js';

  let activeTab = $state('contributors');
  let isLoading = $state(true);
  let error = null;

  // Summary stats
  let summary = $state({ total_earned: 0, total_paid: 0, total_pending: 0, reward_count: 0, pending_payout_count: 0, total_score: 0 });

  // Contributors tab
  let contributors = $state([]);
  let contributorsTotal = $state(0);
  let contributorsPage = $state(1);
  let contributorsTotalPages = $state(1);
  let contributorSearch = $state('');
  let expandedContributor = $state(null);
  let contributorDetail = $state(null);
  let showRetroAssignForm = $state(false);
  let isRetroAssigning = $state(false);
  let isLoadingRetroRules = $state(false);
  let retroAssignTarget = $state(null);
  let retroMatchingRules = $state([]);
  let retroRewardForm = $state(getEmptyRetroRewardForm());

  // Rules tab
  let rules = $state([]);
  let editingRule = $state(null);
  let showRuleForm = $state(false);
  let ruleForm = $state(getEmptyRuleForm());

  // Payouts tab
  let payouts = $state([]);
  let payoutsTotal = $state(0);
  let payoutsPage = $state(1);
  let payoutsTotalPages = $state(1);
  let payoutStatusFilter = $state('');
  let showPayoutForm = $state(false);
  let payoutForm = $state({ user_id: '', amount: '', is_bonus: false, note: '' });

  function getEmptyRuleForm() {
    return { name: '', description: '', category: '', entities: '', change_type: '', data_fields: '', min_amount: '', max_amount: '', sort_order: '0' };
  }

  function getEmptyRetroRewardForm() {
    return { rule_id: '', amount: '', note: '' };
  }

  onMount(() => {
    loadSummary();
    loadContributors();
    loadRules();
    loadPayouts();
  });

  async function loadSummary() {
    try {
      const res = await fetch('/api/admin/rewards/summary');
      if (res.ok) summary = await res.json();
    } catch {}
  }

  async function loadContributors() {
    isLoading = true;
    try {
      const params = new URLSearchParams({ page: String(contributorsPage), limit: '50' });
      if (contributorSearch) params.set('q', contributorSearch);
      const res = await fetch(`/api/admin/rewards/contributors?${params}`);
      if (!res.ok) { isLoading = false; return; }
      const data = await res.json();
      contributors = data.contributors || [];
      contributorsTotal = data.total || 0;
      contributorsTotalPages = data.totalPages || 1;
    } catch (e) {
      error = e.message;
    } finally {
      isLoading = false;
    }
  }

  async function loadContributorDetail(userId, forceReload = false) {
    if (!forceReload && expandedContributor === userId) {
      expandedContributor = null;
      contributorDetail = null;
      closeRetroAssignForm();
      return;
    }
    if (!forceReload) {
      closeRetroAssignForm();
    }
    expandedContributor = userId;
    contributorDetail = null;
    try {
      const res = await fetch(`/api/admin/rewards/contributors/${userId}`);
      if (!res.ok) return;
      const data = await res.json();
      contributorDetail = {
        user: data.user || null,
        rewards: data.rewards || [],
        payouts: data.payouts || [],
        eligible_changes: data.eligible_changes || []
      };
    } catch {}
  }

  async function loadRules() {
    try {
      const res = await fetch('/api/admin/rewards/rules');
      if (!res.ok) return;
      const data = await res.json();
      rules = data.rules || [];
    } catch {}
  }

  async function loadPayouts() {
    try {
      const params = new URLSearchParams({ page: String(payoutsPage), limit: '50' });
      if (payoutStatusFilter) params.set('status', payoutStatusFilter);
      const res = await fetch(`/api/admin/rewards/payouts?${params}`);
      if (!res.ok) return;
      const data = await res.json();
      payouts = data.payouts || [];
      payoutsTotal = data.total || 0;
      payoutsTotalPages = data.totalPages || 1;
    } catch {}
  }

  // Rule CRUD
  function startCreateRule() {
    editingRule = null;
    ruleForm = getEmptyRuleForm();
    showRuleForm = true;
  }

  function startEditRule(rule) {
    editingRule = rule.id;
    ruleForm = {
      name: rule.name || '',
      description: rule.description || '',
      category: rule.category || '',
      entities: (rule.entities || []).join(', '),
      change_type: rule.change_type || '',
      data_fields: (rule.data_fields || []).join(', '),
      min_amount: rule.min_amount,
      max_amount: rule.max_amount,
      sort_order: String(rule.sort_order || 0)
    };
    showRuleForm = true;
  }

  function parseArrayField(str) {
    if (!str?.trim()) return null;
    return str.split(',').map(s => s.trim()).filter(Boolean);
  }

  async function saveRule() {
    const body = {
      name: ruleForm.name,
      description: ruleForm.description || null,
      category: ruleForm.category || null,
      entities: parseArrayField(ruleForm.entities),
      change_type: ruleForm.change_type || null,
      data_fields: parseArrayField(ruleForm.data_fields),
      min_amount: parseFloat(ruleForm.min_amount),
      max_amount: parseFloat(ruleForm.max_amount),
      sort_order: parseInt(ruleForm.sort_order || '0')
    };

    const url = editingRule ? `/api/admin/rewards/rules/${editingRule}` : '/api/admin/rewards/rules';
    const method = editingRule ? 'PATCH' : 'POST';

    const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (res.ok) {
      showRuleForm = false;
      editingRule = null;
      await loadRules();
    } else {
      const data = await res.json();
      addToast(data.error || 'Failed to save rule');
    }
  }

  async function deleteRule(id) {
    if (!confirm('Delete this reward rule?')) return;
    const res = await fetch(`/api/admin/rewards/rules/${id}`, { method: 'DELETE' });
    if (res.ok) await loadRules();
  }

  async function toggleRuleActive(rule) {
    await fetch(`/api/admin/rewards/rules/${rule.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active: !rule.active })
    });
    await loadRules();
  }

  // Payout CRUD
  async function createPayout() {
    if (!payoutForm.user_id || !payoutForm.amount) return;
    const res = await fetch('/api/admin/rewards/payouts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: payoutForm.user_id,
        amount: parseFloat(payoutForm.amount),
        is_bonus: payoutForm.is_bonus,
        note: payoutForm.note || null
      })
    });
    if (res.ok) {
      showPayoutForm = false;
      payoutForm = { user_id: '', amount: '', is_bonus: false, note: '' };
      await Promise.all([loadPayouts(), loadSummary(), loadContributors()]);
    } else {
      const data = await res.json();
      addToast(data.error || 'Failed to create payout');
    }
  }

  async function completePayout(id) {
    const res = await fetch(`/api/admin/rewards/payouts/${id}`, { method: 'PATCH' });
    if (res.ok) {
      await Promise.all([loadPayouts(), loadSummary()]);
    }
  }

  function startPayoutForUser(userId, amount) {
    payoutForm = { user_id: String(userId), amount: String(amount), is_bonus: false, note: '' };
    showPayoutForm = true;
    activeTab = 'payouts';
  }

  function formatAmount(val) {
    const num = parseFloat(val);
    return isNaN(num) ? '0.00' : num.toFixed(2);
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  }

  function contributorSearchKeydown(e) {
    if (e.key === 'Enter') {
      contributorsPage = 1;
      loadContributors();
    }
  }

  function closeRetroAssignForm() {
    showRetroAssignForm = false;
    isRetroAssigning = false;
    isLoadingRetroRules = false;
    retroAssignTarget = null;
    retroMatchingRules = [];
    retroRewardForm = getEmptyRetroRewardForm();
  }

  async function startRetroAssign(change) {
    retroAssignTarget = change;
    retroMatchingRules = [];
    retroRewardForm = getEmptyRetroRewardForm();
    showRetroAssignForm = true;
    isLoadingRetroRules = true;

    try {
      const [rewardRes, matchRes] = await Promise.all([
        fetch(`/api/admin/rewards/assign?change_id=${change.id}`),
        fetch(`/api/admin/rewards/match/${change.id}`)
      ]);

      if (rewardRes.ok) {
        const rewardData = await rewardRes.json();
        if (rewardData?.rewards?.length) {
          addToast('This change already has reward(s) assigned.');
          if (expandedContributor) {
            await loadContributorDetail(expandedContributor, true);
          }
          closeRetroAssignForm();
          return;
        }
      }

      if (matchRes.ok) {
        const data = await matchRes.json();
        retroMatchingRules = data.rules || [];
        if (retroMatchingRules.length === 1) {
          const rule = retroMatchingRules[0];
          retroRewardForm.rule_id = String(rule.id);
          retroRewardForm.amount = rule.min_amount === rule.max_amount ? String(rule.min_amount) : '';
        }
      }
    } catch {
      addToast('Failed to load reward suggestions for this change');
    } finally {
      isLoadingRetroRules = false;
    }
  }

  function onRetroRuleSelect() {
    const rule = retroMatchingRules.find(r => String(r.id) === retroRewardForm.rule_id);
    if (!rule) return;
    if (rule.min_amount === rule.max_amount) {
      retroRewardForm.amount = String(rule.min_amount);
    }
  }

  async function assignRetroReward() {
    if (!retroAssignTarget) return;
    if (!retroRewardForm.amount || parseFloat(retroRewardForm.amount) <= 0) return;

    const userId = contributorDetail?.user?.id || expandedContributor;
    if (!userId) {
      addToast('Unable to determine contributor user ID');
      return;
    }

    isRetroAssigning = true;
    try {
      const res = await fetch('/api/admin/rewards/assign', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          change_id: parseInt(retroAssignTarget.id),
          user_id: String(userId),
          rule_id: retroRewardForm.rule_id ? parseInt(retroRewardForm.rule_id) : null,
          amount: parseFloat(retroRewardForm.amount),
          note: retroRewardForm.note?.trim() || null
        })
      });

      if (!res.ok) {
        const data = await res.json();
        addToast(data.error || 'Failed to assign reward');
        return;
      }

      addToast('Reward assigned');
      closeRetroAssignForm();
      await Promise.all([
        loadSummary(),
        loadContributors(),
        expandedContributor ? loadContributorDetail(expandedContributor, true) : Promise.resolve()
      ]);
    } catch {
      addToast('Failed to assign reward');
    } finally {
      isRetroAssigning = false;
    }
  }
</script>

<svelte:head>
  <title>Rewards | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .rewards-page { max-width: 1200px; }
  .breadcrumb { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; font-size: 14px; }
  .breadcrumb a { color: var(--accent-color); text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }
  .breadcrumb span { color: var(--text-muted); }
  h1 { margin: 0 0 20px; font-size: 24px; color: var(--text-color); }

  /* Stats */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
  }
  .stat-card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 14px;
    text-align: center;
  }
  .stat-value { font-size: 22px; font-weight: 700; color: var(--text-color); }
  .stat-value.earned { color: var(--success-color); }
  .stat-value.paid { color: var(--accent-color); }
  .stat-value.owed { color: var(--warning-color); }
  .stat-label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

  /* Tabs */
  .tabs { display: flex; gap: 0; border-bottom: 1px solid var(--border-color); margin-bottom: 16px; }
  .tab {
    padding: 10px 20px; background: none; border: none;
    border-bottom: 2px solid transparent; color: var(--text-muted);
    cursor: pointer; font-size: 14px; font-weight: 500;
  }
  .tab:hover { color: var(--text-color); }
  .tab.active { color: var(--accent-color); border-bottom-color: var(--accent-color); }

  /* Tables */
  .data-table {
    width: 100%; border-collapse: collapse;
    font-size: 14px;
  }
  .data-table th {
    text-align: left; padding: 10px 12px;
    border-bottom: 2px solid var(--border-color);
    color: var(--text-muted); font-weight: 600; font-size: 12px;
    text-transform: uppercase; letter-spacing: 0.5px;
  }
  .data-table td {
    padding: 10px 12px; border-bottom: 1px solid var(--border-color);
    color: var(--text-color);
  }
  .data-table tr:hover td { background: var(--hover-color); }
  .data-table tr.expanded td { background: rgba(59, 130, 246, 0.05); }

  .clickable-row { cursor: pointer; }

  /* User display */
  .user-cell { display: flex; align-items: center; gap: 8px; }
  .user-avatar {
    width: 28px; height: 28px; border-radius: 50%;
    background: var(--hover-color);
  }
  .user-name { font-weight: 500; }
  .user-eu { font-size: 12px; color: var(--text-muted); }

  /* Detail panel */
  .detail-row td { padding: 0; background: var(--primary-color) !important; }
  .detail-panel { padding: 16px 12px; }
  .detail-section { margin-bottom: 16px; }
  .detail-section h4 { margin: 0 0 8px; font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
  .detail-table { width: 100%; font-size: 13px; }
  .detail-table th { padding: 6px 8px; font-size: 11px; }
  .detail-table td { padding: 6px 8px; border-bottom: 1px solid var(--border-color); }

  /* Badges */
  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 11px; font-weight: 500;
  }
  .badge-pending { background: rgba(245, 158, 11, 0.2); color: var(--warning-color); }
  .badge-completed { background: rgba(16, 185, 129, 0.2); color: var(--success-color); }
  .badge-bonus { background: rgba(168, 85, 247, 0.2); color: #a855f7; }
  .badge-active { background: rgba(16, 185, 129, 0.2); color: var(--success-color); }
  .badge-inactive { background: rgba(107, 114, 128, 0.2); color: #6b7280; }

  /* Buttons */
  .btn {
    padding: 6px 14px; border-radius: 4px; border: 1px solid var(--border-color);
    background: var(--hover-color); color: var(--text-color);
    font-size: 13px; cursor: pointer; transition: all 0.15s ease;
  }
  .btn:hover { background: var(--accent-color); color: white; border-color: var(--accent-color); }
  .btn-primary { background: var(--accent-color); color: white; border-color: var(--accent-color); }
  .btn-primary:hover { background: var(--accent-color-hover); }
  .btn-success { background: var(--success-color); color: white; border-color: var(--success-color); }
  .btn-danger { background: transparent; color: var(--error-color); border-color: var(--error-color); }
  .btn-danger:hover { background: var(--error-color); color: white; }
  .btn-sm { padding: 3px 8px; font-size: 12px; }

  /* Controls bar */
  .controls { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
  .search-input {
    padding: 6px 10px; border: 1px solid var(--border-color); border-radius: 4px;
    background: var(--primary-color); color: var(--text-color); font-size: 13px;
    min-width: 200px;
  }
  .filter-select {
    padding: 6px 10px; border: 1px solid var(--border-color); border-radius: 4px;
    background: var(--primary-color); color: var(--text-color); font-size: 13px;
  }

  /* Pagination */
  .pagination {
    display: flex; align-items: center; justify-content: center;
    gap: 10px; margin-top: 16px; font-size: 13px; color: var(--text-muted);
  }

  /* Form overlay */
  .form-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5); z-index: 100;
    display: flex; align-items: center; justify-content: center;
  }
  .form-dialog {
    background: var(--secondary-color); border: 1px solid var(--border-color);
    border-radius: 8px; padding: 24px; width: 480px; max-width: 95vw;
    max-height: 90vh; overflow-y: auto;
  }
  .form-dialog h3 { margin: 0 0 16px; color: var(--text-color); }
  .form-group { margin-bottom: 12px; }
  .form-group label, .form-group .form-label-text { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 4px; }
  .form-group input, .form-group select, .form-group textarea {
    width: 100%; padding: 8px 10px; border: 1px solid var(--border-color);
    border-radius: 4px; background: var(--primary-color); color: var(--text-color);
    font-size: 14px; box-sizing: border-box;
  }
  .form-group textarea { resize: vertical; min-height: 60px; }
  .form-row { display: flex; gap: 12px; }
  .form-row .form-group { flex: 1; }
  .form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
  .checkbox-label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-color); cursor: pointer; }
  .checkbox-label input { width: auto; }

  .amount-cell { font-family: 'Consolas', monospace; text-align: right; }
  .balance-positive { color: var(--warning-color); font-weight: 600; }
  .balance-zero { color: var(--text-muted); }

  .empty-state { text-align: center; padding: 40px; color: var(--text-muted); }

  @media (max-width: 768px) {
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
    .data-table { font-size: 13px; }
    .data-table th, .data-table td { padding: 8px 6px; }
    .form-row { flex-direction: column; gap: 0; }
    .controls { flex-direction: column; align-items: stretch; }
  }
</style>

<div class="rewards-page">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Rewards</span>
  </div>

  <h1>Contributor Rewards</h1>

  <!-- Summary Stats -->
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-value earned">{formatAmount(summary.total_earned)} PED</div>
      <div class="stat-label">Total Earned</div>
    </div>
    <div class="stat-card">
      <div class="stat-value paid">{formatAmount(summary.total_paid)} PED</div>
      <div class="stat-label">Total Paid</div>
    </div>
    <div class="stat-card">
      <div class="stat-value owed">{formatAmount(parseFloat(summary.total_earned) - parseFloat(summary.total_paid))} PED</div>
      <div class="stat-label">Outstanding</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{summary.reward_count}</div>
      <div class="stat-label">Rewards Assigned</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{summary.pending_payout_count}</div>
      <div class="stat-label">Pending Payouts</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{formatAmount(summary.total_score)}</div>
      <div class="stat-label">Total Score</div>
    </div>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab" class:active={activeTab === 'contributors'} onclick={() => activeTab = 'contributors'}>
      Contributors ({contributorsTotal})
    </button>
    <button class="tab" class:active={activeTab === 'rules'} onclick={() => activeTab = 'rules'}>
      Rules ({rules.length})
    </button>
    <button class="tab" class:active={activeTab === 'payouts'} onclick={() => activeTab = 'payouts'}>
      Payouts ({payoutsTotal})
    </button>
  </div>

  <!-- Contributors Tab -->
  {#if activeTab === 'contributors'}
    <div class="controls">
      <input class="search-input" type="text" placeholder="Search contributors..." bind:value={contributorSearch} onkeydown={contributorSearchKeydown} />
      <button class="btn" onclick={() => { contributorsPage = 1; loadContributors(); }}>Search</button>
    </div>

    {#if contributors.length === 0 && !isLoading}
      <div class="empty-state">No contributors found.</div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Approved</th>
            <th>Rewarded</th>
            <th class="amount-cell">Earned</th>
            <th class="amount-cell">Paid</th>
            <th class="amount-cell">Balance</th>
            <th class="amount-cell">Score</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each contributors as c (c.id)}
            <tr class="clickable-row" class:expanded={expandedContributor === c.id} onclick={() => loadContributorDetail(c.id)}>
              <td>
                <div class="user-cell">
                  {#if c.avatar}
                    <img class="user-avatar" src="https://cdn.discordapp.com/avatars/{c.id}/{c.avatar}.webp?size=56" alt="" />
                  {:else}
                    <div class="user-avatar"></div>
                  {/if}
                  <div>
                    <div class="user-name">{c.global_name || 'Unknown'}</div>
                    {#if c.eu_name}<div class="user-eu">{c.eu_name}</div>{/if}
                  </div>
                </div>
              </td>
              <td>{c.approved_count}</td>
              <td>{c.rewarded_count}</td>
              <td class="amount-cell">{formatAmount(c.total_earned)}</td>
              <td class="amount-cell">{formatAmount(c.total_paid)}</td>
              <td class="amount-cell {parseFloat(c.total_earned) - parseFloat(c.total_paid) > 0 ? 'balance-positive' : 'balance-zero'}">
                {formatAmount(parseFloat(c.total_earned) - parseFloat(c.total_paid))}
              </td>
              <td class="amount-cell">{formatAmount(c.total_score)}</td>
              <td>
                {#if parseFloat(c.total_earned) - parseFloat(c.total_paid) > 0}
                  <button class="btn btn-sm" onclick={(e) => { e.stopPropagation(); startPayoutForUser(c.id, (parseFloat(c.total_earned) - parseFloat(c.total_paid)).toFixed(2)); }}>
                    Pay
                  </button>
                {/if}
              </td>
            </tr>
            {#if expandedContributor === c.id}
              <tr class="detail-row">
                <td colspan="8">
                  <div class="detail-panel">
                    {#if !contributorDetail}
                      <div style="color: var(--text-muted)">Loading...</div>
                    {:else}
                      <div class="detail-section">
                        <h4>Rewards ({contributorDetail.rewards.length})</h4>
                        {#if contributorDetail.rewards.length > 0}
                          <table class="detail-table">
                            <thead><tr><th>Change</th><th>Entity</th><th>Rule</th><th>Amount</th><th>Score</th><th>Note</th><th>Date</th></tr></thead>
                            <tbody>
                              {#each contributorDetail.rewards as r}
                                <tr>
                                  <td><a href="/admin/changes/{r.change_id}">#{r.change_id}</a> {r.entity_name || ''}</td>
                                  <td>{r.entity} ({r.type})</td>
                                  <td>{r.rule_name || 'Custom'}</td>
                                  <td class="amount-cell">{formatAmount(r.amount)}</td>
                                  <td class="amount-cell">{r.contribution_score != null ? formatAmount(r.contribution_score) : '-'}</td>
                                  <td>{r.note || '-'}</td>
                                  <td>{formatDate(r.created_at)}</td>
                                </tr>
                              {/each}
                            </tbody>
                          </table>
                        {:else}
                          <div style="color: var(--text-muted); font-size: 13px;">No rewards assigned yet.</div>
                        {/if}
                      </div>
                      <div class="detail-section">
                        <h4>Eligible Approved Changes ({contributorDetail.eligible_changes.length})</h4>
                        {#if contributorDetail.eligible_changes.length > 0}
                          <table class="detail-table">
                            <thead><tr><th>Change</th><th>Entity</th><th>Type</th><th>Updated</th><th></th></tr></thead>
                            <tbody>
                              {#each contributorDetail.eligible_changes as change}
                                <tr>
                                  <td>
                                    <a href="/admin/changes/{change.id}">#{change.id}</a>
                                    {#if change.entity_name}
                                      {' '}{change.entity_name}
                                    {/if}
                                  </td>
                                  <td>{change.entity}</td>
                                  <td>{change.type}</td>
                                  <td>{formatDate(change.last_update || change.created_at)}</td>
                                  <td style="text-align: right;">
                                    <button class="btn btn-sm" onclick={() => startRetroAssign(change)}>Assign</button>
                                  </td>
                                </tr>
                              {/each}
                            </tbody>
                          </table>
                        {:else}
                          <div style="color: var(--text-muted); font-size: 13px;">No unrewarded approved changes found.</div>
                        {/if}
                      </div>
                      <div class="detail-section">
                        <h4>Payouts ({contributorDetail.payouts.length})</h4>
                        {#if contributorDetail.payouts.length > 0}
                          <table class="detail-table">
                            <thead><tr><th>Amount</th><th>Type</th><th>Status</th><th>Note</th><th>Date</th></tr></thead>
                            <tbody>
                              {#each contributorDetail.payouts as p}
                                <tr>
                                  <td class="amount-cell">{formatAmount(p.amount)}</td>
                                  <td>{p.is_bonus ? 'Bonus' : 'Payout'}</td>
                                  <td><span class="badge {p.status === 'completed' ? 'badge-completed' : 'badge-pending'}">{p.status}</span></td>
                                  <td>{p.note || '-'}</td>
                                  <td>{formatDate(p.created_at)}</td>
                                </tr>
                              {/each}
                            </tbody>
                          </table>
                        {:else}
                          <div style="color: var(--text-muted); font-size: 13px;">No payouts yet.</div>
                        {/if}
                      </div>
                    {/if}
                  </div>
                </td>
              </tr>
            {/if}
          {/each}
        </tbody>
      </table>

      {#if contributorsTotalPages > 1}
        <div class="pagination">
          <button class="btn btn-sm" disabled={contributorsPage <= 1} onclick={() => { contributorsPage--; loadContributors(); }}>Previous</button>
          <span>Page {contributorsPage} of {contributorsTotalPages}</span>
          <button class="btn btn-sm" disabled={contributorsPage >= contributorsTotalPages} onclick={() => { contributorsPage++; loadContributors(); }}>Next</button>
        </div>
      {/if}
    {/if}
  {/if}

  <!-- Rules Tab -->
  {#if activeTab === 'rules'}
    <div class="controls">
      <button class="btn btn-primary" onclick={startCreateRule}>Create Rule</button>
    </div>

    {#if rules.length === 0}
      <div class="empty-state">No reward rules defined yet.</div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Category</th>
            <th>Entities</th>
            <th>Type</th>
            <th>Data Fields</th>
            <th class="amount-cell">Amount</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each rules as rule (rule.id)}
            <tr>
              <td>
                <strong>{rule.name}</strong>
                {#if rule.description}<br><span style="font-size: 12px; color: var(--text-muted)">{rule.description}</span>{/if}
              </td>
              <td>{rule.category || '-'}</td>
              <td style="max-width: 150px; font-size: 12px; word-break: break-word;">{rule.entities ? rule.entities.join(', ') : 'Any'}</td>
              <td>{rule.change_type || 'Any'}</td>
              <td style="font-size: 12px;">{rule.data_fields ? rule.data_fields.join(', ') : '-'}</td>
              <td class="amount-cell">
                {#if rule.min_amount === rule.max_amount}
                  {formatAmount(rule.min_amount)}
                {:else}
                  {formatAmount(rule.min_amount)} - {formatAmount(rule.max_amount)}
                {/if}
              </td>
              <td>
                <button class="badge {rule.active ? 'badge-active' : 'badge-inactive'}" style="cursor:pointer; border: none;" onclick={() => toggleRuleActive(rule)}>
                  {rule.active ? 'Active' : 'Inactive'}
                </button>
              </td>
              <td>
                <div style="display: flex; gap: 4px;">
                  <button class="btn btn-sm" onclick={() => startEditRule(rule)}>Edit</button>
                  <button class="btn btn-sm btn-danger" onclick={() => deleteRule(rule.id)}>Del</button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/if}

  <!-- Payouts Tab -->
  {#if activeTab === 'payouts'}
    <div class="controls">
      <button class="btn btn-primary" onclick={() => { showPayoutForm = true; }}>Create Payout</button>
      <select class="filter-select" bind:value={payoutStatusFilter} onchange={() => { payoutsPage = 1; loadPayouts(); }}>
        <option value="">All Status</option>
        <option value="pending">Pending</option>
        <option value="completed">Completed</option>
      </select>
    </div>

    {#if payouts.length === 0}
      <div class="empty-state">No payouts yet.</div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th>User</th>
            <th class="amount-cell">Amount</th>
            <th>Type</th>
            <th>Note</th>
            <th>Status</th>
            <th>Created</th>
            <th>Completed</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each payouts as p (p.id)}
            <tr>
              <td>
                <div class="user-cell">
                  {#if p.avatar}
                    <img class="user-avatar" src="https://cdn.discordapp.com/avatars/{p.user_id}/{p.avatar}.webp?size=56" alt="" />
                  {:else}
                    <div class="user-avatar"></div>
                  {/if}
                  <div>
                    <div class="user-name">{p.global_name || 'Unknown'}</div>
                    {#if p.eu_name}<div class="user-eu">{p.eu_name}</div>{/if}
                  </div>
                </div>
              </td>
              <td class="amount-cell">{formatAmount(p.amount)} PED</td>
              <td>
                {#if p.is_bonus}<span class="badge badge-bonus">Bonus</span>{:else}Payout{/if}
              </td>
              <td>{p.note || '-'}</td>
              <td><span class="badge {p.status === 'completed' ? 'badge-completed' : 'badge-pending'}">{p.status}</span></td>
              <td>{formatDate(p.created_at)}</td>
              <td>{p.completed_at ? formatDate(p.completed_at) : '-'}</td>
              <td>
                {#if p.status === 'pending'}
                  <button class="btn btn-sm btn-success" onclick={() => completePayout(p.id)}>Complete</button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>

      {#if payoutsTotalPages > 1}
        <div class="pagination">
          <button class="btn btn-sm" disabled={payoutsPage <= 1} onclick={() => { payoutsPage--; loadPayouts(); }}>Previous</button>
          <span>Page {payoutsPage} of {payoutsTotalPages}</span>
          <button class="btn btn-sm" disabled={payoutsPage >= payoutsTotalPages} onclick={() => { payoutsPage++; loadPayouts(); }}>Next</button>
        </div>
      {/if}
    {/if}
  {/if}
</div>

<!-- Rule Form Dialog -->
{#if showRuleForm}
  <div class="form-overlay" onclick={(e) => { if (e.target === e.currentTarget) showRuleForm = false; }} role="presentation">
    <div class="form-dialog">
      <h3>{editingRule ? 'Edit Rule' : 'Create Rule'}</h3>
      <div class="form-group">
        <label>Name *
          <input type="text" bind:value={ruleForm.name} placeholder="e.g. Add mob spawn" />
        </label>
      </div>
      <div class="form-group">
        <label>Description
          <textarea bind:value={ruleForm.description} placeholder="Shown on public bounties page"></textarea>
        </label>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Category
            <input type="text" bind:value={ruleForm.category} placeholder="e.g. Mapping" />
          </label>
        </div>
        <div class="form-group">
          <label>Change Type
            <select bind:value={ruleForm.change_type}>
              <option value="">Any</option>
              <option value="Create">Create</option>
              <option value="Update">Update</option>
              <option value="Delete">Delete</option>
            </select>
          </label>
        </div>
      </div>
      <div class="form-group">
        <label>Entities (comma-separated, leave empty for any)
          <input type="text" bind:value={ruleForm.entities} placeholder="e.g. Area, Location" />
        </label>
      </div>
      <div class="form-group">
        <label>Data Fields (comma-separated, optional)
          <input type="text" bind:value={ruleForm.data_fields} placeholder="e.g. Tiers, DamageTypes" />
        </label>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Min Amount (PED) *
            <input type="number" step="0.01" min="0" bind:value={ruleForm.min_amount} />
          </label>
        </div>
        <div class="form-group">
          <label>Max Amount (PED) *
            <input type="number" step="0.01" min="0" bind:value={ruleForm.max_amount} />
          </label>
        </div>
      </div>
      <div class="form-row">
        <div class="form-group">
          <label>Sort Order
            <input type="number" bind:value={ruleForm.sort_order} />
          </label>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn" onclick={() => showRuleForm = false}>Cancel</button>
        <button class="btn btn-primary" onclick={saveRule}>
          {editingRule ? 'Save Changes' : 'Create Rule'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Payout Form Dialog -->
{#if showPayoutForm}
  <div class="form-overlay" onclick={(e) => { if (e.target === e.currentTarget) showPayoutForm = false; }} role="presentation">
    <div class="form-dialog">
      <h3>Create Payout</h3>
      <div class="form-group">
        <label>User ID *
          <input type="text" bind:value={payoutForm.user_id} placeholder="Discord user ID" />
        </label>
      </div>
      <div class="form-group">
        <label>Amount (PED) *
          <input type="number" step="0.01" min="0.01" bind:value={payoutForm.amount} />
        </label>
      </div>
      <div class="form-group">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={payoutForm.is_bonus} /> This is a bonus payment
        </label>
      </div>
      <div class="form-group">
        <label>Note
          <textarea bind:value={payoutForm.note} placeholder="Optional note about this payout"></textarea>
        </label>
      </div>
      <div class="form-actions">
        <button class="btn" onclick={() => showPayoutForm = false}>Cancel</button>
        <button class="btn btn-primary" onclick={createPayout}>Create Payout</button>
      </div>
    </div>
  </div>
{/if}

<!-- Retroactive Reward Assignment Dialog -->
{#if showRetroAssignForm && retroAssignTarget}
  <div class="form-overlay" onclick={(e) => { if (e.target === e.currentTarget) closeRetroAssignForm(); }} role="presentation">
    <div class="form-dialog">
      <h3>Assign Reward</h3>
      <div class="form-group">
        <span class="form-label-text">Change</span>
        <div style="font-size: 14px; color: var(--text-color);">
          <a href="/admin/changes/{retroAssignTarget.id}">#{retroAssignTarget.id}</a>
          {#if retroAssignTarget.entity_name}
            {' '}{retroAssignTarget.entity_name}
          {/if}
        </div>
        <div style="margin-top: 4px; font-size: 12px; color: var(--text-muted);">
          {retroAssignTarget.entity} ({retroAssignTarget.type})
        </div>
      </div>

      {#if isLoadingRetroRules}
        <div class="form-group">
          <div style="font-size: 13px; color: var(--text-muted);">Loading matching rules...</div>
        </div>
      {/if}

      {#if retroMatchingRules.length > 0}
        <div class="form-group">
          <label>Rule
          <select bind:value={retroRewardForm.rule_id} onchange={onRetroRuleSelect}>
            <option value="">Custom (no rule)</option>
            {#each retroMatchingRules as rule}
              <option value={String(rule.id)}>
                {rule.name} ({rule.min_amount === rule.max_amount ? `${formatAmount(rule.min_amount)}` : `${formatAmount(rule.min_amount)}-${formatAmount(rule.max_amount)}`} PED)
              </option>
            {/each}
          </select>
          </label>
        </div>
      {/if}

      <div class="form-row">
        <div class="form-group">
          <label>Amount (PED) *
            <input type="number" step="0.01" min="0.01" bind:value={retroRewardForm.amount} />
          </label>
        </div>
      </div>

      <div class="form-group">
        <label>Note
          <textarea bind:value={retroRewardForm.note} placeholder="Optional note"></textarea>
        </label>
      </div>

      <div class="form-actions">
        <button class="btn" onclick={closeRetroAssignForm}>Cancel</button>
        <button class="btn btn-primary" onclick={assignRetroReward} disabled={isRetroAssigning || isLoadingRetroRules}>
          {isRetroAssigning ? 'Assigning...' : 'Assign Reward'}
        </button>
      </div>
    </div>
  </div>
{/if}
