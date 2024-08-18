<script>
// @ts-nocheck
  import { clampDecimals } from "$lib/util";
  import { genericMats, weaponMats, armorMats, medicalToolMats, finderMats, excavatorMats, matValues } from '$lib/tieringUtil.js';
  
  import '$lib/style.css';

  export let tieringInfo;
  export let setPieceCount = 1;

  const allMaterials1 = [...weaponMats.Material1, ...armorMats.Material1, ...medicalToolMats.Material1, ...finderMats.Material1, ...excavatorMats.Material1];
  const allMaterials2 = [...weaponMats.Material2, ...armorMats.Material2, ...medicalToolMats.Material2, ...finderMats.Material2, ...excavatorMats.Material2];

  let markup;
  
  $: if(tieringInfo) reset();

  let tier = 1;

  function reset() {
    tier = 1;
    
    if (tieringInfo && tieringInfo.length > 0) tieringInfo = extrapolate(tieringInfo);

    markup = [[], [], [], [], [], [], [], [], [], []];

    tieringInfo.forEach(x => {
      x.Materials.forEach(y => {
        markup[x.Properties.Tier - 1].push(100);
      });
    });

    tieringInfo.forEach(x => {
      // get material from list matching Tier X Component (X = 1-10)
      let tierComponent = x.Materials.find(y => y.Material.Properties.Type === 'Enhancer Component');
      let pileOfGems = x.Materials.find(y => y.Material.Properties.Type === 'Precious Stones');
      let fragment = x.Materials.find(y => y.Material.Properties.Type === 'Fragment');
      let material1 = x.Materials.find(y => allMaterials1.includes(y.Material.Name));
      let material2 = x.Materials.find(y => allMaterials2.includes(y.Material.Name));

      if (tierComponent && pileOfGems && fragment && material1 && material2) {
        x.Materials = [tierComponent, pileOfGems, fragment, material1, material2];
      }
    });
  }

  function extrapolate(info) {
    let testTier = info.reduce((prev, current) => {
      return (prev.Properties.Tier > current.Properties.Tier) ? prev : current;
    });

    const materials = [weaponMats, armorMats, medicalToolMats, finderMats, excavatorMats];
    let mats = materials.find(mat => 
      testTier.Materials.find(x => mat.Material1.includes(x.Material.Name)) &&
      testTier.Materials.find(x => mat.Material2.includes(x.Material.Name))
    );

    if (!mats) {
      return info;
    }

    mats = {
      Components: genericMats.Components,
      Gems: genericMats.Gems,
      Fragments: genericMats.Fragments,
      Material1: mats.Material1,
      Material2: mats.Material2,
    };

    const match = testTier.Name.match(/^(.*?)(?=Tier [1-9]|Tier 10)/);
    let name = match[1].trim();

    let minBlazar = Math.round(testTier.Materials.find(x => x.Material.Name === 'Blazar Fragment').Amount / testTier.Properties.Tier);

    let minMats = {
      Components: testTier.Materials.find(y => y.Material.Properties.Type === 'Enhancer Component'),
      Gems: testTier.Materials.find(y => y.Material.Properties.Type === 'Precious Stones'),
      Fragments: testTier.Materials.find(y => y.Material.Properties.Type === 'Fragment'),
      Material1: testTier.Materials.find(y => allMaterials1.includes(y.Material.Name)),
      Material2: testTier.Materials.find(y => allMaterials2.includes(y.Material.Name)),
    }

    let blazarCount = testTier.Materials.find(x => x.Material.Name === 'Blazar Fragment').Amount;

    let minMatValues = Object.keys(minMats).reduce((acc, key) => {
      acc[key] = (minMats[key].Amount * minMats[key].Material.Properties.Economy.MaxTT) / blazarCount;
      return acc;
    }, {});

    for (let i = 1; i <= 10; i++) {
      let tier = info.find(x => x.Properties.Tier === i);

      if (!tier || tier.Materials.length !== 5) {
        let newTier = {
          Name: `${name} Tier ${i}`,
          Properties: {
            Tier: i,
            IsArmorSet: mats === armorMats,
            IsExtrapolated: true,
          },
          Materials: ['Components', 'Gems', 'Fragments', 'Material1', 'Material2'].map(type => ({
            Material: {
              Name: mats[type][i - 1],
              Properties: {
                Type: type === 'Components' ? 'Enhancer Component' : type === 'Gems' ? 'Precious Stones' : type === 'Fragments' ? 'Fragment' : null,
                Economy: {
                  MaxTT: matValues[mats[type][i - 1]],
                }
              }
            },
            Amount: Math.round((minMatValues[type] * minBlazar * i) / matValues[mats[type][i - 1]]),
          }))
        };

        info.push(newTier);
      }
    }

    return info;
  }

  let fullSet = false;

  let costCurrentTier = 0;
  let costUpToThisTier = 0;

  let costCurrentTierWithoutMarkup = 0;
  let costUpToThisTierWithoutMarkup = 0;

  $: if(markup && tier) updateTierCosts();

  function updateTierCosts() {
    if(tieringInfo && tieringInfo.find(x => x.Properties.Tier === tier) !== undefined) {
      costCurrentTier = tieringInfo.find(x => x.Properties.Tier === tier).Materials.reduce((acc, cur, index) => {
        return acc + cur.Material.Properties.Economy.MaxTT * cur.Amount * markup[tier - 1][index] / 100;
      }, 0).toFixed(2);

      costCurrentTierWithoutMarkup = tieringInfo.find(x => x.Properties.Tier === tier).Materials.reduce((acc, cur) => {
        return acc + cur.Material.Properties.Economy.MaxTT * cur.Amount;
      }, 0).toFixed(2);
    }
    else {
      costCurrentTier = null;
    }
    
    let tieringInfoSorted = tieringInfo.sort((a, b) => a.Properties.Tier - b.Properties.Tier);

    if(tieringInfoSorted.filter(x => x.Properties.Tier <= tier).length === tier) {
      costUpToThisTier = tieringInfoSorted.slice(0, tier).reduce((acc, cur) => {
        return acc + cur.Materials.reduce((acc2, cur2, index) => {
          return acc2 + cur2.Material.Properties.Economy.MaxTT * cur2.Amount * markup[cur.Properties.Tier - 1][index] / 100;
        }, 0);
      }, 0).toFixed(2);

      costUpToThisTierWithoutMarkup = tieringInfoSorted.slice(0, tier).reduce((acc, cur) => {
        return acc + cur.Materials.reduce((acc2, cur2) => {
          return acc2 + cur2.Material.Properties.Economy.MaxTT * cur2.Amount;
        }, 0);
      }, 0).toFixed(2);
    }
    else {
      costUpToThisTier = null;
    }
  }
</script>

<style>
  .button-container {
    display: flex;
  }

  .square-button {
    width: 40px;
    height: 40px;
    background-color: var(--primary-color);
    border: none;
    margin-right: 5px;
  }

  .square-button:not([disabled]):hover {
    cursor: pointer;
    background-color: var(--hover-color);
  }

  .square-button:not([disabled]).selected {
    border: 1px solid var(--text-color);
    background-color: var(--secondary-color);
  }
</style>

<h2>Tiering</h2>
<br />

<div class="button-container">
  {#each Array.from({ length: 10 }, (_, i) => i + 1) as number}
    <button class="square-button {tier === number ? 'selected' : ''}" on:click={() => tier = number} disabled='{(!tieringInfo || !tieringInfo.find(x => x.Properties.Tier === number) ? 'disabled' : '')}'>{number}</button>
  {/each}
</div>
<br />
{#if tieringInfo && tieringInfo.find(x => x.Properties.Tier === tier) !== undefined}
<table>
  <thead>
    <tr>
      <th>Material</th>
      <th>TT</th>
      <th>Amount</th>
      <th>Markup (%)</th>
      <th>Cost</th>
    </tr>
  </thead>
  {#each tieringInfo.find(x => x.Properties.Tier === tier).Materials as material, index}
  <tr>
    <td>{material.Material.Name}</td>
    <td>{clampDecimals(material.Material.Properties.Economy.MaxTT, 2, 8)}</td>
    <td>{material.Amount}</td>
    <td><input type="number" bind:value={markup[tier - 1][index]} step="0.1" style="width: 70px;" /></td>
    <td>{clampDecimals(material.Material.Properties.Economy.MaxTT * material.Amount * markup[tier - 1][index] / 100, 2, 8)}</td>
  </tr>
  {/each}
</table>
{#if tieringInfo.find(x => x.Properties.Tier === tier).Properties.IsExtrapolated}
<span style="color: red" title="This data was based on another tier and these values should be within 99% of the real values, if the provided tier was accurate. I still do not provide any guarantees that this data is correct!">!! Extrapolated data !!</span>
{/if}
{:else}
There is no information about this tier available.<br />
{/if}

<br />
<table>
  <thead>
    <tr>
      <th>{#if setPieceCount > 1}Full Set <input type="checkbox" bind:checked={fullSet} />{/if}</th>
      <th>TT</th>
      <th>MU</th>
      <th>TT+MU</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Current Tier: </td>
      <td>{costCurrentTier ? (costCurrentTierWithoutMarkup * (fullSet ? setPieceCount : 1)).toFixed(2) : 'N/A'} PED</td>
      <td>{costCurrentTier ? ((costCurrentTier - costCurrentTierWithoutMarkup) * (fullSet ? setPieceCount : 1)).toFixed(2) : 'N/A'} PED</td>
      <td>{costCurrentTier ? (costCurrentTier * (fullSet ? setPieceCount : 1)).toFixed(2) : 'N/A'} PED</td>
    </tr>
    <tr>
      <td>Up To This Tier: </td>
      <td>{costUpToThisTier ? (costUpToThisTierWithoutMarkup * (fullSet ? setPieceCount : 1)).toFixed(2) : 'N/A'} PED</td>
      <td>{costUpToThisTier ? ((costUpToThisTier - costUpToThisTierWithoutMarkup) * (fullSet ? setPieceCount : 1)).toFixed(2) : 'N/A'} PED</td>
      <td>{costUpToThisTier ? (costUpToThisTier * (fullSet ? setPieceCount : 1)).toFixed(2) : 'N/A'} PED</td>
    </tr>
  </tbody>
</table>
