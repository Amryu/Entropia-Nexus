import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';
import { getUserShops, getShopManagers } from "../../db.js";

export const data = new SlashCommandBuilder()
  .setName('myshops')
  .setDescription('List shops you own or manage.')
  .addUserOption(option => option.setName('user')
    .setDescription('The user to check shops for (admin only).')
    .setRequired(false));

export async function execute(interaction) {
  const targetUser = interaction.options.getUser('user');
  const isAdminQuery = targetUser && interaction.member.permissions.has('ADMINISTRATOR');
  
  // If checking another user, must be admin
  if (targetUser && !isAdminQuery) {
    return interaction.reply({ content: 'You do not have permission to check other users\' shops.', ephemeral: true });
  }

  const discordUserId = targetUser ? targetUser.id : interaction.user.id;
  const displayName = targetUser ? targetUser.username : interaction.user.username;

  try {
    // Get user's shops
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
  } catch (error) {
    console.error('Error fetching user shops:', error);
    await interaction.reply({ content: 'An error occurred while fetching shop information.', ephemeral: true });
  }
}
