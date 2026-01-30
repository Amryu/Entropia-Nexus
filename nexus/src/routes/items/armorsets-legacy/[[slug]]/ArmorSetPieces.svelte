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
    malePieces = {};
    armorSet?.Armors.forEach(x => {
      let armor = x.find(y => ['Both', 'Male'].includes(y.Properties.Gender));
      
      if (armor) {
        malePieces[armor.Properties.Slot] = armor;
      }
    });
    femalePieces
    armorSet?.Armors.forEach(x => {
      let armor = x.find(y => ['Both', 'Female'].includes(y.Properties.Gender));

      if (armor) {
        femalePieces[armor.Properties.Slot] = armor;
      }
    });
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
