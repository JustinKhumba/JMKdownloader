const express = require('express');
const cors = require('cors');
const path = require('path');

const app = express();

// Railway dynamically assigns a PORT. We must prioritize it for the server to be reachable.
// We fall back to your custom API_PORT requirement, then 3000.
const PORT = process.env.PORT || process.env.API_PORT || 3000;
const RAW_API_URL = process.env.API_URL || 'https://api.cobalt.tools/';
const CORS_WILDCARD = process.env.CORS_WILDCARD === '1' || process.env.CORS_WILDCARD === 'true';

// Clean the API URL. If it's a base domain without a path or trailing slash, add the slash.
// This prevents 301/308 redirects from stripping the POST body and causing a 400 Bad Request.
let API_URL = RAW_API_URL.trim();
if (!API_URL.endsWith('/') && !API_URL.match(/\/[a-zA-Z0-9_-]+$/)) {
    API_URL += '/';
}

// Enable JSON body parsing so the server can read the frontend's request body
app.use(express.json());
// Handle URL-encoded requests just in case
app.use(express.urlencoded({ extended: true })); 

// Apply wildcard CORS if configured
if (CORS_WILDCARD) {
    app.use(cors());
    console.log('CORS Wildcard enabled for all origins.');
}

// Serve static frontend assets from the "public" directory
app.use(express.static(path.join(__dirname, 'public')));

// Server-side Proxy Endpoint
// This prevents 400/403 errors by making a clean server-to-server request
// to the Cobalt API, bypassing strict browser Origin and CORS checks.
app.post('/api/process', async (req, res) => {
    try {
        const { url } = req.body;
        
        if (!url) {
            return res.status(400).json({ error: 'URL is required' });
        }

        // Forward the request to the Cobalt API
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                // Some WAFs or Edge Routers block default Node fetch User-Agents with 400/403.
                // Providing a standard browser User-Agent prevents this.
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            },
            // Forward the entire body to support any additional Cobalt v10 parameters
            body: JSON.stringify(req.body)
        });

        // Safely parse the response. If it's a 400 from a WAF/Router, it might be HTML, not JSON.
        const responseText = await response.text();
        let data;
        
        try {
            data = JSON.parse(responseText);
        } catch (parseError) {
            console.error('Failed to parse Cobalt response as JSON. Raw response:', responseText.substring(0, 500));
            return res.status(response.status).json({
                status: 'error',
                text: `Received non-JSON response from Cobalt API (HTTP ${response.status}). Check server logs or ensure API_URL is correct.`
            });
        }

        // Forward the HTTP status code from Cobalt
        if (!response.ok) {
            return res.status(response.status).json(data);
        }

        res.json(data);
    } catch (error) {
        console.error('Cobalt API proxy error:', error);
        res.status(500).json({ status: 'error', text: 'Internal server proxy error. Check logs.' });
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