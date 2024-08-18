import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';
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
  .setDescription('Moderator only - Approves changes.')
  .addBooleanOption(option => option.setName('force')
    .setDescription('Force approve the changes.')
    .setRequired(false));

export async function execute(interaction) {
  let moderatorRoleId = getConfigValue('moderatorRoleId');
  if (!moderatorRoleId) {
    return interaction.reply({ content: 'The moderator role has not been set.', ephemeral: true });
  }
  if (!interaction.member.roles.cache.has(moderatorRoleId) && !interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply({ content: 'You do not have permission to use this command.', ephemeral: true });
  }

  let channelId = getConfigValue('pendingChangesChannelId');
  if (!channelId) {
    return interaction.reply({ content: 'The changes channel has not been set.', ephemeral: true });
  }
  if (interaction.channel.parentId !== channelId || !interaction.channel.isThread()) {
    return interaction.reply({ content: `This command can only be used in a thread that is a child of <#${channelId}>.`, ephemeral: true });
  }

  let thread = interaction.channel;

  let change = await getChangeByThreadId(thread.id);

  if (change.state === 'Approved' || change.state === 'Denied') {
    return interaction.reply({ content: `This change has already been ${change.state.toLowerCase()}.`, ephemeral: true });
  }

  let userChange = await getUserById(change.author_id);

  if (!userChange.verified) {
    return interaction.reply({ content: 'This user is not verified.', ephemeral: true });
  }
  if (!userChange.eu_name) {
    return interaction.reply({ content: 'The user has not yet set his EU name.', ephemeral: true });
  }

  if (change.state === 'Draft' && !interaction.options.getBoolean('force')) {
    return interaction.reply({ content: 'This change is still a draft. Use /approve force to approve it anyways.', ephemeral: true });
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
  const prompt = { content: `Are you sure you want to approve these changes? Make sure there is sufficient proof!`, components: [approveRow], ephemeral: true };
  
  await interaction.reply(prompt);

  const filter = _ => true;
  const collector = interaction.channel.createMessageComponentCollector({ filter, time: 0 });
  
  collector.on('collect', async i => {
    if (i.customId === 'yes') {
      i.update({ content: '...', components: [], ephemeral: true });
      await onApprove();
      collector.stop();
    }
    else {
      i.reply('The approval was cancelled.', { ephemeral: true });
      collector.stop();
    }
  });
}