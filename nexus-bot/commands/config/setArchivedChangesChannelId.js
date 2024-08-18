import { SlashCommandBuilder } from 'discord.js';
import { setConfigValue } from "../../bot.js";

export const data = new SlashCommandBuilder()
  .setName('setarchivedchangeschannel')
  .setDescription('Set the channel that will be used for archived changes.')
  .addChannelOption(option => option.setName('channel')
    .setDescription('The channel to set as the archived changes channel.')
    .setRequired(true));
export async function execute(interaction) {
  if (!interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply('You do not have permission to use this command.');
  }

  const channel = interaction.options.getChannel('channel');
  if (!channel) {
    return interaction.reply('Please provide a channel.');
  }
  setConfigValue('archivedChangesChannelId', channel.id);
  await interaction.reply(`Archived changes channel set to <#${channel.id}>.`);
}