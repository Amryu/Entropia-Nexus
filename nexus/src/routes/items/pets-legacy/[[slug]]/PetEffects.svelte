<script>
  // @ts-nocheck
  import '$lib/style.css';

  export let pet;
</script>

<h2>Pet Skills</h2>
{#if pet.Effects && pet.Effects.length > 0}
<table>
  <thead>
    <tr>
      <th>Effect</th>
      <th>Upkeep</th>
      <th>Level</th>
      <th>Cost</th>
      <th>Criteria</th>
    </tr>
  </thead>
  <tbody>
    {#each pet.Effects as effect}
    <tr>
      <td>{effect.Properties.Strength ?? ''}{effect.Properties.Unit ?? ''} {effect.Name}</td>
      <td>{effect.Properties.NutrioConsumptionPerHour ?? 'N/A'}/h</td>
      <td>{effect.Properties.Unlock.Level ?? 'N/A'}</td>
      <td>
        {effect.Properties.Unlock.CostPED != null ? `${effect.Properties.Unlock.CostPED} PED` : 'N/A'}
        {@html effect.Properties.Unlock.CostEssence != null ? `<br />${effect.Properties.Unlock.CostEssence} Animal Essence` : ''}
        {@html effect.Properties.Unlock.CostRareEssence != null ? `<br />${effect.Properties.Unlock.CostRareEssence} Rare Animal Essence` : ''}
      </td>
      <td>
        {effect.Properties.Unlock.Criteria != null ? effect.Properties.Unlock.Criteria : 'N/A'}
        {@html effect.Properties.Unlock.CriteriaValue != null ? `<br />Amount needed: ${effect.Properties.Unlock.CriteriaValue}` : ''}
      </td>
    </tr>
    {/each}
  </tbody>
</table>
{:else}
<br />
<div>No data available.</div>
{/if}