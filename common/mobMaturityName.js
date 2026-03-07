/**
 * Construct the full in-game name for a mob maturity from the mob name,
 * maturity name, and the NameMode that controls how they combine.
 *
 * @param {string} mobName      - Parent mob name (e.g., "Araneatrox")
 * @param {string} maturityName - Maturity name (e.g., "Young")
 * @param {string|null} nameMode - One of 'Suffix', 'Prefix', 'Verbatim', 'Empty', or null
 * @returns {string} The constructed full name
 */
export function getMobMaturityFullName(mobName, maturityName, nameMode) {
  switch (nameMode) {
    case 'Prefix':   return `${maturityName} ${mobName}`;
    case 'Verbatim': return maturityName;
    case 'Empty':    return mobName;
    case 'Suffix':
    default:         return `${mobName} ${maturityName}`;
  }
}
