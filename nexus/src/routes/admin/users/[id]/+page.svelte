<script>
  // @ts-nocheck
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { encodeURIComponentSafe } from '$lib/util';

  let user = null;
  let metrics = null;
  let actions = null;
  let isLoading = true;
  let error = null;

  // Dialog states
  let showLockDialog = false;
  let showBanDialog = false;
  let lockReason = '';
  let banReason = '';
  let banDuration = '';
  let isSubmitting = false;
  let actionError = '';

  // Roles & grants state
  let userRoles = [];
  let userGrants = [];
  let allRoles = [];
  let allGrants = [];
  let rolesLoading = false;
  let rolesError = '';
  let selectedRoleToAdd = '';

  $: userId = $page.params.id;
  $: availableRoles = allRoles.filter(r => !userRoles.some(ur => ur.role_id === r.id));

  onMount(() => {
    loadUser();
    loadRolesAndGrants();
  });

  async function loadUser() {
    isLoading = true;
    error = null;

    try {
      const response = await fetch(`/api/admin/users/${userId}?includeMetrics=true&includeActions=true`);
      if (!response.ok) {
        if (response.status === 404) throw new Error('User not found');
        throw new Error('Failed to load user');
      }

      const data = await response.json();
      user = data.user;
      metrics = data.metrics;
      actions = data.actions;
    } catch (err) {
      error = err.message;
    } finally {
      isLoading = false;
    }
  }

  async function performAction(action, body = {}) {
    isSubmitting = true;
    actionError = '';

    try {
      const response = await fetch(`/api/admin/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...body })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Action failed');
      }

      // Update local state
      user = data.user;

      // Close dialogs
      showLockDialog = false;
      showBanDialog = false;
      lockReason = '';
      banReason = '';
      banDuration = '';

      // Reload to get updated actions
      await loadUser();
    } catch (err) {
      actionError = err.message;
    } finally {
      isSubmitting = false;
    }
  }

  function handleLock() {
    if (!lockReason.trim()) {
      actionError = 'Reason is required';
      return;
    }
    performAction('lock', { reason: lockReason.trim() });
  }

  function handleBan() {
    if (!banReason.trim()) {
      actionError = 'Reason is required';
      return;
    }
    const durationDays = banDuration ? parseInt(banDuration) : null;
    performAction('ban', { reason: banReason.trim(), durationDays });
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  }

  function getActionLabel(action) {
    switch (action) {
      case 'lock': return 'Locked user';
      case 'unlock': return 'Unlocked user';
      case 'ban': return 'Banned user';
      case 'unban': return 'Unbanned user';
      case 'approve_change': return 'Approved change';
      case 'deny_change': return 'Denied change';
      default: return action;
    }
  }

  function getPublicProfileUrl() {
    if (!user) return null;
    const identifier = user.eu_name || user.id;
    return `/users/${encodeURIComponentSafe(String(identifier))}`;
  }

  async function loadRolesAndGrants() {
    rolesLoading = true;
    rolesError = '';
    try {
      const [rolesRes, grantsRes, allRolesRes, allGrantsRes] = await Promise.all([
        fetch(`/api/admin/users/${userId}/roles`),
        fetch(`/api/admin/users/${userId}/grants`),
        fetch('/api/admin/roles'),
        fetch('/api/admin/grants')
      ]);
      if (rolesRes.ok) userRoles = await rolesRes.json();
      if (grantsRes.ok) userGrants = await grantsRes.json();
      if (allRolesRes.ok) allRoles = await allRolesRes.json();
      if (allGrantsRes.ok) allGrants = await allGrantsRes.json();
    } catch (e) {
      rolesError = 'Failed to load roles/grants';
    } finally {
      rolesLoading = false;
    }
  }

  async function addRole() {
    if (!selectedRoleToAdd) return;
    rolesError = '';
    const updatedRoles = [...userRoles.map(ur => ur.role_id), parseInt(selectedRoleToAdd)];
    try {
      const res = await fetch(`/api/admin/users/${userId}/roles`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roleIds: updatedRoles })
      });
      if (res.ok) {
        userRoles = await res.json();
        selectedRoleToAdd = '';
      } else {
        rolesError = (await res.json()).error || 'Failed to add role';
      }
    } catch (e) {
      rolesError = 'Network error';
    }
  }

  async function removeRole(roleId) {
    rolesError = '';
    const updatedRoles = userRoles.filter(ur => ur.role_id !== roleId).map(ur => ur.role_id);
    try {
      const res = await fetch(`/api/admin/users/${userId}/roles`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roleIds: updatedRoles })
      });
      if (res.ok) {
        userRoles = await res.json();
      } else {
        rolesError = (await res.json()).error || 'Failed to remove role';
      }
    } catch (e) {
      rolesError = 'Network error';
    }
  }

  async function toggleGrantOverride(grantKey, currentState) {
    rolesError = '';
    // Cycle: none -> granted -> denied -> none
    let newGrants = [...userGrants];
    const existing = newGrants.find(g => g.key === grantKey);

    if (!existing) {
      // Add as granted
      newGrants.push({ key: grantKey, granted: true });
    } else if (existing.granted) {
      // Change to denied
      existing.granted = false;
    } else {
      // Remove override
      newGrants = newGrants.filter(g => g.key !== grantKey);
    }

    try {
      const res = await fetch(`/api/admin/users/${userId}/grants`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ grants: newGrants.map(g => ({ key: g.key, granted: g.granted })) })
      });
      if (res.ok) {
        userGrants = await res.json();
      } else {
        rolesError = (await res.json()).error || 'Failed to update grant';
      }
    } catch (e) {
      rolesError = 'Network error';
    }
  }

  function getGrantOverrideState(grantKey) {
    const override = userGrants.find(g => g.key === grantKey);
    if (!override) return 'inherit';
    return override.granted ? 'granted' : 'denied';
  }

  function getRoleName(roleId) {
    const role = allRoles.find(r => r.id === roleId);
    return role?.name || `Role #${roleId}`;
  }
</script>

<svelte:head>
  <title>{user?.eu_name || user?.global_name || 'User'} | Admin | Entropia Nexus</title>
</svelte:head>

<style>
  .user-detail {
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

  .user-info {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .user-avatar {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    object-fit: cover;
  }

  .user-name h1 {
    margin: 0 0 4px 0;
    font-size: 24px;
    color: var(--text-color);
  }

  .user-name .username {
    color: var(--text-muted);
    font-size: 14px;
  }

  .header-badges {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  .badge {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
  }

  .badge-banned { background-color: rgba(239, 68, 68, 0.2); color: var(--error-color); }
  .badge-locked { background-color: rgba(245, 158, 11, 0.2); color: var(--warning-color); }
  .badge-admin { background-color: rgba(139, 92, 246, 0.2); color: #8b5cf6; }
  .badge-verified { background-color: rgba(16, 185, 129, 0.2); color: var(--success-color); }
  .badge-unverified { background-color: var(--hover-color); color: var(--text-muted); }

  .action-buttons {
    display: flex;
    gap: 8px;
  }

  .btn {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    border: none;
    transition: all 0.15s ease;
  }

  .btn-danger {
    background-color: var(--error-color);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-warning {
    background-color: var(--warning-color);
    color: white;
  }

  .btn-warning:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-success {
    background-color: var(--success-color);
    color: white;
  }

  .btn-success:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .btn-secondary {
    background-color: var(--hover-color);
    color: var(--text-color);
    border: 1px solid var(--border-color);
  }

  .btn-secondary:hover:not(:disabled) {
    background-color: var(--accent-color);
    color: white;
    border-color: var(--accent-color);
  }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .content-grid {
    display: grid;
    grid-template-columns: 1fr 350px;
    gap: 24px;
  }

  .main-content {
    display: flex;
    flex-direction: column;
    gap: 24px;
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
  }

  .card-body {
    padding: 16px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 16px;
  }

  .stat-item {
    text-align: center;
  }

  .stat-value {
    font-size: 28px;
    font-weight: bold;
    color: var(--text-color);
  }

  .stat-label {
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .info-row {
    display: flex;
    justify-content: space-between;
    padding: 10px 0;
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

  .changes-list {
    font-size: 13px;
  }

  .change-item {
    padding: 10px 0;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .change-item:last-child {
    border-bottom: none;
  }

  .change-name {
    font-weight: 500;
    color: var(--text-color);
  }

  .change-meta {
    font-size: 12px;
    color: var(--text-muted);
  }

  .action-item {
    padding: 10px 0;
    border-bottom: 1px solid var(--border-color);
    font-size: 13px;
  }

  .action-item:last-child {
    border-bottom: none;
  }

  .action-type {
    font-weight: 500;
    color: var(--text-color);
  }

  .action-meta {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  .action-reason {
    font-size: 12px;
    color: var(--text-muted);
    font-style: italic;
    margin-top: 4px;
  }

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
    margin: 0 0 16px 0;
    color: var(--text-color);
  }

  .form-group {
    margin-bottom: 16px;
  }

  .form-group label {
    display: block;
    margin-bottom: 6px;
    font-size: 14px;
    color: var(--text-color);
  }

  .form-group input,
  .form-group textarea,
  .form-group select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-color);
    font-size: 14px;
    box-sizing: border-box;
  }

  .form-group textarea {
    min-height: 80px;
    resize: vertical;
  }

  .dialog-buttons {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 20px;
  }

  .error-message {
    background-color: var(--error-bg);
    color: var(--error-color);
    padding: 10px 12px;
    border-radius: 4px;
    margin-bottom: 16px;
    font-size: 14px;
  }

  .status-alert {
    padding: 16px;
    border-radius: 6px;
    margin-bottom: 16px;
  }

  .status-alert.banned {
    background-color: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error-color);
  }

  .status-alert.locked {
    background-color: rgba(245, 158, 11, 0.1);
    border: 1px solid var(--warning-color);
  }

  .status-alert h4 {
    margin: 0 0 8px 0;
    font-size: 14px;
  }

  .status-alert.banned h4 {
    color: var(--error-color);
  }

  .status-alert.locked h4 {
    color: var(--warning-color);
  }

  .status-alert p {
    margin: 4px 0;
    font-size: 13px;
    color: var(--text-color);
  }

  .loading, .error {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
  }

  .error {
    color: var(--error-color);
  }

  /* Roles & Grants */
  .role-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
  }

  .role-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background-color: rgba(139, 92, 246, 0.15);
    color: #8b5cf6;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
  }

  .role-remove {
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: 0 2px;
    font-size: 14px;
    line-height: 1;
    opacity: 0.6;
    transition: opacity 0.15s;
  }

  .role-remove:hover {
    opacity: 1;
  }

  .add-role-row {
    display: flex;
    gap: 8px;
    margin-top: 8px;
  }

  .role-select {
    flex: 1;
    padding: 6px 8px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    background-color: var(--bg-color);
    color: var(--text-color);
    font-size: 12px;
  }

  .grants-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .grant-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 8px;
    border: none;
    background: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: background-color 0.1s;
    text-align: left;
    width: 100%;
  }

  .grant-row:hover {
    background-color: var(--hover-color);
  }

  .grant-row.grant-granted {
    background-color: rgba(16, 185, 129, 0.08);
  }

  .grant-row.grant-denied {
    background-color: rgba(239, 68, 68, 0.08);
  }

  .grant-key {
    color: var(--text-color);
    font-family: monospace;
  }

  .grant-state {
    color: var(--text-muted);
    font-size: 11px;
  }

  .grant-state.granted {
    color: var(--success-color);
    font-weight: 500;
  }

  .grant-state.denied {
    color: var(--error-color);
    font-weight: 500;
  }

  /* Mobile responsive */
  @media (max-width: 768px) {
    .page-header {
      flex-direction: column;
      gap: 16px;
    }

    .user-info {
      gap: 12px;
    }

    .user-avatar {
      width: 48px;
      height: 48px;
    }

    .user-name h1 {
      font-size: 18px;
    }

    .action-buttons {
      flex-wrap: wrap;
      width: 100%;
    }

    .action-buttons .btn {
      flex: 1;
      min-width: 120px;
      text-align: center;
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

    .stat-value {
      font-size: 22px;
    }

    .change-item {
      flex-direction: column;
      align-items: flex-start;
      gap: 4px;
    }

    .dialog {
      padding: 16px;
      width: 95%;
    }

    .dialog-buttons {
      flex-direction: column;
    }

    .dialog-buttons .btn {
      width: 100%;
    }
  }
</style>

<div class="user-detail">
  <div class="breadcrumb">
    <a href="/admin">Admin</a>
    <span>/</span>
    <a href="/admin/users">Users</a>
    <span>/</span>
    <span>{user?.eu_name || user?.global_name || userId}</span>
  </div>

  {#if isLoading}
    <div class="loading">Loading user details...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else if user}
    <div class="page-header">
      <div class="user-info">
        <img
          src={user.avatar ? `https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png` : `https://cdn.discordapp.com/embed/avatars/${Number(BigInt(user.id) % 5n)}.png`}
          alt=""
          class="user-avatar"
        />
        <div class="user-name">
          <h1>{user.global_name || user.username}</h1>
          <div class="username">@{user.username} &bull; ID: {user.id}</div>
          <div class="header-badges">
            {#if user.banned}
              <span class="badge badge-banned">Banned</span>
            {/if}
            {#if user.locked}
              <span class="badge badge-locked">Locked</span>
            {/if}
            {#each userRoles as ur}
              <span class="badge badge-admin">{getRoleName(ur.role_id)}</span>
            {/each}
            {#if user.verified}
              <span class="badge badge-verified">Verified</span>
            {:else}
              <span class="badge badge-unverified">Unverified</span>
            {/if}
          </div>
        </div>
      </div>

      <div class="action-buttons">
        <a class="btn btn-secondary" href={getPublicProfileUrl()}>
          View Public Profile
        </a>
        {#if user.banned}
          <button class="btn btn-success" on:click={() => performAction('unban')}>
            Unban User
          </button>
        {:else}
          <button class="btn btn-danger" on:click={() => { showBanDialog = true; actionError = ''; }}>
            Ban User
          </button>
        {/if}

        {#if user.locked}
          <button class="btn btn-success" on:click={() => performAction('unlock')}>
            Unlock User
          </button>
        {:else if !user.banned}
          <button class="btn btn-warning" on:click={() => { showLockDialog = true; actionError = ''; }}>
            Lock User
          </button>
        {/if}
      </div>
    </div>

    {#if user.banned}
      <div class="status-alert banned">
        <h4>User is Banned</h4>
        <p><strong>Reason:</strong> {user.banned_reason || 'No reason provided'}</p>
        <p><strong>Banned at:</strong> {formatDate(user.banned_at)}</p>
        {#if user.banned_until}
          <p><strong>Expires:</strong> {formatDate(user.banned_until)}</p>
        {:else}
          <p><strong>Duration:</strong> Permanent</p>
        {/if}
      </div>
    {/if}

    {#if user.locked && !user.banned}
      <div class="status-alert locked">
        <h4>User is Locked</h4>
        <p><strong>Reason:</strong> {user.locked_reason || 'No reason provided'}</p>
        <p><strong>Locked at:</strong> {formatDate(user.locked_at)}</p>
      </div>
    {/if}

    <div class="content-grid">
      <div class="main-content">
        {#if metrics}
          <div class="card">
            <div class="card-header">Activity Metrics</div>
            <div class="card-body">
              <div class="stats-grid">
                <div class="stat-item">
                  <div class="stat-value">{metrics.changes.total}</div>
                  <div class="stat-label">Total Changes</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value" style="color: var(--success-color)">{metrics.changes.approved}</div>
                  <div class="stat-label">Approved</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value" style="color: var(--warning-color)">{metrics.changes.pending}</div>
                  <div class="stat-label">Pending</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value" style="color: var(--error-color)">{metrics.changes.denied}</div>
                  <div class="stat-label">Denied</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{metrics.services}</div>
                  <div class="stat-label">Services</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{metrics.flightsTaken}</div>
                  <div class="stat-label">Flights Taken</div>
                </div>
              </div>
            </div>
          </div>

          {#if metrics.recentChanges?.length > 0}
            <div class="card">
              <div class="card-header">Recent Changes</div>
              <div class="card-body changes-list">
                {#each metrics.recentChanges as change}
                  <a href="/admin/changes/{change.id}" class="change-item">
                    <div>
                      <div class="change-name">{change.name || 'Unknown'}</div>
                      <div class="change-meta">{change.entity} &bull; {change.type}</div>
                    </div>
                    <span class="badge" class:badge-verified={change.state === 'Approved'} class:badge-locked={change.state === 'Pending'} class:badge-banned={change.state === 'Denied'}>
                      {change.state}
                    </span>
                  </a>
                {/each}
              </div>
            </div>
          {/if}
        {/if}
      </div>

      <div class="sidebar">
        <div class="card">
          <div class="card-header">User Details</div>
          <div class="card-body">
            {#if user.eu_name}
              <div class="info-row">
                <span class="info-label">EU Name</span>
                <span class="info-value">{user.eu_name}</span>
              </div>
            {/if}
            <div class="info-row">
              <span class="info-label">Discord ID</span>
              <span class="info-value" style="font-family: monospace; font-size: 12px;">{user.id}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Verified</span>
              <span class="info-value">{user.verified ? 'Yes' : 'No'}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Roles</span>
              <span class="info-value">
                {#if userRoles.length > 0}
                  {userRoles.map(ur => getRoleName(ur.role_id)).join(', ')}
                {:else}
                  None
                {/if}
              </span>
            </div>
          </div>
        </div>

        <!-- Roles Management -->
        <div class="card">
          <div class="card-header">Assigned Roles</div>
          <div class="card-body">
            {#if rolesError}
              <div class="error-message" style="margin-bottom: 12px;">{rolesError}</div>
            {/if}
            {#if rolesLoading}
              <div style="color: var(--text-muted); font-size: 13px;">Loading...</div>
            {:else}
              {#if userRoles.length > 0}
                <div class="role-tags">
                  {#each userRoles as ur}
                    <span class="role-tag">
                      {getRoleName(ur.role_id)}
                      <button class="role-remove" on:click={() => removeRole(ur.role_id)} title="Remove role">&times;</button>
                    </span>
                  {/each}
                </div>
              {:else}
                <div style="color: var(--text-muted); font-size: 13px; margin-bottom: 8px;">No roles assigned</div>
              {/if}
              {#if availableRoles.length > 0}
                <div class="add-role-row">
                  <select bind:value={selectedRoleToAdd} class="role-select">
                    <option value="">Add role...</option>
                    {#each availableRoles as role}
                      <option value={role.id}>{role.name}</option>
                    {/each}
                  </select>
                  <button class="btn btn-secondary" style="padding: 6px 12px; font-size: 12px;" on:click={addRole} disabled={!selectedRoleToAdd}>Add</button>
                </div>
              {/if}
            {/if}
          </div>
        </div>

        <!-- Grant Overrides -->
        <div class="card">
          <div class="card-header">Grant Overrides</div>
          <div class="card-body">
            <div style="color: var(--text-muted); font-size: 11px; margin-bottom: 10px;">
              Click to cycle: inherit &rarr; granted &rarr; denied &rarr; inherit
            </div>
            {#if allGrants.length > 0}
              <div class="grants-list">
                {#each allGrants as grant}
                  {@const state = getGrantOverrideState(grant.key)}
                  <button
                    class="grant-row"
                    class:grant-granted={state === 'granted'}
                    class:grant-denied={state === 'denied'}
                    on:click={() => toggleGrantOverride(grant.key, state)}
                    title={grant.description || grant.key}
                  >
                    <span class="grant-key">{grant.key}</span>
                    <span class="grant-state" class:granted={state === 'granted'} class:denied={state === 'denied'}>
                      {state === 'inherit' ? '-' : state === 'granted' ? 'Granted' : 'Denied'}
                    </span>
                  </button>
                {/each}
              </div>
            {:else if !rolesLoading}
              <div style="color: var(--text-muted); font-size: 13px;">No grants defined</div>
            {/if}
          </div>
        </div>

        {#if actions?.length > 0}
          <div class="card">
            <div class="card-header">Admin Action History</div>
            <div class="card-body">
              {#each actions as action}
                <div class="action-item">
                  <div class="action-type">{getActionLabel(action.action_type)}</div>
                  <div class="action-meta">
                    by {action.admin_name || 'Unknown'} &bull; {formatDate(action.created_at)}
                  </div>
                  {#if action.reason}
                    <div class="action-reason">"{action.reason}"</div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<!-- Lock Dialog -->
{#if showLockDialog}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="dialog-overlay" on:click={() => showLockDialog = false}>
    <div class="dialog" on:click|stopPropagation>
      <h3>Lock User</h3>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        Locking a user prevents them from using verified-only features. They can still log in and view content.
      </p>

      {#if actionError}
        <div class="error-message">{actionError}</div>
      {/if}

      <div class="form-group">
        <label for="lock-reason">Reason *</label>
        <textarea
          id="lock-reason"
          bind:value={lockReason}
          placeholder="Explain why this user is being locked..."
        ></textarea>
      </div>

      <div class="dialog-buttons">
        <button class="btn btn-secondary" on:click={() => showLockDialog = false} disabled={isSubmitting}>
          Cancel
        </button>
        <button class="btn btn-warning" on:click={handleLock} disabled={isSubmitting}>
          {isSubmitting ? 'Locking...' : 'Lock User'}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Ban Dialog -->
{#if showBanDialog}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="dialog-overlay" on:click={() => showBanDialog = false}>
    <div class="dialog" on:click|stopPropagation>
      <h3>Ban User</h3>
      <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 16px;">
        Banning a user will immediately log them out, prevent future logins, and trigger a Discord server ban.
      </p>

      {#if actionError}
        <div class="error-message">{actionError}</div>
      {/if}

      <div class="form-group">
        <label for="ban-reason">Reason *</label>
        <textarea
          id="ban-reason"
          bind:value={banReason}
          placeholder="Explain why this user is being banned..."
        ></textarea>
      </div>

      <div class="form-group">
        <label for="ban-duration">Duration (days)</label>
        <input
          id="ban-duration"
          type="number"
          bind:value={banDuration}
          placeholder="Leave empty for permanent ban"
          min="1"
        />
      </div>

      <div class="dialog-buttons">
        <button class="btn btn-secondary" on:click={() => showBanDialog = false} disabled={isSubmitting}>
          Cancel
        </button>
        <button class="btn btn-danger" on:click={handleBan} disabled={isSubmitting}>
          {isSubmitting ? 'Banning...' : 'Ban User'}
        </button>
      </div>
    </div>
  </div>
{/if}
