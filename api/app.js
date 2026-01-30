const express = require('express');
const cors = require('cors');
const swaggerJsDoc = require('swagger-jsdoc');
const swaggerUi = require('swagger-ui-express');
const compression = require('compression');
const { recordRequest, snapshotAndReset } = require('./metrics');

// Register split endpoint modules (DB + routes colocated) while keeping a single DB pool
const endpoints = require('./endpoints');
const app = express();
const port = parseInt(process.env.API_PORT || '3000', 10);

// --- Automatic async error forwarding ---
// Wrap async route handlers so thrown/rejected errors reach the global error middleware immediately
['get','post','put','delete','patch'].forEach(method => {
  const orig = app[method].bind(app);
  app[method] = (path, ...handlers) => {
    const wrapped = handlers.map(h => {
      if (typeof h === 'function' && h.constructor && h.constructor.name === 'AsyncFunction') {
        return function wrappedAsyncHandler(req, res, next) {
          Promise.resolve(h(req, res, next)).catch(err => {
            if (!res.headersSent && !res.writableEnded) {
              return next(err);
            }
            // Avoid double-send: just log since response is already on the wire
            console.error('Handler error after response sent:', req.method, req.originalUrl, err);
          });
        };
      }
      return h;
    });
    return orig(path, ...wrapped);
  };
});

// --- Request timeout safeguard ---
// Ensures a hung handler (e.g., unresolved promise) returns a 503 instead of stalling indefinitely
const ROUTE_TIMEOUT_MS = process.env.ROUTE_TIMEOUT_MS ? parseInt(process.env.ROUTE_TIMEOUT_MS) : 30000;
app.use((req, res, next) => {
  res.setTimeout(ROUTE_TIMEOUT_MS, () => {
    // Mark as timed-out to prevent later handlers from writing again
    res.locals.timedOut = true;
    if (!res.headersSent && !res.writableEnded) {
      console.error('Request timed out:', req.method, req.originalUrl);
      try { res.status(503).json({ error: 'Timeout', message: 'Request exceeded time limit' }); } catch {}
    }
  });
  next();
});

// --- Response guard to prevent double-send after timeout or prior writes ---
app.use((req, res, next) => {
  const origJson = res.json.bind(res);
  const origSend = res.send.bind(res);
  res.json = (body) => {
    if (res.headersSent || res.writableEnded || res.locals.timedOut) return res; 
    return origJson(body);
  };
  res.send = (body) => {
    if (res.headersSent || res.writableEnded || res.locals.timedOut) return res;
    return origSend(body);
  };
  next();
});

const swaggerOptions = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'Entropia Nexus API',
      version: '1.0.0',
      description: 'Serves all entities from the Entropia Nexus database.',
    },
    servers: [
      {
        url: 'https://api.entropianexus.com',
        description: 'Production server'
      }
    ]
  },
  // Path to the API docs (use only modular endpoint files)
  apis: ['./endpoints/*.js'],
};

const swaggerDocs = swaggerJsDoc(swaggerOptions);

app.use('/docs', swaggerUi.serve, swaggerUi.setup(swaggerDocs, { explorer: true, customCss: '.swagger-ui .topbar { display: none }', customSiteTitle: 'Entropia Nexus API', apisSorter: 'alpha', operationsSorter: 'alpha'  }));

app.use(compression());
app.use(cors());
app.use(express.json());

// Per-request timing (compact): record duration and route
app.use((req, res, next) => {
  const start = process.hrtime.bigint();
  res.on('finish', () => {
    const durMs = Number(process.hrtime.bigint() - start) / 1e6;
    const path = (req.route && req.route.path) || req.path || req.originalUrl || 'unknown';
    recordRequest(req.method, path, durMs);
  });
  next();
});

// Periodic compact performance report (no spam)
const REPORT_EVERY_MS = parseInt(process.env.METRICS_EVERY_MS || '60000', 10);
setInterval(() => {
  const mem = process.memoryUsage();
  const snap = snapshotAndReset();
  console.log('[metrics]', {
    upMs: snap.elapsedMs,
    req: { count: snap.requests, avgMs: Math.round(snap.avgReqMs), slow: snap.slowRequests },
    sql: { count: snap.queries, avgMs: Math.round(snap.avgQueryMs), slow: snap.slowQueries },
    topRoutes: snap.byRoute,
    mem: {
      rssMB: Math.round(mem.rss / 1024 / 1024),
      heapUsedMB: Math.round(mem.heapUsed / 1024 / 1024),
      extMB: Math.round(mem.external / 1024 / 1024)
    }
  });
}, REPORT_EVERY_MS).unref();

app.disable('x-powered-by');

app.listen(port, () => {
  console.log(`App running on port ${port}.`);
});

// Attach modular endpoints
try { endpoints.registerAll(app); } catch (e) { console.warn('Endpoints registration failed:', e?.message); }

app.get('/schema.json', (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.send(swaggerDocs);
});

// Global error handling middleware
app.use((err, req, res, next) => {
  console.error('API Error:', err);
  console.error('URL:', req.originalUrl);
  console.error('Method:', req.method);
  
  // Send a generic error response to prevent crashes
  if (!res.headersSent) {
    res.status(500).json({
      error: 'Internal server error',
      message: process.env.NODE_ENV === 'production' ? 'Something went wrong' : err.message
    });
  }
});

// Handle 404 errors
app.use((req, res) => {
  res.status(404).json({
    error: 'Not found',
    message: `Route ${req.originalUrl} not found`
  });
});

// Handle unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Promise Rejection:', reason);
});

// Handle uncaught exceptions  
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  console.error('Shutting down gracefully...');
  process.exit(1);
});