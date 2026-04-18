/**
 * Shared reward evaluation and prompting logic.
 * Used by both /approve (thread-based review) and Direct Apply.
 *
 * Reward prompts are ephemeral (only visible to the approver).
 * A single public summary message is posted after all rewards are addressed.
 */
import {
  ActionRowBuilder, ButtonBuilder, ButtonStyle,
  MessageFlags, ModalBuilder, TextInputBuilder, TextInputStyle,
  PermissionFlagsBits,
} from 'discord.js';
import { getConfigValue } from '../bot.js';
import {
  getMatchingRewardRules, assignChangeReward,
  setRewardSummaryMessageId, getRewardsForChange,
} from '../db.js';
import { compareJson, validate } from '../change.js';
import { sendChangeApprovalDm } from '../rewards.js';

/** Check if a button interaction is from an authorized reviewer/moderator/admin. */
export function isAuthorizedReviewer(interaction) {
  const reviewerRoleId = getConfigValue('reviewerRoleId');
  const moderatorRoleId = getConfigValue('moderatorRoleId');
  const hasReviewer = reviewerRoleId && interaction.member?.roles?.cache?.has(reviewerRoleId);
  const hasModerator = moderatorRoleId && interaction.member?.roles?.cache?.has(moderatorRoleId);
  const isAdmin = interaction.member?.permissions?.has(PermissionFlagsBits.Administrator);
  return hasReviewer || hasModerator || isAdmin;
}

/** Check if the interaction user has Discord Administrator permission. */
export function isDiscordAdmin(interaction) {
  return !!interaction.member?.permissions?.has(PermissionFlagsBits.Administrator);
}

// ─── Entity API helpers ─────────────────────────────────────────────────────

export function getEntityApiCollection(entityType) {
  switch (entityType) {
    case 'TeleportChip':
    case 'TeleportationChip':
      return 'teleportationchips';
    case 'CreatureControlCapsule':
    case 'Capsule':
      return 'capsules';
    case 'Fish':
      return 'fishes';
    default:
      return `${entityType.toLowerCase()}s`;
  }
}

export async function fetchEntityForReward(change) {
  if (!change?.data || change.type !== 'Update') return null;

  const rawChangeId = change.data.Id;
  if (!Number.isFinite(Number(rawChangeId))) return null;

  const apartmentId = change.entity === 'Apartment'
    ? (Number(rawChangeId) > 300000 ? Number(rawChangeId) - 300000 : Number(rawChangeId))
    : Number(rawChangeId);
  const fetchId = change.entity === 'Apartment' ? apartmentId : rawChangeId;

  const fetchUrl = `${process.env.API_URL}/${getEntityApiCollection(change.entity)}/${fetchId}`;
  return fetch(fetchUrl)
    .then(res => res.status === 404 ? Promise.resolve({}) : res.json())
    .catch(_ => null);
}

// ─── Change diff helpers ────────────────────────────────────────────────────

export async function getChangedDataKeys(change, preChangeEntity = null) {
  if (!change?.data) return [];
  if (change.type === 'Create') return Object.keys(change.data);
  if (change.type !== 'Update') return [];

  const entity = preChangeEntity ?? await fetchEntityForReward(change);
  if (!entity) return [];

  const validatedEntity = JSON.parse(JSON.stringify(entity));
  const validatedChange = JSON.parse(JSON.stringify(change.data));

  validate(change.entity, validatedEntity);
  validate(change.entity, validatedChange);

  const diff = compareJson(validatedEntity, validatedChange);
  if (!diff || Array.isArray(diff)) return [];

  return extractChangedTopLevelKeys(diff);
}

function extractChangedTopLevelKeys(diffObject) {
  return Object.entries(diffObject)
    .filter(([key, value]) => key !== '_status' && isDiffNodeChanged(value))
    .map(([key]) => key);
}

function isDiffNodeChanged(node) {
  if (Array.isArray(node)) return node.length > 0;
  if (!node || typeof node !== 'object') return false;
  if (node._changed === true || node._status) return true;
  return Object.entries(node)
    .some(([key, value]) => !key.startsWith('_') && isDiffNodeChanged(value));
}

// ─── PED formatting ─────────────────────────────────────────────────────────

export function roundPed(amount) {
  return Math.round((amount + Number.EPSILON) * 100) / 100;
}

export function formatPed(amount) {
  return roundPed(amount).toFixed(2);
}

function lerpPed(min, max, t) {
  return roundPed(min + (max - min) * t);
}

// ─── Reward summary ─────────────────────────────────────────────────────────

function buildRewardSummaryContent(rewards) {
  if (!rewards.length) return null;
  const totalPed = roundPed(rewards.reduce((sum, r) => sum + parseFloat(r.amount), 0));
  const totalScore = rewards.reduce((sum, r) => sum + parseFloat(r.contribution_score || 0), 0);
  let text = `**Rewards:** ${formatPed(totalPed)} PED`;
  if (totalScore > 0) text += ` (+${totalScore} score)`;
  return text;
}

/**
 * Post or update the public reward summary message in a thread.
 */
export async function postRewardSummary(thread, change) {
  const rewards = await getRewardsForChange(change.id);
  const content = buildRewardSummaryContent(rewards);
  if (!content) return;

  // Try to update existing summary message
  if (change.reward_summary_message_id) {
    try {
      const msg = await thread.messages.fetch(change.reward_summary_message_id);
      await msg.edit(content);
      return;
    } catch {
      // Message deleted or not found, post a new one
    }
  }

  // Post new summary
  const msg = await thread.send(content);
  await setRewardSummaryMessageId(change.id, msg.id);
}

// ─── Reward evaluation & prompting ──────────────────────────────────────────

/**
 * Evaluate matching reward rules and prompt the approver ephemerally.
 * Posts a single public summary after all prompts are resolved.
 *
 * @param {object} approverInteraction - The interaction of the reviewer who approved
 *   (used to send ephemeral follow-ups)
 * @returns {boolean} true if rewards were found (caller should wait for summary)
 */
export async function handleReward(client, thread, change, approverInteraction, preChangeEntity = null) {
  try {
    const changedKeys = await getChangedDataKeys(change, preChangeEntity);
    if (change.type === 'Update' && changedKeys.length === 0) {
      return false;
    }

    const subType = change.data?.Properties?.Type || null;
    const rules = await getMatchingRewardRules(change.entity, change.type, changedKeys, subType);
    if (!rules.length) return false;

    const promptRules = [];

    for (const rule of rules) {
      const minAmount = parseFloat(rule.min_amount);
      const maxAmount = parseFloat(rule.max_amount);

      promptRules.push({
        rule,
        minAmount,
        maxAmount,
        isFixed: minAmount === maxAmount,
      });
    }

    if (!promptRules.length) return false;

    const rewardResults = [];
    let pendingPrompts = promptRules.length;
    const onPromptDone = async () => {
      pendingPrompts -= 1;
      if (pendingPrompts > 0) return;

      // Post public summary
      try {
        await postRewardSummary(thread, change);
      } catch (e) {
        console.error('[rewards] Failed to post reward summary:', e);
      }

      // Send combined approval+rewards DM
      try {
        await sendChangeApprovalDm(client, change.author_id, {
          changeName: change.data.Name,
          changeType: change.type,
          entity: change.entity,
          rewards: rewardResults,
        });
      } catch (e) {
        console.error('[rewards] Failed to send approval DM:', e);
      }
      try {
        await thread.setArchived(true);
      } catch {}
    };

    // Process prompts sequentially so the approver addresses one at a time
    for (const { rule, minAmount, maxAmount, isFixed } of promptRules) {
      if (isFixed) {
        await promptFixedReward({
          approverInteraction,
          thread,
          change,
          rule,
          amount: minAmount,
          rewardResults,
        });
      } else {
        await promptRangeReward({
          approverInteraction,
          thread,
          change,
          rule,
          minAmount,
          maxAmount,
          rewardResults,
        });
      }
      await onPromptDone();
    }

    return true;
  } catch (e) {
    console.error('[rewards] Reward assignment failed:', e);
    return false;
  }
}

// ─── Ephemeral reward prompts ───────────────────────────────────────────────

function promptFixedReward({ approverInteraction, thread, change, rule, amount, rewardResults }) {
  return new Promise(async (resolve) => {
    const approveButtonId = `reward_fixed_approve_${change.id}_${rule.id}`;
    const skipButtonId = `reward_fixed_skip_${change.id}_${rule.id}`;
    const actionsRow = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(approveButtonId)
        .setLabel(`Approve ${formatPed(amount)} PED`)
        .setStyle(ButtonStyle.Success),
      new ButtonBuilder()
        .setCustomId(skipButtonId)
        .setLabel('Skip')
        .setStyle(ButtonStyle.Danger),
    );

    const msg = await approverInteraction.followUp({
      content: `Matching rule: **${rule.name}** (${formatPed(amount)} PED fixed)\nApprove this reward or skip this rule.`,
      components: [actionsRow],
      flags: MessageFlags.Ephemeral,
    });

    const collector = msg.createMessageComponentCollector({ time: 300_000 });

    collector.on('collect', async (btnInteraction) => {
      try {
        const customId = btnInteraction.customId;

        if (customId === skipButtonId) {
          await btnInteraction.update({
            content: `Reward skipped for rule: **${rule.name}**`,
            components: [],
          });
          collector.stop('skipped');
          return;
        }

        if (customId !== approveButtonId) {
          await btnInteraction.reply({
            content: 'Unknown reward action.',
            flags: MessageFlags.Ephemeral,
          });
          return;
        }

        const assigned = await assignChangeReward({
          change_id: change.id,
          user_id: change.author_id,
          rule_id: rule.id,
          amount: roundPed(amount),
          contribution_score: rule.contribution_score,
          assigned_by: btnInteraction.user.id,
          note: `Assigned on approval (${rule.name})`,
        });

        if (!assigned) {
          await btnInteraction.update({
            content: `A reward for **${rule.name}** is already assigned for this change.`,
            components: [],
          });
          collector.stop('duplicate');
          return;
        }

        rewardResults.push({
          amount: roundPed(amount), contribution_score: rule.contribution_score,
          note: `Assigned on approval (${rule.name})`,
        });
        await btnInteraction.update({
          content: `Reward assigned: **${formatPed(amount)} PED** (${rule.name})`,
          components: [],
        });
        collector.stop('assigned');
      } catch (e) {
        console.error('[rewards] Fixed reward prompt interaction failed:', e);
        try {
          if (!btnInteraction.replied && !btnInteraction.deferred) {
            await btnInteraction.reply({
              content: 'Failed to assign reward. Please try again.',
              flags: MessageFlags.Ephemeral,
            });
          }
        } catch {}
      }
    });

    collector.on('end', () => resolve());
  });
}

function promptRangeReward({ approverInteraction, thread, change, rule, minAmount, maxAmount, rewardResults }) {
  return new Promise(async (resolve) => {
    const presets = [
      { key: '0', label: 'Minimum', t: 0 },
      { key: '25', label: 'Low', t: 0.25 },
      { key: '50', label: 'Middle', t: 0.5 },
      { key: '75', label: 'High', t: 0.75 },
      { key: '100', label: 'Max', t: 1 },
    ];
    const presetAmounts = new Map(presets.map(p => [p.key, lerpPed(minAmount, maxAmount, p.t)]));

    const presetRow = new ActionRowBuilder().addComponents(
      ...presets.map((p) =>
        new ButtonBuilder()
          .setCustomId(`reward_pick_${change.id}_${rule.id}_${p.key}`)
          .setLabel(`${p.label} ${formatPed(presetAmounts.get(p.key))}`)
          .setStyle(ButtonStyle.Secondary)
      )
    );
    const actionsRow = new ActionRowBuilder().addComponents(
      new ButtonBuilder()
        .setCustomId(`reward_custom_${change.id}_${rule.id}`)
        .setLabel('Custom Amount')
        .setStyle(ButtonStyle.Primary),
      new ButtonBuilder()
        .setCustomId(`reward_skip_${change.id}_${rule.id}`)
        .setLabel('Skip')
        .setStyle(ButtonStyle.Danger),
    );

    const msg = await approverInteraction.followUp({
      content: `Matching rule: **${rule.name}** (${formatPed(minAmount)}-${formatPed(maxAmount)} PED)\nChoose an amount, set a custom value, or skip this rule.`,
      components: [presetRow, actionsRow],
      flags: MessageFlags.Ephemeral,
    });

    const collector = msg.createMessageComponentCollector({ time: 300_000 });
    const customButtonId = `reward_custom_${change.id}_${rule.id}`;
    const skipButtonId = `reward_skip_${change.id}_${rule.id}`;
    const modalId = `reward_modal_${change.id}_${rule.id}`;

    collector.on('collect', async (btnInteraction) => {
      try {
        const customId = btnInteraction.customId;

        if (customId === skipButtonId) {
          await btnInteraction.update({
            content: `Reward skipped for rule: **${rule.name}**`,
            components: [],
          });
          collector.stop('skipped');
          return;
        }

        if (customId === customButtonId) {
          const modal = new ModalBuilder()
            .setCustomId(modalId)
            .setTitle('Assign Reward');
          const amountInput = new TextInputBuilder()
            .setCustomId('amount')
            .setLabel(`Amount (${formatPed(minAmount)}-${formatPed(maxAmount)} PED)`)
            .setStyle(TextInputStyle.Short)
            .setRequired(true)
            .setPlaceholder(formatPed(minAmount));
          modal.addComponents(new ActionRowBuilder().addComponents(amountInput));
          await btnInteraction.showModal(modal);

          try {
            const modalSubmit = await btnInteraction.awaitModalSubmit({
              time: 120_000,
              filter: (x) => x.customId === modalId && x.user.id === btnInteraction.user.id,
            });
            const amount = parseFloat(modalSubmit.fields.getTextInputValue('amount'));
            if (isNaN(amount) || amount < minAmount || amount > maxAmount) {
              await modalSubmit.reply({
                content: `Invalid amount. Must be between ${formatPed(minAmount)} and ${formatPed(maxAmount)} PED.`,
                flags: MessageFlags.Ephemeral,
              });
              return;
            }

            const assigned = await assignChangeReward({
              change_id: change.id,
              user_id: change.author_id,
              rule_id: rule.id,
              amount: roundPed(amount),
              contribution_score: rule.contribution_score,
              assigned_by: modalSubmit.user.id,
              note: `Assigned on approval (${rule.name})`,
            });

            if (!assigned) {
              await modalSubmit.reply({
                content: `A reward for **${rule.name}** is already assigned for this change.`,
                flags: MessageFlags.Ephemeral,
              });
              collector.stop('duplicate');
              return;
            }

            rewardResults.push({
              amount: roundPed(amount), contribution_score: rule.contribution_score,
              note: `Assigned on approval (${rule.name})`,
            });
            await modalSubmit.reply({
              content: `Reward assigned: **${formatPed(amount)} PED** (${rule.name})`,
              flags: MessageFlags.Ephemeral,
            });
            collector.stop('assigned');
          } catch {
            // Modal timed out
          }
          return;
        }

        const amountStep = customId.split('_').at(-1);
        const amount = presetAmounts.get(amountStep);
        if (amount == null) {
          await btnInteraction.reply({ content: 'Unknown reward amount preset.', flags: MessageFlags.Ephemeral });
          return;
        }

        const assigned = await assignChangeReward({
          change_id: change.id,
          user_id: change.author_id,
          rule_id: rule.id,
          amount,
          contribution_score: rule.contribution_score,
          assigned_by: btnInteraction.user.id,
          note: `Assigned on approval (${rule.name})`,
        });

        if (!assigned) {
          await btnInteraction.update({
            content: `A reward for **${rule.name}** is already assigned for this change.`,
            components: [],
          });
          collector.stop('duplicate');
          return;
        }

        rewardResults.push({
          amount, contribution_score: rule.contribution_score,
          note: `Assigned on approval (${rule.name})`,
        });
        await btnInteraction.update({
          content: `Reward assigned: **${formatPed(amount)} PED** (${rule.name})`,
          components: [],
        });
        collector.stop('assigned');
      } catch (e) {
        console.error('[rewards] Reward prompt interaction failed:', e);
        try {
          if (!btnInteraction.replied && !btnInteraction.deferred) {
            await btnInteraction.reply({
              content: 'Failed to assign reward. Please try again.',
              flags: MessageFlags.Ephemeral,
            });
          }
        } catch {}
      }
    });

    collector.on('end', () => resolve());
  });
}
