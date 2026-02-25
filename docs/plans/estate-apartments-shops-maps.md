# Plan: Estates in Maps + Shops (Apartments + Shops)

## Goal
Add Estate support to the change workflow and UI:
- **Shops** remain managed in `/market/shops`.
- **Apartments** managed in **Maps**.
- Both map to the same Estates table and **EstateSections** 1:n relationship.

## Constraints / Source of Truth
- Estates appear in `public."Locations"` view with offsets:
  - Teleporters: `Id + 100000`
  - Areas: `Id + 200000`
  - Estates: `Id + 300000`
- Estates table fields: `Name`, `Description`, `Longitude`, `Latitude`, `Altitude`, `PlanetId`, `Type` (`Shop` | `Apartment`), `OwnerId`, `ItemTradeAvailable`, `MaxGuests`
- EstateSections PK: (`EstateId`, `Name`)
- ItemTradeAvailable: **true for shops**, **false for apartments**
- OwnerId: **discord user id** (from nexus_users users table)

## Phase 1 — Data + Change Pipeline

### 1) Schema updates
- Update `common/schemas/Location.js` and `Area.js` if needed for estate offsets in map selection logic.
- Add / update estate schema (if needed) for `Shop` and new `Apartment`:
  - Ensure `Sections: [{ Name, Description, ItemPoints }]`
  - Ensure coordinates + Planet + Description are covered.

### 2) Change endpoint
- Update `/api/changes` category mapping if needed for `Apartment` entity or Estate changes.
- Ensure description sanitization covers `Properties.Description` (already done).

### 3) Bot upsert changes (nexus-bot)
- Extend `UpsertConfigs`:
  - **Shop**:
    - Already upserts into `Estates` with `Type='Shop'`.
    - Confirm it sets `ItemTradeAvailable=true`.
    - Ensure `EstateSections` relation change persists.
  - **Apartment** (new):
    - Same table as Shop: `Estates`
    - `Type='Apartment'`
    - `ItemTradeAvailable=false`
    - Uses `EstateSections` for sections
    - Coordinates + PlanetId + Description + MaxGuests + OwnerId

### 4) OwnerId mapping
- Determine how `OwnerId` is supplied in UI:
  - If only admins can edit owner, add explicit field.
  - Otherwise, preserve existing owner if not in change payload.

## Phase 2 — Maps (Apartment UI)

### 1) Maps data load
- When loading locations, include estate locations (already in Locations view).
- Ensure filters allow `Type='Apartment'` visibility by default (if desired).
- Add edit mode support to create/update **Apartment**:
  - Type dropdown includes Apartment
  - When Type is Apartment, treat it as Estate in DB
  - Sections editor (EstateSections) for apartments

### 2) Map detail panel
- Display Estate sections for Apartment in view mode (shows as badges, the same way it is done one /market/shops, same styling).
- Edit: allow add/remove sections (Name, ItemPoints)
- Ensure coordinates and planet selection work as with Location/Area.

### 3) Create flow
- `?mode=create` for Apartment should initialize Estate template:
  - `Type='Apartment'`, `ItemTradeAvailable=false`
  - `OwnerId` optional (admin-only! same for shops)
  - `Sections=[]`

## Phase 3 — Shops page adjustments

### 1) Ensure Shop changes still use Estates
- Confirm Shop change flow continues:
  - `Type='Shop'`, `ItemTradeAvailable=true`
  - `EstateSections` upsert

### 2) Add missing fields to Shop edit
- If MaxGuests / Sections are missing in shop UI, decide which are editable.
- Ensure sections editor is shared between Shops and Apartments.

## Phase 4 — Validation / QA

### Scenarios
- Create Apartment in Maps → draft → submit → approve → shows in Maps and Locations view.
- Update Apartment → sections update persists.
- Create Shop in Shops page → sections update persists.
- Ensure Locations view offsets used correctly (Estate IDs + 300000).

### Regression checks
- Existing Shop changes still work.
- Map selection for Teleporters/Areas unaffected.

## Open Questions (needs your decision)
- Should Apartments be visible by default in Maps filters?
- Should OwnerId be editable or fixed?
- Which Shop fields are user-editable vs admin-only?
