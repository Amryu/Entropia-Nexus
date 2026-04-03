<!--
  @component Events Page
  Lists upcoming and past events with progressive loading for history.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import { onMount, onDestroy } from 'svelte';

  let { data } = $props();

  const BATCH_SIZE = 20;
  let visibleCount = $state(BATCH_SIZE);
  let sentinel = $state();
  let observer;

  let upcoming = $derived(data.upcoming || []);
  let allPast = $derived(data.past || []);
  let visiblePast = $derived(allPast.slice(0, visibleCount));
  let hasMore = $derived(visibleCount < allPast.length);

  function formatEventDate(dateStr) {
    const d = new Date(dateStr);
    return {
      month: d.toLocaleDateString('en-US', { month: 'short' }).toUpperCase(),
      day: d.getDate(),
      time: d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }),
      year: d.getFullYear()
    };
  }

  function isEventActive(event) {
    const now = Date.now();
    const start = new Date(event.start_date).getTime();
    if (start > now) return false;
    if (event.end_date) return new Date(event.end_date).getTime() > now;
    return now - start < 24 * 60 * 60 * 1000;
  }

  function formatDuration(event, active) {
    if (!event.end_date) return null;
    const now = Date.now();
    const end = new Date(event.end_date).getTime();
    const start = new Date(event.start_date).getTime();
    const ms = active ? end - now : end - start;
    if (ms <= 0) return null;
    const hours = Math.round(ms / (60 * 60 * 1000));
    const days = Math.round(ms / (24 * 60 * 60 * 1000));
    let span;
    if (days < 1) span = hours <= 1 ? '1 hour' : `${hours} hours`;
    else if (days === 1) span = '1 day';
    else if (days < 14) span = `${days} days`;
    else { const w = Math.round(days / 7); span = w === 1 ? '1 week' : `${w} weeks`; }
    return active ? `ends in ${span}` : `lasts ${span}`;
  }

  function formatPastDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  }

  onMount(() => {
    observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting && hasMore) {
        visibleCount = Math.min(visibleCount + BATCH_SIZE, allPast.length);
      }
    }, { rootMargin: '200px' });

    if (sentinel) observer.observe(sentinel);
  });

  onDestroy(() => {
    observer?.disconnect();
  });
</script>

<svelte:head>
  <title>Events - Entropia Nexus</title>
  <meta name="description" content="Browse upcoming and past Entropia Universe events. Official MindArk events and player-organized community events." />
  <link rel="canonical" href="https://entropianexus.com/events" />

  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://entropianexus.com/events" />
  <meta property="og:title" content="Entropia Universe Events - Entropia Nexus" />
  <meta property="og:description" content="Browse upcoming and past Entropia Universe events. Official and player-organized community events." />
  <meta property="og:image" content="https://entropianexus.com/icon.png" />
  <meta property="og:site_name" content="Entropia Nexus" />

  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="Entropia Universe Events - Entropia Nexus" />
  <meta name="twitter:description" content="Browse upcoming and past Entropia Universe events. Official and player-organized community events." />
  <meta name="twitter:image" content="https://entropianexus.com/icon.png" />
</svelte:head>

<div class="page-container">
  <nav class="breadcrumb">
    <a href="/">Home</a>
    <span class="separator">/</span>
    <span>Events</span>
  </nav>

  <div class="page-header">
    <h1>Events</h1>
    <a href="/events/submit" class="action-btn">Submit Event</a>
  </div>

  <!-- Upcoming Events -->
  {#if upcoming.length > 0}
    <section class="section">
      <h2 class="section-title">Upcoming</h2>
      <div class="events-list">
        {#each upcoming as event}
          {@const ed = formatEventDate(event.start_date)}
          {@const active = isEventActive(event)}
          {@const duration = formatDuration(event, active)}
          <div class="event-row" class:event-active={active}>
            <div class="event-date-block">
              <span class="event-month">{ed.month}</span>
              <span class="event-day">{ed.day}</span>
            </div>
            <div class="event-info">
              <div class="event-title-row">
                <h3 class="event-title">{event.title}</h3>
                {#if active}
                  <span class="event-active-badge">Live</span>
                {/if}
                {#if event.recurring_event_name}
                  <span class="event-recurring-badge">{event.recurring_event_name}</span>
                {/if}
                <span class="event-type-badge" class:official={event.type === 'official'}>
                  {event.type === 'official' ? 'Official' : 'Player Event'}
                </span>
              </div>
              <div class="event-details">
                <span class="event-time">{ed.time} UTC</span>
                {#if duration}
                  <span class="event-duration">{duration}</span>
                {/if}
                {#if event.location}
                  <span class="event-location">{event.location}</span>
                {/if}
              </div>
            </div>
            {#if event.link}
              <a href={event.link} class="event-link" target="_blank" rel="noopener">Details</a>
            {/if}
          </div>
        {/each}
      </div>
    </section>
  {/if}

  <!-- Past Events -->
  {#if allPast.length > 0}
    <section class="section">
      <h2 class="section-title">Past Events</h2>
      <div class="events-list">
        {#each visiblePast as event}
          {@const ed = formatEventDate(event.start_date)}
          <div class="event-row past">
            <div class="event-date-block">
              <span class="event-month">{ed.month}</span>
              <span class="event-day">{ed.day}</span>
              <span class="event-year">{ed.year}</span>
            </div>
            <div class="event-info">
              <div class="event-title-row">
                <h3 class="event-title">{event.title}</h3>
                {#if event.recurring_event_name}
                  <span class="event-recurring-badge">{event.recurring_event_name}</span>
                {/if}
                <span class="event-type-badge" class:official={event.type === 'official'}>
                  {event.type === 'official' ? 'Official' : 'Player Event'}
                </span>
              </div>
              <div class="event-details">
                <span class="event-time">{formatPastDate(event.start_date)}</span>
                {#if event.location}
                  <span class="event-location">{event.location}</span>
                {/if}
              </div>
            </div>
            {#if event.link}
              <a href={event.link} class="event-link" target="_blank" rel="noopener">Details</a>
            {/if}
          </div>
        {/each}
      </div>

      {#if hasMore}
        <div class="sentinel" bind:this={sentinel}></div>
      {/if}
    </section>
  {/if}

  {#if upcoming.length === 0 && allPast.length === 0}
    <p class="empty-state">No events yet. Be the first to <a href="/events/submit">submit one</a>!</p>
  {/if}
</div>

<style>
  .page-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
    box-sizing: border-box;
  }

  .breadcrumb {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .breadcrumb a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .breadcrumb a:hover {
    text-decoration: underline;
  }

  .separator {
    color: var(--text-muted);
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    margin: 0;
    color: var(--text-color);
  }

  .action-btn {
    padding: 0.5rem 1rem;
    background-color: var(--accent-color);
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    text-decoration: none;
    transition: background-color 0.15s;
  }

  .action-btn:hover {
    background-color: var(--accent-color-hover);
  }

  .section {
    margin-bottom: 2.5rem;
  }

  .section-title {
    margin: 0 0 1rem 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .empty-state {
    text-align: center;
    padding: 3rem;
    color: var(--text-muted);
  }

  .empty-state a {
    color: var(--accent-color);
    text-decoration: none;
  }

  .empty-state a:hover {
    text-decoration: underline;
  }

  .events-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .event-row {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 16px;
    background-color: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    transition: border-color 0.15s ease;
  }

  .event-row:hover {
    border-color: var(--accent-color);
  }

  .event-row.event-active {
    border-color: rgba(34, 197, 94, 0.4);
    background-color: rgba(34, 197, 94, 0.05);
  }

  .event-row.past {
    opacity: 0.75;
  }

  .event-row.past:hover {
    opacity: 1;
  }

  .event-active-badge {
    font-size: 0.6875rem;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    background-color: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }

  .event-date-block {
    flex-shrink: 0;
    width: 52px;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    line-height: 1;
  }

  .event-month {
    font-size: 0.6875rem;
    font-weight: 700;
    color: var(--accent-color);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .event-day {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-color);
  }

  .event-year {
    font-size: 0.625rem;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .event-info {
    flex: 1;
    min-width: 0;
  }

  .event-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .event-title {
    margin: 0;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--text-color);
  }

  .event-type-badge {
    font-size: 0.6875rem;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    background-color: rgba(107, 114, 128, 0.15);
    color: var(--text-muted);
  }

  .event-type-badge.official {
    background-color: rgba(59, 130, 246, 0.15);
    color: var(--accent-color);
  }

  .event-recurring-badge {
    font-size: 0.6875rem;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
    letter-spacing: 0.3px;
    background-color: rgba(255, 107, 53, 0.15);
    color: #ff6b35;
  }

  .event-details {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 4px;
    font-size: 0.8125rem;
    color: var(--text-muted);
  }

  .event-duration::before,
  .event-location::before {
    content: '\00B7';
    margin-right: 12px;
  }

  .event-link {
    flex-shrink: 0;
    font-size: 0.8125rem;
    color: var(--accent-color);
    text-decoration: none;
    padding: 4px 12px;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    transition: border-color 0.15s ease;
  }

  .event-link:hover {
    border-color: var(--accent-color);
  }

  .sentinel {
    height: 1px;
  }

  @media (max-width: 899px) {
    .page-container {
      padding: 16px;
    }

    .page-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 0.75rem;
    }
  }

  @media (max-width: 599px) {
    .event-row {
      flex-wrap: wrap;
      gap: 12px;
    }

    .event-link {
      margin-left: auto;
    }
  }
</style>
