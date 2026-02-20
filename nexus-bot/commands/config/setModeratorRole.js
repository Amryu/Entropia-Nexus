import { SlashCommandBuilder, PermissionFlagsBits } from 'discord.js';
import { setConfigValue } from "../../bot.js";

export const data = new SlashCommandBuilder()
  .setName('setmoderatorrole')
  .setDescription('Set the role that will be given to moderators.')
  .addRoleOption(option => option.setName('role')
    .setDescription('The role to set as the moderator role.')
    .setRequired(true));
export async function execute(interaction) {
  if (!interaction.member.permissions.has(PermissionFlagsBits.Administrator)) {
    return interaction.reply('You do not have permission to use this command.');
  }

  const role = interaction.options.getRole('role');
  if (!role) {
    return interaction.reply('Please provide a role.');
  }
  setConfigValue('moderatorRoleId', role.id);
  await interaction.reply(`Moderator role set to <@&${role.id}>.`);
}