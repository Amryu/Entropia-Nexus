<script>
  import { page } from '$app/stores';

  const navItems = [
    { href: '/market/services/my', label: 'Overview', exact: true },
    { href: '/market/services/my/offers', label: 'My Offers' },
    { href: '/market/services/my/requests', label: 'My Requests' },
    { href: '/market/services/my/tickets', label: 'Tickets' }
  ];

  function isActive(href, exact = false) {
    if (exact) {
      return $page.url.pathname === href;
    }
    return $page.url.pathname.startsWith(href);
  }
</script>

<nav class="dashboard-nav">
  <ul>
    {#each navItems as item}
      <li class:active={isActive(item.href, item.exact)}>
        <a href={item.href}>{item.label}</a>
      </li>
    {/each}
  </ul>
</nav>

<style>
  .dashboard-nav {
    margin-bottom: 1.5rem;
    border-bottom: 1px solid var(--border-color, #ccc);
  }

  ul {
    display: flex;
    gap: 0;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  li {
    position: relative;
  }

  a {
    display: block;
    padding: 0.75rem 1.25rem;
    color: var(--text-muted, #666);
    text-decoration: none;
    font-weight: 500;
    transition: color 0.15s ease;
  }

  a:hover {
    color: var(--text-color, #333);
  }

  li.active a {
    color: var(--accent-color, #4a9eff);
  }

  li.active::after {
    content: '';
    position: absolute;
    bottom: -1px;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--accent-color, #4a9eff);
  }

  @media (max-width: 600px) {
    ul {
      flex-wrap: wrap;
    }

    a {
      padding: 0.5rem 0.75rem;
      font-size: 0.9rem;
    }
  }
</style>
