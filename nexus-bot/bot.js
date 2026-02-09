import dotenv from 'dotenv';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { dump } from 'js-yaml';
import { Client, GatewayIntentBits, Collection, Events, ChannelType } from 'discord.js';
import { getUsers, getOpenChanges, setChangeThreadId, getDeletedChanges, deleteChange, getFlightsNeedingThread, setFlightThreadId, getCheckinsPendingThreadAdd, markCheckinAddedToThread, getUnnotifiedFlightStateChanges, getFlightsNeedingArchive, clearFlightThreadId, getPendingRescheduleNotifications, markRescheduleNotificationSent, getServicePilots, getFlightAcceptedCheckins, getFlightsReadyForCustomerKick, setFlightCompletedAt, expireTickets, computeAllPriceSummaries, getPendingTradeRequests, getTradeRequestItems, setTradeRequestThread, getWarnableTradeRequests, markWarningSent, getExpirableTradeRequests, updateTradeRequestStatus, findTradeRequestByThread, updateLastActivity, getActiveTradeRequestsWithNewItems, getNewTradeRequestItems } from './db.js';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compareJson, validate, printSideBySide } from './change.js';

const adminUserId = '178245652633878528';

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
    GatewayIntentBits.GuildMembers
  ]
});

export async function notifyModerators({ title = 'Bot Error', error = null, context = '', extra = '' } = {}) {
  try {
    const guildId = config.guildId;
    const moderatorRoleId = config.moderatorRoleId;
    if (!guildId || !moderatorRoleId) {
      console.error('notifyModerators: Missing guildId or moderatorRoleId in config.');
      return;
    }

    const guild = client.guilds.cache.get(guildId) || await client.guilds.fetch(guildId).catch(() => null);
    if (!guild) {
      console.error('notifyModerators: Guild not found.');
      return;
    }

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

client.on('ready', async () => {
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
    // On-demand service requests are no longer handled by the bot.
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
  
  try {
    await channel.guild.members.fetch();
  } catch (e) {
    console.error('Error fetching members, using old list instead.', e);
  }

  const unverifiedUsers = (await getUsers()).filter(x => !x.verified);

  for (const user of unverifiedUsers) {
    const guildMember = channel.guild.members.cache.get(user.id);

    if (!guildMember) {
      const existingThread = channel.threads.cache.find(thread => thread.name === `${user.username}-verification`);
      if (existingThread && !existingThread.archived) {
        try {
          await existingThread.setArchived(true);
          console.log(`Archived thread for user ${user.username} as they are no longer on the server.`);
        } catch (e) {
          console.error('Error archiving thread for user no longer on the server.', e);
        }
      }
      continue;
    }

    const existingThread = channel.threads.cache.find(thread => thread.name === `${user.username}-verification`);

    if (existingThread) {
      try {
        // Add user to thread if he isnt already
        await existingThread.members.add(user.id);
      }
      catch (e) {
        console.error('Error adding user to thread. Is he on the server?', e);
      }

      continue;
    }

    const thread = await channel.threads.create({
      name: `${user.username}-verification`,
      autoArchiveDuration: 10080,
      reason: `Verification thread created for ${user.username}`,
      type: ChannelType.PrivateThread,
      permissionOverwrites: [
        {
          id: user.id,
          allow: ['VIEW_CHANNEL', 'SEND_MESSAGES'],
        },
        {
          id: config.moderatorRoleId,
          allow: ['VIEW_CHANNEL', 'SEND_MESSAGES'],
        },
        {
          id: channel.guild.roles.everyone.id,
          deny: ['VIEW_CHANNEL', 'SEND_MESSAGES'],
        },
      ],
    });

    try {
      await thread.send(`Hello <@${user.id}>, please set your full Entropia Universe username using /seteuname and wait for a moderator to validate it in-game. You can't change your username after verification has been completed!`);
    } catch (e) {
      console.error(`Failed to send welcome message to verification thread for ${user.username}: ${e.message}`);
    }
  }
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
    let thread = change.thread_id
      ? await channel.threads.fetch(change.thread_id).catch(_ => null)
      : null;

    const rawChangeId = change?.data?.Id;
    const apartmentId = change.entity === 'Apartment' && Number.isFinite(Number(rawChangeId))
      ? (Number(rawChangeId) > 300000 ? Number(rawChangeId) - 300000 : Number(rawChangeId))
      : rawChangeId;
    const fetchId = change.entity === 'Apartment' ? apartmentId : rawChangeId;
    const fetchUrl = `${process.env.API_URL}/${change.entity.toLowerCase()}s/${fetchId}`;
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
        name: `[${change.state}] ${change.type}: ${change.data.Name.substring(0, 80)}`,
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
        await thread.send(`A new change has been submitted by <@${change.author_id}>. Please post proof to validate your changes and await approval.`);
      } catch (e) {
        console.error(`Failed to send submission message to thread ${thread.id} (${change.data.Name}): ${e.message}`);
      }
    }
    else {
      try {
        await thread.setName(`[${change.state}] ${change.type}: ${change.data.Name.substring(0, 80)}`);
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
      try {
        await thread.send(`This change has been updated by <@${change.author_id}>.`);
      } catch (e) {
        console.error(`Failed to send update notification to thread ${thread.id} (${change.data.Name}): ${e.message}`);
      }

      let newCheckTime = new Date(change.content_updated_at);
      newCheckTime.setMilliseconds(newCheckTime.getMilliseconds() + 1);
      setConfigValue('lastChangeCheck', newCheckTime.toISOString());
    }

    // Add static user to the thread
    if (change.state == 'Pending' && !thread.members.cache.has(adminUserId)) {
      try {
        await thread.members.add(adminUserId);
      }
      catch (e) {
        console.error(`Error adding admin to change thread (${thread.id}, ${change.data.Name}): ${e.message}`);
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
      await thread.setName(`[${change.state}] ${change.type}: ${change.data.Name.substring(0, 80)}`);
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

function formatJsonForDiscord(json) {
  if (json === null) {
    return ['```yaml\nNo changes detected\n```'];
  }
  
  let formatted = dump(json, { indent: 2 }).replace(/^( +)/g, '\t');

  // Split the formatted string into chunks at line breaks
  let chunks = [];
  let lines = formatted.split('\n');
  let currentChunk = '';
  for (let line of lines) {
    if (currentChunk.length + line.length + 12 > 2000) { // 7 is the length of '```yaml\n'
      chunks.push(currentChunk);
      currentChunk = '';
    }
    currentChunk += line + '\n';
  }
  if (currentChunk.length > 0) {
    chunks.push(currentChunk);
  }

  // Wrap each chunk in a code block with YAML syntax highlighting
  return chunks.map(chunk => '```yaml\n' + chunk + '```');
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

        // Add pilots to the thread (if different from provider)
        for (const pilot of pilots) {
          if (pilot.user_id.toString() !== flight.provider_user_id.toString()) {
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
setInterval(() => runScheduled('checkTradeRequests', checkTradeRequests), 30 * 1000);

// ---- Trade Request Thread Management ----

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
        const mu = item.markup != null ? ` @ ${item.markup}` : '';
        msg += `- ${side} ${item.quantity}x **${item.item_name}**${mu}\n`;
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

      console.log(`Created trade thread for request #${req.id}: ${thread.name}`);
    } catch (e) {
      console.error(`Error creating trade thread for request #${req.id}:`, e);
    }
  }

  // 2. Announce new items added to existing active trade threads
  const requestsWithNewItems = await getActiveTradeRequestsWithNewItems(lastTradeItemCheck);
  for (const req of requestsWithNewItems) {
    try {
      const newItems = await getNewTradeRequestItems(req.id, lastTradeItemCheck);
      if (newItems.length === 0) continue;

      const thread = await channel.threads.fetch(req.discord_thread_id).catch(() => null);
      if (!thread) continue;

      let msg = `**New items added to trade:**\n`;
      for (const item of newItems) {
        const side = item.side === 'SELL' ? 'Buy' : 'Sell';
        const mu = item.markup != null ? ` @ ${item.markup}` : '';
        msg += `- ${side} ${item.quantity}x **${item.item_name}**${mu}\n`;
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

// Compute price summaries every 15 minutes
async function runPriceSummaries() {
  try {
    const results = await computeAllPriceSummaries();
    const totalProcessed = results.reduce((sum, r) => sum + r.processed, 0);
    if (totalProcessed > 0) {
      console.log(`Price summaries: ${results.map(r => `${r.period_type}=${r.processed}`).join(', ')}`);
    }
  } catch (e) {
    console.error('Error computing price summaries:', e);
  }
}
setInterval(() => runScheduled('runPriceSummaries', runPriceSummaries), 15 * 60 * 1000);

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
