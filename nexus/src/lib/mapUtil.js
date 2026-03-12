//@ts-nocheck

/**
 * Format a MobArea/MobSpawn display name from its raw DB name.
 * Raw format: "Mob1 - Mat1/Mat2/Mat3, Mob2 - Mat4/Mat5"
 *
 * @param {string} name - Raw DB name
 * @param {Array|null} [maturities] - Optional MobSpawn.Maturities array with Level data
 * @returns {string} Simplified display name
 */
export function formatMobSpawnDisplayName(name, maturities) {
  if (!name) return '';

  // Parse "Mob1 - Mat1/Mat2, Mob2 - Mat3/Mat4" into groups
  const groups = name.split(',').map(g => g.trim()).filter(Boolean);
  const parsed = [];
  for (const g of groups) {
    const dashIdx = g.indexOf(' - ');
    if (dashIdx === -1) {
      parsed.push({ mob: g, mats: [] });
    } else {
      const mob = g.substring(0, dashIdx).trim();
      const mats = g.substring(dashIdx + 3).trim().split('/').map(m => m.trim()).filter(Boolean);
      parsed.push({ mob, mats });
    }
  }

  if (parsed.length === 0) return name;

  const mobNames = parsed.map(g => g.mob);
  const totalMats = parsed.reduce((sum, g) => sum + g.mats.length, 0);

  // Multiple mobs
  if (parsed.length > 1) {
    return totalMats > 0
      ? `${mobNames.join(', ')} (${totalMats} ${totalMats === 1 ? 'Maturity' : 'Maturities'})`
      : mobNames.join(', ');
  }

  // Single mob
  const { mob, mats } = parsed[0];
  if (mats.length === 0) return mob;
  if (mats.length === 1) return `${mob} (${mats[0]})`;

  // 2+ maturities: try level-sorted range from structured data
  if (maturities?.length >= 2) {
    const nonBoss = maturities
      .filter(m => !m.Maturity?.Properties?.Boss)
      .sort((a, b) => (a.Maturity?.Properties?.Level ?? Infinity) - (b.Maturity?.Properties?.Level ?? Infinity));
    if (nonBoss.length >= 2) {
      const low = nonBoss[0].Maturity?.Name;
      const high = nonBoss[nonBoss.length - 1].Maturity?.Name;
      if (low && high) return `${mob} (${low}-${high})`;
    }
  }

  // Fallback: use first/last from name string (already stored in level order)
  return `${mob} (${mats[0]}-${mats[mats.length - 1]})`;
}

/**
 * Extract just the mob names from a MobArea name string.
 * "Mob1 - Mat1/Mat2, Mob2 - Mat3" → "Mob1, Mob2"
 */
export function getMobAreaShortName(name) {
  if (!name) return '';
  const groups = name.split(',').map(g => g.trim()).filter(Boolean);
  const mobs = groups.map(g => {
    const dash = g.indexOf(' - ');
    return dash !== -1 ? g.substring(0, dash).trim() : g.trim();
  });
  return mobs.join(', ');
}

/**
 * Compute difficulty band and color for a mob area from its Maturities array.
 * @param {Array} maturities - MobSpawn.Maturities array
 * @returns {{ band: number, label: string, color: string } | null}
 *   band 0-4 = Very Low → Very High, band 5 = Boss
 */
export function getMobAreaDifficulty(maturities) {
  if (!maturities?.length) return null;

  let levels = [];
  let bossCount = 0;
  let total = 0;

  for (const entry of maturities) {
    const props = entry.Maturity?.Properties;
    if (!props) continue;
    total++;
    if (props.Boss) bossCount++;
    if (props.Level != null) levels.push(props.Level);
  }

  if (total === 0) return null;
  if (bossCount === total) return { band: 5, label: 'Boss', color: 'rgb(180, 80, 220)' };
  if (levels.length === 0) return null;

  const avg = levels.reduce((s, v) => s + v, 0) / levels.length;
  const bands = [
    { max: 5,  label: 'Very Low', color: 'rgb(100, 230, 50)' },
    { max: 15, label: 'Low',      color: 'rgb(200, 230, 0)' },
    { max: 35, label: 'Medium',   color: 'rgb(255, 200, 0)' },
    { max: 70, label: 'High',     color: 'rgb(255, 120, 0)' },
    { max: Infinity, label: 'Very High', color: 'rgb(255, 50, 30)' },
  ];
  for (let i = 0; i < bands.length; i++) {
    if (avg <= bands[i].max) return { band: i, label: bands[i].label, color: bands[i].color };
  }
  return null;
}

/**
 * Format mob maturity listings for a mob area's info panel.
 * Groups by mob, shows maturity ranges when consecutive by level.
 * Returns array of { mob: string, display: string, mobSlug: string|null }
 *
 * Example output: [{ mob: "Atrox", display: "Young-Old Alpha, Stalker", mobSlug: "atrox" }]
 */
export function formatMobAreaMaturities(maturities) {
  if (!maturities?.length) return [];

  // Group maturities by mob name
  const byMob = new Map();
  for (const entry of maturities) {
    const mat = entry.Maturity;
    if (!mat) continue;
    const mobName = mat.Mob?.Name || 'Unknown';
    if (!byMob.has(mobName)) {
      byMob.set(mobName, { mob: mobName, mats: [], mobSlug: null });
    }
    const group = byMob.get(mobName);
    group.mats.push({
      name: mat.Name,
      level: mat.Properties?.Level ?? null,
      health: mat.Properties?.Health ?? 0,
      boss: mat.Properties?.Boss === true,
      isRare: entry.IsRare || false,
    });
    // Build slug from mob Links URL if available
    if (!group.mobSlug && mat.Mob?.Links?.['$Url']) {
      const url = mat.Mob.Links['$Url'];
      const match = url.match(/\/mobs\/(.+)/);
      if (match) group.mobSlug = match[1];
    }
  }

  const result = [];
  for (const [, group] of byMob) {
    // Sort maturities by level (then health as tiebreaker)
    group.mats.sort((a, b) => {
      const la = a.level ?? Infinity;
      const lb = b.level ?? Infinity;
      if (la !== lb) return la - lb;
      return a.health - b.health;
    });

    // Build display string using ranges for consecutive maturities
    const display = _formatMaturityRange(group.mats);
    result.push({ mob: group.mob, display, mobSlug: group.mobSlug });
  }
  return result;
}

/**
 * Format a sorted list of maturities into ranges.
 * Consecutive maturities (adjacent indices in sorted order) become "First-Last".
 * Non-consecutive ones are listed individually.
 */
function _formatMaturityRange(sortedMats) {
  if (sortedMats.length === 0) return '';
  if (sortedMats.length === 1) return sortedMats[0].name;

  // Build ranges: group consecutive indices
  const ranges = [];
  let rangeStart = 0;

  for (let i = 1; i <= sortedMats.length; i++) {
    // Check if this maturity is consecutive to the previous
    // "Consecutive" means adjacent in the sorted order — we treat all sorted entries as consecutive
    // since they're already ordered by level. We break ranges only at boss maturities.
    const isBossBreak = i < sortedMats.length && sortedMats[i].boss !== sortedMats[i - 1].boss;
    if (i === sortedMats.length || isBossBreak) {
      const rangeLen = i - rangeStart;
      if (rangeLen >= 3) {
        ranges.push(`${sortedMats[rangeStart].name}-${sortedMats[i - 1].name}`);
      } else {
        for (let j = rangeStart; j < i; j++) {
          ranges.push(sortedMats[j].name);
        }
      }
      rangeStart = i;
    }
  }

  return ranges.join(', ');
}

export function getTooltipText(location) {
  let name;

  if (location.Properties.AreaType === 'MobArea') {
    name = formatMobSpawnDisplayName(location.Name, location.Maturities);
  }
  else {
    name = location.Name;
  }

  return `${name.length > 50 ? name.substring(0,47) + '...' :  name} - <span style="color: gray;">(Right-click to copy)</span><br />${getWaypointFromLocation(location)}`;
}

export const planetGroups = {
  Calypso: [
    { Name: 'Calypso', _type: 'calypso' },
    { Name: 'Setesh', _type: 'setesh' },
    { Name: 'ARIS', _type: 'aris' },
    { Name: 'Crystal Palace', _type: 'crystalpalace' },
    { Name: 'Asteroid F.O.M.A', _type: 'asteroidfoma' }
  ],
  Arkadia: [
    { Name: 'Arkadia', _type: 'arkadia' },
    { Name: 'Arkadia Underground', _type: 'arkadiaunderground' },
    { Name: 'Arkadia Moon', _type: 'arkadiamoon' }
  ],
  Cyrene: [{ Name: 'Cyrene', _type: 'cyrene' }],
  Rocktropia: [
    { Name: 'ROCKtropia', _type: 'rocktropia' },
    { Name: 'HELL', _type: 'hell' },
    { Name: 'Hunt The THING', _type: 'huntthething' },
    { Name: 'Secret Island', _type: 'secretisland' }
  ],
  NextIsland: [
    { Name: 'Next Island', _type: 'nextisland' },
    { Name: 'Ancient Greece', _type: 'ancientgreece' }
  ],
  Toulan: [{ Name: 'Toulan', _type: 'toulan' }],
  Monria: [
    { Name: 'Monria', _type: 'monria' },
    { Name: 'DSEC9', _type: 'dsec9' },
  ],
  Space: [
    { Name: 'Space', _type: 'space' }
  ]
};

export function getMainPlanetNames() {
  return Object.keys(planetGroups);
}

/**
 * Get the main (parent) planet name for any planet/sub-planet name.
 * e.g. 'ARIS' → 'Calypso', 'Arkadia Moon' → 'Arkadia', 'Calypso' → 'Calypso'
 */
export function getMainPlanet(planetName) {
  for (const planets of Object.values(planetGroups)) {
    if (planets.some(p => p.Name === planetName)) {
      return planets[0].Name;
    }
  }
  return planetName;
}

/**
 * Build a planet nav filter config for WikiNavigation.
 * Shows main planets as buttons; filterFn includes sub-planets.
 * @param {string} key - Dot-notation path to planet name on items (e.g. 'Planet.Name' or 'Planet')
 */
export function getPlanetNavFilter(key = 'Planet.Name') {
  const groupNames = {};
  for (const planets of Object.values(planetGroups)) {
    const names = new Set(planets.map(p => p.Name));
    for (const p of planets) {
      groupNames[p.Name] = names;
    }
  }

  const values = Object.entries(planetGroups).map(([groupKey, planets]) => ({
    value: planets[0].Name,
    label: groupKey === 'NextIsland' ? 'Next Island' : groupKey
  }));

  return {
    key,
    label: 'Planet',
    values,
    filterFn: (item, selectedValue) => {
      const parts = key.split('.');
      let planetName = item;
      for (const part of parts) {
        planetName = planetName?.[part];
      }
      const group = groupNames[selectedValue];
      return group ? group.has(planetName) : planetName === selectedValue;
    }
  };
}

export function getPlanetGroupByType(type) {
  if (!type) return null;
  const normalized = String(type).toLowerCase();
  for (const [groupName, list] of Object.entries(planetGroups)) {
    const match = list.find((entry) => entry._type === normalized);
    if (match) {
      return { groupName, list };
    }
  }
  return null;
}

export function normalizePlanetSlug(name) {
  if (!name) return '';
  return String(name).replace(/[^0-9a-zA-Z]/g, '').toLowerCase();
}

export function copyLocation(location) {
  navigator.clipboard.writeText(`/wp ${getWaypointFromLocation(location)}`);
}

export function getWaypointFromLocation(location) {
  if (!location) return '';
  const areaType = location.Properties?.AreaType;
  const name = areaType === 'MobArea'
    ? (location.Name || '').split(',').map(x => x.trim().split(' - ')[0].trim()).join('/')
    : (location.Name || '');
  const planet = location.Planet?.Properties?.TechnicalName ?? location.Planet?.Name ?? '';
  const coords = location.Properties?.Coordinates || {};
  return `${getWaypoint(planet, coords.Longitude, coords.Latitude, coords.Altitude, name)}`;
}

export function getWaypoint(planet, x, y, z, name) {
  return `[${planet}, ${x}, ${y}, ${z}, ${name}]`;
}

// Fuzzy scoring - adapted from wiki navigation
export function fuzzyScore(name, query) {
  if (!name || !query) return 0;
  const nameLower = name.toLowerCase();
  const queryLower = query.toLowerCase();

  if (nameLower === queryLower) return 1000;
  if (nameLower.startsWith(queryLower)) return 900;

  const words = nameLower.split(/\s+/);
  for (let i = 0; i < words.length; i++) {
    if (words[i].startsWith(queryLower)) {
      return 800 - i * 5;
    }
  }

  const index = nameLower.indexOf(queryLower);
  if (index !== -1) {
    return 700 - Math.min(index, 50);
  }

  if (queryLower.length < 4) {
    return 0;
  }

  let queryIdx = 0;
  let score = 0;
  let consecutiveBonus = 0;
  let matchPositions = [];

  for (let i = 0; i < nameLower.length && queryIdx < queryLower.length; i++) {
    if (nameLower[i] === queryLower[queryIdx]) {
      matchPositions.push(i);
      queryIdx++;
      consecutiveBonus += 10;
      score += consecutiveBonus;
      if (i === 0 || nameLower[i - 1] === ' ' || nameLower[i - 1] === '-' || nameLower[i - 1] === '_') {
        score += 30;
      }
    } else {
      consecutiveBonus = 0;
    }
  }

  if (queryIdx === queryLower.length) {
    const spread = matchPositions.length > 1
      ? matchPositions[matchPositions.length - 1] - matchPositions[0]
      : 0;

    if (spread > queryLower.length * 2) {
      return 0;
    }

    const compactBonus = Math.max(0, 50 - spread);
    return 300 + score + compactBonus;
  }

  const matchRatio = queryIdx / queryLower.length;
  if (matchRatio >= 0.95 && queryLower.length >= 5) {
    const spread = matchPositions.length > 1
      ? matchPositions[matchPositions.length - 1] - matchPositions[0]
      : 0;
    if (spread <= queryLower.length * 2) {
      return 100 + Math.floor(score * matchRatio);
    }
  }

  return 0;
}
