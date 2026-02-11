import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags } from 'discord.js';
import { getConfigValue } from '../../bot.js';
import { getUserById, getChangeByThreadId, setChangeState } from '../../db.js';
import { applyChange } from '../../changes/util.js';

const approveRow = new ActionRowBuilder()
  .addComponents(
    new ButtonBuilder()
      .setCustomId('yes')
      .setLabel('Yes')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId('no')
      .setLabel('No')
      .setStyle(ButtonStyle.Danger),
  );

export const data = new SlashCommandBuilder()
  .setName('approve')
  .setDescription('Reviewer/Moderator only - Approves changes.')
  .addBooleanOption(option => option.setName('force')
    .setDescription('Force approve the changes.')
    .setRequired(false));

export async function execute(interaction) {
  const reviewerRoleId = getConfigValue('reviewerRoleId');
  const moderatorRoleId = getConfigValue('moderatorRoleId');

  const hasReviewerRole = reviewerRoleId && interaction.member.roles.cache.has(reviewerRoleId);
  const hasModeratorRole = moderatorRoleId && interaction.member.roles.cache.has(moderatorRoleId);
  const isAdmin = interaction.member.permissions.has('ADMINISTRATOR');

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

  let userChange = await getUserById(change.author_id);

  if (!userChange.verified) {
    return interaction.reply({ content: 'This user is not verified.', flags: MessageFlags.Ephemeral });
  }
  if (!userChange.eu_name) {
    return interaction.reply({ content: 'The user has not yet set his EU name.', flags: MessageFlags.Ephemeral });
  }

  if (change.state === 'Draft' && !interaction.options.getBoolean('force')) {
    return interaction.reply({ content: 'This change is still a draft. Use /approve force to approve it anyways.', flags: MessageFlags.Ephemeral });
  }

  await promptModeratorForConfirmation(interaction, async () => {
    if (!(await applyChange(change))) {
      await thread.send('An error occurred while applying the changes. Please try again later.');
      return false;
    }

    await setChangeState(change.id, 'Approved');
    await thread.setName(`[Approved] ${change.type}: ${change.data.Name.substring(0, 80)}`);
    await thread.send('The changes were approved!');
    await thread.setArchived(true);
    return true;
  });
}

async function promptModeratorForConfirmation(interaction, onApprove) {
  const prompt = { content: `Are you sure you want to approve these changes? Make sure there is sufficient proof!`, components: [approveRow], flags: MessageFlags.Ephemeral };
  
  await interaction.reply(prompt);

  const filter = _ => true;
  const collector = interaction.channel.createMessageComponentCollector({ filter, time: 0 });
  
  collector.on('collect', async i => {
    if (i.customId === 'yes') {
      i.update({ content: '...', components: [], flags: MessageFlags.Ephemeral });
      await onApprove();
      collector.stop();
    }
    else {
      i.reply('The approval was cancelled.', { flags: MessageFlags.Ephemeral });
      collector.stop();
    }
  });
}