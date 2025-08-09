const pgp = require('pg-promise')();
const { getObjects, getObjectByIdOrName, parseItemList } = require('./utils');
const { pool } = require('./dbClient');

const queries = {
  Vendors: 'SELECT "Vendors".*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" AS "PlanetTechnicalName" FROM ONLY "Vendors" LEFT JOIN ONLY "Planets" ON "Vendors"."PlanetId" = "Planets"."Id"',
  VendorOffers: 'SELECT "VendorOffers".*, "Items"."Name" AS "Item", "Items"."Value" AS "ItemValue", "Items"."Type" AS "ItemType", "Vendors"."Name" AS "Vendor", "Vendors"."PlanetId" AS "PlanetId", "Planets"."Name" AS "Planet" FROM ONLY "VendorOffers" LEFT JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" LEFT JOIN ONLY "Vendors" ON "VendorOffers"."VendorId" = "Vendors"."Id" LEFT JOIN ONLY "Planets" ON "Vendors"."PlanetId" = "Planets"."Id"',
};

function _formatVendorOfferPrice(x){
  return { Amount: x.Amount !== null ? Number(x.Amount) : null, Item: { Name: x.Item, Properties: { Type: x.ItemType, Economy: { Value: x.Value !== null ? Number(x.Value) : null } }, Links: { "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}` } } };
}

function _formatVendorOffer(x){
  return { IsLimited: x.IsLimited, Item: { Name: x.Item, Properties: { Type: x.ItemType, Economy: { Value: x.Value !== null ? Number(x.Value) : null } }, Links: { "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}` } }, Prices: x.Prices ?? [] };
}

function formatVendor(x, data){
  let offers = data.Offers[x.Id] ?? [];
  offers.forEach(offer => offer.Prices = (data.Prices[offer.Id] ?? []).map(_formatVendorOfferPrice));
  offers = offers.map(_formatVendorOffer);
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      Coordinates: { Longitude: x.Longitude !== null ? Number(x.Longitude) : null, Latitude: x.Latitude !== null ? Number(x.Latitude) : null, Altitude: x.Altitude !== null ? Number(x.Altitude) : null }
    },
    Planet: { Name: x.Planet, Properties: { TechnicalName: x.PlanetTechnicalName }, Links: { "$Url": `/planets/${x.PlanetId}` } },
    Offers: offers,
    Links: { "$Url": `/vendors/${x.Id}` }
  };
}

async function _getVendorOffers(ids){
  if (ids.length === 0) return { Offers: {}, Prices: {} };
  const { rows: offers } = await pool.query(`SELECT "VendorOffers".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" AS "Value" FROM ONLY "VendorOffers" INNER JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" WHERE "VendorId" IN (${ids.join(',')})`);
  const offerIds = offers.map(x => x.Id);
  if (offerIds.length === 0) return { Offers: {}, Prices: {} };
  const { rows: prices } = await pool.query(`SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" AS "Value" FROM ONLY "VendorOfferPrices" INNER JOIN ONLY "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" IN (${offerIds.join(',')})`);
  return { Offers: offers.reduce((a,r)=>{ (a[r.VendorId] ||= []).push(r); return a; }, {}), Prices: prices.reduce((a,r)=>{ (a[r.OfferId] ||= []).push(r); return a; }, {}) };
}

async function formatVendorOffer(x, data){
  const prices = (data[x.Id] ?? []).map(_formatVendorOfferPrice);
  const val = (x.ItemValue !== undefined ? x.ItemValue : x.Value);
  return {
    Id: x.Id,
    IsLimited: x.IsLimited,
    Item: { Name: x.Item, Properties: { Type: x.ItemType, Economy: { Value: val !== null && val !== undefined ? Number(val) : null } }, Links: { "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}` } },
    Vendor: { Name: x.Vendor, Planet: { Name: x.Planet, Links: { "$Url": `/planets/${x.PlanetId}` } }, Links: { "$Url": `/vendors/${x.VendorId}` } },
    Prices: prices,
    Links: { "$Url": `/vendoroffers/${x.Id}` }
  };
}

// DB methods
async function getVendors(offerItems = null){
  let where = '';
  if (offerItems !== null){
    where = pgp.as.format(' WHERE "Vendors"."Id" IN (SELECT DISTINCT "VendorId" FROM ONLY "VendorOffers" INNER JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" WHERE "Items"."Name" IN ($1:csv))', [offerItems.map(x => `${x}`)]);
  }
  const rows = await getObjects(queries.Vendors + where, x=>x);
  const data = await _getVendorOffers(rows.map(r=>r.Id));
  return rows.map(r => formatVendor(r, data));
}

async function getVendor(idOrName){
  const row = await getObjectByIdOrName(queries.Vendors, 'Vendors', idOrName);
  if (!row) return null;
  const data = await _getVendorOffers([row.Id]);
  return formatVendor(row, data);
}

async function getVendorOffers(items, prices = null){
  let where = '';
  if (items !== null) where += pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [items.map(x => `${x}`)]);
  const { rows } = await pool.query(queries.VendorOffers + where);
  const pricesMap = await (async () => {
    const ids = rows.map(r=>r.Id);
    if (ids.length === 0) return {};
    const { rows: p } = await pool.query(`SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" FROM ONLY "VendorOfferPrices" INNER JOIN ONLY "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" IN (${ids.join(',')})`);
    return p.reduce((a,r)=>{ (a[r.OfferId] ||= []).push(r); return a; },{});
  })();
  let objs = await Promise.all(rows.map(r => formatVendorOffer(r, pricesMap)));
  if (prices !== null) objs = objs.filter(x => (x.Prices ?? []).some(y => prices.includes(y.Item.Name)));
  return objs;
}

async function getVendorOffer(idOrName){
  const row = await getObjectByIdOrName(queries.VendorOffers, 'VendorOffers', idOrName);
  if (!row) return null;
  const pricesMap = await (async () => {
    const { rows: p } = await pool.query(`SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" FROM ONLY "VendorOfferPrices" INNER JOIN ONLY "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" = ${row.Id}`);
    return { [row.Id]: p };
  })();
  return formatVendorOffer(row, pricesMap);
}

// Endpoints
function register(app){
  /**
   * @swagger
   * /vendors:
   *  get:
   *    description: Get all vendors
   *    responses:
   *      '200':
   *        description: A list of vendors
   */
  app.get('/vendors', async (req,res) => { res.json(await getVendors()); });
  /**
   * @swagger
   * /vendors/{vendor}:
   *  get:
   *    description: Get a vendor by name or id
   *    parameters:
   *      - in: path
   *        name: vendor
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the vendor
   *    responses:
   *      '200':
   *        description: The vendor
   *      '404':
   *        description: Vendor not found
   */
  app.get('/vendors/:vendor', async (req,res) => { const r = await getVendor(req.params.vendor); if (r) res.json(r); else res.status(404).send(); });

  /**
   * @swagger
   * /vendoroffers:
   *  get:
   *    description: Get all vendor offers
   *    parameters:
   *      - in: query
   *        name: Item
   *        schema:
   *          type: string
   *        description: The item to filter vendor offers by
   *      - in: query
   *        name: Items
   *        schema:
   *          type: string
   *        description: A comma-separated list of items to filter vendor offers by
   *    responses:
   *      '200':
   *        description: A list of vendor offers
   *      '400':
   *        description: Cannot specify both Item and Items
   */
  app.get('/vendoroffers', async (req,res,next) => {
    try {
      let items = null;
      if (req.query.Item && req.query.Items) return res.status(400).send('Cannot specify both Item and Items');
      if (req.query.Item || req.query.Items){
        items = req.query.Items ? parseItemList(req.query.Items) : [req.query.Item];
        if (items.length === 0) return res.status(400).send('Items cannot be empty');
      }
      res.json(await getVendorOffers(items));
    } catch (e){ next(e); }
  });

  /**
   * @swagger
   * /vendoroffers/{vendorOffer}:
   *  get:
   *    description: Get a vendor offer by name or id
   *    parameters:
   *      - in: path
   *        name: vendorOffer
   *        schema:
   *          type: string
   *        required: true
   *        description: The name or id of the vendor offer
   *    responses:
   *      '200':
   *        description: The vendor offer
   *      '404':
   *        description: Vendor offer not found
   */
  app.get('/vendoroffers/:vendorOffer', async (req,res) => { const r = await getVendorOffer(req.params.vendorOffer); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getVendors, getVendor, getVendorOffers, getVendorOffer };
