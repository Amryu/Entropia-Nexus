import { getContributorBalance, getRewardDmEnabled } from './db.js';

/**
 * Send a DM to a user notifying them of a reward assignment.
 * Respects the user's reward DM preference. Silently fails if DMs are disabled.
 */
export async function sendRewardDm(client, userId, { amount, contribution_score, note }) {
  try {
    if (!(await getRewardDmEnabled(userId))) return;

    const balance = await getContributorBalance(userId);
    const dmUser = await client.users.fetch(String(userId));

    const lines = [
      `You received a contributor reward of **${amount.toFixed(2)} PED**` +
        (contribution_score > 0 ? ` (+${contribution_score} score)` : '') +
        ` — ${note}`,
      '',
      `Your balance: **${balance.balance.toFixed(2)} PED** (earned: ${balance.total_earned.toFixed(2)}, paid out: ${balance.total_paid.toFixed(2)}, score: ${balance.total_score.toFixed(0)})`,
      '',
      `You can turn off these notifications with \`/rewards notifications\` in the server.`,
    ];

    await dmUser.send(lines.join('\n'));
  } catch (e) {
    console.error(`[rewards] Failed to DM user ${userId}:`, e.message);
  }
}

/**
 * Send a DM notifying a user that their change was denied.
 * Includes the optional denial reason if provided.
 */
export async function sendChangeDenialDm(client, userId, { changeName, changeType, entity, reason }) {
  try {
    if (!(await getRewardDmEnabled(userId))) return;

    const dmUser = await client.users.fetch(String(userId));

    const lines = [
      `Your **${entity}** ${changeType.toLowerCase()} change "**${changeName}**" was denied.`,
    ];
    if (reason) {
      lines.push(`Reason: ${reason}`);
    }
    lines.push('', `You can turn off these notifications with \`/rewards notifications\` in the server.`);

    await dmUser.send(lines.join('\n'));
  } catch (e) {
    console.error(`[rewards] Failed to send denial DM to user ${userId}:`, e.message);
  }
}

/**
 * Send a combined DM notifying a user that their change was approved,
 * including all reward details (if any) in a single message.
 */
export async function sendChangeApprovalDm(client, userId, { changeName, changeType, entity, rewards }) {
  try {
    if (!(await getRewardDmEnabled(userId))) return;

    const dmUser = await client.users.fetch(String(userId));

    const lines = [
      `Your **${entity}** ${changeType.toLowerCase()} change "**${changeName}**" was approved!`,
    ];

    if (rewards.length > 0) {
      lines.push('');
      for (const r of rewards) {
        lines.push(
          `Reward: **${r.amount.toFixed(2)} PED**` +
            (r.contribution_score > 0 ? ` (+${r.contribution_score} score)` : '') +
            ` — ${r.note}`
        );
      }

      const balance = await getContributorBalance(userId);
      lines.push('', `Your balance: **${balance.balance.toFixed(2)} PED** (earned: ${balance.total_earned.toFixed(2)}, paid out: ${balance.total_paid.toFixed(2)}, score: ${balance.total_score.toFixed(0)})`);
    }

    lines.push('', `You can turn off these notifications with \`/rewards notifications\` in the server.`);

    await dmUser.send(lines.join('\n'));
  } catch (e) {
    console.error(`[rewards] Failed to send approval DM to user ${userId}:`, e.message);
  }
}

/**
 * Format a contributor balance into a human-readable string.
 */
export function formatBalance(balance) {
  return `**${balance.balance.toFixed(2)} PED** (earned: ${balance.total_earned.toFixed(2)}, paid out: ${balance.total_paid.toFixed(2)}, score: ${balance.total_score.toFixed(0)})`;
}
