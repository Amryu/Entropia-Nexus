// @ts-nocheck
import { getResponse } from '$lib/util';
import { checkRateLimit } from '$lib/server/rateLimiter.js';
import { getServiceById, createServiceRequest } from '$lib/server/db';

export async function POST({ params, request, locals }) {
  const user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to ask a question.' }, 401);
  }

  const rateCheck = checkRateLimit(`services:question:${user.id}`, 5, 60_000);
  if (!rateCheck.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }
  const rateCheckH = checkRateLimit(`services:question-h:${user.id}`, 20, 3_600_000);
  if (!rateCheckH.allowed) {
    return getResponse({ error: 'Too many requests. Please try again later.' }, 429);
  }

  const serviceId = parseInt(params.id);
  if (isNaN(serviceId)) {
    return getResponse({ error: 'Invalid service ID.' }, 400);
  }

  try {
    const body = await request.json();
    const { message } = body;

    if (!message || !message.trim()) {
      return getResponse({ error: 'Question message is required.' }, 400);
    }

    // Get the service
    const service = await getServiceById(serviceId);
    if (!service) {
      return getResponse({ error: 'Service not found.' }, 404);
    }

    // Check if user is the owner (only admins can ask questions on their own services)
    if (service.user_id === user.id && !user?.grants?.includes('admin.panel')) {
      return getResponse({ error: 'You cannot ask questions on your own service.' }, 403);
    }

    // Create a service request with the question
    // Using 'pending' status so it gets picked up by the bot for thread creation
    // Store the question in service_notes with a [QUESTION] prefix
    const requestData = {
      service_id: serviceId,
      requester_id: user.id,
      status: 'pending',
      service_notes: `[QUESTION] ${message.trim()}`
    };

    const newRequest = await createServiceRequest(requestData);

    return getResponse({
      success: true,
      request: newRequest,
      message: 'Your question has been sent to the provider. A Discord thread will be created for you to discuss.'
    }, 201);
  } catch (error) {
    console.error('Error creating question:', error);
    return getResponse({ error: 'Failed to send question.' }, 500);
  }
}
