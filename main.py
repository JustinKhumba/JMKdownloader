import os
import tempfile
from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import yt_dlp

app = FastAPI(title="YouTube Downloader")

# Modern, Mobile-First HTML Frontend
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <!-- Prevents iOS zoom on input focus while remaining mobile-responsive -->
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0">
    <title>YouTube Downloader</title>
    <style>
        :root { 
            --primary: #ef4444; 
            --primary-hover: #dc2626;
            --bg: #f3f4f6; 
            --card: #ffffff; 
            --text: #1f2937; 
            --text-muted: #6b7280;
            --border: #e5e7eb;
        }
        body { 
            margin: 0; 
            background-color: var(--bg); 
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            min-height: 100vh; 
            padding: 16px; 
            color: var(--text); 
            box-sizing: border-box;
        }
        .card { 
            background: var(--card); 
            width: 100%; 
            max-width: 420px; 
            border-radius: 16px; 
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); 
            padding: 24px; 
            box-sizing: border-box; 
        }
        .header { text-align: center; margin-bottom: 24px; }
        .header h1 { font-size: 20px; font-weight: 700; margin: 0 0 6px 0; color: #111827; }
        .header p { font-size: 14px; color: var(--text-muted); margin: 0; }
        
        .input-group { margin-bottom: 16px; }
        input[type="url"] { 
            width: 100%; 
            padding: 14px 16px; 
            font-size: 15px; 
            border: 1px solid var(--border); 
            border-radius: 10px; 
            outline: none; 
            transition: border-color 0.2s, box-shadow 0.2s; 
            box-sizing: border-box; 
            background: #f9fafb;
        }
        input[type="url"]:focus { 
            border-color: var(--primary); 
            background: #ffffff;
            box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
        }
        
        button.btn-primary { 
            width: 100%; 
            background: var(--primary); 
            color: white; 
            border: none; 
            padding: 14px; 
            font-size: 16px; 
            font-weight: 600; 
            border-radius: 10px; 
            cursor: pointer; 
            transition: background 0.2s; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            gap: 10px; 
        }
        button.btn-primary:active { background: var(--primary-hover); transform: scale(0.98); }
        button:disabled { opacity: 0.7; cursor: not-allowed; }
        
        /* Result State Styles */
        #result-section { display: none; }
        .thumbnail-wrapper {
            position: relative;
            width: 100%;
            padding-top: 56.25%; /* 16:9 Aspect Ratio */
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 16px;
            background: #e5e7eb;
        }
        .thumbnail { 
            position: absolute;
            top: 0;
            left: 0;
            width: 100%; 
            height: 100%;
            object-fit: cover; 
        }
        .video-title { 
            font-size: 16px; 
            font-weight: 600; 
            margin: 0 0 16px 0; 
            line-height: 1.4;
            display: -webkit-box; 
            -webkit-line-clamp: 2; 
            -webkit-box-orient: vertical; 
            overflow: hidden; 
        }
        
        .formats-label { font-size: 13px; font-weight: 600; color: var(--text-muted); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.5px; }
        .formats-grid { 
            display: grid; 
            grid-template-columns: repeat(2, 1fr); 
            gap: 10px; 
            margin-bottom: 16px; 
        }
        .format-btn { 
            background: #f9fafb; 
            border: 1px solid var(--border); 
            padding: 12px 8px; 
            border-radius: 10px; 
            text-align: center; 
            cursor: pointer; 
            transition: all 0.2s; 
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
        }
        .format-btn:hover, .format-btn:active { 
            border-color: var(--primary); 
            background: #fef2f2; 
        }
        .format-btn .res { font-weight: 600; font-size: 15px; color: #111827; }
        .format-btn .ext { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
        
        .back-link { 
            text-align: center; 
            display: block; 
            font-size: 14px; 
            color: var(--primary); 
            text-decoration: none; 
            font-weight: 500;
        }
        
        /* Spinners & Overlays */
        .spinner { 
            border: 2px solid rgba(255,255,255,0.3); 
            border-radius: 50%; 
            border-top: 2px solid white; 
            width: 18px; 
            height: 18px; 
            animation: spin 1s linear infinite; 
            display: none; 
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        
        #overlay { 
            position: fixed; top: 0; left: 0; right: 0; bottom: 0; 
            background: rgba(255,255,255,0.95); 
            z-index: 100; 
            display: none; 
            flex-direction: column; 
            justify-content: center; 
            align-items: center; 
            text-align: center; 
            padding: 32px; 
        }
        #overlay .spinner-dark { 
            border: 3px solid var(--border); 
            border-top: 3px solid var(--primary); 
            border-radius: 50%; 
            width: 48px; 
            height: 48px; 
            animation: spin 1s linear infinite; 
            margin-bottom: 20px; 
        }
        #overlay h2 { font-size: 20px; margin: 0 0 8px 0; color: #111827; }
        #overlay p { font-size: 15px; color: var(--text-muted); line-height: 1.5; }
    </style>
</head>
<body>
    <div class="card">
        <!-- STEP 1: Enter URL -->
        <div id="input-section">
            <div class="header">
                <h1>Video Downloader</h1>
                <p>Paste a link to fetch available qualities.</p>
            </div>
            
            <form id="infoForm" onsubmit="fetchInfo(event)">
                <div class="input-group">
                    <input type="url" id="url-input" placeholder="https://www.youtube.com/watch?v=..." required>
                </div>
                <button type="submit" id="fetch-btn" class="btn-primary">
                    <span id="btn-spinner" class="spinner"></span>
                    <span id="btn-text">Get Download Links</span>
                </button>
            </form>
        </div>

        <!-- STEP 2: Select Quality -->
        <div id="result-section">
            <div class="thumbnail-wrapper">
                <img id="thumbnail" class="thumbnail" src="" alt="Video Thumbnail">
            </div>
            <h2 id="video-title" class="video-title"></h2>
            
            <div class="formats-label">Available Qualities</div>
            <div id="formats-grid" class="formats-grid">
                <!-- Quality buttons injected via JS -->
            </div>
            
            <a href="#" class="back-link" onclick="resetUI(event)">Paste a different link</a>
        </div>
    </div>

    <!-- Hidden form for native browser downloading -->
    <form id="hidden-dl-form" action="/download" method="post" style="display: none;">
        <input type="hidden" name="url" id="dl-url">
        <input type="hidden" name="format_id" id="dl-format">
    </form>

    <!-- Fullscreen Processing Overlay -->
    <div id="overlay">
        <div id="overlay-spinner" class="spinner-dark"></div>
        <h2 id="overlay-title">Processing Video...</h2>
        <p id="overlay-status">Downloading and merging the best audio with your selected video quality.<br><br><b>Please keep this page open.</b> Your browser will automatically save the file when it is ready.</p>
    </div>

    <script>
        let currentUrl = '';

        async function fetchInfo(event) {
            event.preventDefault();
            const urlInput = document.getElementById('url-input');
            const url = urlInput.value.trim();
            if (!url) return;

            const btn = document.getElementById('fetch-btn');
            const btnText = document.getElementById('btn-text');
            const spinner = document.getElementById('btn-spinner');

            // Set loading UI
            btn.disabled = true;
            btnText.innerText = 'Fetching...';
            spinner.style.display = 'block';

            try {
                const formData = new FormData();
                formData.append('url', url);

                const response = await fetch('/info', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.detail || 'Failed to fetch video info. Please check the URL.');
                }

                const data = await response.json();
                currentUrl = url;
                renderResult(data);

            } catch (error) {
                alert(error.message);
            } finally {
                // Reset loading UI
                btn.disabled = false;
                btnText.innerText = 'Get Download Links';
                spinner.style.display = 'none';
            }
        }

        function renderResult(data) {
            document.getElementById('input-section').style.display = 'none';
            document.getElementById('result-section').style.display = 'block';
            
            document.getElementById('thumbnail').src = data.thumbnail;
            document.getElementById('video-title').innerText = data.title;

            const grid = document.getElementById('formats-grid');
            grid.innerHTML = '';

            data.formats.forEach(f => {
                const btn = document.createElement('div');
                btn.className = 'format-btn';
                btn.onclick = () => startDownload(f.format_id);
                
                const fpsText = f.fps ? `<span style="margin-left: 2px;">${f.fps}fps</span>` : '';
                btn.innerHTML = `
                    <div class="res">${f.resolution}</div>
                    <div class="ext">MP4 ${fpsText}</div>
                `;
                grid.appendChild(btn);
            });
        }

        function startDownload(formatId) {
            // Show processing overlay
            document.getElementById('overlay').style.display = 'flex';
            document.getElementById('overlay-title').innerText = 'Processing Video...';
            document.getElementById('overlay-spinner').style.display = 'block';
            document.getElementById('overlay-status').innerHTML = 'Downloading and merging the best audio with your selected video quality.<br><br><b>Please keep this page open.</b> Your browser will automatically save the file when it is ready.';
            
            // Populate hidden form and submit to trigger standard browser file download
            document.getElementById('dl-url').value = currentUrl;
            document.getElementById('dl-format').value = formatId;
            document.getElementById('hidden-dl-form').submit();

            // Provide a way to interact after a delay (since we don't know exactly when download finishes)
            setTimeout(() => {
                 document.getElementById('overlay-title').innerText = 'Download Started!';
                 document.getElementById('overlay-spinner').style.display = 'none';
                 document.getElementById('overlay-status').innerHTML = 'If your browser hasn\\'t started the download yet, it should momentarily.<br><br><a href="#" onclick="location.reload()" style="color:var(--primary); font-weight: 600; text-decoration: none;">&larr; Download another video</a>';
            }, 8000); // 8 seconds delay assumption for UI change
        }

        function resetUI(event) {
            event.preventDefault();
            document.getElementById('input-section').style.display = 'block';
            document.getElementById('result-section').style.display = 'none';
            document.getElementById('url-input').value = '';
            document.getElementById('url-input').focus();
        }
    </script>
</body>
</html>
"""

@app.get("/")
def read_root():
    """Serves the frontend interface."""
    return HTMLResponse(content=HTML_CONTENT)

@app.post("/info")
def get_video_info(url: str = Form(...)):
    """Fetches video metadata and available qualities without downloading."""
    ydl_opts = {
        'quiet': True, 
        'noplaylist': True
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info without downloading
            info = ydl.extract_info(url, download=False)
            
            formats = info.get('formats', [])
            video_formats = []
            seen_heights = set()
            
            # Filter for formats containing video data, sort by resolution (height) highest to lowest
            sorted_formats = sorted(
                [f for f in formats if f.get('vcodec') != 'none' and f.get('height')],
                key=lambda x: x.get('height', 0), 
                reverse=True
            )
            
            # Extract unique resolutions for the UI
            for f in sorted_formats:
                height = f.get('height')
                if height and height not in seen_heights:
                    seen_heights.add(height)
                    video_formats.append({
                        "format_id": f.get('format_id'),
                        "resolution": f"{height}p",
                        "fps": f.get('fps'),
                        "ext": f.get('ext')
                    })
                    
            # Fallback if no specific resolutions were extracted cleanly
            if not video_formats:
                video_formats.append({
                    "format_id": "best",
                    "resolution": "Best Quality",
                    "fps": None,
                    "ext": "mp4"
                })

            # Limit to top 6 qualities to keep the mobile UI clean and uncluttered
            return JSONResponse({
                "title": info.get('title', 'Unknown Title'),
                "thumbnail": info.get('thumbnail', ''),
                "formats": video_formats[:6] 
            })
            
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})

def cleanup_file(filepath: str):
    """Background task to remove the file after it has been served."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"Error cleaning up file {filepath}: {e}")

@app.post("/download")
def download_video(background_tasks: BackgroundTasks, url: str = Form(...), format_id: str = Form(...)):
    """Downloads the selected format, merges audio, and streams the file to the user."""
    temp_dir = tempfile.gettempdir()
    
    # Construct the format string based on user selection.
    # We ask yt-dlp to download the specific video format + the best audio format, and fallback to "best" if needed.
    if format_id == "best":
        target_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    else:
        target_format = f"{format_id}+bestaudio[ext=m4a]/bestaudio/best"
    
    ydl_opts = {
        'format': target_format,
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'restrictfilenames': True, 
        'noplaylist': True,
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Download and merge
            info_dict = ydl.extract_info(url, download=True)
            
            # Identify output file
            filename = ydl.prepare_filename(info_dict)
            base, _ = os.path.splitext(filename)
            final_filename = base + ".mp4"
            
            if not os.path.exists(final_filename) and os.path.exists(filename):
                final_filename = filename
                
        # Schedule cleanup
        background_tasks.add_task(cleanup_file, final_filename)
        
        # Return as attachment
        return FileResponse(
            path=final_filename, 
            filename=os.path.basename(final_filename),
            media_type='video/mp4',
            headers={"Content-Disposition": f"attachment; filename={os.path.basename(final_filename)}"}
        )
        
    except Exception as e:
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: system-ui, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f3f4f6; padding: 20px; text-align: center; }}
                .card {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }}
                h3 {{ color: #ef4444; margin-top: 0; }}
                p {{ color: #4b5563; font-size: 14px; word-break: break-word; }}
                a {{ display: inline-block; margin-top: 20px; padding: 10px 20px; background: #ef4444; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h3>Download Failed</h3>
                <p>{str(e)}</p>
                <a href="/">&larr; Try Again</a>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=400)