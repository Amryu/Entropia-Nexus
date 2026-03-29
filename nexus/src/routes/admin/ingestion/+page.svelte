<script>
  /**
   * @typedef {Object} Props
   * @property {any} data
   */

  /** @type {Props} */
  let { data } = $props();

  let stats = $state((() => data.stats)());
  let alerts = $state([]);
  let alertTotal = $state(0);
  let alertPage = $state(1);
  let alertPeriod = $state('30'); // '30', '90', or 'all'
  const ALERTS_PER_PAGE = 10;
  let alertsLoading = $state(true);
  let users = $state((() => data.users)());
  let allowedClients = $state((() => data.allowedClients || [])());
  let tradeChannels = $state((() => data.tradeChannels || [])());

  let showBanDialog = $state(false);
  let showPurgeDialog = $state(false);
  let showResolveDialog = $state(false);
  let showAddClientDialog = $state(false);
  let selectedUserId = null;
  let selectedUserName = $state('');
  let selectedAlertId = null;
  let banReason = $state('');
  let resolveNotes = $state('');
  let actionError = $state('');
  let actionLoading = $state(false);

  // Add client dialog state
  let oauthClients = []; // All registered OAuth apps (fetched on demand)
  let oauthClientsLoaded = false;
  let addClientNotes = $state('');

  // Add channel dialog state
  let showAddChannelDialog = $state(false);
  let newChannelName = $state('');
  let newChannelPlanet = $state('');
  const KNOWN_PLANETS = ['Calypso', 'Arkadia', 'Cyrene', 'Rocktropia', 'Toulan', 'Next Island', 'Monria', 'FOMA'];

  // Active section tab
  let activeTab = $state('alerts');

  // Load alerts asynchronously after mount (don't block page load)
  loadAlertPage(1);

  function formatNumber(n) {
    return parseInt(n || 0).toLocaleString();
  }

  function formatDate(d) {
    if (!d) return '-';
    return new Date(d).toLocaleString();
  }

  function formatPercent(part, total) {
    if (!total || total === '0') return '0%';
    return Math.round((parseInt(part) / parseInt(total)) * 100) + '%';
  }

  let alertTotalPages = $derived(Math.max(1, Math.ceil(alertTotal / ALERTS_PER_PAGE)));

  async function loadAlertPage(page) {
    alertsLoading = true;
    try {
      const daysParam = alertPeriod !== 'all' ? `&days=${alertPeriod}` : '';
      const res = await fetch(`/api/admin/ingestion/alerts?page=${page}&limit=${ALERTS_PER_PAGE}${daysParam}`);
      if (res.ok) {
        const d = await res.json();
        alerts = d.rows;
        alertTotal = d.total;
        alertPage = page;
      }
    } catch (e) {
      console.error('Failed to load alerts:', e);
    } finally {
      alertsLoading = false;
    }
  }

  // --- Actions ---

  function openBan(userId, userName) {
    selectedUserId = userId;
    selectedUserName = userName;
    banReason = '';
    actionError = '';
    showBanDialog = true;
  }

  async function handleBan() {
    if (!banReason.trim()) {
      actionError = 'Reason is required';
      return;
    }
    actionLoading = true;
    actionError = '';
    try {
      const res = await fetch('/api/admin/ingestion/ban', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: selectedUserId, reason: banReason.trim() }),
      });
      if (!res.ok) {
        const data = await res.json();
        actionError = data.error || 'Failed to ban user';
        return;
      }
      showBanDialog = false;
      await reloadData();
    } catch (e) {
      actionError = 'Network error';
    } finally {
      actionLoading = false;
    }
  }

  async function handleUnban(userId) {
    try {
      const res = await fetch('/api/admin/ingestion/ban', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId }),
      });
      if (res.ok) await reloadData();
    } catch (e) {
      console.error('Failed to unban:', e);
    }
  }

  function openPurge(userId, userName) {
    selectedUserId = userId;
    selectedUserName = userName;
    actionError = '';
    showPurgeDialog = true;
  }

  async function handlePurge() {
    actionLoading = true;
    actionError = '';
    try {
      const res = await fetch(`/api/admin/ingestion/purge/${selectedUserId}`, {
        method: 'POST',
      });
      if (!res.ok) {
        const data = await res.json();
        actionError = data.error || 'Failed to purge data';
        return;
      }
      showPurgeDialog = false;
      await reloadData();
    } catch (e) {
      actionError = 'Network error';
    } finally {
      actionLoading = false;
    }
  }

  function openResolve(alertId) {
    selectedAlertId = alertId;
    resolveNotes = '';
    actionError = '';
    showResolveDialog = true;
  }

  async function handleResolve() {
    actionLoading = true;
    actionError = '';
    try {
      const res = await fetch(`/api/admin/ingestion/alerts/${selectedAlertId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resolved: true, notes: resolveNotes.trim() || null }),
      });
      if (!res.ok) {
        const data = await res.json();
        actionError = data.error || 'Failed to resolve alert';
        return;
      }
      showResolveDialog = false;
      await reloadData();
    } catch (e) {
      actionError = 'Network error';
    } finally {
      actionLoading = false;
    }
  }

  async function reloadData() {
    try {
      const [statsRes, alertsRes, usersRes, allowedRes, channelsRes] = await Promise.all([
        fetch('/api/admin/ingestion/stats'),
        fetch(`/api/admin/ingestion/alerts?page=${alertPage}&limit=${ALERTS_PER_PAGE}`),
        fetch('/api/admin/ingestion/users?limit=20'),
        fetch('/api/admin/ingestion/allowed?limit=50'),
        fetch('/api/admin/ingestion/channels'),
      ]);
      stats = await statsRes.json();
      const alertData = await alertsRes.json();
      alerts = alertData.rows;
      alertTotal = alertData.total;
      // If current page is now empty (e.g. resolved last alert on page), go back
      if (alerts.length === 0 && alertPage > 1) {
        alertPage = Math.min(alertPage, Math.max(1, Math.ceil(alertData.total / ALERTS_PER_PAGE)));
        await loadAlertPage(alertPage);
      }
      users = await usersRes.json();
      const allowedData = await allowedRes.json();
      allowedClients = allowedData.rows || [];
      const channelData = await channelsRes.json();
      tradeChannels = channelData.rows || [];
    } catch (e) {
      console.error('Failed to reload:', e);
    }
  }

  // --- Allowed Clients (OAuth Applications) ---

  async function openAddClient() {
    addClientNotes = '';
    actionError = '';
    if (!oauthClientsLoaded) {
      try {
        const res = await fetch('/api/admin/oauth/clients');
        if (res.ok) {
          const data = await res.json();
          oauthClients = data.clients || [];
        }
      } catch (e) {
        console.error('Failed to load OAuth clients:', e);
      }
      oauthClientsLoaded = true;
    }
    showAddClientDialog = true;
  }

  function availableOAuthClients() {
    const allowedIds = new Set(allowedClients.map(c => c.client_id));
    return oauthClients.filter(c => !allowedIds.has(c.id));
  }

  async function handleAddClient(clientId) {
    actionLoading = true;
    actionError = '';
    try {
      const res = await fetch('/api/admin/ingestion/allowed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clientId, notes: addClientNotes.trim() || null }),
      });
      if (!res.ok) {
        const data = await res.json();
        actionError = data.error || 'Failed to add application';
        return;
      }
      showAddClientDialog = false;
      oauthClientsLoaded = false; // refresh on next open
      await reloadData();
    } catch (e) {
      actionError = 'Network error';
    } finally {
      actionLoading = false;
    }
  }

  async function handleRemoveClient(clientId) {
    try {
      const res = await fetch('/api/admin/ingestion/allowed', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ clientId }),
      });
      if (res.ok) {
        oauthClientsLoaded = false;
        await reloadData();
      }
    } catch (e) {
      console.error('Failed to remove client:', e);
    }
  }

  // --- Trade Channels ---

  function openAddChannel() {
    newChannelName = '';
    newChannelPlanet = '';
    actionError = '';
    showAddChannelDialog = true;
  }

  async function handleAddChannel() {
    const name = newChannelName.trim().toLowerCase();
    if (!name) {
      actionError = 'Channel name is required';
      return;
    }
    actionLoading = true;
    actionError = '';
    try {
      const res = await fetch('/api/admin/ingestion/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channelName: name, planet: newChannelPlanet || null }),
      });
      if (!res.ok) {
        const data = await res.json();
        actionError = data.error || 'Failed to add channel';
        return;
      }
      showAddChannelDialog = false;
      await reloadData();
    } catch (e) {
      actionError = 'Network error';
    } finally {
      actionLoading = false;
    }
  }

  async function handleRemoveChannel(channelName) {
    try {
      const res = await fetch('/api/admin/ingestion/channels', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channelName }),
      });
      if (res.ok) await reloadData();
    } catch (e) {
      console.error('Failed to remove channel:', e);
    }
  }
</script>

<div class="ingestion-page">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <span>Ingestion</span>
  </div>

  <h1>Data Ingestion</h1>
  <p class="subtitle">Crowdsourced trade messages and global events from desktop clients</p>

  <!-- Stats Grid -->
  <div class="stats-grid">
    <div class="stat-card">
      <h3>Globals Ingested</h3>
      <p class="stat-value">{formatNumber(stats.total_globals)} <span class="stat-inline-detail">({formatPercent(stats.confirmed_globals, stats.total_globals)} confirmed)</span></p>
    </div>
    <div class="stat-card">
      <h3>Trade Messages</h3>
      <p class="stat-value">{formatNumber(stats.total_trades)}</p>
    </div>
    <div class="stat-card">
      <h3>Active Contributors</h3>
      <p class="stat-value">{formatNumber(stats.active_contributors)}</p>
    </div>
    <div class="stat-card">
      <h3>Pending Alerts</h3>
      <p class="stat-value" class:stat-pending={parseInt(stats.pending_alerts) > 0}>
        {formatNumber(stats.pending_alerts)}
      </p>
    </div>
    <div class="stat-card">
      <h3>Active Bans</h3>
      <p class="stat-value" class:stat-denied={parseInt(stats.active_bans) > 0}>
        {formatNumber(stats.active_bans)}
      </p>
    </div>
    <div class="stat-card">
      <h3>Allowed Clients</h3>
      <p class="stat-value">{formatNumber(stats.allowed_clients)}</p>
    </div>
    <div class="stat-card">
      <h3>Trade Channels</h3>
      <p class="stat-value">{formatNumber(stats.configured_channels)}</p>
    </div>
    <div class="stat-card">
      <h3>Price Submissions</h3>
      <p class="stat-value">{formatNumber(stats.total_mp_submissions)}</p>
    </div>
    <div class="stat-card">
      <h3>Price Contributors</h3>
      <p class="stat-value">{formatNumber(stats.mp_contributors)}</p>
    </div>
    <div class="stat-card">
      <h3>Finalized Snapshots</h3>
      <p class="stat-value">{formatNumber(stats.finalized_snapshots)}</p>
    </div>
  </div>

  <!-- Tabs -->
  <div class="tabs">
    <button class="tab" class:active={activeTab === 'alerts'} onclick={() => activeTab = 'alerts'}>
      Alerts {parseInt(stats.pending_alerts) > 0 ? `(${stats.pending_alerts})` : ''}
    </button>
    <button class="tab" class:active={activeTab === 'users'} onclick={() => activeTab = 'users'}>
      Contributors
    </button>
    <button class="tab" class:active={activeTab === 'allowed'} onclick={() => activeTab = 'allowed'}>
      Allowed Clients ({formatNumber(stats.allowed_clients)})
    </button>
    <button class="tab" class:active={activeTab === 'channels'} onclick={() => activeTab = 'channels'}>
      Trade Channels ({formatNumber(stats.configured_channels)})
    </button>
  </div>

  <!-- Alerts Tab -->
  {#if activeTab === 'alerts'}
    <div class="section">
      <div class="alert-period-filter">
        {#each [['1', '24h'], ['7', '7 days'], ['30', '30 days'], ['90', '90 days'], ['all', 'All time']] as [value, label]}
          <button class="period-btn" class:active={alertPeriod === value} onclick={() => { alertPeriod = value; loadAlertPage(1); }}>
            {label}
          </button>
        {/each}
      </div>
      {#if alerts.length === 0 && !alertsLoading}
        <p class="empty-state">No pending alerts</p>
      {:else}
        {#each alerts as alert}
          <div class="alert-card" class:loading-fade={alertsLoading}>
            <div class="alert-header">
              <span class="alert-type"
                class:badge-danger={alert.type === 'collusion_pattern' || alert.type === 'solo_fabrication'}
                class:badge-warning={alert.type === 'mp_consistent_outlier' || alert.type === 'mp_confidence_cluster' || alert.type === 'mp_low_confidence'}>
                {alert.type.replace(/_/g, ' ')}
              </span>
              <span class="alert-date">{formatDate(alert.created_at)}</span>
            </div>
            <div class="alert-body">
              <p><strong>Users:</strong> {(alert.user_names || []).filter(Boolean).join(', ') || 'Unknown'}</p>
              {#if alert.details}
                <div class="alert-details">
                  <!-- collusion_pattern -->
                  {#if alert.type === 'collusion_pattern'}
                    <span>Shared: {alert.details.shared_count}</span>
                    <span>Exclusive: {alert.details.exclusive_count} ({alert.details.exclusive_rate}%)</span>
                    {#if alert.details.exclusive_hofs > 0}
                      <span class="stat-denied">Exclusive HoFs: {alert.details.exclusive_hofs}</span>
                    {/if}
                    <span>Suspicion: {alert.details.suspicion_level}</span>
                    {#if alert.details.top_locations?.length > 0}
                      <span>Locations: {alert.details.top_locations.map(l => l.location).join(', ')}</span>
                    {/if}
                  {/if}

                  <!-- solo_fabrication -->
                  {#if alert.type === 'solo_fabrication'}
                    <span>Submissions: {alert.details.submission_count}</span>
                    <span>Solo: {alert.details.solo_count} ({alert.details.solo_rate}%)</span>
                    {#if alert.details.solo_hof_count > 0}
                      <span class="stat-denied">Solo HoFs: {alert.details.solo_hof_count}</span>
                    {/if}
                    <span>Avg solo rate: {alert.details.avg_solo_rate}%</span>
                  {/if}

                  <!-- mp_consistent_outlier -->
                  {#if alert.type === 'mp_consistent_outlier'}
                    <span>Price Submissions: {alert.details.total_submissions}</span>
                    <span>Outliers: {alert.details.outlier_count} ({alert.details.outlier_rate}%)</span>
                    <span>Avg outlier score: {alert.details.avg_outlier_score}</span>
                  {/if}

                  <!-- mp_confidence_cluster -->
                  {#if alert.type === 'mp_confidence_cluster'}
                    <span>Price Submissions: {alert.details.total_submissions}</span>
                    <span>Mode confidence: {alert.details.mode_confidence}</span>
                    <span>At mode: {alert.details.mode_count} ({alert.details.mode_pct}%)</span>
                  {/if}

                  <!-- mp_low_confidence -->
                  {#if alert.type === 'mp_low_confidence'}
                    <span>Price Submissions: {alert.details.total_submissions}</span>
                    <span>Below {alert.details.threshold}: {alert.details.low_count} ({alert.details.low_rate}%)</span>
                    <span>Avg confidence: {alert.details.avg_confidence}</span>
                  {/if}
                </div>
              {/if}
            </div>
            <div class="alert-actions">
              <button class="btn btn-small btn-secondary" onclick={() => openResolve(alert.id)}>
                Resolve
              </button>
              {#each (alert.user_ids || []) as uid}
                <button class="btn btn-small btn-danger" onclick={() => openBan(uid, '')}>
                  Ban User {uid}
                </button>
              {/each}
            </div>
          </div>
        {/each}

        {#if alertTotalPages > 1}
          <div class="pagination">
            <button class="btn btn-small btn-secondary" disabled={alertPage <= 1 || alertsLoading} onclick={() => loadAlertPage(alertPage - 1)}>
              Previous
            </button>
            <span class="pagination-info">Page {alertPage} of {alertTotalPages}</span>
            <button class="btn btn-small btn-secondary" disabled={alertPage >= alertTotalPages || alertsLoading} onclick={() => loadAlertPage(alertPage + 1)}>
              Next
            </button>
          </div>
        {/if}
      {/if}
    </div>
  {/if}

  <!-- Users Tab -->
  {#if activeTab === 'users'}
    <div class="section">
      {#if users.length === 0}
        <p class="empty-state">No contributors yet</p>
      {:else}
        <table class="data-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Submissions</th>
              <th>Prices</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each users as user}
              <tr>
                <td>
                  <a href="/admin/users/{user.user_id}">{user.username || `User ${user.user_id}`}</a>
                </td>
                <td>{formatNumber(user.submission_count)}</td>
                <td>{formatNumber(user.mp_count)}</td>
                <td>
                  {#if user.banned}
                    <span class="status-badge status-banned">Banned</span>
                  {:else}
                    <span class="status-badge status-active">Active</span>
                  {/if}
                </td>
                <td class="actions-cell">
                  {#if user.banned}
                    <button class="btn btn-small btn-success" onclick={() => handleUnban(user.user_id)}>
                      Unban
                    </button>
                  {:else}
                    <button class="btn btn-small btn-danger" onclick={() => openBan(user.user_id, user.username)}>
                      Ban
                    </button>
                  {/if}
                  <button class="btn btn-small btn-warning" onclick={() => openPurge(user.user_id, user.username)}>
                    Purge
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  {/if}

  <!-- Allowed Clients Tab -->
  {#if activeTab === 'allowed'}
    <div class="section">
      <div class="section-header">
        <p class="section-description">Only approved OAuth applications can submit ingestion data. Distribution endpoints remain open to all verified users.</p>
        <button class="btn btn-primary" onclick={openAddClient}>Add Application</button>
      </div>

      {#if allowedClients.length === 0}
        <p class="empty-state">No applications configured — ingestion submissions are blocked for all clients</p>
      {:else}
        <table class="data-table">
          <thead>
            <tr>
              <th>Application</th>
              <th>Client ID</th>
              <th>Approved By</th>
              <th>Date</th>
              <th>Notes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each allowedClients as client}
              <tr>
                <td>{client.client_name}</td>
                <td class="hash-cell">{client.client_id}</td>
                <td>{client.allowed_by_name || '-'}</td>
                <td>{formatDate(client.allowed_at)}</td>
                <td class="notes-cell">{client.notes || '-'}</td>
                <td>
                  <button class="btn btn-small btn-danger" onclick={() => handleRemoveClient(client.client_id)}>
                    Remove
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  {/if}

  <!-- Trade Channels Tab -->
  {#if activeTab === 'channels'}
    <div class="section">
      <div class="section-header">
        <p class="section-description">Configure which trade channels are accepted for ingestion. Only messages from listed channels will be processed.</p>
        <button class="btn btn-primary" onclick={openAddChannel}>Add Channel</button>
      </div>

      {#if tradeChannels.length === 0}
        <p class="empty-state">No channels configured — all trade messages will be rejected</p>
      {:else}
        <table class="data-table">
          <thead>
            <tr>
              <th>Channel</th>
              <th>Planet</th>
              <th>Added By</th>
              <th>Date</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {#each tradeChannels as ch}
              <tr>
                <td><code>{ch.channel_name}</code></td>
                <td>{ch.planet || 'Global'}</td>
                <td>{ch.added_by_name || '-'}</td>
                <td>{formatDate(ch.added_at)}</td>
                <td>
                  <button class="btn btn-small btn-danger" onclick={() => handleRemoveChannel(ch.channel_name)}>
                    Remove
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </div>
  {/if}
</div>

<!-- Ban Dialog -->
{#if showBanDialog}
  <div class="dialog-overlay" role="presentation" onclick={() => showBanDialog = false}>
    <div class="dialog" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
      <h3>Ban from Ingestion</h3>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        This will block the user from submitting and receiving ingestion data.
        {selectedUserName ? `User: ${selectedUserName}` : ''}
      </p>

      {#if actionError}
        <div class="error-message">{actionError}</div>
      {/if}

      <div class="form-group">
        <label for="ban-reason">Reason *</label>
        <textarea
          id="ban-reason"
          bind:value={banReason}
          placeholder="Describe why this user is being banned from ingestion..."
        ></textarea>
      </div>

      <div class="dialog-buttons">
        <button class="btn btn-secondary" onclick={() => showBanDialog = false}>Cancel</button>
        <button class="btn btn-danger" onclick={handleBan} disabled={actionLoading}>
          {actionLoading ? 'Banning...' : 'Ban User'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Purge Dialog -->
{#if showPurgeDialog}
  <div class="dialog-overlay" role="presentation" onclick={() => showPurgeDialog = false}>
    <div class="dialog" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
      <h3>Purge User Data</h3>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        This will permanently delete all ingested data (globals, trades, and market prices)
        from this user, recalculate confirmation counts, and re-finalize affected price snapshots.
        This action cannot be undone.
        {selectedUserName ? `User: ${selectedUserName}` : ''}
      </p>

      {#if actionError}
        <div class="error-message">{actionError}</div>
      {/if}

      <div class="dialog-buttons">
        <button class="btn btn-secondary" onclick={() => showPurgeDialog = false}>Cancel</button>
        <button class="btn btn-danger" onclick={handlePurge} disabled={actionLoading}>
          {actionLoading ? 'Purging...' : 'Purge All Data'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Resolve Alert Dialog -->
{#if showResolveDialog}
  <div class="dialog-overlay" role="presentation" onclick={() => showResolveDialog = false}>
    <div class="dialog" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
      <h3>Resolve Alert</h3>

      {#if actionError}
        <div class="error-message">{actionError}</div>
      {/if}

      <div class="form-group">
        <label for="resolve-notes">Resolution Notes (optional)</label>
        <textarea
          id="resolve-notes"
          bind:value={resolveNotes}
          placeholder="Describe the resolution..."
        ></textarea>
      </div>

      <div class="dialog-buttons">
        <button class="btn btn-secondary" onclick={() => showResolveDialog = false}>Cancel</button>
        <button class="btn btn-success" onclick={handleResolve} disabled={actionLoading}>
          {actionLoading ? 'Resolving...' : 'Mark Resolved'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Add Application Dialog -->
{#if showAddClientDialog}
  <div class="dialog-overlay" role="presentation" onclick={() => showAddClientDialog = false}>
    <div class="dialog dialog-wide" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
      <h3>Allow Application</h3>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        Select a registered OAuth application to grant ingestion access.
      </p>

      {#if actionError}
        <div class="error-message">{actionError}</div>
      {/if}

      {#if availableOAuthClients().length > 0}
        <div class="search-results">
          {#each availableOAuthClients() as app}
            <button
              class="search-result-item"
              onclick={() => handleAddClient(app.id)}
              disabled={actionLoading}
            >
              <div>
                <div class="search-result-name">{app.name}</div>
                {#if app.description}
                  <div class="search-result-eu">{app.description}</div>
                {/if}
              </div>
              <span class="badge">{app.is_confidential ? 'Confidential' : 'Public'}</span>
            </button>
          {/each}
        </div>
      {:else}
        <p class="search-status">No unregistered OAuth applications available</p>
      {/if}

      <div class="form-group" style="margin-top: 12px;">
        <label for="client-notes">Notes (optional)</label>
        <input
          id="client-notes"
          type="text"
          bind:value={addClientNotes}
          placeholder="e.g. Official desktop client"
        />
      </div>

      <div class="dialog-buttons">
        <button class="btn btn-secondary" onclick={() => showAddClientDialog = false}>Close</button>
      </div>
    </div>
  </div>
{/if}

<!-- Add Trade Channel Dialog -->
{#if showAddChannelDialog}
  <div class="dialog-overlay" role="presentation" onclick={() => showAddChannelDialog = false}>
    <div class="dialog" role="dialog" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
      <h3>Add Trade Channel</h3>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        Add a trade channel that clients are allowed to submit messages from.
      </p>

      {#if actionError}
        <div class="error-message">{actionError}</div>
      {/if}

      <div class="form-group">
        <label for="channel-name">Channel Name *</label>
        <input
          id="channel-name"
          type="text"
          bind:value={newChannelName}
          placeholder="e.g. #trade, #arktrade"
        />
      </div>

      <div class="form-group">
        <label for="channel-planet">Planet</label>
        <select id="channel-planet" bind:value={newChannelPlanet}>
          <option value="">Global</option>
          {#each KNOWN_PLANETS as planet}
            <option value={planet}>{planet}</option>
          {/each}
        </select>
      </div>

      <div class="dialog-buttons">
        <button class="btn btn-secondary" onclick={() => showAddChannelDialog = false}>Cancel</button>
        <button class="btn btn-primary" onclick={handleAddChannel} disabled={actionLoading}>
          {actionLoading ? 'Adding...' : 'Add Channel'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .ingestion-page {
    max-width: 1400px;
    padding: 0 0 2rem;
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

  h1 {
    margin: 0 0 4px;
  }

  .subtitle {
    color: var(--text-muted);
    margin: 0 0 24px;
    font-size: 14px;
  }

  /* Stats Grid */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }

  .stat-card {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
  }

  .stat-card h3 {
    margin: 0 0 8px;
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 500;
  }

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    margin: 0;
  }

  .stat-inline-detail {
    font-size: 14px;
    font-weight: 400;
    color: var(--text-muted);
  }

  .stat-pending { color: var(--warning-color); }
  .stat-denied { color: var(--error-color); }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 16px;
  }

  .tab {
    padding: 10px 20px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
  }

  .tab:hover {
    color: var(--text-color);
  }

  .tab.active {
    color: var(--accent-color);
    border-bottom-color: var(--accent-color);
  }

  /* Section */
  .section {
    min-height: 200px;
  }

  .empty-state {
    color: var(--text-muted);
    text-align: center;
    padding: 40px 0;
    font-size: 14px;
  }

  .alert-period-filter {
    display: flex;
    gap: 4px;
    margin-bottom: 12px;
  }
  .period-btn {
    padding: 4px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background: var(--secondary-color);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.8rem;
  }
  .period-btn.active {
    background: var(--accent-color);
    color: #fff;
    border-color: var(--accent-color);
  }

  /* Alert Cards */
  .alert-card {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .alert-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .alert-type {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    text-transform: capitalize;
  }

  .badge-danger {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error-color);
  }

  .badge-warning {
    background-color: rgba(232, 168, 56, 0.2);
    color: var(--warning-color);
  }

  .alert-date {
    font-size: 12px;
    color: var(--text-muted);
  }

  .alert-body p {
    margin: 4px 0;
    font-size: 14px;
  }

  .alert-details {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 16px;
    margin-top: 8px;
    font-size: 13px;
    color: var(--text-muted);
  }

  .alert-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
  }

  /* Data Table */
  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }

  .data-table th {
    text-align: left;
    padding: 10px 12px;
    border-bottom: 2px solid var(--border-color);
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .data-table td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border-color);
  }

  .data-table tr:hover {
    background-color: var(--hover-color);
  }

  .data-table a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .data-table a:hover {
    text-decoration: underline;
  }

  .hash-cell {
    font-family: monospace;
    font-size: 12px;
    color: var(--text-muted);
  }

  .actions-cell {
    display: flex;
    gap: 6px;
    flex-wrap: nowrap;
  }

  /* Status Badges */
  .status-badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
  }

  .status-banned {
    background-color: rgba(239, 68, 68, 0.2);
    color: var(--error-color);
  }

  .status-active {
    background-color: rgba(34, 197, 94, 0.2);
    color: var(--success-color);
  }

  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    background-color: var(--hover-color);
    color: var(--text-color);
  }

  /* Buttons */
  .btn {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
  }

  .btn-small {
    padding: 4px 10px;
    font-size: 12px;
    border-radius: 4px;
  }

  .btn-secondary {
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }

  .btn-danger {
    background-color: var(--error-color);
    color: white;
  }

  .btn-warning {
    background-color: var(--warning-color);
    color: white;
  }

  .btn-success {
    background-color: var(--success-color);
    color: white;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  /* Dialogs */
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
    padding: 24px;
    border-radius: 8px;
    max-width: 450px;
    width: 90%;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  }

  .dialog h3 {
    margin: 0 0 8px;
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-group label {
    display: block;
    margin-bottom: 6px;
    font-size: 13px;
    font-weight: 500;
  }

  .form-group textarea {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-color);
    font-size: 14px;
    box-sizing: border-box;
    min-height: 80px;
    resize: vertical;
    font-family: inherit;
  }

  .dialog-buttons {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 20px;
  }

  .error-message {
    background-color: rgba(239, 68, 68, 0.1);
    color: var(--error-color);
    padding: 10px 12px;
    border-radius: 4px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  /* Section Header */
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 16px;
    gap: 16px;
  }

  .section-description {
    color: var(--text-muted);
    font-size: 13px;
    margin: 0;
  }

  .btn-primary {
    background-color: var(--accent-color);
    color: white;
    white-space: nowrap;
  }

  .notes-cell {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-muted);
    font-size: 13px;
  }

  /* Add Application Dialog */
  .dialog-wide {
    max-width: 520px;
  }

  .form-group input[type="text"],
  .form-group select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-color);
    font-size: 14px;
    box-sizing: border-box;
    font-family: inherit;
  }

  .form-group select option {
    background-color: var(--secondary-color);
    color: var(--text-color);
  }

  .search-status {
    color: var(--text-muted);
    font-size: 13px;
    margin: 8px 0;
  }

  .search-results {
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: 4px;
  }

  .search-result-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid var(--border-color);
    background: none;
    color: var(--text-color);
    cursor: pointer;
    font-size: 14px;
    text-align: left;
    font-family: inherit;
  }

  .search-result-item:last-child {
    border-bottom: none;
  }

  .search-result-item:hover {
    background-color: var(--hover-color);
  }

  .search-result-item:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .search-result-name {
    font-weight: 500;
  }

  .search-result-eu {
    color: var(--text-muted);
    font-size: 12px;
    margin-top: 2px;
  }

  /* Pagination */
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-top: 16px;
    padding: 8px 0;
  }

  .pagination-info {
    font-size: 13px;
    color: var(--text-muted);
  }

  .loading-fade {
    opacity: 0.5;
    pointer-events: none;
  }

  @media (max-width: 768px) {
    .stats-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .data-table {
      font-size: 12px;
    }

    .data-table th, .data-table td {
      padding: 8px 6px;
    }

    .actions-cell {
      flex-direction: column;
    }
  }
</style>
