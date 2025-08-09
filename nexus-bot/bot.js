import dotenv from 'dotenv';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { dump } from 'js-yaml';
import { Client, GatewayIntentBits, Collection, Events, ChannelType } from 'discord.js';
import { getUsers, getOpenChanges, setChangeThreadId, getDeletedChanges, deleteChange } from './db.js';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compareJson, validate, printSideBySide } from './change.js';

const adminUserId = '178245652633878528';

dotenv.config();
const config = JSON.parse(readFileSync('config.json', 'utf8'));

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

client.on('ready', () => {
  console.log(`Logged in as ${client.user.tag}!`);
});

client.on(Events.InteractionCreate, async interaction => {
	if (!interaction.isChatInputCommand()) return;

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
			await interaction.followUp({ content: 'There was an error while executing this command!', ephemeral: true });
		} else {
			await interaction.reply({ content: 'There was an error while executing this command!', ephemeral: true });
		}
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
  if (!channel) throw new Error('Changes channel not found');

  let lastCheck = new Date(getConfigValue('lastChangeCheck'));

  let changes = (await getOpenChanges(lastCheck)).sort((a, b) => new Date(a.last_update).getTime() - new Date(b.last_update).getTime());

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

      let newCheckTime = new Date(change.last_update);
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


setInterval(checkUnverifiedUsers, 1 * 60 * 1000);
setInterval(checkChanges, 1 * 15 * 1000);
 
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