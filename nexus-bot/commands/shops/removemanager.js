import { SlashCommandBuilder } from 'discord.js';
import { getShopByName, removeShopManager, getUserByUsername } from "../../db.js";

export const data = new SlashCommandBuilder()
  .setName('removeshopmanager')
  .setDescription('Remove a manager from a shop.')
  .addStringOption(option => option.setName('shop')
    .setDescription('The name of the shop.')
    .setRequired(true))
  .addStringOption(option => option.setName('username')
    .setDescription('The username of the manager to remove.')
    .setRequired(true));

export async function execute(interaction) {
  if (!interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply({ content: 'You do not have permission to use this command.', ephemeral: true });
  }

  const shopName = interaction.options.getString('shop');
  const username = interaction.options.getString('username');

  if (!shopName || !username) {
    return interaction.reply({ content: 'Please provide both shop name and username.', ephemeral: true });
  }

  try {
    // Find the shop
    const shop = await getShopByName(shopName);
    if (!shop) {
      return interaction.reply({ content: `Shop "${shopName}" not found.`, ephemeral: true });
    }

    // Find the user
    const user = await getUserByUsername(username);
    if (!user) {
      return interaction.reply({ content: `User "${username}" not found.`, ephemeral: true });
    }

    // Remove manager
    await removeShopManager(shop.id, user.id);

    await interaction.reply({
      content: `Successfully removed **${user.username}** as a manager from shop **${shop.name}**.`,
      ephemeral: false
    });
  } catch (error) {
    console.error('Error removing shop manager:', error);
    await interaction.reply({ content: 'An error occurred while removing the shop manager.', ephemeral: true });
  }
}
