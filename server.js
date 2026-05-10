const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();

// Railway dynamically assigns a PORT. We must prioritize it for the server to be reachable.
// We fall back to your custom API_PORT requirement, then 3000.
const PORT = process.env.PORT || process.env.API_PORT || 3000;
const API_URL = process.env.API_URL || 'https://api.cobalt.tools/';
const CORS_WILDCARD = process.env.CORS_WILDCARD === '1' || process.env.CORS_WILDCARD === 'true';

// Apply wildcard CORS if configured
if (CORS_WILDCARD) {
    app.use(cors());
    console.log('CORS Wildcard enabled for all origins.');
}

// Serve static frontend assets from the "public" directory
app.use(express.static(path.join(__dirname, 'public')));

// Configuration endpoint for the frontend client
// This allows the client to know where to direct the Cobalt API requests
app.get('/api/config', (req, res) => {
    res.json({
        apiUrl: API_URL
    });
});

// Fallback to serve the single-page application for any other route
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start the server bound to '0.0.0.0' so it accepts connections from Railway's edge proxy
app.listen(PORT, '0.0.0.0', () => {
    console.log(`=========================================`);
    console.log(`Server started successfully`);
    console.log(`Listening on Port : ${PORT}`);
    console.log(`Target Cobalt API : ${API_URL}`);
    console.log(`CORS Wildcard     : ${CORS_WILDCARD ? 'Enabled' : 'Disabled'}`);
    console.log(`=========================================`);
});