const express = require('express');
const cors = require('cors');
const swaggerJsDoc = require('swagger-jsdoc');
const swaggerUi = require('swagger-ui-express');
const compression = require('compression');

// Register split endpoint modules (DB + routes colocated) while keeping a single DB pool
const endpoints = require('./endpoints');
const app = express();
const port = 3000;

// --- Automatic async error forwarding ---
// Wrap async route handlers so thrown/rejected errors reach the global error middleware immediately
['get','post','put','delete','patch'].forEach(method => {
  const orig = app[method].bind(app);
  app[method] = (path, ...handlers) => {
    const wrapped = handlers.map(h => {
      if (typeof h === 'function' && h.constructor && h.constructor.name === 'AsyncFunction') {
        return function wrappedAsyncHandler(req, res, next) {
          Promise.resolve(h(req, res, next)).catch(next);
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
    if (!res.headersSent) {
      console.error('Request timed out:', req.method, req.originalUrl);
      res.status(503).json({ error: 'Timeout', message: 'Request exceeded time limit' });
    }
  });
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