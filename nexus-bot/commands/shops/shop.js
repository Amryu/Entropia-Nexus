import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import {
  getShops,
  getShopByName,
  getShopById,
  getShopManagers,
  getUserShops,
  addShopManager,
  removeShopManager,
  updateShopOwner,
  getUserByUsername
} from '../../db.js';

export const data = new SlashCommandBuilder()
  .setName('shop')
  .setDescription('Manage shops')
  .addSubcommand(subcommand =>
    subcommand
      .setName('info')
      .setDescription('Get information about a shop or list all shops')
      .addStringOption(option =>
        option
          .setName('shop')
          .setDescription('The name or ID of a specific shop (leave empty to list all shops)')))
  .addSubcommand(subcommand =>
    subcommand
      .setName('list')
      .setDescription('List shops you own or manage')
      .addUserOption(option =>
        option
          .setName('user')
          .setDescription('The user to check shops for (admin only)')))
  .addSubcommand(subcommand =>
    subcommand
      .setName('addmanager')
      .setDescription('Add a manager to a shop')
      .addStringOption(option =>
        option
          .setName('shop')
          .setDescription('The name or ID of the shop')
          .setRequired(true))
      .addUserOption(option =>
        option
          .setName('user')
          .setDescription('The user to add as manager'))
      .addStringOption(option =>
        option
          .setName('username')
          .setDescription('Username of the user to add as manager (alternative to @user)')))
  .addSubcommand(subcommand =>
    subcommand
      .setName('removemanager')
      .setDescription('Remove a manager from a shop')
      .addStringOption(option =>
        option
          .setName('shop')
          .setDescription('The name or ID of the shop')
          .setRequired(true))
      .addUserOption(option =>
        option
          .setName('user')
          .setDescription('The user to remove as manager'))
      .addStringOption(option =>
        option
          .setName('username')
          .setDescription('Username of the user to remove as manager (alternative to @user)')))
  .addSubcommand(subcommand =>
    subcommand
      .setName('listmanagers')
      .setDescription('List all managers of a shop')
      .addStringOption(option =>
        option
          .setName('shop')
          .setDescription('The name or ID of the shop')
          .setRequired(true)))
  .addSubcommand(subcommand =>
    subcommand
      .setName('setowner')
      .setDescription('Set or remove the owner of a shop (admin only)')
      .addStringOption(option =>
        option
          .setName('shop')
          .setDescription('The name or ID of the shop')
          .setRequired(true))
      .addUserOption(option =>
        option
          .setName('owner')
          .setDescription('The user to set as owner (leave empty to remove owner)'))
      .addStringOption(option =>
        option
          .setName('username')
          .setDescription('Username of the user to set as owner (alternative to @user)')));

export async function execute(interaction) {
  const subcommand = interaction.options.getSubcommand();
  const adminUserId = '178245652633878528';

  try {
    switch (subcommand) {
      case 'info':
        await handleInfo(interaction);
        break;
      case 'list':
        await handleList(interaction);
        break;
      case 'addmanager':
        await handleAddManager(interaction, adminUserId);
        break;
      case 'removemanager':
        await handleRemoveManager(interaction, adminUserId);
        break;
      case 'listmanagers':
        await handleListManagers(interaction);
        break;
      case 'setowner':
        await handleSetOwner(interaction, adminUserId);
        break;
      default:
        await interaction.reply({ content: 'Unknown subcommand.', ephemeral: true });
    }
  } catch (error) {
    console.error(`Error in /shop ${subcommand}:`, error);
    await interaction.reply({ content: 'An error occurred while processing your request.', ephemeral: true });
  }
}

async function handleInfo(interaction) {
  const shopIdentifier = interaction.options.getString('shop');

  if (!shopIdentifier) {
    // List all shops
    const shops = await getShops();

    if (shops.length === 0) {
      return interaction.reply('No shops found.');
    }

    // Group shops by owner status
    const ownedShops = shops.filter(s => s.owner_id);
    const unownedShops = shops.filter(s => !s.owner_id);

    let response = `**All Shops (${shops.length} total):**\n\n`;

    if (ownedShops.length > 0) {
      response += `**Owned Shops (${ownedShops.length}):**\n`;
      response += ownedShops.map(shop =>
        `• **${shop.name}** (ID: ${shop.id}) - ${shop.planet_name || 'Unknown Planet'} - Owner: <@${shop.owner_id}>`
      ).join('\n');
      response += '\n\n';
    }

    if (unownedShops.length > 0) {
      response += `**Unowned Shops (${unownedShops.length}):**\n`;
      response += unownedShops.map(shop =>
        `• **${shop.name}** (ID: ${shop.id}) - ${shop.planet_name || 'Unknown Planet'}`
      ).join('\n');
    }

    // Discord has a 2000 character limit, so we might need to truncate
    if (response.length > 1900) {
      response = response.substring(0, 1900) + '\n... (truncated)';
    }

    return interaction.reply(response);
  } else {
    // Get specific shop info
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

    const managers = await getShopManagers(shop.id);

    let response = `**${shop.name}** (ID: ${shop.id})\n`;
    response += `📍 **Location:** ${shop.planet_name || 'Unknown Planet'}`;

    if (shop.longitude && shop.latitude) {
      response += ` (${shop.longitude}, ${shop.latitude})`;
    }
    response += '\n';

    if (shop.description) {
      response += `📝 **Description:** ${shop.description}\n`;
    }

    response += `👤 **Owner:** ${shop.owner_id ? `<@${shop.owner_id}>` : 'No Owner'}\n`;

    if (managers.length > 0) {
      response += `🛠️ **Managers:** ${managers.map(m => `<@${m.user_id}>`).join(', ')}\n`;
    } else {
      response += `🛠️ **Managers:** None\n`;
    }

    if (shop.updated_at) {
      response += `🕒 **Last Updated:** <t:${Math.floor(new Date(shop.updated_at).getTime() / 1000)}:R>`;
    }

    return interaction.reply(response);
  }
}

async function handleList(interaction) {
  const targetUser = interaction.options.getUser('user');
  const isAdminQuery = targetUser && interaction.member.permissions.has('ADMINISTRATOR');

  // If checking another user, must be admin
  if (targetUser && !isAdminQuery) {
    return interaction.reply({ content: 'You do not have permission to check other users\' shops.', ephemeral: true });
  }

  const discordUserId = targetUser ? targetUser.id : interaction.user.id;
  const displayName = targetUser ? targetUser.username : interaction.user.username;

  const shops = await getUserShops(discordUserId);

  if (shops.length === 0) {
    return interaction.reply({
      content: targetUser ? `**${displayName}** doesn't own or manage any shops.` : 'You don\'t own or manage any shops.',
      ephemeral: true
    });
  }

  const embed = new EmbedBuilder()
    .setTitle(`${displayName}'s Shops`)
    .setColor(0x0099FF);

  for (const shop of shops) {
    const managers = await getShopManagers(shop.id);
    const isOwner = shop.owner_id === discordUserId;
    const role = isOwner ? 'Owner' : 'Manager';

    let fieldValue = `**Role:** ${role}\n`;
    fieldValue += `**Planet:** ${shop.planet_name || 'Unknown'}\n`;

    if (shop.longitude && shop.latitude) {
      fieldValue += `**Location:** ${shop.longitude}, ${shop.latitude}\n`;
    }

    if (managers.length > 0) {
      fieldValue += `**Managers:** ${managers.map(m => m.username).join(', ')}\n`;
    }

    embed.addFields({
      name: shop.name,
      value: fieldValue,
      inline: true
    });
  }

  await interaction.reply({ embeds: [embed], ephemeral: !isAdminQuery });
}

async function handleAddManager(interaction, adminUserId) {
  const shopIdentifier = interaction.options.getString('shop');
  const targetUser = interaction.options.getUser('user');
  const targetUsername = interaction.options.getString('username');

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

  // Check permissions - admin, shop owner, or existing manager can add managers
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

  // Get target user info
  if (!targetUser && !targetUsername) {
    return interaction.reply({ content: 'Please specify a user to add as manager.', ephemeral: true });
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

  // Check if user is already the owner
  if (shop.owner_id === targetUserId) {
    return interaction.reply({ content: `${userDisplay} is already the owner of this shop.`, ephemeral: true });
  }

  await addShopManager(shop.id, targetUserId);
  await interaction.reply(`✅ ${userDisplay} has been added as a manager for "${shop.name}".`);
}

async function handleRemoveManager(interaction, adminUserId) {
  const shopIdentifier = interaction.options.getString('shop');
  const targetUser = interaction.options.getUser('user');
  const targetUsername = interaction.options.getString('username');

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

  // Check permissions - admin, shop owner, or existing manager can remove managers
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

  // Get target user info
  if (!targetUser && !targetUsername) {
    return interaction.reply({ content: 'Please specify a user to remove as manager.', ephemeral: true });
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

  await removeShopManager(shop.id, targetUserId);
  await interaction.reply(`✅ ${userDisplay} has been removed as a manager from "${shop.name}".`);
}

async function handleListManagers(interaction) {
  const shopIdentifier = interaction.options.getString('shop');

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

  const managers = await getShopManagers(shop.id);
  if (managers.length === 0) {
    return interaction.reply(`Shop "${shop.name}" has no managers.`);
  }

  const managerList = managers.map(m => `• ${m.username || m.global_name || `<@${m.user_id}>`}`).join('\n');
  return interaction.reply(`**Managers for "${shop.name}":**\n${managerList}`);
}

async function handleSetOwner(interaction, adminUserId) {
  // Check permissions - only admin can change ownership
  if (interaction.user.id !== adminUserId) {
    return interaction.reply({ content: 'You do not have permission to use this command.', ephemeral: true });
  }

  const shopIdentifier = interaction.options.getString('shop');
  const ownerUser = interaction.options.getUser('owner');
  const ownerUsername = interaction.options.getString('username');

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
}
