const { getObjects, getObjectByIdOrName } = require('./utils');

const queries = { Items: 'SELECT * FROM ONLY "Items"' };

function formatItem(x){
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: { Type: x.Type, Weight: x.Weight !== null ? Number(x.Weight) : null, Economy: { Value: x.Value !== null ? Number(x.Value) : null } },
    Links: { "$Url": `/${x.Type.toLowerCase()}s/${x.Id % 100000}` }
  };
}

async function _getObjects(query, formatFn){ return getObjects(query, formatFn); }
async function _getObject(idOrName, query){ const row = await getObjectByIdOrName(query, 'Items', idOrName); return row ? formatItem(row) : null; }

const getItems = () => _getObjects(queries.Items, formatItem);
const getItem = (idOrName) => _getObject(idOrName, queries.Items);

function register(app){
  /**
   * @swagger
   * /items:
   *  get:
   *    description: Get all items
   *    responses:
   *      '200':
   *        description: A list of items
   */
  app.get('/items', async (req,res) => { res.json(await getItems()); });
  app.get('/items/:item', async (req,res) => {
    /**
     * @swagger
     * /items/{item}:
     *  get:
     *    description: Get an item by name or id
     *    parameters:
     *      - in: path
     *        name: item
     *        schema:
     *          type: string
     *        required: true
     *        description: The name or id of the item
     *    responses:
     *      '200':
     *        description: The item
     *      '404':
     *        description: Item not found
     */
    const it = await getItem(req.params.item);
    if (it) res.json(it); else res.status(404).send('Item not found');
  });
}

module.exports = { register, getItems, getItem };
