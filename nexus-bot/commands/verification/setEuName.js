import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags } from 'discord.js';
import { getUsers, getUserById, setUserEuName, createUser } from '../../db.js';
import { getConfigValue, notifyModerators } from '../../bot.js';

const NAME_TIMEOUT_MS = 5 * 60 * 1000;

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
    collectName(interaction.channel, interaction, targetId, isOverride);

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

function collectName(channel, interaction, targetId, isOverride) {
  const invokerId = interaction.user.id;
  let confirmMsg = null;
  let btnCollector = null;
  let settled = false;

  const msgCollector = channel.createMessageCollector({
    filter: m => m.author.id === invokerId,
    idle: NAME_TIMEOUT_MS,
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
      time: NAME_TIMEOUT_MS,
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
          return;
        }

        await setUserEuName(targetId, euName);

        if (isOverride) {
          await i.update({
            content: `The EU name for <@${targetId}> has been set to **${euName}**.`,
            components: []
          });
        } else {
          await i.update({
            content: `Your EU name has been set to **${euName}**. A moderator will continue the verification process.`,
            components: []
          });
          await notifyModeratorsOfName(interaction, targetId, euName);
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

    btnCollector.on('end', (_, reason) => {
      if (reason === 'time' && !settled) {
        settled = true;
        msgCollector.stop('time');
        confirmMsg.edit({ content: 'Timed out. Please run `/seteuname` again.', components: [] }).catch(() => {});
      }
    });
  });

  msgCollector.on('end', (collected, reason) => {
    if (settled) return;
    settled = true;
    if (btnCollector) btnCollector.stop('done');
    if (confirmMsg) {
      confirmMsg.edit({ content: 'Timed out. Please run `/seteuname` again.', components: [] }).catch(() => {});
    } else {
      channel.send('No name was entered in time. Please run `/seteuname` again.').catch(() => {});
    }
  });
}

async function notifyModeratorsOfName(interaction, targetId, euName) {
  const moderatorRoleId = getConfigValue('moderatorRoleId');
  if (!moderatorRoleId) return;

  const moderatorRole = interaction.guild.roles.cache.get(moderatorRoleId);
  if (!moderatorRole) return;

  const guildId = interaction.guildId;
  const threadId = interaction.channelId;
  const threadLink = `https://discord.com/channels/${guildId}/${threadId}`;
  const message = [
    `A user with the ID ${targetId} has set their EU name to "${euName}". Please verify their account.`,
    `Thread: ${threadLink}`,
    `Guild ID: ${guildId}`,
    `Channel ID: ${interaction.channel.parentId || threadId}`,
    `Thread ID: ${threadId}`
  ].join('\n');

  await Promise.all(
    moderatorRole.members.map(member =>
      member.send(message).catch(err => {
        console.error('Failed to DM moderator:', err);
      })
    )
  );
}
