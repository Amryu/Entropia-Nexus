# Search Scoring Algorithm

The search scoring algorithm is used across the project to rank search results by relevance. It is implemented in three locations that must be kept in sync:

| Implementation | File | Notes |
|---|---|---|
| Backend (API) | `api/endpoints/search.js` | Server-side scoring + SQL pre-filtering. Includes gendered query handling. |
| Frontend (shared) | `nexus/src/lib/search.js` | Client-side ES module. Used by exchange and SearchInput components. |
| Backend SQL | `api/endpoints/search.js` | Multi-word ILIKE conditions for database pre-filtering. |

## Score Tiers

Results are scored on a numeric scale. Higher = better match. Zero = no match (filtered out).

| Score Range | Tier | Description | Example (query: "wool") |
|---|---|---|---|
| **1000** | Exact match | Name equals query exactly | "Wool" → 1000 |
| **900 − length** | Starts with | Name starts with query; shorter names rank higher | "Wool Cloth" (10 chars) → 890 |
| **800 − pos×5 − length** | Word starts with | A word in the name starts with query; earlier words rank higher | "Thin Wool" → 800 − 5 − 9 = 786 |
| **700 − index − length** | Contains substring | Name contains query as substring; earlier position ranks higher | "Angelic Wool Thread" → 700 − 8 − 19 = 673 |
| **550 – 650** | Multi-word match | Each query word matched independently against name words (see below) | "electric nanochip 5" matching "Electric Attack Nanochip 5" |
| **300 – 500** | Fuzzy match | Character-by-character subsequence matching (4+ char queries only) | |
| **100 – 299** | Partial fuzzy | ≥95% of query chars matched in order (5+ char queries only) | |
| **0** | No match | Filtered out | |

## Scoring Functions

### `scoreSearchResult(name, query)`

Main entry point. Evaluates tiers top-down and returns the first match:

1. **Exact match**: `nameLower === queryLower` → 1000
2. **Starts with**: `nameLower.startsWith(queryLower)` → `900 - nameLower.length`
3. **Word starts with**: Split name by spaces, check each word → `800 - wordIndex * 5 - nameLower.length`
4. **Contains substring**: `nameLower.indexOf(queryLower)` → `700 - min(index, 50) - nameLower.length`
5. **Multi-word**: Only if query has 2+ words → delegates to `scoreMultiWord()`
6. **Short query bail-out**: If query < 4 chars, return 0 (no fuzzy for short queries)
7. **Fuzzy match**: Character-by-character matching with consecutive and word-boundary bonuses
8. **Partial fuzzy**: If ≥95% chars matched and query ≥5 chars

### `scoreMultiWord(nameLower, queryWords)`

Each query word is matched against name words independently using `scoreWordPair()`. Name words are split on spaces and commas.

- Each query word finds its best match among unused name words
- Requires ≥50% of query words to match
- Score: `550 + avgWordScore × 1.5 + ratioBonus − lengthPenalty`
  - `ratioBonus`: +50 if all query words matched
  - `lengthPenalty`: `min(nameLower.length × 0.5, 30)`

### `scoreWordPair(nameWord, queryWord)`

Scores a single query word against a single name word:

| Score | Condition |
|---|---|
| 100 | Exact word match |
| 85 − min(lengthDiff, 15) | Name word starts with query word |
| 60 | Name word contains query word |
| 30 | Fuzzy subsequence match (query word ≥3 chars) |
| 0 | No match |

## Fuzzy Matching Details

For queries ≥4 characters, fuzzy matching checks if all query characters appear in order within the name:

- **Consecutive bonus**: +10 per consecutive matched character (cumulative: 10, 20, 30, ...)
- **Word boundary bonus**: +30 when match is at start of name or after space/dash/underscore
- **Spread check**: If matched characters span more than `queryLength × 2` positions, score is 0
- **Compact bonus**: `max(0, 50 - spread)` for tightly grouped matches
- **Final score**: `300 + cumulativeScore + compactBonus`

## Gendered Query Handling (Backend Only)

The backend `scoreSearchResult` accepts an optional `genderedQuery` parameter for queries like "Bear Armor (M)". This:
- Parses the gender tag from the query
- Scores against the base name without gender
- Generates aliased display names for clothing items with `Both` gender

This is not needed client-side since the exchange and SearchInput work with pre-filtered data.

## SQL Pre-filtering (Backend Only)

The backend uses SQL to pre-filter candidates before scoring:

- **ILIKE**: `"Name" ILIKE '%query%'` for substring matching
- **pg_trgm similarity**: `similarity("Name", query) >= 0.1` when extension is available
- **Multi-word ILIKE**: Each query word generates `"Name" ILIKE '%word%'`, joined with AND
- **ROW_NUMBER partitioning**: Limits to 5 results per type category
- **Partition ordering** (determines which 5 per type are kept):
  - With pg_trgm: prefix match first, then similarity descending, then name alphabetically
  - Without pg_trgm: prefix match first, then name length ascending (shorter = more relevant), then name alphabetically

Results from SQL are then scored in JavaScript and re-sorted by score descending, with name length as tiebreaker.

## Consumers

| Consumer | How it uses search | File |
|---|---|---|
| Exchange browser (item list) | Client-side scoring via `$lib/search.js`. Items filtered by `score > 0`, sorted by score (primary) then order priority (secondary). | `ExchangeBrowser.svelte` |
| Global SearchInput | Calls backend API (`/search`), then re-scores client-side for consistent ranking. Enter without arrow selection → navigates to `/search?q=...`. | `nexus/src/lib/components/SearchInput.svelte` |
| Search page (`/search`) | Calls backend API (`/search/detailed`). Displays enriched results in grouped tables with user-configured columns. | `nexus/src/routes/search/+page.svelte` |
| Wiki SearchInput (local mode) | Client-side scoring via `$lib/search.js`. Options scored, filtered, and sorted by score. | `nexus/src/lib/components/wiki/SearchInput.svelte` |
| Wiki SearchInput (API mode) | Calls backend API (`/search/items`). Backend scoring applies. | `nexus/src/lib/components/wiki/SearchInput.svelte` |
| Backend `/search` endpoint | SQL pre-filter + JavaScript scoring. | `api/endpoints/search.js` |
| Backend `/search/detailed` endpoint | Enriches `/search` results with full entity Properties from cached data. `perType=20`, `totalLimit=100`. | `api/endpoints/search.js` |
| Backend `/search/items` endpoint | SQL pre-filter + JavaScript scoring. Optional type filter removes per-category limit. | `api/endpoints/search.js` |
| Market search (`/api/market/search`) | Server-side scoring via `$lib/search.js`. Searches exchange cache, services, auctions (with item sets), rentals (with item sets), and shops (with inventory). Per-type limits: exchange 10, others 5. Non-exchange +50 bonus. | `nexus/src/routes/api/market/search/+server.js` |

## Search Page (`/search`)

The dedicated search page provides a full-page search experience with enriched results.

### Architecture

- **Data loader** (`+page.js`): Reads `q` from URL params, calls `/search/detailed?query=...&fuzzy=true`
- **Page** (`+page.svelte`): Debounced input (300ms) updates URL via `goto()` with `replaceState`
- **Column defs** (`search-columns.js`): Shared column definitions per entity type, matching sidebar column keys

### Column Resolution

1. Read `localStorage` key `wiki-nav-columns-{pageTypeId}` (user's sidebar preferences)
2. Take first 5 column keys, resolve against `SEARCH_COLUMN_DEFS[pageTypeId]`
3. Fall back to `DEFAULT_SEARCH_COLUMNS[pageTypeId]` if no stored preferences

### `/search/detailed` Endpoint

Enriches standard search results with full entity Properties:

1. Runs `search(query, fuzzy, perType=20, totalLimit=100)`
2. For each result Type, loads entity cache via `withCache` (already in memory from regular API usage)
3. Matches results by Name, merges `Properties` from cached entity data
4. Types without enrichment endpoints (User, Society, Location, Mission) are returned as-is

## Keeping Implementations in Sync

When modifying the scoring algorithm:

1. Update `api/endpoints/search.js` (backend)
2. Update `nexus/src/lib/search.js` (frontend shared module)
3. Update this document
4. The frontend module omits gendered query handling (backend-specific)
5. The backend includes SQL pre-filtering logic (not needed client-side)
