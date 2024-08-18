import { SlashCommandBuilder } from 'discord.js';
import { getUsers, getUserById, setUserEuName, createUser } from '../../db.js';
import { getConfigValue } from '../../bot.js';

export const data = new SlashCommandBuilder()
  .setName('seteuname')
  .setDescription('Sets your entropia universe name used in verification. Can\'t be changed once set!')
  .addStringOption(option => option.setName('eu_name')
    .setDescription('Your Entropia Universe name. Make sure to match the exact capitalization and spacing.')
    .setRequired(true));

export async function execute(interaction) {
  let channelId = getConfigValue('verifiedChannelId');
  if (!channelId) {
    return interaction.reply({ content: 'The verified channel has not been set.', ephemeral: true });
  }
  if (interaction.channel.parentId !== channelId || !interaction.channel.isThread()) {
    return interaction.reply({ content: `This command can only be used in a thread that is a child of <#${channelId}>.`, ephemeral: true });
  }

  const euName = interaction.options.getString('eu_name');
  if (!euName) {
    return interaction.reply({ content: 'Please provide your Entropia Universe name.', ephemeral: true });
  }

  let user = await getUserById(interaction.user.id);

  if (!user) {
    user = await createUser(interaction.user);

    if (!user) {
      return interaction.reply({ content: 'An error occurred while creating your user. Please try again later.', ephemeral: true });
    }
  }
  if (user.verified) {
    return interaction.reply({ content: 'You have already verified your account. Name changes are typically not possible in Entropia Universe, so we do not allow them here either. If there are special circumstances, please contact a moderator with evidence.', ephemeral: true });
  }
  if (user.eu_name === euName) {
    return interaction.reply({ content: 'Your EU name is already set to that.', ephemeral: true });
  }

  let users = await getUsers();
  if (users.some(x => x.eu_name?.toLowerCase() === euName?.toLowerCase())) {
    return interaction.reply({ content: 'This Entropia Universe name is already in use. Contact a moderator if you believe this is an error.', ephemeral: true });
  }

  await setUserEuName(interaction.user.id, euName);

  await interaction.reply(`Your EU name has been set to "${euName}". Wait for a moderator to continue the verification process.`);

  let moderatorRoleId = getConfigValue('moderatorRoleId');

  if (moderatorRoleId) {
    const moderatorRole = interaction.guild.roles.cache.get(moderatorRoleId);
    if (moderatorRole) {
      moderatorRole.members.forEach(member => {
        member.send(`A user with the ID ${interaction.user.id} has set their EU name to "${euName}". Please verify their account.`).catch(console.error);
      });
    }
  }
}