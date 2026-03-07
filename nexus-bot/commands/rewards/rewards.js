import { SlashCommandBuilder, MessageFlags } from 'discord.js';
import { getContributorBalance, getRewardDmEnabled, setRewardDmEnabled } from '../../db.js';
import { formatBalance } from '../../rewards.js';

export const data = new SlashCommandBuilder()
  .setName('rewards')
  .setDescription('View your contributor reward balance or manage notifications.')
  .addSubcommand(sub => sub
    .setName('balance')
    .setDescription('View your current contributor reward balance.'))
  .addSubcommand(sub => sub
    .setName('notifications')
    .setDescription('Toggle reward DM notifications on or off.')
    .addBooleanOption(option => option
      .setName('enabled')
      .setDescription('Enable or disable reward DM notifications')
      .setRequired(true)));

export async function execute(interaction) {
  const sub = interaction.options.getSubcommand();

  if (sub === 'balance') {
    const balance = await getContributorBalance(interaction.user.id);
    if (balance.total_earned === 0 && balance.total_paid === 0) {
      return interaction.reply({ content: 'You have no contributor rewards yet.', flags: MessageFlags.Ephemeral });
    }
    return interaction.reply({ content: `Your balance: ${formatBalance(balance)}`, flags: MessageFlags.Ephemeral });
  }

  if (sub === 'notifications') {
    const enabled = interaction.options.getBoolean('enabled');
    await setRewardDmEnabled(interaction.user.id, enabled);
    return interaction.reply({
      content: enabled
        ? 'Reward DM notifications **enabled**. You will receive a DM when you are awarded a reward.'
        : 'Reward DM notifications **disabled**. You will no longer receive DMs for rewards. You can still check your balance anytime with `/rewards balance` in the server.',
      flags: MessageFlags.Ephemeral,
    });
  }
}
