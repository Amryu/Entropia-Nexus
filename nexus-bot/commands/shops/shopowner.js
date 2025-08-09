import { SlashCommandBuilder } from 'discord.js';
import { getShopByName, getShopById, updateShopOwner, getUserByUsername } from '../../db.js';

export const data = new SlashCommandBuilder()
  .setName('shopowner')
  .setDescription('Set or remove the owner of a shop')
  .addStringOption(option => option.setName('shop')
    .setDescription('The name or ID of the shop')
    .setRequired(true))
  .addUserOption(option => option.setName('owner')
    .setDescription('The user to set as owner (leave empty to remove owner)'))
  .addStringOption(option => option.setName('username')
    .setDescription('Username of the user to set as owner (alternative to @user)'));

export async function execute(interaction) {
  const adminUserId = '178245652633878528';
  
  // Check permissions - only admin or shop owner can change ownership
  if (interaction.user.id !== adminUserId) {
    return interaction.reply({ content: 'You do not have permission to use this command.', ephemeral: true });
  }

  const shopIdentifier = interaction.options.getString('shop');
  const ownerUser = interaction.options.getUser('owner');
  const ownerUsername = interaction.options.getString('username');

  try {
    // Find the shop
    let shop = await getShopByName(shopIdentifier);
    if (!shop) {
      const shopId = parseInt(shopIdentifier);
      if (!isNaN(shopId)) {
        shop = await getShopById(shopId);
      }
    }

    if (!shop) {
      return interaction.reply({ content: `Shop "${shopIdentifier}" not found.`, ephemeral: true });
    }

    let newOwnerId = null;
    let ownerDisplay = 'No Owner';

    // Determine the new owner
    if (ownerUser) {
      newOwnerId = ownerUser.id;
      ownerDisplay = `<@${ownerUser.id}>`;
    } else if (ownerUsername) {
      const user = await getUserByUsername(ownerUsername);
      if (!user) {
        return interaction.reply({ content: `User "${ownerUsername}" not found in the database.`, ephemeral: true });
      }
      newOwnerId = user.id;
      ownerDisplay = `${user.username}`;
    }

    // Update the shop owner
    await updateShopOwner(shop.id, newOwnerId);

    if (newOwnerId) {
      await interaction.reply(`✅ Shop "${shop.name}" ownership has been set to ${ownerDisplay}.`);
    } else {
      await interaction.reply(`✅ Shop "${shop.name}" ownership has been removed.`);
    }

  } catch (error) {
    console.error('Error setting shop owner:', error);
    await interaction.reply({ content: 'An error occurred while updating the shop owner.', ephemeral: true });
  }
}
