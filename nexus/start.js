// start.mjs
import { config } from 'dotenv';
import { spawn } from 'child_process';
import path from 'path';

// Load environment variables from .env.production
const env = config({ path: path.resolve(process.cwd(), '.env.production') }).parsed;

// Filter out variables that start with VITE_
const filteredEnv = Object.keys(env)
  .filter(key => !key.startsWith('VITE_'))
  .reduce((obj, key) => {
    obj[key] = env[key];
    return obj;
  }, {});

// Start the application with the environment variables
const host = process.argv[2] || '127.0.0.1';
const port = process.argv[3] || 3001;

const start = spawn('node', ['build'], { env: { ...process.env, ...filteredEnv, HOST: host, PORT: port } });

start.stdout.on('data', (data) => {
  console.log(`${data}`);
});

start.stderr.on('data', (data) => {
  console.error(`${data}`);
});