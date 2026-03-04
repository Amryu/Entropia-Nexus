import {
  SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle,
  MessageFlags, PermissionFlagsBits, ModalBuilder, TextInputBuilder,
  TextInputStyle,
} from 'discord.js';
import { getConfigValue } from '../../bot.js';
import {
  getUserById, getChangeByThreadId, setChangeState,
  getMatchingRewardRules, assignChangeReward,
} from '../../db.js';
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

    // Evaluate reward rules and auto-assign or prompt
    const archived = await handleReward(interaction, thread, change);
    if (!archived) {
      await thread.setArchived(true);
    }
    return true;
  });
}

/**
 * Evaluate matching reward rules and handle assignment.
 * Returns true if the thread will be archived by this function (deferred archive).
 */
async function handleReward(interaction, thread, change) {
  try {
    const dataKeys = change.data ? Object.keys(change.data) : [];
    const rules = await getMatchingRewardRules(change.entity, change.type, dataKeys);

    if (rules.length !== 1) return false; // 0 or 2+ matches — skip

    const rule = rules[0];
    const minAmount = parseFloat(rule.min_amount);
    const maxAmount = parseFloat(rule.max_amount);

    if (minAmount === maxAmount) {
      // Fixed amount — auto-assign immediately
      await assignChangeReward({
        change_id: change.id,
        user_id: change.author_id,
        rule_id: rule.id,
        amount: minAmount,
        contribution_score: rule.contribution_score,
        assigned_by: interaction.user.id,
      });
      await thread.send(
        `Reward auto-assigned: **${minAmount} PED** (${rule.name})`
      );
      return false;
    }

    // Range — prompt approver with button → modal
    const promptRow = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`reward_prompt_${change.id}`)
        .setLabel(`Assign Reward (${minAmount}\u2013${maxAmount} PED)`)
        .setStyle(ButtonStyle.Primary),
    );
    const msg = await thread.send({
      content: `Matching rule: **${rule.name}** (${minAmount}\u2013${maxAmount} PED)\nClick to assign reward amount:`,
      components: [promptRow],
    });

    const collector = msg.createMessageComponentCollector({ time: 300_000 });

    collector.on('collect', async (btnInteraction) => {
      const modal = new ModalBuilder()
        .setCustomId(`reward_modal_${change.id}`)
        .setTitle('Assign Reward');
      const amountInput = new TextInputBuilder()
        .setCustomId('amount')
        .setLabel(`Amount (${minAmount}\u2013${maxAmount} PED)`)
        .setStyle(TextInputStyle.Short)
        .setRequired(true)
        .setPlaceholder(String(minAmount));
      modal.addComponents(
        new ActionRowBuilder().addComponents(amountInput)
      );
      await btnInteraction.showModal(modal);

      try {
        const modalSubmit = await btnInteraction.awaitModalSubmit({
          time: 120_000,
        });
        const amount = parseFloat(
          modalSubmit.fields.getTextInputValue('amount')
        );
        if (isNaN(amount) || amount < minAmount || amount > maxAmount) {
          await modalSubmit.reply({
            content: `Invalid amount. Must be between ${minAmount} and ${maxAmount}.`,
            flags: MessageFlags.Ephemeral,
          });
          return;
        }
        await assignChangeReward({
          change_id: change.id,
          user_id: change.author_id,
          rule_id: rule.id,
          amount,
          contribution_score: rule.contribution_score,
          assigned_by: btnInteraction.user.id,
        });
        await modalSubmit.reply(
          `Reward assigned: **${amount} PED** (${rule.name})`
        );
        collector.stop();
      } catch {
        // Modal timed out
      }
    });

    // Archive thread when collector ends (reward assigned or timed out)
    collector.on('end', async () => {
      try {
        await msg.edit({ components: [] });
      } catch {}
      try {
        await thread.setArchived(true);
      } catch {}
    });

    return true; // Thread will be archived by collector
  } catch (e) {
    console.error('[approve] Reward assignment failed:', e);
    return false;
  }
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
