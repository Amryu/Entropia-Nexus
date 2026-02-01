<script>
  // @ts-nocheck
  import Table from '$lib/components/Table.svelte';
  import '$lib/style.css';
  
  export let maturities;
  export let type = null;

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
    return attack.TotalDamage;
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

  function getDamageText(attack) {
    let composition = Object.entries(attack.Damage)
      .filter(([key, value]) => value != null && value > 0)
      .map(([key, value]) => `${key}: ${value}%`)
      .join(', ');

    return `<span style="text-decoration: underline; text-decoration-style: dotted;" title="${composition}">${attack.TotalDamage ?? 'N/A'}</span>`
  }
</script>

<style>
  .container {
    display: flex;
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
          values: type === 'Asteroid'
            ? ['Name', 'Level', 'HP', 'HP/Lv']
            : ['Name', 'Level', 'HP', 'HP/Lv', 'Regen', 'Primary', 'Secondary', 'Tertiary', 'Defense', 'Tameable']
        }
      }
      data = {
        maturities.map((maturity) => ({
          values: type === 'Asteroid'
            ? [
                maturities.length === 1 && (maturity.Name == null || maturity.Name.trim().length === 0) ? 'Single Maturity Mob' : maturity.Name,
                maturity.Properties?.Level ?? 'N/A',
                maturity.Properties?.Health ?? 'N/A',
                maturity.Properties?.Health != null && maturity.Properties?.Level != null ? (maturity.Properties.Health / Math.max(maturity.Properties.Level, 1)).toFixed(2) : 'N/A',
              ]
            : [
                maturities.length === 1 && (maturity.Name == null || maturity.Name.trim().length === 0) ? 'Single Maturity Mob' : maturity.Name,
                maturity.Properties?.Level ?? 'N/A',
                maturity.Properties?.Health ?? 'N/A',
                maturity.Properties?.Health != null && maturity.Properties?.Level != null ? (maturity.Properties.Health / Math.max(maturity.Properties.Level, 1)).toFixed(2) : 'N/A',
                maturity.Properties?.RegenerationAmount != null ? `${maturity.Properties?.RegenerationAmount}/s` : 'N/A',
                maturity.Attacks.length === 1 ? getDamageText(maturity.Attacks[0]) : 'N/A',
                maturity.Attacks.length > 1 ? getDamageText(maturity.Attacks[1]) : 'N/A',
                maturity.Attacks.length > 2 ? getDamageText(maturity.Attacks[2]) : 'N/A',
                getTotalDefense(maturity),
                maturity.Properties?.TamingLevel > 0 ? `Level ${maturity.Properties.TamingLevel}` : 'No',
              ]
        }))
      }
      options={{searchable: "true"}} />
  </div>
</div>
{/if}