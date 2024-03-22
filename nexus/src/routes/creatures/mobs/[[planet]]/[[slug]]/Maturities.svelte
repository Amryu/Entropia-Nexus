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
    return attack.Impact + attack.Cut + attack.Stab + attack.Penetration + attack.Shrapnel + attack.Burn + attack.Cold + attack.Acid + attack.Electric;
  }

  function getTotalDefense(maturity) {
    return maturity.Properties.Defenses.Impact
      + maturity.Properties.Defenses.Cut
      + maturity.Properties.Defenses.Stab
      + maturity.Properties.Defenses.Penetration
      + maturity.Properties.Defenses.Shrapnel
      + maturity.Properties.Defenses.Burn
      + maturity.Properties.Defenses.Cold
      + maturity.Properties.Defenses.Acid
      + maturity.Properties.Defenses.Electric;
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
  
<div class="title">Maturities</div>
{#if (!maturities || maturities.length === 0)}
<br />
<div>No data available.</div>
{:else}
<div class="container">
  <div class="main-table">
    <Table
      header = { 
        {
          values: ['Name', 'Level', 'HP', 'HP/Lv', 'Regen', 'Damage', 'Crit. Chance', 'Defense', 'Tameable']
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
            maturity.Attacks.length === 1 ? getTotalDamage(maturity.Attacks[0]) : maturity.Attacks.map(x => `${x.Name}: ${getTotalDamage(x)}`),
            maturity.Properties?.CriticalHitChance != null ? `${maturity.Properties?.CriticalHitChance}%` : 'N/A',
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
  {#if selectedMaturity >= 0}
    {#if maturities[selectedMaturity].Attacks.length === 0}
      <br />
      <br />
      <div>No attacks available.</div>
    {:else}
      <Table
        header = { 
          {
            values: ['Type', ...maturities[selectedMaturity].Attacks.map(x => x.Name)]
          }
        }
        data = { 
          ['Impact', 'Cut', 'Stab', 'Penetration', 'Shrapnel', 'Burn', 'Cold', 'Acid', 'Electric'].map(x =>
            ({ values: [x, ...(maturities[selectedMaturity].Attacks.map(y => y[x] ?? 0))] }),
          ).filter(x => x.values[1] !== 0)
        } />
    {/if}
  {/if}
</div>
</div>
{/if}