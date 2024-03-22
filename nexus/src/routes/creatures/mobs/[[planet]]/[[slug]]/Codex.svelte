<script>
  // @ts-nocheck
  import Table from '$lib/components/Table.svelte';
  import '$lib/style.css';

  const codexMultipliers = [
    1, 2, 3, 4, 6,
    8, 10, 12, 14, 16,
    18, 20, 24, 28, 32,
    36, 40, 44, 48, 56,
    64, 72, 80, 90, 100
  ];

  const cat1 = [
    'Aim',
    'Anatomy',
    'Athletics',
    'BLP Weaponry Technology',
    'Combat Reflexes',
    'Dexterity',
    'Handgun',
    'Heavy Melee Weapons',
    'Laser Weaponry Technology',
    'Light Melee Weapons',
    'Longblades',
    'Power Fist',
    'Rifle',
    'Shortblades',
    'Weapons Handling'
  ];

  const cat2 = [
    'Clubs',
    'Courage',
    'Cryogenics',
    'Diagnosis',
    'Electrokinesis',
    'Inflict Melee Damage',
    'Inflict Ranged Damage',
    'Melee Combat',
    'Perception',
    'Plasma Weaponry Technology',
    'Pyrokinesis'
  ];

  const cat3 = [
    'Alertness',
    'Bioregenesis',
    'Bravado',
    'Concentration',
    'Dodge',
    'Evade',
    'First Aid',
    'Telepathy',
    'Translocation',
    'Vehicle Repairing'
  ];

  const cat4 = [
    'Analysis',
    'Animal Lore',
    'Biology',
    'Botany',
    'Computer',
    'Explosive Projectile Weaponry Technology',
    'Heavy Weapons',
    'Support Weapon Systems',
    'Zoology'
  ]

  export let baseCost = null;
  export let isCat4 = false;

  function chooseValueByCat(rank, cat1, cat2, cat3) {
    if (rank % 5 === 1 || rank % 5 === 2) {
      return cat1;
    } else if (rank % 5 === 3 || rank % 5 === 4) {
      return cat2;
    } else {
      return cat3;
    }
  }

  let rankSelected = 0;
</script>
<style>
  .button {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 80px;
    height: 80px;
    color: black;
    font-weight: bold;
    border: none;
    outline: none;
    cursor: pointer;
  }

  .container {
    display: flex;
  }

  .grid {
    display: inline-flex;
    align-items: flex-start;
    flex-direction: column;
    gap: 2px;
  }

  .row {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 2px;
  }

  .button:hover {
    background-color: white;
  }

  .button.selected {
    border: 1px solid black;
    background-color: gray;
  }
  
  .button:nth-child(5n+1), .button:nth-child(5n+2) {
    background-color: #CCCCCC;
  }

  .button:nth-child(5n+1):hover, .button:nth-child(5n+2):hover,
  .button:nth-child(5n+1).selected, .button:nth-child(5n+2).selected {
    background-color: #FFFFFF;
  }

  .button:nth-child(5n+3), .button:nth-child(5n+4) {
    background-color: #BBBBBB;
  }

  .button:nth-child(5n+3):hover, .button:nth-child(5n+4):hover,
  .button:nth-child(5n+3).selected, .button:nth-child(5n+4).selected {
    background-color: #EEEEEE;
  }

  .button:nth-child(5n) {
    background-color: #C0C0FF;
  }

  .button:nth-child(5n):hover {
    background-color: #F0F0FF;
  }

  .cat4 {
    background-color: #E8E89C !important;
  }

  .button.cat4.selected, .button.cat4:hover {
    background-color: #FFFF00 !important;
  }

  .rewards {
    margin-left: 20px;
  }
</style>

<div class="title">Codex</div>
{#if baseCost != null}
<div class="container">
  <div class="grid">
    {#each Array(5) as _, index}
      <div class="row">
        {#each codexMultipliers.slice(index * 5, index * 5 + 5) as multiplier, index2}
          <button class="{isCat4 && index2 === 4 ? 'cat4' : ''} button {rankSelected === index * 5 + index2 ? 'selected' : ''}" on:click={() => rankSelected = index * 5 + index2}>
            Rank {index * 5 + index2 + 1}<br /><br />{multiplier * baseCost}<br />PED
          </button>
        {/each}
      </div>
    {/each}
  </div>
  <div class="rewards">
    <Table
      style="min-width: 300px;"
      title="Reward Choices"
      header={
        {
          values: ['Skill', 'Value'],
          widths: ['1fr', 'max-content']
        }
      }
      data={
        chooseValueByCat(rankSelected + 1, cat1, cat2, cat3).map(skill => ({
          values: [
            skill,
            (codexMultipliers[rankSelected] * baseCost / chooseValueByCat(rankSelected + 1, 200, 320, 640)).toFixed(4) + ' PED'
          ],
          spans: [null, chooseValueByCat(rankSelected + 1, cat1, cat2, cat3).length],
        }))
        .concat(isCat4 && (rankSelected + 1) % 10 === 5 ? cat4.map(skill => ({
          values: [
            skill,
            (codexMultipliers[rankSelected] * baseCost / 1000).toFixed(4) + ' PED',
          ],
          spans: [null, cat4.length],
          tdStyles: ['cat4', 'cat4']
        })) : [])
      }
      options={
        {
          sortable: false,
        }
      }/>
  </div>
</div>
{:else}
<br />
<div>No data available.</div>
{/if}

