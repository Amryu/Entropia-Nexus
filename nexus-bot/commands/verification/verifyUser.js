import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags } from 'discord.js';
import { getConfigValue } from '../../bot.js';
import { getUserByUsername, setUserVerified, assignUserRole } from '../../db.js';

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

export async function execute(interaction) {
  let moderatorRoleId = getConfigValue('moderatorRoleId');
  if (!moderatorRoleId) {
    return interaction.reply({ content: 'The moderator role has not been set.', flags: MessageFlags.Ephemeral });
  }
  if (!interaction.member.roles.cache.has(moderatorRoleId) && !interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply({ content: 'You do not have permission to use this command.', flags: MessageFlags.Ephemeral });
  }

  let channelId = getConfigValue('verifiedChannelId');
  if (!channelId) {
    return interaction.reply({ content: 'The verified channel has not been set.', flags: MessageFlags.Ephemeral });
  }
  if (interaction.channel.parentId !== channelId || !interaction.channel.isThread()) {
    return interaction.reply({ content: `This command can only be used in a thread that is a child of <#${channelId}>.`, flags: MessageFlags.Ephemeral });
  }

  let guild = interaction.guild;
  let thread = interaction.channel;
  let userName = thread.name.split('-')[0];
  let userVerify = await getUserByUsername(userName);
  let discordUserVerify = await guild.members.fetch(userVerify.id);

  if (!discordUserVerify) {
    return interaction.reply({ content: 'The user was not found. Did they leave the server?', flags: MessageFlags.Ephemeral });
  }
  if (userVerify.verified) {
    if (!discordUserVerify.roles.cache.has(getConfigValue('verifiedRoleId'))) {
      await discordUserVerify.roles.add(getConfigValue('verifiedRoleId'));
    }

    return interaction.reply({ content: 'This user is already verified.', flags: MessageFlags.Ephemeral });
  }

  if (!userVerify || !userVerify.eu_name) {
    return interaction.reply({ content: 'The user has not yet set their EU name.', flags: MessageFlags.Ephemeral });
  }

  let code = Math.floor(10000000 + Math.random() * 90000000);

  // Public message to user in thread
  try {
    await thread.send(`<@${userVerify.id}> — A moderator will send you a verification code in Entropia Universe via PM or Mail. Please type the code here when you receive it.`);
  } catch (e) {
    console.error(`Failed to send verification message to thread ${thread.id} for user ${userVerify.username}: ${e.message}`);
    return interaction.reply({ content: 'Failed to send verification message. The thread may be archived.', flags: MessageFlags.Ephemeral });
  }

  // Ephemeral message to moderator with code and cancel button
  const modPrompt = { content: `Send the code **${code}** to "${userVerify.eu_name}" in Entropia Universe via PM or Mail.\n\nThe user will type the code here to complete verification.`, components: [cancelRow], flags: MessageFlags.Ephemeral };
  await interaction.reply(modPrompt);

  await collectVerificationCode(interaction, thread, userVerify, discordUserVerify, guild, code, modPrompt);
}

async function collectVerificationCode(interaction, thread, userVerify, discordUserVerify, guild, code, modPrompt) {
  let settled = false;
  const codeStr = String(code);

  // Collect messages from the user being verified
  const msgCollector = thread.createMessageCollector({
    filter: m => m.author.id === userVerify.id,
    idle: VERIFY_TIMEOUT_MS,
  });

  // Collect button interactions from the moderator
  const btnCollector = thread.createMessageComponentCollector({
    filter: i => i.user.id === interaction.user.id,
    idle: VERIFY_TIMEOUT_MS,
  });

  async function onVerified() {
    if (settled) return;
    settled = true;
    msgCollector.stop('verified');
    btnCollector.stop('verified');

    let verifiedRole = guild.roles.cache.get(getConfigValue('verifiedRoleId'));
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
    try {
      await thread.send(`${userVerify.global_name} has been successfully verified with the Entropia name "${userVerify.eu_name}"!`);
      await thread.setArchived(true);
    } catch (e) {
      console.error(`Failed to send success message or archive thread ${thread.id}: ${e.message}`);
    }
  }

  function onCancel() {
    if (settled) return;
    settled = true;
    msgCollector.stop('cancelled');
    btnCollector.stop('cancelled');
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
    if (settled) return;
    settled = true;
    btnCollector.stop('done');
    thread.send('Verification timed out. A moderator can restart with `/verifyuser`.').catch(() => {});
  });

  // Listen for moderator cancel button
  btnCollector.on('collect', async (i) => {
    if (i.customId === 'verify_cancel') {
      await i.update({ content: 'Are you sure you want to cancel verification?', components: [cancelConfirmRow], flags: MessageFlags.Ephemeral });
    } else if (i.customId === 'verify_cancel_confirm') {
      await i.update({ content: 'Verification cancelled.', components: [], flags: MessageFlags.Ephemeral });
      onCancel();
      try {
        await thread.send('The verification process was cancelled by a moderator.');
      } catch (e) {
        console.error(`Failed to send cancel message to thread ${thread.id}: ${e.message}`);
      }
    } else if (i.customId === 'verify_cancel_deny') {
      await i.update(modPrompt);
    }
  });
}
