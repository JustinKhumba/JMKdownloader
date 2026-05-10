import os
import shutil
import tempfile
from io import BytesIO
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import yt_dlp

app = Flask(__name__)
# A secret key is required for Flask's flash messaging to work
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_for_development_environment')

@app.route('/')
def index():
    """Render the main homepage with the download form."""
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    """Handle the video download process."""
    url = request.form.get('url')
    
    # Basic URL validation
    if not url or 'instagram.com' not in url:
        flash('Please provide a valid Instagram URL.', 'error')
        return redirect(url_for('index'))

    # Create a temporary directory to store the video before sending
    temp_dir = tempfile.mkdtemp()
    
    # Configure yt-dlp options
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            # Adding a standard User-Agent helps avoid immediate blocks from the platform
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }

    try:
        # Extract and download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_title = info_dict.get('title', 'instagram_video')
            # Sanitize the title to prevent header issues when serving the file
            safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            if not safe_title:
                safe_title = 'instagram_video'
                
            ext = info_dict.get('ext', 'mp4')
            
            # Find the downloaded file in our temporary directory
            files = os.listdir(temp_dir)
            if not files:
                raise Exception("Download completed but file could not be found.")
            
            file_path = os.path.join(temp_dir, files[0])
            
            # Read the file into memory (BytesIO) so we can clean up the temp directory
            # immediately before returning the response. This is safe for typical IG videos.
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            io_stream = BytesIO(file_data)
            io_stream.seek(0)
            
            # Clean up the temporary directory to save disk space on Railway
            shutil.rmtree(temp_dir)

            # Serve the file directly to the user's browser
            return send_file(
                io_stream,
                as_attachment=True,
                download_name=f"{safe_title}.{ext}",
                mimetype=f"video/{ext}"
            )
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        # Clean up directory on error
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            
        # Parse common yt-dlp errors to provide user-friendly feedback
        if 'private video' in error_msg or 'requested format not available' in error_msg or 'video unavailable' in error_msg or 'login' in error_msg:
            flash('This video is private, restricted, or the URL is invalid. Public videos only.', 'error')
        else:
            flash('Unable to download this video. Please check the URL and try again.', 'error')
        return redirect(url_for('index'))
        
    except Exception as e:
        # Clean up directory on unexpected error
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        flash('An unexpected processing error occurred. Please try again later.', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    # Use Railway's provided PORT environment variable, fallback to 5000 for local dev
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)