<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import RichTextEditor from '$lib/components/wiki/RichTextEditor.svelte';
  import { encodeURIComponentSafe } from '$lib/util';
  import { sanitizeHtml } from '$lib/sanitize';

  export let data;

  let society = data.societyData.society;
  let members = data.societyData.members || [];
  let isLeader = data.societyData.isLeader;
  let pendingCount = data.societyData.pendingCount || 0;

  let showPendingDialog = false;
  let pendingTableKey = 0;
  let pendingError = '';
  let pendingStatus = '';
  let pendingActionBusy = false;
  let disbandError = '';
  let disbandStatus = '';
  let isDisbanding = false;
  let showDisbandDialog = false;
  let disbandStep = 1;
  let isMember = data.societyData.isMember;
  let isEditingDescription = false;
  let descriptionDraft = society.description || '';
  let discordDraft = society.discord_code || '';
  let discordPublicDraft = society.discord_public || false;
  let descriptionError = '';
  let descriptionStatus = '';
  let isSavingDescription = false;

  $: leader = members.find(member => String(member.id) === String(society.leader_id));

  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function getDiscordLabel(member) {
    if (!member) return '';
    if (member.discriminator && Number(member.discriminator) !== 0) {
      return `${member.username}#${member.discriminator}`;
    }
    return member.global_name || member.username || '';
  }

  function getMemberDisplay(member) {
    return member.eu_name || member.global_name || member.username || member.user_id || member.id;
  }

  function getProfileUrl(member) {
    return `/users/${encodeURIComponentSafe(String(member.eu_name || member.id))}`;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString();
  }

  const pendingColumns = [
    {
      key: 'user',
      header: 'User',
      sortable: false,
      searchable: false,
      width: '280px',
      formatter: (_, row) => {
        const displayName = escapeHtml(getMemberDisplay(row));
        const discordLabel = escapeHtml(getDiscordLabel(row));
        const sub = discordLabel && displayName !== discordLabel
          ? `<div class="pending-sub">${discordLabel}</div>`
          : '';
        return `
          <div class="pending-user">
            <div class="pending-name">${displayName}</div>
            ${sub}
          </div>
        `;
      }
    },
    {
      key: 'created_at',
      header: 'Requested',
      sortable: false,
      searchable: false,
      width: '180px',
      formatter: (value) => formatDate(value)
    },
    {
      key: 'actions',
      header: 'Actions',
      sortable: false,
      searchable: false,
      width: '200px',
      formatter: (_, row) => `
        <div class="pending-actions">
          <button class="pending-btn approve" data-action="approve" data-id="${row.id}">Approve</button>
          <button class="pending-btn reject" data-action="reject" data-id="${row.id}">Reject</button>
        </div>
      `
    }
  ];

  async function fetchPendingRequests(offset, limit) {
    const page = Math.floor(offset / limit) + 1;
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('pageSize', String(limit));
    params.set('status', 'pending');

    const response = await fetch(`/api/societies/${society.id}/requests?${params}`);
    if (!response.ok) throw new Error('Failed to load requests');

    const payload = await response.json();
    return {
      rows: payload.rows || [],
      total: payload.total || payload.rows?.length || 0
    };
  }

  async function handlePendingAction(requestId, action) {
    pendingError = '';
    pendingStatus = '';
    pendingActionBusy = true;
    try {
      const response = await fetch(`/api/societies/requests/${requestId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Failed to update request.');
      }
      pendingStatus = action === 'approve' ? 'Request approved.' : 'Request rejected.';
      pendingTableKey += 1;
      await refreshSocietyData();
    } catch (err) {
      pendingError = err.message || 'Failed to update request.';
    } finally {
      pendingActionBusy = false;
    }
  }

  function handlePendingTableClick(event) {
    const target = event.target?.closest?.('button[data-action]');
    if (!target) return;
    event.preventDefault();
    event.stopPropagation();
    if (pendingActionBusy) return;
    const requestId = Number(target.dataset.id);
    const action = String(target.dataset.action);
    if (!Number.isFinite(requestId)) return;
    handlePendingAction(requestId, action);
  }

  async function refreshSocietyData() {
    try {
      const response = await fetch(`/api/societies/${society.id}`);
      if (!response.ok) return;
      const payload = await response.json();
      society = payload.society;
      members = payload.members || [];
      isLeader = payload.isLeader;
      isMember = payload.isMember;
      pendingCount = payload.pendingCount || 0;
    } catch (err) {
      console.error('Failed to refresh society data:', err);
    }
  }

  function openPendingDialog() {
    pendingError = '';
    pendingStatus = '';
    showPendingDialog = true;
    pendingTableKey += 1;
  }

  function startEditingDescription() {
    descriptionDraft = society.description || '';
    discordDraft = society.discord_code || '';
    discordPublicDraft = society.discord_public || false;
    descriptionError = '';
    descriptionStatus = '';
    isEditingDescription = true;
  }

  function cancelEditingDescription() {
    descriptionDraft = society.description || '';
    discordDraft = society.discord_code || '';
    discordPublicDraft = society.discord_public || false;
    descriptionError = '';
    descriptionStatus = '';
    isEditingDescription = false;
  }

  async function saveDescription() {
    if (!isLeader || isSavingDescription) return;
    descriptionError = '';
    descriptionStatus = '';
    isSavingDescription = true;
    try {
      const response = await fetch(`/api/societies/${society.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: descriptionDraft, discord: discordDraft, discordPublic: discordPublicDraft })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Failed to update society.');
      }
      society = payload.society || society;
      descriptionStatus = 'Society updated.';
      isEditingDescription = false;
    } catch (err) {
      descriptionError = err.message || 'Failed to update description.';
    } finally {
      isSavingDescription = false;
    }
  }

  async function handleDisband() {
    if (!isLeader || isDisbanding) return;
    disbandError = '';
    disbandStatus = '';
    isDisbanding = true;
    try {
      const response = await fetch(`/api/societies/${society.id}/disband`, { method: 'POST' });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error || 'Failed to disband society.');
      }
      disbandStatus = 'Society disbanded.';
      window.location.href = '/';
    } catch (err) {
      disbandError = err.message || 'Failed to disband society.';
    } finally {
      isDisbanding = false;
    }
  }

  function openDisbandDialog() {
    if (!isLeader) return;
    disbandError = '';
    disbandStatus = '';
    disbandStep = 1;
    showDisbandDialog = true;
  }

  function closeDisbandDialog() {
    if (isDisbanding) return;
    showDisbandDialog = false;
    disbandStep = 1;
  }

  function advanceDisbandStep() {
    if (disbandStep < 2) {
      disbandStep = 2;
    }
  }
</script>

<svelte:head>
  <title>{society?.name || 'Society'} | Society | Entropia Nexus</title>
  <meta name="description" content="Society profile for {society?.name || 'a society'} on Entropia Nexus." />
</svelte:head>

<div class="society-page">
  <div class="society-header">
    <div class="society-title">
      <h1>{society.name}{society.abbreviation ? ` (${society.abbreviation})` : ''}</h1>
      <div class="society-meta">
        <div class="society-meta-item">
          <span class="meta-label">Leader</span>
          <span class="meta-value">{leader ? getMemberDisplay(leader) : society.leader_id}</span>
        </div>
        <div class="society-meta-item">
          <span class="meta-label">Members</span>
          <span class="meta-value">{members.length}</span>
        </div>
        <div class="society-meta-item">
          <span class="meta-label">Discord</span>
          {#if society.discord_code}
            <a class="meta-link" href={`https://discord.gg/${society.discord_code}`} target="_blank" rel="noreferrer">
              discord.gg/{society.discord_code}
            </a>
          {:else if isMember}
            <span class="meta-value">-</span>
          {:else}
            <span class="meta-value meta-muted">Members only</span>
          {/if}
        </div>
      </div>
      {#if isEditingDescription}
        <div class="society-edit-fields">
          <label class="society-edit-label">Discord</label>
          <input
            type="text"
            class="society-edit-input"
            bind:value={discordDraft}
            placeholder="Invite link or code"
          />
          <label class="society-edit-checkbox">
            <input type="checkbox" bind:checked={discordPublicDraft} />
            Public — visible to everyone (otherwise members only)
          </label>
          {#if descriptionError}
            <div class="dialog-error">{descriptionError}</div>
          {:else if descriptionStatus}
            <div class="success-text">{descriptionStatus}</div>
          {/if}
        </div>
      {/if}
    </div>
    {#if isLeader}
      <div class="society-actions">
        {#if !isEditingDescription}
          <button class="secondary edit-btn" on:click={startEditingDescription}>Edit</button>
        {:else}
          <button class="secondary" on:click={cancelEditingDescription} disabled={isSavingDescription}>Cancel</button>
          <button class="primary" on:click={saveDescription} disabled={isSavingDescription}>
            {isSavingDescription ? 'Saving...' : 'Save'}
          </button>
        {/if}
        <button class="primary" on:click={openPendingDialog}>
          Pending Invites{pendingCount ? ` (${pendingCount})` : ''}
        </button>
        <button class="danger" on:click={openDisbandDialog} disabled={isDisbanding}>
          Disband
        </button>
      </div>
    {/if}
  </div>

  <div class="society-grid">
    <div class="card">
      <div class="card-header">Description</div>
      <div class="card-body">
        {#if isEditingDescription}
          <RichTextEditor bind:content={descriptionDraft} placeholder="Society description" />
        {:else if society.description}
          <div class="society-description">{@html sanitizeHtml(society.description)}</div>
        {:else}
          <div class="empty-state">No description yet.</div>
        {/if}
      </div>
    </div>

    <div class="card">
      <div class="card-header">Members</div>
      <div class="card-body">
        {#if members.length === 0}
          <div class="empty-state">No members listed yet.</div>
        {:else}
          <div class="member-list">
            {#each members as member}
              <a class="member-row" href={getProfileUrl(member)}>
                <div class="member-main">
                  <div class="member-name">{getMemberDisplay(member)}</div>
                  {#if member.eu_name && getDiscordLabel(member)}
                    <div class="member-sub">{getDiscordLabel(member)}</div>
                  {/if}
                </div>
                {#if String(member.id) === String(society.leader_id)}
                  <span class="member-badge">Leader</span>
                {/if}
              </a>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

{#if showPendingDialog}
  <div class="dialog-backdrop" on:click={() => (showPendingDialog = false)} on:keydown={(e) => e.key === 'Escape' && (showPendingDialog = false)}>
    <div class="dialog dialog-wide" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="pending-invites-title">
      <div class="dialog-header">
        <h3 id="pending-invites-title">Pending Society Invites</h3>
        <button class="close-btn" on:click={() => (showPendingDialog = false)} aria-label="Close dialog">&#10005;</button>
      </div>
      <div class="dialog-body">
        {#if pendingError}
          <div class="dialog-error">{pendingError}</div>
        {:else if pendingStatus}
          <div class="success-text">{pendingStatus}</div>
        {/if}
        <div class="pending-table">
          {#key pendingTableKey}
            <FancyTable
              columns={pendingColumns}
              fetchData={fetchPendingRequests}
              rowHeight={52}
              pageSize={20}
              sortable={false}
              searchable={false}
              emptyMessage="No pending requests"
              on:click={handlePendingTableClick}
            />
          {/key}
        </div>
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" on:click={() => (showPendingDialog = false)}>Close</button>
      </div>
    </div>
  </div>
{/if}

{#if showDisbandDialog}
  <div class="dialog-backdrop" on:click={closeDisbandDialog} on:keydown={(e) => e.key === 'Escape' && closeDisbandDialog()}>
    <div class="dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-labelledby="disband-title">
      <div class="dialog-header">
        <h3 id="disband-title">Disband Society</h3>
        <button class="close-btn" on:click={closeDisbandDialog} aria-label="Close dialog">&#10005;</button>
      </div>
      <div class="dialog-body">
        {#if disbandError}
          <div class="dialog-error">{disbandError}</div>
        {:else if disbandStatus}
          <div class="success-text">{disbandStatus}</div>
        {/if}
        {#if disbandStep === 1}
          <p class="dialog-warning">
            Disband this society? All members will be removed and pending invites declined.
          </p>
        {:else}
          <p class="dialog-warning">
            This cannot be undone. Are you absolutely sure?
          </p>
        {/if}
      </div>
      <div class="dialog-footer">
        <button class="dialog-btn secondary" on:click={closeDisbandDialog} disabled={isDisbanding}>Cancel</button>
        {#if disbandStep === 1}
          <button class="dialog-btn danger" on:click={advanceDisbandStep} disabled={isDisbanding}>Continue</button>
        {:else}
          <button class="dialog-btn danger" on:click={handleDisband} disabled={isDisbanding}>
            {isDisbanding ? 'Disbanding...' : 'Disband Society'}
          </button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .society-page {
    max-width: 1100px;
    margin: 0 auto;
    padding: 24px 20px 60px;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  .society-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #444);
    border-radius: 16px;
    padding: 20px;
  }

  .society-title h1 {
    margin: 0;
    font-size: 26px;
  }

  .society-meta {
    margin-top: 8px;
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }

  .society-meta-item {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 140px;
  }

  .meta-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--text-muted, #999);
  }

  .meta-value {
    font-size: 14px;
  }

  .meta-link {
    font-size: 14px;
    color: var(--accent-color);
    text-decoration: none;
  }

  .meta-link:hover {
    text-decoration: underline;
  }

  .society-edit-fields {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-width: 360px;
  }

  .society-edit-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted, #999);
  }

  .society-edit-input {
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #444);
    background: var(--bg-color, #111);
    color: var(--text-color);
  }

  .society-edit-checkbox {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-muted, #999);
    cursor: pointer;
  }

  .society-edit-checkbox input[type="checkbox"] {
    cursor: pointer;
  }

  .meta-muted {
    font-style: italic;
    color: var(--text-muted, #999);
  }

  .society-description {
    font-size: 14px;
    color: var(--text-muted, #999);
  }

  .society-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .society-actions button {
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #444);
    cursor: pointer;
    background: var(--bg-color, #111);
    color: var(--text-color);
  }

  .society-actions .primary {
    background: var(--accent-color, #4a9eff);
    border-color: transparent;
    color: #fff;
  }

  .society-actions .secondary {
    background: var(--hover-color);
    border-color: var(--border-color, #444);
  }

  .society-actions .edit-btn {
    font-weight: 600;
    padding: 8px 16px;
    border-color: var(--accent-color, #4a9eff);
  }

  .society-actions .danger {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.5);
    color: var(--error-color);
  }

  .society-actions .danger:hover {
    background: rgba(239, 68, 68, 0.3);
  }

  .society-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 24px;
  }

  .card {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #444);
    border-radius: 16px;
    overflow: hidden;
  }

  .card-header {
    padding: 12px 16px;
    background: var(--hover-color);
    border-bottom: 1px solid var(--border-color, #444);
    font-weight: 600;
  }

  .card-body {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .member-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .member-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border: 1px solid var(--border-color, #444);
    border-radius: 10px;
    background: var(--bg-color, #111);
    color: var(--text-color);
    text-decoration: none;
  }

  .member-row:hover {
    background: var(--hover-color);
  }

  .member-name {
    font-weight: 600;
  }

  .member-sub {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  .member-badge {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    background-color: rgba(59, 130, 246, 0.2);
    color: var(--accent-color);
  }

  .empty-state {
    color: var(--text-muted, #999);
    font-size: 13px;
  }

  .dialog-backdrop {
    position: fixed;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 90;
    padding: 20px;
  }

  .dialog {
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 12px;
    width: min(900px, 94vw);
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  }

  .dialog-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color, #555);
  }

  .dialog-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: var(--text-color);
  }

  .close-btn {
    background: none;
    border: none;
    padding: 4px;
    cursor: pointer;
    color: var(--text-muted, #999);
    border-radius: 4px;
  }

  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px 18px;
    font-size: 13px;
    color: var(--text-color);
    flex: 1;
    min-height: 0;
    overflow: auto;
  }

  .dialog-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 12px 18px 16px;
    border-top: 1px solid var(--border-color, #555);
  }

  .dialog-btn {
    padding: 8px 14px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #555);
    background: var(--accent-color, #4a9eff);
    color: #fff;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
  }

  .dialog-btn.secondary {
    background: transparent;
    color: var(--text-color);
  }

  .dialog-btn.danger {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.5);
    color: var(--error-color);
  }

  .dialog-error {
    color: #ff6b6b;
    font-size: 12px;
  }

  .success-text {
    color: #4ade80;
    font-size: 12px;
  }

  .dialog-warning {
    margin: 0;
    font-size: 14px;
    color: var(--text-color);
  }

  .pending-table {
    min-height: 360px;
    height: 50vh;
  }

  :global(.pending-actions) {
    display: flex;
    gap: 8px;
  }

  :global(.pending-btn) {
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid var(--border-color, #444);
    background: var(--bg-color, #111);
    color: var(--text-color);
    font-size: 12px;
    cursor: pointer;
  }

  :global(.pending-btn.approve) {
    background: rgba(16, 185, 129, 0.2);
    border-color: rgba(16, 185, 129, 0.5);
    color: var(--success-color);
  }

  :global(.pending-btn.reject) {
    background: rgba(239, 68, 68, 0.2);
    border-color: rgba(239, 68, 68, 0.5);
    color: var(--error-color);
  }

  :global(.pending-user) {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  :global(.pending-name) {
    font-weight: 600;
  }

  :global(.pending-sub) {
    font-size: 12px;
    color: var(--text-muted, #999);
  }

  @media (max-width: 720px) {
    .society-header {
      flex-direction: column;
    }

    .society-actions {
      width: 100%;
    }

    .society-actions button {
      width: 100%;
    }

    .society-page {
      padding: 18px 14px 40px;
    }

    .society-title h1 {
      font-size: 22px;
    }

    .society-meta {
      gap: 12px;
    }

    .society-meta-item {
      min-width: 120px;
    }

    .society-grid {
      grid-template-columns: 1fr;
      gap: 16px;
    }

    .member-row {
      align-items: flex-start;
      gap: 8px;
    }

    .member-badge {
      align-self: flex-start;
    }

    .pending-table {
      min-height: 240px;
      height: 45vh;
    }
  }

  @media (max-width: 480px) {
    .society-header {
      padding: 16px;
    }

    .card-body {
      padding: 14px;
    }

    .society-actions {
      gap: 8px;
    }

    .society-actions button {
      width: 100%;
    }

    .society-edit-fields {
      max-width: 100%;
    }

    .dialog {
      width: min(100%, 92vw);
    }

    .dialog-body {
      padding: 12px 14px;
    }

    .dialog-footer {
      padding: 10px 14px 14px;
      flex-direction: column;
      align-items: stretch;
    }

    .society-meta {
      flex-direction: column;
      align-items: flex-start;
    }

    .society-meta-item {
      width: 100%;
    }
  }
</style>
