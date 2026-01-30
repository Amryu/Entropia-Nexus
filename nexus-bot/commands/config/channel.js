import { SlashCommandBuilder } from 'discord.js';
import { setConfigValue } from "../../bot.js";

export const data = new SlashCommandBuilder()
  .setName('channel')
  .setDescription('Manage bot channel settings')
  .addSubcommand(subcommand =>
    subcommand
      .setName('set')
      .setDescription('Set a channel for a specific purpose')
      .addStringOption(option =>
        option
          .setName('type')
          .setDescription('The type of channel to set')
          .setRequired(true)
          .addChoices(
            { name: 'Verified', value: 'verified' },
            { name: 'Pending Changes', value: 'pending-changes' },
            { name: 'Archived Changes', value: 'archived-changes' },
            { name: 'Flights', value: 'flights' },
            { name: 'Services', value: 'services' }
          ))
      .addChannelOption(option =>
        option
          .setName('channel')
          .setDescription('The channel to set')
          .setRequired(true)));

export async function execute(interaction) {
  if (!interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply({ content: 'You do not have permission to use this command.', ephemeral: true });
  }

  const subcommand = interaction.options.getSubcommand();

  if (subcommand === 'set') {
    const type = interaction.options.getString('type');
    const channel = interaction.options.getChannel('channel');

    if (!channel) {
      return interaction.reply({ content: 'Please provide a channel.', ephemeral: true });
    }

    // Map type to config key
    const configKeyMap = {
      'verified': 'verifiedChannelId',
      'pending-changes': 'pendingChangesChannelId',
      'archived-changes': 'archivedChangesChannelId',
      'flights': 'flightsChannelId',
      'services': 'servicesChannelId'
    };

    const configKey = configKeyMap[type];
    if (!configKey) {
      return interaction.reply({ content: 'Invalid channel type.', ephemeral: true });
    }

    setConfigValue(configKey, channel.id);

    // Create friendly name for response
    const typeNames = {
      'verified': 'Verified',
      'pending-changes': 'Pending Changes',
      'archived-changes': 'Archived Changes',
      'flights': 'Flights',
      'services': 'Services'
    };

    await interaction.reply(`${typeNames[type]} channel set to <#${channel.id}>.`);
  }
}
