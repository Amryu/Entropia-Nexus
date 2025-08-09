const { getObjects, getObjectByIdOrName } = require('./utils');
const { idOffsets } = require('./constants');

const queries = { MiscTools: 'SELECT "MiscTools".*, "Professions"."Name" AS "Profession" FROM ONLY "MiscTools" LEFT JOIN ONLY "Professions" ON "MiscTools"."ProfessionId" = "Professions"."Id"' };

function formatMiscTool(x){
  return {
    Id: x.Id,
    ItemId: x.Id + idOffsets.MiscTools,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Weight: x.Weight != null ? Number(x.Weight) : null,
      UsesPerMinute: x.Uses != null ? Number(x.Uses) : null,
      Efficiency: x.Efficiency != null ? Number(x.Efficiency) : null,
      Economy: {
        MaxTT: x.MaxTT != null ? Number(x.MaxTT) : null,
        MinTT: x.MinTT != null ? Number(x.MinTT) : null,
        Decay: x.Decay != null ? Number(x.Decay) : null,
      },
      LearningInterval: {
        Start: x.IntervalStart != null ? Number(x.IntervalStart) : null,
        End: x.IntervalEnd != null ? Number(x.IntervalEnd) : null,
        IsSiB: x.IntervalStart != null && x.IntervalEnd != null,
      },
    },
    Profession: { Name: x.Profession, Links: { "$Url": x.ProfessionId ? `/professions/${x.ProfessionId}` : null } },
    Links: { "$Url": `/misctools/${x.Id}` },
  };
}

const getMiscTools = () => getObjects(queries.MiscTools, formatMiscTool);
const getMiscTool = async(idOrName) => { const row = await getObjectByIdOrName(queries.MiscTools,'MiscTools',idOrName); return row ? formatMiscTool(row) : null; };

function register(app){
  /**
   * @swagger
   * /misctools:
   *  get:
   *    description: Get all misc. tools
   *    responses:
   *      '200':
   *        description: A list of misc. tools
   */
  app.get('/misctools', async (req,res)=>{ res.json(await getMiscTools()); });
  /**
   * @swagger
   * /misctools/{miscTool}:
   *  get:
   *    description: Get a misc. tool by name or id
   *    parameters:
   *      - in: path
   *        name: miscTool
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the misc. tool
   *    responses:
   *      '200':
   *        description: The misc. tool
   *      '404':
   *        description: Misc. tool not found
   */
  app.get('/misctools/:miscTool', async (req,res)=>{ const r = await getMiscTool(req.params.miscTool); if(r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getMiscTools, getMiscTool };
