const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, loadClassIds } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  BlueprintBooks: 'SELECT "BlueprintBooks"."Id", "BlueprintBooks"."Name", "BlueprintBooks"."Description", "PlanetId", "Planets"."Name" AS "Planet", "Weight", "Value" FROM ONLY "BlueprintBooks" LEFT JOIN ONLY "Planets" ON "BlueprintBooks"."PlanetId" = "Planets"."Id"',
};

function formatBlueprintBook(x, classIds){
  return {
    Id: x.Id,
    ClassId: classIds[x.Id] || null,
    ItemId: x.Id + idOffsets.BlueprintBooks,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight !== null ? Number(x.Weight) : null,
      Economy: { Value: x.Value !== null ? Number(x.Value) : null },
    },
    Planet: { Name: x.Planet, Links: { "$Url": `/planets/${x.PlanetId}` } },
    Links: { "$Url": `/blueprintbooks/${x.Id}` },
  };
}

// DB methods
async function getBlueprintBooks() {
  const { rows } = await pool.query(queries.BlueprintBooks);
  const classIds = await loadClassIds('BlueprintBook', rows.map(r => r.Id));
  return rows.map(r => formatBlueprintBook(r, classIds));
}
const getBlueprintBook = async (idOrName) => { const row = await getObjectByIdOrName(queries.BlueprintBooks, 'BlueprintBooks', idOrName); if (!row) return null; const classIds = await loadClassIds('BlueprintBook', [row.Id]); return formatBlueprintBook(row, classIds); };

// Endpoints
function register(app){
  /**
   * @swagger
   * /blueprintbooks:
   *  get:
   *    description: Get all blueprint books
   *    responses:
   *      '200':
   *        description: A list of blueprint books
   */
  app.get('/blueprintbooks', async (req,res) => { res.json(await withCache('/blueprintbooks', ['BlueprintBooks', 'Planets', 'ClassIds'], getBlueprintBooks)); });
  /**
   * @swagger
   * /blueprintbooks/{blueprintBook}:
   *  get:
   *    description: Get a blueprint book by name or id
   *    parameters:
   *      - in: path
   *        name: blueprintBook
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the blueprint book
   *    responses:
   *      '200':
   *        description: The blueprint book
   *      '404':
   *        description: Blueprint book not found
   */
  app.get('/blueprintbooks/:blueprintBook', async (req,res) => {
    const result = await withCachedLookup('/blueprintbooks', ['BlueprintBooks', 'Planets', 'ClassIds'], getBlueprintBooks, req.params.blueprintBook);
    if (result) res.json(result); else res.status(404).send();
  });
}

module.exports = { register, getBlueprintBooks, getBlueprintBook };
