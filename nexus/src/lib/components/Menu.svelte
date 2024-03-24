<script lang="ts">
  // @ts-nocheck

  import '$lib/style.css';

  import { darkMode } from '../../stores.js';

  import { getTypeLink, getTypeName } from "$lib/util";
  import { loading } from "../../actions/loading";

  let isLoggedIn = true; // Change to false to see the login/sign-up buttons
  let userName = 'User Name';
  let dropdownOpen: string | null = null;

  interface MenuItems {
    [key: string]: { label: string; url: string }[];
  }
  const menuItems: MenuItems = {
    'Items': [
      { label: 'Weapons', url: 'weapons' },
      { label: 'Armor Sets', url: 'armorsets' },
      { label: 'Medical Tools', url: 'medicaltools' },
      { label: 'Tools', url: 'tools' },
      { label: 'Attachments', url: 'attachments' },
      { label: 'Blueprints', url: 'blueprints' },
      { label: 'Materials', url: 'materials' },
      { label: 'Pets', url: 'pets' },
      { label: 'Consumables', url: 'consumables' },
      { label: 'Vehicles', url: 'vehicles' },
      { label: 'Furnishings', url: 'furnishings' },
      { label: 'Clothing', url: 'clothing' }
    ],
    'Creatures': [
      { label: 'Mobs', url: 'mobs' },
      // { label: 'NPCs', url: 'npcs' },
    ],
    /*'Missions': [
      { label: 'Calypso', url: 'calypso' },
      { label: 'Cyrene', url: 'cyrene' },
      { label: 'Arkadia', url: 'arkadia' },
      { label: 'Arkadia Underground', url: 'arkadiaunderground' },
      { label: 'Arkadia Moon', url: 'arkadiamoon' },
      { label: 'Monria', url: 'monria' },
      { label: 'DSEC9', url: 'dsec9' },
      { label: 'Toulan', url: 'toulan' },
      { label: 'Rocktropia', url: 'rocktropia' },
      { label: 'HELL', url: 'hell' },
      { label: 'Next Island', url: 'nextisland' },
      { label: 'Ancient Greece', url: 'nextisland' }
    ],
    */
    'Maps': [
      { label: 'Calypso', url: 'calypso' },
      { label: 'Cyrene', url: 'cyrene' },
      { label: 'Arkadia', url: 'arkadia' },
      { label: 'Arkadia Underground', url: 'arkadiaunderground' },
      { label: 'Arkadia Moon', url: 'arkadiamoon' },
      { label: 'Monria', url: 'monria' },
      { label: 'DSEC9', url: 'dsec9' },
      { label: 'Toulan', url: 'toulan' },
      { label: 'Rocktropia', url: 'rocktropia' },
      { label: 'HELL', url: 'hell' },
      { label: 'Secret Island', url: 'secretisland' },
      { label: 'Hunt the THING', url: 'huntthething' },
      { label: 'Next Island', url: 'nextisland' },
      { label: 'Ancient Greece', url: 'ancientgreece' },
      { label: 'Space', url: 'space' },
      { label: 'Crystal Palace', url: 'crystalpalace' },
      { label: 'Asteroid F.O.M.A', url: 'asteroidfoma' }
    ],
    'Tools': [
      { label: 'Loadout Manager', url: 'loadouts' },
      { label: 'API', url: 'api' },
    /*
      { label: 'Skill Manager', url: 'skillmanager' },
  */]
  };

  const userMenuItems: string[] = ['Profile', 'Settings', 'Dashboard'];

  let timeout;
  let searchQuery = '';
  let searchResults = [];

  let showDropdown = false;

  function handleSearch(event) {
    searchQuery = event.target.value;

    if (searchQuery.length < 2) {
      showDropdown = false;
      return;
    }

    clearTimeout(timeout);
    timeout = setTimeout(fetchSearchResults, 300);
  }

  async function fetchSearchResults() {
    fetch(import.meta.env.VITE_API_URL + `/search?query=${searchQuery}`)
      .then(response => response.json())
      .then(data => {
        searchResults = data;

        showDropdown = searchResults.length > 0;
      });
  }

  function hideDropdown() {
    setTimeout(() => {
      showDropdown = false;
    }, 200);
  }

  function setDarkModePreference(isDarkMode) {
    if (typeof window === 'undefined') return;

    darkMode.set(isDarkMode);
    localStorage.setItem('darkMode', isDarkMode ? 'true' : 'false');
  }
</script>
  
<style>
  nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: var(--secondary-color);
    height: 80px;
    padding: 0 20px;
    font-family: 'Arial', sans-serif;
    font-size: 18px;
    border-bottom: 1px solid grey;
  }

  .menu-container, .auth-container {
    display: flex;
    position: relative;
    align-items: center;
    height: 100%;
  }

  .website-icon {
    margin-right: auto;
    padding-right: 20px;
    font-weight: bold;
    font-size: 24px;
  }

  .menu-item {
    padding: 0 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    height: 100%;
    position: relative;
  }

  .dropdown-content {
    display: none;
    position: absolute;
    left: 0;
    min-width: 160px;
    top: 100%; /* Position it right below the menu item */
    background-color: var(--secondary-color);
    box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
    z-index: 1;
  }

  .menu-item:hover .dropdown-content {
    display: block;
  }

  .menu-dropdown-item {
    padding: 10px;
    white-space: nowrap;
  }

  a {
    text-decoration: none;
  }

  .search {
    font-size: 24px;
    border-radius: 5px;
  }

  .dropdown-search {
    position: absolute;
    top: 100%;
    right: 0;
    z-index: 1;
    min-width: 300px;
    overflow: auto;
    box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.2);
    background-color: #f9f9f9;
  }

  .search-container {
    position: relative;
    margin-left: 20px;
  }

  .search-dropdown-item {
    padding: 2px;
    white-space: nowrap;
    font-size: 16px;
  }

  .search-item-wrapper:nth-child(odd) {
    background-color: var(--table-row-color);
  }

  .search-item-wrapper:nth-child(even) {
    background-color: var(--table-row-color-alt);
  }

  .search-dropdown-item:hover {
    background-color: #a7a7a7;
  }

  .menu-item:hover, .menu-dropdown-item:hover {
    background-color: var(--hover-color);
  }

  .dark-light-toggle {
    margin-left: 20px;
    width: 34px;
    height: 34px;
    cursor: pointer;
  }

  .dark-light-button {
    background: none;
    border: none;
    padding: 0;
    margin: 0;
    font: inherit;
    color: inherit;
    cursor: pointer;
  }
</style>

<nav>
  <div class="menu-container">
    <span class="website-icon">Entropia Nexus</span>
    {#each Object.keys(menuItems) as menu (menu)}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="menu-item" on:mouseenter={() => dropdownOpen = menu} on:mouseleave={() => dropdownOpen = null}>
          {menu}
          {#if dropdownOpen === menu}
          <div class="dropdown-content">
              {#each menuItems[menu] as item (item)}
                {#if item.url === 'api'}
                  <a href="{import.meta.env.VITE_API_URL}/docs"><div class="menu-dropdown-item">{item.label}</div></a>
                {:else}
                  <a use:loading href="/{menu.toLowerCase()}/{item.url.toLowerCase()}"><div class="menu-dropdown-item">{item.label}</div></a>
                {/if}
              {/each}
          </div>
          {/if}
      </div>
    {/each}
  </div>

  <div class="auth-container">
    <div class="search-container">
      <input type="text" placeholder="Search..." class="search" on:blur={hideDropdown} on:focus={(evt) => { evt.target.select(); handleSearch(evt); }} on:input={handleSearch} />
      {#if showDropdown}
        <div class="dropdown-search">
          {#each searchResults as result}
            <div class='search-item-wrapper'>
              <a use:loading href={getTypeLink(result.Name, result.Type, result.SubType)}>
                <div class="search-dropdown-item">
                  {result.Name}<br />
                  <div style="font-size: 16px; width: 100%; text-align: right; margin-right: 2px;">{getTypeName(result.Type)}</div>
                </div>
              </a>
            </div>
          {/each}
        </div>
      {/if}
    </div>
    <div class="dark-light-toggle">
      {#if $darkMode === null || $darkMode === false}
        <button class="dark-light-button" on:click={() => setDarkModePreference(true)} title="Enable Dark Mode"><img width="32px" height="32px" src={'/dark.png'} /></button>
      {:else}
        <button class="dark-light-button" on:click={() => setDarkModePreference(false)} title="Disable Dark Mode"><img width="32px" height="32px" src={'/light.png'} /></button>
      {/if}
    </div>
    <!--
    {#if isLoggedIn}
      <div class="user-name" on:mouseenter={() => dropdownOpen = 'userMenu'} on:mouseleave={() => dropdownOpen = null}>
        {userName}
        {#if dropdownOpen === 'userMenu'}
          <div class="dropdown-content">
            {#each userMenuItems as item}
              <div class="menu-dropdown-item">{item}</div>
            {/each}
          </div>
        {/if}
      </div>
      <button class="logout-button">Logout</button>
    {:else}
      <button class="auth-button">Login</button>
      <button class="auth-button">Sign-Up</button>
    {/if}
    -->
  </div>
</nav>
  