const { pool } = require('./dbClient');
const { idOffsets } = require('./constants');
const { getObjectByIdOrName, loadClassIds, loadItemProperties } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = { Vehicles: 'SELECT "Vehicles".*, "Materials"."Name" AS "Fuel" FROM ONLY "Vehicles" LEFT JOIN ONLY "Materials" ON "Vehicles"."FuelMaterialId" = "Materials"."Id"' };

function groupBy(arr,key){ return arr.reduce((a,r)=>{ (a[r[key]] ||= []).push(r); return a; },{}); }

async function getAttachmentSlots(ids){ if(ids.length===0) return {}; const { rows } = await pool.query(`SELECT "VehicleAttachmentSlots".*, "VehicleAttachmentTypes"."Name" AS "Type" FROM ONLY "VehicleAttachmentSlots" INNER JOIN ONLY "VehicleAttachmentTypes" ON "VehicleAttachmentTypes"."Id" = "VehicleAttachmentSlots"."AttachmentId" WHERE "VehicleId" = ANY($1::int[])`, [ids]); return groupBy(rows,'VehicleId'); }

function formatAttachmentSlot(x){ return { Name: x.Type, Links: { "$Url": `/vehicleattachmenttypes/${x.AttachmentId}` } }; }

function formatVehicle(x,data){
  const slots = (data.Slots[x.Id]||[]).map(formatAttachmentSlot);
  const itemId = x.Id + idOffsets.Vehicles;
  const props = data.ItemProps[itemId];
  return {
    Id: x.Id,
    ClassId: data.ClassIds[x.Id] || null,
    ItemId: x.Id + idOffsets.Vehicles,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      Type: x.Type != null ? x.Type : null,
      SpawnedWeight: x.SpawnedWeight != null ? Number(x.SpawnedWeight) : null,
      PassengerCount: x.Passengers != null ? Number(x.Passengers) : null,
      ItemCapacity: x.StorageCount != null ? Number(x.StorageCount) : null,
      WeightCapacity: x.StorageWeight != null ? Number(x.StorageWeight) : null,
      WheelGrip: x.WheelGrip != null ? Number(x.WheelGrip) : null,
      EnginePower: x.EnginePower != null ? Number(x.EnginePower) : null,
      MaxSpeed: x.MaxSpeed != null ? Number(x.MaxSpeed) : null,
      MaxStructuralIntegrity: x.MaxSI != null ? Number(x.MaxSI) : null,
      Economy: {
        MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT != null ? Number(x.MinTT) : null,
        Durability: x.Durability != null ? Number(x.Durability) : null,
        FuelConsumptionActive: x.FuelActive != null ? Number(x.FuelActive) : null,
        FuelConsumptionPassive: x.FuelPassive != null ? Number(x.FuelPassive) : null,
        Decay: x.Decay != null ? Number(x.Decay) : null,
      },
      Defense: {
        Stab: x.Stab != null ? Number(x.Stab) : null,
        Cut: x.Cut != null ? Number(x.Cut) : null,
        Impact: x.Impact != null ? Number(x.Impact) : null,
        Penetration: x.Penetration != null ? Number(x.Penetration) : null,
        Shrapnel: x.Shrapnel != null ? Number(x.Shrapnel) : null,
        Burn: x.Burn != null ? Number(x.Burn) : null,
        Cold: x.Cold != null ? Number(x.Cold) : null,
        Acid: x.Acid != null ? Number(x.Acid) : null,
        Electric: x.Electric != null ? Number(x.Electric) : null,
      },
      IsUntradeable: props?.IsUntradeable || false,
      IsRare: props?.IsRare || false,
    },
    AttachmentSlots: slots,
    Fuel: { Name: x.Fuel, Links: { "$Url": `/materials/${x.FuelMaterialId}` } },
    Links: { "$Url": `/vehicles/${x.Id}` },
  };
}

async function getVehicles(){ const { rows } = await pool.query(queries.Vehicles); const itemIds = rows.map(r => r.Id + idOffsets.Vehicles); const [slots, classIds, itemProps] = await Promise.all([getAttachmentSlots(rows.map(r=>r.Id)), loadClassIds('Vehicle', rows.map(r=>r.Id)), loadItemProperties(itemIds)]); const data = { Slots: slots, ClassIds: classIds, ItemProps: itemProps }; return rows.map(r=>formatVehicle(r,data)); }
async function getVehicle(idOrName){ const row = await getObjectByIdOrName(queries.Vehicles,'Vehicles',idOrName); if(!row) return null; const itemId = row.Id + idOffsets.Vehicles; const [slots, classIds, itemProps] = await Promise.all([getAttachmentSlots([row.Id]), loadClassIds('Vehicle', [row.Id]), loadItemProperties([itemId])]); const data = { Slots: slots, ClassIds: classIds, ItemProps: itemProps }; return formatVehicle(row,data); }

function register(app){
  /**
   * @swagger
   * /vehicles:
   *  get:
   *    description: Get all vehicles
   *    responses:
   *      '200':
   *        description: A list of vehicles
   */
  app.get('/vehicles', async (req,res)=>{ res.json(await withCache('/vehicles', ['Vehicles', 'ClassIds', 'ItemProperties'], getVehicles)); });
  /**
   * @swagger
   * /vehicles/{vehicle}:
   *  get:
   *    description: Get a vehicle by name or id
   *    parameters:
   *      - in: path
   *        name: vehicle
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the vehicle
   *    responses:
   *      '200':
   *        description: The vehicle
   *      '404':
   *        description: Vehicle not found
   */
  app.get('/vehicles/:vehicle', async (req,res)=>{ const r = await withCachedLookup('/vehicles', ['Vehicles', 'ClassIds', 'ItemProperties'], getVehicles, req.params.vehicle); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getVehicles, getVehicle, formatVehicle };
