/**
 * Shared search scoring module.
 * Mirrors the scoring algorithm in api/endpoints/search.js (lines 12-152).
 * See docs/search.md for algorithm documentation.
 *
 * When updating this file, keep api/endpoints/search.js in sync.
 */

/**
 * Score how well a single query word matches a single name word.
 * @param {string} nameWord
 * @param {string} queryWord
 * @returns {number} 0-100
 */
function scoreWordPair(nameWord, queryWord) {
  if (nameWord === queryWord) return 100;
  if (nameWord.startsWith(queryWord)) return 85 - Math.min(nameWord.length - queryWord.length, 15);
  if (nameWord.includes(queryWord)) return 60;
  if (queryWord.length >= 3) {
    let qi = 0;
    for (let ni = 0; ni < nameWord.length && qi < queryWord.length; ni++) {
      if (nameWord[ni] === queryWord[qi]) qi++;
    }
    if (qi === queryWord.length) return 30;
  }
  return 0;
}

/**
 * Score multi-word query: each query word is matched against name words independently.
 * @param {string} nameLower - Lowercase item name
 * @param {string[]} queryWords - Array of lowercase query words
 * @returns {number} 0 or 550+
 */
function scoreMultiWord(nameLower, queryWords) {
  const nameWords = nameLower.split(/[\s,]+/).filter(w => w.length > 0);
  let totalScore = 0;
  let matchedCount = 0;
  const usedNameWords = new Set();

  for (const qWord of queryWords) {
    let bestScore = 0;
    let bestIdx = -1;
    for (let i = 0; i < nameWords.length; i++) {
      if (usedNameWords.has(i)) continue;
      const s = scoreWordPair(nameWords[i], qWord);
      if (s > bestScore) { bestScore = s; bestIdx = i; }
    }
    if (bestScore > 0 && bestIdx >= 0) {
      usedNameWords.add(bestIdx);
      totalScore += bestScore;
      matchedCount++;
    }
  }

  if (matchedCount === 0) return 0;
  const matchRatio = matchedCount / queryWords.length;
  if (matchRatio < 0.5) return 0;

  const avgScore = totalScore / queryWords.length;
  const baseScore = 550 + avgScore * 1.5;
  const ratioBonus = matchRatio >= 1 ? 50 : 0;
  const lengthPenalty = Math.min(nameLower.length * 0.5, 30);
  return Math.round(baseScore + ratioBonus - lengthPenalty);
}

/**
 * Score a search result against the query.
 * Higher scores = better matches.
 *
 * Score tiers:
 *   1000        — Exact match
 *   900-8xx     — Starts with query (shorter names rank higher)
 *   800-7xx     — A word starts with query (earlier word position ranks higher)
 *   700-6xx     — Contains exact substring (earlier position ranks higher)
 *   550-650     — Multi-word match (word-independent scoring)
 *   300-500     — Fuzzy match (character-by-character, 4+ char queries only)
 *   100-299     — Partial fuzzy (≥95% chars matched, 5+ char queries)
 *   0           — No match
 *
 * @param {string} name - The item name to score
 * @param {string} query - The search query
 * @returns {number} Score (0 = no match, higher = better)
 */
export function scoreSearchResult(name, query) {
  if (!name || !query) return 0;

  const nameLower = name.toLowerCase();
  const queryLower = query.toLowerCase().trim();

  if (!queryLower) return 0;

  // Exact match (highest priority)
  if (nameLower === queryLower) return 1000;

  // Starts with query
  if (nameLower.startsWith(queryLower)) return 900 - nameLower.length;

  // Word starts with query (e.g., "Calypso Sword" matches "sword")
  const words = nameLower.split(/\s+/);
  for (let i = 0; i < words.length; i++) {
    if (words[i].startsWith(queryLower)) {
      return 800 - i * 5 - nameLower.length;
    }
  }

  // Contains exact substring
  const index = nameLower.indexOf(queryLower);
  if (index !== -1) {
    return 700 - Math.min(index, 50) - nameLower.length;
  }

  // Multi-word matching
  const queryWords = queryLower.split(/\s+/).filter(w => w.length > 0);
  if (queryWords.length > 1) {
    const mwScore = scoreMultiWord(nameLower, queryWords);
    if (mwScore > 0) return mwScore;
  }

  // For short queries (< 4 chars), only match substrings
  if (queryLower.length < 4) {
    return 0;
  }

  // Fuzzy match for longer queries
  let queryIdx = 0;
  let score = 0;
  let consecutiveBonus = 0;
  const matchPositions = [];

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
    if (spread > queryLower.length * 2) return 0;
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
