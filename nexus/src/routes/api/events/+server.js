// @ts-nocheck
import { json } from '@sveltejs/kit';
import { getUpcomingEvents, getPastEvents, createEvent, countPendingEventsByUser, notifyAdmins } from '$lib/server/db.js';
import { requireGrantAPI } from '$lib/server/auth.js';

const MAX_PENDING_PER_USER = 5;

export async function GET({ url }) {
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '5', 10), 20);
  const include = url.searchParams.get('include') || '';

  const upcoming = await getUpcomingEvents(limit);
  if (include === 'past') {
    const pastLimit = Math.min(parseInt(url.searchParams.get('past_limit') || '10', 10), 50);
    const past = await getPastEvents(pastLimit);
    return json({ upcoming, past });
  }
  return json(upcoming);
}

export async function POST({ request, locals }) {
  const user = requireGrantAPI(locals, 'events.submit');
  const body = await request.json();

  // Validate title
  if (!body.title?.trim()) {
    return json({ error: 'Title is required' }, { status: 400 });
  }
  if (body.title.trim().length > 200) {
    return json({ error: 'Title must be 200 characters or less' }, { status: 400 });
  }

  // Validate start_date
  if (!body.start_date) {
    return json({ error: 'Start date is required' }, { status: 400 });
  }
  const startDate = new Date(body.start_date);
  if (isNaN(startDate.getTime())) {
    return json({ error: 'Invalid start date' }, { status: 400 });
  }
  const now = new Date();
  const isUserAdmin = !!user.administrator || (user.grants || []).includes('admin.panel');
  const ONE_WEEK_MS = 7 * 24 * 60 * 60 * 1000;
  if (startDate <= now) {
    if (!isUserAdmin && now - startDate > ONE_WEEK_MS) {
      return json({ error: 'Start date cannot be more than 1 week in the past' }, { status: 400 });
    }
  }

  // Validate end_date if provided
  if (body.end_date) {
    const endDate = new Date(body.end_date);
    if (isNaN(endDate.getTime())) {
      return json({ error: 'Invalid end date' }, { status: 400 });
    }
    if (endDate <= startDate) {
      return json({ error: 'End date must be after start date' }, { status: 400 });
    }
  }

  // Validate description
  if (body.description && body.description.length > 2000) {
    return json({ error: 'Description must be 2000 characters or less' }, { status: 400 });
  }

  // Validate location
  if (body.location && body.location.length > 200) {
    return json({ error: 'Location must be 200 characters or less' }, { status: 400 });
  }

  // Rate limit: max pending events per user
  const pendingCount = await countPendingEventsByUser(user.id);
  if (pendingCount >= MAX_PENDING_PER_USER) {
    return json({ error: `You can have at most ${MAX_PENDING_PER_USER} pending events. Please wait for existing submissions to be reviewed.` }, { status: 429 });
  }

  const event = await createEvent({
    title: body.title.trim(),
    description: body.description?.trim() || null,
    start_date: body.start_date,
    end_date: body.end_date || null,
    location: body.location?.trim() || null,
    type: body.type === 'official' ? 'official' : 'player_run',
    link: body.link?.trim() || null,
    image_url: body.image_url?.trim() || null,
    submitted_by: user.id
  });

  const displayName = user.eu_name || user.global_name || user.username;
  notifyAdmins(`${displayName} submitted an event for review: ${event.title}`).catch(() => {});

  return json(event, { status: 201 });
}
