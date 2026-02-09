import { SlashCommandBuilder } from 'discord.js';
import { findTradeRequestByThread, updateTradeRequestStatus } from '../../db.js';

export const data = new SlashCommandBuilder()
  .setName('done')
  .setDescription('Mark the current trade as completed and close the thread');

export async function execute(interaction) {
  // Must be used in a thread
  if (!interaction.channel.isThread()) {
    return interaction.reply({ content: 'This command can only be used inside a trade thread.', flags: 64 });
  }

  const tradeRequest = await findTradeRequestByThread(interaction.channel.id);
  if (!tradeRequest) {
    return interaction.reply({ content: 'This thread is not a trade request thread.', flags: 64 });
  }

  if (tradeRequest.status !== 'active') {
    return interaction.reply({ content: `This trade is already ${tradeRequest.status}.`, flags: 64 });
  }

  // Only participants can close the trade
  const userId = interaction.user.id;
  if (userId !== tradeRequest.requester_id.toString() && userId !== tradeRequest.target_id.toString()) {
    return interaction.reply({ content: 'Only trade participants can close a trade.', flags: 64 });
  }

  try {
    await updateTradeRequestStatus(tradeRequest.id, 'completed');

    await interaction.reply(
      `\u2705 **Trade Completed** — This trade has been marked as completed by <@${userId}>. Thread will be locked and archived.`
    );

    // Lock and archive the thread
    await interaction.channel.setLocked(true).catch(() => {});
    await interaction.channel.setArchived(true).catch(() => {});
  } catch (error) {
    console.error('Error completing trade:', error);
    await interaction.reply({ content: 'An error occurred while completing the trade.', flags: 64 });
  }
}
