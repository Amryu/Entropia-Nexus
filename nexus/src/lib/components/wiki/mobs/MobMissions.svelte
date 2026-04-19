<!--
  @component MobMissions
  Lists missions that reference this mob in their objectives.
  Uses FancyTable with links to mission pages, item pages, and skill pages.
-->
<script>
  // @ts-nocheck
  import FancyTable from '$lib/components/FancyTable.svelte';
  import '$lib/style.css';
  import { encodeURIComponentSafe } from '$lib/util';

  let { missions = [] } = $props();

  const OBJECTIVE_LABELS = {
    KillCount: 'Kill',
    KillCycle: 'Kill Cycle',
    AIKillCycle: 'AI Kill Cycle'
  };

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatPed(value) {
    if (value == null) return '';
    const num = Number(value);
    if (!Number.isFinite(num)) return '';
    return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function formatAmount(objectives) {
    if (!objectives?.length) return '';
    const parts = [];
    for (const obj of objectives) {
      const p = obj?.Payload || {};
      if (obj.Type === 'KillCount') {
        const total = p.totalCountRequired;
        if (total != null) {
          parts.push(p.useKillPoints ? `${total} pts` : `${total}\u00d7`);
        }
      } else if (obj.Type === 'KillCycle' || obj.Type === 'AIKillCycle') {
        const ped = p.pedToCycle;
        if (ped != null) parts.push(`${formatPed(ped)} PED`);
      }
    }
    return parts.join(' + ');
  }

  function formatObjectiveType(objectives) {
    if (!objectives?.length) return '';
    const types = [...new Set(objectives.map(o => OBJECTIVE_LABELS[o.Type] || o.Type))];
    return types.join(', ');
  }

  function formatRewards(rewards) {
    if (!rewards) return '<span class="reward-empty">-</span>';
    const items = rewards.Items || [];
    const skills = rewards.Skills || [];
    const unlocks = rewards.Unlocks || [];

    // Handle choice mode (Items is array of packages)
    const isChoices = items.length > 0 && items[0]?.Items !== undefined;
    const packages = isChoices ? items : [{ Items: items, Skills: skills, Unlocks: unlocks }];

    const parts = [];
    packages.forEach((pkg, idx) => {
      const pkgParts = [];
      for (const item of (pkg.Items || [])) {
        const name = escapeHtml(item.itemName || `Item #${item.itemId}`);
        const qty = item.quantity != null && item.quantity !== 1 ? `${item.quantity}\u00d7&nbsp;` : '';
        if (item.itemId) {
          pkgParts.push(`${qty}<a href="/items/${item.itemId}" class="wiki-link">${name}</a>`);
        } else {
          pkgParts.push(`${qty}${name}`);
        }
      }
      for (const skill of (pkg.Skills || [])) {
        const name = skill.skillName;
        const ped = skill.pedValue ? ` (+${formatPed(skill.pedValue)} PED)` : '';
        if (name) {
          pkgParts.push(`<a href="/information/skills/${encodeURIComponentSafe(name)}" class="wiki-link">${escapeHtml(name)}</a>${ped}`);
        } else {
          pkgParts.push(`<span>Skill #${skill.skillItemId}</span>${ped}`);
        }
      }
      for (const unlock of (pkg.Unlocks || [])) {
        pkgParts.push(`<span class="reward-unlock">${escapeHtml(unlock)}</span>`);
      }
      if (pkgParts.length) {
        const prefix = isChoices && packages.length > 1 ? `<span class="reward-choice">Choice ${idx + 1}:</span> ` : '';
        parts.push(prefix + pkgParts.join(', '));
      }
    });
    return parts.length ? parts.join(' <span class="reward-sep">|</span> ') : '<span class="reward-empty">-</span>';
  }

  let tableData = $derived((missions || []).map(m => ({
    missionId: m.Id,
    missionName: m.Name,
    missionHref: `/information/missions/${encodeURIComponentSafe(m.Name)}`,
    objectiveType: formatObjectiveType(m.MatchingObjectives),
    amount: formatAmount(m.MatchingObjectives),
    rewardsHtml: formatRewards(m.Rewards),
    chainName: m.MissionChain?.Name || '',
    chainHref: m.MissionChain?.Name
      ? `/information/missions/${encodeURIComponentSafe(m.MissionChain.Name)}?view=chains`
      : null
  })));

  const columns = [
    {
      key: 'missionName',
      header: 'Mission',
      main: true,
      sortable: true,
      width: '200px',
      mobileWidth: '140px',
      formatter: (value, row) => `<a href="${row.missionHref}" class="wiki-link mission-name-link">${escapeHtml(value)}</a>`
    },
    {
      key: 'objectiveType',
      header: 'Objective',
      sortable: true,
      widthBasis: 'both'
    },
    {
      key: 'amount',
      header: 'Amount',
      sortable: false,
      widthBasis: 'both'
    },
    {
      key: 'rewardsHtml',
      header: 'Rewards',
      sortable: false,
      width: '320px',
      mobileWidth: '180px',
      cellClass: () => 'rewards-cell'
    },
    {
      key: 'chainName',
      header: 'Chain',
      sortable: true,
      hideOnMobile: true,
      formatter: (value, row) => value
        ? `<a href="${row.chainHref}" class="wiki-link">${escapeHtml(value)}</a>`
        : '<span style="color: var(--text-muted);">-</span>'
    }
  ];
</script>

<div class="missions-table-container">
  <FancyTable
    {columns}
    data={tableData}
    searchable={tableData.length > 15}
    sortable={true}
    rowHeight={36}
    compact
    fitContent
    emptyMessage="No missions reference this mob."
  />
</div>

<style>
  .missions-table-container {
    width: 100%;
    max-width: 100%;
    overflow: hidden;
  }

  .missions-table-container :global(.fancy-table-container) {
    max-height: 596px;
  }

  .missions-table-container :global(.mission-name-link) {
    font-weight: 500;
  }

  .missions-table-container :global(.rewards-cell) {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }

  .missions-table-container :global(.reward-choice) {
    color: var(--text-muted);
    font-size: 11px;
    margin-right: 4px;
  }

  .missions-table-container :global(.reward-unlock) {
    color: var(--accent-color, #22c55e);
  }

  .missions-table-container :global(.reward-empty),
  .missions-table-container :global(.reward-sep) {
    color: var(--text-muted);
  }

  .missions-table-container :global(.reward-sep) {
    margin: 0 2px;
  }

  @media (max-width: 899px) {
    .missions-table-container :global(.fancy-table-container) {
      max-height: 499px;
    }
  }

  .missions-table-container :global(.mission-name-link) {
    display: inline-block;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }
</style>
