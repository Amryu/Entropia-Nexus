import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags } from 'discord.js';
import { getConfigValue } from '../../bot.js';
import { getChangeByThreadId, setChangeDenied } from '../../db.js';
import { sendChangeDenialDm } from '../../rewards.js';
import { isAuthorizedReviewer, isDiscordAdmin } from '../../changes/rewards.js';

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
  .setDescription('Reviewer/Moderator only - Denies changes.')
  .addStringOption(option => option
    .setName('reason')
    .setDescription('Reason for denying the change')
    .setRequired(false)
    .setMaxLength(500));

export async function execute(interaction) {
  if (!isAuthorizedReviewer(interaction)) {
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

  if (!change) {
    return interaction.reply({ content: 'No change found for this thread.', flags: MessageFlags.Ephemeral });
  }

  if (change.state === 'Approved' || change.state === 'Denied') {
    return interaction.reply({ content: `This change has already been ${change.state.toLowerCase()}.`, flags: MessageFlags.Ephemeral });
  }

  if (change.author_id.toString() === interaction.user.id && !isDiscordAdmin(interaction)) {
    return interaction.reply({ content: 'You cannot deny your own changes.', flags: MessageFlags.Ephemeral });
  }

  const reason = interaction.options.getString('reason');

  await promptModeratorForConfirmation(interaction, reason, async () => {
    if (!(await setChangeDenied(change.id, reason))) {
      await thread.send('This change was already processed by another reviewer.');
      return false;
    }
    await thread.setName(`[Denied] ${change.type}: ${change.data.Name.substring(0, 80)}`);
    await thread.send(`The changes were denied!${reason ? ` Reason: ${reason}` : ''}`);
    await sendChangeDenialDm(interaction.client, change.author_id, {
      changeName: change.data.Name,
      changeType: change.type,
      entity: change.entity,
      reason,
    });
    await thread.setArchived(true);
    return true;
  });
}

async function promptModeratorForConfirmation(interaction, reason, onDeny) {
  const prompt = {
    content: `Are you sure you want to deny these changes?${reason ? `\nReason: ${reason}` : ''}`,
    components: [denyRow],
    flags: MessageFlags.Ephemeral,
  };

  await interaction.reply(prompt);

  const filter = i => (i.customId === 'yes' || i.customId === 'no') && i.user.id === interaction.user.id && isAuthorizedReviewer(i);
  const collector = interaction.channel.createMessageComponentCollector({ filter, time: 300_000 });

  collector.on('collect', async i => {
    if (i.customId === 'yes') {
      await i.update({ content: 'Denying changes...', components: [], flags: MessageFlags.Ephemeral });
      try {
        await onDeny();
      } catch (e) {
        console.error('[deny] Error during denial:', e);
        try {
          await interaction.channel.send('An error occurred during the denial process.');
        } catch {}
      }
      collector.stop();
    }
    else {
      await i.reply({ content: 'The denial was cancelled.', flags: MessageFlags.Ephemeral });
      collector.stop();
    }
  });
}
