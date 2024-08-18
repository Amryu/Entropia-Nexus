import { SlashCommandBuilder } from 'discord.js';
import { getTypeLink } from "../../util.js";

let items;

// Function to fetch all items and cache them
async function fetchItems() {
  const response = await fetch(`${process.env.API_URL}/items`);
  items = await response.json();
}

// Function to search for an item by name
async function getItemByName(name) {
  if (!items) {
    await fetchItems();
  }
  
  const lowercaseName = name.toLowerCase();
  const item = items.find(item => item.Name.toLowerCase() === lowercaseName);

  return item;
}

// Function to fetch the full item from the endpoint link
async function fetchFullItem(item) {
  const response = await fetch(process.env.API_URL+item.Links.$Url);
  const fullItem = await response.json();
  return fullItem;
}

export const data = new SlashCommandBuilder()
  .setName('item')
  .setDescription('Show info about an item.')
  .addStringOption(option => option.setName('name')
    .setDescription('The name of the item.')
    .setRequired(true));
export async function execute(interaction) {
  let item = await getItemByName(interaction.options.getString('name'));

  if (!item) {
    return interaction.reply('Item not found.');
  }

  let type = item.Properties.Type;

  fullItem = await fetchFullItem(item);

  const embed = {
    title: item.Name,
    url: `https://entropianexus.com${getTypeLink(item.Name, type)}`,
    fields: [
      {
        name: 'Type',
        value: type,
        inline: true
      },
      {
        name: 'Weight',
        value: item.Properties.Weight != null ? `${item.Properties.Weight}kg` : 'N/A',
        inline: true
      },
      {
        name: 'Value',
        value: item.Properties.Economy.Value != null ? `${item.Properties.Economy.Value} PED` : 'N/A',
        inline: true
      }
    ],
    image: {
      url: item.Image
    }
  };

  await interaction.reply({ embeds: [embed] });
}