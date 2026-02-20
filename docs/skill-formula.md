# Skill Formula - Current State

## Overview

The formula converts between **skill points** and **PED value** (the TT value shown on ESI chips). It is piecewise with a hard breakpoint at effective skill 250 (displayed as 251).

**Key relationship:** `PED(S) = integral from 1 to S of cost(x) dx`, where cost(x) is the inverse of gain (skill points per activity tick).

- Skill point 1 = 0 PED (integration starts at 1, not 0)
- The formula is deterministic: same skill points always yields same PED

## Current Implementation (`skillFormula.js`)

### Parameters

```
K  = 200/9        ≈ 22.222   (scale factor)
BP = 250                      (breakpoint)

Pre-BP:
  a  = 2.465937               (base cost)
  b  = 0.00027699             (growth coefficient)
  c  = 1.125                  (exponent)

Post-BP convergence:
  f0    = 36/85    ≈ 0.4235   (initial f, converges to 1/4)
  f_inf = 1/4      = 0.25     (asymptotic f)
  tau_f = 712                  (f convergence time constant)

  g0    = -139/86  ≈ -1.6163  (initial g, converges to -125/84)
  g_inf = -125/84  ≈ -1.4881  (asymptotic g)
  tau_g = 4878                 (g convergence time constant)

Oscillation (Poisson kernel):
  a_max = 0.30                 (asymptotic Poisson parameter)
  tau_a = 2264.4               (a convergence time constant)
  period = 500                 (oscillation period in skill points)
```

### Formula

**Pre-breakpoint (x < 250):**
```
cost(x) = 2.465937 + 0.00027699 * x^1.125
```

**Post-breakpoint (x >= 250):**
```
t = x - 250

f(x) = 0.25 + (36/85 - 0.25) * exp(-t / 712)
g(x) = -125/84 + (-139/86 + 125/84) * exp(-t / 4878)
a(x) = 0.30 * (1 - exp(-t / 2264.4))

poisson(x) = sqrt(1 - a(x)^2) / (1 - a(x) * cos(2*pi*x / 500))

cost(x) = K * (f(x) * x^0.25 + g(x)) * poisson(x)
```

**Cumulative PED value:**
```
PED(S) = (1/1,000,000) * integral from 0 to S of cost(x) dx
```
(Trapezoidal rule, adaptive step count: min(max(ceil(S*4), 200), 50000) steps)

**Inverse (PED → skill points):**
Binary search. Initial range [0, 100000], doubles hi until `skillPointsToPED(hi) >= ped`. Then 60 bisection iterations for double-precision convergence. Returns midpoint.

## Known Issues

### 1. Wrong divisor (1,000,000)

The `/1_000_000` divisor produces values ~1000x too small compared to ESI data. The PED/CumCost ratio is NOT constant - it grows systematically with skill level:

| Skill Points | ESI PED | Approx PED/CumCost ratio |
|-------------|---------|--------------------------|
| ~88         | 0.1036  | ~0.00048                 |
| ~550        | 1.43    | ~0.0015                  |
| ~1090       | 4.05    | ~0.0028                  |
| ~2058       | 12.59   | ~0.0038                  |
| ~5088       | 163.42  | ~0.0049                  |

No single constant divisor can fix this. The relationship between CumCost and PED is nonlinear.

### 2. Integration starts at 0 instead of 1

Skill point 1 = 0 PED. The integration should be `integral from 1 to S`, not `integral from 0 to S`.

### 3. Missing second period (1250)

Spectral analysis of Electrokinesis gain data revealed TWO independent periods:
- **1248 SP** (fundamental, relative power 1.000) - likely exactly **1250**
- **499 SP** (secondary, relative power 0.648) - likely exactly **500**

These are in a 5:2 ratio - NOT harmonics of each other (a harmonic would be at 625). The current formula only models the 500 period via the Poisson kernel. The missing 1250 period may explain the systematic PED/CumCost drift.

### 4. Activity dependence of K

The scale factor K may vary per skill (different weapons/tools have different activity efficiencies). However, ESI data shows duplicate skill point values across different skills yield identical PED, suggesting the skill→PED mapping is universal (same for all skills).

## ESI Calibration Data

52 data points from ESI chips (skill implants). Format: `[optional_name, PED, skill_points, empty, optional_quantum]`

4 entries have known quantum values:
- Zoology @ 497 SP → quantum = 0.0008771
- Unknown @ 298 SP → quantum = 0.0006163
- Wood Processing @ 462 SP → quantum = 0.0008163
- Wood Carving @ 423 SP → quantum = 0.0007592

Duplicate SP entries have identical PED values (deterministic mapping):
- SP=550 → PED 1.43 (appears twice)
- SP=1090 → PED 4.05 (appears twice)
- SP=88 → PED 0.1036 (appears twice)

## What Needs to Happen

1. Fix the CumCost → PED conversion (not a simple divisor)
2. Add second Poisson kernel for period 1250
3. Change integration lower bound from 0 to 1
4. Validate against all 52 ESI data points
