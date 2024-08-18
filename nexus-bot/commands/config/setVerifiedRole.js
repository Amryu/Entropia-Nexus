import { SlashCommandBuilder } from 'discord.js';
import { setConfigValue } from "../../bot.js";

export const data = new SlashCommandBuilder()
  .setName('setverifiedrole')
  .setDescription('Set the role that will be given to verified users.')
  .addRoleOption(option => option.setName('role')
    .setDescription('The role to set as the verified role.')
    .setRequired(true));
export async function execute(interaction) {
  if (!interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply('You do not have permission to use this command.');
  }

  const role = interaction.options.getRole('role');
  if (!role) {
    return interaction.reply('Please provide a role.');
  }
  setConfigValue('verifiedRoleId', role.id);
  await interaction.reply(`Verified role set to <@&${role.id}>.`);
}