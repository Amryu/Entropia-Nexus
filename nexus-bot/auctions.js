/**
 * Discord auction channel integration.
 * Manages embed messages in a dedicated channel, one per active auction.
 * Polls auction_audit_log to react to state changes in near-real-time.
 */
import { EmbedBuilder } from 'discord.js';
import { poolUsers, getBotConfig, setBotConfig } from './db.js';
import { isBuyoutOnly } from './common/auctionUtils.js';

const SITE_URL = 'https://entropianexus.com';

// Embed colors by status/urgency
const COLOR_ACTIVE_SAFE    = 0x2ECC71; // Green  — more than 24 hours left
const COLOR_ACTIVE_WARNING = 0xF1C40F; // Yellow — 1-24 hours left
const COLOR_ACTIVE_URGENT  = 0xE74C3C; // Red    — less than 1 hour left
const COLOR_FROZEN         = 0x3498DB; // Blue   — frozen by admin
const COLOR_ENDED          = 0x95A5A6; // Gray   — ended
const COLOR_BUYOUT         = 0x9B59B6; // Purple — bought out
const COLOR_CANCELLED      = 0x7F8C8D; // Dark gray — cancelled

// Time thresholds (ms)
const URGENT_THRESHOLD_MS  = 60 * 60 * 1000;       // 1 hour
const WARNING_THRESHOLD_MS = 24 * 60 * 60 * 1000;   // 24 hours

// How long to keep ended/settled embeds before deleting (ms)
const CLEANUP_DELAY_MS = 30 * 60 * 1000; // 30 minutes

// In-memory cleanup timeouts (lost on restart — fullSync handles cleanup)
const cleanupTimeouts = new Map();

// Re-entrancy guard — prevents overlapping checkAuctions calls
let checking = false;


// ---- Database Queries ----

async function getAuditLogSince(lastId) {
  const { rows } = await poolUsers.query(
    `SELECT al.id, al.auction_id, al.action, al.details, al.created_at
     FROM auction_audit_log al
     WHERE al.id > $1
     ORDER BY al.id ASC`,
    [lastId]
  );
  return rows;
}

async function getActiveAuctions() {
  const { rows } = await poolUsers.query(
    `SELECT a.*, u.eu_name AS seller_name
     FROM auctions a
     LEFT JOIN users u ON u.id = a.seller_id
     WHERE a.status IN ('active', 'frozen')
       AND a.deleted_at IS NULL
     ORDER BY a.ends_at ASC NULLS LAST`
  );
  return rows;
}

async function getMaxAuditLogId() {
  const { rows } = await poolUsers.query(
    `SELECT COALESCE(MAX(id), 0) AS max_id FROM auction_audit_log`
  );
  return parseInt(rows[0].max_id, 10);
}

async function getAuctionForEmbed(auctionId) {
  const { rows } = await poolUsers.query(
    `SELECT a.*, u.eu_name AS seller_name
     FROM auctions a
     LEFT JOIN users u ON u.id = a.seller_id
     WHERE a.id = $1`,
    [auctionId]
  );
  return rows[0] || null;
}

async function setAuctionMessageId(auctionId, messageId) {
  await poolUsers.query(
    `UPDATE auctions SET discord_message_id = $2 WHERE id = $1`,
    [auctionId, messageId]
  );
}

async function clearAuctionMessageId(auctionId) {
  await poolUsers.query(
    `UPDATE auctions SET discord_message_id = NULL WHERE id = $1`,
    [auctionId]
  );
}


// ---- Embed Builder ----

function getEmbedColor(auction) {
  const status = auction.status;

  if (status === 'frozen') return COLOR_FROZEN;
  if (status === 'cancelled') return COLOR_CANCELLED;

  if (status === 'ended' || status === 'settled') {
    const wasBuyout = auction.buyout_price &&
      parseFloat(auction.current_bid) >= parseFloat(auction.buyout_price);
    return wasBuyout ? COLOR_BUYOUT : COLOR_ENDED;
  }

  if (status === 'active' && auction.ends_at) {
    const timeLeft = new Date(auction.ends_at).getTime() - Date.now();
    if (timeLeft < URGENT_THRESHOLD_MS) return COLOR_ACTIVE_URGENT;
    if (timeLeft < WARNING_THRESHOLD_MS) return COLOR_ACTIVE_WARNING;
    return COLOR_ACTIVE_SAFE;
  }

  return COLOR_ACTIVE_SAFE;
}

function buildAuctionEmbed(auction) {
  const embed = new EmbedBuilder();
  const endsAt = auction.ends_at ? new Date(auction.ends_at) : null;
  const endsAtUnix = endsAt ? Math.floor(endsAt.getTime() / 1000) : null;
  const status = auction.status;

  embed.setTitle(auction.title);
  embed.setURL(`${SITE_URL}/market/auction/${auction.id}`);
  embed.setColor(getEmbedColor(auction));

  const fields = [];

  // Starting Bid
  fields.push({
    name: 'Starting Bid',
    value: `${parseFloat(auction.starting_bid).toFixed(2)} PED`,
    inline: true
  });

  // Current Bid
  if (auction.bid_count > 0) {
    fields.push({
      name: 'Current Bid',
      value: `${parseFloat(auction.current_bid).toFixed(2)} PED (${auction.bid_count} bid${auction.bid_count !== 1 ? 's' : ''})`,
      inline: true
    });
  } else {
    fields.push({
      name: 'Current Bid',
      value: isBuyoutOnly(auction) ? 'Buyout Only' : 'No bids yet',
      inline: true
    });
  }

  // Buyout price (if applicable and not buyout-only)
  if (auction.buyout_price && !isBuyoutOnly(auction)) {
    fields.push({
      name: 'Buyout',
      value: `${parseFloat(auction.buyout_price).toFixed(2)} PED`,
      inline: true
    });
  }

  // Time / Status
  if (status === 'active' && endsAtUnix) {
    fields.push({
      name: 'Ends',
      value: `<t:${endsAtUnix}:R> (<t:${endsAtUnix}:f>)`,
      inline: false
    });
  } else if (status === 'frozen') {
    fields.push({
      name: 'Status',
      value: '\u2744\uFE0F Frozen by admin',
      inline: false
    });
  } else if (status === 'ended') {
    fields.push({
      name: 'Status',
      value: auction.bid_count > 0 ? 'Ended \u2014 Winner pending settlement' : 'Ended \u2014 No bids',
      inline: false
    });
  } else if (status === 'settled') {
    fields.push({
      name: 'Status',
      value: '\u2705 Settled',
      inline: false
    });
  } else if (status === 'cancelled') {
    fields.push({
      name: 'Status',
      value: '\u274C Cancelled',
      inline: false
    });
  }

  // Seller
  fields.push({
    name: 'Seller',
    value: auction.seller_name || 'Unknown',
    inline: true
  });

  embed.addFields(fields);
  embed.setFooter({ text: `ID: ${auction.id.slice(0, 8)}` });
  embed.setTimestamp(new Date(auction.created_at));

  return embed;
}


// ---- Message Operations ----

async function editAuctionEmbed(channel, auctionId) {
  const auction = await getAuctionForEmbed(auctionId);
  if (!auction || !auction.discord_message_id) return;

  try {
    const msg = await channel.messages.fetch(auction.discord_message_id);
    const embed = buildAuctionEmbed(auction);
    await msg.edit({ embeds: [embed] });
  } catch (e) {
    if (e.code === 10008) {
      // Unknown Message — deleted externally
      console.log(`Auction ${auctionId}: Discord message not found, clearing reference`);
      await clearAuctionMessageId(auctionId);
    } else {
      throw e;
    }
  }
}

async function deleteAuctionMessage(channel, auctionId) {
  const auction = await getAuctionForEmbed(auctionId);
  if (!auction || !auction.discord_message_id) return;

  try {
    const msg = await channel.messages.fetch(auction.discord_message_id);
    await msg.delete();
  } catch (e) {
    if (e.code !== 10008) {
      console.error(`Failed to delete auction message for ${auctionId}:`, e.message);
    }
  }
  await clearAuctionMessageId(auctionId);
}

function scheduleMessageCleanup(channel, auctionId, delayMs) {
  if (cleanupTimeouts.has(auctionId)) {
    clearTimeout(cleanupTimeouts.get(auctionId));
  }

  const timeout = setTimeout(async () => {
    cleanupTimeouts.delete(auctionId);
    try {
      await deleteAuctionMessage(channel, auctionId);
    } catch (e) {
      console.error(`Error in scheduled cleanup for auction ${auctionId}:`, e);
    }
  }, delayMs);

  cleanupTimeouts.set(auctionId, timeout);
}


// ---- Audit Log Processing ----

async function processAuditEntry(channel, entry) {
  const auctionId = entry.auction_id;

  switch (entry.action) {
    case 'activated': {
      const auction = await getAuctionForEmbed(auctionId);
      if (!auction) break;
      // If embed already exists (e.g. from fullSync), update instead of duplicating
      if (auction.discord_message_id) {
        await editAuctionEmbed(channel, auctionId);
      } else {
        const embed = buildAuctionEmbed(auction);
        const msg = await channel.send({ embeds: [embed] });
        await setAuctionMessageId(auctionId, msg.id);
      }
      break;
    }

    case 'bid_placed':
    case 'edited':
    case 'bid_rolled_back':
    case 'frozen':
    case 'unfrozen': {
      await editAuctionEmbed(channel, auctionId);
      break;
    }

    case 'buyout': {
      // Buyout sets status to 'ended' without a separate 'ended' audit entry
      await editAuctionEmbed(channel, auctionId);
      scheduleMessageCleanup(channel, auctionId, CLEANUP_DELAY_MS);
      break;
    }

    case 'ended': {
      await editAuctionEmbed(channel, auctionId);
      scheduleMessageCleanup(channel, auctionId, CLEANUP_DELAY_MS);
      break;
    }

    case 'settled': {
      await editAuctionEmbed(channel, auctionId);
      scheduleMessageCleanup(channel, auctionId, CLEANUP_DELAY_MS);
      break;
    }

    case 'cancelled_by_seller':
    case 'cancelled_by_admin': {
      await deleteAuctionMessage(channel, auctionId);
      break;
    }

    // 'created' = draft, no embed
    default:
      break;
  }
}


// ---- Full Sync (first run / restart recovery) ----

async function fullSync(channel) {
  console.log('Auction channel: performing full sync...');

  const auctions = await getActiveAuctions();
  let synced = 0;

  for (const auction of auctions) {
    try {
      if (auction.discord_message_id) {
        // Verify message still exists and update it
        try {
          const msg = await channel.messages.fetch(auction.discord_message_id);
          const embed = buildAuctionEmbed(auction);
          await msg.edit({ embeds: [embed] });
        } catch (e) {
          if (e.code === 10008) {
            // Message deleted — repost
            const embed = buildAuctionEmbed(auction);
            const msg = await channel.send({ embeds: [embed] });
            await setAuctionMessageId(auction.id, msg.id);
          } else {
            throw e;
          }
        }
      } else {
        // No message yet — post new embed
        const embed = buildAuctionEmbed(auction);
        const msg = await channel.send({ embeds: [embed] });
        await setAuctionMessageId(auction.id, msg.id);
      }
      synced++;
    } catch (e) {
      console.error(`Error syncing auction ${auction.id}:`, e);
    }
  }

  // Clean up embeds for auctions no longer active
  const { rows: staleAuctions } = await poolUsers.query(
    `SELECT id, discord_message_id FROM auctions
     WHERE discord_message_id IS NOT NULL
       AND status NOT IN ('active', 'frozen')`
  );

  for (const stale of staleAuctions) {
    try {
      const msg = await channel.messages.fetch(stale.discord_message_id).catch(() => null);
      if (msg) await msg.delete().catch(() => {});
      await clearAuctionMessageId(stale.id);
    } catch (e) {
      console.error(`Error cleaning stale auction message ${stale.id}:`, e);
    }
  }

  // Set watermark to current max audit log ID
  const maxId = await getMaxAuditLogId();
  await setBotConfig('lastAuctionAuditId', String(maxId));

  console.log(`Auction channel: synced ${synced} active auctions, cleaned ${staleAuctions.length} stale`);
}


// ---- Exported Functions ----

/**
 * Main auction check loop. Called every 30 seconds from bot.js.
 * Polls audit log for new entries and updates Discord embeds accordingly.
 */
export async function checkAuctions(client, config) {
  if (checking) return; // Prevent overlapping runs (fullSync can be slow)
  checking = true;

  try {
    const channelId = config.auctionChannelId;
    if (!channelId) return;

    const channel = client.channels.cache.get(channelId);
    if (!channel) {
      console.error('Auction channel not found:', channelId);
      return;
    }

    // Get watermark
    const rawWatermark = await getBotConfig('lastAuctionAuditId');
    let lastId = parseInt(rawWatermark || '0', 10);

    // First run — do full sync
    if (!lastId) {
      await fullSync(channel);
      return;
    }

    // Get new audit log entries since watermark
    const entries = await getAuditLogSince(lastId);
    if (entries.length === 0) return;

    for (const entry of entries) {
      try {
        await processAuditEntry(channel, entry);
      } catch (e) {
        console.error(`Error processing auction audit #${entry.id} (${entry.action}):`, e);
      }
    }

    // Update watermark
    const newWatermark = entries[entries.length - 1].id;
    await setBotConfig('lastAuctionAuditId', String(newWatermark));
  } finally {
    checking = false;
  }
}

/**
 * Refresh embed colors for active auctions.
 * Called every 5 minutes to update urgency colors as time passes.
 * Only edits messages whose color actually changed.
 */
export async function refreshAuctionColors(client, config) {
  const channelId = config.auctionChannelId;
  if (!channelId) return;

  const channel = client.channels.cache.get(channelId);
  if (!channel) return;

  const auctions = await getActiveAuctions();

  for (const auction of auctions) {
    if (!auction.discord_message_id) continue;

    try {
      const msg = await channel.messages.fetch(auction.discord_message_id);
      const currentColor = msg.embeds[0]?.color;
      const newColor = getEmbedColor(auction);

      // Only edit if color changed
      if (currentColor !== newColor) {
        const embed = buildAuctionEmbed(auction);
        await msg.edit({ embeds: [embed] });
      }
    } catch (e) {
      if (e.code === 10008) {
        await clearAuctionMessageId(auction.id);
      }
      // Silently ignore other errors during refresh
    }
  }
}
