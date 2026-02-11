import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags } from 'discord.js';
import { getUsers, getUserById, setUserEuName, createUser } from '../../db.js';
import { getConfigValue, notifyModerators } from '../../bot.js';
import { startVerification } from './verifyUser.js';

const confirmRow = new ActionRowBuilder()
  .addComponents(
    new ButtonBuilder()
      .setCustomId('euname_yes')
      .setLabel('Yes')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId('euname_no')
      .setLabel('No')
      .setStyle(ButtonStyle.Danger),
  );

export const data = new SlashCommandBuilder()
  .setName('seteuname')
  .setDescription('Set your Entropia Universe name for verification.')
  .addUserOption(option =>
    option.setName('user')
      .setDescription('Set the name for another user (moderator only)'));

export async function execute(interaction) {
  try {
    const channelId = getConfigValue('verifiedChannelId');
    if (!channelId) {
      return interaction.reply({ content: 'The verified channel has not been set.', flags: MessageFlags.Ephemeral });
    }
    if (interaction.channel.parentId !== channelId || !interaction.channel.isThread()) {
      return interaction.reply({ content: `This command can only be used in a thread that is a child of <#${channelId}>.`, flags: MessageFlags.Ephemeral });
    }

    const targetDiscordUser = interaction.options.getUser('user');
    const moderatorRoleId = getConfigValue('moderatorRoleId');
    const isModerator = moderatorRoleId && (
      interaction.member.roles.cache.has(moderatorRoleId) ||
      interaction.member.permissions.has('ADMINISTRATOR')
    );
    const isOverride = !!targetDiscordUser;

    if (isOverride && !isModerator) {
      return interaction.reply({ content: 'Only moderators can set another user\'s name.', flags: MessageFlags.Ephemeral });
    }

    const targetId = isOverride ? targetDiscordUser.id : interaction.user.id;
    let user = await getUserById(targetId);

    if (!user) {
      if (isOverride) {
        return interaction.reply({ content: `<@${targetId}> is not registered. They need to interact with the bot first.`, flags: MessageFlags.Ephemeral });
      }
      user = await createUser(interaction.user);
      if (!user) {
        return interaction.reply({ content: 'An error occurred while creating your account. Please try again later.', flags: MessageFlags.Ephemeral });
      }
    }

    if (user.verified && !isOverride) {
      return interaction.reply({
        content: 'You have already verified your account. Name changes are typically not possible in Entropia Universe, so we do not allow them here either. If there are special circumstances, please contact a moderator with evidence.',
        flags: MessageFlags.Ephemeral
      });
    }

    const prompt = isOverride
      ? `Type the Entropia Universe name for <@${targetId}> below.`
      : 'Type your Entropia Universe name below.';

    await interaction.reply(prompt);

    collectEuName(interaction.channel, targetId, {
      typerId: interaction.user.id,
      isOverride,
      guild: interaction.guild,
    });

  } catch (error) {
    console.error('Error in seteuname:', error);
    await notifyModerators({
      title: 'Set EU Name Error',
      error,
      context: `user=${interaction.user?.tag || interaction.user?.id}`
    });
    if (!interaction.replied && !interaction.deferred) {
      await interaction.reply({ content: 'An error occurred. Please try again later.', flags: MessageFlags.Ephemeral }).catch(() => {});
    }
  }
}

/**
 * Start collecting an EU name from a user in a channel/thread.
 * After the name is confirmed, automatically starts the verification flow (unless isOverride).
 *
 * @param {import('discord.js').TextChannel} channel - The channel/thread to collect in
 * @param {string} targetId - The user ID whose EU name is being set
 * @param {object} options
 * @param {string} [options.typerId] - The user ID who will type the name (defaults to targetId)
 * @param {boolean} [options.isOverride=false] - Whether a moderator is setting someone else's name
 * @param {import('discord.js').Guild} options.guild - The guild
 * @param {function} [options.onEnd] - Called when the entire flow (name + verification) ends
 */
export function collectEuName(channel, targetId, { typerId, isOverride = false, guild, onEnd }) {
  const invokerId = typerId || targetId;
  let confirmMsg = null;
  let btnCollector = null;
  let settled = false;

  const msgCollector = channel.createMessageCollector({
    filter: m => m.author.id === invokerId,
  });

  msgCollector.on('collect', async (msg) => {
    const euName = msg.content.trim();
    if (!euName || euName.length > 100) return;

    // Stop previous button collector — user typed a new name
    if (btnCollector) btnCollector.stop('superseded');

    const content = `You entered: **${euName}**\n\nMake sure the capitalization and spacing exactly matches the in-game name. Is this correct?`;

    if (confirmMsg) {
      await confirmMsg.edit({ content, components: [confirmRow] });
    } else {
      confirmMsg = await channel.send({ content, components: [confirmRow] });
    }

    btnCollector = confirmMsg.createMessageComponentCollector({
      filter: i => i.user.id === invokerId,
    });

    btnCollector.on('collect', async (i) => {
      if (i.customId === 'euname_yes') {
        settled = true;
        btnCollector.stop('confirmed');
        msgCollector.stop('confirmed');

        const users = await getUsers();
        const duplicate = users.find(u =>
          u.eu_name?.toLowerCase() === euName.toLowerCase() && u.id !== targetId
        );
        if (duplicate) {
          await i.update({
            content: 'This Entropia Universe name is already in use by another account. Contact a moderator if you believe this is an error.',
            components: []
          });
          onEnd?.();
          return;
        }

        await setUserEuName(targetId, euName);

        if (isOverride) {
          await i.update({
            content: `The EU name for <@${targetId}> has been set to **${euName}**.`,
            components: []
          });
          onEnd?.();
        } else {
          await i.update({
            content: `Your EU name has been set to **${euName}**. Verification will begin shortly.`,
            components: []
          });
          // Auto-chain into verification — onEnd is passed through
          await startVerification(channel, targetId, guild, { onEnd });
        }
      } else if (i.customId === 'euname_no') {
        btnCollector.stop('retry');
        await i.update({
          content: 'Type your name again below.',
          components: []
        });
        // msgCollector is still running — user just types a new name
      }
    });

    btnCollector.on('end', () => {
      if (confirmMsg) confirmMsg.edit({ components: [] }).catch(() => {});
    });
  });

  msgCollector.on('end', () => {
    if (settled) return;
    settled = true;
    if (btnCollector) btnCollector.stop('done');
    if (confirmMsg) {
      confirmMsg.edit({ components: [] }).catch(() => {});
    }
    onEnd?.();
  });
}
