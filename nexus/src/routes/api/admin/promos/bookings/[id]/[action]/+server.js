// @ts-nocheck
import { error, json } from '@sveltejs/kit';
import { getPromoBookingById, updatePromoBooking } from '$lib/server/db.js';
import { requireAdminAPI } from '$lib/server/auth.js';

const VALID_ACTIONS = ['approve', 'reject', 'activate'];

export async function POST({ params, request, locals }) {
  const user = requireAdminAPI(locals);

  const { action } = params;
  if (!VALID_ACTIONS.includes(action)) {
    throw error(400, `Invalid action: ${action}. Must be one of: ${VALID_ACTIONS.join(', ')}`);
  }

  const id = parseInt(params.id, 10);
  const booking = await getPromoBookingById(id);
  if (!booking) {
    return json({ error: 'Booking not found' }, { status: 404 });
  }

  // Validate status transitions
  const allowedTransitions = {
    approve: ['pending'],
    reject: ['pending', 'approved'],
    activate: ['approved']
  };

  if (!allowedTransitions[action].includes(booking.status)) {
    return json({ error: `Cannot ${action} a booking with status '${booking.status}'.` }, { status: 400 });
  }

  const body = await request.json().catch(() => ({}));
  let fields;

  switch (action) {
    case 'approve': {
      const price = body.price ?? booking.price;
      if (!price) {
        return json({ error: 'Price must be set before approving' }, { status: 400 });
      }

      fields = {
        status: 'approved',
        approved_by: user.id
      };

      if (body.price != null) fields.price = body.price;

      // Auto-activate if start_date is today or in the past
      const startDate = booking.start_date ? new Date(booking.start_date) : null;
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (startDate && startDate <= today) {
        fields.status = 'active';
      }
      break;
    }

    case 'reject': {
      fields = { status: 'cancelled' };
      if (body.admin_note) {
        fields.admin_note = body.admin_note.trim();
      }
      break;
    }

    case 'activate': {
      fields = { status: 'active' };
      break;
    }
  }

  const updated = await updatePromoBooking(id, fields);
  return json(updated);
}
