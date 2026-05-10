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

// Middleware to parse JSON bodies from frontend requests
app.use(express.json());

// Serve static frontend assets from the "public" directory
app.use(express.static(path.join(__dirname, 'public')));

// Configuration endpoint for the frontend client (Kept for backward compatibility)
app.get('/api/config', (req, res) => {
    res.json({
        apiUrl: API_URL
    });
});

// Proxy endpoint to handle requests to Cobalt API securely
// This bypasses browser CORS & Origin restrictions that public instances enforce
app.post('/api/process', async (req, res) => {
    try {
        const { url } = req.body;
        
        if (!url) {
            return res.status(400).json({ error: { text: 'No URL provided by the client.' } });
        }

        // Proxy the request to the configured Cobalt API
        const cobaltResponse = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                // Custom User-Agent helps prevent blocks on public API instances
                'User-Agent': 'UniversalMediaDownloader/1.0 (Node.js)'
            },
            body: JSON.stringify({ url })
        });

        // Parse the response from Cobalt
        const data = await cobaltResponse.json();
        
        // Return the exact status and data back to the frontend
        res.status(cobaltResponse.status).json(data);
    } catch (error) {
        console.error('Error proxying request to Cobalt API:', error.message);
        res.status(500).json({ error: { text: 'Internal Server Error: Could not connect to the media processor.' } });
    }
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