import { SlashCommandBuilder } from 'discord.js';
import { setConfigValue } from "../../bot.js";

export const data = new SlashCommandBuilder()
  .setName('setpendingchangeschannel')
  .setDescription('Set the channel that will be used for pending changes.')
  .addChannelOption(option => option.setName('channel')
    .setDescription('The channel to set as the pending changes channel.')
    .setRequired(true));
export async function execute(interaction) {
  if (!interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply('You do not have permission to use this command.');
  }

  const channel = interaction.options.getChannel('channel');
  if (!channel) {
    return interaction.reply('Please provide a channel.');
  }
  setConfigValue('pendingChangesChannelId', channel.id);
  await interaction.reply(`Pending changes channel set to <#${channel.id}>.`);
}