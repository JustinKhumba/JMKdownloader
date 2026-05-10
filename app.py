import os
import uuid
import tempfile
import asyncio
from fastapi import FastAPI, BackgroundTasks, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
import yt_dlp

app = FastAPI()

@app.get("/")
async def serve_frontend():
    """Serves the single-page HTML frontend."""
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read())

def remove_file(path: str):
    """Background task to delete the file after it's sent to the user."""
    try:
        if os.path.exists(path):
            os.remove(path)
            print(f"Cleaned up temporary file: {path}")
    except Exception as e:
        print(f"Error removing file {path}: {e}")

def download_with_ytdlp(url: str, base_path: str):
    """
    Executes yt-dlp synchronously. 
    We use 'best' format to get a pre-merged video/audio file,
    which avoids the need for FFmpeg to be installed on the Railway container.
    """
    ydl_opts = {
        'outtmpl': f"{base_path}.%(ext)s",
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        ext = info.get('ext', 'mp4')
        title = info.get('title', 'downloaded_video')
        
        # Sanitize the title to prevent header issues with FileResponse
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
        final_path = f"{base_path}.{ext}"
        
        return final_path, f"{safe_title}.{ext}"

@app.post("/api/download")
async def download_endpoint(background_tasks: BackgroundTasks, url: str = Form(...)):
    """API Endpoint to trigger the download process."""
    if not url:
        return JSONResponse(status_code=400, content={"error": "URL is required."})

    # Prepare temporary file path within the ephemeral disk (/tmp)
    temp_dir = tempfile.gettempdir()
    file_id = str(uuid.uuid4())
    base_path = os.path.join(temp_dir, file_id)

    # Run the blocking yt-dlp operation in a separate thread
    loop = asyncio.get_event_loop()
    try:
        final_path, filename = await loop.run_in_executor(None, download_with_ytdlp, url, base_path)
    except yt_dlp.utils.DownloadError as e:
        # Handle invalid URLs, private videos, and region blocks gracefully
        return JSONResponse(status_code=400, content={"error": f"Download failed. The video might be private, restricted, or the URL is invalid."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"An unexpected error occurred: {str(e)}"})

    if not os.path.exists(final_path):
        return JSONResponse(status_code=500, content={"error": "File extraction failed."})

    # Schedule the deletion of the video immediately after the response finishes sending
    background_tasks.add_task(remove_file, final_path)

    return FileResponse(
        path=final_path, 
        filename=filename, 
        media_type='application/octet-stream'
    )