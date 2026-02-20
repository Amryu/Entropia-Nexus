import { SlashCommandBuilder, MessageFlags, PermissionFlagsBits } from 'discord.js';
import { getConfigValue, replaceVerificationFlow, clearVerificationFlow } from '../../bot.js';
import { getUserByUsername, setUserEuName, setBotConfig } from '../../db.js';
import { collectEuName } from './setEuName.js';

export const data = new SlashCommandBuilder()
  .setName('resetverification')
  .setDescription('Moderator only - Resets the verification flow for a user, keeping the thread.');

export async function execute(interaction) {
  const moderatorRoleId = getConfigValue('moderatorRoleId');
  if (!moderatorRoleId) {
    return interaction.reply({ content: 'The moderator role has not been set.', flags: MessageFlags.Ephemeral });
  }
  if (!interaction.member.roles.cache.has(moderatorRoleId) && !interaction.member.permissions.has(PermissionFlagsBits.Administrator)) {
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
  const user = await getUserByUsername(userName);

  if (!user) {
    return interaction.reply({ content: 'Could not find a user matching this thread.', flags: MessageFlags.Ephemeral });
  }
  if (user.verified) {
    return interaction.reply({ content: 'This user is already verified. Verification cannot be reset after completion.', flags: MessageFlags.Ephemeral });
  }

  // Clear EU name and verification code
  await setUserEuName(user.id, null);
  await setBotConfig(`verify_code:${user.id}`, null);

  await interaction.reply({ content: 'Verification has been reset.', flags: MessageFlags.Ephemeral });
  await thread.send(`Verification has been reset by a moderator. <@${user.id}>, please type your full Entropia Universe name below to begin again.`);

  const handle = collectEuName(thread, user.id, {
    typerId: user.id,
    guild: interaction.guild,
    onEnd: () => clearVerificationFlow(user.id),
  });
  replaceVerificationFlow(user.id, handle);
}
