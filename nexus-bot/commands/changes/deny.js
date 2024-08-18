import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';
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
  .setDescription('Moderator only - Denies changes.');

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

  await promptModeratorForConfirmation(interaction, async () => {
    await setChangeState(change.id, 'Denied');
    await thread.setName(`[Denied] ${change.type}: ${change.data.Name.substring(0, 80)}`);
    await thread.send('The changes were denied!');
    await thread.setArchived(true);
    return true;
  });
}

async function promptModeratorForConfirmation(interaction, onApprove) {
  const prompt = { content: `Are you sure you want to deny these changes?`, components: [denyRow], ephemeral: true };
  
  await interaction.reply(prompt);

  const filter = _ => true;
  const collector = interaction.channel.createMessageComponentCollector({ filter, time: 0 });
  
  collector.on('collect', async i => {
    if (i.customId === 'yes') {
      i.update({ content: '...', ephemeral: true });
      if (!(await onApprove())) {
        i.update({ content: 'The denial failed.', components: [], ephemeral: true });
      }
      collector.stop();
    }
    else {
      i.reply('The denial was cancelled.', { ephemeral: true });
      collector.stop();
    }
  });
}