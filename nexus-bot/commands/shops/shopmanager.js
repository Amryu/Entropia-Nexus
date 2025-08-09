import { SlashCommandBuilder } from 'discord.js';
import { getShopByName, getShopById, addShopManager, removeShopManager, getShopManagers, getUserByUsername } from '../../db.js';

export const data = new SlashCommandBuilder()
  .setName('shopmanager')
  .setDescription('Add or remove a shop manager')
  .addStringOption(option => option.setName('action')
    .setDescription('Action to perform')
    .setRequired(true)
    .addChoices(
      { name: 'Add', value: 'add' },
      { name: 'Remove', value: 'remove' },
      { name: 'List', value: 'list' }
    ))
  .addStringOption(option => option.setName('shop')
    .setDescription('The name or ID of the shop')
    .setRequired(true))
  .addUserOption(option => option.setName('user')
    .setDescription('The user to add/remove as manager'))
  .addStringOption(option => option.setName('username')
    .setDescription('Username of the user to add/remove as manager (alternative to @user)'));

export async function execute(interaction) {
  const adminUserId = '178245652633878528';
  
  const action = interaction.options.getString('action');
  const shopIdentifier = interaction.options.getString('shop');
  const targetUser = interaction.options.getUser('user');
  const targetUsername = interaction.options.getString('username');

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

    // Check permissions - admin, shop owner, or existing manager can manage
    const isAdmin = interaction.user.id === adminUserId;
    const isOwner = shop.owner_id === interaction.user.id;
    
    let isManager = false;
    if (!isAdmin && !isOwner) {
      const managers = await getShopManagers(shop.id);
      isManager = managers.some(m => m.user_id === interaction.user.id);
    }

    if (!isAdmin && !isOwner && !isManager) {
      return interaction.reply({ content: 'You do not have permission to manage this shop.', ephemeral: true });
    }

    // Handle list action
    if (action === 'list') {
      const managers = await getShopManagers(shop.id);
      if (managers.length === 0) {
        return interaction.reply(`Shop "${shop.name}" has no managers.`);
      }
      
      const managerList = managers.map(m => `• ${m.username || m.global_name || `<@${m.user_id}>`}`).join('\n');
      return interaction.reply(`**Managers for "${shop.name}":**\n${managerList}`);
    }

    // For add/remove actions, we need a target user
    if (!targetUser && !targetUsername) {
      return interaction.reply({ content: 'Please specify a user to add or remove as manager.', ephemeral: true });
    }

    let targetUserId;
    let userDisplay;

    if (targetUser) {
      targetUserId = targetUser.id;
      userDisplay = `<@${targetUser.id}>`;
    } else if (targetUsername) {
      const user = await getUserByUsername(targetUsername);
      if (!user) {
        return interaction.reply({ content: `User "${targetUsername}" not found in the database.`, ephemeral: true });
      }
      targetUserId = user.id;
      userDisplay = `${user.username}`;
    }

    if (action === 'add') {
      // Check if user is already the owner
      if (shop.owner_id === targetUserId) {
        return interaction.reply({ content: `${userDisplay} is already the owner of this shop.`, ephemeral: true });
      }

      await addShopManager(shop.id, targetUserId);
      await interaction.reply(`✅ ${userDisplay} has been added as a manager for "${shop.name}".`);
      
    } else if (action === 'remove') {
      await removeShopManager(shop.id, targetUserId);
      await interaction.reply(`✅ ${userDisplay} has been removed as a manager from "${shop.name}".`);
    }

  } catch (error) {
    console.error('Error managing shop manager:', error);
    await interaction.reply({ content: 'An error occurred while managing the shop manager.', ephemeral: true });
  }
}
