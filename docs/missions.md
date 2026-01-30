# Missions: Page, Data Model, and Integration Spec

This document captures requirements and a proposed implementation plan for a new Missions feature, including UI, routing, data model, and DB integration.

## Routes

- List and detail: `/informations/missions/[[slug]]`
  - No slug: list of mission chains with planet filters.
  - With slug: detail view for a mission or mission chain.
  - Slugs should be URL-safe, unique per mission or chain.

## UI/UX

- Planet filters: Reuse the planet filter UX from mobs to filter missions by planet. Missions are planet-specific; chains can span multiple planets.
- List view: Display missions grouped or filterable by planet. Allow search by name.
- Detail view:
  - Show chain context (predecessors/successors) to reflect branching/merging like git commits.
  - Show mission steps with objectives and optional descriptions.
  - Show rewards with PED values. For skill rewards, reference the item id of the corresponding "<Skill Name> Skill Implant (L)".

## Mission graph model

Chains are implied by completion requirements between missions. Model as a directed acyclic graph (DAG):
- Each edge means: to start/complete mission B, mission A must be completed.
- Branching/merging supported via multiple predecessors/successors.

Recommended tables (see Data Model): `MissionDependencies` linking `MissionId -> PrerequisiteMissionId`.

## Data model

Tables (proposed):

- Missions
  - Id (PK)
  - Name (text)
  - Slug (text, unique)
  - PlanetId (nullable: some missions may be cross-planet, but instances are planet-specific)
  - Description (text, optional)
  - Repeatable (bool, optional)

- MissionDependencies
  - MissionId (FK -> Missions)
  - PrerequisiteMissionId (FK -> Missions)
  - Constraint: composite PK (MissionId, PrerequisiteMissionId)

- MissionSteps
  - Id (PK)
  - MissionId (FK -> Missions)
  - Index (int, 0-based or 1-based ordering)
  - Title (text, optional)
  - Description (text, optional)

- MissionObjectives
  - Id (PK)
  - StepId (FK -> MissionSteps)
  - Type (enum): Dialog | KillCount | KillCycle | Explore | Interact | HandIn
  - Payload (jsonb): type-specific payload (see below)

- MissionRewards
  - Id (PK)
  - MissionId (FK -> Missions)
  - Items (jsonb[]) of { itemId: number, quantity?: number, pedValue: number }
  - Skills (jsonb[]) of { skillItemId: number, pedValue: number }
  - Unlocks (text[]): free-form descriptions for unique unlocks

- Npcs
  - Id (PK)
  - Name (text)
  - Description (text, optional)
  - PlanetId (FK)
  - Longitude (numeric), Latitude (numeric), Altitude (numeric)

- Interactables
  - Id (PK)
  - Name (text)
  - Description (text, optional)
  - PlanetId (FK)
  - Longitude (numeric), Latitude (numeric), Altitude (numeric)

- Quest Locations are represented as `Areas` with `Type = 'QuestArea'` (reuses existing `Areas` table), so no new table needed for quest areas.

### Objective payloads (jsonb)

- Dialog
  - { targetLocationId: number, dialogText?: string }
  - `targetLocationId` references unified `Locations` view (see below).

- KillCount
  - { targets: number[], totalCountRequired: number, countsPerTarget?: Record<number, number> }
  - `targets` are Mob Maturity IDs. Progress can be summed across the target set unless `countsPerTarget` is provided.

- KillCycle
  - { targets: number[], pedToCycle: number }
  - `targets` are Mob Maturity IDs; progress measured by PED cycled.

- Explore
  - { planetId: number, longitude: number, latitude: number, altitude: number }

- Interact
  - { targetLocationId: number }
  - References an NPC or Interactable via `Locations` view.

- HandIn
  - { npcLocationId: number, items: { itemId: number, quantity?: number, minPedValue?: number, pedValue?: number }[] }
  - `npcLocationId` references the recipient NPC via `Locations` view.

### Rewards

- Items and Skills must carry a PED value (not always fully repaired).
- Skills are represented by item ids of "<Skill Name> Skill Implant (L)".
- Unlocks are represented as free-form descriptions.

## Unified Locations view

There is an existing view that unifies Teleporters, Areas, and Estates:

```sql
CREATE OR REPLACE VIEW public."Locations"
 AS
 SELECT "Teleporters"."Id" + 100000 AS "Id",
    "Teleporters"."Name",
    "Teleporters"."Longitude",
    "Teleporters"."Latitude",
    "Teleporters"."Altitude",
    "Teleporters"."PlanetId",
    'Teleporter'::text AS "Type"
   FROM ONLY "Teleporters"
UNION ALL
 SELECT "Areas"."Id" + 200000 AS "Id",
    "Areas"."Name",
    "Areas"."Longitude",
    "Areas"."Latitude",
    "Areas"."Altitude",
    "Areas"."PlanetId",
    "Areas"."Type"::text AS "Type"
   FROM ONLY "Areas"
UNION ALL
 SELECT "Estates"."Id" + 300000 AS "Id",
    "Estates"."Name",
    "Estates"."Longitude",
    "Estates"."Latitude",
    "Estates"."Altitude",
    "Estates"."PlanetId",
    "Estates"."Type"::text AS "Type"
   FROM ONLY "Estates";
```

To include NPCs and Interactables, extend the view and introduce new id ranges:

```sql
-- Proposed additions (requires Npcs and Interactables tables)
UNION ALL
 SELECT "Npcs"."Id" + 400000 AS "Id",
    "Npcs"."Name",
    "Npcs"."Longitude",
    "Npcs"."Latitude",
    "Npcs"."Altitude",
    "Npcs"."PlanetId",
    'Npc'::text AS "Type"
   FROM ONLY "Npcs"
UNION ALL
 SELECT "Interactables"."Id" + 500000 AS "Id",
    "Interactables"."Name",
    "Interactables"."Longitude",
    "Interactables"."Latitude",
    "Interactables"."Altitude",
    "Interactables"."PlanetId",
    'Interactable'::text AS "Type"
   FROM ONLY "Interactables";
```

Notes:
- Quest Locations are `Areas` with `Type = 'QuestArea'`, so they are already included via the `Areas` union.
- Ensure id ranges don't conflict with existing unions.

## API endpoints (proposed)

- GET `/missions?planetId=<id>`: list missions filtered by planet.
- GET `/missions/:slug` or `/missions/:id`: return mission details, steps, objectives, rewards, dependencies.
- GET `/missions/:id/graph`: return neighbors (predecessors/successors) for chain visualization.
- POST/PUT/PATCH endpoints for admin tools (optional) to manage missions, steps, objectives, rewards, NPCs, Interactables.

## Frontend implementation notes

- Create route folder: `nexus/src/routes/informations/missions/[[slug]]/` with `+page.svelte` and `+page.js`.
- Reuse planet filter component/logic from mobs to filter list view.
- Render steps and objectives with type-specific UI (e.g., waypoint link for Explore, mob maturity lists for Kill objectives).
- Show rewards with PED values; for skills, resolve item by `skillItemId`.
- Optional: graph mini-map to show chain predecessors/successors.

## Data examples

Mission example:

```json
{
  "id": 101,
  "name": "IFN Challenge: Arret Stage 1",
  "slug": "ifn-challenge-arret-stage-1",
  "planetId": 2,
  "description": "Hunt Arret to help the IFN.",
  "steps": [
    {
      "index": 1,
      "title": "Report in",
      "objectives": [
        { "type": "Dialog", "payload": { "targetLocationId": 400123, "dialogText": "Report to Sergeant X" } }
      ]
    },
    {
      "index": 2,
      "title": "Hunt Arret",
      "objectives": [
        { "type": "KillCount", "payload": { "targets": [90011, 90012], "totalCountRequired": 100 } }
      ],
      "description": "Any maturity counts."
    }
  ],
  "rewards": {
    "items": [ { "itemId": 700345, "pedValue": 3.5 } ],
    "skills": [ { "skillItemId": 800123, "pedValue": 1.2 } ],
    "unlocks": [ "Unlocks Arret Stage 2" ]
  }
}
```

## Edge cases

- Cross-planet chains: each mission is planet-specific; dependencies can cross planets.
- Variable kill objective targets: use `countsPerTarget` when exact per-target counts are required.
- Partial TT/ped values for rewards must be stored explicitly.
- NPC/Interactable without precise coordinates: allow nullable coordinates but still include in `Locations` with best-known location.

## Acceptance criteria

- List view at `/informations/missions/` with planet filters.
- Detail view at `/informations/missions/[slug]` showing steps, objectives, and rewards.
- Data model supports all objective types and chain dependencies.
- NPCs, Interactables, and Quest Areas surface in `Locations` view.

## Next steps

1. Create DB migrations for new tables and extend the `Locations` view.
2. Add API endpoints in `api/endpoints/missions.js` and related modules.
3. Implement frontend route and components; reuse planet filter UI.
4. Seed a few missions to validate the model and UI.
