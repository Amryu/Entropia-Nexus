const pgp = require('pg-promise')();
const { getObjects } = require('./utils');
const { pool } = require('./dbClient');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Vendors: 'SELECT l.*, "Planets"."Name" AS "Planet", "Planets"."TechnicalName" AS "PlanetTechnicalName" FROM ONLY "Locations" l LEFT JOIN ONLY "Planets" ON l."PlanetId" = "Planets"."Id" WHERE l."Type" = \'Vendor\'',
};

function _formatVendorOfferPrice(x){
  return {
    Amount: x.Amount !== null ? Number(x.Amount) : null,
    Item: {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
        Economy: {
          Value: x.Value !== null ? Number(x.Value) : null,
        },
      },
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    }
  };
}

function _formatVendorOffer(x){
  return {
    IsLimited: x.IsLimited,
    Item: {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
        Economy: {
          Value: x.Value !== null ? Number(x.Value) : null,
        },
      },
      Links: {
        "$Url": `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}`
      }
    },
    Prices: x.Prices ?? []
  };
}

function formatVendor(x, data){
  let offers = data.Offers[x.Id] ?? [];
  // format nested prices then offers to match db.js / FE schema
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
  const { rows: offers } = await pool.query(`SELECT "VendorOffers".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" AS "Value" FROM ONLY "VendorOffers" INNER JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" WHERE "LocationId" IN (${ids.join(',')})`);
  const offerIds = offers.map(x => x.Id);
  if (offerIds.length === 0) return { Offers: {}, Prices: {} };
  const { rows: prices } = await pool.query(`SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" AS "Value" FROM ONLY "VendorOfferPrices" INNER JOIN ONLY "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" IN (${offerIds.join(',')})`);
  return { Offers: offers.reduce((a,r)=>{ (a[r.LocationId] ||= []).push(r); return a; }, {}), Prices: prices.reduce((a,r)=>{ (a[r.OfferId] ||= []).push(r); return a; }, {}) };
}

// DB methods
async function getVendors(offerItems = null){
  let extra = '';
  if (offerItems !== null){
    extra = pgp.as.format(' AND l."Id" IN (SELECT DISTINCT "LocationId" FROM ONLY "VendorOffers" INNER JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" WHERE "Items"."Name" IN ($1:csv))', [offerItems.map(x => `${x}`)]);
  }
  const rows = await getObjects(queries.Vendors + extra, x=>x);
  const data = await _getVendorOffers(rows.map(r=>r.Id));
  return rows.map(r => formatVendor(r, data));
}

async function getVendor(idOrName){
  const isById = /^(\d+)$/.test(String(idOrName));
  const sql = queries.Vendors + (isById ? ' AND l."Id" = $1' : ' AND l."Name" = $1');
  const { rows } = await pool.query(sql, [idOrName]);
  if (rows.length !== 1) return null;
  const row = rows[0];
  const data = await _getVendorOffers([row.Id]);
  return formatVendor(row, data);
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
  app.get('/vendors', async (req,res) => { res.json(await withCache('/vendors', ['Locations', 'Planets', 'VendorOffers', 'VendorOfferPrices', 'Items'], getVendors)); });
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
  app.get('/vendors/:vendor', async (req,res) => { const r = await withCachedLookup('/vendors', ['Locations', 'Planets', 'VendorOffers', 'VendorOfferPrices', 'Items'], getVendors, req.params.vendor); if (r) res.json(r); else res.status(404).send(); });
}

module.exports = { register, getVendors, getVendor, formatVendor };
