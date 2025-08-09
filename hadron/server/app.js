const WebSocket = require('ws');
const http = require('http');
const crypto = require('crypto');

const server = http.createServer();
const wss = new WebSocket.Server({ server });

const clients = new Map();
const commandQueue = new Map(); // Map to store commands for each user
const game = {
  players: [],
  enemies: [],
  instances: [],
};

function generateSessionId() {
  return crypto.randomBytes(16).toString('hex');
}

function authenticate(sessionId) {
  // Placeholder for actual authentication logic
  return sessionId && sessionId.length === 32;
}

wss.on('connection', (ws) => {
  let sessionId = null;

  ws.on('message', (message) => {
    const data = JSON.parse(message);

    if (data.type === 'authenticate') {
      if (authenticate(data.sessionId)) {
        sessionId = data.sessionId;
        clients.set(sessionId, ws);
        commandQueue.set(sessionId, []); // Initialize an empty command queue for the user
        ws.send(JSON.stringify({ type: 'authenticated' }));
      } else {
        ws.send(JSON.stringify({ type: 'error', message: 'Invalid session ID' }));
      }
    } else if (sessionId) {      
      if (!commandQueue.has(sessionId)) {
        commandQueue.set(sessionId, []);
      }
      
      const userCommands = commandQueue.get(sessionId);
      userCommands.set(data.type, data); // Overwrite any existing command of the same type
    } else {
      ws.send(JSON.stringify({ type: 'error', message: 'Not authenticated' }));
    }
  });

  ws.on('close', () => {
    if (sessionId) {
      clients.delete(sessionId);
      commandQueue.delete(sessionId); // Remove the user's command queue on disconnect
    }
  });
});

function gameLoop() {
  // Placeholder for game logic
  console.log('Processing game logic...');

  // Process commands for each user
  for (const [sessionId, commands] of commandQueue.entries()) {
    while (commands.length > 0) {
      const command = commands.shift(); // Remove the command from the queue
      console.log(`Processing command for ${sessionId}:`, command);

      // Example: Handle specific command types
      if (command.type === 'move') {
        console.log(`User ${sessionId} moved to position:`, command.payload.position);
      } else if (command.type === 'attack') {
        console.log(`User ${sessionId} attacked target:`, command.payload.targetId);
      } else {
        console.log(`Unknown command type from ${sessionId}:`, command.type);
      }
    }
  }

  for (const [sessionId, ws] of clients.entries()) {
    const player = game.players.find(player => player.sessionId === sessionId);
    if (!player) continue; // Skip if player not found

    // Placeholder for sending game state to clients
    const gameState = {
      player: player,
      enemies: game.enemies.filter(enemy => enemy.aggro_table.includes(player.id)),
      instance: game.instances.find(instance => instance.players.includes(player.id)),
    };
    ws.send(JSON.stringify({ type: 'gameState', payload: gameState }));
  }
}

server.listen(8080, () => {
  console.log('Server is listening on port 8080');
  setInterval(gameLoop, 1000);
});