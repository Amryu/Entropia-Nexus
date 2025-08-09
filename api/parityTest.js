#!/usr/bin/env node
/*
 Endpoint parity smoke test.
 Base URL default: http://127.0.0.1:3000 (override via BASE_URL env var).

 This script:
 1. Defines a catalog of endpoints (collection + single) to probe.
 2. For each collection endpoint expects HTTP 200 and JSON array/object.
 3. If detail sample needed, takes first item's Name or Id to query singular route (when pattern exists).
 4. Reports summary with failures and basic field presence checks (Id / Name / Properties when applicable).

 NOTE: This is a lightweight smoke test, not a strict schema validator.
*/

const http = require('http');
const https = require('https');
const { URL } = require('url');

const BASE_URL = process.env.BASE_URL || 'http://127.0.0.1:3000';
const API_PREFIX = process.env.API_PREFIX || '';// e.g., '/api' if frontend proxies to backend

function joinPath(prefix, p){
  if (!prefix) return p;
  return `${prefix.replace(/\/$/,'')}/${p.replace(/^\//,'')}`;
}

function requestJson(path) {
  return new Promise((resolve, reject) => {
    const url = new URL(joinPath(API_PREFIX, path), BASE_URL);
    const lib = url.protocol === 'https:' ? https : http;
    const req = lib.request(url, { method: 'GET' }, res => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        const contentType = res.headers['content-type'] || '';
        if (!/^application\/(json|problem\+json)/.test(contentType) && res.statusCode === 200) {
          return reject(new Error(`Non-JSON 200 response for ${url.href} content-type=${contentType}`));
        }
        if (data.length === 0) {
          return resolve({ status: res.statusCode, body: null });
        }
        try {
          const parsed = JSON.parse(data);
          resolve({ status: res.statusCode, body: parsed });
        } catch (e) {
          reject(new Error(`JSON parse failed for ${url.href}: ${e.message}`));
        }
      });
    });
    req.on('error', reject);
    req.setTimeout(8000, () => { req.destroy(new Error('Timeout')); });
    req.end();
  });
}

const endpoints = [
  { base: '/areas', single: '/areas/{key}' },
  { base: '/locations', single: '/locations/{key}' },
  { base: '/planets', single: '/planets/{key}' },
  { base: '/teleporters', single: '/teleporters/{key}' },
  { base: '/shops', single: '/shops/{key}' },
  { base: '/items', single: '/items/{key}' },
  { base: '/absorbers', single: '/absorbers/{key}' },
  { base: '/armorplatings', single: '/armorplatings/{key}' },
  { base: '/armorsets', single: '/armorsets/{key}' },
  { base: '/armors', single: '/armors/{key}' },
  { base: '/blueprintbooks', single: '/blueprintbooks/{key}' },
  { base: '/blueprints', single: '/blueprints/{key}' },
  { base: '/clothings', single: '/clothings/{key}' },
  { base: '/stimulants', single: '/stimulants/{key}' },
  { base: '/capsules', single: '/capsules/{key}' },
  { base: '/decorations', single: '/decorations/{key}' },
  { base: '/effectchips', single: '/effectchips/{key}' },
  { base: '/effects', single: '/effects/{key}' },
  { base: '/enhancers', single: '/enhancers/{key}' },
  { base: '/equipsets', single: '/equipsets/{key}' },
  { base: '/excavators', single: '/excavators/{key}' },
  { base: '/finderamplifiers', single: '/finderamplifiers/{key}' },
  { base: '/finders', single: '/finders/{key}' },
  { base: '/furniture', single: '/furniture/{key}' },
  { base: '/materials', single: '/materials/{key}' },
  { base: '/medicalchips', single: '/medicalchips/{key}' },
  { base: '/medicaltools', single: '/medicaltools/{key}' },
  { base: '/mindforceimplants', single: '/mindforceimplants/{key}' },
  { base: '/misctools', single: '/misctools/{key}' },
  { base: '/mobloots' },
  { base: '/mobmaturities', single: '/mobmaturities/{key}' },
  { base: '/mobspawns', single: '/mobspawns/{key}' },
  { base: '/mobspecies', single: '/mobspecies/{key}' },
  { base: '/mobs', single: '/mobs/{key}' },
  { base: '/pets', single: '/pets/{key}' },
  { base: '/professioncategories', single: '/professioncategories/{key}' },
  { base: '/professions', single: '/professions/{key}' },
  { base: '/skills', single: '/skills/{key}' },
  { base: '/weapons', single: '/weapons/{key}' },
  { base: '/weaponamplifiers', single: '/weaponamplifiers/{key}' },
  { base: '/weaponvisionattachments', single: '/weaponvisionattachments/{key}' },
  { base: '/teleportationchips', single: '/teleportationchips/{key}' },
  { base: '/vendors', single: '/vendors/{key}' },
  { base: '/vendoroffers' },
  { base: '/refiningrecipes', single: '/refiningrecipes/{key}' },
  { base: '/scanners', single: '/scanners/{key}' },
  { base: '/refiners', single: '/refiners/{key}' },
  // Special cases below
  { base: '/tiers', special: 'tiers' },
  { base: '/search', special: 'search' },
  { base: '/search/items', special: 'searchItems' },
  { base: '/acquisition', special: 'acquisition' },
  { base: '/usage', special: 'usage' }
];

function pickKey(entry) {
  if (!entry) return null;
  if (entry.Id != null) return entry.Id;
  if (entry.Name) return encodeURIComponent(entry.Name);
  return null;
}

(async () => {
  // Preload samples for dynamic queries
  const itemsList = await requestJson('/items').catch(()=>({ body: [] }));
  const firstItem = Array.isArray(itemsList.body) && itemsList.body.length ? itemsList.body[0] : null;
  const mobsList = await requestJson('/mobs').catch(()=>({ body: [] }));
  const firstMob = Array.isArray(mobsList.body) && mobsList.body.length ? mobsList.body[0] : null;
  const failures = [];
  for (const def of endpoints) {
    let url = def.base;
    // Handle special builders
    if (def.special === 'tiers') {
      if (firstItem && (firstItem.ItemId != null || firstItem.Id != null)) {
        const itemId = firstItem.ItemId != null ? firstItem.ItemId : firstItem.Id;
        url += `?ItemId=${encodeURIComponent(itemId)}&IsArmorSet=0`;
      } else {
        // Skip tiers if no item sample
        process.stdout.write(`Skipping ${url} (no sample item)\n`);
        continue;
      }
    } else if (def.special === 'search') {
      const q = firstItem?.Name?.slice(0,2) || 'A';
      url += `?query=${encodeURIComponent(q)}`;
    } else if (def.special === 'searchItems') {
      const q = firstItem?.Name?.slice(0,2) || 'A';
      url += `?query=${encodeURIComponent(q)}`;
    } else if (def.special === 'acquisition') {
      if (firstItem?.Name) {
        url += `?items=${encodeURIComponent(firstItem.Name)}`;
      } else {
        process.stdout.write(`Skipping ${url} (no sample item)\n`);
        continue;
      }
    } else if (def.special === 'usage') {
      if (firstItem?.Name) {
        url += `?items=${encodeURIComponent(firstItem.Name)}`;
      } else {
        process.stdout.write(`Skipping ${url} (no sample item)\n`);
        continue;
      }
    } else if (def.base === '/mobloots') {
      const qItem = firstItem?.Name;
      const qMob = firstMob?.Name;
      if (qItem) url += `?Item=${encodeURIComponent(qItem)}`;
      else if (qMob) url += `?Mob=${encodeURIComponent(qMob)}`;
    } else if (def.base === '/vendoroffers') {
      const qItem = firstItem?.Name;
      if (qItem) url += `?Item=${encodeURIComponent(qItem)}`;
    }
    process.stdout.write(`Checking ${url} ... `);
    try {
      const { status, body } = await requestJson(url);
      if (status !== 200) throw new Error(`Status ${status}`);
      if (body == null) throw new Error('Empty body');
      let arr = Array.isArray(body) ? body : (Array.isArray(body.Items) ? body.Items : null);
      if (!arr && Array.isArray(body.results)) arr = body.results;
      const sample = arr && arr.length > 0 ? arr[0] : (Array.isArray(body) ? body[0] : body);
      process.stdout.write('OK');
      if (def.single && sample) {
        const key = pickKey(sample);
        if (key) {
          const singleUrl = def.single.replace('{key}', key);
          process.stdout.write(` -> ${singleUrl} ... `);
          const singleRes = await requestJson(singleUrl);
          if (singleRes.status !== 200) throw new Error(`Single status ${singleRes.status}`);
          if (!singleRes.body || (singleRes.body.Id == null && !singleRes.body.Name)) throw new Error('Single missing Id/Name');
          process.stdout.write('OK');
        } else {
          process.stdout.write('(no key)');
        }
      }
      process.stdout.write('\n');
    } catch (e) {
      process.stdout.write('FAIL\n');
      failures.push({ endpoint: url, error: e.message });
    }
  }

  if (failures.length) {
    console.log('\nFailures:');
    failures.forEach(f => console.log('-', f.endpoint, f.error));
    process.exit(1);
  } else {
    console.log('\nAll endpoints responded successfully.');
  }
})();
