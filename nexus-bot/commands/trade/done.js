import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';
import { findTradeRequestByThread } from '../../db.js';

export const data = new SlashCommandBuilder()
  .setName('done')
  .setDescription('Close this trade thread (whether or not a trade was made)');

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

  // Only the target (offer owner/seller) can close the thread
  const userId = interaction.user.id;
  if (userId !== tradeRequest.target_id.toString()) {
    return interaction.reply({
      content: 'Only the order owner (the person receiving the trade request) can close this thread.',
      flags: 64
    });
  }

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`trade_done_yes_${tradeRequest.id}`)
      .setLabel('Trade completed — adjust quantities')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId(`trade_done_no_${tradeRequest.id}`)
      .setLabel('No trade happened — cancel')
      .setStyle(ButtonStyle.Secondary),
    new ButtonBuilder()
      .setCustomId(`trade_done_cancel_${tradeRequest.id}`)
      .setLabel('Go back')
      .setStyle(ButtonStyle.Danger),
  );

  await interaction.reply({
    content: '**Close Trade Thread** — Did the trade go through?',
    components: [row],
    flags: 64
  });
}
