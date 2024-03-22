<script>
  // @ts-nocheck
  import { clampDecimals, getItemLink } from '$lib/util';

  import '$lib/style.css';

  export let blueprint;

  let markup;

  $: if (blueprint) resetMarkup();

  function resetMarkup() {
    markup = new Array(blueprint.Materials?.length ?? 0).fill(100);
  }
</script>

<div class="title">Construction</div>
<table>
  <thead>
    <tr>
      <th>Ingredient</th>
      <th>Amount</th>
      <th>TT</th>
      <th>Markup (%)</th>
      <th>Total</th>
    </tr>
  </thead>
  <tbody>
    {#each blueprint.Materials ?? [] as material, index}
    <tr>
      <td><a href='{getItemLink(material.Item)}'>{material.Item.Name}</a></td>
      <td>{material.Amount}</td>
      <td>{clampDecimals(material.Item.Properties?.Economy.MaxTT, 2, 8)} PED</td>
      <td><input type="number" bind:value={markup[index]} step=0.01 /></td>
      <td>{clampDecimals(material.Amount * material.Item.Properties?.Economy.MaxTT * (markup[index] / 100), 2, 8)} PED</td>
    </tr>
    {/each}
    <tr>
      <td colspan=4>Sum:</td>
      <td>{clampDecimals(blueprint.Materials?.map((x, i) => x.Amount * x.Item.Properties?.Economy.MaxTT * (markup[i] / 100)).reduce((acc, val) => acc + val, 0) ?? 0, 2, 8)} PED</td>
    </tr>
  </tbody>
</table>