//@ts-nocheck
export function getTooltipText(location) {
  let name;

  if (location.Properties.Type === 'MobArea') {
    name = location.Name.replace(',', ' + ');
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
    { Name: 'ARIS', _type: 'aris' }
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
    { Name: 'Hunt the THING', _type: 'huntthething' },
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
    { Name: 'Space', _type: 'space' },
    { Name: 'Crystal Palace', _type: 'crystalpalace' },
    { Name: 'Asteroid F.O.M.A', _type: 'asteroidfoma' },
  ]
};

export function getMainPlanetNames() {
  return Object.keys(planetGroups);
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
  const type = location.Properties?.Type;
  const name = type === 'MobArea'
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
