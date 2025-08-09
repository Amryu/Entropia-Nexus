const { getObjects, getObjectByIdOrName } = require('./utils');

const queries = { VehicleAttachmentTypes: 'SELECT * FROM ONLY "VehicleAttachmentTypes"' };

function formatVehicleAttachmentType(x){ return { Id: x.Id, Name: x.Name, Links: { "$Url": `/vehicleattachmenttypes/${x.Id}` } }; }

const getVehicleAttachmentTypes = () => getObjects(queries.VehicleAttachmentTypes, formatVehicleAttachmentType);
const getVehicleAttachmentType = async(idOrName) => { const row = await getObjectByIdOrName(queries.VehicleAttachmentTypes,'VehicleAttachmentTypes',idOrName); return row ? formatVehicleAttachmentType(row) : null; };

function register(app){
  /**
   * @swagger
   * /vehicleattachmenttypes:
   *  get:
   *    description: Get all vehicle attachment types
   *    responses:
   *      '200':
   *        description: A list of vehicle attachment types
   */
  app.get('/vehicleattachmenttypes', async (req,res)=>{ res.json(await getVehicleAttachmentTypes()); });
  /**
   * @swagger
   * /vehicleattachmenttypes/{vehicleAttachmentType}:
   *  get:
   *    description: Get a vehicle attachment type by name or id
   *    parameters:
   *      - in: path
   *        name: vehicleAttachmentType
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the vehicle attachment type
   *    responses:
   *      '200':
   *        description: The vehicle attachment type
   *      '404':
   *        description: Vehicle attachment type not found
   */
  app.get('/vehicleattachmenttypes/:vehicleAttachmentType', async (req,res)=>{ const r = await getVehicleAttachmentType(req.params.vehicleAttachmentType); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getVehicleAttachmentTypes, getVehicleAttachmentType };
