import os
import tempfile
from fastapi import APIRouter, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

# Import separated logic
from services.downloader import get_video_metadata, download_video_file
from utils.file_manager import cleanup_file

router = APIRouter()

@router.get("/")
def read_root():
    """Serves the frontend interface."""
    # Robustly find the templates directory relative to this file
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(base_dir, "templates", "index.html")
    return FileResponse(template_path)

@router.post("/info")
def get_video_info(url: str = Form(...)):
    """Fetches video metadata and available qualities without downloading."""
    try:
        data = get_video_metadata(url)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse(status_code=400, content={"detail": str(e)})

@router.post("/download")
def download_video(background_tasks: BackgroundTasks, url: str = Form(...), format_id: str = Form(...)):
    """Downloads the selected format, merges audio, and streams the file to the user."""
    temp_dir = tempfile.gettempdir()

    try:
        # Leverage our abstracted service
        final_filename = download_video_file(url, format_id, temp_dir)
            
        # Schedule cleanup to free storage later
        background_tasks.add_task(cleanup_file, final_filename)
        
        # Return as attachment
        return FileResponse(
            path=final_filename, 
            filename=os.path.basename(final_filename),
            media_type='video/mp4',
            headers={"Content-Disposition": f"attachment; filename={os.path.basename(final_filename)}"}
        )
        
    except Exception as e:
        # Fallback error page matching the UI style
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