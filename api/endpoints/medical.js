const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = {
  MedicalChips: 'SELECT "MedicalChips".*, "Materials"."Name" AS "Ammo" FROM ONLY "MedicalChips" LEFT JOIN ONLY "Materials" ON "MedicalChips"."AmmoId" = "Materials"."Id"',
  MedicalTools: 'SELECT * FROM ONLY "MedicalTools"',
};

function formatMedicalChip(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MedicalChips,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      AttackInterval: x.AttackInterval !== null ? Number(x.AttackInterval) : null,
      UsesPerMinute: x.UsesPerMinute !== null ? Number(x.UsesPerMinute) : null,
      Skill: {
        LearningIntervalStart: x.MinLvl !== null ? Number(x.MinLvl) : null,
        LearningIntervalEnd: x.MaxLvl !== null ? Number(x.MaxLvl) : null,
        IsSiB: x.IsSib === 1,
      },
      HealMax: x.HealMax !== null ? Number(x.HealMax) : null,
      HealMin: x.HealMin !== null ? Number(x.HealMin) : null,
      TreatmentInterval: x.TreatmentInterval !== null ? Number(x.TreatmentInterval) : null,
    },
    Ammo: x.Ammo,
    Links: { "$Url": `/medicalchips/${x.Id}` },
  };
}

function formatMedicalTool(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MedicalTools,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Heal: x.Heal !== null ? Number(x.Heal) : null,
      HealSkillReq: x.HealSkillReq !== null ? Number(x.HealSkillReq) : null,
    },
    Links: { "$Url": `/medicaltools/${x.Id}` },
  };
}

// DB methods
const getMedicalChips = () => getObjects(queries.MedicalChips, formatMedicalChip);
const getMedicalChip = async (idOrName) => { const row = await getObjectByIdOrName(queries.MedicalChips, 'MedicalChips', idOrName); return row ? formatMedicalChip(row) : null; };
const getMedicalTools = () => getObjects(queries.MedicalTools, formatMedicalTool);
const getMedicalTool = async (idOrName) => { const row = await getObjectByIdOrName(queries.MedicalTools, 'MedicalTools', idOrName); return row ? formatMedicalTool(row) : null; };

function register(app){
  /**
   * @swagger
   * /medicalchips:
   *  get:
   *    description: Get all medical chips
   *    responses:
   *      '200':
   *        description: A list of medical chips
   */
  app.get('/medicalchips', async (req,res) => { res.json(await getMedicalChips()); });
  /**
   * @swagger
   * /medicalchips/{medicalChip}:
   *  get:
   *    description: Get a medical chip by name or id
   *    parameters:
   *      - in: path
   *        name: medicalChip
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the medical chip
   *    responses:
   *      '200':
   *        description: The medical chip
   *      '404':
   *        description: Medical chip not found
   */
  app.get('/medicalchips/:medicalChip', async (req,res) => { const r = await getMedicalChip(req.params.medicalChip); if (r) res.json(r); else res.status(404).send(); });

  /**
   * @swagger
   * /medicaltools:
   *  get:
   *    description: Get all medical tools
   *    responses:
   *      '200':
   *        description: A list of medical tools
   */
  app.get('/medicaltools', async (req,res) => { res.json(await getMedicalTools()); });
  /**
   * @swagger
   * /medicaltools/{medicalTool}:
   *  get:
   *    description: Get a medical tool by name or id
   *    parameters:
   *      - in: path
   *        name: medicalTool
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the medical tool
   *    responses:
   *      '200':
   *        description: The medical tool
   *      '404':
   *        description: Medical tool not found
   */
  app.get('/medicaltools/:medicalTool', async (req,res) => { const r = await getMedicalTool(req.params.medicalTool); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMedicalChips, getMedicalChip, getMedicalTools, getMedicalTool };
