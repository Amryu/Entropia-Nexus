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

  let columnData = await Promise.all(config.columns.map(async col => ({ name: col.name, value: await col.value(object, client) })));

  try {
    if (object.Id) {
      await client.query(`UPDATE ONLY "${config.table}"
          SET
            ${columnData.map((col, i) => `"${col.name}" = $${i + 1}`).join(", ")}
          WHERE "Id" = $${columnData.length + 1}`, columnData.map(col => col.value).concat(object.Id));
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

    await commitTransaction(client);

    return true;
  }
  catch (error) {
    console.error(error);
    await rollbackTransaction(client);

    return false;
  }
}