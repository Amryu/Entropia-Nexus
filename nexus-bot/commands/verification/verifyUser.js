import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags } from 'discord.js';
import { getConfigValue } from '../../bot.js';
import { getUserById, getUserByUsername, setUserVerified, assignUserRole, getBotConfig, setBotConfig } from '../../db.js';

const VERIFY_TIMEOUT_MS = 30 * 60 * 1000;

const cancelRow = new ActionRowBuilder()
  .addComponents(
    new ButtonBuilder()
      .setCustomId('verify_cancel')
      .setLabel('Cancel')
      .setStyle(ButtonStyle.Danger),
  );

const cancelConfirmRow = new ActionRowBuilder()
  .addComponents(
    new ButtonBuilder()
      .setCustomId('verify_cancel_confirm')
      .setLabel('Yes, cancel')
      .setStyle(ButtonStyle.Danger),
    new ButtonBuilder()
      .setCustomId('verify_cancel_deny')
      .setLabel('No')
      .setStyle(ButtonStyle.Secondary),
  );

export const data = new SlashCommandBuilder()
  .setName('verifyuser')
  .setDescription('Moderator only - Starts the verification process for a user.');

/**
 * Slash command handler for /verifyuser — manual trigger by moderators.
 */
export async function execute(interaction) {
  const moderatorRoleId = getConfigValue('moderatorRoleId');
  if (!moderatorRoleId) {
    return interaction.reply({ content: 'The moderator role has not been set.', flags: MessageFlags.Ephemeral });
  }
  if (!interaction.member.roles.cache.has(moderatorRoleId) && !interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply({ content: 'You do not have permission to use this command.', flags: MessageFlags.Ephemeral });
  }

  const channelId = getConfigValue('verifiedChannelId');
  if (!channelId) {
    return interaction.reply({ content: 'The verified channel has not been set.', flags: MessageFlags.Ephemeral });
  }
  if (interaction.channel.parentId !== channelId || !interaction.channel.isThread()) {
    return interaction.reply({ content: `This command can only be used in a thread that is a child of <#${channelId}>.`, flags: MessageFlags.Ephemeral });
  }

  const thread = interaction.channel;
  const userName = thread.name.split('-')[0];
  const userVerify = await getUserByUsername(userName);

  if (!userVerify) {
    return interaction.reply({ content: 'Could not find a user matching this thread.', flags: MessageFlags.Ephemeral });
  }
  if (!userVerify.eu_name) {
    return interaction.reply({ content: 'The user has not yet set their EU name.', flags: MessageFlags.Ephemeral });
  }
  if (userVerify.verified) {
    const guild = interaction.guild;
    const discordUser = await guild.members.fetch(userVerify.id).catch(() => null);
    if (discordUser && !discordUser.roles.cache.has(getConfigValue('verifiedRoleId'))) {
      await discordUser.roles.add(getConfigValue('verifiedRoleId'));
    }
    return interaction.reply({ content: 'This user is already verified.', flags: MessageFlags.Ephemeral });
  }

  await interaction.reply({ content: 'Verification started.', flags: MessageFlags.Ephemeral });
  await startVerification(thread, userVerify.id, interaction.guild);
}

/**
 * Start the verification code exchange for a user.
 * Can be called from:
 * - /verifyuser command (manual moderator trigger)
 * - collectEuName (automatic after name confirmation)
 * - bot.js checkUnverifiedUsers (for users who already have an EU name)
 *
 * @param {import('discord.js').ThreadChannel} thread - The verification thread
 * @param {string} userId - The Discord user ID to verify
 * @param {import('discord.js').Guild} guild - The guild
 * @param {object} [options]
 * @param {function} [options.onEnd] - Called when verification completes, times out, or is cancelled
 */
export async function startVerification(thread, userId, guild, { onEnd } = {}) {
  const userVerify = await getUserById(userId);
  if (!userVerify || !userVerify.eu_name) {
    onEnd?.();
    return;
  }
  if (userVerify.verified) {
    onEnd?.();
    return;
  }

  const discordUserVerify = await guild.members.fetch(userId).catch(() => null);
  if (!discordUserVerify) {
    onEnd?.();
    return;
  }

  const code = Math.floor(10000000 + Math.random() * 90000000);

  // Persist code so it survives bot restarts
  await setBotConfig(`verify_code:${userId}`, String(code));

  // Public message to user in thread
  try {
    await thread.send(`<@${userId}> — A moderator will send you a verification code in Entropia Universe via PM or Mail. Please type the code here when you receive it.`);
  } catch (e) {
    console.error(`Failed to send verification message to thread ${thread.id}: ${e.message}`);
    onEnd?.();
    return;
  }

  // DM moderators with the code
  await notifyModeratorsWithCode(guild, thread.id, code, userVerify.eu_name);

  collectVerificationCode(thread, userVerify, discordUserVerify, guild, code, onEnd);
}

/**
 * Resume listening for a verification code that was already generated before a restart.
 * Does NOT generate a new code or send any messages — just sets up the collector.
 *
 * @param {import('discord.js').ThreadChannel} thread
 * @param {string} userId
 * @param {import('discord.js').Guild} guild
 * @param {object} [options]
 * @param {function} [options.onEnd]
 */
export async function resumeVerification(thread, userId, guild, { onEnd } = {}) {
  const existingCode = await getBotConfig(`verify_code:${userId}`);
  if (!existingCode) {
    // No code was ever generated — nothing to resume
    onEnd?.();
    return;
  }

  const userVerify = await getUserById(userId);
  if (!userVerify || !userVerify.eu_name || userVerify.verified) {
    await setBotConfig(`verify_code:${userId}`, null);
    onEnd?.();
    return;
  }

  const discordUserVerify = await guild.members.fetch(userId).catch(() => null);
  if (!discordUserVerify) {
    onEnd?.();
    return;
  }

  console.log(`resumeVerification: Resuming code collector for ${userVerify.username} (code preserved)`);
  collectVerificationCode(thread, userVerify, discordUserVerify, guild, parseInt(existingCode, 10), onEnd);
}

async function notifyModeratorsWithCode(guild, threadId, code, euName) {
  const moderatorRoleId = getConfigValue('moderatorRoleId');
  if (!moderatorRoleId) return;

  const moderatorRole = guild.roles.cache.get(moderatorRoleId);
  if (!moderatorRole) return;

  const threadLink = `https://discord.com/channels/${guild.id}/${threadId}`;
  const message = [
    `Send the code **${code}** to "${euName}" in Entropia Universe via PM or Mail.`,
    `The user will type it in the thread to complete verification.`,
    `Thread: ${threadLink}`,
  ].join('\n');

  await Promise.all(
    moderatorRole.members.map(member =>
      member.send(message).catch(err => {
        console.error('Failed to DM moderator:', err);
      })
    )
  );
}

function collectVerificationCode(thread, userVerify, discordUserVerify, guild, code, onEnd) {
  let settled = false;
  const codeStr = String(code);

  const msgCollector = thread.createMessageCollector({
    filter: m => m.author.id === userVerify.id,
    idle: VERIFY_TIMEOUT_MS,
  });

  const btnCollector = thread.createMessageComponentCollector({
    filter: i => {
      const moderatorRoleId = getConfigValue('moderatorRoleId');
      return moderatorRoleId && i.member?.roles?.cache?.has(moderatorRoleId);
    },
    idle: VERIFY_TIMEOUT_MS,
  });

  function settle() {
    if (settled) return false;
    settled = true;
    msgCollector.stop('done');
    btnCollector.stop('done');
    onEnd?.();
    return true;
  }

  async function onVerified() {
    if (!settle()) return;

    const verifiedRole = guild.roles.cache.get(getConfigValue('verifiedRoleId'));
    if (!verifiedRole) {
      try {
        await thread.send('The verified role has not been set. Please contact an administrator.');
      } catch (e) {
        console.error(`Failed to send error message to thread ${thread.id}: ${e.message}`);
      }
      return;
    }

    await discordUserVerify.roles.add(verifiedRole);
    await setUserVerified(userVerify.id, true);
    await assignUserRole(userVerify.id);
    await setBotConfig(`verify_code:${userVerify.id}`, null);
    try {
      await thread.send(`${userVerify.global_name} has been successfully verified with the Entropia name "${userVerify.eu_name}"!`);
      await thread.setArchived(true);
    } catch (e) {
      console.error(`Failed to send success message or archive thread ${thread.id}: ${e.message}`);
    }
  }

  // Listen for user typing the code
  msgCollector.on('collect', async (msg) => {
    const typed = msg.content.trim();
    if (!typed) return;

    if (typed === codeStr) {
      await onVerified();
    } else {
      try {
        await thread.send('That code is incorrect. Please check the message you received in Entropia Universe and try again.');
      } catch (e) {
        console.error(`Failed to send incorrect code message to thread ${thread.id}: ${e.message}`);
      }
    }
  });

  msgCollector.on('end', () => {
    if (!settle()) return;
    thread.send('Verification timed out. A moderator can restart with `/verifyuser`.').catch(() => {});
  });

  // Listen for moderator cancel button (from ephemeral messages in /verifyuser)
  btnCollector.on('collect', async (i) => {
    if (i.customId === 'verify_cancel') {
      await i.update({ content: 'Are you sure you want to cancel verification?', components: [cancelConfirmRow], flags: MessageFlags.Ephemeral });
    } else if (i.customId === 'verify_cancel_confirm') {
      await i.update({ content: 'Verification cancelled.', components: [], flags: MessageFlags.Ephemeral });
      if (!settle()) return;
      try {
        await thread.send('The verification process was cancelled by a moderator.');
      } catch (e) {
        console.error(`Failed to send cancel message to thread ${thread.id}: ${e.message}`);
      }
    } else if (i.customId === 'verify_cancel_deny') {
      await i.update({ content: 'Verification is in progress. The user will type the code here.', components: [cancelRow], flags: MessageFlags.Ephemeral });
    }
  });
}
