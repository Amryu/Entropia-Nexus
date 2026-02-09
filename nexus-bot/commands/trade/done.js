import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';
import { findTradeRequestByThread } from '../../db.js';

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

  // Only the target (offer owner/seller) can complete the trade
  const userId = interaction.user.id;
  if (userId !== tradeRequest.target_id.toString()) {
    return interaction.reply({
      content: 'Only the offer owner (the person receiving the trade request) can mark a trade as completed.',
      flags: 64
    });
  }

  const row = new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`trade_done_yes_${tradeRequest.id}`)
      .setLabel('Yes')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId(`trade_done_no_${tradeRequest.id}`)
      .setLabel('No')
      .setStyle(ButtonStyle.Secondary),
    new ButtonBuilder()
      .setCustomId(`trade_done_cancel_${tradeRequest.id}`)
      .setLabel('Cancel')
      .setStyle(ButtonStyle.Danger),
  );

  await interaction.reply({
    content: '**Complete Trade** — Should the offer quantities be adjusted automatically to reflect the traded amounts?',
    components: [row],
    flags: 64
  });
}
