# Entropia Nexus Discord Bot Guidelines

## Project Overview

**Framework**: Discord.js v14  
**Language**: JavaScript (ES Modules)  
**Database**: PostgreSQL (via pg)  
**Purpose**: Discord bot for community management, change tracking, and database update workflows

## Technology Stack

- **Discord.js v14** - Discord bot framework
- **pg** - PostgreSQL client
- **dotenv** - Environment configuration
- **js-yaml** - YAML parsing for change files
- **Ajv** - JSON schema validation

## Project Structure

```
nexus-bot/
├── commands/              # Slash command handlers
│   ├── approve.js         # Approve pending changes
│   ├── reject.js          # Reject pending changes
│   ├── list.js            # List pending changes
│   └── ...
├── changes/               # Change tracking YAML files
│   └── pending/           # Pending changes awaiting approval
├── common/                # Shared schemas and utilities (symlinked)
├── bot.js                 # Main bot application
├── db.js                  # Database queries
├── change.js              # Change validation and comparison
├── util.js                # Utility functions
├── config.json            # Bot configuration (not committed)
├── deploy-commands.js     # Deploy slash commands to Discord
├── package.json
├── .env.example           # Environment template
└── .env                   # Environment variables (not committed)
```

## Coding Guidelines

### General Principles

1. **ES Modules**: Use `import/export` syntax (not CommonJS)
2. **Async/Await**: All Discord interactions are async
3. **Error Handling**: Always catch and log errors
4. **Ephemeral Responses**: Use ephemeral messages for sensitive info
5. **Thread Management**: Create threads for change discussions
6. **Change Tracking**: All DB changes go through approval workflow

### Discord.js Patterns

#### Client Initialization

```javascript
import { Client, GatewayIntentBits } from 'discord.js';

const client = new Client({ 
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.GuildMessageReactions,
    GatewayIntentBits.GuildMembers
  ]
});

client.on('ready', () => {
  console.log(`Logged in as ${client.user.tag}!`);
});

client.login(process.env.DISCORD_TOKEN);
```

#### Slash Command Pattern

```javascript
// commands/mycommand.js
import { SlashCommandBuilder } from 'discord.js';

export const data = new SlashCommandBuilder()
  .setName('mycommand')
  .setDescription('Does something cool')
  .addStringOption(option =>
    option.setName('input')
      .setDescription('Input text')
      .setRequired(true)
  );

export async function execute(interaction) {
  const input = interaction.options.getString('input');
  
  try {
    // Do work
    await interaction.reply({
      content: `Processed: ${input}`,
      ephemeral: true // Only visible to user
    });
  } catch (error) {
    console.error('Command error:', error);
    await interaction.reply({
      content: 'An error occurred!',
      ephemeral: true
    });
  }
}
```

#### Loading Commands Dynamically

```javascript
// In bot.js
const commandsPath = join(__dirname, 'commands');
const commandFiles = readdirSync(commandsPath).filter(f => f.endsWith('.js'));

client.commands = new Collection();

for (const file of commandFiles) {
  const filePath = pathToFileURL(join(commandsPath, file));
  const command = await import(filePath.href);
  client.commands.set(command.data.name, command);
}
```

### Database Access

#### Connection Setup

```javascript
// db.js
import pg from 'pg';
import dotenv from 'dotenv';

dotenv.config();

const pool = new pg.Pool({
  user: process.env.DB_USER,
  host: process.env.DB_HOST,
  database: process.env.DB_NAME,
  password: process.env.DB_PASSWORD,
  port: process.env.DB_PORT
});

export default pool;
```

#### Query Functions

```javascript
// db.js
export async function getUsers() {
  const result = await pool.query('SELECT * FROM users ORDER BY username');
  return result.rows;
}

export async function getUserById(id) {
  const result = await pool.query(
    'SELECT * FROM users WHERE id = $1',
    [id]
  );
  return result.rows[0];
}

export async function createUser(username, discordId) {
  const result = await pool.query(
    'INSERT INTO users (username, discord_id) VALUES ($1, $2) RETURNING *',
    [username, discordId]
  );
  return result.rows[0];
}
```

#### Using in Commands

```javascript
import { getUsers, getUserById } from './db.js';

export async function execute(interaction) {
  const userId = interaction.options.getInteger('user');
  const user = await getUserById(userId);
  
  if (!user) {
    return interaction.reply({
      content: 'User not found!',
      ephemeral: true
    });
  }
  
  await interaction.reply(`Found user: ${user.username}`);
}
```

### Change Tracking System

#### Change File Format (YAML)

```yaml
changeType: create
entityType: Weapon
data:
  Name: New Weapon
  Properties:
    Damage: 10
    DamageType: Cut
submittedBy: 178245652633878528
submittedAt: '2026-01-27T10:30:00Z'
status: pending
```

#### Validating Changes

```javascript
// change.js
import { validate } from './util.js';

export function validateChange(changeData) {
  const schema = getSchemaForEntityType(changeData.entityType);
  const valid = validate(changeData.data, schema);
  
  if (!valid) {
    throw new Error('Validation failed: ' + validate.errors);
  }
  
  return true;
}
```

#### Comparing Changes

```javascript
import { compareJson } from './change.js';

export async function showDiff(interaction, changeId) {
  const change = await getChangeById(changeId);
  const current = await getCurrentData(change.entityType, change.entityId);
  
  const diff = compareJson(current, change.data);
  
  await interaction.reply({
    content: '```diff\n' + diff + '\n```',
    ephemeral: false
  });
}
```

### Thread Management

#### Creating Threads for Changes

```javascript
export async function createChangeThread(channel, change) {
  const thread = await channel.threads.create({
    name: `Change #${change.id}: ${change.entityType}`,
    autoArchiveDuration: 1440, // 24 hours
    reason: 'New change submitted for review'
  });
  
  // Store thread ID in database
  await setChangeThreadId(change.id, thread.id);
  
  return thread;
}
```

#### Posting to Threads

```javascript
async function notifyReviewers(thread, change) {
  await thread.send({
    content: `New ${change.changeType} for ${change.entityType}\n` +
             `Submitted by: <@${change.submittedBy}>\n` +
             `React with ✅ to approve or ❌ to reject`
  });
}
```

### Permission Checking

```javascript
const ADMIN_USER_ID = '178245652633878528';

function isAdmin(userId) {
  return userId === ADMIN_USER_ID;
}

function hasRole(member, roleName) {
  return member.roles.cache.some(role => role.name === roleName);
}

export async function execute(interaction) {
  if (!isAdmin(interaction.user.id)) {
    return interaction.reply({
      content: 'You do not have permission to use this command!',
      ephemeral: true
    });
  }
  
  // Command logic
}
```

### Configuration Management

```javascript
// bot.js
import { readFileSync, writeFileSync } from 'node:fs';

const config = JSON.parse(readFileSync('config.json', 'utf8'));

export function setConfigValue(key, value) {
  config[key] = value;
  writeFileSync('config.json', JSON.stringify(config, null, 2));
}

export function getConfigValue(key) {
  return config[key];
}
```

### Error Handling

#### Interaction Errors

```javascript
try {
  await interaction.reply('Processing...');
  await doSomethingAsync();
  await interaction.editReply('Done!');
} catch (error) {
  console.error('Error:', error);
  
  // Reply or edit based on whether we've already responded
  if (interaction.replied || interaction.deferred) {
    await interaction.editReply({
      content: 'An error occurred!',
      ephemeral: true
    });
  } else {
    await interaction.reply({
      content: 'An error occurred!',
      ephemeral: true
    });
  }
}
```

#### Deferring Responses

For long-running operations:

```javascript
export async function execute(interaction) {
  // Defer immediately to prevent timeout
  await interaction.deferReply({ ephemeral: true });
  
  try {
    // Long operation
    const result = await processLongOperation();
    
    await interaction.editReply({
      content: `Result: ${result}`
    });
  } catch (error) {
    console.error(error);
    await interaction.editReply({
      content: 'Operation failed!'
    });
  }
}
```

### Deploying Commands

```javascript
// deploy-commands.js
import { REST, Routes } from 'discord.js';
import { readdirSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';

const commands = [];
const commandFiles = readdirSync('./commands').filter(f => f.endsWith('.js'));

for (const file of commandFiles) {
  const command = await import(`./commands/${file}`);
  commands.push(command.data.toJSON());
}

const rest = new REST().setToken(process.env.DISCORD_TOKEN);

await rest.put(
  Routes.applicationGuildCommands(
    process.env.CLIENT_ID,
    process.env.GUILD_ID
  ),
  { body: commands }
);

console.log('Successfully deployed commands!');
```

## Development Workflow

### Running Locally

```bash
# Start the bot
npm start

# Deploy slash commands
node deploy-commands.js
```

### Testing Commands

1. Deploy commands to your test server
2. Invoke commands in Discord
3. Check console logs for errors
4. Iterate and redeploy

### Environment Variables

Required in `.env`:

```env
DISCORD_TOKEN=your_bot_token
CLIENT_ID=your_client_id
GUILD_ID=your_guild_id

# Database
DB_USER=nexus_users
DB_HOST=localhost
DB_NAME=nexus_users
DB_PASSWORD=your_password
DB_PORT=5432
```

## Common Patterns

### User Lookup

```javascript
export async function execute(interaction) {
  const discordId = interaction.user.id;
  const user = await getUserByDiscordId(discordId);
  
  if (!user) {
    return interaction.reply({
      content: 'You are not registered! Use /register first.',
      ephemeral: true
    });
  }
  
  // Continue with user
}
```

### Change Approval Workflow

```javascript
// 1. User submits change
export async function submitChange(interaction, entityType, data) {
  const changeId = await createChange({
    changeType: 'create',
    entityType,
    data,
    submittedBy: interaction.user.id,
    status: 'pending'
  });
  
  const channel = await client.channels.fetch(CHANGES_CHANNEL_ID);
  const thread = await createChangeThread(channel, changeId);
  
  await interaction.reply({
    content: `Change submitted! Track it here: <#${thread.id}>`,
    ephemeral: true
  });
}

// 2. Admin approves
export async function approveChange(interaction, changeId) {
  if (!isAdmin(interaction.user.id)) {
    return interaction.reply({
      content: 'Permission denied!',
      ephemeral: true
    });
  }
  
  await interaction.deferReply({ ephemeral: true });
  
  const change = await getChangeById(changeId);
  await applyChangeToDB(change);
  await updateChangeStatus(changeId, 'approved');
  
  await interaction.editReply('Change approved and applied!');
}
```

### Pagination with Buttons

```javascript
import { ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';

export async function showPaginatedList(interaction, items) {
  let page = 0;
  const pageSize = 10;
  
  const getPage = () => items.slice(page * pageSize, (page + 1) * pageSize);
  
  const row = new ActionRowBuilder()
    .addComponents(
      new ButtonBuilder()
        .setCustomId('prev')
        .setLabel('Previous')
        .setStyle(ButtonStyle.Primary)
        .setDisabled(page === 0),
      new ButtonBuilder()
        .setCustomId('next')
        .setLabel('Next')
        .setStyle(ButtonStyle.Primary)
        .setDisabled((page + 1) * pageSize >= items.length)
    );
  
  const response = await interaction.reply({
    content: formatPage(getPage()),
    components: [row]
  });
  
  // Button collector
  const collector = response.createMessageComponentCollector({
    time: 60000 // 1 minute
  });
  
  collector.on('collect', async i => {
    if (i.customId === 'next') page++;
    if (i.customId === 'prev') page--;
    
    await i.update({
      content: formatPage(getPage()),
      components: [row]
    });
  });
}
```

## Best Practices

1. **Always Defer Long Operations**: Use `interaction.deferReply()` for operations >3 seconds
2. **Use Ephemeral for Errors**: Error messages should be ephemeral (private)
3. **Validate Input**: Always validate user input before processing
4. **Log Everything**: Log all command executions and errors
5. **Handle Permissions**: Check permissions before executing sensitive commands
6. **Clean Up**: Delete/archive old threads and messages
7. **Rate Limiting**: Be aware of Discord's rate limits

## Common Pitfalls to Avoid

1. ❌ Not deferring long-running operations (3+ second timeout)
2. ❌ Replying twice to the same interaction
3. ❌ Not handling errors in command execution
4. ❌ Hardcoding channel/role IDs (use config)
5. ❌ Not validating change data before applying
6. ❌ Leaving threads open indefinitely
7. ❌ Not checking permissions before admin commands

## Discord API Limits

- **Message Length**: 2000 characters max
- **Embed Fields**: 25 max per embed
- **Interaction Response Time**: 3 seconds (use defer for longer)
- **Rate Limits**: Varies by endpoint (bot handles automatically)
- **File Size**: 8MB for regular servers, 50MB for boosted

## Security Considerations

1. **Token Protection**: Never commit `.env` file
2. **Permission Checks**: Always verify user permissions
3. **SQL Injection**: Use parameterized queries
4. **Data Validation**: Validate all user-submitted data
5. **Audit Logging**: Log all administrative actions

## Deployment

- Run as a service (systemd/PM2)
- Use environment variables for all configuration
- Monitor logs for errors
- Set up restart on crash
- Keep dependencies updated

## Resources

- [Discord.js Guide](https://discordjs.guide/)
- [Discord.js Docs](https://discord.js.org/)
- [Discord API Docs](https://discord.com/developers/docs/)
- [pg Documentation](https://node-postgres.com/)
- Project README: `../README.md`
