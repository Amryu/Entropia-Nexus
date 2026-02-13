import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveShortRedirect } from '../../src/lib/server/short-url.js';

const env = {
  SHORT_REDIRECT_ENABLED: 'true',
  SHORT_REDIRECT_HOSTS: 'eunex.us,www.eunex.us',
  CANONICAL_PUBLIC_URL: 'https://entropianexus.com'
};

test('short code iw expands to weapons route', () => {
  const result = resolveShortRedirect({
    host: 'eunex.us',
    path: '/iw/Adjusted~Harrier',
    search: '',
    env
  });
  assert.equal(result?.status, 301);
  assert.equal(result?.location, 'https://entropianexus.com/items/weapons/Adjusted~Harrier');
});

test('short code eo expands to exchange orders route', () => {
  const result = resolveShortRedirect({
    host: 'eunex.us',
    path: '/eo/Oknar~Zec~Zuki',
    search: '',
    env
  });
  assert.equal(result?.status, 301);
  assert.equal(result?.location, 'https://entropianexus.com/market/exchange/orders/Oknar~Zec~Zuki');
});

test('pseudo code mc maps to missions chains route', () => {
  const result = resolveShortRedirect({
    host: 'eunex.us',
    path: '/mc/Iron~Challenge',
    search: '',
    env
  });
  assert.equal(result?.status, 301);
  assert.equal(result?.location, 'https://entropianexus.com/information/missions?view=chains&chain=Iron%7EChallenge');
});

test('pseudo code eq maps to exchange with item query', () => {
  const result = resolveShortRedirect({
    host: 'eunex.us',
    path: '/eq/12345',
    search: '',
    env
  });
  assert.equal(result?.status, 301);
  assert.equal(result?.location, 'https://entropianexus.com/market/exchange?item=12345');
});

test('long-form path on short host passes through unchanged path/query', () => {
  const result = resolveShortRedirect({
    host: 'eunex.us',
    path: '/market/exchange/orders/X',
    search: '?x=1',
    env
  });
  assert.equal(result?.status, 301);
  assert.equal(result?.location, 'https://entropianexus.com/market/exchange/orders/X?x=1');
});

test('unknown short path on short host passes through unchanged path/query', () => {
  const result = resolveShortRedirect({
    host: 'eunex.us',
    path: '/unknown/path',
    search: '?x=1',
    env
  });
  assert.equal(result?.status, 301);
  assert.equal(result?.location, 'https://entropianexus.com/unknown/path?x=1');
});

test('short codes are inactive on canonical host', () => {
  const result = resolveShortRedirect({
    host: 'entropianexus.com',
    path: '/iw/foo',
    search: '',
    env
  });
  assert.equal(result, null);
});

test('short code matching is case-insensitive', () => {
  const result = resolveShortRedirect({
    host: 'eunex.us',
    path: '/IW/foo',
    search: '',
    env
  });
  assert.equal(result?.status, 301);
  assert.equal(result?.location, 'https://entropianexus.com/items/weapons/foo');
});

