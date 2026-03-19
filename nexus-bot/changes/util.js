import { commitTransaction, rollbackTransaction, startNexusTransaction } from "../db.js";
import { UpsertConfigs } from "./entity.js";

export async function applyChange(change) {
  let config = UpsertConfigs[change.entity];

  if (!config) {
    console.error(`No upsert config found for entity: ${change.entity}`);
    return false;
  }

  let object = change.data;

  let client = await startNexusTransaction();

  try {
    // Compute column values inside try-catch so errors rollback the transaction
    let columnData = await Promise.all(config.columns.map(async col => ({ name: col.name, value: await col.value(object, client) })));

    if (object.Id) {
      const updateResult = await client.query(`UPDATE ONLY "${config.table}"
          SET
            ${columnData.map((col, i) => `"${col.name}" = $${i + 1}`).join(", ")}
          WHERE "Id" = $${columnData.length + 1}`, columnData.map(col => col.value).concat(object.Id));

      // Entity has an Id but doesn't exist yet — insert with explicit Id
      if (updateResult.rowCount === 0) {
        console.warn(`[applyChange] UPDATE matched 0 rows for ${config.table} Id=${object.Id}, inserting with explicit Id`);
        await client.query(`INSERT INTO "${config.table}" (
            "Id", ${columnData.map((col) => `"${col.name}"`).join(", ")}
          ) VALUES (
            $1, ${columnData.map((_, i) => `$${i + 2}`).join(", ")}
          )`, [object.Id, ...columnData.map(col => col.value)]);
      }
    }
    else {
      object.Id = await client.query(`INSERT INTO "${config.table}" (
          ${columnData.map((col) => `"${col.name}"`).join(", ")}
        ) VALUES (
          ${columnData.map((_, i) => `$${i + 1}`).join(", ")}
        ) RETURNING "Id"`, columnData.map(col => col.value))
        .then(res => res.rows[0].Id);
    }

    if (config.relationChangeFunc) {
      await config.relationChangeFunc(client, (config.offset ?? 0) + object.Id, object);
    }

    // Upsert or remove ClassId in the centralized lookup table
    if (object.ClassId != null && object.ClassId !== undefined) {
      await client.query(
        `INSERT INTO "ClassIds" ("EntityType", "EntityId", "ClassId")
         VALUES ($1, $2, $3)
         ON CONFLICT ("EntityType", "EntityId") DO UPDATE SET "ClassId" = $3`,
        [change.entity, object.Id, object.ClassId]
      );
    } else if (object.ClassId === null) {
      await client.query(
        'DELETE FROM ONLY "ClassIds" WHERE "EntityType" = $1 AND "EntityId" = $2',
        [change.entity, object.Id]
      );
    }

    await commitTransaction(client);

    return true;
  }
  catch (error) {
    console.error(error);
    await rollbackTransaction(client);

    return false;
  }
}