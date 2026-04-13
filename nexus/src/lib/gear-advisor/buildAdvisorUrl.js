// @ts-nocheck

export const VALID_ADVISOR_SCOPES = new Set(['lowest', 'average', 'highest']);
export const VALID_ADVISOR_RANK_BY = new Set(['typeMatch', 'mitigation', 'damageTaken', 'deflected']);

/**
 * Build a deep-link URL into the Gear Advisor armor-vs-mob tool.
 * Unknown/invalid fields are omitted — the target tool ignores missing params.
 * URLSearchParams handles percent-encoding of values.
 */
export function buildAdvisorUrl({ armor, plating, mob, scope, rankBy } = {}) {
  const params = new URLSearchParams();
  if (armor) params.set('armor', armor);
  if (plating) params.set('plating', plating);
  if (mob) params.set('mob', mob);
  if (scope && VALID_ADVISOR_SCOPES.has(scope)) params.set('scope', scope);
  if (rankBy && VALID_ADVISOR_RANK_BY.has(rankBy)) params.set('rankBy', rankBy);
  const qs = params.toString();
  return qs ? `/tools/gear-advisor/armor-vs-mob?${qs}` : '/tools/gear-advisor/armor-vs-mob';
}
