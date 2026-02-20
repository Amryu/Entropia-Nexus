const pgp = require("pg-promise")();
const { getObjectByIdOrName, parseItemList } = require("./utils");
const { pool } = require("./dbClient");
const { ITEM_TABLES } = require('./constants');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  VendorOffers:
    'SELECT "VendorOffers".*, "Items"."Name" AS "Item", "Items"."Value" AS "ItemValue", "Items"."Type" AS "ItemType", l."Name" AS "Vendor", l."PlanetId" AS "PlanetId", "Planets"."Name" AS "Planet" FROM ONLY "VendorOffers" LEFT JOIN ONLY "Items" ON "VendorOffers"."ItemId" = "Items"."Id" LEFT JOIN ONLY "Locations" l ON "VendorOffers"."LocationId" = l."Id" LEFT JOIN ONLY "Planets" ON l."PlanetId" = "Planets"."Id"',
};

function _formatVendorOfferPrice(x) {
  return {
    Amount: x.Amount !== null ? Number(x.Amount) : null,
    Item: {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
        Economy: { Value: x.Value !== null ? Number(x.Value) : null },
      },
      Links: { $Url: `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}` },
    },
  };
}

async function formatVendorOffer(x, data) {
  const prices = (data[x.Id] ?? []).map(_formatVendorOfferPrice);
  
  return {
    Id: x.Id,
    IsLimited: x.IsLimited,
    Value: x.Value !== null ? Number(x.Value) : x.ItemValue !== null ? Number(x.ItemValue) : null,
    Item: {
      Name: x.Item,
      Properties: {
        Type: x.ItemType,
        Economy: {
          Value: x.ItemValue !== null ? Number(x.ItemValue) : null,
        },
      },
      Links: { $Url: `/${x.ItemType.toLowerCase()}s/${x.ItemId % 100000}` },
    },
    Vendor: {
      Name: x.Vendor,
      Planet: { Name: x.Planet, Links: { $Url: `/planets/${x.PlanetId}` } },
      Links: { $Url: `/vendors/${x.LocationId}` },
    },
    Prices: prices,
    Links: { $Url: `/vendoroffers/${x.Id}` },
  };
}

async function getVendorOffers(items, prices = null) {
  let where = "";
  if (items !== null)
    where += pgp.as.format(' WHERE "Items"."Name" IN ($1:csv)', [
      items.map((x) => `${x}`),
    ]);
  const { rows } = await pool.query(queries.VendorOffers + where);
  const pricesMap = await (async () => {
    const ids = rows.map((r) => r.Id);
    if (ids.length === 0) return {};
    const { rows: p } = await pool.query(
      `SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" FROM ONLY "VendorOfferPrices" INNER JOIN ONLY "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" IN (${ids.join(",")})`
    );
    return p.reduce((a, r) => {
      (a[r.OfferId] ||= []).push(r);
      return a;
    }, {});
  })();
  let objs = await Promise.all(
    rows.map((r) => formatVendorOffer(r, pricesMap))
  );
  if (prices !== null)
    objs = objs.filter((x) =>
      (x.Prices ?? []).some((y) => prices.includes(y.Item.Name))
    );
  return objs;
}

async function getVendorOffer(idOrName) {
  const row = await getObjectByIdOrName(
    queries.VendorOffers,
    "VendorOffers",
    idOrName
  );
  if (!row) return null;
  const pricesMap = await (async () => {
    const { rows: p } = await pool.query(
      `SELECT "VendorOfferPrices".*, "Items"."Name" AS "Item", "Items"."Type" AS "ItemType", "Items"."Value" FROM ONLY "VendorOfferPrices" INNER JOIN ONLY "Items" ON "VendorOfferPrices"."ItemId" = "Items"."Id" WHERE "OfferId" = ${row.Id}`
    );
    return { [row.Id]: p };
  })();
  return formatVendorOffer(row, pricesMap);
}

function register(app) {
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
  app.get("/vendoroffers", async (req, res, next) => {
    try {
      let items = null;
      if (req.query.Item && req.query.Items)
        return res.status(400).send("Cannot specify both Item and Items");
      if (req.query.Item || req.query.Items) {
        items = req.query.Items
          ? parseItemList(req.query.Items)
          : [req.query.Item];
        if (items.length === 0)
          return res.status(400).send("Items cannot be empty");
      }
      if (items) {
        res.json(await getVendorOffers(items));
      } else {
        res.json(await withCache('/vendoroffers', ['VendorOffers', 'VendorOfferPrices', ...ITEM_TABLES, 'Locations', 'Planets'], getVendorOffers));
      }
    } catch (e) {
      next(e);
    }
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
  app.get("/vendoroffers/:vendorOffer", async (req, res) => {
    const r = await withCachedLookup('/vendoroffers', ['VendorOffers', 'VendorOfferPrices', ...ITEM_TABLES, 'Locations', 'Planets'], getVendorOffers, req.params.vendorOffer);
    if (r) res.json(r);
    else res.status(404).send();
  });
}

module.exports = { register, getVendorOffers, getVendorOffer };
