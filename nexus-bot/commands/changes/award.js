import {
  SlashCommandBuilder, MessageFlags, PermissionFlagsBits,
} from 'discord.js';
import { getConfigValue } from '../../bot.js';
import {
  getChangeByThreadId, assignChangeReward,
} from '../../db.js';
import { sendRewardDm } from '../../rewards.js';
import { postRewardSummary } from '../../changes/rewards.js';

export const data = new SlashCommandBuilder()
  .setName('award')
  .setDescription('Reviewer/Moderator only - Manually assign a reward to an approved change.')
  .addNumberOption(option => option.setName('amount')
    .setDescription('Reward amount in PED')
    .setRequired(true)
    .setMinValue(0.01))
  .addStringOption(option => option.setName('note')
    .setDescription('Reason for the reward')
    .setRequired(false))
  .addNumberOption(option => option.setName('score')
    .setDescription('Contribution score (default: 0)')
    .setRequired(false)
    .setMinValue(0));

export async function execute(interaction) {
  const reviewerRoleId = getConfigValue('reviewerRoleId');
  const moderatorRoleId = getConfigValue('moderatorRoleId');

  const hasReviewerRole = reviewerRoleId && interaction.member.roles.cache.has(reviewerRoleId);
  const hasModeratorRole = moderatorRoleId && interaction.member.roles.cache.has(moderatorRoleId);
  const isAdmin = interaction.member.permissions.has(PermissionFlagsBits.Administrator);

  if (!hasReviewerRole && !hasModeratorRole && !isAdmin) {
    return interaction.reply({ content: 'You do not have permission to use this command.', flags: MessageFlags.Ephemeral });
  }

  const channelId = getConfigValue('pendingChangesChannelId');
  if (!channelId) {
    return interaction.reply({ content: 'The changes channel has not been set.', flags: MessageFlags.Ephemeral });
  }
  if (interaction.channel.parentId !== channelId || !interaction.channel.isThread()) {
    return interaction.reply({ content: `This command can only be used in a thread that is a child of <#${channelId}>.`, flags: MessageFlags.Ephemeral });
  }

  const change = await getChangeByThreadId(interaction.channel.id);
  if (!change) {
    return interaction.reply({ content: 'No change found for this thread.', flags: MessageFlags.Ephemeral });
  }

  if (change.state !== 'Approved') {
    return interaction.reply({ content: 'Rewards can only be assigned to approved changes.', flags: MessageFlags.Ephemeral });
  }

  const amount = Math.round((interaction.options.getNumber('amount') + Number.EPSILON) * 100) / 100;
  const note = interaction.options.getString('note') || 'Manual reward';
  const score = interaction.options.getNumber('score') || 0;

  const assigned = await assignChangeReward({
    change_id: change.id,
    user_id: change.author_id,
    rule_id: null,
    amount,
    contribution_score: score,
    assigned_by: interaction.user.id,
    note,
  });

  if (!assigned) {
    return interaction.reply({ content: 'Failed to assign the reward.', flags: MessageFlags.Ephemeral });
  }

  await sendRewardDm(interaction.client, change.author_id, {
    amount, contribution_score: score, note,
  });

  await interaction.reply({
    content: `Manual reward assigned: **${amount.toFixed(2)} PED**${score > 0 ? ` (+${score} score)` : ''} - ${note}`,
    flags: MessageFlags.Ephemeral,
  });

  // Update the public reward summary message
  await postRewardSummary(interaction.channel, change);
}
