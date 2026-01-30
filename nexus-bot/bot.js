import dotenv from 'dotenv';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { dump } from 'js-yaml';
import { Client, GatewayIntentBits, Collection, Events, ChannelType, ButtonBuilder, ButtonStyle, ActionRowBuilder, ModalBuilder, TextInputBuilder, TextInputStyle } from 'discord.js';
import { getUsers, getOpenChanges, setChangeThreadId, getDeletedChanges, deleteChange, getFlightsNeedingThread, setFlightThreadId, getCheckinsPendingThreadAdd, markCheckinAddedToThread, getUnnotifiedFlightStateChanges, getFlightsNeedingArchive, clearFlightThreadId, getPendingRescheduleNotifications, markRescheduleNotificationSent, getServicePilots, getFlightAcceptedCheckins, getFlightsReadyForCustomerKick, setFlightCompletedAt, expireTickets, getOnDemandRequestsNeedingThread, setRequestThreadId, getRequestsReadyForArchive, clearRequestThreadId, updateRequestStatus, getTicketById, restoreTicketUse, deletePendingTicket, getRequestById, updateServiceRequest, activateTicket, useTicket, updateProviderLocation } from './db.js';
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

client.on('ready', async () => {
  console.log(`Logged in as ${client.user.tag}!`);
  // Fetch planets from API on startup
  await fetchPlanets();
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
      if (interaction.replied || interaction.deferred) {
        await interaction.followUp({ content: 'There was an error while executing this command!', flags: 64 });
      } else {
        await interaction.reply({ content: 'There was an error while executing this command!', flags: 64 });
      }
    }
    return;
  }

  // Handle button interactions
  if (interaction.isButton()) {
    await handleServiceButtonInteraction(interaction);
    return;
  }

  // Handle modal submissions
  if (interaction.isModalSubmit()) {
    await handleServiceModalSubmit(interaction);
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

    const fetchUrl = `${process.env.API_URL}/${change.entity.toLowerCase()}s/${change.data.Id}`;
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

    // Print side-by-side comparison for debugging
    printSideBySide(entity, change.data, 'Entity vs Change Data');

    validate(change.entity, entity);

    // Print side-by-side comparison for debugging
    printSideBySide(entity, change.data, 'Entity vs Change Data');

    let compareObject = compareJson(entity, change.data);
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

setInterval(checkUnverifiedUsers, 1 * 60 * 1000);
setInterval(checkChanges, 1 * 15 * 1000);
setInterval(checkFlights, 30 * 1000);
setInterval(checkRescheduleNotifications, 30 * 1000);

// =============================================
// SERVICE REQUEST BUTTON/MODAL HANDLERS
// =============================================

// Helper to check if a request is a question
function isRequestQuestion(request) {
  return request.service_notes && request.service_notes.startsWith('[QUESTION]');
}

// Build action buttons based on request status and user role
function buildServiceButtons(request, isProvider, isRequester) {
  const buttons = [];
  const status = request.status;
  const isQuestion = isRequestQuestion(request);

  if (isProvider) {
    if (isQuestion) {
      // Question-specific buttons for provider
      if (status === 'pending' || status === 'negotiating') {
        buttons.push(
          new ButtonBuilder()
            .setCustomId(`service_close_question_${request.id}`)
            .setLabel('Close Question')
            .setStyle(ButtonStyle.Secondary)
        );
      }
    } else {
      // Normal request buttons
      if (status === 'pending') {
        buttons.push(
          new ButtonBuilder()
            .setCustomId(`service_negotiate_${request.id}`)
            .setLabel('Start Conversation')
            .setStyle(ButtonStyle.Primary),
          new ButtonBuilder()
            .setCustomId(`service_decline_${request.id}`)
            .setLabel('Decline')
            .setStyle(ButtonStyle.Danger)
        );
      } else if (status === 'negotiating') {
        buttons.push(
          new ButtonBuilder()
            .setCustomId(`service_accept_${request.id}`)
            .setLabel('Accept Request')
            .setStyle(ButtonStyle.Success),
          new ButtonBuilder()
            .setCustomId(`service_decline_${request.id}`)
            .setLabel('Decline')
            .setStyle(ButtonStyle.Danger)
        );
      } else if (status === 'accepted') {
        buttons.push(
          new ButtonBuilder()
            .setCustomId(`service_start_${request.id}`)
            .setLabel('Start Service')
            .setStyle(ButtonStyle.Primary),
          new ButtonBuilder()
            .setCustomId(`service_abort_${request.id}`)
            .setLabel('Cancel')
            .setStyle(ButtonStyle.Secondary)
        );
      } else if (status === 'in_progress') {
        buttons.push(
          new ButtonBuilder()
            .setCustomId(`service_finish_${request.id}`)
            .setLabel('Finish')
            .setStyle(ButtonStyle.Success),
          new ButtonBuilder()
            .setCustomId(`service_abort_${request.id}`)
            .setLabel('Abort')
            .setStyle(ButtonStyle.Danger)
        );
      }
    }
  }

  if (isRequester) {
    if (isQuestion) {
      // Question-specific buttons for customer
      if (['pending', 'negotiating'].includes(status)) {
        buttons.push(
          new ButtonBuilder()
            .setCustomId(`service_submit_request_${request.id}`)
            .setLabel('Submit Request')
            .setStyle(ButtonStyle.Success),
          new ButtonBuilder()
            .setCustomId(`service_close_question_${request.id}`)
            .setLabel('Close Question')
            .setStyle(ButtonStyle.Secondary)
        );
      }
    } else {
      // Normal requests
      if (['pending', 'negotiating', 'accepted', 'in_progress'].includes(status)) {
        // Only add abort button if not already added by provider section
        if (!buttons.some(b => b.data.custom_id === `service_abort_${request.id}`)) {
          buttons.push(
            new ButtonBuilder()
              .setCustomId(`service_abort_${request.id}`)
              .setLabel('Cancel Request')
              .setStyle(ButtonStyle.Danger)
          );
        }
      }
    }
  }

  if (buttons.length === 0) return null;

  return new ActionRowBuilder().addComponents(buttons);
}

// Build the "Show My Controls" button for initial thread message
function buildShowControlsButton(requestId) {
  return new ActionRowBuilder().addComponents(
    new ButtonBuilder()
      .setCustomId(`service_show_controls_${requestId}`)
      .setLabel('Show My Controls')
      .setStyle(ButtonStyle.Primary)
  );
}

// Send ephemeral control message to a user (via interaction)
async function sendEphemeralControlMessage(interaction, request, isProvider, isRequester) {
  const actionRow = buildServiceButtons(request, isProvider, isRequester);

  const isQuestion = isRequestQuestion(request);

  let statusText;
  if (isQuestion) {
    statusText = {
      pending: 'Question awaiting response',
      negotiating: 'Discussing question'
    };
  } else {
    statusText = {
      pending: 'Waiting for provider response',
      negotiating: 'In conversation - discuss details then accept or decline',
      accepted: 'Request accepted - ready to start',
      in_progress: 'Service in progress'
    };
  }

  const roleLabel = isProvider ? 'Provider' : 'Customer';
  let content = `**${roleLabel} Controls** - Status: ${statusText[request.status] || request.status}`;

  // Add hint for customer about converting question to request
  if (isQuestion && isRequester) {
    content += `\n\nWhen you're ready to book this service, click **Submit Request** to provide your booking details.`;
  }

  // If no controls available, let them know
  if (!actionRow) {
    content += '\n\nNo actions available at this time.';
  }

  await interaction.reply({
    content,
    components: actionRow ? [actionRow] : [],
    flags: 64 // Ephemeral
  });
}

// Handle "Show My Controls" button
async function handleShowControlsButton(interaction, requestId) {
  try {
    const request = await getRequestById(requestId);
    if (!request) {
      return interaction.reply({ content: 'Request not found.', flags: 64 });
    }

    const userId = interaction.user.id;
    const isProvider = userId === request.provider_user_id.toString();
    const isRequester = userId === request.requester_discord_id.toString();

    if (!isProvider && !isRequester) {
      return interaction.reply({ content: 'You are not a participant in this request.', flags: 64 });
    }

    await sendEphemeralControlMessage(interaction, request, isProvider, isRequester);
  } catch (error) {
    console.error('Error handling show controls button:', error);
    if (!interaction.replied && !interaction.deferred) {
      await interaction.reply({ content: 'An error occurred while fetching controls.', flags: 64 });
    }
  }
}

// Handle service button interactions
async function handleServiceButtonInteraction(interaction) {
  const customId = interaction.customId;

  // Check if this is a service-related button
  if (!customId.startsWith('service_')) return;

  // Handle "show_controls" button specially (format: service_show_controls_{requestId})
  if (customId.startsWith('service_show_controls_')) {
    const showRequestId = parseInt(customId.replace('service_show_controls_', ''));
    if (!isNaN(showRequestId)) {
      await handleShowControlsButton(interaction, showRequestId);
    }
    return;
  }

  const parts = customId.split('_');
  if (parts.length < 3) return;

  const action = parts[1];
  const requestId = parseInt(parts[2]);

  if (isNaN(requestId)) {
    return interaction.reply({ content: 'Invalid request ID.', flags: 64 });
  }

  try {
    const request = await getRequestById(requestId);
    if (!request) {
      return interaction.reply({ content: 'Request not found.', flags: 64 });
    }

    const userId = interaction.user.id;
    const isProvider = userId === request.provider_user_id.toString();
    const isRequester = userId === request.requester_discord_id.toString();

    if (!isProvider && !isRequester) {
      return interaction.reply({ content: 'You are not authorized to interact with this request.', flags: 64 });
    }

    switch (action) {
      case 'negotiate':
        await handleNegotiateButton(interaction, request, isProvider);
        break;
      case 'accept':
        await handleAcceptButton(interaction, request, isProvider);
        break;
      case 'decline':
        await handleDeclineButton(interaction, request, isProvider);
        break;
      case 'start':
        await handleStartButton(interaction, request, isProvider);
        break;
      case 'finish':
        await handleFinishButton(interaction, request, isProvider);
        break;
      case 'abort':
        await handleAbortButton(interaction, request, isProvider, isRequester);
        break;
      case 'submit':
        // Handle submit_request (action is 'submit', parts[2] is 'request', parts[3] is requestId)
        if (parts[2] === 'request') {
          const submitRequestId = parseInt(parts[3]);
          if (!isNaN(submitRequestId)) {
            const submitRequest = await getRequestById(submitRequestId);
            if (submitRequest) {
              await handleSubmitRequestButton(interaction, submitRequest, isRequester);
            }
          }
        }
        break;
      case 'close':
        // Handle close_question (action is 'close', parts[2] is 'question', parts[3] is requestId)
        if (parts[2] === 'question') {
          const closeRequestId = parseInt(parts[3]);
          if (!isNaN(closeRequestId)) {
            const closeRequest = await getRequestById(closeRequestId);
            if (closeRequest) {
              await handleCloseQuestionButton(interaction, closeRequest, isProvider, isRequester);
            }
          }
        }
        break;
      default:
        await interaction.reply({ content: 'Unknown action.', flags: 64 });
    }
  } catch (error) {
    console.error('Error handling service button:', error);
    if (!interaction.replied && !interaction.deferred) {
      await interaction.reply({ content: 'An error occurred while processing your request.', flags: 64 });
    }
  }
}

async function handleNegotiateButton(interaction, request, isProvider) {
  if (!isProvider) {
    return interaction.reply({ content: 'Only the provider can start the conversation.', flags: 64 });
  }

  if (request.status !== 'pending') {
    return interaction.reply({ content: `Cannot start conversation for a request with status '${request.status}'.`, flags: 64 });
  }

  await updateRequestStatus(request.id, 'negotiating');

  // Update the message with new buttons
  const newRow = buildServiceButtons({ ...request, status: 'negotiating' }, true, false);

  await interaction.update({
    content: `<@${interaction.user.id}>\n**Provider Controls** - Status: In negotiation - discuss details and then accept or decline`,
    components: newRow ? [newRow] : []
  });

  // Notify in thread
  await interaction.channel.send({
    content: `**Conversation Started**\n\nThe provider is now reviewing the request. Feel free to discuss details.`
  });
}

async function handleAcceptButton(interaction, request, isProvider) {
  if (!isProvider) {
    return interaction.reply({ content: 'Only the provider can accept requests.', flags: 64 });
  }

  if (request.status !== 'negotiating' && request.status !== 'pending') {
    return interaction.reply({ content: `Cannot accept a request with status '${request.status}'.`, flags: 64 });
  }

  await updateRequestStatus(request.id, 'accepted');

  const newRow = buildServiceButtons({ ...request, status: 'accepted' }, true, false);

  await interaction.update({
    content: `<@${interaction.user.id}>\n**Provider Controls** - Status: Request accepted - ready to start`,
    components: newRow ? [newRow] : []
  });

  await interaction.channel.send({
    content: `**Request Accepted**\n\nThe provider has accepted this request. The service can begin when ready.`
  });
}

async function handleDeclineButton(interaction, request, isProvider) {
  if (!isProvider) {
    return interaction.reply({ content: 'Only the provider can decline requests.', flags: 64 });
  }

  if (!['pending', 'negotiating'].includes(request.status)) {
    return interaction.reply({ content: `Cannot decline a request with status '${request.status}'.`, flags: 64 });
  }

  // Handle ticket refund if applicable
  let ticketMessage = '';
  if (request.ticket_id) {
    const ticket = await getTicketById(request.ticket_id);
    if (ticket) {
      if (ticket.status === 'pending') {
        await deletePendingTicket(request.ticket_id);
        ticketMessage = '\n\nThe pending ticket has been deleted.';
      } else if (ticket.status === 'active') {
        await restoreTicketUse(request.ticket_id);
        ticketMessage = '\n\nThe ticket use has been refunded.';
      }
    }
  }

  await updateRequestStatus(request.id, 'declined');

  await interaction.update({
    content: `<@${interaction.user.id}>\n**Request Declined**`,
    components: []
  });

  await interaction.channel.send({
    content: `**Request Declined**\n\nThe provider has declined this request.${ticketMessage}\n\nThis thread will be archived shortly.`
  });
}

async function handleStartButton(interaction, request, isProvider) {
  if (!isProvider) {
    return interaction.reply({ content: 'Only the provider can start the service.', flags: 64 });
  }

  if (request.status !== 'accepted') {
    return interaction.reply({ content: `Cannot start a service with status '${request.status}'.`, flags: 64 });
  }

  await updateServiceRequest(request.id, {
    status: 'in_progress',
    actual_start: new Date().toISOString()
  });

  const newRow = buildServiceButtons({ ...request, status: 'in_progress' }, true, false);

  await interaction.update({
    content: `<@${interaction.user.id}>\n**Provider Controls** - Status: Service in progress`,
    components: newRow ? [newRow] : []
  });

  await interaction.channel.send({
    content: `**Service Started**\n\nThe service session has begun.`
  });
}

async function handleFinishButton(interaction, request, isProvider) {
  if (!isProvider) {
    return interaction.reply({ content: 'Only the provider can finish the service.', flags: 64 });
  }

  if (request.status !== 'in_progress' && request.status !== 'accepted') {
    return interaction.reply({ content: `Cannot finish a service with status '${request.status}'.`, flags: 64 });
  }

  // For DPS/Healing services, show a modal to enter duration and decay
  if (request.service_type === 'healing' || request.service_type === 'dps') {
    const includesDecay = request.service_type === 'healing'
      ? request.healing_includes_decay
      : request.dps_includes_decay;

    const modal = new ModalBuilder()
      .setCustomId(`service_finish_modal_${request.id}`)
      .setTitle('Complete Service Session');

    const durationInput = new TextInputBuilder()
      .setCustomId('duration')
      .setLabel('Duration (minutes)')
      .setStyle(TextInputStyle.Short)
      .setPlaceholder('e.g., 60')
      .setRequired(true);

    const breakInput = new TextInputBuilder()
      .setCustomId('breaks')
      .setLabel('Break time (minutes, optional)')
      .setStyle(TextInputStyle.Short)
      .setPlaceholder('e.g., 5')
      .setRequired(false);

    const rows = [
      new ActionRowBuilder().addComponents(durationInput),
      new ActionRowBuilder().addComponents(breakInput)
    ];

    // Add decay input if payment includes decay
    if (includesDecay) {
      const decayInput = new TextInputBuilder()
        .setCustomId('decay')
        .setLabel('Actual decay cost (PED)')
        .setStyle(TextInputStyle.Short)
        .setPlaceholder('e.g., 12.50')
        .setRequired(false);
      rows.push(new ActionRowBuilder().addComponents(decayInput));
    }

    modal.addComponents(...rows);
    await interaction.showModal(modal);
  } else {
    // For other services, complete directly
    await completeServiceRequest(interaction, request, null, null, null);
  }
}

async function handleAbortButton(interaction, request, isProvider, isRequester) {
  if (!isProvider && !isRequester) {
    return interaction.reply({ content: 'You cannot abort this request.', flags: 64 });
  }

  const allowedStatuses = ['pending', 'negotiating', 'accepted', 'in_progress'];
  if (!allowedStatuses.includes(request.status)) {
    return interaction.reply({ content: `Cannot abort a request with status '${request.status}'.`, flags: 64 });
  }

  const who = isProvider ? 'provider' : 'customer';

  // Handle ticket refund
  let ticketMessage = '';
  if (request.ticket_id) {
    const ticket = await getTicketById(request.ticket_id);
    if (ticket) {
      if (ticket.status === 'pending') {
        await deletePendingTicket(request.ticket_id);
        ticketMessage = '\n\nThe pending ticket has been deleted.';
      } else if (ticket.status === 'active') {
        await restoreTicketUse(request.ticket_id);
        ticketMessage = '\n\nThe ticket use has been refunded.';
      }
    }
  }

  await updateRequestStatus(request.id, 'aborted');

  await interaction.update({
    content: `<@${interaction.user.id}>\n**Request Aborted**`,
    components: []
  });

  await interaction.channel.send({
    content: `**Request Aborted**\n\nThis service request has been aborted by the ${who}.${ticketMessage}\n\nThis thread will be archived shortly.`
  });
}

async function handleSubmitRequestButton(interaction, request, isRequester) {
  if (!isRequester) {
    return interaction.reply({ content: 'Only the customer can submit a request.', flags: 64 });
  }

  if (!isRequestQuestion(request)) {
    return interaction.reply({ content: 'This is already a request.', flags: 64 });
  }

  if (!['pending', 'negotiating'].includes(request.status)) {
    return interaction.reply({ content: `Cannot submit a request for a question with status '${request.status}'.`, flags: 64 });
  }

  // Show modal for basic request details
  const modal = new ModalBuilder()
    .setCustomId(`service_request_modal_${request.id}`)
    .setTitle('Submit Service Request');

  const dateInput = new TextInputBuilder()
    .setCustomId('requested_date')
    .setLabel('Preferred Date (optional)')
    .setStyle(TextInputStyle.Short)
    .setPlaceholder('e.g., 2024-01-15 or "today" or "tomorrow"')
    .setRequired(false);

  const timeInput = new TextInputBuilder()
    .setCustomId('requested_time')
    .setLabel('Preferred Time (Game Time, optional)')
    .setStyle(TextInputStyle.Short)
    .setPlaceholder('e.g., 14:00 or "now"')
    .setRequired(false);

  const durationInput = new TextInputBuilder()
    .setCustomId('duration')
    .setLabel('Duration in minutes (optional)')
    .setStyle(TextInputStyle.Short)
    .setPlaceholder('e.g., 60')
    .setRequired(false);

  const notesInput = new TextInputBuilder()
    .setCustomId('notes')
    .setLabel('Additional notes (optional)')
    .setStyle(TextInputStyle.Paragraph)
    .setPlaceholder('Any additional details for the provider...')
    .setRequired(false);

  modal.addComponents(
    new ActionRowBuilder().addComponents(dateInput),
    new ActionRowBuilder().addComponents(timeInput),
    new ActionRowBuilder().addComponents(durationInput),
    new ActionRowBuilder().addComponents(notesInput)
  );

  await interaction.showModal(modal);
}

async function handleCloseQuestionButton(interaction, request, isProvider, isRequester) {
  // Both provider and customer can close questions
  if (!isProvider && !isRequester) {
    return interaction.reply({ content: 'You are not authorized to close this question.', flags: 64 });
  }

  if (!isRequestQuestion(request)) {
    return interaction.reply({ content: 'This is not a question.', flags: 64 });
  }

  if (!['pending', 'negotiating'].includes(request.status)) {
    return interaction.reply({ content: `Cannot close a question with status '${request.status}'.`, flags: 64 });
  }

  const who = isProvider ? 'provider' : 'customer';

  // Mark the question as cancelled
  await updateRequestStatus(request.id, 'cancelled');

  await interaction.update({
    content: `<@${interaction.user.id}>\n**Question Closed**`,
    components: []
  });

  await interaction.channel.send({
    content: `**Question Closed**\n\nThis question has been closed by the ${who}. If you have more questions, feel free to open a new one.\n\nThis thread will be archived shortly.`
  });
}

// Handle request submission modal (when converting question to request)
async function handleRequestModalSubmit(interaction) {
  const customId = interaction.customId;
  const requestId = parseInt(customId.replace('service_request_modal_', ''));

  if (isNaN(requestId)) {
    return interaction.reply({ content: 'Invalid request ID.', flags: 64 });
  }

  try {
    const request = await getRequestById(requestId);
    if (!request) {
      return interaction.reply({ content: 'Request not found.', flags: 64 });
    }

    const userId = interaction.user.id;
    const isRequester = userId === request.requester_discord_id.toString();

    if (!isRequester) {
      return interaction.reply({ content: 'Only the customer can submit this request.', flags: 64 });
    }

    if (!isRequestQuestion(request)) {
      return interaction.reply({ content: 'This is already a request.', flags: 64 });
    }

    // Parse modal fields
    const dateStr = interaction.fields.getTextInputValue('requested_date') || '';
    const timeStr = interaction.fields.getTextInputValue('requested_time') || '';
    const durationStr = interaction.fields.getTextInputValue('duration') || '';
    const notes = interaction.fields.getTextInputValue('notes') || '';

    // Parse requested start time
    let requestedStart = null;
    if (dateStr || timeStr) {
      try {
        const now = new Date();
        let date = now;

        if (dateStr.toLowerCase() === 'today') {
          date = now;
        } else if (dateStr.toLowerCase() === 'tomorrow') {
          date = new Date(now.getTime() + 24 * 60 * 60 * 1000);
        } else if (dateStr) {
          date = new Date(dateStr);
        }

        if (timeStr.toLowerCase() === 'now') {
          // Use current time
        } else if (timeStr) {
          const [hours, minutes] = timeStr.split(':').map(Number);
          if (!isNaN(hours)) {
            date.setHours(hours, minutes || 0, 0, 0);
          }
        }

        if (!isNaN(date.getTime())) {
          requestedStart = date.toISOString();
        }
      } catch (e) {
        // Ignore parsing errors, leave requestedStart as null
      }
    }

    // Parse duration
    const duration = durationStr ? parseInt(durationStr) : null;

    // Get original question text
    const originalQuestion = request.service_notes.replace('[QUESTION]', '').trim();

    // Update the request to convert from question to actual request
    const updateData = {
      status: 'negotiating',
      service_notes: notes ? `${notes}\n\n(Originally asked: ${originalQuestion})` : `(Originally asked: ${originalQuestion})`
    };

    if (requestedStart) {
      updateData.requested_start = requestedStart;
    }
    if (duration && !isNaN(duration)) {
      updateData.requested_duration_minutes = duration;
    }

    await updateServiceRequest(request.id, updateData);

    // Build request summary
    let summary = `**Request Submitted**\n\n`;
    summary += `<@${request.requester_discord_id}> has converted their question into a service request.\n\n`;

    if (requestedStart) {
      const startDate = new Date(requestedStart);
      summary += `**Requested Time:** ${startDate.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}\n`;
    }
    if (duration) {
      summary += `**Duration:** ${duration} minutes\n`;
    }
    if (notes) {
      summary += `**Notes:** ${notes}\n`;
    }
    summary += `\n**Original question:** ${originalQuestion}`;

    // Update customer's button message
    const updatedRequest = { ...request, status: 'negotiating', service_notes: null };
    const customerRow = buildServiceButtons(updatedRequest, false, true);

    await interaction.update({
      content: `<@${interaction.user.id}>\n**Customer Controls** - Request submitted, waiting for provider`,
      components: customerRow ? [customerRow] : []
    });

    // Send summary to thread
    await interaction.channel.send({ content: summary });

    // Send new buttons to provider
    const providerRow = buildServiceButtons(updatedRequest, true, false);
    if (providerRow) {
      await interaction.channel.send({
        content: `<@${request.provider_user_id}>\n**Provider Controls** - A request has been submitted. Review and accept or decline.`,
        components: [providerRow]
      });
    }
  } catch (error) {
    console.error('Error handling request modal:', error);
    if (!interaction.replied && !interaction.deferred) {
      await interaction.reply({ content: 'An error occurred while submitting the request.', flags: 64 });
    }
  }
}

// Handle modal submissions
async function handleServiceModalSubmit(interaction) {
  const customId = interaction.customId;

  // Handle request submission modal (from question conversion)
  if (customId.startsWith('service_request_modal_')) {
    await handleRequestModalSubmit(interaction);
    return;
  }

  if (!customId.startsWith('service_finish_modal_')) return;

  const requestId = parseInt(customId.replace('service_finish_modal_', ''));
  if (isNaN(requestId)) {
    return interaction.reply({ content: 'Invalid request ID.', flags: 64 });
  }

  try {
    const request = await getRequestById(requestId);
    if (!request) {
      return interaction.reply({ content: 'Request not found.', flags: 64 });
    }

    const userId = interaction.user.id;
    const isProvider = userId === request.provider_user_id.toString();

    if (!isProvider) {
      return interaction.reply({ content: 'Only the provider can complete this service.', flags: 64 });
    }

    // Parse modal fields
    const durationStr = interaction.fields.getTextInputValue('duration');
    const breaksStr = interaction.fields.getTextInputValue('breaks') || '0';
    const decayStr = interaction.fields.getTextInputValue('decay') || null;

    const duration = parseFloat(durationStr);
    const breaks = parseFloat(breaksStr) || 0;
    const decay = decayStr ? parseFloat(decayStr) : null;

    if (isNaN(duration) || duration <= 0) {
      return interaction.reply({ content: 'Please enter a valid duration in minutes.', flags: 64 });
    }

    await completeServiceRequest(interaction, request, duration, breaks, decay);
  } catch (error) {
    console.error('Error handling finish modal:', error);
    if (!interaction.replied && !interaction.deferred) {
      await interaction.reply({ content: 'An error occurred while completing the service.', flags: 64 });
    }
  }
}

async function completeServiceRequest(interaction, request, duration, breaks, decay) {
  const updateData = {
    status: 'completed',
    actual_end: new Date().toISOString()
  };

  if (duration !== null) {
    // Calculate actual end from actual start + duration
    if (request.actual_start) {
      const startTime = new Date(request.actual_start);
      const endTime = new Date(startTime.getTime() + duration * 60 * 1000);
      updateData.actual_end = endTime.toISOString();
    }
  }

  if (decay !== null) {
    updateData.actual_decay_ped = decay;
  }

  if (breaks !== null && breaks > 0) {
    updateData.break_minutes = breaks;
  }

  await updateServiceRequest(request.id, updateData);

  // Handle ticket usage (for transportation services)
  let ticketMessage = '';
  if (request.ticket_id) {
    const ticket = await getTicketById(request.ticket_id);
    if (ticket) {
      if (ticket.status === 'pending') {
        await activateTicket(request.ticket_id);
      }
      const updatedTicket = await useTicket(request.ticket_id);
      if (updatedTicket) {
        if (updatedTicket.uses_remaining <= 0) {
          ticketMessage = '\n\nThe ticket has been fully used.';
        } else {
          ticketMessage = `\n\nTicket use consumed. ${updatedTicket.uses_remaining} uses remaining.`;
        }
      }
    }
  }

  // Update provider location (for transportation services)
  if (request.destination_planet_id) {
    await updateProviderLocation(request.service_id, request.destination_planet_id);
  }

  // Build summary message
  let summary = '**Service Completed**\n\n';

  if (duration !== null || decay !== null) {
    summary += '**Session Summary:**\n';
    if (duration !== null) {
      const hours = Math.floor(duration / 60);
      const mins = Math.round(duration % 60);
      summary += `- Duration: ${hours > 0 ? `${hours}h ` : ''}${mins}min\n`;
    }
    if (breaks !== null && breaks > 0) {
      summary += `- Breaks: ${breaks}min\n`;
    }
    if (decay !== null) {
      summary += `- Decay: ${decay.toFixed(2)} PED\n`;
    }
    summary += '\n';
  }

  summary += `This service request has been marked as completed.${ticketMessage}\n\nThank you for using our services! This thread will be archived shortly.`;

  // Update the button message
  await interaction.update({
    content: `<@${interaction.user.id}>\n**Service Completed**`,
    components: []
  });

  await interaction.channel.send({ content: summary });
}

// =============================================
// ON-DEMAND SERVICE REQUESTS
// =============================================

async function checkOnDemandRequests() {
  try {
    // Create threads for new service requests
    const requests = await getOnDemandRequestsNeedingThread();
    const servicesChannel = client.channels.cache.get(config.servicesChannelId);

    if (!servicesChannel && requests.length > 0) {
      console.error('Services channel not configured. Use /channel set services to configure.');
      return;
    }

    for (const request of requests) {
      try {
        // Check if this is a question (service_notes starts with [QUESTION])
        const isQuestion = request.service_notes && request.service_notes.startsWith('[QUESTION]');
        const questionText = isQuestion ? request.service_notes.replace('[QUESTION]', '').trim() : null;

        let details;

        if (isQuestion) {
          // Simplified message for questions - just the question itself
          details = `**Question about "${request.service_title}"**\n\n`;
          details += `**From:** <@${request.requester_discord_id}>`;
          if (request.requester_eu_name) {
            details += ` (${request.requester_eu_name})`;
          }
          details += '\n\n';
          details += `> ${questionText}\n\n`;
          details += `---\n`;
          details += `Discuss in this thread. The customer can use the **Submit Request** button below to convert this question into an actual service request when ready.`;
        } else {
          // Full details for actual service requests
          details = `**Service Request**\n\n`;
          details += `**Service:** ${request.service_title}\n`;
          details += `**Type:** ${request.service_type.charAt(0).toUpperCase() + request.service_type.slice(1)}\n`;
          details += `**Customer:** <@${request.requester_discord_id}>`;
          if (request.requester_eu_name) {
            details += ` (${request.requester_eu_name})`;
          }
          details += '\n';

          // Transportation-specific details
          if (request.service_type === 'transportation') {
            const needsPickup = request.customer_planet_id &&
              request.provider_planet_id &&
              request.customer_planet_id !== request.provider_planet_id;
            const pickupFeeWaived = request.ticket_waives_fee || false;

            if (request.customer_planet_id) {
              details += `**Pickup Location:** ${getPlanetName(request.customer_planet_id)}`;
              if (request.pickup_location) {
                details += ` (${request.pickup_location})`;
              }
              details += '\n';
            }

            if (request.dropoff_location) {
              const dropoffPlanetId = parseInt(request.dropoff_location);
              if (!isNaN(dropoffPlanetId)) {
                details += `**Destination:** ${getPlanetName(dropoffPlanetId)}\n`;
              }
            }

            if (needsPickup && !pickupFeeWaived) {
              details += `\n**Note:** Pickup fee may apply (provider is on a different planet).\n`;
            } else if (needsPickup && pickupFeeWaived) {
              details += `\n**Note:** Pickup fee waived by ticket.\n`;
            }
          }

          // DPS/Healing-specific details
          if (request.service_type === 'healing' || request.service_type === 'dps') {
            if (request.service_planet_id) {
              details += `**Location:** ${getPlanetName(request.service_planet_id)}\n`;
            }

            if (request.requested_start) {
              const startTime = new Date(request.requested_start).toLocaleString('en-US', {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false
              });
              details += `**Requested Start:** ${startTime}\n`;
            }

            if (request.requested_duration_minutes) {
              const hours = Math.floor(request.requested_duration_minutes / 60);
              const mins = request.requested_duration_minutes % 60;
              details += `**Requested Duration:** ${hours > 0 ? `${hours}h ` : ''}${mins}min\n`;
            } else if (request.is_open_ended) {
              details += `**Duration:** Open-ended\n`;
            }

            const rate = request.healing_rate || request.dps_rate;
            if (rate) {
              details += `**Rate:** ${parseFloat(rate).toFixed(2)} PED/hour\n`;
            }
          }

          // Add description/notes if provided
          if (request.service_notes) {
            details += `\n**Notes:** ${request.service_notes}\n`;
          }

          details += `\n---\n`;
          details += `Use the buttons below to manage this request.`;
        }

        // Create thread with appropriate name
        const threadName = isQuestion
          ? `Question: ${request.service_title} - ${request.requester_username}`
          : `${request.service_title} - ${request.requester_username}`;

        const thread = await servicesChannel.threads.create({
          name: threadName.substring(0, 100),
          autoArchiveDuration: 1440, // 24 hours
          type: ChannelType.PrivateThread,
          reason: isQuestion ? `Question for service #${request.service_id}` : `Service request #${request.id}`
        });

        // Add provider and customer to thread
        await thread.members.add(request.provider_user_id.toString());
        await thread.members.add(request.requester_discord_id.toString());

        // Send initial message with request details and show controls button
        await thread.send({
          content: details,
          components: [buildShowControlsButton(request.id)]
        });

        // Save thread ID to database
        await setRequestThreadId(request.id, thread.id);

        console.log(`Created ${isQuestion ? 'question' : 'service request'} thread for request #${request.id} (${request.service_type})`);
      } catch (e) {
        console.error(`Error creating thread for request #${request.id}:`, e);
      }
    }

    // Archive completed/aborted request threads
    const completedRequests = await getRequestsReadyForArchive();
    for (const request of completedRequests) {
      try {
        const thread = client.channels.cache.get(request.discord_thread_id);
        if (thread && thread.isThread() && !thread.archived) {
          await thread.setArchived(true);
          console.log(`Archived service request thread for request #${request.id}`);
        }
        await clearRequestThreadId(request.id);
      } catch (e) {
        console.error(`Error archiving thread for request #${request.id}:`, e);
      }
    }
  } catch (e) {
    console.error('Error in checkOnDemandRequests:', e);
  }
}

setInterval(checkOnDemandRequests, 30 * 1000);

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
setInterval(runTicketExpiration, 60 * 60 * 1000);
runTicketExpiration(); // Run once on startup

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