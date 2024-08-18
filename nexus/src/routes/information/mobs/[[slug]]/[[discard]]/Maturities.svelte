<script>
  // @ts-nocheck
  import Table from '$lib/components/Table.svelte';
  import '$lib/style.css';
  
  export let maturities;

  let selectedMaturity = -1;

  $: if (maturities) {
    maturities = maturities.sort((a, b) => {
      if (a.Properties.Level !== b.Properties.Level) {
        return a.Properties.Level - b.Properties.Level;
      }
      if (a.Properties.Health !== b.Properties.Health) {
        return a.Properties.Health - b.Properties.Health;
      }
      return a.Properties.Damage - b.Properties.Damage;
    });
  }

  function getTotalDamage(attack) {
    return attack.Damage.Impact + attack.Damage.Cut + attack.Damage.Stab + attack.Damage.Penetration + attack.Damage.Shrapnel + attack.Damage.Burn + attack.Damage.Cold + attack.Damage.Acid + attack.Damage.Electric;
  }

  function getTotalDefense(maturity) {
    return maturity.Properties.Defense.Impact
      + maturity.Properties.Defense.Cut
      + maturity.Properties.Defense.Stab
      + maturity.Properties.Defense.Penetration
      + maturity.Properties.Defense.Shrapnel
      + maturity.Properties.Defense.Burn
      + maturity.Properties.Defense.Cold
      + maturity.Properties.Defense.Acid
      + maturity.Properties.Defense.Electric;
  }
</script>

<style>
  .container {
    display: flex;
  }

  .damage-table {
    margin-left: 20px;
    text-align: center;
  }
</style>
  
<h2>Maturities</h2>
{#if (!maturities || maturities.length === 0)}
<br />
<div>No data available.</div>
{:else}
<div class="container">
  <div class="main-table">
    <Table
      header = { 
        {
          values: ['Name', 'Level', 'HP', 'HP/Lv', 'Regen', 'Damage', 'Miss Chance', 'Defense', 'Tameable']
        }
      }
      data = {
        maturities.map((maturity) => ({
          values: [
            maturities.length === 1 && (maturity.Name == null || maturity.Name.trim().length === 0) ? 'Single Maturity Mob' : maturity.Name,
            maturity.Properties?.Level ?? 'N/A',
            maturity.Properties?.Health ?? 'N/A',
            maturity.Properties?.Health != null && maturity.Properties?.Level != null ? (maturity.Properties.Health / Math.max(maturity.Properties.Level, 1)).toFixed(2) : 'N/A',
            maturity.Properties?.RegenerationAmount != null ? `${maturity.Properties?.RegenerationAmount}/s` : 'N/A',
            maturity.Attacks.length === 1 ? getTotalDamage(maturity.Attacks[0]) : maturity.Attacks.map(x => `${x.Name}: ${getTotalDamage(x)}`).join('<br />'),
            maturity.Properties?.MissChance != null ? `${maturity.Properties?.MissChance}%` : 'N/A',
            getTotalDefense(maturity),
            maturity.Properties?.TamingLevel > 0 ? `Level ${maturity.Properties.TamingLevel}` : 'No',
          ]
        }))
      }
      options={{searchable: "true"}} />
  </div>
  <div class="damage-table">
  <select bind:value={selectedMaturity}>
    <option value={-1}>Select maturity</option>
    {#each maturities as maturity, index}
      <option value={index}>{maturity.Name}</option>
    {/each}
  </select>
  <br />
  <br />
  {#if selectedMaturity >= 0}
    {#if maturities[selectedMaturity].Attacks.length === 0}
      <div>No attacks available.</div>
    {:else}
      <Table
        header = { 
          {
            values: ['Type', ...maturities[selectedMaturity].Attacks.map(x => x.Name)]
          }
        }
        data = { 
          ['Stab', 'Cut', 'Impact', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'].map(x =>
            ({ values: [x, ...(maturities[selectedMaturity].Attacks.map(y => y.Damage[x] ?? 0))] }),
          )
        } />
    {/if}
  {/if}
</div>
</div>
{/if}