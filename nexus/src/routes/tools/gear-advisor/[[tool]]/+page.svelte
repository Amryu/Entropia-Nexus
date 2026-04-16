<!--
  @component Gear Advisor
  Container for a collection of small gear-related calculators, selectable from the sidebar.
  First sub-tool: Armor vs Mob.
-->
<script>
  // @ts-nocheck
  import '$lib/style.css';
  import '../../tools.css';
  import '../gear-advisor.css';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import WikiPage from '$lib/components/wiki/WikiPage.svelte';
  import ArmorVsMob from '../ArmorVsMob.svelte';
  import WeaponProfitability from '../WeaponProfitability.svelte';
  import EffectOptimizer from '../EffectOptimizer.svelte';
  import FishingAdvisor from '../FishingAdvisor.svelte';

  let { data } = $props();

  // Sub-tool registry — add new entries here as more calculators are built
  const SUB_TOOLS = [
    {
      slug: 'armor-vs-mob',
      label: 'Armor vs Mob',
      description: 'Rank armor sets against a target mob (or vice versa).'
    },
    {
      slug: 'weapon-profitability',
      label: '(L) Weapon Profitability',
      description: 'Evaluate (L) weapon purchases based on efficiency savings over their lifetime.'
    },
    {
      slug: 'effect-optimizer',
      label: 'Effect Optimizer',
      description: 'Find optimal equipment to hit effect caps.'
    },
    {
      slug: 'fishing-advisor',
      label: 'Fishing Advisor',
      description: 'Build and compare fishing rigs with rod and attachment stats.'
    }
  ];

  let user = $derived($page.data?.user);
  let drawerOpen = $state(false);

  // Route sub-tool from URL (falls back to the first tool)
  let activeToolSlug = $derived(
    SUB_TOOLS.find(t => t.slug === data.additional?.tool)?.slug ?? SUB_TOOLS[0].slug
  );
  let activeTool = $derived(SUB_TOOLS.find(t => t.slug === activeToolSlug));

  let breadcrumbs = $derived([
    { label: 'Tools', href: '/tools' },
    { label: 'Gear Advisor', href: '/tools/gear-advisor' },
    ...(activeTool ? [{ label: activeTool.label, href: `/tools/gear-advisor/${activeTool.slug}` }] : [])
  ]);

  function selectSubTool(slug) {
    drawerOpen = false;
    goto(`/tools/gear-advisor/${slug}`);
  }
</script>

<svelte:head>
  <title>Gear Advisor - Entropia Nexus</title>
  <meta name="description" content="Collection of small gear-related calculators for Entropia Universe: armor vs mob damage coverage and more." />
  <link rel="canonical" href="https://entropianexus.com/tools/gear-advisor" />
</svelte:head>

<WikiPage
  title="Gear Advisor"
  {breadcrumbs}
  entity={{ Name: 'Gear Advisor' }}
  basePath="/tools/gear-advisor"
  pageClass="tool-gear-advisor"
  navItems={[]}
  bind:drawerOpen
  {user}
  editable={false}
  canEdit={false}
>
  {#snippet sidebar({ isMobile })}
    <div class="sidebar-root">
      <div class="nav-header">
        <h2 class="nav-title">Gear Advisor</h2>
      </div>
      <div class="sidebar-body">
        <div class="subtool-list">
          {#each SUB_TOOLS as tool (tool.slug)}
            <button
              type="button"
              class="subtool-item"
              class:active={tool.slug === activeToolSlug}
              onclick={() => selectSubTool(tool.slug)}
            >
              <span class="subtool-name">{tool.label}</span>
              <span class="subtool-desc">{tool.description}</span>
            </button>
          {/each}
        </div>
      </div>
    </div>
  {/snippet}

  <!-- Main content: routed to the active sub-tool -->
  {#if activeToolSlug === 'armor-vs-mob'}
    <ArmorVsMob
      armorSets={data.additional?.armorSets ?? []}
      armorPlatings={data.additional?.armorPlatings ?? []}
      mobs={data.additional?.mobs ?? []}
    />
  {:else if activeToolSlug === 'weapon-profitability'}
    <WeaponProfitability
      weapons={data.additional?.weapons ?? []}
      weaponAmplifiers={data.additional?.weaponAmplifiers ?? []}
      weaponVisionAttachments={data.additional?.weaponVisionAttachments ?? []}
      absorbers={data.additional?.absorbers ?? []}
      mindforceImplants={data.additional?.mindforceImplants ?? []}
    />
  {:else if activeToolSlug === 'effect-optimizer'}
    <EffectOptimizer
      clothings={data.additional?.clothings ?? []}
      pets={data.additional?.pets ?? []}
      effectsCatalog={data.additional?.effects ?? []}
      armorSets={data.additional?.armorSets ?? []}
      weapons={data.additional?.weapons ?? []}
      weaponAmplifiers={data.additional?.weaponAmplifiers ?? []}
      weaponVisionAttachments={data.additional?.weaponVisionAttachments ?? []}
      absorbers={data.additional?.absorbers ?? []}
      mindforceImplants={data.additional?.mindforceImplants ?? []}
    />
  {:else if activeToolSlug === 'fishing-advisor'}
    <FishingAdvisor
      fishingRods={data.additional?.fishingRods ?? []}
      fishingReels={data.additional?.fishingReels ?? []}
      fishingBlanks={data.additional?.fishingBlanks ?? []}
      fishingLines={data.additional?.fishingLines ?? []}
      fishingLures={data.additional?.fishingLures ?? []}
    />
  {/if}
</WikiPage>
