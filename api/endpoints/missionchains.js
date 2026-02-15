const { pool } = require('./dbClient');
const { getObjectByIdOrName } = require('./utils');
const { formatMissionSummary, getMissionChainGraph } = require('./missions');
const { withCache } = require('./responseCache');

const baseQuery = `
  SELECT "MissionChains".*, "Planets"."Name" AS "Planet"
  FROM ONLY "MissionChains"
  LEFT JOIN ONLY "Planets" ON "MissionChains"."PlanetId" = "Planets"."Id"
`;

const missionsQuery = `
  SELECT "Missions".*, "Planets"."Name" AS "Planet", "MissionChains"."Name" AS "MissionChain"
  FROM ONLY "Missions"
  LEFT JOIN ONLY "Planets" ON "Missions"."PlanetId" = "Planets"."Id"
  LEFT JOIN ONLY "MissionChains" ON "Missions"."MissionChainId" = "MissionChains"."Id"
`;

function formatMissionChainSummary(row) {
  return {
    Id: row.Id,
    Name: row.Name,
    Properties: {
      Type: row.Type ?? null,
      Description: row.Description ?? null
    },
    Planet: row.Planet ? { Name: row.Planet, Links: { "$Url": `/planets/${row.PlanetId}` } } : null,
    Links: { "$Url": `/missionchains/${row.Id}` }
  };
}

async function getMissionChains(planetId = null) {
  const params = [];
  let sql = baseQuery;
  if (planetId) {
    params.push(planetId);
    sql += ' WHERE "MissionChains"."PlanetId" = $1';
  }
  const { rows } = await pool.query(sql, params);
  return rows.map(formatMissionChainSummary);
}

async function getMissionsForChain(chainId) {
  const { rows } = await pool.query(
    `${missionsQuery} WHERE "Missions"."MissionChainId" = $1 ORDER BY "Missions"."Id"`,
    [chainId]
  );
  return rows.map(formatMissionSummary);
}

async function getMissionChain(idOrName) {
  const row = await getObjectByIdOrName(baseQuery, 'MissionChains', idOrName);
  if (!row) return null;
  const [missions, graph] = await Promise.all([
    getMissionsForChain(row.Id),
    getMissionChainGraph(row.Id)
  ]);
  return {
    ...formatMissionChainSummary(row),
    Missions: missions,
    Graph: graph
  };
}

function register(app) {
  app.get('/missionchains', async (req, res) => {
    try {
      const planetId = req.query.planetId || req.query.PlanetId;
      const parsed = planetId ? Number(planetId) : null;
      const result = Number.isFinite(parsed)
        ? await getMissionChains(parsed)
        : await withCache('/missionchains', ['MissionChains', 'Planets'], getMissionChains);
      res.json(result);
    } catch (e) {
      res.status(500).json({ error: 'Failed to fetch mission chains' });
    }
  });

  app.get('/missionchains/:chain/graph', async (req, res) => {
    try {
      const chainRow = await getObjectByIdOrName(baseQuery, 'MissionChains', req.params.chain);
      if (!chainRow) return res.status(404).send();
      const graph = await getMissionChainGraph(chainRow.Id);
      res.json(graph);
    } catch (e) {
      res.status(500).json({ error: 'Failed to fetch mission chain graph' });
    }
  });

  app.get('/missionchains/:chain', async (req, res) => {
    try {
      const chain = await getMissionChain(req.params.chain);
      if (!chain) return res.status(404).send();
      res.json(chain);
    } catch (e) {
      res.status(500).json({ error: 'Failed to fetch mission chain' });
    }
  });
}

module.exports = { register, getMissionChains, getMissionChain, formatMissionChainSummary };
