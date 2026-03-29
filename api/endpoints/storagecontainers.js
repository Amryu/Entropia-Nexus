const { pool } = require('./dbClient');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { idOffsets } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { StorageContainers: 'SELECT "StorageContainers".*, "Planets"."Name" AS "Planet" FROM ONLY "StorageContainers" LEFT JOIN ONLY "Planets" ON "StorageContainers"."PlanetId" = "Planets"."Id"' };

function formatStorageContainer(x, data){
  const itemId = x.Id + idOffsets.StorageContainers;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: itemId,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      ItemCapacity: x.Capacity != null ? Number(x.Capacity) : null,
      WeightCapacity: x.MaxWeight != null ? Number(x.MaxWeight) : null,
      Economy: { MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    Planet: { Name: x.Planet, Links: { "$Url": `/planets/${x.PlanetId}` } },
    Links: { "$Url": `/storagecontainers/${x.Id}` },
  };
}

async function getStorageContainers() {
  const { rows } = await pool.query(queries.StorageContainers);
  const itemIds = rows.map(r => r.Id + idOffsets.StorageContainers);
  const [classIds, itemProps] = await Promise.all([
    loadClassIds('StorageContainer', rows.map(r => r.Id)),
    loadItemProperties(itemIds)
  ]);
  const data = { ClassIds: classIds, ItemProps: itemProps };
  return rows.map(r => formatStorageContainer(r, data));
}
const getStorageContainer = async(idOrName) => { const row = await getObjectByIdOrName(queries.StorageContainers,'StorageContainers',idOrName); if (!row) return null; const itemId = row.Id + idOffsets.StorageContainers; const [classIds, itemProps] = await Promise.all([loadClassIds('StorageContainer', [row.Id]), loadItemProperties([itemId])]); const data = { ClassIds: classIds, ItemProps: itemProps }; return formatStorageContainer(row, data); };

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
  app.get('/storagecontainers', async (req,res)=>{ res.json(await withCache('/storagecontainers', ['StorageContainers', 'ClassIds', 'ItemProperties'], getStorageContainers)); });
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
  app.get('/storagecontainers/:storageContainer', async (req,res)=>{ const r = await withCachedLookup('/storagecontainers', ['StorageContainers', 'ClassIds', 'ItemProperties'], getStorageContainers, req.params.storageContainer); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getStorageContainers, getStorageContainer, formatStorageContainer };
