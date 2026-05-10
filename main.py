import os
import tempfile
from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
import yt_dlp

app = FastAPI(title="YouTube Downloader")

# Simple HTML Frontend
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Downloader</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            background-color: #f3f4f6; 
            margin: 0; 
        }
        .container { 
            background-color: white; 
            padding: 40px; 
            border-radius: 12px; 
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); 
            text-align: center; 
            width: 100%;
            max-width: 500px;
        }
        h2 { margin-top: 0; color: #111827; }
        p { color: #6b7280; margin-bottom: 24px; }
        input[type="url"] { 
            width: 90%; 
            padding: 12px; 
            margin-bottom: 20px; 
            border: 1px solid #d1d5db; 
            border-radius: 6px; 
            font-size: 16px;
            outline: none;
        }
        input[type="url"]:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2); }
        button { 
            padding: 12px 24px; 
            background-color: #ef4444; 
            color: white; 
            border: none; 
            border-radius: 6px; 
            font-size: 16px;
            font-weight: bold;
            cursor: pointer; 
            transition: background-color 0.2s;
            width: 95%;
        }
        button:hover { background-color: #dc2626; }
        button:disabled { background-color: #fca5a5; cursor: not-allowed; }
        .footer { margin-top: 20px; font-size: 12px; color: #9ca3af; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Video Downloader</h2>
        <p>Enter a YouTube URL to download the highest quality MP4.</p>
        
        <form id="downloadForm" action="/download" method="post">
            <input type="url" name="url" placeholder="https://www.youtube.com/watch?v=..." required>
            <br>
            <button type="submit" id="downloadBtn" onclick="showLoading()">Download MP4</button>
        </form>
        <div class="footer">Processing might take a few moments.</div>
    </div>

    <script>
        function showLoading() {
            const form = document.getElementById('downloadForm');
            const btn = document.getElementById('downloadBtn');
            // Basic validation check before changing button state
            if(form.checkValidity()) {
                setTimeout(() => {
                    btn.innerText = 'Processing & Merging... Please wait';
                    btn.disabled = true;
                }, 50);
            }
        }
    </script>
</body>
</html>
"""

@app.get("/")
def read_root():
    """Serves the simple HTML frontend."""
    return HTMLResponse(content=HTML_CONTENT)

def cleanup_file(filepath: str):
    """Background task to remove the file after it has been served."""
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"Error cleaning up file {filepath}: {e}")

@app.post("/download")
def download_video(background_tasks: BackgroundTasks, url: str = Form(...)):
    """Processes the URL, downloads the video, and returns it as a file response."""
    temp_dir = tempfile.gettempdir()
    
    # yt-dlp configuration to extract the best video and audio and merge into MP4
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        # restrictfilenames ensures the filename only has ASCII chars, preventing HTTP header errors
        'restrictfilenames': True, 
        'noplaylist': True,
        'quiet': True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info and download
            info_dict = ydl.extract_info(url, download=True)
            
            # Prepare the expected output filename
            filename = ydl.prepare_filename(info_dict)
            base, _ = os.path.splitext(filename)
            final_filename = base + ".mp4"
            
            # Sometimes yt-dlp uses a slightly different name or the merge extension fallback happens
            if not os.path.exists(final_filename) and os.path.exists(filename):
                final_filename = filename
                
        # Schedule the cleanup task to run AFTER the FileResponse completes
        background_tasks.add_task(cleanup_file, final_filename)
        
        # Stream the file directly to the user's browser as an attachment
        return FileResponse(
            path=final_filename, 
            filename=os.path.basename(final_filename),
            media_type='video/mp4',
            headers={"Content-Disposition": f"attachment; filename={os.path.basename(final_filename)}"}
        )
        
    except Exception as e:
        error_html = f"""
        <div style="font-family: sans-serif; text-align: center; margin-top: 50px;">
            <h3 style="color: red;">An error occurred while processing the video.</h3>
            <p>{str(e)}</p>
            <a href="/" style="color: blue; text-decoration: none;">&larr; Go back</a>
        </div>
        """
        return HTMLResponse(content=error_html, status_code=400)