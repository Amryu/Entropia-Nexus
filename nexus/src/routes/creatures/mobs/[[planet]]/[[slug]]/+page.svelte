<script lang="ts">
  // @ts-nocheck
  import '$lib/style.css';

  import EntityViewer from "$lib/components/EntityViewer.svelte";
  import Codex from './Codex.svelte';
  import Loots from './Loots.svelte';
  import Maturities from './Maturities.svelte';

  export let data;

  const navButtonInfo = [
    {
      Label: 'Cly',
      Title: 'Calypso',
      Type: 'calypso',
    },
    {
      Label: 'Cyr',
      Title: 'Cyrene',
      Type: 'cyrene',
    },
    {
      Label: 'Ark',
      Title: 'Arkadia',
      Type: 'arkadia',
    },
    {
      Label: 'Mnr',
      Title: 'Monria',
      Type: 'monria',
    },
    {
      Label: 'Rck',
      Title: 'ROCKtropia',
      Type: 'rocktropia',
    },
    {
      Label: 'Tou',
      Title: 'Toulan',
      Type: 'toulan',
    },
    {
      Label: 'NI',
      Title: 'Next Island',
      Type: 'nextisland',
    }
  ]

  function getDamageSpread(mob, name) {
    let attackSpreads = mob.Maturities.map(x => {
      let attack = x.Attacks.find(y => y.Name === name)

      if (attack == null) return null;

      let total = attack.Impact + attack.Cut + attack.Stab + attack.Penetration + attack.Shrapnel + attack.Burn + attack.Cold + attack.Acid + attack.Electric;

      return {
        Impact: attack.Impact / total,
        Cut: attack.Cut / total,
        Stab: attack.Stab / total,
        Penetration: attack.Penetration / total,
        Shrapnel: attack.Shrapnel / total,
        Burn: attack.Burn / total,
        Cold: attack.Cold / total,
        Acid: attack.Acid / total,
        Electric: attack.Electric / total,
      }
    }).filter(x => x != null).flat();

    if (attackSpreads.length === 0) return null;

    return {
      Impact: attackSpreads.map(x => x.Impact).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Cut: attackSpreads.map(x => x.Cut).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Stab: attackSpreads.map(x => x.Stab).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Penetration: attackSpreads.map(x => x.Penetration).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Shrapnel: attackSpreads.map(x => x.Shrapnel).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Burn: attackSpreads.map(x => x.Burn).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Cold: attackSpreads.map(x => x.Cold).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Acid: attackSpreads.map(x => x.Acid).reduce((a, b) => a + b, 0) / attackSpreads.length,
      Electric: attackSpreads.map(x => x.Electric).reduce((a, b) => a + b, 0) / attackSpreads.length,
    }
  }

  let propertiesDataFunction = (mob) => {
    let primaryDamageSpread = getDamageSpread(mob, 'Primary');

    return {
      General: {
        Species: {
          Value: mob.Species?.Name ?? 'N/A',
          Tooltip: 'The Codex entry name for this mob. Mobs with the same species will progress the same codex.'
        },
        Planet: mob.Planet?.Name ?? 'N/A',
        Type: mob.ScanningProfession?.Name === 'Animal Investigator'
          ? 'Animal'
          : mob.ScanningProfession?.Name === 'Mutant Investigator'
          ? 'Mutant'
          : mob.ScanningProfession?.Name === 'Robot Investigator'
          ? 'Robot'
          : 'N/A',
        AttacksSpeed: {
          Label: 'Attack Speed',
          Value: mob.Properties?.AttacksPerMinute != null ? (60 /mob.Properties?.AttacksPerMinute).toFixed(2) : 'N/A',
        },
        AttackRange: {
          Label: 'Attack Range',
          Value: mob.Properties?.AttackRange != null ? `${mob.Properties?.AttackRange}m` : 'N/A',
        },
        AggressionRange: {
          Label: 'Aggression Range',
          Value: mob.Properties?.AggressionRange != null ? `${mob.Properties?.AggressionRange}m` : 'N/A',
        },
        VisionRange: {
          Label: 'Vision Range',
          Value: mob.Properties?.VisionRange != null ? `${mob.Properties?.VisionRange}m` : 'N/A',
        },
        Sweatable: {
          Label: 'Sweatable',
          Value: mob.Properties?.IsSweatable ? 'Yes' : 'No',
        },
      },
      Damage: {
        Primary: {
          Label: 'Primary',
          // Find all damage spreads that aren't 0
          Value: primaryDamageSpread != null
            ? Object.entries(primaryDamageSpread).filter(x => x[1] > 0).map(x => `${x[0]}: ${(x[1] * 100).toFixed(1)}%`)
            : 'N/A',
        },
      },
      Skill: {
        Defense: {
          Label: 'Defense',
          Value: mob.DefensiveProfession?.Name ?? 'N/A',
        },
        Scanning: {
          Label: 'Scanning',
          Value: mob.ScanningProfession?.Name ?? 'N/A',
        },
        Looting: {
          Label: 'Looting',
          Value: mob.ScanningProfession?.Name === 'Animal Investigator'
            ? 'Animal Looter'
            : mob.ScanningProfession?.Name === 'Mutant Investigator'
            ? 'Mutant Looter'
            : mob.ScanningProfession?.Name === 'Robot Investigator'
            ? 'Robot Looter'
            : 'N/A',
        },
      }
    };
  };

  let viewInfoSection = {
    columns: ['Name', 'Species', 'Type', 'Planet'],
    columnWidths: ['1fr', '100px', '100px', '150px'],
    rowValuesFunction: (item) => {
      return [
        item.Name,
        item.Species?.Name ?? 'N/A',
        item.ScanningProfession?.Name === 'Animal Investigator'
          ? 'Animal'
          : item.ScanningProfession?.Name === 'Mutant Investigator'
          ? 'Mutant'
          : item.ScanningProfession?.Name === 'Robot Investigator'
          ? 'Robot'
          : 'N/A',
        item.Planet?.Name ?? 'N/A'
      ];
    }
  };

  let tableViewInfo = {
    all: viewInfoSection,
    calypso: viewInfoSection,
    cyrene: viewInfoSection,
    arkadia: viewInfoSection,
    monria: viewInfoSection,
    rocktropia: viewInfoSection,
    toulan: viewInfoSection,
    nextisland: viewInfoSection,
  }
</script>

<EntityViewer
  data={data}
  tableViewInfo={tableViewInfo}
  navButtonInfo={navButtonInfo}
  propertiesDataFunction={propertiesDataFunction}
  title='Mobs'
  basePath='/creatures/mobs'
  let:object
  let:additional>
  <div class="flex-item-double">
    <div class="big-title">{object.Name}</div>
  </div>
  <div class="flex-item">
    <Maturities maturities={object.Maturities} />
  </div>
  <div class="flex-item">
    <Codex baseCost={object.Species?.Properties?.CodexBaseCost} isCat4={object.Species?.Properties?.IsCat4Codex ?? false} />
  </div>
  <div class="flex-item">
    <Loots loots={additional.loots} />
  </div>
</EntityViewer>