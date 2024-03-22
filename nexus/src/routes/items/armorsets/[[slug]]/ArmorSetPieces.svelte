<script>
// @ts-nocheck
  import { addItemTag, groupBy } from "$lib/util";
  
  import '$lib/style.css';

  import Table from "$lib/components/Table.svelte";

  export let armorSet;

  const slots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];

  let malePieces = [];
  let femalePieces = [];

  $: {
    malePieces = (armorSet?.Armors ?? []).reduce((acc, piece) => {
      acc[piece.Properties.Slot] = piece;
      return acc;
    }, {});
    femalePieces = (armorSet?.Armors ?? []).reduce((acc, piece) => {
      acc[piece.Properties.Slot] = piece;
      return acc;
    }, {});
  }
</script>

<div style="font-size: 32px">Set Pieces</div>
<Table
  header={
    {
      values: ['Slot', 'Male', 'Female', 'TT', 'Weight'],
      widths: ['max-content', 'max-content', 'max-content', 'max-content', 'max-content']
    }
  }
  data={
    slots.map(slot => {
      return {
        values: [
          slot,
          malePieces[slot]?.Name ? addItemTag(malePieces[slot].Name, 'M') : 'N/A',
          malePieces[slot]?.Name ? addItemTag(femalePieces[slot].Name, 'F') : 'N/A',
          malePieces[slot]?.Properties.Economy.MaxTT ?? 'N/A',
          malePieces[slot]?.Properties.Weight ?? 'N/A'
        ]
      }
    })
  }/>
{#if armorSet?.EffectsOnSetEquip?.length > 0}
<div style="font-size: 32px">Set Effects</div>
<Table
  header={
    {
      values: ['Piece Count', 'Effect', 'Value'],
      widths: ['max-content', 'max-content', 'max-content']
    }
  }
  data={
    Object.entries(groupBy(armorSet.EffectsOnSetEquip, x => x.Values.MinSetPieces)).flatMap(([pieceCount, effects]) => {
      return effects.map(effect => {
        return {
          values: [
            effect.Values.MinSetPieces,
            effect.Name,
            effect.Values.Strength
          ],
          spans: [effects.length, null]
        }
      })
    })
  }
  options={
    {
      sortable: false
    }
  }/>
{/if}
