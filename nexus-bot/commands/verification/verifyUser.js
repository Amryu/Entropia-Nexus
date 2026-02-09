import { SlashCommandBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';
import { getConfigValue } from '../../bot.js';
import { getUserById, getUserByUsername, setUserVerified, assignUserRole } from '../../db.js';

const promptRow = new ActionRowBuilder()
  .addComponents(
    new ButtonBuilder()
      .setCustomId('approve')
      .setLabel('Approve')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId('cancel')
      .setLabel('Cancel')
      .setStyle(ButtonStyle.Danger),
  );

const cancelRow = new ActionRowBuilder()
  .addComponents(
    new ButtonBuilder()
      .setCustomId('cancel_confirm')
      .setLabel('Yes')
      .setStyle(ButtonStyle.Danger),
    new ButtonBuilder()
      .setCustomId('cancel_deny')
      .setLabel('No')
      .setStyle(ButtonStyle.Secondary),
  );

const approveRow = new ActionRowBuilder()
  .addComponents(
    new ButtonBuilder()
      .setCustomId('approve_confirm')
      .setLabel('Yes')
      .setStyle(ButtonStyle.Success),
    new ButtonBuilder()
      .setCustomId('approve_deny')
      .setLabel('No')
      .setStyle(ButtonStyle.Danger),
  );

export const data = new SlashCommandBuilder()
  .setName('verifyuser')
  .setDescription('Moderator only - Starts the verification process for a user.');

export async function execute(interaction) {
  let moderatorRoleId = getConfigValue('moderatorRoleId');
  if (!moderatorRoleId) {
    return interaction.reply({ content: 'The moderator role has not been set.', ephemeral: true });
  }
  if (!interaction.member.roles.cache.has(moderatorRoleId) && !interaction.member.permissions.has('ADMINISTRATOR')) {
    return interaction.reply({ content: 'You do not have permission to use this command.', ephemeral: true });
  }

  let channelId = getConfigValue('verifiedChannelId');
  if (!channelId) {
    return interaction.reply({ content: 'The verified channel has not been set.', ephemeral: true });
  }
  if (interaction.channel.parentId !== channelId || !interaction.channel.isThread()) {
    return interaction.reply({ content: `This command can only be used in a thread that is a child of <#${channelId}>.`, ephemeral: true });
  }

  let guild = interaction.guild;
  let thread = interaction.channel;
  let userName = thread.name.split('-')[0];
  let userVerify = await getUserByUsername(userName);
  let discordUserVerify = await guild.members.fetch(userVerify.id);

  if (!discordUserVerify) {
    return interaction.reply({ content: 'The user was not found. Did he leave the server?', ephemeral: true });
  }
  if (userVerify.verified) {
    if (!discordUserVerify.roles.cache.has(getConfigValue('verifiedRoleId'))) {
      await discordUserVerify.roles.add(getConfigValue('verifiedRoleId'));
    }

    return interaction.reply({ content: 'This user is already verified.', ephemeral: true });
  }

  if (!userVerify || !userVerify.eu_name) {
    return interaction.reply({ content: 'The user has not yet set his EU name.', ephemeral: true });
  }

  let userModerator = await getUserById(interaction.member.id);
  let code = Math.floor(10000000 + Math.random() * 90000000);

  try {
    interaction.channel.send(`<@${userVerify.id}> - Please message "${userModerator.eu_name}" with the code ${code} in Entropia Universe via PM or Mail to finish verification.`);
  } catch (e) {
    console.error(`Failed to send verification message to thread ${interaction.channel.id} for user ${userVerify.username}: ${e.message}`);
    return interaction.reply({ content: 'Failed to send verification message. The thread may be archived.', ephemeral: true });
  }

  await promptModeratorForConfirmation(interaction, userVerify, code, async () => {
    let verifiedRole = guild.roles.cache.get(getConfigValue('verifiedRoleId'));
    if (!verifiedRole) {
      try {
        await interaction.channel.send('The verified role has not been set. Please contact an administrator.');
      } catch (e) {
        console.error(`Failed to send error message to thread ${interaction.channel.id}: ${e.message}`);
      }
      return;
    }

    await discordUserVerify.roles.add(verifiedRole);
    await setUserVerified(userVerify.id, true);
    await assignUserRole(userVerify.id);
    try {
      await interaction.channel.send(`${userVerify.global_name} has been successfully verified with the Entropia name "${userVerify.eu_name}"!`);
      await interaction.channel.setArchived(true);
    } catch (e) {
      console.error(`Failed to send success message or archive thread ${interaction.channel.id}: ${e.message}`);
    }
  });
}

async function promptModeratorForConfirmation(interaction, verifyUser, code, onApprove) {
  const prompt = { content: `${verifyUser.global_name} has set his name to "${verifyUser.eu_name}". Approve this if he sends you the code "${code}" inside Entropia Universe.`, components: [promptRow], ephemeral: true };
  
  await interaction.reply(prompt);

  const filter = _ => true;
  const collector = interaction.channel.createMessageComponentCollector({ filter, time: 0 });
  
  collector.on('collect', async i => {
    if (i.customId === 'approve') {
      await i.update({ content: 'Are you sure you want to approve?', components: [approveRow], ephemeral: true});
    } else if (i.customId === 'cancel'){
      await i.update({ content: 'Are you sure you want to cancel?', components: [cancelRow], ephemeral: true });
    } else if (i.customId === 'approve_confirm') {
      i.update({ content: '...', components: [], ephemeral: true });
      await onApprove();
      collector.stop();
    } else if (i.customId === 'approve_deny') {
      await i.update(prompt);
    } else if (i.customId === 'cancel_confirm') {
      i.update({ content: 'The verification process was cancelled.', ephemeral: true });
      collector.stop();
    } else if (i.customId === 'cancel_deny') {
      await i.update(prompt);
    }
  });
}