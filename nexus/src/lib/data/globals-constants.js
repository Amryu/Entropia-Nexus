/**
 * Shared constants for globals pages and components.
 */

/** Global type configuration: labels, CSS classes, and chart colors. */
export const TYPE_CONFIG = {
  kill:       { label: 'Hunting',     cssClass: 'type-kill',      color: '#ef4444' },
  team_kill:  { label: 'Team Hunt',   cssClass: 'type-kill',      color: '#ef4444' },
  deposit:    { label: 'Mining',      cssClass: 'type-deposit',   color: '#60b0ff' },
  craft:      { label: 'Crafting',    cssClass: 'type-craft',     color: '#f97316' },
  rare_item:  { label: 'Rare Find',   cssClass: 'type-rare',      color: '#60b0ff' },
  discovery:  { label: 'Discovery',   cssClass: 'type-discovery', color: '#9b59b6' },
  tier:       { label: 'Tier Record', cssClass: 'type-tier',      color: '#f1c40f' },
  examine:    { label: 'Instance',    cssClass: 'type-examine',   color: '#2ecc71' },
  pvp:        { label: 'PvP',         cssClass: 'type-pvp',       color: '#e74c3c' },
};

/** Type filter buttons for the filter bar. */
export const TYPE_FILTERS = [
  { value: '', label: 'All' },
  { value: 'kill,team_kill', label: 'Hunting' },
  { value: 'deposit', label: 'Mining' },
  { value: 'craft', label: 'Crafting' },
  { value: 'examine', label: 'Instance' },
];

/** Top loots tab definitions. */
export const TOP_LOOTS_TABS = [
  { value: 'hunting',   label: 'Hunting',     types: "('kill', 'team_kill')", hasValue: true },
  { value: 'mining',    label: 'Mining',       types: "('deposit')",          hasValue: true },
  { value: 'crafting',  label: 'Crafting',     types: "('craft')",            hasValue: true },
  { value: 'rare_item', label: 'Rare Find',    types: "('rare_item')",        hasValue: true,  isSpecial: true },
  { value: 'discovery', label: 'Discovery',    types: "('discovery')",        hasValue: false, isSpecial: true },
  { value: 'tier',      label: 'Tier Record',  types: "('tier')",             hasValue: false, isSpecial: true },
  { value: 'pvp',       label: 'PvP',          types: "('pvp')",              hasValue: true,  isSpecial: true },
];

/** Period preset options for the date range picker. */
export const PERIOD_OPTIONS = [
  { value: '24h', label: '24 Hours' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
  { value: '1y', label: '1 Year' },
  { value: 'all', label: 'All Time' },
];

/** Get the type config for a global type, with fallback. */
export function getTypeConfig(type) {
  return TYPE_CONFIG[type] || { label: type, cssClass: '', color: '#888' };
}
