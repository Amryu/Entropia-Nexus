const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { withCache } = require('./responseCache');

const baseQuery = `
  SELECT "Missions".*, "Planets"."Name" AS "Planet",
    "MissionChains"."Name" AS "MissionChain",
    "MissionChains"."Description" AS "MissionChainDescription",
    "MissionChains"."PlanetId" AS "MissionChainPlanetId",
    "ChainPlanets"."Name" AS "MissionChainPlanet",
    "Events"."Name" AS "EventName",
    "StartLoc"."Name" AS "StartLocationName",
    "StartLoc"."Longitude" AS "StartLocationLongitude",
    "StartLoc"."Latitude" AS "StartLocationLatitude",
    "StartLoc"."Altitude" AS "StartLocationAltitude",
    "StartLoc"."PlanetId" AS "StartLocationPlanetId",
    "StartLocPlanet"."Name" AS "StartLocationPlanet"
  FROM ONLY "Missions"
  LEFT JOIN ONLY "Planets" ON "Missions"."PlanetId" = "Planets"."Id"
  LEFT JOIN ONLY "MissionChains" ON "Missions"."MissionChainId" = "MissionChains"."Id"
  LEFT JOIN ONLY "Planets" AS "ChainPlanets" ON "MissionChains"."PlanetId" = "ChainPlanets"."Id"
  LEFT JOIN ONLY "Events" ON "Missions"."EventId" = "Events"."Id"
  LEFT JOIN ONLY "Locations" AS "StartLoc" ON "Missions"."StartLocationId" = "StartLoc"."Id"
  LEFT JOIN ONLY "Planets" AS "StartLocPlanet" ON "StartLoc"."PlanetId" = "StartLocPlanet"."Id"
`;

function formatMissionSummary(row) {
  return {
    Id: row.Id,
    Name: row.Name,
    Properties: {
      Type: row.Type ?? null,
      Description: row.Description ?? null,
      CooldownDuration: row.CooldownDuration ?? null,
      CooldownStartsOn: row.CooldownStartsOn ?? null
    },
    Planet: row.Planet ? { Name: row.Planet, Links: { "$Url": `/planets/${row.PlanetId}` } } : null,
    MissionChain: row.MissionChain ? {
      Name: row.MissionChain,
      Description: row.MissionChainDescription ?? null,
      Planet: row.MissionChainPlanet ? { Name: row.MissionChainPlanet, Links: { "$Url": `/planets/${row.MissionChainPlanetId}` } } : null,
      Links: { "$Url": `/missionchains/${row.MissionChainId}` }
    } : null,
    Event: row.EventId ? {
      Id: row.EventId,
      Name: row.EventName ?? null,
      Links: { "$Url": `/events/${row.EventId}` }
    } : null,
    StartLocationId: row.StartLocationId ?? null,
    StartLocation: row.StartLocationId ? {
      Id: row.StartLocationId,
      Name: row.StartLocationName ?? null,
      Planet: row.StartLocationPlanet ? { Name: row.StartLocationPlanet, Links: { "$Url": `/planets/${row.StartLocationPlanetId}` } } : null,
      Coordinates: {
        Longitude: row.StartLocationLongitude != null ? Number(row.StartLocationLongitude) : null,
        Latitude: row.StartLocationLatitude != null ? Number(row.StartLocationLatitude) : null,
        Altitude: row.StartLocationAltitude != null ? Number(row.StartLocationAltitude) : null
      },
      Links: { "$Url": `/locations/${row.StartLocationId}` }
    } : null,
    Links: { "$Url": `/missions/${row.Id}` }
  };
}

function formatMissionDetail(row, related) {
  const base = formatMissionSummary(row);
  const missionId = row.Id;
  return {
    ...base,
    Steps: related.Steps[missionId] || [],
    Rewards: related.Rewards[missionId] || { Items: [], Skills: [], Unlocks: [] },
    Dependencies: related.Dependencies[missionId] || { Prerequisites: [], Dependents: [] }
  };
}

async function getMissionSteps(missionIds) {
  if (!missionIds.length) return [];
  const { rows } = await pool.query(
    'SELECT * FROM ONLY "MissionSteps" WHERE "MissionId" = ANY($1) ORDER BY "MissionId", "Index", "Id"',
    [missionIds]
  );
  return rows;
}

async function getMissionObjectives(stepIds) {
  if (!stepIds.length) return [];
  const { rows } = await pool.query(
    'SELECT * FROM ONLY "MissionObjectives" WHERE "StepId" = ANY($1) ORDER BY "StepId", "Id"',
    [stepIds]
  );
  return rows;
}

async function getMissionRewards(missionIds) {
  if (!missionIds.length) return [];
  const { rows } = await pool.query(
    'SELECT * FROM ONLY "MissionRewards" WHERE "MissionId" = ANY($1)',
    [missionIds]
  );
  return rows;
}

async function getMissionDependencies(missionIds) {
  if (!missionIds.length) return { prerequisites: [], dependents: [] };

  const [prereqResult, dependentResult] = await Promise.all([
    pool.query(
      `SELECT md."MissionId", md."PrerequisiteMissionId", m."Name" AS "PrerequisiteName"
       FROM ONLY "MissionDependencies" md
       LEFT JOIN ONLY "Missions" m ON md."PrerequisiteMissionId" = m."Id"
       WHERE md."MissionId" = ANY($1)`,
      [missionIds]
    ),
    pool.query(
      `SELECT md."PrerequisiteMissionId" AS "MissionId", md."MissionId" AS "DependentMissionId", m."Name" AS "DependentName"
       FROM ONLY "MissionDependencies" md
       LEFT JOIN ONLY "Missions" m ON md."MissionId" = m."Id"
       WHERE md."PrerequisiteMissionId" = ANY($1)`,
      [missionIds]
    )
  ]);

  return {
    prerequisites: prereqResult.rows,
    dependents: dependentResult.rows
  };
}

async function loadMissionRelated(missionIds) {
  if (!missionIds.length) {
    return { Steps: {}, Rewards: {}, Dependencies: {} };
  }

  const [steps, rewards, dependencyRows] = await Promise.all([
    getMissionSteps(missionIds),
    getMissionRewards(missionIds),
    getMissionDependencies(missionIds)
  ]);

  const objectives = await getMissionObjectives(steps.map(s => s.Id));

  const objectivesByStepId = {};
  for (const obj of objectives) {
    if (!objectivesByStepId[obj.StepId]) objectivesByStepId[obj.StepId] = [];
    objectivesByStepId[obj.StepId].push({
      Id: obj.Id,
      Type: obj.Type,
      Payload: obj.Payload
    });
  }

  const stepsByMissionId = {};
  for (const step of steps) {
    if (!stepsByMissionId[step.MissionId]) stepsByMissionId[step.MissionId] = [];
    stepsByMissionId[step.MissionId].push({
      Id: step.Id,
      Index: step.Index,
      Title: step.Title ?? null,
      Description: step.Description ?? null,
      Objectives: objectivesByStepId[step.Id] || []
    });
  }

  const rewardsByMissionId = {};
  for (const reward of rewards) {
    rewardsByMissionId[reward.MissionId] = {
      Items: reward.Items || [],
      Skills: reward.Skills || [],
      Unlocks: reward.Unlocks || []
    };
  }

  const dependenciesByMissionId = {};
  for (const row of dependencyRows.prerequisites) {
    if (!dependenciesByMissionId[row.MissionId]) {
      dependenciesByMissionId[row.MissionId] = { Prerequisites: [], Dependents: [] };
    }
    dependenciesByMissionId[row.MissionId].Prerequisites.push({
      Id: row.PrerequisiteMissionId,
      Name: row.PrerequisiteName ?? null,
      Links: { "$Url": `/missions/${row.PrerequisiteMissionId}` }
    });
  }

  for (const row of dependencyRows.dependents) {
    if (!dependenciesByMissionId[row.MissionId]) {
      dependenciesByMissionId[row.MissionId] = { Prerequisites: [], Dependents: [] };
    }
    dependenciesByMissionId[row.MissionId].Dependents.push({
      Id: row.DependentMissionId,
      Name: row.DependentName ?? null,
      Links: { "$Url": `/missions/${row.DependentMissionId}` }
    });
  }

  return {
    Steps: stepsByMissionId,
    Rewards: rewardsByMissionId,
    Dependencies: dependenciesByMissionId
  };
}

async function getMissions(planetId = null) {
  const params = [];
  let sql = baseQuery;
  if (planetId) {
    params.push(planetId);
    sql += ' WHERE "Missions"."PlanetId" = $1';
  }
  const { rows } = await pool.query(sql, params);
  return rows.map(formatMissionSummary);
}

async function getMission(idOrName) {
  const row = await getObjectByIdOrName(baseQuery, 'Missions', idOrName);
  if (!row) return null;
  const related = await loadMissionRelated([row.Id]);
  return formatMissionDetail(row, related);
}

async function getMissionChainGraph(chainId) {
  const { rows: missions } = await pool.query(
    'SELECT "Id", "Name", "Type", "PlanetId" FROM ONLY "Missions" WHERE "MissionChainId" = $1 ORDER BY "Id"',
    [chainId]
  );
  const ids = missions.map(m => m.Id);
  const edges = ids.length
    ? (await pool.query(
        'SELECT "MissionId", "PrerequisiteMissionId" FROM ONLY "MissionDependencies" WHERE "MissionId" = ANY($1) AND "PrerequisiteMissionId" = ANY($1)',
        [ids]
      )).rows
    : [];

  return {
    nodes: missions.map(m => ({ Id: m.Id, Name: m.Name, Type: m.Type ?? null, PlanetId: m.PlanetId ?? null })),
    edges: edges.map(e => ({ FromId: e.PrerequisiteMissionId, ToId: e.MissionId }))
  };
}

async function getMissionLocalGraph(missionId) {
  const { rows: missionRows } = await pool.query('SELECT "Id" FROM ONLY "Missions" WHERE "Id" = $1', [missionId]);
  if (!missionRows.length) return null;

  const prereqRows = await pool.query(
    'SELECT "PrerequisiteMissionId" FROM ONLY "MissionDependencies" WHERE "MissionId" = $1',
    [missionId]
  );
  const prereqIds = prereqRows.rows.map(r => r.PrerequisiteMissionId);

  const dependentRows = await pool.query(
    'SELECT "MissionId" FROM ONLY "MissionDependencies" WHERE "PrerequisiteMissionId" = $1',
    [missionId]
  );
  const dependentIds = dependentRows.rows.map(r => r.MissionId);

  const prereq2Ids = prereqIds.length
    ? (await pool.query(
        'SELECT "PrerequisiteMissionId" FROM ONLY "MissionDependencies" WHERE "MissionId" = ANY($1)',
        [prereqIds]
      )).rows.map(r => r.PrerequisiteMissionId)
    : [];

  const dependent2Ids = dependentIds.length
    ? (await pool.query(
        'SELECT "MissionId" FROM ONLY "MissionDependencies" WHERE "PrerequisiteMissionId" = ANY($1)',
        [dependentIds]
      )).rows.map(r => r.MissionId)
    : [];

  const nodeIds = Array.from(new Set([missionId, ...prereqIds, ...dependentIds, ...prereq2Ids, ...dependent2Ids]));
  if (!nodeIds.length) return { nodes: [], edges: [] };

  const nodes = (await pool.query(
    'SELECT "Id", "Name", "Type", "PlanetId" FROM ONLY "Missions" WHERE "Id" = ANY($1)',
    [nodeIds]
  )).rows;

  const edges = (await pool.query(
    'SELECT "MissionId", "PrerequisiteMissionId" FROM ONLY "MissionDependencies" WHERE "MissionId" = ANY($1) AND "PrerequisiteMissionId" = ANY($1)',
    [nodeIds]
  )).rows;

  return {
    nodes: nodes.map(m => ({ Id: m.Id, Name: m.Name, Type: m.Type ?? null, PlanetId: m.PlanetId ?? null })),
    edges: edges.map(e => ({ FromId: e.PrerequisiteMissionId, ToId: e.MissionId }))
  };
}

async function getMissionGraph(idOrName) {
  const row = await getObjectByIdOrName('SELECT "Id", "MissionChainId" FROM ONLY "Missions"', 'Missions', idOrName);
  if (!row) return null;
  if (row.MissionChainId) {
    return { ...(await getMissionChainGraph(row.MissionChainId)), source: 'chain', chainId: row.MissionChainId, rootId: row.Id };
  }
  return { ...(await getMissionLocalGraph(row.Id)), source: 'local', rootId: row.Id };
}

function register(app) {
  app.get('/missions', async (req, res) => {
    try {
      const planetId = req.query.planetId || req.query.PlanetId;
      const parsed = planetId ? Number(planetId) : null;
      const result = Number.isFinite(parsed)
        ? await getMissions(parsed)
        : await withCache('/missions', ['Missions', 'Planets', 'MissionChains', 'Events', 'Locations'], getMissions);
      res.json(result);
    } catch (e) {
      res.status(500).json({ error: 'Failed to fetch missions' });
    }
  });

  app.get('/missions/:mission/graph', async (req, res) => {
    try {
      const graph = await getMissionGraph(req.params.mission);
      if (!graph) return res.status(404).send();
      res.json(graph);
    } catch (e) {
      res.status(500).json({ error: 'Failed to fetch mission graph' });
    }
  });

  app.get('/missions/:mission', async (req, res) => {
    try {
      const mission = await getMission(req.params.mission);
      if (!mission) return res.status(404).send();
      res.json(mission);
    } catch (e) {
      res.status(500).json({ error: 'Failed to fetch mission' });
    }
  });
}

module.exports = {
  register,
  getMissions,
  getMission,
  getMissionGraph,
  getMissionChainGraph,
  formatMissionSummary,
  formatMissionDetail
};
