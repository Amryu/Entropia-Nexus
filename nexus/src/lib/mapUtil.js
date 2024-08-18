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

export function copyLocation(location) {
  navigator.clipboard.writeText(`/wp ${getWaypointFromLocation(location)}`);
}

export function getWaypointFromLocation(location) {
  let name;

  if (location.Properties.Type === 'MobArea') {
    name = location.Name.split(',').map(x => x.trim().split(' - ')[0].trim()).join('/');
  }
  else {
    name = location.Name;
  }

  return `${getWaypoint(location.Planet.Properties.TechnicalName ?? location.Planet.Name, location.Properties.Coordinates.Longitude, location.Properties.Coordinates.Latitude, location.Properties.Coordinates.Altitude, name)}`;
}

export function getWaypoint(planet, x, y, z, name) {
  return `[${planet}, ${x}, ${y}, ${z}, ${name}]`;
}

export function locationFilter(location, mapSettings) {
  const searchTerm = mapSettings.filters.search.trim() ? mapSettings.filters.search?.toLowerCase() : '';
  
  if (searchTerm.length > 0 && !location.Name.toLowerCase().includes(searchTerm)) {
    return false;
  }

  if (mapSettings.locations.enabled && !location.Properties.Type.endsWith('Area')) {
    if (mapSettings.locations.teleporters && location.Properties.Type === 'Teleporter') return true;
    if (mapSettings.locations.outposts && location.Properties.Type === 'Outpost') return true;
    if (mapSettings.locations.missions && (location.Properties.Type === 'Mission' || location.Properties.Type === 'Objective')) return true;
  }

  if (mapSettings.areas.enabled && location.Properties.Type.endsWith('Area')) {
    if (mapSettings.areas.landAreas && location.Properties.Type === 'LandArea') return true;
    if (mapSettings.areas.zoneAreas && location.Properties.Type === 'ZoneArea') return true;
    if (mapSettings.areas.pvpAreas && (location.Properties.Type === 'PvpArea' || location.Properties.Type === 'PvpLootArea')) return true;
    if (mapSettings.areas.eventAreas && location.Properties.Type === 'EventArea') return true;
    if (mapSettings.areas.waveEvents && item.Properties?.Type === 'WaveEventArea') return true;
  }

  if (mapSettings.mobs.enabled && location.Properties.Type === 'MobArea') {
    return true;
    if (mapSettings.mobs.rookie && false) return true;
    if (mapSettings.mobs.adept && false) return true;
    if (mapSettings.mobs.intermediate && false) return true;
    if (mapSettings.mobs.expert && false) return true;
    if (mapSettings.mobs.uber && false) return true;
  }

  return false;
}