# Construction Calculator

The construction calculator helps players plan crafting sessions by estimating material requirements, craft attempts needed, and accounting for the game's unique near-success refund mechanics and condition system.

## Overview

The calculator:
1. Takes target blueprints and desired quantities as input
2. Builds a crafting tree including sub-blueprints and craftable materials
3. Estimates craft attempts needed based on hotspot-model success rates and certainty level
4. Calculates material requirements with per-material refund adjustments via Monte Carlo simulation
5. Accounts for blueprint condition (enhancer stacking) with automatic optimization
6. Generates ordered crafting steps and a shopping list

## Hotspot-Based Crafting Model

Crafting outcomes are modeled using empirically-derived value hotspots from KDE lognormal analysis. Each non-fail craft attempt hits one of these hotspots, which determines both the outcome type and the value multiplier.

### Hotspot Definitions

| Multiplier | Weight | Type |
|------------|--------|------|
| 0.20x | 7.8% | Near-success |
| 0.50x | 26.47% | Near-success |
| 0.85x | 20.10% | Near-success |
| 1.10x | 42.82% | Split (4.7% near / 95.3% success) |
| 2.50x | 1.49% | Success |
| 5.00x | 0.68% | Success |
| 10.0x | 0.30% | Success |
| >10x | 0.18% | Success |

Each hotspot has +/-10% variance following a Beta(2,2) distribution.

### Outcome Types

| Outcome | Condition | Result |
|---------|-----------|--------|
| **Success** | Value >= blueprint cost | Produces items |
| **Near-success** | Value < blueprint cost | Partial material refund only |
| **Fail** | Roll failure | Loses all materials, no output |

The **success threshold** is 1.0x blueprint cost. The 1.10x hotspot straddles this threshold: ~4.7% of its variance falls below 1.0x (near-success) while ~95.3% falls above (success).

### Maximum Non-Fail Rates

| Blueprint Type | Max Non-Fail | Min Fail Rate |
|----------------|--------------|---------------|
| **SiB** (Skill Increase Bonus) | 95% | 5% |
| **Non-SiB** | 90% | 10% |

### Success Rate Calculation

Hotspot weights are normalized to 100% of non-fail outcomes:

```
successRate = nonFailChance * (totalSuccessWeight / totalWeight)
nearSuccessRate = nonFailChance * (totalNearSuccessWeight / totalWeight)
failRate = 1 - nonFailChance
```

For a 90% non-fail blueprint (base condition):
- Success rate: ~40.7%
- Near-success rate: ~49.3%
- Fail rate: 10%

## Output Per Success

### Output Range Formula

Each success hotspot produces items based on a dynamically computed output range:

```
effectiveMult = hotspot.multiplier * conditionMultiplier
outputRange = [min(effectiveMult * 0.9, 3), min(effectiveMult * 1.1, 7)]
```

The output range is uniformly distributed, with hard caps at 3 (low) and 7 (high). Product units are computed as:

```
productUnits = floor(outputRangeMult * blueprintCost / productTT)
```

Capped by `MaximumCraftAmount` if set on the blueprint.

### Base Case Output Ranges (condition = 0%)

| Hotspot | Effective Mult | Output Range |
|---------|---------------|--------------|
| 1.10x | 1.10 | [0.99, 1.21] |
| 2.50x | 2.50 | [2.25, 2.75] |
| 5.00x | 5.00 | [3.0, 5.5] |
| 10.0x | 10.0 | [3.0, 7.0] |
| >10x | 15+ | [3.0, 7.0] |

### Weighted Integer Average

Since the game floors output to integers, the calculator computes the expected floored output by weighting each integer bucket by its overlap with the continuous output range. This handles threshold crossings smoothly.

## Condition System

Condition (from enhancer stacking) increases the effective value multiplier of each craft attempt. The condition slider ranges from 0% to 100%.

### Condition Multiplier

The multiplier ranges linearly from 1.0x (0%) to 7.5x (100%).

### What Condition Affects

| Effect | How |
|--------|-----|
| **Output per success** | Higher effective multiplier pushes output range toward caps, producing more items per success |
| **Material refund pool** | Near-success refund pools scale with condition (pool = poolMultiplier * blueprintCost * conditionMult) |
| **Max refund per material** | Each material can be refunded up to `floor(amount * conditionMult)` units |
| **Non-fail chance** | Divided by condition multiplier, increasing fail rate |

The success/near-success **split** does NOT change with condition because both hotspot values and the success threshold scale equally.

### Condition Presets

Global presets apply condition settings to all crafting steps at once:

| Preset | Behavior | Use Case |
|--------|----------|----------|
| **Stability** | Sets all steps to 0% | Highest success rate, lowest output per success |
| **Attempts** | Per-step optimization | Minimizes total craft attempts by balancing output gains against fail rate |
| **Output** (default) | Per-step optimization | Maximizes average output per attempt for best throughput |

The **Output** preset is the default when no condition is explicitly set. It is disabled for blueprints where the product has condition (e.g., items requiring residue) or where `MaximumCraftAmount` is 1, since output optimization is meaningless for single-item outputs.

Each step also has its own condition slider (0-100%) and per-step preset buttons showing the computed optimal values.

## Craft Attempt Estimation

### Negative Binomial Distribution

The calculator uses the negative binomial distribution to estimate attempts needed:

```
successesNeeded = ceil(quantityWanted / avgOutput)
meanAttempts = successesNeeded / successRate
variance = successesNeeded * (1 - successRate) / successRate^2
```

### Certainty Levels

Users can specify a confidence level (50-99%) which adjusts the estimate using z-scores:

| Certainty | Z-Score | Interpretation |
|-----------|---------|----------------|
| 50% | 0 | Mean estimate (50% chance of having enough) |
| 75% | 0.67 | 75% confidence |
| 90% | 1.28 | 90% confidence |
| 95% | 1.65 | 95% confidence |
| 99% | 2.33 | 99% confidence |

```
adjustedAttempts = meanAttempts + (zScore * standardDeviation)
```

Higher certainty = more estimated attempts = safer material buffer.

## Pool-Based Refund System

On near-success, the game generates a refund pool and distributes it among materials. The calculator models this with Monte Carlo simulation.

### How It Works

1. A **near-success hotspot** is chosen (weighted random from the near-success breakdown)
2. A **pool multiplier** is sampled with Beta(2,2) variance around the hotspot's multiplier
3. The **refund pool** = poolMultiplier * blueprintCost * conditionMultiplier
4. Each material **rolls independently** with `rollChance` probability (configurable, default 80%)
5. **Winners are processed in random order** (Fisher-Yates shuffle), consuming from the pool
6. Each winner gets `floor(remaining_pool / unitTT)` units refunded, capped at `floor(amount * conditionMult)`

### Near-Success Hotspot Pool Sources

| Source | Pool Multiplier | Weight |
|--------|----------------|--------|
| 0.20x hotspot | ~0.20x cost | 7.8% |
| 0.50x hotspot | ~0.50x cost | 26.47% |
| 0.85x hotspot | ~0.85x cost | 20.10% |
| 1.10x split (truncated) | ~0.97x cost | ~2.0% |

The 1.10x hotspot's near-success portion uses a truncated Beta(2,2) distribution conditioned on falling below the 1.0x threshold, sampled via inverse CDF with Newton's method.

### Why Processing Order Matters

Consider a blueprint costing 5.00 PED with:
- Material A: 8 x 0.05 PED = 0.40 PED total (cheap)
- Material B: 2 x 2.00 PED = 4.00 PED total (expensive)

Pool roll = 2.31 PED. Both materials win their roll.

**If A processed first:**
- A: floor(2.31 / 0.05) = 46, capped at 8 -> **8 refunded**, pool = 1.91
- B: floor(1.91 / 2.00) = 0 -> **0 refunded**

**If B processed first:**
- B: floor(2.31 / 2.00) = 1 -> **1 refunded**, pool = 0.31
- A: floor(0.31 / 0.05) = 6 -> **6 refunded**

**Result**: Expensive materials consistently receive fewer refunds because they need more pool per unit.

### Monte Carlo Simulation

Due to the complexity of random ordering, hotspot-weighted pools, and partial refunds, the calculator uses Monte Carlo simulation (2000 iterations) with a **seeded PRNG** (Mulberry32) for deterministic results:

- Seed is derived from material composition, roll chance, and condition multiplier
- Same blueprint + settings always produces the same refund estimates
- Each iteration: pick near-success hotspot -> sample pool -> roll materials -> shuffle winners -> process

### Per-Material Multiplier

Each material gets its own multiplier based on simulation results:

```
multiplier = 1 - (nearSuccessRate * refundFraction)
adjustedAmount = ceil(rawAmount * multiplier)
```

Example with 90% non-fail (49.3% near-success rate):
- Material A (cheap): 60% refund fraction -> multiplier = 0.70
- Material B (expensive): 15% refund fraction -> multiplier = 0.926

A **TT-weighted average multiplier** is also computed for summary display and residue adjustment.

## Residue Calculation

Some products require residue (items with condition). Residue required per craft:

```
residuePerClick = productMaxTT - materialCost
totalResidue = residuePerClick * estimatedAttempts
adjustedResidue = totalResidue * weightedMultiplier
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rollChance` | 80% | Per-material refund roll probability |
| `certainty` | 50% | Confidence level for attempt estimation |
| `nonFailChances` | Max per BP | Override non-fail % per blueprint |
| `conditionPercents` | Auto (output) | Condition % per blueprint (0-100) |
| `materialCraftConfig` | {} | Enable/configure sub-material crafting |

## Tree Building

### Node Structure

Each crafting node contains:

```javascript
{
  blueprint,              // The blueprint object
  quantityWanted,         // Desired output quantity
  estimatedAttempts,      // Calculated craft attempts
  avgOutput,              // Average items per success
  avgOutputPerAttempt,    // successRate * avgOutput
  successRate,            // Probability of success per attempt
  nearSuccessRate,        // Probability of near-success per attempt
  failRate,               // Probability of fail per attempt
  nonFailChance,          // Base non-fail percentage
  effectiveNonFailChance, // After condition adjustment
  conditionPercent,       // Condition slider value (0-100)
  conditionMultiplier,    // Computed from conditionPercent
  materialMultiplier,     // Weighted average refund multiplier
  isLimited,              // Whether blueprint is limited (L)
  isSiB,                  // Whether blueprint has SiB
  owned,                  // Whether player owns this blueprint
  materials: [{           // Array of material requirements
    item,
    amountPerAttempt,
    totalAmount,          // Raw: amountPerAttempt * attempts
    adjustedAmount,       // After per-material refund adjustment
    multiplier,           // Per-material multiplier (from simulation)
    refundFraction,       // Expected refund % on near-success
    hasCraftableBlueprint,
    craftableVersions
  }],
  materialChildren,       // Craftable materials (sub-trees)
  depth,
  residuePerClick,
  totalResidue,
  adjustedResidue
}
```

### Recursion

The tree builder recursively processes craftable materials when enabled. Each material that has a matching blueprint can be expanded into its own crafting sub-tree. Circular references are detected via a visited set to prevent infinite loops.

## Output Generation

### Crafting Steps

Steps are generated in **leaf-first order** (post-order traversal):
1. Visit all material children first (dependencies)
2. Then visit current node
3. This ensures materials/sub-products are crafted before they're needed

Each step includes per-step condition controls with its own slider and presets.

### Shopping List

The shopping list aggregates:
- **Materials**: All raw materials needed (with both raw and adjusted amounts)
- **Products to buy**: Final products from unowned unlimited blueprints
- **Limited blueprints**: Limited blueprints that need to be purchased
- **Residue**: Total residue TT required

Materials being crafted via sub-blueprints are excluded from the shopping list.

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `HOTSPOT_VARIANCE` | 0.10 (10%) | Each hotspot varies +/-10%, Beta(2,2) shaped |
| `SUCCESS_THRESHOLD` | 1.0 | Value multiplier threshold for success |
| `MAX_OUTPUT_MULTIPLIER` | 7 | Hard cap on output range high |
| `OUTPUT_RANGE_LOW_CAP` | 3 | Hard cap on output range low |
| `SPLIT_NEAR_SUCCESS_FRACTION` | 0.047 | Fraction of 1.10x hotspot below threshold |
| `HIGH_SUCCESS_WEIGHT` | 0.0018 | Weight for >10x outcomes |
| `SIMULATION_ITERATIONS` | 2000 | Monte Carlo iterations |
| `MAX_NON_FAIL_SIB` | 95% | SiB blueprint max non-fail |
| `MAX_NON_FAIL_NON_SIB` | 90% | Non-SiB blueprint max non-fail |
| `CONDITION_MIN` | 0 | Minimum condition slider value |
| `CONDITION_MAX` | 100 | Maximum condition slider value |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tools/construction/plans` | GET | List user's saved crafting plans |
| `/api/tools/construction/plans` | POST | Create a new crafting plan |
| `/api/tools/construction/plans/[id]` | PUT | Update a crafting plan |
| `/api/tools/construction/plans/[id]` | DELETE | Delete a crafting plan |
| `/api/tools/construction/ownership` | GET | Get user's blueprint ownership map |
| `/api/tools/construction/ownership` | PUT | Replace user's blueprint ownership map |
| `/api/tools/construction/import` | POST | Import blueprints from game data |

All endpoints require authentication. The ownership endpoint stores only unowned blueprints (owned is the default assumption) to minimize storage.

## Database

Crafting plans and blueprint ownership are stored in the `nexus_users` database:

| Table | Description |
|-------|-------------|
| `crafting_plans` | User's saved crafting plans (targets, config) |
| `blueprint_ownership` | Per-user blueprint ownership map (JSONB) |

See `sql/nexus_users/migrations/020_crafting_plans.sql` for schema.

## File Locations

| File | Description |
|------|-------------|
| `nexus/src/lib/utils/constructionCalculator.js` | Core calculator logic (hotspot model, simulation, tree building) |
| `nexus/src/routes/tools/construction/[[planId]]/+page.svelte` | UI component (planning, steps, shopping views) |
| `nexus/src/routes/tools/construction/[[planId]]/+page.js` | Page data loader |
| `nexus/src/routes/tools/construction/construction.css` | Feature-specific styles |
| `nexus/src/routes/api/tools/construction/` | API endpoints for plans, ownership, import |
