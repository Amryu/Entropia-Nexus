const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = { StorageContainers: 'SELECT "StorageContainers".*, "Planets"."Name" AS "Planet" FROM ONLY "StorageContainers" LEFT JOIN ONLY "Planets" ON "StorageContainers"."PlanetId" = "Planets"."Id"' };

function formatStorageContainer(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.StorageContainers,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      ItemCapacity: x.Capacity != null ? Number(x.Capacity) : null,
      WeightCapacity: x.MaxWeight != null ? Number(x.MaxWeight) : null,
      Economy: { MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null },
    },
    Planet: { Name: x.Planet, Links: { "$Url": `/planets/${x.PlanetId}` } },
    Links: { "$Url": `/storagecontainers/${x.Id}` },
  };
}

const getStorageContainers = () => getObjects(queries.StorageContainers, formatStorageContainer);
const getStorageContainer = async(idOrName) => { const row = await getObjectByIdOrName(queries.StorageContainers,'StorageContainers',idOrName); return row ? formatStorageContainer(row) : null; };

function register(app){
  /**
   * @swagger
   * /storagecontainers:
   *  get:
   *    description: Get all storage containers
   *    responses:
   *      '200':
   *        description: A list of storage containers
   */
  app.get('/storagecontainers', async (req,res)=>{ res.json(await getStorageContainers()); });
  /**
   * @swagger
   * /storagecontainers/{storageContainer}:
   *  get:
   *    description: Get a storage container by name or id
   *    parameters:
   *      - in: path
   *        name: storageContainer
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the storage container
   *    responses:
   *      '200':
   *        description: The storage container
   *      '404':
   *        description: Storage container not found
   */
  app.get('/storagecontainers/:storageContainer', async (req,res)=>{ const r = await getStorageContainer(req.params.storageContainer); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getStorageContainers, getStorageContainer, formatStorageContainer };
