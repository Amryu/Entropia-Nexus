import { SlashCommandBuilder } from 'discord.js';
import { getShops, getShopByName, getShopById, getShopManagers } from '../../db.js';

export const data = new SlashCommandBuilder()
  .setName('shopinfo')
  .setDescription('Get information about a shop or list all shops')
  .addStringOption(option => option.setName('shop')
    .setDescription('The name or ID of a specific shop (leave empty to list all shops)'));

export async function execute(interaction) {
  const shopIdentifier = interaction.options.getString('shop');

  try {
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

  } catch (error) {
    console.error('Error getting shop info:', error);
    await interaction.reply({ content: 'An error occurred while retrieving shop information.', ephemeral: true });
  }
}
