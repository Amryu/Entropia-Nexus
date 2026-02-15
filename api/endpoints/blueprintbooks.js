const { idOffsets } = require('./constants');
const { getObjects, getObjectByIdOrName } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  BlueprintBooks: 'SELECT "BlueprintBooks"."Id", "BlueprintBooks"."Name", "BlueprintBooks"."Description", "PlanetId", "Planets"."Name" AS "Planet", "Weight", "Value" FROM ONLY "BlueprintBooks" LEFT JOIN ONLY "Planets" ON "BlueprintBooks"."PlanetId" = "Planets"."Id"',
};

function formatBlueprintBook(x){
  return {
    Id: x.Id,
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
const getBlueprintBooks = () => getObjects(queries.BlueprintBooks, formatBlueprintBook);
const getBlueprintBook = async (idOrName) => { const row = await getObjectByIdOrName(queries.BlueprintBooks, 'BlueprintBooks', idOrName); return row ? formatBlueprintBook(row) : null; };

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
  app.get('/blueprintbooks', async (req,res) => { res.json(await withCache('/blueprintbooks', ['BlueprintBooks', 'Planets'], getBlueprintBooks)); });
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
    const result = await withCachedLookup('/blueprintbooks', ['BlueprintBooks', 'Planets'], getBlueprintBooks, req.params.blueprintBook);
    if (result) res.json(result); else res.status(404).send();
  });
}

module.exports = { register, getBlueprintBooks, getBlueprintBook };
