import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags, PermissionFlagsBits } from 'discord.js';
import { getConfigValue } from '../../bot.js';
import { getChangeByThreadId, setChangeState } from '../../db.js';

const denyRow = new ActionRowBuilder()
  .addComponents(
    new ButtonBuilder()
      .setCustomId('yes')
      .setLabel('Yes')
      .setStyle(ButtonStyle.Danger),
    new ButtonBuilder()
      .setCustomId('no')
      .setLabel('No')
      .setStyle(ButtonStyle.Secondary),
  );

export const data = new SlashCommandBuilder()
  .setName('deny')
  .setDescription('Reviewer/Moderator only - Denies changes.');

export async function execute(interaction) {
  const reviewerRoleId = getConfigValue('reviewerRoleId');
  const moderatorRoleId = getConfigValue('moderatorRoleId');

  const hasReviewerRole = reviewerRoleId && interaction.member.roles.cache.has(reviewerRoleId);
  const hasModeratorRole = moderatorRoleId && interaction.member.roles.cache.has(moderatorRoleId);
  const isAdmin = interaction.member.permissions.has(PermissionFlagsBits.Administrator);

  if (!hasReviewerRole && !hasModeratorRole && !isAdmin) {
    return interaction.reply({ content: 'You do not have permission to use this command.', flags: MessageFlags.Ephemeral });
  }

  let channelId = getConfigValue('pendingChangesChannelId');
  if (!channelId) {
    return interaction.reply({ content: 'The changes channel has not been set.', flags: MessageFlags.Ephemeral });
  }
  if (interaction.channel.parentId !== channelId || !interaction.channel.isThread()) {
    return interaction.reply({ content: `This command can only be used in a thread that is a child of <#${channelId}>.`, flags: MessageFlags.Ephemeral });
  }

  let thread = interaction.channel;

  let change = await getChangeByThreadId(thread.id);

  if (change.state === 'Approved' || change.state === 'Denied') {
    return interaction.reply({ content: `This change has already been ${change.state.toLowerCase()}.`, flags: MessageFlags.Ephemeral });
  }

  await promptModeratorForConfirmation(interaction, async () => {
    await setChangeState(change.id, 'Denied');
    await thread.setName(`[Denied] ${change.type}: ${change.data.Name.substring(0, 80)}`);
    await thread.send('The changes were denied!');
    await thread.setArchived(true);
    return true;
  });
}

async function promptModeratorForConfirmation(interaction, onApprove) {
  const prompt = { content: `Are you sure you want to deny these changes?`, components: [denyRow], flags: MessageFlags.Ephemeral };
  
  await interaction.reply(prompt);

  const filter = _ => true;
  const collector = interaction.channel.createMessageComponentCollector({ filter, time: 0 });
  
  collector.on('collect', async i => {
    if (i.customId === 'yes') {
      i.update({ content: '...', flags: MessageFlags.Ephemeral });
      if (!(await onApprove())) {
        i.update({ content: 'The denial failed.', components: [], flags: MessageFlags.Ephemeral });
      }
      collector.stop();
    }
    else {
      i.reply('The denial was cancelled.', { flags: MessageFlags.Ephemeral });
      collector.stop();
    }
  });
}