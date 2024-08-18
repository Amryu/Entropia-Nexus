<script lang="ts">
  // @ts-nocheck

  import '$lib/style.css';

  import { darkMode } from '../../stores.js';

  import { getTypeLink, getTypeName } from "$lib/util";
  import { loading } from "../../actions/loading";
  
  export let user;

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
    'Information': [
      { label: 'Mobs', url: 'mobs' },
      { label: 'Professions', url: 'professions' },
      { label: 'Skills', url: 'skills' },
      { label: 'Vendors', url: 'vendors' },
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
  */],
    'External': [
      { label: 'NI Helper', url: 'nihelper' },
      { label: 'Cyrenedream', url: 'cyrenedream' },
    ]
  };

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
    padding-top: 5px;
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

  .dropdown-content.right {
    left: auto;
    right: 0;
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

  .discord-button {
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: #7289DA;
    color: white;
    border: none;
    padding: 10px;
    padding: 4px 10px;
    border-radius: 5px;
    cursor: pointer;
    margin-left: 20px;
  }

  .discord-button:hover {
    background-color: #677bc4;
  }

  .user {
    margin-left: 20px;
  }

  .user-image {
    border-radius: 50%;
  }
</style>

<nav>
  <div class="menu-container">
    <a href="/"><img class="website-icon" src="/favicon.png" alt="Entropia Nexus" title="Entropia Nexus" width="48px" height="48px" /></a>
    {#each Object.keys(menuItems) as menu (menu)}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="menu-item" on:mouseenter={() => dropdownOpen = menu} on:mouseleave={() => dropdownOpen = null}>
          {menu}
          <div class="dropdown-content" style="visiblity: {dropdownOpen === menu ? 'visible' : 'hidden'}">
              {#each menuItems[menu] as item (item)}
                {#if item.url === 'api'}
                  <a href="{import.meta.env.VITE_API_URL}/docs/"><div class="menu-dropdown-item">{item.label}</div></a>
                {:else if item.url === 'nihelper'}
                  <a href="https://www.nihelper.com"><div class="menu-dropdown-item">{item.label}</div></a>
                {:else if item.url === 'cyrenedream'}
                  <a href="https://www.cyrenedream.org"><div class="menu-dropdown-item">{item.label}</div></a>
                {:else}
                  <a use:loading href="/{menu.toLowerCase()}/{item.url.toLowerCase()}"><div class="menu-dropdown-item">{item.label}</div></a>
                {/if}
              {/each}
          </div>
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
    {#if user == null}
      <a href="/discord/login">
        <button class="discord-button">
          <img src="/discord.svg" alt="Discord Login" width="24px" height="24px" style="margin-right: 8px" /> Login with Discord
        </button>
      </a>
    {:else}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="menu-item user" on:mouseenter={() => dropdownOpen = 'user'} on:mouseleave={() => dropdownOpen = null}>
        <img src="https://cdn.discordapp.com/avatars/{user.id}/{user.avatar}.png" class="user-image" width="48px" height="48px" alt="Discord Avatar" />
        <div class="dropdown-content right" style="visiblity: {dropdownOpen === 'user' ? 'visible' : 'hidden'}">
          <div class="menu-dropdown-item">Logged in as {user.discriminator == 0 ? user.global_name : `${user.username}#${user.discriminator}`}</div>
          <a use:loading href="/discord/logout"><div class="menu-dropdown-item">Logout</div></a>
        </div>
      </div>
    {/if}
    <div class="dark-light-toggle">
      {#if $darkMode === null || $darkMode === false}
        <button class="dark-light-button" on:click={() => setDarkModePreference(true)}><img width="32px" height="32px" src={'/dark.png'} alt="Dark mode button" title="Enable Dark Mode" /></button>
      {:else}
        <button class="dark-light-button" on:click={() => setDarkModePreference(false)}><img width="32px" height="32px" src={'/light.png'} alt="Light mode button" title="Disable Dark Mode" /></button>
      {/if}
    </div>
  </div>
</nav>
  