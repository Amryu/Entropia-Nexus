# Change Workflow Expansion Plan (Profession, Skill, Location, Area, Strongbox)

## Goal
Implement full change workflow support (draft/pending/approve) for:
- Profession
- Skill
- Location
- Area
- Strongbox

## Sources reviewed
- Change workflow docs: `docs/wiki-editing.md`
- Changes endpoint: `nexus/src/routes/api/changes/[[slug]]/+server.js`
- Wiki edit store: `nexus/src/lib/stores/wikiEditState.js`
- Existing entity pages:
  - `nexus/src/routes/information/professions/[[slug]]/+page.svelte`
  - `nexus/src/routes/information/skills/[[slug]]/+page.svelte`
  - `nexus/src/routes/items/strongboxes/[[slug]]/+page.svelte`
  - `nexus/src/routes/maps/[[planet]]/[[slug]]/+page.js`
- Schemas:
  - `common/schemas/Location.js`, `common/schemas/Area.js`, `common/schemas/Strongbox.js`
  - Profession and Skill schemas need to be created
  - `common/EntitySchemas.js` and `nexus/src/lib/common/EntitySchemas.js`
- Change application (bot):
  - `nexus-bot/changes/entity.js`
  - `nexus-bot/changes/util.js`
- DB enums/migrations:
  - `sql/nexus_users_schema.sql`
  - `sql/nexus_users/migrations/014_add_strongbox_change_type.sql`
  - `sql/nexus_users/migrations/016_add_location_area_change_type.sql`

## Change workflow recap (baseline)
- UI edits accumulate via `wikiEditState` and `InlineEdit`.
- Save Draft/Submit uses `EditActionBar` → `POST /api/changes?type=Create|Update&entity=...&state=Draft|Pending`
- Update existing change: `PUT /api/changes/:id?state=Draft|Pending`
- Changes endpoint validates against JSON schema (`EntitySchemas`) and sanitizes Description (currently only top-level `Description`).
- Admin/bot applies change using `nexus-bot/changes/entity.js` → `UpsertConfigs` (table/column mapping + relation handlers).

## Known gaps (from current code)
- `Profession` and `Skill` **schemas missing** in both `common` and `nexus/src/lib/common` (the latter is just a symlink, only focus on common).
- `Strongbox` schema exists but:
  - export is incorrectly named `Vendor`
  - missing fields used by UI (Weight, Economy.MaxTT)
  - uses `type: ["date", "null"]` which AJV doesn’t recognize (should be string with `format: "date"`).
- `EntitySchemas` missing `Strongbox`, `Profession`, `Skill`.
- `nexus-bot/changes/entity.js` has Strongbox, but **no Location/Area/Profession/Skill** UpsertConfigs.
- `getEntityCategory()` in `/api/changes` lacks mappings for Profession/Skill/Strongbox (affects duplicate checks and API endpoints).

---

## Work Plan (global)

1. **Update JSON schemas (both `common/` and `nexus/src/lib/common/`).**
   - Add `Profession.js`, `Skill.js`.
   - Fix `Strongbox.js` export + fields.
   - Ensure `Location.js` + `Area.js` are correct for map editing (include Properties + Coordinates/Shape/Data).
   - Update `EntitySchemas.js` in both locations to include new entities.

2. **Extend `/api/changes` behavior.**
   - Ensure schema validation covers new entities (via updated `EntitySchemas`).
   - Update `getEntityCategory` to map:
     - `Profession` → `professions`
     - `Skill` → `skills`
     - `Strongbox` → likely `items` or `strongboxes` (verify API endpoint)
   - Consider sanitizing nested `Properties.Description` for entities that store Description inside `Properties` (Location/Area/Strongbox). Align with existing entities if needed.

3. **Add UpsertConfigs to `nexus-bot/changes/entity.js`.**
   - Implement UpsertConfig entries for Profession, Skill, Location, Area.
   - Verify existing Strongbox mapping includes all fields from UI (Weight, Economy.MaxTT, Description).
   - Add any relation handlers (join tables) for Skills/Professions/Unlocks.

4. **Verify change_entity enum values are in DB.**
   - Ensure migrations `014` and `016` are applied in the target DB.

5. **Validation/QA Checklist.**
   - Create & update flow for each entity.
   - Draft → Pending → Approved pipeline.
   - Admin/bot apply updates to DB tables.
   - Confirm sidebar navigation and `loadPendingChangesData` behaves correctly for create/update.

---

## Entity-specific Plans

### 1) Profession
**Observed shape (UI):**
- `Name`
- `Description` (top-level)
- `Category` (object with `Name`)
- `Skills` (array)
- `Unlocks` (array)

**Schema tasks:**
- Add `common/schemas/Profession.js` with fields above.
- Use `NamedEntity` for `Category`, `Skills`, `Unlocks`.
- Add to `EntitySchemas` (both `common` and `nexus/src/lib/common`).

**Changes endpoint tasks:**
- Map `Profession` to `professions` in `getEntityCategory`.
- Ensure Description sanitization supports top-level Description (already) and any nested fields if needed.

**Bot UpsertConfig (needs DB research):**
- Table likely `"Professions"`.
- Columns: `Name`, `Description`, `CategoryId` (look up by category name).
- Relation tables likely:
  - ProfessionSkills (profession ↔ skill)
  - ProfessionUnlocks (profession ↔ profession/skill?, should be handled via Skill)
- Implement relationChangeFunc to upsert the join records (similar to StrongboxLoots approach).

**API research to do:**
- Inspect `/api/professions` response structure to confirm field names.
- Inspect DB schema for profession-category / skills / unlocks joins.

---

### 2) Skill
**Observed shape (UI):**
- `Id`, `Name`
- `Category` (object with `Name`)
- `Properties`: `Description`, `HpIncrease`, `IsHidden`, `IsExtractable`
- `Professions` (array)
- `Unlocks` (array)

**Schema tasks:**
- Add `common/schemas/Skill.js` matching UI structure.
- Use `NamedEntity` for `Category`, `Professions`, `Unlocks`.
- Add to `EntitySchemas` (both locations).

**Changes endpoint tasks:**
- Map `Skill` → `skills` in `getEntityCategory`.
- Consider sanitizing `Properties.Description`.

**Bot UpsertConfig (needs DB research):**
- Table likely `"Skills"`.
- Columns: `Name`, `Description`, `HpIncrease`, `IsHidden`, `IsExtractable`, `CategoryId`.
- Relation tables likely:
  - SkillProfessions (skill ↔ profession)
  - SkillUnlocks (skill ↔ skill/profession? is also a profession to skill mapping, but indicates at what profession level a hidden skill becomes unlocked, make sure to add a way to edit this information on the Profession wiki page (unless it exists already for Skill))s
- Implement relationChangeFunc accordingly.

**API research to do:**
- Inspect `/api/skills` response structure.
- Confirm DB join tables + expected column names for professions/unlocks.

---

### 3) Location
**Observed shape (schema/UI):**
- `Name`
- `Properties`: `Description`, `Type`, `Coordinates {Longitude, Latitude, Altitude}`
- `Planet` (NamedEntity)

**Schema tasks:**
- Confirm `Location.js` aligns with API output (currently matches).
- Ensure schema exists in both `common` and `nexus/src/lib/common`.
- Add to `EntitySchemas` if missing (already present).

**Changes endpoint tasks:**
- Map `Location` → `locations` in `getEntityCategory` (already present).
- Consider sanitizing `Properties.Description`.

**Bot UpsertConfig (needs DB research):**
- Table likely `"Locations"` (verify).
- Columns: `Name`, `Description`, `Type`, `Longitude`, `Latitude`, `Altitude`, `PlanetId`.
- Ensure planet lookup uses `Planets.Name` or `Planets.TechnicalName` (match existing items).

**API research to do:**
- Inspect `/api/locations?Planet=...` data shape.
- Confirm DB column names for coordinates.

---

### 4) Area
**Observed shape (schema/UI):**
- `Name`
- `Properties`: `Description`, `Type`, `Shape`, `Data`, `Coordinates`
- `Planet` (NamedEntity)

**Schema tasks:**
- Confirm `Area.js` in both schema locations.
- Add to `EntitySchemas` if missing (already present).

**Changes endpoint tasks:**
- Map `Area` → `areas` in `getEntityCategory` (already present).
- Consider sanitizing `Properties.Description`.

**Bot UpsertConfig (needs DB research):**
- Table likely `"Areas"`.
- Columns: `Name`, `Type`, `Shape`, `Data`, `Altitude`, `PlanetId`.
- Decide how to map `Properties.Coordinates` → DB fields (Altitude?).
- Ensure non-MobArea create/update uses correct Type and shape.

**API research to do:**
- Inspect `/api/areas?Planet=...` data shape.
- Confirm DB column names for shape/data/altitude.

---

### 5) Strongbox
**Observed shape (UI):**
- `Name`
- `Properties`: `Description`, `Weight`, `Economy.MaxTT`
- `Loots[]`: `Item`, `Rarity`, `AvailableFrom`, `AvailableUntil`

**Schema tasks:**
- Fix export name to `Strongbox`.
- Add missing `Properties.Weight` + `Properties.Economy.MaxTT`.
- Update `Loots[].AvailableFrom/AvailableUntil` to `string` with `format: "date"` or nullable string.
- Add to `EntitySchemas` (both locations).

**Changes endpoint tasks:**
- Map `Strongbox` entity category for duplicate checks (likely `items` or `strongboxes`; confirm API endpoint).
- Consider sanitizing `Properties.Description`.

**Bot UpsertConfig:**
- Existing config only maps Name + Description; extend to Weight + MaxTT.
- Validate `offset` and `applyStrongboxLootsChanges` ID math align with DB IDs.

**API research to do:**
- Inspect `/api/strongboxes` response structure.
- Confirm DB table column names (Strongboxes + StrongboxLoots).

---

## Suggested Implementation Order
1. Fix schemas + EntitySchemas (includes Strongbox export bug).
2. Update `/api/changes` category mapping + Description sanitization.
3. Add/extend bot UpsertConfigs (Profession/Skill/Location/Area/Strongbox).
4. Verify DB enum migrations applied.
5. Manual QA flows for each entity (create/update, draft/pending, approve).

## Validation Checklist (per entity)
- Create mode: `/.../?mode=create` saves draft and submits pending.
- Update mode: edit existing entity, save draft, submit.
- Pending change preview loads in page and admin view.
- Bot applies Approved change to DB and entity refresh matches.
- Duplicate-name checks use correct category endpoint.
