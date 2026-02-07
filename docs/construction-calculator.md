# Construction Calculator

The construction calculator helps players plan crafting sessions by estimating material requirements, craft attempts needed, and accounting for the game's unique near-success refund mechanics.

## Overview

The calculator:
1. Takes target blueprints and desired quantities as input
2. Builds a crafting tree including sub-blueprints and craftable materials
3. Estimates craft attempts needed based on success rates and certainty level
4. Calculates material requirements with per-material refund adjustments
5. Generates ordered crafting steps and a shopping list

## Crafting Success Model

Entropia Universe has three craft outcomes:

| Outcome | Probability | Result |
|---------|-------------|--------|
| **Success** | 4/9 of non-fail (~44.4%) | Produces items |
| **Near-success** | 5/9 of non-fail (~55.6%) | Produces items + partial material refund |
| **Fail** | Remaining % | Loses all materials, no output |

### Maximum Non-Fail Rates

| Blueprint Type | Max Non-Fail | Min Fail Rate |
|----------------|--------------|---------------|
| **SiB** (Skill Increase Bonus) | 95% | 5% |
| **Non-SiB** | 90% | 10% |

### Success Rate Calculation

```javascript
successRate = nonFailChance × (4/9)
nearSuccessRate = nonFailChance × (5/9)
failRate = 1 - nonFailChance
```

For a 90% non-fail blueprint:
- Success rate: 90% × 4/9 = 40%
- Near-success rate: 90% × 5/9 = 50%
- Fail rate: 10%

## Craft Attempt Estimation

### Negative Binomial Distribution

The calculator uses the negative binomial distribution to estimate attempts needed:

```
Mean attempts = successesNeeded / successRate
Variance = successesNeeded × (1 - successRate) / successRate²
```

### Certainty Levels

Users can specify a confidence level (50-99%) which adjusts the estimate using z-scores:

| Certainty | Z-Score | Interpretation |
|-----------|---------|----------------|
| 50% | 0 | Mean estimate (50% chance of success) |
| 75% | 0.67 | 75% confidence of having enough materials |
| 90% | 1.28 | 90% confidence |
| 95% | 1.65 | 95% confidence |
| 99% | 2.33 | 99% confidence |

**Formula:**
```
adjustedAttempts = meanAttempts + (zScore × standardDeviation)
```

Higher certainty = more estimated attempts = safer material buffer.

### Output Estimation

When a blueprint's `MinimumCraftAmount` is null or 1, the calculator estimates output based on material cost and product value:

```javascript
lowEstimate = blueprintCost / productTT
highEstimate = blueprintCost × 1.2 / productTT
avgOutput = weightedIntegerAverage(low, high)
```

The weighted integer average accounts for the game's floor behavior—barely crossing into a new integer contributes minimally to the average.

## Pool-Based Refund System

This is the most complex part of the calculation. On near-success:

### How It Works

1. A **refund pool** is generated: uniform distribution between 20% and 99.99% of blueprint TT cost
2. Each material **rolls independently** with `rollChance` probability (configurable, default 50%)
3. **Winners are processed in random order**, consuming from the pool
4. Each winner gets `floor(remaining_pool / unitTT)` units refunded, capped at amount used

### Why Order Matters

Consider a blueprint costing 5.00 PED with:
- Material A: 8 × 0.05 PED = 0.40 PED total (cheap)
- Material B: 2 × 2.00 PED = 4.00 PED total (expensive)

Pool roll = 2.31 PED. Both materials win their roll.

**If A processed first:**
- A: floor(2.31 / 0.05) = 46, capped at 8 → **8 refunded**, pool = 1.91
- B: floor(1.91 / 2.00) = 0 → **0 refunded**

**If B processed first:**
- B: floor(2.31 / 2.00) = 1 → **1 refunded**, pool = 0.31
- A: floor(0.31 / 0.05) = 6 → **6 refunded**

**Result**: Expensive materials consistently receive fewer refunds because:
- They need more pool per unit
- Cheap materials often consume the pool first

### Monte Carlo Simulation

Due to the complexity of random ordering and partial refunds, the calculator uses Monte Carlo simulation (2000 iterations default):

```javascript
function simulateRefundRates(materials, rollChance, iterations = 2000) {
  const refundedUnits = new Map(materials.map(m => [m.name, 0]));

  for (let i = 0; i < iterations; i++) {
    // Generate pool: uniform [0.2, 0.9999] × blueprintCost
    const poolFraction = 0.2 + Math.random() * 0.7999;
    let pool = poolFraction * blueprintCost;

    // Each material rolls independently
    const winners = materials.filter(() => Math.random() < rollChance / 100);

    // Shuffle winners for random processing order
    shuffle(winners);

    // Process winners
    for (const mat of winners) {
      const unitsRefundable = Math.floor(pool / mat.unitTT);
      const unitsRefunded = Math.min(unitsRefundable, mat.amount);
      if (unitsRefunded > 0) {
        refundedUnits.set(mat.name, refundedUnits.get(mat.name) + unitsRefunded);
        pool -= unitsRefunded * mat.unitTT;
      }
    }
  }

  // Convert to per-material refund fractions
  return new Map(materials.map(m => [
    m.name,
    (refundedUnits.get(m.name) / iterations) / m.amount
  ]));
}
```

### Per-Material Multiplier

Each material gets its own multiplier based on simulation results:

```javascript
multiplier = 1 - (nearSuccessRate × refundFraction)
adjustedAmount = ceil(rawAmount × multiplier)
```

Example with 90% non-fail (50% near-success rate):
- Material A: 60% refund fraction → multiplier = 1 - (0.5 × 0.6) = 0.70
- Material B: 15% refund fraction → multiplier = 1 - (0.5 × 0.15) = 0.925

Expensive materials have higher multipliers (closer to 1.0) meaning less savings from refunds.

### Weighted Average Multiplier

For backward compatibility and summary display, a TT-weighted average multiplier is calculated:

```javascript
weightedMultiplier = Σ(materialMultiplier × materialTTCost) / totalTTCost
```

## Residue Calculation

Some products require residue (items with condition). Residue required per craft:

```javascript
residuePerClick = productMaxTT - materialCost
totalResidue = residuePerClick × estimatedAttempts
adjustedResidue = totalResidue × weightedMultiplier  // Also subject to refund
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rollChance` | 50% | Per-material refund roll probability |
| `certainty` | 50% | Confidence level for attempt estimation |
| `nonFailChances` | Max per BP | Override non-fail % per blueprint |
| `materialCraftConfig` | {} | Enable/configure sub-material crafting |

## Tree Building

### Node Structure

Each crafting node contains:

```javascript
{
  blueprint,           // The blueprint object
  quantityWanted,      // Desired output quantity
  estimatedAttempts,   // Calculated craft attempts
  avgOutput,           // Average items per success
  successRate,         // Probability of success
  nonFailChance,       // Non-fail percentage
  materialMultiplier,  // Weighted average multiplier
  materials: [{        // Array of material requirements
    item,
    amountPerAttempt,
    totalAmount,       // Raw: amountPerAttempt × attempts
    adjustedAmount,    // After refund adjustment
    multiplier,        // Per-material multiplier
    refundFraction,    // Expected refund % on near-success
    hasCraftableBlueprint
  }],
  children,            // Sub-blueprints (from drops)
  materialChildren,    // Craftable materials
  residuePerClick,
  totalResidue,
  adjustedResidue
}
```

### Recursion

The tree builder recursively processes:
1. **Blueprint drops**: Sub-blueprints that drop from this blueprint
2. **Craftable materials**: Materials that can themselves be crafted

Circular references are detected and handled to prevent infinite loops.

## Output Generation

### Crafting Steps

Steps are generated in **leaf-first order** (post-order traversal):
1. Visit all children first (dependencies)
2. Then visit current node
3. This ensures materials/sub-products are crafted before they're needed

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
| `POOL_MIN` | 0.2 (20%) | Minimum refund pool fraction |
| `POOL_MAX` | 0.9999 (~100%) | Maximum refund pool fraction |
| `AVG_RETURN_FRACTION` | 0.6 (60%) | Average refund pool (for legacy calculation) |
| `VARIANCE_FACTOR` | 1.2 | Output estimation variance |
| `SIMULATION_ITERATIONS` | 2000 | Monte Carlo iterations |
| `MAX_NON_FAIL_SIB` | 95% | SiB blueprint max non-fail |
| `MAX_NON_FAIL_NON_SIB` | 90% | Non-SiB blueprint max non-fail |

## File Location

Main calculator logic: `nexus/src/lib/utils/constructionCalculator.js`

UI component: `nexus/src/routes/tools/construction/[[planId]]/+page.svelte`
