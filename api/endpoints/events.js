const { getObjects, getObjectByIdOrName } = require('./utils');
const { withCache, withCachedLookup } = require('./responseCache');

const queries = {
  Events: 'SELECT * FROM ONLY "Events" ORDER BY "StartDate" DESC NULLS LAST, "Name"'
};

function formatEvent(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Properties: {
      Description: x.Description,
      StartDate: x.StartDate,
      EndDate: x.EndDate,
      IsActive: x.IsActive
    },
    Links: { "$Url": `/events/${x.Id}` }
  };
}

async function _getObjects(query, formatFn) {
  return getObjects(query, formatFn);
}

async function _getObject(idOrName, query) {
  const row = await getObjectByIdOrName(query, 'Events', idOrName);
  return row ? formatEvent(row) : null;
}

const getEvents = () => _getObjects(queries.Events, formatEvent);
const getEvent = (idOrName) => _getObject(idOrName, queries.Events);

function register(app) {
  app.get('/events', async (req, res) => {
    try {
      res.json(await withCache('/events', ['Events'], getEvents));
    } catch (err) {
      console.error('Error fetching events:', err);
      res.status(500).json({ error: 'Failed to fetch events' });
    }
  });

  app.get('/events/:event', async (req, res) => {
    try {
      const result = await withCachedLookup('/events', ['Events'], getEvents, req.params.event);
      if (result) {
        res.json(result);
      } else {
        res.status(404).json({ error: 'Event not found' });
      }
    } catch (err) {
      console.error('Error fetching event:', err);
      res.status(500).json({ error: 'Failed to fetch event' });
    }
  });
}

module.exports = { register, getEvents, getEvent };
