import dotenv from 'dotenv';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
// js-yaml no longer needed — diff format replaced YAML output
import { Client, GatewayIntentBits, Collection, Events, ChannelType, ActionRowBuilder, ButtonBuilder, ButtonStyle, EmbedBuilder } from 'discord.js';
import { getUsers, getUserById, getOpenChanges, setChangeThreadId, getDeletedChanges, deleteChange, getChangeById, setChangeState, getFlightsNeedingThread, setFlightThreadId, getCheckinsPendingThreadAdd, markCheckinAddedToThread, getUnnotifiedFlightStateChanges, getFlightsNeedingArchive, clearFlightThreadId, getPendingRescheduleNotifications, markRescheduleNotificationSent, getPendingRentalDmNotifications, markRentalDmNotificationSent, getServicePilots, getFlightAcceptedCheckins, getFlightsReadyForCustomerKick, setFlightCompletedAt, expireTickets, getPendingTradeRequests, getTradeRequestItems, setTradeRequestThread, getWarnableTradeRequests, markWarningSent, getExpirableTradeRequests, updateTradeRequestStatus, findTradeRequestByThread, updateLastActivity, getActiveTradeRequestsWithNewItems, getNewTradeRequestItems, adjustOfferQuantities, getUsersWithGrant, getPendingServiceRequests, setServiceRequestThread, markServiceRequestNotified, acceptServiceRequest, declineServiceRequest, getServiceRequestById, acceptCheckin, denyCheckin, getCheckinWithContext, activateTicketByCheckin, getPendingCheckinsDmNotify, getBotConfig, setBotConfig, getActiveContentCreators, setUserLeftServer, clearUserLeftServer, getStaleUnverifiedUsers, deleteUnverifiedUser, startUsersTransaction, commitTransaction, rollbackTransaction, resolveMarketPriceItemIds } from './db.js';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compareJson, validate, printSideBySide } from './change.js';
import { applyChange } from './changes/util.js';
import { handleReward, fetchEntityForReward } from './changes/rewards.js';
import { getTypeLink, getStateLabel } from './util.js';
import { renderMapChange } from './mapRenderer.js';
import { snapshotExchangePrices, computeAllExchangeSummaries } from './exchange-prices.js';
import { checkAuctions, refreshAuctionColors } from './auctions.js';
import { collectEuName } from './commands/verification/setEuName.js';
import { resumeVerification } from './commands/verification/verifyUser.js';

const adminUserId = '178245652633878528';

// Track active verification flows to prevent re-triggering from the 1-minute interval.
// Maps userId -> { stop() } so existing collectors can be stopped before starting new ones.
const activeVerificationFlows = new Map();

/**
 * Stop any existing verification flow for a user and start tracking a new one.
 * @param {string} userId
 * @param {{ stop: () => void }} handle - The collector handle to track
 */
export function replaceVerificationFlow(userId, handle) {
  const existing = activeVerificationFlows.get(userId);
  if (existing) existing.stop();
  activeVerificationFlows.set(userId, handle);
}

/**
 * Remove the verification flow tracking for a user.
 * @param {string} userId
 */
export function clearVerificationFlow(userId) {
  activeVerificationFlows.delete(userId);
}

dotenv.config();
const config = JSON.parse(readFileSync('config.json', 'utf8'));

// Planet ID to name lookup - fetched from API
let planetCache = null;
let planetCacheTime = 0;
const PLANET_CACHE_TTL = 60 * 60 * 1000; // 1 hour

async function fetchPlanets() {
  try {
    const response = await fetch(`${process.env.API_URL}/planets`);
    if (response.ok) {
      const planets = await response.json();
      planetCache = {};
      for (const planet of planets) {
        planetCache[planet.Id] = planet.Name;
      }
      planetCacheTime = Date.now();
      console.log(`Fetched ${planets.length} planets from API`);
    }
  } catch (error) {
    console.error('Error fetching planets from API:', error);
  }
}

function getPlanetName(planetId) {
  if (!planetId) return null;
  // Refresh cache if expired
  if (!planetCache || Date.now() - planetCacheTime > PLANET_CACHE_TTL) {
    fetchPlanets(); // Non-blocking refresh
  }
  return planetCache?.[planetId] || `Planet #${planetId}`;
}

// Full planet data cache (with Map properties for map rendering)
let planetDataCache = {};

async function fetchPlanetData(planetName) {
  if (!planetName) return null;
  if (planetDataCache[planetName]) return planetDataCache[planetName];
  try {
    const res = await fetch(`${process.env.API_URL}/planets/${encodeURIComponent(planetName)}`);
    if (!res.ok) return null;
    const data = await res.json();
    planetDataCache[planetName] = data;
    return data;
  } catch {
    return null;
  }
}

function getEntityApiCollection(entityType) {
  switch (entityType) {
    case 'TeleportChip':
    case 'TeleportationChip':
      return 'teleportationchips';
    case 'CreatureControlCapsule':
    case 'Capsule':
      return 'capsules';
    case 'Area':
      return 'locations';
    default:
      return `${entityType.toLowerCase()}s`;
  }
}

export function setConfigValue(key, value) {
  config[key] = value;

  // Save to file config.json
  writeFileSync('config.json', JSON.stringify(config));
}
export function getConfigValue(key) {
  return config[key];
}

const client = new Client({ intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.GuildMessageReactions,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.MessageContent
  ]
});

export async function notifyModerators({ title = 'Bot Error', error = null, context = '', extra = '' } = {}) {
  try {
    const moderatorRoleId = config.moderatorRoleId;
    if (!moderatorRoleId) {
      console.error('notifyModerators: Missing moderatorRoleId in config.');
      return;
    }

    // Resolve guild through cached channels (avoids guildId number precision loss)
    const channel = client.channels.cache.get(config.pendingChangesChannelId)
      || client.channels.cache.get(config.verifiedChannelId);
    if (!channel?.guild) {
      console.error('notifyModerators: Could not resolve guild from cached channels.');
      return;
    }
    const guild = channel.guild;

    const role = guild.roles.cache.get(moderatorRoleId) || await guild.roles.fetch(moderatorRoleId).catch(() => null);
    const members = role ? Array.from(role.members.values()) : [];

    const errorMessage = error?.message || String(error || 'Unknown error');
    const errorStack = error?.stack ? String(error.stack) : '';

    let message = `**${title}**\n`;
    if (context) message += `**Context:** ${context}\n`;
    if (extra) message += `**Details:** ${extra}\n`;
    message += `**Error:** ${errorMessage}\n`;
    if (errorStack) message += `**Stack:**\n${errorStack}\n`;

    if (message.length > 1900) {
      message = message.slice(0, 1900) + '\n…(truncated)';
    }

    if (members.length === 0) {
      const fallbackMember = await guild.members.fetch(adminUserId).catch(() => null);
      if (fallbackMember) {
        await fallbackMember.send(message).catch(() => {});
      }
      return;
    }

    await Promise.all(
      members.map(member => member.send(message).catch(() => {}))
    );
  } catch (notifyError) {
    console.error('notifyModerators failed:', notifyError);
  }
}

client.on(Events.ClientReady, async () => {
  console.log(`Logged in as ${client.user.tag}!`);
  // Fetch planets from API on startup
  await fetchPlanets();
});

process.on('unhandledRejection', async (error) => {
  console.error('Unhandled promise rejection:', error);
  await notifyModerators({
    title: 'Unhandled Promise Rejection',
    error
  });
});

process.on('uncaughtException', async (error) => {
  console.error('Uncaught exception:', error);
  await notifyModerators({
    title: 'Uncaught Exception',
    error
  });
});

client.on(Events.InteractionCreate, async interaction => {
  // Handle slash commands
  if (interaction.isChatInputCommand()) {
    const command = interaction.client.commands.get(interaction.commandName);

    if (!command) {
      console.error(`No command matching ${interaction.commandName} was found.`);
      return;
    }

    try {
      await command.execute(interaction);
    } catch (error) {
      console.error(error);
      await notifyModerators({
        title: 'Command Execution Error',
        error,
        context: `/${interaction.commandName} by ${interaction.user?.tag || interaction.user?.id}`
      });
      if (interaction.replied || interaction.deferred) {
        await interaction.followUp({ content: 'There was an error while executing this command!', flags: 64 }).catch(() => {});
      } else {
        await interaction.reply({ content: 'There was an error while executing this command!', flags: 64 }).catch(() => {});
      }
    }
    return;
  }

  // Handle button interactions
  if (interaction.isButton()) {
    const customId = interaction.customId;

    // Trade completion buttons: trade_done_{yes|no|cancel}_{requestId}
    if (customId.startsWith('trade_done_')) {
      const parts = customId.split('_');
      const action = parts[2]; // yes, no, cancel
      const requestId = parseInt(parts[3], 10);

      if (action === 'cancel') {
        return interaction.update({ content: 'Trade completion cancelled.', components: [] });
      }

      try {
        let summary = '';
        let publicMsg;

        if (action === 'yes') {
          const adjustments = await adjustOfferQuantities(requestId);
          const closed = adjustments.filter(a => a.closed);
          const reduced = adjustments.filter(a => !a.closed);
          const parts = [];
          if (reduced.length > 0) parts.push(`${reduced.length} order(s) adjusted`);
          if (closed.length > 0) parts.push(`${closed.length} order(s) closed (quantity depleted)`);
          summary = parts.length > 0 ? `\n${parts.join(', ')}.` : '\nNo orders needed adjustment.';
        }

        publicMsg = `\ud83d\udd12 **Thread Closed** — This trade thread has been closed by <@${interaction.user.id}>. Thread will be locked and archived.`;

        await updateTradeRequestStatus(requestId, 'completed');
        await interaction.update({ content: `Thread closed.${summary}`, components: [] });

        // Send public message and lock/archive the thread
        const thread = interaction.channel;
        if (thread?.isThread()) {
          await thread.send(publicMsg);
          await thread.setLocked(true).catch(() => {});
          await thread.setArchived(true).catch(() => {});
        }
      } catch (error) {
        console.error('Error closing trade thread via button:', error);
        await interaction.update({ content: 'An error occurred while closing the trade thread.', components: [] }).catch(() => {});
      }
      return;
    }

    // Service request buttons: svc_req_{accept|decline}_{requestId}
    if (customId.startsWith('svc_req_')) {
      const parts = customId.split('_');
      const action = parts[2]; // accept, decline
      const requestId = parseInt(parts[3], 10);

      try {
        const req = await getServiceRequestById(requestId);
        if (!req) {
          return interaction.reply({ content: 'Request not found.', flags: 64 });
        }

        // Verify the user is staff (manager, owner, or pilot)
        const userId = interaction.user.id;
        const isStaff = userId === req.manager_id.toString() ||
          (req.owner_user_id && userId === req.owner_user_id.toString()) ||
          (await getServicePilots(req.service_id)).some(p => p.user_id.toString() === userId);

        if (!isStaff) {
          return interaction.reply({ content: 'You do not have permission to manage this request.', flags: 64 });
        }

        if (action === 'accept') {
          const updated = await acceptServiceRequest(requestId);
          if (!updated) {
            return interaction.update({ content: interaction.message.content + '\n\n✅ Already processed.', components: [] });
          }
          await interaction.update({ content: interaction.message.content + `\n\n✅ **Accepted** by <@${userId}>`, components: [] });
        } else if (action === 'decline') {
          const updated = await declineServiceRequest(requestId);
          if (!updated) {
            return interaction.update({ content: interaction.message.content + '\n\n❌ Already processed.', components: [] });
          }
          await interaction.update({ content: interaction.message.content + `\n\n❌ **Declined** by <@${userId}>`, components: [] });
        }
      } catch (error) {
        console.error('Error handling service request button:', error);
        await interaction.reply({ content: 'An error occurred.', flags: 64 }).catch(() => {});
      }
      return;
    }

    // Check-in buttons: checkin_{accept|deny}_{checkinId}
    if (customId.startsWith('checkin_')) {
      const parts = customId.split('_');
      const action = parts[1]; // accept, deny
      const checkinId = parseInt(parts[2], 10);

      try {
        const checkin = await getCheckinWithContext(checkinId);
        if (!checkin) {
          return interaction.reply({ content: 'Check-in not found.', flags: 64 });
        }

        // Verify the user is staff
        const userId = interaction.user.id;
        const isStaff = userId === checkin.manager_id.toString() ||
          (checkin.owner_user_id && userId === checkin.owner_user_id.toString()) ||
          (await getServicePilots(checkin.service_id)).some(p => p.user_id.toString() === userId);

        if (!isStaff) {
          return interaction.reply({ content: 'You do not have permission to manage this check-in.', flags: 64 });
        }

        const passengerName = checkin.passenger_name || checkin.passenger_username || 'Unknown';

        if (action === 'accept') {
          const updated = await acceptCheckin(checkinId);
          if (!updated) {
            return interaction.update({ content: interaction.message.content + '\n\n✅ Already processed.', components: [] });
          }
          // Activate ticket on first accepted check-in
          if (checkin.ticket_id) {
            await activateTicketByCheckin(checkin.ticket_id).catch(() => {});
          }
          await interaction.update({ content: interaction.message.content + `\n\n✅ **${passengerName}** accepted by <@${userId}>`, components: [] });
        } else if (action === 'deny') {
          const updated = await denyCheckin(checkinId);
          if (!updated) {
            return interaction.update({ content: interaction.message.content + '\n\n❌ Already processed.', components: [] });
          }
          await interaction.update({ content: interaction.message.content + `\n\n❌ **${passengerName}** denied by <@${userId}>`, components: [] });
        }
      } catch (error) {
        console.error('Error handling check-in button:', error);
        await interaction.reply({ content: 'An error occurred.', flags: 64 }).catch(() => {});
      }
      return;
    }

    // Direct Apply retry/discard buttons (sent via DM, persist across restarts)
    if (customId.startsWith('change_retry_') || customId.startsWith('change_discard_')) {
      const parts = customId.split('_');
      const action = parts[1]; // retry or discard
      const changeId = parseInt(parts[2], 10);

      try {
        const change = await getChangeById(changeId);
        if (!change) {
          return interaction.update({ content: 'Change not found.', components: [] });
        }
        if (change.author_id.toString() !== interaction.user.id) {
          return interaction.reply({ content: 'You are not the author of this change.', flags: 64 });
        }
        if (change.state !== 'ApplyFailed' && change.state !== 'DirectApply') {
          return interaction.update({ content: `This change is no longer pending (state: ${getStateLabel(change.state)}).`, components: [] });
        }

        if (action === 'retry') {
          await interaction.update({ content: `Retrying **${change.data.Name}**...`, components: [] });

          const success = await applyChange(change);
          if (success) {
            await setChangeState(changeId, 'Approved');
            await interaction.followUp(`Change **${change.data.Name}** applied successfully!`);
          } else {
            const row = new ActionRowBuilder().addComponents(
              new ButtonBuilder()
                .setCustomId(`change_retry_${changeId}`)
                .setLabel('Retry')
                .setStyle(ButtonStyle.Success),
              new ButtonBuilder()
                .setCustomId(`change_discard_${changeId}`)
                .setLabel('Discard')
                .setStyle(ButtonStyle.Danger),
            );
            await interaction.followUp({
              content: `Failed again to apply **${change.data.Name}**. You can retry or discard.`,
              components: [row]
            });
          }
        } else if (action === 'discard') {
          await setChangeState(changeId, 'Deleted');
          await interaction.update({
            content: `Change **${change.data.Name}** has been discarded.`,
            components: []
          });
        }
      } catch (error) {
        console.error('Error handling change button:', error);
        await interaction.reply({ content: 'An error occurred.', flags: 64 }).catch(() => {});
      }
      return;
    }

    return;
  }

  // Handle modal submissions
  if (interaction.isModalSubmit()) {
    // On-demand service requests are no longer handled by the bot.
    return;
  }
});

async function checkUnverifiedUsers() {
  const channel = client.channels.cache.find(channel => channel.id === config.verifiedChannelId);
  if (!channel) throw new Error('Verification channel not found');

  const unverifiedUsers = (await getUsers()).filter(x => !x.verified);
  console.log(`[VERIFY] Checking ${unverifiedUsers.length} unverified users`);

  // Fetch guild members in batches — Discord Gateway limits REQUEST_GUILD_MEMBERS to 100 user IDs
  const MEMBER_FETCH_BATCH = 100;
  const userIds = unverifiedUsers.map(u => u.id);
  for (let i = 0; i < userIds.length; i += MEMBER_FETCH_BATCH) {
    const batch = userIds.slice(i, i + MEMBER_FETCH_BATCH);
    try {
      const fetched = await channel.guild.members.fetch({ user: batch });
      console.log(`[VERIFY] Batch ${Math.floor(i / MEMBER_FETCH_BATCH) + 1}: fetched ${fetched.size}/${batch.length} members`);
    } catch (e) {
      console.error(`[VERIFY] Batch fetch error:`, e.message);
    }
  }

  for (const user of unverifiedUsers) {
    try {
      const guildMember = channel.guild.members.cache.get(user.id);

      if (!guildMember) {
        console.log(`[VERIFY] ${user.username}: not in guild, marking left_server_at`);
        await setUserLeftServer(user.id);
        const existingThread = channel.threads.cache.find(thread => thread.name === `${user.username}-verification`);
        if (existingThread && !existingThread.archived) {
          try {
            await existingThread.setArchived(true);
            console.log(`[VERIFY] ${user.username}: archived orphan thread`);
          } catch (e) {
            console.error(`[VERIFY] ${user.username}: error archiving orphan thread:`, e);
          }
        }
        continue;
      }

      // User is in guild — clear left_server_at if previously set (handles rejoins)
      await clearUserLeftServer(user.id);

      let existingThread = channel.threads.cache.find(thread => thread.name === `${user.username}-verification`);
      console.log(`[VERIFY] ${user.username}: in guild, cached thread=${existingThread?.id || 'none'}`);

      // Also check archived threads — they won't be in the cache.
      // Paginate through all pages since there may be many archived threads.
      if (!existingThread) {
        try {
          let hasMore = true;
          let before;
          let pages = 0;
          while (hasMore && !existingThread) {
            pages++;
            const archived = await channel.threads.fetchArchived({ type: 'private', before });
            existingThread = archived.threads.find(thread => thread.name === `${user.username}-verification`);
            hasMore = archived.hasMore;
            if (hasMore && archived.threads.size > 0) {
              before = archived.threads.last()?.id;
            }
          }
          console.log(`[VERIFY] ${user.username}: searched ${pages} archived page(s), found=${existingThread?.id || 'none'}`);
        } catch (e) {
          console.error(`[VERIFY] ${user.username}: error fetching archived threads: ${e.message}`);
        }
      }

      if (existingThread) {
        // Unarchive if needed so the bot can send messages and collectors work.
        // If unarchiving fails, discard the stale thread and fall through to create a new one.
        if (existingThread.archived) {
          try {
            await existingThread.setArchived(false);
            console.log(`[VERIFY] ${user.username}: unarchived thread ${existingThread.id}`);
          } catch (e) {
            console.error(`[VERIFY] ${user.username}: cannot unarchive thread ${existingThread.id}, will create new: ${e.message}`);
            existingThread = null;
          }
        }
      }

      if (existingThread) {
        console.log(`[VERIFY] ${user.username}: reusing existing thread ${existingThread.id}`);
        try {
          await existingThread.members.add(user.id);
        } catch (e) {
          console.error(`[VERIFY] ${user.username}: error adding to thread: ${e.message}`);
        }

        // Send a reminder if the thread has been idle for too long
        await sendVerificationReminder(existingThread, user);

        // Only start/resume the verification flow if one isn't already active
        if (activeVerificationFlows.has(user.id)) {
          console.log(`[VERIFY] ${user.username}: flow already active, skipping`);
        } else {
          // Check if bot already sent the initial welcome message in this thread
          const botHasSentWelcome = await threadHasBotMessage(existingThread);

          if (!botHasSentWelcome) {
            console.log(`[VERIFY] ${user.username}: no welcome yet, starting name collection`);
            await setBotConfig(`verify_reminder:${user.id}`, String(Date.now()));
            await startNameCollectionFlow(existingThread, user, channel.guild);
          } else if (!user.eu_name) {
            console.log(`[VERIFY] ${user.username}: has welcome but no EU name, restarting name collection`);
            const handle = collectEuName(existingThread, user.id, {
              typerId: user.id,
              guild: channel.guild,
              onEnd: () => clearVerificationFlow(user.id),
            });
            replaceVerificationFlow(user.id, handle);
          } else {
            console.log(`[VERIFY] ${user.username}: has EU name "${user.eu_name}", resuming verification`);
            await resumeVerification(existingThread, user.id, channel.guild, {
              onEnd: () => clearVerificationFlow(user.id),
            });
          }
        }

        continue;
      }

      // Create new thread — private threads are only visible to added members
      console.log(`[VERIFY] ${user.username}: creating new verification thread`);
      const thread = await channel.threads.create({
        name: `${user.username}-verification`,
        autoArchiveDuration: 10080,
        reason: `Verification thread created for ${user.username}`,
        type: ChannelType.PrivateThread,
      });
      await thread.members.add(user.id);
      console.log(`[VERIFY] ${user.username}: created thread ${thread.id}, starting name collection`);

      // Seed the reminder cooldown so the user isn't nudged immediately
      await setBotConfig(`verify_reminder:${user.id}`, String(Date.now()));

      await startNameCollectionFlow(thread, user, channel.guild);
    } catch (e) {
      console.error(`[VERIFY] ${user.username}: UNHANDLED ERROR: ${e.message}`, e.stack);
    }
  }
  console.log(`[VERIFY] Finished processing ${unverifiedUsers.length} users`);
}

/**
 * Check if the bot has already sent a message in a thread.
 */
async function threadHasBotMessage(thread) {
  try {
    const messages = await thread.messages.fetch({ limit: 10 });
    return messages.some(m => m.author.id === client.user.id);
  } catch {
    return false;
  }
}

const VERIFICATION_REMINDER_INTERVAL_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * Send a periodic reminder in an idle verification thread.
 * Checks how long it has been since the last reminder (or thread creation)
 * and sends a contextual nudge if the thread has been idle too long.
 */
async function sendVerificationReminder(thread, user) {
  const configKey = `verify_reminder:${user.id}`;
  try {
    const lastReminder = await getBotConfig(configKey);
    const now = Date.now();

    if (lastReminder && (now - Number(lastReminder)) < VERIFICATION_REMINDER_INTERVAL_MS) {
      return; // Too soon for another reminder
    }

    // Check if the user has sent any message recently — if so, they're active, no nudge needed
    const messages = await thread.messages.fetch({ limit: 20 });
    const lastUserMsg = messages.find(m => m.author.id === user.id);
    if (lastUserMsg && (now - lastUserMsg.createdTimestamp) < VERIFICATION_REMINDER_INTERVAL_MS) {
      return;
    }

    // Don't send a reminder if the thread was just created (no bot messages yet)
    const botMessages = messages.filter(m => m.author.id === client.user.id);
    if (botMessages.size === 0) return;

    // Contextual reminder based on verification state
    let reminder;
    if (!user.eu_name) {
      reminder = `<@${user.id}> — Friendly reminder: please type your full Entropia Universe name here to begin verification. Make sure the capitalization and spacing exactly match your in-game name.`;
    } else {
      reminder = `<@${user.id}> — Reminder: a verification code was sent to you in Entropia Universe via PM or Mail. Please type the code here to complete verification. If you haven't received it, let a moderator know.`;
    }

    await thread.send(reminder);
    await setBotConfig(configKey, String(now));
    console.log(`Sent verification reminder to ${user.username} (eu_name: ${user.eu_name ? 'set' : 'not set'})`);
  } catch (e) {
    console.error(`Error sending verification reminder for ${user.username}: ${e.message}`);
  }
}

/**
 * Send welcome message and start EU name collection in a verification thread.
 */
async function startNameCollectionFlow(thread, user, guild) {
  try {
    await thread.send(`Hello <@${user.id}>, please type your full Entropia Universe name below to begin verification. Make sure the capitalization and spacing exactly match your in-game name.`);
  } catch (e) {
    console.error(`Failed to send welcome message to verification thread for ${user.username}: ${e.message}`);
    return;
  }

  const handle = collectEuName(thread, user.id, {
    typerId: user.id,
    guild,
    onEnd: () => clearVerificationFlow(user.id),
  });
  replaceVerificationFlow(user.id, handle);
}

/**
 * Handle a DirectApply change: apply immediately.
 * If a Discord thread exists (or needs to be created), close it with a reason
 * and post reward prompts before archiving.
 * On failure, set state to ApplyFailed and DM the admin with retry/discard buttons.
 */
async function handleDirectApply(change) {
  console.log(`Direct apply: ${change.entity} "${change.data.Name}" (change ${change.id})`);

  // Verify the author has admin privileges (defense in depth — API already validates)
  const author = await getUserById(change.author_id);
  if (!author?.administrator) {
    console.error(`DirectApply rejected: author ${change.author_id} is not an admin`);
    await setChangeState(change.id, 'Pending'); // Downgrade to regular review flow
    return;
  }

  // Fetch pre-change entity for reward diffing BEFORE applying
  const preChangeEntity = await fetchEntityForReward(change);

  const success = await applyChange(change);

  if (success) {
    await setChangeState(change.id, 'Approved');

    // Find or create a Discord thread for the closing message and rewards
    const channel = client.channels.cache.find(ch => ch.id === config.pendingChangesChannelId);
    let thread = null;
    let dmHandledByRewards = false;

    if (channel) {
      // Try to fetch existing thread
      if (change.thread_id) {
        thread = await channel.threads.fetch(change.thread_id).catch(_ => null);
        // Unarchive if needed so we can post to it
        if (thread?.archived) {
          try { await thread.setArchived(false); } catch {}
        }
      }

      // Create a thread if none exists
      if (!thread) {
        try {
          thread = await channel.threads.create({
            name: `[Approved] ${change.type}: ${change.data.Name.substring(0, 80)}`,
            autoArchiveDuration: 10080,
            reason: `Direct apply thread for change ${change.id}`,
          });
          await setChangeThreadId(change.id, thread.id);
        } catch (e) {
          console.error(`Failed to create thread for direct apply (change ${change.id}):`, e.message);
        }
      }
    }

    if (thread) {
      try {
        // Update thread name to show approved state
        if (change.thread_id) {
          await thread.setName(`[Approved] ${change.type}: ${change.data.Name.substring(0, 80)}`);
        }
        await thread.send(`This change was directly applied by <@${change.author_id}>.`);
      } catch (e) {
        console.error(`Failed to post direct apply message to thread (change ${change.id}):`, e.message);
      }

      // Evaluate and prompt for rewards in the thread, then archive
      // handleReward sends the combined approval+rewards DM when all prompts resolve
      dmHandledByRewards = await handleReward(client, thread, change, preChangeEntity);
      if (!dmHandledByRewards) {
        try { await thread.setArchived(true); } catch {}
      }
    }

    // Send approval-only DM if handleReward didn't handle it (no matching rules or no thread)
    if (!dmHandledByRewards) {
      const { sendChangeApprovalDm } = await import('./rewards.js');
      await sendChangeApprovalDm(client, change.author_id, {
        changeName: change.data.Name,
        changeType: change.type,
        entity: change.entity,
        rewards: [],
      });
    }
  } else {
    await setChangeState(change.id, 'ApplyFailed');
    try {
      const dmUser = await client.users.fetch(String(change.author_id));
      const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder()
          .setCustomId(`change_retry_${change.id}`)
          .setLabel('Retry')
          .setStyle(ButtonStyle.Success),
        new ButtonBuilder()
          .setCustomId(`change_discard_${change.id}`)
          .setLabel('Discard')
          .setStyle(ButtonStyle.Danger),
      );
      await dmUser.send({
        content: `Failed to apply change **${change.data.Name}** (${change.type} ${change.entity}). You can retry or discard this change.`,
        components: [row]
      });
    } catch (e) {
      console.error(`Failed to DM admin ${change.author_id}:`, e.message);
    }
  }

  // Update lastChangeCheck so this change isn't re-processed
  let newCheckTime = new Date(change.content_updated_at);
  newCheckTime.setMilliseconds(newCheckTime.getMilliseconds() + 1);
  setConfigValue('lastChangeCheck', newCheckTime.toISOString());
}

async function checkChanges() {
  const channel = client.channels.cache.find(channel => channel.id === config.pendingChangesChannelId);
  if (!channel) {
    console.error('Changes channel not found');
    return;
  }

  let lastCheck = new Date(getConfigValue('lastChangeCheck'));

  let changes = (await getOpenChanges(lastCheck)).sort((a, b) => new Date(a.content_updated_at).getTime() - new Date(b.content_updated_at).getTime());

  for (const change of changes) {
    // DirectApply: skip thread creation, apply immediately
    if (change.state === 'DirectApply') {
      await handleDirectApply(change);
      continue;
    }

    let thread = change.thread_id
      ? await channel.threads.fetch(change.thread_id).catch(_ => null)
      : null;

    const rawChangeId = change?.data?.Id;
    const apartmentId = change.entity === 'Apartment' && Number.isFinite(Number(rawChangeId))
      ? (Number(rawChangeId) > 300000 ? Number(rawChangeId) - 300000 : Number(rawChangeId))
      : rawChangeId;
    const fetchId = change.entity === 'Apartment' ? apartmentId : rawChangeId;
    const fetchUrl = `${process.env.API_URL}/${getEntityApiCollection(change.entity)}/${fetchId}`;
    console.log(`Fetching old object from: ${fetchUrl}`);
    
    let entity = await fetch(fetchUrl)
      .then(res => res.status === 404 ? Promise.resolve({}) : res.json())
      .catch(_ => null);

    // Fetch refining recipes for materials
    if (change.entity === 'Material' && entity && entity.Id) {
      const refiningUrl = `${process.env.API_URL}/refiningrecipes?Product=${entity.Id}`;
      console.log(`Fetching refining recipes from: ${refiningUrl}`);
      
      try {
        const refiningRecipes = await fetch(refiningUrl)
          .then(res => res.json())
          .catch(_ => []);
        entity.RefiningRecipes = refiningRecipes;
      } catch (error) {
        console.error(`Failed to fetch refining recipes for material ${entity.Id}:`, error);
        entity.RefiningRecipes = [];
      }
    }

    // Deep clone both before validation (validate mutates with removeAdditional)
    let validatedEntity = JSON.parse(JSON.stringify(entity));
    let validatedChange = JSON.parse(JSON.stringify(change.data));

    // Validate and strip extra properties from both sides
    validate(change.entity, validatedEntity);
    validate(change.entity, validatedChange);

    // Print side-by-side comparison for debugging
    printSideBySide(validatedEntity, validatedChange, 'Entity vs Change Data (validated)');

    let compareObject = compareJson(validatedEntity, validatedChange);
    console.log(`Comparison result for ${change.data.Name}:`, compareObject ? 'Changes detected' : 'No changes detected');

    if (!thread) {
      thread = await channel.threads.create({
        name: `[${getStateLabel(change.state)}] ${change.type}: ${change.data.Name.substring(0, 80)}`,
        autoArchiveDuration: 10080,
        reason: `Change thread created for change ${change.id}`,
        permissionOverwrites: [
          {
            id: channel.guild.roles.everyone.id,
            deny: ['VIEW_CHANNEL', 'SEND_MESSAGES'],
          },
        ],
      });
      await setChangeThreadId(change.id, thread.id);
      setConfigValue('lastChangeCheck', new Date().toISOString());

      const formatted = formatJsonForDiscord(compareObject);
      
      for (const message of formatted) {
        try {
          await thread.send(message);
        } catch (e) {
          console.error(`Failed to send message to thread ${thread.id} (${change.data.Name}): ${e.message}`);
          if (e.code === 50083) { // Thread is archived
            console.log(`Thread ${thread.id} is archived, skipping message.`);
            break;
          }
        }
      }
      try {
        const reviewerRoleId = getConfigValue('reviewerRoleId');
        const reviewerMention = reviewerRoleId ? ` <@&${reviewerRoleId}>` : '';
        await thread.send(`A new change has been submitted by <@${change.author_id}>.${reviewerMention} Please post proof to validate your changes and await approval.`);
      } catch (e) {
        console.error(`Failed to send submission message to thread ${thread.id} (${change.data.Name}): ${e.message}`);
      }

      // Render map image for Location/Area changes
      if ((change.entity === 'Area' || change.entity === 'Location') && change.data?.Properties?.Shape) {
        try {
          const planetData = await fetchPlanetData(change.data.Planet?.Name);
          if (planetData) {
            const mapImage = await renderMapChange(change.data, entity, planetData);
            if (mapImage) {
              await thread.send({ files: [{ attachment: mapImage, name: 'map-change.png' }] });
            }
          }
        } catch (e) {
          console.error(`Failed to render map image for thread ${thread.id}: ${e.message}`);
        }
      }

      const entityPath = getTypeLink(change.data.Name, change.entity, change.data.Planet?.Name ?? null);
      if (entityPath) {
        try {
          const baseUrl = `https://entropianexus.com${entityPath}`;
          const editUrl = change.type === 'Create'
            ? `${baseUrl}?mode=create&changeId=${change.id}`
            : `${baseUrl}?mode=edit&changeId=${change.id}`;
          const linkMsg = await thread.send(`**Edit:** ${editUrl}`);
          await linkMsg.pin().catch(e => console.error(`Failed to pin edit link in thread ${thread.id}: ${e.message}`));
        } catch (e) {
          console.error(`Failed to post edit link in thread ${thread.id}: ${e.message}`);
        }
      }
    }
    else {
      try {
        await thread.setName(`[${getStateLabel(change.state)}] ${change.type}: ${change.data.Name.substring(0, 80)}`);
      } catch (e) {
        console.error(`Failed to update thread name ${thread.id} (${change.data.Name}): ${e.message}`);
      }

      const formatted = formatJsonForDiscord(compareObject);
      
      for (const message of formatted) {
        try {
          await thread.send(message);
        } catch (e) {
          console.error(`Failed to send update message to thread ${thread.id} (${change.data.Name}): ${e.message}`);
          if (e.code === 50083) { // Thread is archived
            console.log(`Thread ${thread.id} is archived, skipping remaining messages.`);
            break;
          }
        }
      }
      // Render map image for Location/Area changes
      if ((change.entity === 'Area' || change.entity === 'Location') && change.data?.Properties?.Shape) {
        try {
          const planetData = await fetchPlanetData(change.data.Planet?.Name);
          if (planetData) {
            const mapImage = await renderMapChange(change.data, entity, planetData);
            if (mapImage) {
              await thread.send({ files: [{ attachment: mapImage, name: 'map-change.png' }] });
            }
          }
        } catch (e) {
          console.error(`Failed to render map image for thread ${thread.id}: ${e.message}`);
        }
      }

      try {
        const reviewerRoleId = getConfigValue('reviewerRoleId');
        const reviewerMention = reviewerRoleId ? ` <@&${reviewerRoleId}>` : '';
        await thread.send(`This change has been updated by <@${change.author_id}>.${reviewerMention}`);
      } catch (e) {
        console.error(`Failed to send update notification to thread ${thread.id} (${change.data.Name}): ${e.message}`);
      }

      let newCheckTime = new Date(change.content_updated_at);
      newCheckTime.setMilliseconds(newCheckTime.getMilliseconds() + 1);
      setConfigValue('lastChangeCheck', newCheckTime.toISOString());
    }

    // Add all reviewers to the thread
    if (change.state == 'Pending') {
      const reviewerRoleId = getConfigValue('reviewerRoleId');
      if (reviewerRoleId) {
        const guild = channel.guild;
        const role = guild.roles.cache.get(reviewerRoleId);
        if (role) {
          for (const [memberId] of role.members) {
            if (!thread.members.cache.has(memberId)) {
              try {
                await thread.members.add(memberId);
              } catch (e) {
                console.error(`Error adding reviewer ${memberId} to change thread (${thread.id}, ${change.data.Name}): ${e.message}`);
              }
            }
          }
        }
      }
    }
  }

  changes = await getDeletedChanges();

  for (const change of changes) {
    let thread = await channel.threads.fetch(change.thread_id).catch(_ => null);

    if (!thread) {
      await deleteChange(change.id);
      continue;
    }

    try {
      await thread.setName(`[${getStateLabel(change.state)}] ${change.type}: ${change.data.Name.substring(0, 80)}`);
    }
    catch (e) {
      console.error(`Failed to update deleted change thread name ${thread.id} (${change.data.Name}): ${e.message}`);
    }

    try {
      await thread.send('This change has been deleted and the thread will be archived.');
    } catch (e) {
      console.error(`Failed to send deletion message to thread ${thread.id} (${change.data.Name}): ${e.message}`);
    }
    
    try {
      await thread.setArchived(true);
    } catch (e) {
      console.error(`Failed to archive thread ${thread.id} (${change.data.Name}): ${e.message}`);
    }

    await deleteChange(change.id);
  }
}

async function syncReviewerRole() {
  const reviewerRoleId = getConfigValue('reviewerRoleId');
  if (!reviewerRoleId) {
    console.log('syncReviewerRole: No reviewerRoleId configured, skipping');
    return;
  }

  // Get guild through a cached channel (avoids guildId number precision loss)
  const channel = client.channels.cache.get(config.pendingChangesChannelId)
    || client.channels.cache.get(config.verifiedChannelId);
  if (!channel?.guild) {
    console.error('syncReviewerRole: Could not resolve guild from cached channels');
    return;
  }
  const guild = channel.guild;

  const role = guild.roles.cache.get(reviewerRoleId);
  if (!role) {
    console.error(`syncReviewerRole: Reviewer role ${reviewerRoleId} not found in guild`);
    return;
  }

  const grantedUserIds = new Set(await getUsersWithGrant('wiki.approve'));
  console.log(`syncReviewerRole: Found ${grantedUserIds.size} users with wiki.approve: [${[...grantedUserIds].join(', ')}]`);

  // Fetch only the specific members we need instead of the entire guild
  const idsToFetch = [...new Set([...grantedUserIds, ...role.members.keys()])];
  if (idsToFetch.length > 0) {
    try {
      await guild.members.fetch({ user: idsToFetch });
    } catch (e) {
      console.error('syncReviewerRole: Error fetching members, using cache:', e.message);
    }
  }

  const currentMembers = role.members;
  console.log(`syncReviewerRole: ${currentMembers.size} members currently have the role`);

  // Add role to users who should have it
  for (const userId of grantedUserIds) {
    const member = guild.members.cache.get(userId);
    if (!member) {
      console.log(`syncReviewerRole: User ${userId} not found in guild, skipping`);
      continue;
    }
    if (!member.roles.cache.has(reviewerRoleId)) {
      try {
        await member.roles.add(reviewerRoleId);
        console.log(`syncReviewerRole: Added reviewer role to ${member.user.username}`);
      } catch (e) {
        console.error(`syncReviewerRole: Failed to add role to ${userId}: ${e.message}`);
      }
    }
  }

  // Remove role from users who should not have it
  for (const [memberId, member] of currentMembers) {
    if (!grantedUserIds.has(memberId)) {
      try {
        await member.roles.remove(reviewerRoleId);
        console.log(`syncReviewerRole: Removed reviewer role from ${member.user.username}`);
      } catch (e) {
        console.error(`syncReviewerRole: Failed to remove role from ${memberId}: ${e.message}`);
      }
    }
  }
}

async function syncVerifiedRole() {
  const verifiedRoleId = getConfigValue('verifiedRoleId');
  if (!verifiedRoleId) return;

  const channel = client.channels.cache.get(config.verifiedChannelId);
  if (!channel?.guild) {
    console.error('syncVerifiedRole: Could not resolve guild');
    return;
  }
  const guild = channel.guild;

  const role = guild.roles.cache.get(verifiedRoleId);
  if (!role) {
    console.error(`syncVerifiedRole: Role ${verifiedRoleId} not found in guild`);
    return;
  }

  const allUsers = await getUsers();
  const verifiedUsers = allUsers.filter(u => u.verified);

  // Fetch members in batches (Discord limits to 100 per request)
  const BATCH_SIZE = 100;
  const userIds = verifiedUsers.map(u => u.id);
  for (let i = 0; i < userIds.length; i += BATCH_SIZE) {
    const batch = userIds.slice(i, i + BATCH_SIZE);
    try {
      await guild.members.fetch({ user: batch });
    } catch (e) {
      console.error('syncVerifiedRole: Batch fetch error:', e.message);
    }
  }

  // Add role to verified users who are missing it (add-only, never remove)
  let added = 0;
  for (const user of verifiedUsers) {
    const member = guild.members.cache.get(user.id);
    if (!member) continue;
    if (member.roles.cache.has(verifiedRoleId)) continue;

    try {
      await member.roles.add(verifiedRoleId);
      added++;
      console.log(`syncVerifiedRole: Added verified role to ${member.user.username}`);
    } catch (e) {
      console.error(`syncVerifiedRole: Failed to add role to ${user.id}: ${e.message}`);
    }
  }

  if (added > 0) {
    console.log(`syncVerifiedRole: Added role to ${added} member(s)`);
  }
}

function formatJsonForDiscord(json) {
  if (json === null) {
    return ['```\nNo changes detected\n```'];
  }

  const lines = [];
  formatDiffLines(json, lines, 0);
  const formatted = lines.join('\n');

  // Split into chunks respecting Discord's 2000 char limit
  const chunks = [];
  const allLines = formatted.split('\n');
  let currentChunk = '';
  for (const line of allLines) {
    if (currentChunk.length + line.length + 12 > 2000) {
      chunks.push(currentChunk);
      currentChunk = '';
    }
    currentChunk += line + '\n';
  }
  if (currentChunk.length > 0) {
    chunks.push(currentChunk);
  }

  return chunks.map(chunk => '```diff\n' + chunk + '```');
}

/**
 * Recursively format a compareJson result into diff-style lines.
 * - Context keys (unchanged): "  key: value"
 * - Changed primitives ("old -> new"): "- key: old" / "+ key: new"
 * - Nested objects: header line + indented children
 * - Array items: prefixed with _status indicator
 */
function formatDiffLines(obj, lines, depth) {
  const pad = '  '.repeat(depth);

  if (Array.isArray(obj)) {
    for (const item of obj) {
      if (typeof item === 'string') {
        // Primitive change in array: "old -> new"
        const arrow = item.indexOf(' -> ');
        if (arrow >= 0) {
          lines.push(`- ${pad}${item.substring(0, arrow)}`);
          lines.push(`+ ${pad}${item.substring(arrow + 4)}`);
        } else {
          lines.push(`  ${pad}${item}`);
        }
      } else if (typeof item === 'object' && item !== null) {
        const status = item._status;
        const label = item.Name || item.Tier || '';
        const prefix = status === 'added' ? '+' : status === 'removed' ? '-' : ' ';

        if (status === 'added' || status === 'removed') {
          // Show the whole sub-object with +/- prefix
          if (label) lines.push(`${prefix} ${pad}${label}:`);
          formatDiffLinesFlat(item, lines, depth + 1, prefix);
        } else {
          // Changed item — show label as context, diff the fields
          if (label) lines.push(`  ${pad}${label}:`);
          formatDiffLines(item, lines, depth + 1);
        }
      }
    }
    return;
  }

  for (const [key, value] of Object.entries(obj)) {
    if (key === '_status') continue;

    if (typeof value === 'string') {
      const arrow = value.indexOf(' -> ');
      if (arrow >= 0) {
        // Changed value
        lines.push(`- ${pad}${key}: ${value.substring(0, arrow)}`);
        lines.push(`+ ${pad}${key}: ${value.substring(arrow + 4)}`);
      } else {
        // Context key (unchanged)
        lines.push(`  ${pad}${key}: ${value}`);
      }
    } else if (Array.isArray(value)) {
      lines.push(`  ${pad}${key}:`);
      formatDiffLines(value, lines, depth + 1);
    } else if (typeof value === 'object' && value !== null) {
      lines.push(`  ${pad}${key}:`);
      formatDiffLines(value, lines, depth + 1);
    } else if (value != null) {
      lines.push(`  ${pad}${key}: ${value}`);
    }
  }
}

/** Format all fields of an object with a fixed prefix (+/-) for added/removed items. */
function formatDiffLinesFlat(obj, lines, depth, prefix) {
  const pad = '  '.repeat(depth);
  for (const [key, value] of Object.entries(obj)) {
    if (key === '_status' || key === 'Name' || key === 'Tier') continue;
    if (typeof value === 'object' && value !== null) {
      lines.push(`${prefix} ${pad}${key}:`);
      formatDiffLinesFlat(value, lines, depth + 1, prefix);
    } else if (value != null) {
      lines.push(`${prefix} ${pad}${key}: ${value}`);
    }
  }
}


async function checkFlights() {
  const flightsChannelId = config.flightsChannelId;
  if (!flightsChannelId) return;

  const channel = client.channels.cache.get(flightsChannelId);
  if (!channel) {
    console.error('Flights channel not found');
    return;
  }

  try {
    // 1. Create threads for flights that entered boarding/running without a thread
    const flightsNeedingThread = await getFlightsNeedingThread();
    for (const flight of flightsNeedingThread) {
      try {
        const stops = flight.route_stops || [];
        const routeSummary = stops.map(s => s.name).join(' → ');
        const departureTime = new Date(flight.scheduled_departure).toLocaleString('en-US', {
          month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false
        });

        // Create a PRIVATE thread
        const thread = await channel.threads.create({
          name: `✈ ${flight.service_title} - ${departureTime}`.substring(0, 100),
          autoArchiveDuration: 1440, // 24 hours
          reason: `Flight thread for flight #${flight.id}`,
          type: ChannelType.PrivateThread,
        });

        await setFlightThreadId(flight.id, thread.id);

        // Build the initial message
        const pilots = typeof flight.pilots === 'string' ? JSON.parse(flight.pilots) : (flight.pilots || []);
        const pilotMentions = pilots.map(p => `<@${p.user_id}>`).join(', ');

        let initialMessage = `**${flight.service_title}** — Flight #${flight.id}\n`;
        initialMessage += `**Route:** ${routeSummary || 'No route set'}\n`;
        initialMessage += `**Route Type:** ${flight.route_type === 'flexible' ? 'Flexible' : 'Fixed'}\n`;
        initialMessage += `**Scheduled Departure:** ${departureTime}\n`;
        initialMessage += `**Status:** ${flight.status === 'boarding' ? 'Boarding' : 'In Flight'}\n\n`;
        initialMessage += `**Started by:** <@${flight.provider_user_id}> (${flight.provider_username})\n`;
        if (flight.owner_user_id && flight.owner_user_id.toString() !== flight.provider_user_id.toString()) {
          initialMessage += `**Owner:** <@${flight.owner_user_id}>\n`;
        }
        if (pilots.length > 0) {
          initialMessage += `**Pilots:** ${pilotMentions}\n`;
        }

        await thread.send(initialMessage);

        // Add the provider to the thread
        try {
          await thread.members.add(flight.provider_user_id.toString());
        } catch (e) {
          console.error(`Failed to add provider to flight thread: ${e.message}`);
        }

        // Add owner to the thread (if different from provider)
        if (flight.owner_user_id && flight.owner_user_id.toString() !== flight.provider_user_id.toString()) {
          try {
            await thread.members.add(flight.owner_user_id.toString());
          } catch (e) {
            console.error(`Failed to add owner to flight thread: ${e.message}`);
          }
        }

        // Add pilots to the thread (if different from provider/owner)
        for (const pilot of pilots) {
          if (pilot.user_id.toString() !== flight.provider_user_id.toString() &&
              (!flight.owner_user_id || pilot.user_id.toString() !== flight.owner_user_id.toString())) {
            try {
              await thread.members.add(pilot.user_id.toString());
            } catch (e) {
              console.error(`Failed to add pilot ${pilot.username} to flight thread: ${e.message}`);
            }
          }
        }

        console.log(`Created private flight thread for flight #${flight.id}: ${thread.name}`);
      } catch (e) {
        console.error(`Error creating thread for flight #${flight.id}:`, e);
      }
    }

    // 2. Add accepted passengers to their flight threads
    const pendingAdds = await getCheckinsPendingThreadAdd();
    for (const checkin of pendingAdds) {
      try {
        const thread = await channel.threads.fetch(checkin.discord_thread_id.toString()).catch(() => null);
        if (!thread) {
          await markCheckinAddedToThread(checkin.id);
          continue;
        }

        await thread.members.add(checkin.discord_user_id.toString());
        await thread.send(`✅ <@${checkin.discord_user_id}> has been accepted and joined the flight!`);
        await markCheckinAddedToThread(checkin.id);

        console.log(`Added ${checkin.username} to flight #${checkin.flight_id} thread`);
      } catch (e) {
        console.error(`Error adding checkin #${checkin.id} to thread:`, e);
      }
    }

    // 3. Send route state change notifications
    const lastFlightCheck = config.lastFlightStateCheck || new Date(0).toISOString();
    const stateChanges = await getUnnotifiedFlightStateChanges(lastFlightCheck);

    let latestChange = lastFlightCheck;
    for (const change of stateChanges) {
      try {
        const thread = await channel.threads.fetch(change.discord_thread_id.toString()).catch(() => null);
        if (!thread) continue;

        let message = '';
        const stops = typeof change.route_stops === 'string'
          ? JSON.parse(change.route_stops)
          : (change.route_stops || []);
        const currentState = change.current_state;
        const currentStopIndex = change.current_stop_index || 0;

        // Helper to get stop name
        const getStopName = (index) => stops[index]?.name || `Stop #${index + 1}`;


        if (change.new_state === 'boarding' && change.previous_state === 'scheduled') {
          // Boarding started
          message = `**Boarding has started!**\n\n`;
          message += `Passengers with accepted check-ins will be added to this thread.`;
        } else if (change.new_state === 'running' && change.previous_state === 'boarding') {
          // Flight just started - first warp initiated
          const firstStop = getStopName(0);
          const secondStop = stops.length > 1 ? getStopName(1) : null;
          message = `**The flight has started!**\n`;
          message += `Currently at **${firstStop}**`;
          if (secondStop) {
            message += `, preparing to warp to **${secondStop}**.`;
          } else {
            message += `.`;
          }
        } else if (change.new_state === 'running' && change.previous_state === 'running') {
          // Warp/dock event - check current_state to determine what happened
          if (currentState && currentState.startsWith('warp_to_')) {
            // Entered warp
            const targetStopNum = parseInt(currentState.split('_')[2]);
            const targetStop = getStopName(targetStopNum);
            const fromStop = targetStopNum > 0 ? getStopName(targetStopNum - 1) : getStopName(0);
            message = `**Warping** from **${fromStop}** to **${targetStop}**...`;
          } else if (currentState && currentState.startsWith('at_stop_')) {
            // Docked at a stop
            const stopNum = parseInt(currentState.split('_')[2]);
            const arrivedAt = getStopName(stopNum);
            message = `**Docked at ${arrivedAt}!**`;

            // Show remaining route if there are more stops
            if (stopNum < stops.length - 1) {
              const remainingStops = stops.slice(stopNum + 1).map(s => s.name || 'Unknown').join(' → ');
              message += `\nNext stops: → ${remainingStops}`;
            }
          }
        } else if (change.new_state === 'completed') {
          const finalStop = stops.length > 0 ? getStopName(stops.length - 1) : 'destination';
          message = `**Flight completed!** Arrived at **${finalStop}**.\n\n`;
          message += `Thank you for flying with us! You will be removed from this thread in 5 minutes.`;
          // Mark completion time for later kick
          await setFlightCompletedAt(change.flight_id);
        } else if (change.new_state === 'cancelled') {
          message = `**Flight cancelled.**\n\n`;
          message += `Your ticket has been refunded or your remaining uses have been restored.\n`;
          message += `You will be removed from this thread in 5 minutes.`;
          await setFlightCompletedAt(change.flight_id);
        } else if (change.new_state === 'route_changed') {
          // Route was modified - show new route with traveled portion marked
          message = `**Route has been updated!**\n\n`;
          message += `**New Route:**\n`;

          const currentIdx = change.current_stop_index || 0;
          const routeDisplay = stops.map((stop, i) => {
            const name = stop.name || `Stop #${i + 1}`;
            if (i < currentIdx) {
              return `~~${name}~~`; // Visited
            } else if (i === currentIdx) {
              return `**${name}** (current)`; // Current
            }
            return `${name}`; // Upcoming
          }).join('\n');

          message += routeDisplay;
        }

        if (message) {
          await thread.send(message);
        }

        if (new Date(change.changed_at) > new Date(latestChange)) {
          latestChange = change.changed_at;
        }
      } catch (e) {
        console.error(`Error sending state change notification for flight #${change.flight_id}:`, e);
      }
    }

    if (latestChange !== lastFlightCheck) {
      const t = new Date(latestChange);
      t.setMilliseconds(t.getMilliseconds() + 1);
      setConfigValue('lastFlightStateCheck', t.toISOString());
    }

    // 4. Kick customers and archive threads for flights completed 5+ minutes ago
    const flightsToKick = await getFlightsReadyForCustomerKick();
    for (const flight of flightsToKick) {
      try {
        const thread = await channel.threads.fetch(flight.discord_thread_id.toString()).catch(() => null);
        if (!thread) {
          await clearFlightThreadId(flight.id);
          continue;
        }

        // Get all accepted check-ins for this flight
        const checkins = await getFlightAcceptedCheckins(flight.id);

        // Remove customers from thread
        for (const checkin of checkins) {
          try {
            await thread.members.remove(checkin.discord_user_id.toString());
            console.log(`Removed ${checkin.username} from flight #${flight.id} thread`);
          } catch (e) {
            // User might have left already
            console.log(`Could not remove ${checkin.username} from thread: ${e.message}`);
          }
        }

        // Archive the thread
        if (!thread.archived) {
          await thread.send(`This flight thread is now being archived.`);
          await thread.setArchived(true);
          console.log(`Archived thread for flight #${flight.id}`);
        }

        await clearFlightThreadId(flight.id);
      } catch (e) {
        console.error(`Error kicking customers/archiving thread for flight #${flight.id}:`, e);
      }
    }
  } catch (e) {
    console.error('Error in checkFlights:', e);
  }
}

async function checkRescheduleNotifications() {
  try {
    const notifications = await getPendingRescheduleNotifications();

    for (const notification of notifications) {
      try {
        // Fetch the Discord user
        const user = await client.users.fetch(notification.discord_user_id);
        if (!user) {
          console.error(`User ${notification.discord_user_id} not found for reschedule notification #${notification.id}`);
          await markRescheduleNotificationSent(notification.id); // Mark as sent to avoid retrying
          continue;
        }

        // Format the dates
        const oldDate = new Date(notification.old_departure).toLocaleString('en-US', {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          timeZoneName: 'short'
        });
        const newDate = new Date(notification.new_departure).toLocaleString('en-US', {
          weekday: 'short',
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          timeZoneName: 'short'
        });

        // Send DM
        const message = `**Flight Rescheduled**\n\n` +
          `Your check-in for **${notification.service_title}** has been cancelled because the flight was rescheduled.\n\n` +
          `**Original departure:** ${oldDate}\n` +
          `**New departure:** ${newDate}\n\n` +
          `You'll need to check in again for the new departure time if you still wish to join this flight.\n\n`;

        await user.send(message);
        console.log(`Sent reschedule notification to ${notification.username} (${notification.discord_user_id})`);

        // Mark as sent
        await markRescheduleNotificationSent(notification.id);
      } catch (e) {
        console.error(`Error sending reschedule notification #${notification.id} to user ${notification.discord_user_id}:`, e);
        // If it's a DM permission error, mark as sent to avoid retry spam
        if (e.code === 50007) {
          console.error(`Cannot send DM to user ${notification.discord_user_id}, marking as sent`);
          await markRescheduleNotificationSent(notification.id);
        }
      }
    }
  } catch (e) {
    console.error('Error in checkRescheduleNotifications:', e);
  }
}

async function checkRentalDmNotifications() {
  try {
    const notifications = await getPendingRentalDmNotifications();

    for (const n of notifications) {
      try {
        const user = await client.users.fetch(n.discord_user_id);
        if (!user) {
          console.error(`User ${n.discord_user_id} not found for rental DM notification #${n.id}`);
          await markRentalDmNotificationSent(n.id);
          continue;
        }

        const startDate = new Date(n.start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const endDate = new Date(n.end_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

        let message = `**New Rental Request**\n\n` +
          `**${n.requester_name}** wants to rent your **${n.offer_title}**.\n\n` +
          `**Period:** ${startDate} – ${endDate} (${n.total_days} day${n.total_days !== 1 ? 's' : ''})\n` +
          `**Total:** ${parseFloat(n.total_price).toFixed(2)} PED\n`;

        if (parseFloat(n.deposit) > 0) {
          message += `**Deposit:** ${parseFloat(n.deposit).toFixed(2)} PED\n`;
        }

        message += `\nView and respond: https://entropianexus.com/market/rental/${n.offer_id}/edit`;

        await user.send(message);
        console.log(`Sent rental DM notification to ${n.discord_user_id} for offer #${n.offer_id}`);

        await markRentalDmNotificationSent(n.id);
      } catch (e) {
        console.error(`Error sending rental DM notification #${n.id} to user ${n.discord_user_id}:`, e);
        if (e.code === 50007) {
          console.error(`Cannot send DM to user ${n.discord_user_id}, marking as sent`);
          await markRentalDmNotificationSent(n.id);
        }
      }
    }
  } catch (e) {
    console.error('Error in checkRentalDmNotifications:', e);
  }
}

async function cleanupStaleUnverifiedUsers() {
  const staleUsers = await getStaleUnverifiedUsers();
  if (staleUsers.length === 0) return;

  console.log(`[CLEANUP] Found ${staleUsers.length} stale unverified user(s)`);

  for (const user of staleUsers) {
    const txClient = await startUsersTransaction();
    try {
      const deleted = await deleteUnverifiedUser(user.id, txClient);
      if (deleted) {
        await commitTransaction(txClient);
        console.log(`[CLEANUP] Deleted: ${deleted.username} (${deleted.id}), left at ${user.left_server_at}`);
      } else {
        await rollbackTransaction(txClient);
        console.log(`[CLEANUP] Skipped: ${user.username} (${user.id}) — safety check`);
      }
    } catch (error) {
      await rollbackTransaction(txClient);
      console.error(`[CLEANUP] Error deleting ${user.username} (${user.id}):`, error);
    }
  }
}

async function runScheduled(label, fn) {
  try {
    await fn();
  } catch (error) {
    console.error(`Error in scheduled task: ${label}`, error);
    await notifyModerators({
      title: 'Scheduled Task Error',
      error,
      context: label
    });
  }
}

setInterval(() => runScheduled('checkUnverifiedUsers', checkUnverifiedUsers), 1 * 60 * 1000);
setInterval(() => runScheduled('checkChanges', checkChanges), 1 * 15 * 1000);
setInterval(() => runScheduled('checkFlights', checkFlights), 30 * 1000);
setInterval(() => runScheduled('checkRescheduleNotifications', checkRescheduleNotifications), 30 * 1000);
setInterval(() => runScheduled('checkRentalDmNotifications', checkRentalDmNotifications), 30 * 1000);
setInterval(() => runScheduled('checkTradeRequests', checkTradeRequests), 15 * 1000);
setInterval(() => runScheduled('syncReviewerRole', syncReviewerRole), 5 * 60 * 1000);
setInterval(() => runScheduled('syncVerifiedRole', syncVerifiedRole), 5 * 60 * 1000);
setInterval(() => runScheduled('checkAuctions', () => checkAuctions(client, config)), 30 * 1000);
setInterval(() => runScheduled('refreshAuctionColors', () => refreshAuctionColors(client, config)), 5 * 60 * 1000);
setInterval(() => runScheduled('cleanupStaleUnverifiedUsers', cleanupStaleUnverifiedUsers), 60 * 60 * 1000);

// ---- Content Creator Notifications ----

const CREATOR_LIVE_COOLDOWN_MS = 4 * 60 * 60 * 1000; // 4 hours

async function checkContentCreators() {
  const creatorsChannelId = config.creatorsChannelId;
  if (!creatorsChannelId) return;

  const channel = client.channels.cache.get(creatorsChannelId);
  if (!channel) {
    console.error('Creators channel not found');
    return;
  }

  const creators = await getActiveContentCreators();

  for (const creator of creators) {
    if (!creator.cached_data) continue;

    try {
      if (creator.platform === 'twitch') {
        await checkTwitchLive(channel, creator);
      } else if (creator.platform === 'youtube') {
        await checkYouTubeVideos(channel, creator);
      }
    } catch (e) {
      console.error(`Error checking creator ${creator.name} (${creator.platform}):`, e);
    }
  }
}

async function checkTwitchLive(channel, creator) {
  const { cached_data } = creator;
  if (!cached_data.isLive) return;

  const configKey = `creator_live_notified:${creator.id}`;
  const lastNotified = await getBotConfig(configKey);

  if (lastNotified && (Date.now() - Number(lastNotified)) < CREATOR_LIVE_COOLDOWN_MS) {
    return; // Cooldown active
  }

  const displayName = cached_data.displayName || creator.name;
  const embed = new EmbedBuilder()
    .setColor(0x9146FF)
    .setAuthor({
      name: `${displayName} is live on Twitch!`,
      iconURL: cached_data.avatar || undefined,
      url: creator.channel_url
    })
    .setTitle(cached_data.streamTitle || 'Live Stream')
    .setURL(creator.channel_url);

  if (cached_data.streamThumbnail) {
    // Cache-bust the thumbnail so Discord doesn't show a stale preview
    embed.setImage(`${cached_data.streamThumbnail}?t=${Date.now()}`);
  }

  const fields = [];
  if (cached_data.gameName) fields.push({ name: 'Game', value: cached_data.gameName, inline: true });
  if (cached_data.viewerCount != null) fields.push({ name: 'Viewers', value: String(cached_data.viewerCount), inline: true });
  if (fields.length > 0) embed.addFields(fields);

  await channel.send({ embeds: [embed] });
  await setBotConfig(configKey, String(Date.now()));
  console.log(`Sent live notification for ${creator.name} (Twitch)`);
}

async function checkYouTubeVideos(channel, creator) {
  const { cached_data } = creator;
  // Prefer playlist videos when configured — channel feed may include streams
  const latestVideo = creator.youtube_playlist_id
    ? cached_data.playlistVideos?.[0]
    : cached_data.recentVideos?.[0] || cached_data.latestVideo;
  if (!latestVideo?.videoId) return;

  const configKey = `creator_yt_latest:${creator.id}`;
  const lastVideoId = await getBotConfig(configKey);

  if (!lastVideoId) {
    // First run — store current video ID without notifying
    await setBotConfig(configKey, latestVideo.videoId);
    return;
  }

  if (lastVideoId === latestVideo.videoId) return; // No new video

  // Only notify for videos published within the last 48 hours
  const MAX_VIDEO_AGE_MS = 48 * 60 * 60 * 1000;
  if (latestVideo.publishedAt) {
    const publishedAge = Date.now() - new Date(latestVideo.publishedAt).getTime();
    if (publishedAge > MAX_VIDEO_AGE_MS) {
      // Old video — update stored ID silently (e.g. playlist reorder)
      await setBotConfig(configKey, latestVideo.videoId);
      return;
    }
  }

  const channelName = cached_data.channelName || creator.name;
  const embed = new EmbedBuilder()
    .setColor(0xFF0000)
    .setAuthor({
      name: `${channelName} posted a new video!`,
      iconURL: cached_data.channelAvatar || undefined,
      url: creator.channel_url
    })
    .setTitle(latestVideo.title)
    .setURL(`https://www.youtube.com/watch?v=${latestVideo.videoId}`);

  if (latestVideo.thumbnail) {
    embed.setImage(latestVideo.thumbnail);
  }

  await channel.send({ embeds: [embed] });
  await setBotConfig(configKey, latestVideo.videoId);
  console.log(`Sent new video notification for ${creator.name} (YouTube): ${latestVideo.title}`);
}

setInterval(() => runScheduled('checkContentCreators', checkContentCreators), 60 * 1000);

// ---- Trade Request Thread Management ----

function formatTradeItem(item) {
  if (item.markup == null) return '';
  const mu = Number(item.markup);
  const markupStr = item.markup_type === 'absolute'
    ? `@ +${mu.toFixed(2)} PED`
    : `@ ${mu.toFixed(2)}%`;

  if (item.unit_tt != null) {
    const unitTT = Number(item.unit_tt);
    const qty = item.quantity || 1;
    const totalTT = unitTT * qty;
    const totalCost = item.markup_type === 'absolute'
      ? (unitTT + mu) * qty
      : unitTT * (mu / 100) * qty;
    return ` ${markupStr} \u2014 TT: ${totalTT.toFixed(2)} PED, Total: ${totalCost.toFixed(2)} PED`;
  }

  return ` ${markupStr}`;
}

let lastTradeItemCheck = new Date();

async function checkTradeRequests() {
  const tradeChannelId = config.tradeChannelId;
  if (!tradeChannelId) return;

  const channel = client.channels.cache.get(tradeChannelId);
  if (!channel) {
    console.error('Trade channel not found');
    return;
  }

  // 1. Create threads for pending trade requests
  const pending = await getPendingTradeRequests();
  const newlyCreatedIds = new Set();
  for (const req of pending) {
    try {
      const items = await getTradeRequestItems(req.id);
      const requesterName = req.requester_name || req.requester_username || 'Unknown';
      const targetName = req.target_name || req.target_username || 'Unknown';

      const thread = await channel.threads.create({
        name: `Trade: ${requesterName} \u2194 ${targetName}`.substring(0, 100),
        autoArchiveDuration: 1440,
        reason: `Trade request #${req.id}`,
        type: ChannelType.PrivateThread,
      });

      await setTradeRequestThread(req.id, thread.id);

      // Build initial message with item list
      let msg = `**Trade Request #${req.id}**\n`;
      msg += `<@${req.requester_id}> wants to trade with <@${req.target_id}>\n`;
      if (req.planet) msg += `**Planet:** ${req.planet}\n`;
      msg += `\n**Items:**\n`;
      for (const item of items) {
        const side = item.side === 'SELL' ? 'Buy' : 'Sell';
        msg += `- ${side} ${item.quantity}x **${item.item_name}**${formatTradeItem(item)}\n`;
      }
      msg += `\nUse this thread to negotiate. Type \`/done\` when finished to close the trade.`;

      await thread.send(msg);

      // Add both users to the thread
      try { await thread.members.add(req.requester_id.toString()); } catch (e) {
        console.error(`Failed to add requester to trade thread: ${e.message}`);
      }
      try { await thread.members.add(req.target_id.toString()); } catch (e) {
        console.error(`Failed to add target to trade thread: ${e.message}`);
      }

      newlyCreatedIds.add(req.id);
      console.log(`Created trade thread for request #${req.id}: ${thread.name}`);
    } catch (e) {
      console.error(`Error creating trade thread for request #${req.id}:`, e);
    }
  }

  // 2. Announce new items added to existing active trade threads (skip newly created ones — those items were already in the initial message)
  const requestsWithNewItems = await getActiveTradeRequestsWithNewItems(lastTradeItemCheck);
  for (const req of requestsWithNewItems) {
    if (newlyCreatedIds.has(req.id)) continue;
    try {
      const newItems = await getNewTradeRequestItems(req.id, lastTradeItemCheck);
      if (newItems.length === 0) continue;

      const thread = await channel.threads.fetch(req.discord_thread_id).catch(() => null);
      if (!thread) continue;

      let msg = `**New items added to trade:**\n`;
      for (const item of newItems) {
        const side = item.side === 'SELL' ? 'Buy' : 'Sell';
        msg += `- ${side} ${item.quantity}x **${item.item_name}**${formatTradeItem(item)}\n`;
      }
      await thread.send(msg);
    } catch (e) {
      console.error(`Error announcing new trade items for request #${req.id}:`, e);
    }
  }
  lastTradeItemCheck = new Date();

  // 3. Send warnings for inactive trades (18h+)
  const warnable = await getWarnableTradeRequests();
  for (const req of warnable) {
    try {
      if (!req.discord_thread_id) continue;
      const thread = await channel.threads.fetch(req.discord_thread_id).catch(() => null);
      if (!thread) continue;

      await thread.send(
        `\u26a0\ufe0f **Inactivity Warning** — This trade has been inactive for 18+ hours. ` +
        `Send a message to keep it active, or use \`/done\` to close it. ` +
        `This thread will be automatically closed after 24 hours of inactivity.`
      );
      await markWarningSent(req.id);
      console.log(`Sent inactivity warning for trade request #${req.id}`);
    } catch (e) {
      console.error(`Error sending trade warning for request #${req.id}:`, e);
    }
  }

  // 4. Expire inactive trades (24h+)
  const expirable = await getExpirableTradeRequests();
  for (const req of expirable) {
    try {
      await updateTradeRequestStatus(req.id, 'expired');

      if (req.discord_thread_id) {
        const thread = await channel.threads.fetch(req.discord_thread_id).catch(() => null);
        if (thread) {
          await thread.send(
            `\u274c **Trade Expired** — This trade was automatically closed due to 24 hours of inactivity.`
          );
          await thread.setLocked(true).catch(() => {});
          await thread.setArchived(true).catch(() => {});
        }
      }
      console.log(`Expired trade request #${req.id}`);
    } catch (e) {
      console.error(`Error expiring trade request #${req.id}:`, e);
    }
  }
}

// Track activity in trade threads
client.on(Events.MessageCreate, async (message) => {
  if (message.author.bot) return;
  if (!message.channel.isThread()) return;

  try {
    const tradeRequest = await findTradeRequestByThread(message.channel.id);
    if (tradeRequest && tradeRequest.status === 'active') {
      await updateLastActivity(tradeRequest.id);
    }
  } catch (e) {
    // Silently ignore — not every thread message is a trade thread
  }
});

// Re-add unverified users who leave their verification thread and restart their flow
client.on(Events.ThreadMembersUpdate, async (addedMembers, removedMembers, thread) => {
  // Only care about verification threads in the verified channel
  if (thread.parentId !== config.verifiedChannelId) return;
  if (!thread.name.endsWith('-verification')) return;

  for (const [memberId] of removedMembers) {
    // Ignore the bot itself
    if (memberId === client.user.id) continue;

    try {
      const user = await getUserById(memberId);
      if (user && !user.verified) {
        // Unarchive the thread if it was archived
        if (thread.archived) {
          await thread.setArchived(false);
        }
        await thread.members.add(memberId);
        console.log(`Re-added unverified user ${user.username} to their verification thread.`);

        // Restart the verification flow if it isn't running
        if (!activeVerificationFlows.has(memberId)) {
          if (!user.eu_name) {
            const handle = collectEuName(thread, user.id, {
              typerId: user.id,
              guild: thread.guild,
              onEnd: () => clearVerificationFlow(user.id),
            });
            replaceVerificationFlow(user.id, handle);
          } else {
            await resumeVerification(thread, user.id, thread.guild, {
              onEnd: () => clearVerificationFlow(user.id),
            });
          }
        }
      }
    } catch (e) {
      console.error(`Error re-adding user ${memberId} to verification thread: ${e.message}`);
    }
  }
});

// Mark unverified users as left when they leave the Discord server
client.on(Events.GuildMemberRemove, async (member) => {
  try {
    const user = await getUserById(member.id);
    if (user && !user.verified) {
      await setUserLeftServer(user.id);
      console.log(`[CLEANUP] ${member.user.username}: left guild, marked left_server_at`);
    }
  } catch (e) {
    console.error(`[CLEANUP] Error handling member remove for ${member.id}:`, e);
  }
});

// ---- Service Request Thread/DM Management ----

async function checkServiceRequests() {
  const servicesChannelId = config.servicesChannelId;
  if (!servicesChannelId) return;

  const channel = client.channels.cache.get(servicesChannelId);
  if (!channel) {
    console.error('Services channel not found');
    return;
  }

  const pending = await getPendingServiceRequests();
  for (const req of pending) {
    try {
      const isQuestion = req.service_notes?.startsWith('[QUESTION]');
      const isFlightRequest = req.service_notes?.startsWith('[FLIGHT_REQUEST]');
      const pilots = typeof req.pilots === 'string' ? JSON.parse(req.pilots) : (req.pilots || []);
      const requesterName = req.requester_name || req.requester_username || 'Unknown';

      // Build the message content
      let content = '';
      if (isQuestion) {
        const questionText = req.service_notes.replace('[QUESTION]', '').trim();
        content = `**Question for ${req.service_title}**\n`;
        content += `From: <@${req.requester_id}> (${requesterName})\n\n`;
        content += `> ${questionText}\n`;
      } else if (isFlightRequest) {
        const details = req.service_notes.replace('[FLIGHT_REQUEST]', '').trim();
        content = `**Flight Request for ${req.service_title}**\n`;
        content += `From: <@${req.requester_id}> (${requesterName})\n\n`;
        content += `${details}\n`;
      } else {
        content = `**Service Request for ${req.service_title}**\n`;
        content += `From: <@${req.requester_id}> (${requesterName})\n`;
        if (req.service_notes) content += `\n> ${req.service_notes}\n`;
      }

      // Build staff mentions
      const staffMentions = [`<@${req.manager_id}>`];
      if (req.owner_user_id && req.owner_user_id.toString() !== req.manager_id.toString()) {
        staffMentions.push(`<@${req.owner_user_id}>`);
      }
      for (const pilot of pilots) {
        if (pilot.user_id.toString() !== req.manager_id.toString() &&
            (!req.owner_user_id || pilot.user_id.toString() !== req.owner_user_id.toString())) {
          staffMentions.push(`<@${pilot.user_id}>`);
        }
      }

      // If the service has its own Discord server, send DMs instead of creating a thread
      if (req.discord_code) {
        const dmContent = content + `\n**Staff:** ${staffMentions.join(', ')}`;

        // Build action buttons for flight requests
        const dmComponents = [];
        if (isFlightRequest) {
          const row = new ActionRowBuilder().addComponents(
            new ButtonBuilder()
              .setCustomId(`svc_req_accept_${req.id}`)
              .setLabel('Accept Request')
              .setStyle(ButtonStyle.Success),
            new ButtonBuilder()
              .setCustomId(`svc_req_decline_${req.id}`)
              .setLabel('Decline Request')
              .setStyle(ButtonStyle.Danger),
          );
          dmComponents.push(row);
        }

        // Collect unique user IDs to DM (manager, owner, pilots)
        const dmTargets = new Set();
        dmTargets.add(req.manager_id.toString());
        if (req.owner_user_id) dmTargets.add(req.owner_user_id.toString());
        for (const pilot of pilots) dmTargets.add(pilot.user_id.toString());

        for (const userId of dmTargets) {
          try {
            const dmUser = await client.users.fetch(userId);
            await dmUser.send({ content: dmContent, components: dmComponents });
          } catch (e) {
            console.error(`Failed to DM user ${userId} for service request #${req.id}: ${e.message}`);
          }
        }

        await markServiceRequestNotified(req.id);
        console.log(`Sent DM notifications for service request #${req.id} (${dmTargets.size} users)`);
        continue;
      }

      // Create a private thread in the services channel
      const emoji = isQuestion ? '❓' : '✈';
      const thread = await channel.threads.create({
        name: `${emoji} ${requesterName} → ${req.service_title}`.substring(0, 100),
        autoArchiveDuration: 1440,
        reason: `Service request #${req.id}`,
        type: ChannelType.PrivateThread,
      });

      await setServiceRequestThread(req.id, thread.id);

      content += `\n**Staff:** ${staffMentions.join(', ')}`;
      content += `\nUse this thread to discuss. The provider can manage the request on the website.`;
      await thread.send(content);

      // Add requester to thread
      try { await thread.members.add(req.requester_id.toString()); } catch (e) {
        console.error(`Failed to add requester to service thread: ${e.message}`);
      }

      // Add manager
      try { await thread.members.add(req.manager_id.toString()); } catch (e) {
        console.error(`Failed to add manager to service thread: ${e.message}`);
      }

      // Add owner (if different from manager)
      if (req.owner_user_id && req.owner_user_id.toString() !== req.manager_id.toString()) {
        try { await thread.members.add(req.owner_user_id.toString()); } catch (e) {
          console.error(`Failed to add owner to service thread: ${e.message}`);
        }
      }

      // Add pilots (if different from manager/owner)
      for (const pilot of pilots) {
        if (pilot.user_id.toString() !== req.manager_id.toString() &&
            (!req.owner_user_id || pilot.user_id.toString() !== req.owner_user_id.toString())) {
          try { await thread.members.add(pilot.user_id.toString()); } catch (e) {
            console.error(`Failed to add pilot ${pilot.username} to service thread: ${e.message}`);
          }
        }
      }

      console.log(`Created service thread for request #${req.id}: ${thread.name}`);
    } catch (e) {
      console.error(`Error processing service request #${req.id}:`, e);
    }
  }
}

setInterval(() => runScheduled('checkServiceRequests', checkServiceRequests), 15 * 1000);

// Send DM notifications for check-ins on services with their own Discord server
async function checkCheckinDmNotifications() {
  const pendingCheckins = await getPendingCheckinsDmNotify();
  for (const checkin of pendingCheckins) {
    try {
      const passengerName = checkin.passenger_name || checkin.passenger_username || 'Unknown';
      let content = `**New Check-in for ${checkin.service_title}** — Flight #${checkin.flight_id}\n`;
      content += `Passenger: <@${checkin.user_id}> (${passengerName})\n`;
      if (checkin.join_location) content += `Boarding at: ${checkin.join_location}\n`;
      if (checkin.exit_location) content += `Exit at: ${checkin.exit_location}\n`;
      content += `\n_Check-in lets a passenger reserve a spot on this flight. Accept to confirm their boarding, or deny to reject._`;

      const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder()
          .setCustomId(`checkin_accept_${checkin.id}`)
          .setLabel('Accept Check-in')
          .setStyle(ButtonStyle.Success),
        new ButtonBuilder()
          .setCustomId(`checkin_deny_${checkin.id}`)
          .setLabel('Deny Check-in')
          .setStyle(ButtonStyle.Danger),
      );

      const pilots = typeof checkin.pilots === 'string' ? JSON.parse(checkin.pilots) : (checkin.pilots || []);
      const dmTargets = new Set();
      dmTargets.add(checkin.manager_id.toString());
      if (checkin.owner_user_id) dmTargets.add(checkin.owner_user_id.toString());
      for (const pilot of pilots) dmTargets.add(pilot.user_id.toString());

      for (const userId of dmTargets) {
        try {
          const dmUser = await client.users.fetch(userId);
          await dmUser.send({ content, components: [row] });
        } catch (e) {
          console.error(`Failed to DM user ${userId} for check-in #${checkin.id}: ${e.message}`);
        }
      }

      // Mark as notified using the existing added_to_thread column
      await markCheckinAddedToThread(checkin.id);
      console.log(`Sent DM notifications for check-in #${checkin.id} (${dmTargets.size} users)`);
    } catch (e) {
      console.error(`Error processing check-in DM #${checkin.id}:`, e);
    }
  }
}

setInterval(() => runScheduled('checkCheckinDmNotifications', checkCheckinDmNotifications), 15 * 1000);

// Expire tickets once per hour
async function runTicketExpiration() {
  try {
    const count = await expireTickets();
    if (count > 0) {
      console.log(`Expired ${count} ticket(s)`);
    }
  } catch (e) {
    console.error('Error expiring tickets:', e);
  }
}
setInterval(() => runScheduled('runTicketExpiration', runTicketExpiration), 60 * 60 * 1000);
runScheduled('runTicketExpiration', runTicketExpiration); // Run once on startup

// Resolve unresolved market price item IDs every hour
async function runMarketPriceResolution() {
  try {
    const resolved = await resolveMarketPriceItemIds();
    if (resolved > 0) {
      console.log(`Market price item resolution: ${resolved} items resolved`);
    }
  } catch (e) {
    console.error('Error resolving market price item IDs:', e);
  }
}
setInterval(() => runScheduled('runMarketPriceResolution', runMarketPriceResolution), 60 * 60 * 1000);
runScheduled('runMarketPriceResolution', runMarketPriceResolution); // Run once on startup

// Snapshot exchange prices then compute exchange summaries at quarter-hour boundaries (:00, :15, :30, :45)
const SNAPSHOT_INTERVAL_MS = 15 * 60 * 1000;
const SNAPSHOT_GRACE_MS = 5 * 60 * 1000;

async function runExchangePriceSnapshot() {
  try {
    const count = await snapshotExchangePrices();
    if (count > 0) {
      console.log(`Exchange price snapshot: ${count} items`);
    }
    const results = await computeAllExchangeSummaries();
    const totalProcessed = results.reduce((sum, r) => sum + r.processed, 0);
    if (totalProcessed > 0) {
      console.log(`Exchange summaries: ${results.map(r => `${r.period_type}=${r.processed}`).join(', ')}`);
    }
  } catch (e) {
    console.error('Error in exchange price snapshot:', e);
  }
}

function scheduleNextSnapshot() {
  const now = Date.now();
  const msSinceLastBoundary = now % SNAPSHOT_INTERVAL_MS;

  // If we're within the grace period past a boundary, run immediately (retroactive)
  if (msSinceLastBoundary > 0 && msSinceLastBoundary <= SNAPSHOT_GRACE_MS) {
    runScheduled('runExchangePriceSnapshot', runExchangePriceSnapshot);
  }

  // Schedule next boundary
  const delay = SNAPSHOT_INTERVAL_MS - msSinceLastBoundary;
  setTimeout(() => {
    runScheduled('runExchangePriceSnapshot', runExchangePriceSnapshot);
    scheduleNextSnapshot();
  }, delay);
}
scheduleNextSnapshot();

client.login(process.env.CLIENT_TOKEN);

client.commands = new Collection();

const foldersPath = join(dirname(fileURLToPath(import.meta.url)), 'commands');
const commandFolders = readdirSync(foldersPath);

Promise.all(commandFolders.map(async (folder) => {
  const commandsPath = join(foldersPath, folder);
  const commandFiles = readdirSync(commandsPath).filter(file => file.endsWith('.js'));
  return Promise.all(commandFiles.map(async (file) => {
    const filePath = join(commandsPath, file);
    const fileURL = pathToFileURL(filePath).href;
    const command = await import(fileURL);
    // Set a new item in the Collection with the key as the command name and the value as the exported module
    if ('data' in command && 'execute' in command) {
      client.commands.set(command.data.name, command);
    } else {
      console.log(`[WARNING] The command at ${filePath} is missing a required "data" or "execute" property.`);
    }
  }));
})).then(() => {
  // All commands have been loaded at this point
});
