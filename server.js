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
        const { url, ...otherParams } = req.body;
        
        if (!url) {
            return res.status(400).json({ error: 'URL is required' });
        }

        console.log(`[PROXY] Forwarding request for URL: ${url}`);

        // Forward the request to the Cobalt API
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                // Using a programmatic agent bypasses WAF blocks and acts strictly as a backend client.
                'User-Agent': 'NodeDownloaderProxy/1.0.0'
            },
            // Forward the entire body to support any additional parameters
            body: JSON.stringify({ url, ...otherParams })
        });

        // Safely parse the response. If it's a 400 from a WAF/Router, it might be HTML, not JSON.
        const responseText = await response.text();
        let data;
        
        try {
            data = JSON.parse(responseText);
        } catch (parseError) {
            console.error('[PROXY ERROR] Non-JSON response from Cobalt API:', responseText.substring(0, 300));
            return res.status(response.status).json({
                status: 'error',
                text: `Received an invalid response from Cobalt API (HTTP ${response.status}). Check server logs or ensure API_URL is correct.`
            });
        }

        // Handle and translate specific Cobalt API v10 internal error codes
        if (!response.ok || data.status === 'error') {
            let errorMessage = data.text || 'The Cobalt API returned an error.';
            
            // If Cobalt returns a structured error object instead of raw text
            if (data.error && data.error.code) {
                if (data.error.code === 'error.api.youtube.login') {
                    errorMessage = 'YouTube blocked the request. Your Cobalt backend requires YouTube cookies (YOUTUBE_COOKIES) to be configured.';
                } else {
                    errorMessage = `Cobalt Error: ${data.error.code}`;
                }
            }

            console.error(`[COBALT ERROR - HTTP ${response.status}]:`, errorMessage);
            
            // Standardize the error format sent back to the frontend
            return res.status(response.status === 200 ? 400 : response.status).json({
                status: 'error',
                text: errorMessage
            });
        }

        res.json(data);
    } catch (error) {
        console.error('[PROXY EXCEPTION]:', error.message);
        res.status(500).json({ status: 'error', text: 'Internal server proxy error. Check logs.' });
    }
});

// Fallback to serve the single-page application for any other route
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Add global error handlers to ensure the Railway container doesn't unexpectedly crash 
// and stop the container due to an unhandled promise rejection.
process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection at:', promise, 'reason:', reason);
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