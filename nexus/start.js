// start.mjs
import { config } from 'dotenv';
import { spawn } from 'child_process';
import path from 'path';

// Load environment variables from .env (optional in containers)
const parsed = config({ path: path.resolve(process.cwd(), '.env') }).parsed ?? {};

// Filter out variables that start with VITE_
const filteredEnv = Object.keys(parsed)
  .filter(key => !key.startsWith('VITE_'))
  .reduce((obj, key) => {
    obj[key] = parsed[key];
    return obj;
  }, {});

// Start the application with the environment variables
const host = process.argv[2] || '0.0.0.0';
const port = process.argv[3] || 3001;

const runEnv = {
  ...process.env,
  ...filteredEnv,
  // Ensure the server binds on all interfaces in Docker
  HOST: host,
  HOSTNAME: host,
  PORT: String(port)
};
const start = spawn('node', ['build'], { env: runEnv });

start.stdout.on('data', (data) => {
  console.log(`${data}`);
});

start.stderr.on('data', (data) => {
  console.error(`${data}`);
});

start.on('error', (err) => {
  console.error('Failed to start server process:', err);
});

start.on('close', (code) => {
  console.log(`Server process exited with code ${code}`);
});