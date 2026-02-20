<script>
  export let loadout = null;
  export let stats = {};
  export let shareCode = null;
  export let title = 'Loadout Overview';

  const armorSlots = ['Head', 'Torso', 'Arms', 'Hands', 'Legs', 'Shins', 'Feet'];
  const isRingSlot = (slot) => /ring|finger/i.test(slot || '');
  const encode = (value) => encodeURIComponent(value || '');

  function getEquipmentLink(kind, name) {
    if (!name) return null;
    switch (kind) {
      case 'weapon':
        return `/items/weapons/${encode(name)}`;
      case 'armor':
        return `/items/armors/${encode(name)}`;
      case 'armorset':
        return `/items/armorsets/${encode(name)}`;
      case 'clothing':
        return `/items/clothing/${encode(name)}`;
      case 'pet':
        return `/items/pets/${encode(name)}`;
      case 'healingtool':
        return `/items/medicaltools/${encode(name)}`;
      default:
        return null;
    }
  }

  function formatStat(value, digits = 1, suffix = '') {
    if (value == null || Number.isNaN(value)) return 'N/A';
    return `${Number(value).toFixed(digits)}${suffix}`;
  }

  function formatList(values) {
    const list = (values || []).filter(Boolean);
    if (!list.length) return '-';
    if (list.length <= 2) return list.join(', ');
    return `${list[0]}, ${list[1]} +${list.length - 2}`;
  }

  function getArmorLabel() {
    if (!loadout?.Gear?.Armor) return '-';
    if (!loadout.Gear.Armor.ManageIndividual && loadout.Gear.Armor.SetName) {
      return loadout.Gear.Armor.SetName;
    }
    const pieces = armorSlots
      .map(slot => loadout?.Gear?.Armor?.[slot]?.Name)
      .filter(Boolean);
    return formatList(pieces);
  }

  function getRing(side) {
    const list = loadout?.Gear?.Clothing || [];
    if (side) {
      return list.find(item => isRingSlot(item?.Slot) && item?.Side === side) || null;
    }
    return list.find(item => isRingSlot(item?.Slot)) || null;
  }

  $: leftRing = getRing('Left');
  $: rightRing = getRing('Right');
  $: armorLabel = getArmorLabel();
  $: weaponLabel = loadout?.Gear?.Weapon?.Name || '-';
  $: petLabel = loadout?.Gear?.Pet?.Name || '-';
  $: weaponLink = getEquipmentLink('weapon', loadout?.Gear?.Weapon?.Name);
  $: petLink = getEquipmentLink('pet', loadout?.Gear?.Pet?.Name);
  $: leftRingLink = getEquipmentLink('clothing', leftRing?.Name);
  $: rightRingLink = getEquipmentLink('clothing', rightRing?.Name);
  $: armorLink = loadout?.Gear?.Armor?.ManageIndividual
    ? null
    : getEquipmentLink('armorset', loadout?.Gear?.Armor?.SetName || loadout?.Gear?.Armor?.Name);
  $: healingLabel = loadout?.Gear?.Healing?.Name || '-';
  $: healingLink = getEquipmentLink('healingtool', loadout?.Gear?.Healing?.Name);
  $: encodedShareCode = shareCode ? encodeURIComponent(shareCode) : null;
</script>

<div class="compact-embed">
  <div class="embed-header">
    <div class="embed-title">{title}</div>
    {#if encodedShareCode}
      <a class="share-link" href={`/tools/loadouts/${encodedShareCode}`} title="Open loadout">View Loadout</a>
    {/if}
  </div>
  <div class="stat-rows stats-section tier-1">
    <div class="stat-row primary">
      <span class="stat-label">Efficiency</span>
      <span class="stat-value">{formatStat(stats?.efficiency, 1, '%')}</span>
    </div>
    <div class="stat-row primary">
      <span class="stat-label">DPS</span>
      <span class="stat-value">{formatStat(stats?.dps, 4)}</span>
    </div>
    <div class="stat-row primary">
      <span class="stat-label">DPP</span>
      <span class="stat-value">{formatStat(stats?.dpp, 4)}</span>
    </div>
    <div class="stat-row primary">
      <span class="stat-label">HPS</span>
      <span class="stat-value">{formatStat(stats?.hps, 4)}</span>
    </div>
  </div>
  <div class="gear-list">
    <div class="gear-row">
      <span class="gear-label">Weapon</span>
      {#if weaponLink}
        <a class="gear-value gear-link" href={weaponLink}>{weaponLabel}</a>
      {:else}
        <span class="gear-value">{weaponLabel}</span>
      {/if}
    </div>
    <div class="gear-row">
      <span class="gear-label">Armor</span>
      {#if armorLink}
        <a class="gear-value gear-link" href={armorLink}>{armorLabel}</a>
      {:else}
        <span class="gear-value">{armorLabel}</span>
      {/if}
    </div>
    <div class="gear-row">
      <span class="gear-label">Healing</span>
      {#if healingLink}
        <a class="gear-value gear-link" href={healingLink}>{healingLabel}</a>
      {:else}
        <span class="gear-value">{healingLabel}</span>
      {/if}
    </div>
    <div class="gear-row">
      <span class="gear-label">Left Ring</span>
      {#if leftRingLink}
        <a class="gear-value gear-link" href={leftRingLink}>{leftRing?.Name || '-'}</a>
      {:else}
        <span class="gear-value">{leftRing?.Name || '-'}</span>
      {/if}
    </div>
    <div class="gear-row">
      <span class="gear-label">Right Ring</span>
      {#if rightRingLink}
        <a class="gear-value gear-link" href={rightRingLink}>{rightRing?.Name || '-'}</a>
      {:else}
        <span class="gear-value">{rightRing?.Name || '-'}</span>
      {/if}
    </div>
    <div class="gear-row">
      <span class="gear-label">Pet</span>
      {#if petLink}
        <a class="gear-value gear-link" href={petLink}>{petLabel}</a>
      {:else}
        <span class="gear-value">{petLabel}</span>
      {/if}
    </div>
  </div>
</div>

<style>
  .compact-embed {
    position: relative;
    background: var(--bg-color, #111);
    border: 1px solid var(--border-color, #444);
    border-radius: 14px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .embed-header {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .embed-title {
    font-weight: 600;
    font-size: 14px;
  }

  .share-link {
    font-size: 12px;
    color: var(--accent-color, #4a9eff);
    margin-left: auto;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #333);
    background: rgba(255, 255, 255, 0.03);
    transition: background 0.15s ease, border-color 0.15s ease;
  }

  .share-link:hover {
    background: var(--hover-color);
    border-color: var(--accent-color);
  }

  .stat-rows {
    padding: 12px;
    background-color: var(--bg-color, var(--primary-color));
    border-radius: 6px;
  }

  .stats-section.tier-1 {
    background-color: var(--bg-color, var(--primary-color));
    border: 1px solid var(--accent-color);
  }

  .stats-section.tier-1 .stat-row.primary {
    background-color: var(--hover-color);
    border-radius: 4px;
    padding: 6px 10px;
    margin-bottom: 6px;
  }

  .stats-section.tier-1 .stat-row.primary:last-child {
    margin-bottom: 0;
  }

  .stats-section.tier-1 .stat-label {
    color: var(--text-muted);
    font-size: 12px;
    text-transform: uppercase;
    font-weight: 600;
  }

  .stats-section.tier-1 .stat-value {
    color: var(--text-color);
    font-size: 16px;
    font-weight: 700;
  }

  .gear-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .gear-row {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    font-size: 12px;
  }

  .gear-label {
    color: var(--text-muted, #999);
  }

  .gear-value {
    text-align: right;
    max-width: 160px;
  }

  .gear-link {
    color: var(--accent-color, #4a9eff);
  }
</style>

