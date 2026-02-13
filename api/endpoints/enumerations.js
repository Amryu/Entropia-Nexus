const { pool } = require('./dbClient');

const BUILTIN_ENUMERATIONS = [
  { name: 'MobSpecies', description: 'Mob species definitions.' },
  { name: 'MobLoots', description: 'Mob loot relations flattened by mob and item.' },
  { name: 'RefiningRecipes', description: 'Refining recipes flattened by ingredient.' },
  { name: 'Tiers', description: 'Tier requirements flattened by material.' },
  { name: 'BlueprintDrops', description: 'Blueprint drop relations.' },
  { name: 'Effects', description: 'Effect definitions.' },
  { name: 'EffectsOnEquip', description: 'Effects that apply while equipped.' },
  { name: 'EffectsOnSetEquip', description: 'Set effects by minimum set pieces.' },
  { name: 'EffectsOnUse', description: 'Effects that apply on use.' },
  { name: 'Events', description: 'Mission-related events.' },
  { name: 'LandAreaMinerals', description: 'Minerals found in land areas.' },
  { name: 'EffectsOnConsume', description: 'Consumable effects.' },
  { name: 'Planets', description: 'Planet definitions and map metadata.' },
  { name: 'VehicleAttachmentTypes', description: 'Vehicle attachment type definitions.' },
];

const BUILTIN_LOOKUP = new Map(BUILTIN_ENUMERATIONS.map((x) => [x.name.toLowerCase(), x]));

function toNumberOrNull(v) {
  return v === null || v === undefined ? null : Number(v);
}

function toBool(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === 'boolean') return v;
  return Number(v) === 1;
}

function toIsoOrNull(v) {
  if (!v) return null;
  if (v instanceof Date) return v.toISOString();
  return String(v);
}

function detailLink(name) {
  return `/enumerations/${encodeURIComponent(name)}`;
}

function formatListItem({
  id = null,
  name,
  source,
  description = null,
  unit = null,
  metadata = null
}) {
  return {
    Id: id,
    Name: name,
    Properties: {
      Source: source,
      Description: description,
      Unit: unit,
      Metadata: metadata
    },
    Links: { "$Url": detailLink(name) }
  };
}

function formatDetail({
  id = null,
  name,
  source,
  description = null,
  unit = null,
  metadata = null,
  columns,
  rows
}) {
  return {
    Id: id,
    Name: name,
    Properties: {
      Source: source,
      Description: description,
      Unit: unit,
      Metadata: metadata
    },
    Table: {
      Columns: columns,
      Rows: rows
    },
    Links: { "$Url": detailLink(name) }
  };
}

function withRefs(row, refs = null) {
  if (!refs) return row;
  const filtered = Object.fromEntries(
    Object.entries(refs).filter(([, ref]) => !!ref && !!ref.name)
  );
  if (Object.keys(filtered).length === 0) return row;
  return { ...row, __refs: filtered };
}

function getMetadataColumns(metadata) {
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) return [];
  if (!Array.isArray(metadata.columns)) return [];
  return metadata.columns
    .map((x) => String(x || '').trim())
    .filter((x) => !!x && x !== 'Name' && x !== 'Value');
}

function buildCustomDetailTable(metadata, values) {
  const metadataColumns = getMetadataColumns(metadata);
  const fallbackKeys = new Set();

  for (const row of values) {
    const data = row.Data;
    if (!data || typeof data !== 'object' || Array.isArray(data)) continue;
    for (const key of Object.keys(data)) {
      const normalized = String(key || '').trim();
      if (!normalized || normalized === 'Name' || normalized === 'Value') continue;
      fallbackKeys.add(normalized);
    }
  }

  const extraKeys = metadataColumns.length > 0
    ? metadataColumns
    : Array.from(fallbackKeys).sort((a, b) => a.localeCompare(b));

  const columns = [
    { key: 'Name', label: 'Name' },
    { key: 'Value', label: 'Value' },
    ...extraKeys.map((key) => ({ key, label: key })),
  ];

  const rows = values.map((row) => {
    const out = { Name: row.Name, Value: row.Value };
    const data = row.Data && typeof row.Data === 'object' && !Array.isArray(row.Data)
      ? row.Data
      : null;
    for (const key of extraKeys) {
      out[key] = data && Object.prototype.hasOwnProperty.call(data, key) ? data[key] : null;
    }
    return out;
  });

  return { columns, rows };
}

async function safeRows(sql, params = []) {
  try {
    const { rows } = await pool.query(sql, params);
    return rows;
  } catch (err) {
    // Optional table in some environments/migration states.
    if (err && err.code === '42P01') return [];
    throw err;
  }
}

async function getCustomEnumerations() {
  try {
    const { rows } = await pool.query(
      `SELECT "Id", "Name", "Description", "Unit", "Metadata"
       FROM ONLY "Enumerations"
       ORDER BY "Name"`
    );
    return rows;
  } catch (err) {
    if (err && err.code === '42P01') return [];
    throw err;
  }
}

async function getCustomEnumerationByName(name) {
  try {
    const { rows } = await pool.query(
      `SELECT "Id", "Name", "Description", "Unit", "Metadata"
       FROM ONLY "Enumerations"
       WHERE LOWER("Name") = LOWER($1)`,
      [name]
    );
    return rows[0] || null;
  } catch (err) {
    if (err && err.code === '42P01') return null;
    throw err;
  }
}

async function getCustomEnumerationValues(enumerationId) {
  try {
    const { rows } = await pool.query(
      `SELECT "Name", "Value", "Data"
       FROM ONLY "EnumerationValues"
       WHERE "EnumerationId" = $1
       ORDER BY "Name"`,
      [enumerationId]
    );
    return rows;
  } catch (err) {
    if (err && err.code === '42P01') return [];
    throw err;
  }
}

async function loadMobSpecies() {
  const rows = await safeRows(
    `SELECT "Name", "CodexBaseCost", "CodexType", "IsCat4Codex", "Description"
     FROM ONLY "MobSpecies"
     ORDER BY "Name"`
  );
  return {
    columns: [
      { key: 'Name', label: 'Name' },
      { key: 'CodexBaseCost', label: 'Codex Base Cost' },
      { key: 'CodexType', label: 'Codex Type' },
      { key: 'IsCat4Codex', label: 'Is Cat4 Codex' },
      { key: 'Description', label: 'Description' },
    ],
    rows: rows.map((r) => ({
      Name: r.Name,
      CodexBaseCost: toNumberOrNull(r.CodexBaseCost),
      CodexType: r.CodexType || null,
      IsCat4Codex: toBool(r.IsCat4Codex),
      Description: r.Description || null,
    }))
  };
}

async function loadMobLoots() {
  const rows = await safeRows(
    `SELECT ml."Frequency", ml."LastVU", ml."IsEvent", ml."IsDropping",
            m."Id" AS "MobId", m."Name" AS "MobName",
            mm."Name" AS "MaturityName",
            i."Id" AS "ItemId", i."Name" AS "ItemName", i."Type" AS "ItemType"
     FROM ONLY "MobLoots" ml
     INNER JOIN ONLY "Mobs" m ON ml."MobId" = m."Id"
     LEFT JOIN ONLY "MobMaturities" mm ON ml."MaturityId" = mm."Id"
     INNER JOIN ONLY "Items" i ON ml."ItemId" = i."Id"
     ORDER BY m."Name", mm."Name" NULLS FIRST, i."Name"`
  );
  return {
    columns: [
      { key: 'Mob', label: 'Mob' },
      { key: 'Maturity', label: 'Maturity' },
      { key: 'Item', label: 'Item' },
      { key: 'ItemType', label: 'Item Type' },
      { key: 'Frequency', label: 'Frequency' },
      { key: 'LastVU', label: 'Last VU' },
      { key: 'IsEvent', label: 'Is Event' },
      { key: 'IsDropping', label: 'Is Dropping' },
    ],
    rows: rows.map((r) => withRefs(
      {
        Mob: r.MobName,
        Maturity: r.MaturityName || null,
        Item: r.ItemName,
        ItemType: r.ItemType || null,
        Frequency: r.Frequency || null,
        LastVU: r.LastVU || null,
        IsEvent: toBool(r.IsEvent),
        IsDropping: toBool(r.IsDropping),
      },
      {
        Mob: { type: 'Mob', id: r.MobId, name: r.MobName },
        Item: { type: r.ItemType || 'Item', id: r.ItemId, name: r.ItemName }
      }
    ))
  };
}

async function loadRefiningRecipes() {
  const rows = await safeRows(
    `SELECT rr."Id" AS "RecipeId",
            rr."Amount" AS "ProductAmount",
            p."Id" AS "ProductId", p."Name" AS "ProductName", p."Type" AS "ProductType",
            ri."Amount" AS "IngredientAmount",
            ing."Id" AS "IngredientId", ing."Name" AS "IngredientName", ing."Type" AS "IngredientType"
     FROM ONLY "RefiningRecipes" rr
     INNER JOIN ONLY "Items" p ON rr."ProductId" = p."Id"
     LEFT JOIN ONLY "RefiningIngredients" ri ON rr."Id" = ri."RecipeId"
     LEFT JOIN ONLY "Items" ing ON ri."ItemId" = ing."Id"
     ORDER BY p."Name", rr."Id", ing."Name" NULLS FIRST`
  );
  return {
    columns: [
      { key: 'Product', label: 'Product' },
      { key: 'ProductAmount', label: 'Product Amount' },
      { key: 'Ingredient', label: 'Ingredient' },
      { key: 'IngredientAmount', label: 'Ingredient Amount' },
    ],
    rows: rows.map((r) => withRefs(
      {
        Product: r.ProductName,
        ProductAmount: toNumberOrNull(r.ProductAmount),
        Ingredient: r.IngredientName || null,
        IngredientAmount: r.IngredientAmount === null || r.IngredientAmount === undefined ? null : Number(r.IngredientAmount),
      },
      {
        Product: { type: r.ProductType || 'Item', id: r.ProductId, name: r.ProductName },
        Ingredient: r.IngredientName
          ? { type: r.IngredientType || 'Item', id: r.IngredientId, name: r.IngredientName }
          : null
      }
    ))
  };
}

async function loadTiers() {
  const rows = await safeRows(
    `SELECT t."Tier", t."IsArmorSet", t."ItemId",
            COALESCE(s."Name", i."Name") AS "ItemName",
            i."Type" AS "ItemType",
            tm."Amount" AS "MaterialAmount",
            m."Id" AS "MaterialId", m."Name" AS "MaterialName"
     FROM ONLY "Tiers" t
     INNER JOIN ONLY "TierMaterials" tm ON t."Id" = tm."TierId"
     INNER JOIN ONLY "Materials" m ON tm."MaterialId" = m."Id"
     LEFT JOIN ONLY "Items" i ON t."IsArmorSet" = 0 AND t."ItemId" = i."Id"
     LEFT JOIN ONLY "ArmorSets" s ON t."IsArmorSet" = 1 AND t."ItemId" = s."Id"
     ORDER BY COALESCE(s."Name", i."Name"), t."Tier", m."Name"`
  );
  return {
    columns: [
      { key: 'Item', label: 'Item' },
      { key: 'Tier', label: 'Tier' },
      { key: 'IsArmorSet', label: 'Is Armor Set' },
      { key: 'Material', label: 'Material' },
      { key: 'Amount', label: 'Amount' },
    ],
    rows: rows.map((r) => {
      const itemType = Number(r.IsArmorSet) === 1 ? 'ArmorSet' : (r.ItemType || 'Item');
      return withRefs(
        {
          Item: r.ItemName,
          Tier: Number(r.Tier),
          IsArmorSet: toBool(r.IsArmorSet),
          Material: r.MaterialName,
          Amount: r.MaterialAmount === null || r.MaterialAmount === undefined ? null : Number(r.MaterialAmount),
        },
        {
          Item: { type: itemType, id: r.ItemId, name: r.ItemName },
          Material: { type: 'Material', id: r.MaterialId, name: r.MaterialName }
        }
      );
    })
  };
}

async function loadBlueprintDrops() {
  const rows = await safeRows(
    `SELECT bd."SourceId", s."Name" AS "SourceName",
            bd."DropId", d."Name" AS "DropName",
            d."Level" AS "DropLevel"
     FROM ONLY "BlueprintDrops" bd
     INNER JOIN ONLY "Blueprints" s ON s."Id" = bd."SourceId"
     INNER JOIN ONLY "Blueprints" d ON d."Id" = bd."DropId"
     ORDER BY s."Name", d."Name"`
  );
  return {
    columns: [
      { key: 'SourceBlueprint', label: 'Source Blueprint' },
      { key: 'DropBlueprint', label: 'Drop Blueprint' },
      { key: 'DropLevel', label: 'Drop Level' },
    ],
    rows: rows.map((r) => withRefs(
      {
        SourceBlueprint: r.SourceName,
        DropBlueprint: r.DropName,
        DropLevel: r.DropLevel === null || r.DropLevel === undefined ? null : Number(r.DropLevel),
      },
      {
        SourceBlueprint: { type: 'Blueprint', id: r.SourceId, name: r.SourceName },
        DropBlueprint: { type: 'Blueprint', id: r.DropId, name: r.DropName }
      }
    ))
  };
}

async function loadEffects() {
  const rows = await safeRows(
    `SELECT "Name", "Unit", "IsPositive", "LimitAction", "LimitItem", "LimitTotal", "Description"
     FROM ONLY "Effects"
     ORDER BY "Name"`
  );
  return {
    columns: [
      { key: 'Name', label: 'Name' },
      { key: 'Unit', label: 'Unit' },
      { key: 'IsPositive', label: 'Is Positive' },
      { key: 'LimitAction', label: 'Limit Action' },
      { key: 'LimitItem', label: 'Limit Item' },
      { key: 'LimitTotal', label: 'Limit Total' },
      { key: 'Description', label: 'Description' },
    ],
    rows: rows.map((r) => ({
      Name: r.Name,
      Unit: r.Unit || null,
      IsPositive: toBool(r.IsPositive),
      LimitAction: toNumberOrNull(r.LimitAction),
      LimitItem: toNumberOrNull(r.LimitItem),
      LimitTotal: toNumberOrNull(r.LimitTotal),
      Description: r.Description || null,
    }))
  };
}

async function loadEffectsOnEquip() {
  const rows = await safeRows(
    `SELECT eo."Strength",
            i."Id" AS "ItemId", i."Name" AS "ItemName", i."Type" AS "ItemType",
            e."Name" AS "EffectName", e."Unit", e."Description"
     FROM ONLY "EffectsOnEquip" eo
     INNER JOIN ONLY "Effects" e ON eo."EffectId" = e."Id"
     INNER JOIN ONLY "Items" i ON eo."ItemId" = i."Id"
     ORDER BY i."Name", e."Name"`
  );
  return {
    columns: [
      { key: 'Item', label: 'Item' },
      { key: 'ItemType', label: 'Item Type' },
      { key: 'Effect', label: 'Effect' },
      { key: 'Strength', label: 'Strength' },
      { key: 'Unit', label: 'Unit' },
      { key: 'Description', label: 'Description' },
    ],
    rows: rows.map((r) => withRefs(
      {
        Item: r.ItemName,
        ItemType: r.ItemType || null,
        Effect: r.EffectName,
        Strength: toNumberOrNull(r.Strength),
        Unit: r.Unit || null,
        Description: r.Description || null,
      },
      {
        Item: { type: r.ItemType || 'Item', id: r.ItemId, name: r.ItemName }
      }
    ))
  };
}

async function loadEffectsOnSetEquip() {
  const rows = await safeRows(
    `SELECT ese."SetId", ese."MinSetPieces", ese."Strength",
            e."Name" AS "EffectName", e."Unit", e."Description",
            aset."Id" AS "ArmorSetId", aset."Name" AS "ArmorSetName",
            es."Name" AS "EquipSetName"
     FROM ONLY "EffectsOnSetEquip" ese
     INNER JOIN ONLY "Effects" e ON ese."EffectId" = e."Id"
     LEFT JOIN ONLY "ArmorSets" aset ON aset."Id" = ese."SetId"
     LEFT JOIN ONLY "EquipSets" es ON es."Id" + 100000 = ese."SetId"
     ORDER BY COALESCE(aset."Name", es."Name"), ese."MinSetPieces", e."Name"`
  );
  return {
    columns: [
      { key: 'Set', label: 'Set' },
      { key: 'MinSetPieces', label: 'Min Set Pieces' },
      { key: 'Effect', label: 'Effect' },
      { key: 'Strength', label: 'Strength' },
      { key: 'Unit', label: 'Unit' },
      { key: 'Description', label: 'Description' },
    ],
    rows: rows.map((r) => {
      const setName = r.ArmorSetName || r.EquipSetName || `Set #${r.SetId}`;
      return withRefs(
        {
          Set: setName,
          MinSetPieces: Number(r.MinSetPieces),
          Effect: r.EffectName,
          Strength: toNumberOrNull(r.Strength),
          Unit: r.Unit || null,
          Description: r.Description || null,
        },
        {
          Set: r.ArmorSetId ? { type: 'ArmorSet', id: r.ArmorSetId, name: r.ArmorSetName } : null
        }
      );
    })
  };
}

async function loadEffectsOnUse() {
  const rows = await safeRows(
    `SELECT eu."Strength", eu."DurationSeconds", eu."IsSelfTarget",
            i."Id" AS "ItemId", i."Name" AS "ItemName", i."Type" AS "ItemType",
            e."Name" AS "EffectName", e."Unit", e."Description"
     FROM ONLY "EffectsOnUse" eu
     INNER JOIN ONLY "Effects" e ON eu."EffectId" = e."Id"
     INNER JOIN ONLY "Items" i ON eu."ItemId" = i."Id"
     ORDER BY i."Name", e."Name"`
  );
  return {
    columns: [
      { key: 'Item', label: 'Item' },
      { key: 'ItemType', label: 'Item Type' },
      { key: 'Effect', label: 'Effect' },
      { key: 'Strength', label: 'Strength' },
      { key: 'DurationSeconds', label: 'Duration Seconds' },
      { key: 'IsSelfTarget', label: 'Is Self Target' },
      { key: 'Unit', label: 'Unit' },
      { key: 'Description', label: 'Description' },
    ],
    rows: rows.map((r) => withRefs(
      {
        Item: r.ItemName,
        ItemType: r.ItemType || null,
        Effect: r.EffectName,
        Strength: toNumberOrNull(r.Strength),
        DurationSeconds: r.DurationSeconds === null || r.DurationSeconds === undefined ? null : Number(r.DurationSeconds),
        IsSelfTarget: toBool(r.IsSelfTarget),
        Unit: r.Unit || null,
        Description: r.Description || null,
      },
      {
        Item: { type: r.ItemType || 'Item', id: r.ItemId, name: r.ItemName }
      }
    ))
  };
}

async function loadEvents() {
  const rows = await safeRows(
    `SELECT "Name", "Description", "StartDate", "EndDate", "IsActive"
     FROM ONLY "Events"
     ORDER BY "StartDate" DESC NULLS LAST, "Name"`
  );
  return {
    columns: [
      { key: 'Name', label: 'Name' },
      { key: 'Description', label: 'Description' },
      { key: 'StartDate', label: 'Start Date' },
      { key: 'EndDate', label: 'End Date' },
      { key: 'IsActive', label: 'Is Active' },
    ],
    rows: rows.map((r) => ({
      Name: r.Name,
      Description: r.Description || null,
      StartDate: toIsoOrNull(r.StartDate),
      EndDate: toIsoOrNull(r.EndDate),
      IsActive: toBool(r.IsActive),
    }))
  };
}

async function loadLandAreaMinerals() {
  const rows = await safeRows(
    `SELECT lam."Rarity"::text AS "Rarity", lam."Notes",
            l."Id" AS "LocationId", l."Name" AS "LocationName", l."Type"::text AS "LocationType",
            m."Id" AS "MaterialId", m."Name" AS "MaterialName"
     FROM ONLY "LandAreaMinerals" lam
     INNER JOIN ONLY "Locations" l ON lam."LocationId" = l."Id"
     INNER JOIN ONLY "Materials" m ON lam."MaterialId" = m."Id"
     ORDER BY l."Name", m."Name"`
  );
  return {
    columns: [
      { key: 'Location', label: 'Location' },
      { key: 'Material', label: 'Material' },
      { key: 'Rarity', label: 'Rarity' },
      { key: 'Notes', label: 'Notes' },
    ],
    rows: rows.map((r) => withRefs(
      {
        Location: r.LocationName,
        Material: r.MaterialName,
        Rarity: r.Rarity || null,
        Notes: r.Notes || null,
      },
      {
        Location: {
          type: 'Location',
          id: r.LocationId,
          name: r.LocationName,
          locationType: r.LocationType || null
        },
        Material: { type: 'Material', id: r.MaterialId, name: r.MaterialName }
      }
    ))
  };
}

async function loadEffectsOnConsume() {
  const rows = await safeRows(
    `SELECT ec."Strength", ec."DurationSeconds",
            c."Id" AS "ConsumableId", c."Name" AS "ConsumableName",
            e."Name" AS "EffectName", e."Unit", e."Description"
     FROM ONLY "EffectsOnConsume" ec
     INNER JOIN ONLY "Effects" e ON ec."EffectId" = e."Id"
     INNER JOIN ONLY "Consumables" c ON ec."ConsumableId" = c."Id"
     ORDER BY c."Name", e."Name"`
  );
  return {
    columns: [
      { key: 'Consumable', label: 'Consumable' },
      { key: 'Effect', label: 'Effect' },
      { key: 'Strength', label: 'Strength' },
      { key: 'DurationSeconds', label: 'Duration Seconds' },
      { key: 'Unit', label: 'Unit' },
      { key: 'Description', label: 'Description' },
    ],
    rows: rows.map((r) => withRefs(
      {
        Consumable: r.ConsumableName,
        Effect: r.EffectName,
        Strength: toNumberOrNull(r.Strength),
        DurationSeconds: r.DurationSeconds === null || r.DurationSeconds === undefined ? null : Number(r.DurationSeconds),
        Unit: r.Unit || null,
        Description: r.Description || null,
      },
      {
        Consumable: { type: 'Consumable', id: r.ConsumableId, name: r.ConsumableName }
      }
    ))
  };
}

async function loadPlanets() {
  const rows = await safeRows(
    `SELECT "Id", "Name", "TechnicalName", "Description", "X", "Y", "Width", "Height"
     FROM ONLY "Planets"
     ORDER BY "Name"`
  );
  return {
    columns: [
      { key: 'Name', label: 'Name' },
      { key: 'TechnicalName', label: 'Technical Name' },
      { key: 'Description', label: 'Description' },
      { key: 'MapX', label: 'Map X' },
      { key: 'MapY', label: 'Map Y' },
      { key: 'MapWidth', label: 'Map Width' },
      { key: 'MapHeight', label: 'Map Height' },
    ],
    rows: rows.map((r) => withRefs(
      {
        Name: r.Name,
        TechnicalName: r.TechnicalName || null,
        Description: r.Description || null,
        MapX: r.X === null || r.X === undefined ? null : Number(r.X),
        MapY: r.Y === null || r.Y === undefined ? null : Number(r.Y),
        MapWidth: r.Width === null || r.Width === undefined ? null : Number(r.Width),
        MapHeight: r.Height === null || r.Height === undefined ? null : Number(r.Height),
      },
      {
        Name: {
          type: 'Planet',
          id: r.Id,
          name: r.Name,
          technicalName: r.TechnicalName || null
        }
      }
    ))
  };
}

async function loadVehicleAttachmentTypes() {
  const rows = await safeRows(
    `SELECT "Name", "Description"
     FROM ONLY "VehicleAttachmentTypes"
     ORDER BY "Name"`
  );
  return {
    columns: [
      { key: 'Name', label: 'Name' },
      { key: 'Description', label: 'Description' },
    ],
    rows: rows.map((r) => ({
      Name: r.Name,
      Description: r.Description || null
    }))
  };
}

const BUILTIN_LOADERS = {
  MobSpecies: loadMobSpecies,
  MobLoots: loadMobLoots,
  RefiningRecipes: loadRefiningRecipes,
  Tiers: loadTiers,
  BlueprintDrops: loadBlueprintDrops,
  Effects: loadEffects,
  EffectsOnEquip: loadEffectsOnEquip,
  EffectsOnSetEquip: loadEffectsOnSetEquip,
  EffectsOnUse: loadEffectsOnUse,
  Events: loadEvents,
  LandAreaMinerals: loadLandAreaMinerals,
  EffectsOnConsume: loadEffectsOnConsume,
  Planets: loadPlanets,
  VehicleAttachmentTypes: loadVehicleAttachmentTypes
};

async function getBuiltinDetail(name) {
  const def = BUILTIN_LOOKUP.get(String(name || '').toLowerCase());
  if (!def) return null;
  const loader = BUILTIN_LOADERS[def.name];
  const loaded = await loader();
  return formatDetail({
    id: null,
    name: def.name,
    source: 'builtin',
    description: def.description,
    unit: null,
    metadata: null,
    columns: loaded.columns,
    rows: loaded.rows
  });
}

function register(app) {
  /**
   * @swagger
   * /enumerations:
   *  get:
   *    description: Get all custom and built-in enumerations
   *    responses:
   *      '200':
   *        description: A list of enumerations
   */
  app.get('/enumerations', async (req, res, next) => {
    try {
      const custom = await getCustomEnumerations();
      const customNames = new Set(custom.map((x) => String(x.Name).toLowerCase()));

      const customItems = custom.map((x) => formatListItem({
        id: x.Id,
        name: x.Name,
        source: 'custom',
        description: x.Description || null,
        unit: x.Unit || null,
        metadata: x.Metadata || null
      }));

      const builtinItems = BUILTIN_ENUMERATIONS
        .filter((x) => !customNames.has(x.name.toLowerCase()))
        .map((x) => formatListItem({
          id: null,
          name: x.name,
          source: 'builtin',
          description: x.description,
          unit: null,
          metadata: null
        }));

      const result = [...customItems, ...builtinItems]
        .sort((a, b) => a.Name.localeCompare(b.Name));

      res.json(result);
    } catch (err) {
      next(err);
    }
  });

  /**
   * @swagger
   * /enumerations/{enumeration}:
   *  get:
   *    description: Get a custom or built-in enumeration by name
   *    parameters:
   *      - in: path
   *        name: enumeration
   *        schema:
   *          type: string
   *        required: true
   *    responses:
   *      '200':
   *        description: The enumeration detail
   *      '404':
   *        description: Enumeration not found
   */
  app.get('/enumerations/:enumeration', async (req, res, next) => {
    try {
      const enumeration = req.params.enumeration;

      const custom = await getCustomEnumerationByName(enumeration);
      if (custom) {
        const values = await getCustomEnumerationValues(custom.Id);
        const table = buildCustomDetailTable(custom.Metadata || null, values);
        const detail = formatDetail({
          id: custom.Id,
          name: custom.Name,
          source: 'custom',
          description: custom.Description || null,
          unit: custom.Unit || null,
          metadata: custom.Metadata || null,
          columns: table.columns,
          rows: table.rows
        });
        return res.json(detail);
      }

      const builtin = await getBuiltinDetail(enumeration);
      if (builtin) return res.json(builtin);

      return res.status(404).send();
    } catch (err) {
      next(err);
    }
  });
}

module.exports = { register };
