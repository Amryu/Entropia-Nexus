<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';
  import FancyTable from "$lib/components/FancyTable.svelte";
  import DashboardNav from "$lib/components/services/DashboardNav.svelte";
  import RequestStatusBadge from "$lib/components/services/RequestStatusBadge.svelte";
  import SkeletonTable from "$lib/components/SkeletonTable.svelte";
  import SkeletonCard from "$lib/components/SkeletonCard.svelte";
  import { goto } from '$app/navigation';
  import { navigating } from '$app/stores';

  let { data } = $props();

  // Show loading state during navigation
  let isLoading = $derived($navigating !== null);

  let services = $derived(data.services || []);
  let incomingRequests = $derived(data.incomingRequests || []);
  let outgoingRequests = $derived(data.outgoingRequests || []);
  let user = $derived(data.session?.user);

  let activeServices = $derived(services.filter(s => s.is_active));
  let inactiveServices = $derived(services.filter(s => !s.is_active));
  let transportationServices = $derived(services.filter(s => s.type === 'transportation' && s.is_active));

  // Get recent/pending requests for dashboard overview
  let pendingIncoming = $derived(incomingRequests.filter(r => r.status === 'pending').slice(0, 5));
  let activeInProgress = $derived(incomingRequests.filter(r => r.status === 'in_progress').slice(0, 5));
  let pendingOutgoing = $derived(outgoingRequests.filter(r => ['pending', 'accepted'].includes(r.status)).slice(0, 5));

  function getServiceTypeLabel(type) {
    const labels = {
      healing: 'Healing',
      dps: 'DPS',
      transportation: 'Transport',
      crafting: 'Crafting',
      hunting: 'Hunting',
      mining: 'Mining',
      custom: 'Custom'
    };
    return labels[type] || type;
  }

  function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  }

  function viewService(service) {
    goto(`/market/services/${service.id}`);
  }

  // Table columns for services
  const serviceColumns = [
    {
      key: 'title',
      header: 'Service',
      sortable: true,
      searchable: true,
      formatter: (value) => `<span class="service-name">${value}</span>`
    },
    {
      key: 'type',
      header: 'Type',
      sortable: true,
      searchable: false,
      width: '100px',
      formatter: (value) => `<span class="type-badge">${getServiceTypeLabel(value)}</span>`
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      searchable: false,
      width: '100px',
      formatter: (value) => formatDate(value)
    }
  ];

  function handleServiceRowClick(data) {
    const { row } = data;
    viewService(row);
  }
</script>

<svelte:head>
  <title>My Services and Requests | Entropia Nexus</title>
</svelte:head>

<div class="scroll-container">
<div class="page-container">
  <div class="breadcrumb">
    <a href="/market/services">Services</a>
    <span>/</span>
    <span>My Services</span>
  </div>

  <div class="header-row">
    <h1>My Services</h1>
    {#if user?.verified}
      <a href="/market/services/create" class="create-button">+ Create Service</a>
    {/if}
  </div>

  <DashboardNav />

  {#if !user?.verified}
    <div class="notice">
      <p>You need to verify your account to create and manage services.</p>
      <a href="/account/setup">Complete account setup</a>
    </div>
  {:else if services.length === 0}
    <div class="empty-state">
      <p>You haven't created any services yet.</p>
      <a href="/market/services/create" class="create-link">Create your first service</a>
    </div>
  {:else}
    {#if transportationServices.length > 0}
      <div class="section">
        <h2>Flight Dashboards</h2>
        <div class="flight-links">
          {#each transportationServices as service}
            <a href="/market/services/{service.id}/flights" class="flight-link">
              <span class="flight-service-name">{service.title}</span>
              <span class="flight-link-btn">Manage Flights</span>
            </a>
          {/each}
        </div>
      </div>
    {/if}

    {#if activeServices.length > 0}
      <div class="section">
        <h2>Active Services ({activeServices.length})</h2>
        <div class="table-wrapper">
          <FancyTable
            columns={serviceColumns}
            data={activeServices}
            rowHeight={48}
            sortable={true}
            searchable={false}
            emptyMessage="No active services"
            onrowClick={handleServiceRowClick}
          />
        </div>
      </div>
    {/if}

    {#if inactiveServices.length > 0}
      <div class="section">
        <h2>Inactive Services ({inactiveServices.length})</h2>
        <div class="table-wrapper inactive-table">
          <FancyTable
            columns={serviceColumns}
            data={inactiveServices}
            rowHeight={48}
            sortable={true}
            searchable={false}
            emptyMessage="No inactive services"
            onrowClick={handleServiceRowClick}
          />
        </div>
      </div>
    {/if}

    <!-- Dashboard Overview: Pending Incoming Requests -->
    {#if pendingIncoming.length > 0}
      <div class="section">
        <div class="section-header">
          <h2>Pending Requests ({pendingIncoming.length})</h2>
          <a href="/market/services/my/offers" class="view-all">View all</a>
        </div>
        <div class="request-cards">
          {#each pendingIncoming as request}
            <div class="request-card" onclick={() => goto(`/market/services/my/offers/${request.service_id}`)} onkeypress={(e) => e.key === 'Enter' && goto(`/market/services/my/offers/${request.service_id}`)} role="button" tabindex="0">
              <div class="request-info">
                <span class="requester">{request.requester_name}</span>
                <span class="service-name">{request.service_title}</span>
              </div>
              <RequestStatusBadge status={request.status} size="small" />
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Dashboard Overview: In Progress -->
    {#if activeInProgress.length > 0}
      <div class="section">
        <div class="section-header">
          <h2>In Progress ({activeInProgress.length})</h2>
          <a href="/market/services/my/offers" class="view-all">View all</a>
        </div>
        <div class="request-cards">
          {#each activeInProgress as request}
            <div class="request-card" onclick={() => goto(`/market/services/my/offers/${request.service_id}`)} onkeypress={(e) => e.key === 'Enter' && goto(`/market/services/my/offers/${request.service_id}`)} role="button" tabindex="0">
              <div class="request-info">
                <span class="requester">{request.requester_name}</span>
                <span class="service-name">{request.service_title}</span>
              </div>
              <RequestStatusBadge status={request.status} size="small" />
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- Dashboard Overview: My Outgoing Requests -->
    {#if pendingOutgoing.length > 0}
      <div class="section">
        <div class="section-header">
          <h2>My Pending Requests ({pendingOutgoing.length})</h2>
          <a href="/market/services/my/requests" class="view-all">View all</a>
        </div>
        <div class="request-cards">
          {#each pendingOutgoing as request}
            <div class="request-card" onclick={() => goto(`/market/services/my/requests/${request.id}`)} onkeypress={(e) => e.key === 'Enter' && goto(`/market/services/my/requests/${request.id}`)} role="button" tabindex="0">
              <div class="request-info">
                <span class="provider">{request.provider_name}</span>
                <span class="service-name">{request.service_title}</span>
              </div>
              <RequestStatusBadge status={request.status} size="small" />
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}

  <div class="links-section">
    <a href="/market/services">Browse all services</a>
  </div>
</div>
</div>

<style>
  .scroll-container {
    height: 100%;
    overflow-y: auto;
  }

  .page-container {
    padding: 1rem;
    max-width: 1000px;
    margin: 0 auto;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    color: var(--text-muted, #666);
    margin-bottom: 1rem;
  }

  .breadcrumb a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .table-wrapper {
    height: 300px;
    min-height: 200px;
  }

  .table-wrapper.inactive-table {
    opacity: 0.8;
  }

  /* Table cell styles */
  :global(.table-wrapper .service-name) {
    font-weight: 500;
  }

  :global(.table-wrapper .type-badge) {
    display: inline-block;
    padding: 0.2rem 0.5rem;
    background: var(--hover-color);
    border-radius: 4px;
    font-size: 0.85rem;
  }

  .header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  h1 {
    margin: 0;
  }

  .create-button {
    background: var(--accent-color, #4a9eff);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    text-decoration: none;
    font-weight: 500;
    white-space: nowrap;
  }

  .create-button:hover {
    background: var(--accent-color-hover, #3a8eef);
  }

  .notice {
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #ccc);
    border-radius: 8px;
    padding: 1.5rem;
    text-align: center;
  }

  .notice p {
    margin: 0 0 1rem 0;
  }

  .notice a {
    color: var(--accent-color, #4a9eff);
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted, #888);
  }

  .empty-state p {
    margin: 0 0 1rem 0;
  }

  .create-link {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .create-link:hover {
    text-decoration: underline;
  }

  .section {
    margin-bottom: 2rem;
  }

  .section h2 {
    margin: 0 0 1rem 0;
    font-size: 1.2rem;
  }

  .links-section {
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color, #ccc);
  }

  .links-section a {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
  }

  .links-section a:hover {
    text-decoration: underline;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
  }

  .section-header h2 {
    margin: 0;
  }

  .view-all {
    color: var(--accent-color, #4a9eff);
    text-decoration: none;
    font-size: 0.9rem;
  }

  .view-all:hover {
    text-decoration: underline;
  }

  .request-cards {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .request-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #e5e5e5);
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .request-card:hover {
    background: var(--hover-color, #f0f0f0);
    border-color: var(--accent-color);
  }

  .request-info {
    display: flex;
    flex-direction: column;
    gap: 0.125rem;
    min-width: 0;
  }

  .requester, .provider {
    font-weight: 500;
    color: var(--text-color, #333);
  }

  .request-info .service-name {
    font-size: 0.85rem;
    color: var(--text-muted, #666);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .flight-links {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .flight-link {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    background: var(--secondary-color);
    border: 1px solid var(--border-color, #555);
    border-radius: 6px;
    text-decoration: none;
    transition: background-color 0.15s ease, border-color 0.15s ease;
    gap: 1rem;
  }

  .flight-link:hover {
    background: var(--hover-color);
    border-color: var(--accent-color, #4a9eff);
  }

  .flight-service-name {
    font-weight: 500;
    color: var(--text-color);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .flight-link-btn {
    background: var(--accent-color, #4a9eff);
    color: white;
    padding: 0.35rem 0.75rem;
    border-radius: 4px;
    font-size: 0.85rem;
    font-weight: 500;
    white-space: nowrap;
    flex-shrink: 0;
  }

  /* Mobile styles */
  @media (max-width: 600px) {
    .page-container {
      padding: 0.75rem;
    }

    h1 {
      font-size: 1.5rem;
    }

    .header-row {
      flex-direction: column;
      align-items: stretch;
    }

    .create-button {
      text-align: center;
    }

    .table-wrapper {
      height: 250px;
    }

    .request-card {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.5rem;
    }

    .flight-link {
      flex-direction: column;
      align-items: stretch;
      gap: 0.75rem;
    }

    .flight-link-btn {
      text-align: center;
    }
  }
</style>
