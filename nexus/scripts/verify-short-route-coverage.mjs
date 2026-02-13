import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { SHORT_ROUTE_MAP } from '../src/lib/server/short-url.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const routesDir = path.resolve(__dirname, '../src/routes');

const PAGE_FILE_RE = /^\+page(?:\.server)?\.(?:js|ts|svelte)$/;
const SERVER_FILE_RE = /^\+server\.(?:js|ts)$/;

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  let files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files = files.concat(walk(full));
    } else {
      files.push(full);
    }
  }
  return files;
}

function isPublicRouteFile(filePath) {
  const relative = path.relative(routesDir, filePath).replace(/\\/g, '/');
  if (relative.startsWith('api/') || relative.startsWith('admin/')) return false;
  const fileName = path.basename(filePath);
  return PAGE_FILE_RE.test(fileName) || SERVER_FILE_RE.test(fileName);
}

function routePathFromFile(filePath) {
  const relativeDir = path.relative(routesDir, path.dirname(filePath)).replace(/\\/g, '/');
  if (!relativeDir || relativeDir === '.') return '/';
  return `/${relativeDir}`;
}

function coversPrefix(routePath, mappedPrefix) {
  if (mappedPrefix === '/') return routePath === '/';
  return routePath === mappedPrefix || routePath.startsWith(`${mappedPrefix}/`);
}

function verifyCodeMap() {
  const entries = Object.entries(SHORT_ROUTE_MAP);
  const invalidCodes = entries
    .map(([code]) => code)
    .filter((code) => !/^[a-z0-9]{1,2}$/.test(code));

  if (invalidCodes.length > 0) {
    throw new Error(`Invalid short code(s): ${invalidCodes.join(', ')}. Codes must be lowercase 1-2 alphanumeric chars.`);
  }
}

function main() {
  verifyCodeMap();

  const files = walk(routesDir).filter(isPublicRouteFile);
  const routePaths = [...new Set(files.map(routePathFromFile))].sort();
  const prefixes = Object.values(SHORT_ROUTE_MAP);

  const uncovered = routePaths.filter((routePath) =>
    !prefixes.some((prefix) => coversPrefix(routePath, prefix))
  );

  if (uncovered.length > 0) {
    console.error('[short-url] Uncovered public route templates:');
    for (const routePath of uncovered) console.error(` - ${routePath}`);
    process.exit(1);
  }

  console.log(`[short-url] Coverage OK (${routePaths.length} public route templates covered).`);
}

main();

