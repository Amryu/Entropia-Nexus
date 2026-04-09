<!--
  @component ProfitabilityDetailView
  Detailed 1-on-1 comparison of a selected (L) weapon vs a selected base weapon.
  Shows cost analysis, efficiency analysis, damage analysis, and net result.
-->
<script>
  // @ts-nocheck
  import { analyzeWeaponProfitability, formatPED, formatPct, formatNumber } from './weaponProfitability.js';

  let {
    baseWeapons = [],
    comparisonWeapons = [],
    baseStats = [],
    compStats = [],
    allAnalyses = [],
    entities = {},
    selectedBaseIndex = $bindable(0),
    selectedCompIndex = $bindable(0),
    mobHP = $bindable(null)
  } = $props();

  let safeBaseIdx = $derived(Math.min(Math.max(0, selectedBaseIndex), baseWeapons.length - 1));
  let safeCompIdx = $derived(Math.min(Math.max(0, selectedCompIndex), comparisonWeapons.length - 1));

  let analysis = $derived(allAnalyses[safeBaseIdx]?.[safeCompIdx] ?? null);
  let base = $derived(baseStats[safeBaseIdx]);
  let comp = $derived(compStats[safeCompIdx]);

  function fmtPEC(v) {
    return v != null ? v.toFixed(2) + ' PEC' : 'N/A';
  }
  function fmtPED(v) {
    return v != null ? v.toFixed(2) + ' PED' : 'N/A';
  }
  function fmtEff(v) {
    return v != null ? v.toFixed(1) + '%' : 'N/A';
  }
</script>

<div class="detail-view">
  <!-- Selectors -->
  <div class="detail-selectors">
    <label class="selector-label">
      <span>Base:</span>
      <select class="selector" bind:value={selectedBaseIndex}>
        {#each baseWeapons as bw, i}
          <option value={i}>{bw.weaponName || `Base ${i + 1}`}</option>
        {/each}
      </select>
    </label>
    <span class="vs-text">vs</span>
    <label class="selector-label">
      <span>Comparison:</span>
      <select class="selector" bind:value={selectedCompIndex}>
        {#each comparisonWeapons as cw, i}
          <option value={i}>{cw.weaponName || `Weapon ${i + 1}`}</option>
        {/each}
      </select>
    </label>
  </div>

  {#if analysis}
    <!-- Cost Analysis -->
    <div class="detail-section">
      <h4 class="section-title">Cost Analysis</h4>
      <div class="detail-grid">
        <div class="detail-row">
          <span class="detail-label">Comp total uses</span>
          <span class="detail-value">{formatNumber(analysis.compTotalUses)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">TT cost / use</span>
          <span class="detail-value">{fmtPEC(analysis.compTTCostPerUsePEC)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Total cycle</span>
          <span class="detail-value">{fmtPED(analysis.compTotalCyclePED)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Cost / use (comp, at MU)</span>
          <span class="detail-value">{fmtPEC(analysis.compCostPerUsePEC)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Cost / use (base, at MU)</span>
          <span class="detail-value">{fmtPEC(analysis.baseCostPerUsePEC)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">MU cost / use (comp)</span>
          <span class="detail-value">{fmtPEC(analysis.compPremiumPerUsePEC)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">MU cost / use (base)</span>
          <span class="detail-value">{fmtPEC(analysis.basePremiumPerUsePEC)}</span>
        </div>
        <div class="detail-row highlight">
          <span class="detail-label">Total MU cost diff (over lifetime)</span>
          <span class="detail-value">{fmtPED(analysis.premiumDiffPED)}</span>
        </div>
      </div>
    </div>

    <!-- Efficiency Analysis -->
    <div class="detail-section">
      <h4 class="section-title">Efficiency Analysis</h4>
      <div class="detail-grid">
        <div class="detail-row">
          <span class="detail-label">Base efficiency</span>
          <span class="detail-value">{fmtEff(analysis.baseEfficiency)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Comp efficiency</span>
          <span class="detail-value">{fmtEff(analysis.compEfficiency)}</span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Efficiency delta</span>
          <span class="detail-value {(analysis.efficiencyDelta ?? 0) > 0 ? 'positive' : (analysis.efficiencyDelta ?? 0) < 0 ? 'negative' : ''}">
            {formatPct(analysis.efficiencyDelta)}
          </span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Savings rate (per PED cycled)</span>
          <span class="detail-value">
            {analysis.savingsRate != null ? (analysis.savingsRate >= 0 ? '+' : '') + (analysis.savingsRate * 100).toFixed(4) + '%' : 'N/A'}
          </span>
        </div>
        <div class="detail-row highlight">
          <span class="detail-label">Lifetime efficiency savings</span>
          <span class="detail-value {(analysis.efficiencySavingsPED ?? 0) > 0 ? 'positive' : (analysis.efficiencySavingsPED ?? 0) < 0 ? 'negative' : ''}">
            {formatPED(analysis.efficiencySavingsPED).text}
          </span>
        </div>
      </div>
    </div>

    <!-- Damage / Kill Analysis (informational) -->
    <div class="detail-section">
      <h4 class="section-title">Damage Analysis <span class="info-tag">informational</span></h4>
      <div class="detail-grid">
        <div class="detail-row">
          <span class="detail-label">DPP (base / comp)</span>
          <span class="detail-value">
            {analysis.baseDPP != null ? analysis.baseDPP.toFixed(2) : 'N/A'}
            /
            {analysis.compDPP != null ? analysis.compDPP.toFixed(2) : 'N/A'}
            {#if analysis.dppDiffPct != null}
              <span class="{analysis.dppDiffPct > 0 ? 'positive' : analysis.dppDiffPct < 0 ? 'negative' : ''}">
                ({formatPct(analysis.dppDiffPct)})
              </span>
            {/if}
          </span>
        </div>
        <div class="detail-row">
          <span class="detail-label">DPS (base / comp)</span>
          <span class="detail-value">
            {analysis.baseDPS != null ? analysis.baseDPS.toFixed(1) : 'N/A'}
            /
            {analysis.compDPS != null ? analysis.compDPS.toFixed(1) : 'N/A'}
            {#if analysis.dpsDiffPct != null}
              <span class="{analysis.dpsDiffPct > 0 ? 'positive' : analysis.dpsDiffPct < 0 ? 'negative' : ''}">
                ({formatPct(analysis.dpsDiffPct)})
              </span>
            {/if}
          </span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Mob HP</span>
          <span class="detail-value">
            <input type="number" min="0" class="mob-hp-inline" placeholder="Optional"
              value={mobHP ?? ''}
              oninput={(e) => { mobHP = e.target.value ? Number(e.target.value) : null; }} />
          </span>
        </div>
        {#if mobHP && mobHP > 0}
          <div class="detail-row">
            <span class="detail-label">Kills / hour (base / comp)</span>
            <span class="detail-value">
              {analysis.baseKillsPerHour != null ? analysis.baseKillsPerHour.toFixed(1) : 'N/A'}
              /
              {analysis.compKillsPerHour != null ? analysis.compKillsPerHour.toFixed(1) : 'N/A'}
            </span>
          </div>
          {#if analysis.extraKillsOverLifetime != null}
            <div class="detail-row">
              <span class="detail-label">Extra kills over lifetime</span>
              <span class="detail-value {analysis.extraKillsOverLifetime > 0 ? 'positive' : analysis.extraKillsOverLifetime < 0 ? 'negative' : ''}">
                {analysis.extraKillsOverLifetime >= 0 ? '+' : ''}{Math.round(analysis.extraKillsOverLifetime)}
              </span>
            </div>
          {/if}
        {/if}
      </div>
    </div>

    <!-- Net Result -->
    <div class="detail-section net-result">
      <h4 class="section-title">Net Result</h4>
      <div class="detail-grid">
        <div class="detail-row">
          <span class="detail-label">Efficiency savings</span>
          <span class="detail-value positive">
            {formatPED(analysis.efficiencySavingsPED).text}
          </span>
        </div>
        <div class="detail-row">
          <span class="detail-label">MU cost differential</span>
          <span class="detail-value negative">
            {analysis.premiumDiffPED != null ? (analysis.premiumDiffPED > 0 ? '-' : '+') + Math.abs(analysis.premiumDiffPED).toFixed(2) + ' PED' : 'N/A'}
          </span>
        </div>
        <div class="detail-row result-row">
          <span class="detail-label">NET PROFITABILITY</span>
          <span class="detail-value result-value {(analysis.netProfitabilityPED ?? 0) > 0.005 ? 'positive' : (analysis.netProfitabilityPED ?? 0) < -0.005 ? 'negative' : 'neutral'}">
            {formatPED(analysis.netProfitabilityPED).text}
          </span>
        </div>
        <div class="detail-row">
          <span class="detail-label">Break-even markup</span>
          <span class="detail-value break-even">
            {analysis.breakEvenMU != null ? analysis.breakEvenMU.toFixed(1) + '%' : 'N/A'}
          </span>
        </div>
      </div>
    </div>
  {:else}
    <p class="no-data">Select both a base weapon and a comparison weapon to see the analysis.</p>
  {/if}
</div>

<style>
  .detail-view {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .detail-selectors {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .selector-label {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: var(--text-muted);
  }

  .selector {
    padding: 5px 8px;
    font-size: 13px;
    background: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    max-width: 220px;
  }

  .vs-text {
    font-size: 13px;
    color: var(--text-muted);
    font-weight: 500;
  }

  .detail-section {
    background: var(--secondary-color);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px 16px;
  }

  .section-title {
    margin: 0 0 10px 0;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .info-tag {
    font-size: 10px;
    font-weight: 400;
    text-transform: none;
    letter-spacing: 0;
    color: var(--text-muted);
    background: var(--bg-color);
    padding: 2px 6px;
    border-radius: 3px;
    margin-left: 6px;
  }

  .detail-grid {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
    font-size: 13px;
  }

  .detail-row.highlight {
    padding: 6px 8px;
    background: var(--bg-color);
    border-radius: 4px;
    font-weight: 500;
  }

  .detail-label {
    color: var(--text-muted);
  }

  .detail-value {
    color: var(--text-color);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .detail-value.positive { color: var(--success-color, #27ae60); }
  .detail-value.negative { color: var(--danger-color, #e74c3c); }
  .positive { color: var(--success-color, #27ae60); }
  .negative { color: var(--danger-color, #e74c3c); }

  .net-result {
    border-color: var(--accent-color);
    border-width: 2px;
  }

  .result-row {
    padding: 8px 10px;
    background: var(--bg-color);
    border-radius: 6px;
    margin-top: 4px;
  }

  .result-row .detail-label {
    font-weight: 700;
    color: var(--text-color);
    font-size: 14px;
  }

  .result-value {
    font-size: 16px;
    font-weight: 700;
  }

  .break-even {
    font-weight: 600;
    color: var(--accent-color);
  }

  .mob-hp-inline {
    width: 80px;
    padding: 3px 6px;
    font-size: 12px;
    background: var(--bg-color);
    border: 1px solid var(--border-color);
    border-radius: 4px;
    color: var(--text-color);
    text-align: right;
  }

  .mob-hp-inline:focus {
    border-color: var(--accent-color);
    outline: none;
  }

  .no-data {
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
    padding: 24px;
  }

  @media (max-width: 768px) {
    .detail-selectors {
      flex-direction: column;
      align-items: flex-start;
    }

    .vs-text {
      display: none;
    }
  }
</style>
