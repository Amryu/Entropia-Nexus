<script>
  // @ts-nocheck

  import '$lib/style.css';

  import Table from './Table.svelte';

  export let loadouts = null;
  export let currentLoadout = null;

  let search = '';
  let sortedLoadouts;

  let fileInput;

  $: if (loadouts !== null) {
    sortedLoadouts = loadouts.sort((a, b) => a.Name.localeCompare(b.Name));
  }
  
  let filteredLoadouts;

  $: {
    const searchTerm = search?.toLowerCase();
    filteredLoadouts = !search.trim() ? sortedLoadouts : sortedLoadouts.filter((item) => {
      return item.Name.toLowerCase().includes(searchTerm);
    });
  }

  function handleFileChange() {
    const file = fileInput.files[0];
    const reader = new FileReader();

    reader.onload = (e) => {
      const contents = e.target.result;
      const data = JSON.parse(contents);

      if (loadouts === null) {
        loadouts = [];
      }

      if (data) {
        loadouts.push(data);
        currentLoadout = data;
      }
    };

    JSON.parse(reader.readAsText(file));
  }

  function createNewLoadout() {
    let newArmorObject = () => ({
      Name: null,
      Plate: null
    });

    const newLoadout = {
      Id: Math.random().toString(16).slice(3),
      Name: 'New Loadout',
      Properties: {
        BonusDamage: 0,
        BonusCritChance: 0,
        BonusCritDamage: 0,
        BonusReload: 0
      },
      Gear: {
        Weapon: {
          Name: null,
          Amplifier: null,
          Scope: null,
          Sight: null,
          Absorber: null,
          Implant: null,
          Enhancers: {
            Damage: 0,
            Accuracy: 0,
            Range: 0,
            Economy: 0,
            SkillMod: 0,
          }
        },
        Armor: {
          SetName: null,
          PlateName: null,
          Head: newArmorObject(),
          Torso: newArmorObject(),
          Arms: newArmorObject(),
          Hands: newArmorObject(),
          Legs: newArmorObject(),
          Shins: newArmorObject(),
          Feet: newArmorObject(),
          Enhancers: {
            Defense: 0,
            Durability: 0,
          },
          ManageIndividual: false,
        },
        Clothing: [],
        Consumables: [],
        Pet: {
          Name: null,
          Effect: null,
        }
      },
      Skill: {
        Hit: 200,
        Dmg: 200,
      },
      Markup: {
        Weapon: 100,
        Ammo: 100,
        Amplifier: 100,
        Absorber: 100,
        Scope: 100,
        Sight: 100,
        ScopeSight: 100,
        Matrix: 100,
        Implant: 100,
        ArmorSet: 100,
        PlateSet: 100,
        Armors: {
          Head: 100,
          Torso: 100,
          Arms: 100,
          Hands: 100,
          Legs: 100,
          Shins: 100,
          Feet: 100,
        },
        Plates: {
          Head: 100,
          Torso: 100,
          Arms: 100,
          Hands: 100,
          Legs: 100,
          Shins: 100,
          Feet: 100,
        },
      }
    };

    loadouts.push(newLoadout);
    loadouts = loadouts;
    currentLoadout = newLoadout;
  }

  function deleteCurrentLoadout() {
    const index = loadouts.findIndex((x) => x.Id === currentLoadout.Id);

    if (index < 0) return;

    loadouts.splice(index, 1);
    loadouts = loadouts;
    currentLoadout = null;
  }

  function exportLoadout() {
    const data = JSON.stringify(currentLoadout);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = (currentLoadout.Name ?? 'loadout') + '.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  function importLoadout() {
    fileInput.click();
  }
</script>

<style>
  .width100 {
    width: calc(100% - 8px);
  }

  .button-container {
    display: grid;
    text-align: center;
    width: 100%;
    grid-template-columns: 1fr 1fr 1fr 1fr;
    gap: 0 5px;
  }

  .square-button {
    width: 100%;
    height: 32px;
    border: none;
    margin-right: 5px;
    font-size: 12px;
  }

  .square-button:not([disabled]):hover {
    cursor: pointer;
    background-color: var(--hover-color);
  }

  .list-wrapper {
    position: relative;
  }

  .info-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
  }

  .search-input {
    margin-bottom: 10px;
  }
</style>

<div class="list-wrapper">
  <h2>Loadouts</h2>
  <br />

  <div class="info-container">
    <div class="button-container">
      <button class="square-button" on:click={createNewLoadout} title='Add'>Add</button>
      <button class="square-button" on:click={deleteCurrentLoadout} disabled={currentLoadout === null} title='Delete'>Delete</button>
      <button class="square-button" on:click={exportLoadout} disabled={currentLoadout === null} title='Export'>Export</button>
      <button class="square-button" on:click={importLoadout} title='Import'>Import</button>
      <input type="file" bind:this={fileInput} on:change={handleFileChange} style="display: none;">
    </div>
  </div>
  <input class="search-input width100" type="text" placeholder="Search..." bind:value={search} on:focus={(evt) => { if (evt.target.selectionStart === evt.target.selectionEnd) evt.target.select(); }} style="font-size: 20px;">

  <div style="display: flex; overflow-x: auto; overflow-y: hidden; flex-grow: 1;">
    {#if !filteredLoadouts || filteredLoadouts.length === 0}
    <div style="text-align: center; margin: auto;">
      <br />
      No items found...<br />
      <br />
      <input type="button" value="Clear Search" on:click="{() => search = ''}" />
    </div>
    {:else}
      <Table
        style='width: 300px'
        header={
          { 
            values: ['Name'],
            widths: ['1fr']
          }
        }
        data={
          filteredLoadouts.map((item) => {
            return {
              values: [item.Name],
              trStyle: item.Id === currentLoadout?.Id ? `font-weight: bold;` : '',
              id: item.Id
            };
          })
        }
        options={
          { 
            highlightOnHover: true,
            virtual: true
          }
        }
        on:rowClick={(evt) => {
          currentLoadout = loadouts.find(x => x.Id === evt.detail.data.id);
        }} />
    {/if}
  </div>
</div>