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
      `You can turn off these notifications with \`/rewards notifications\`.`,
    ];

    await dmUser.send(lines.join('\n'));
  } catch (e) {
    console.error(`[rewards] Failed to DM user ${userId}:`, e.message);
  }
}

/**
 * Format a contributor balance into a human-readable string.
 */
export function formatBalance(balance) {
  return `**${balance.balance.toFixed(2)} PED** (earned: ${balance.total_earned.toFixed(2)}, paid out: ${balance.total_paid.toFixed(2)}, score: ${balance.total_score.toFixed(0)})`;
}
