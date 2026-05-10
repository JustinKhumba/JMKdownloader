import os
import shutil
import tempfile
import urllib.parse
from io import BytesIO
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature
import yt_dlp

app = Flask(__name__)
# A secret key is required for Flask's flash messaging and token serialization
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_for_development_environment')

# Serializer for creating secure, temporary download tokens (expires in 1 hour)
serializer = URLSafeTimedSerializer(app.secret_key)

@app.after_request
def set_secure_headers(response):
    """Implement robust security headers to prevent common web vulnerabilities."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    # Restrict where resources can be loaded from; allow images from anywhere (HTTPS) due to dynamic IG CDNs
    response.headers['Content-Security-Policy'] = "default-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; img-src 'self' data: https:;"
    return response

def validate_instagram_url(url):
    """Strictly validate the URL to ensure it is a safe Instagram link to prevent SSRF."""
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        # Scheme must be explicitly HTTPS
        if parsed.scheme != 'https':
            return False
        # Domain must exactly match Instagram
        if parsed.netloc not in ['instagram.com', 'www.instagram.com']:
            return False
        # Path must start with allowed Instagram video routes
        valid_path_starts = ('/p/', '/reel/', '/reels/', '/tv/')
        if not parsed.path.startswith(valid_path_starts):
            return False
        return True
    except Exception:
        return False

def get_cookie_path():
    """Safely resolve the absolute path to the cookies file."""
    cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    return cookie_path if os.path.exists(cookie_path) else None

@app.route('/', methods=['GET'])
def index():
    """Render the main homepage with the download form."""
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    """Step 1: Extract video metadata (thumbnail, title) without downloading."""
    url = request.form.get('url', '').strip()
    
    if not validate_instagram_url(url):
        flash('Please provide a valid, secure Instagram URL (e.g., https://www.instagram.com/reel/...).', 'error')
        return redirect(url_for('index'))

    # Clean the URL to remove tracking parameters that cause issues
    if '?' in url:
        url = url.split('?')[0]
    # Normalize /reels/ to /reel/ as yt-dlp prefers the singular format
    url = url.replace('/reels/', '/reel/')

    # Configure yt-dlp options just to fetch metadata
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }

    cookie_path = get_cookie_path()
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        # Extract info without downloading the heavy video file yet
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            title = info_dict.get('title') or info_dict.get('description') or 'Instagram Video'
            if len(title) > 65:
                title = title[:62] + '...'
                
            # Safely grab the best thumbnail
            thumbnail = info_dict.get('thumbnail')
            if not thumbnail and info_dict.get('thumbnails'):
                thumbnail = info_dict['thumbnails'][-1].get('url')
                
            # Generate a secure, time-limited token for the actual download
            token = serializer.dumps(url)
            
            video_data = {
                'title': title,
                'thumbnail': thumbnail,
                'token': token
            }
            
            return render_template('index.html', video_data=video_data)
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if 'private video' in error_msg or 'login' in error_msg:
            flash('This video is private, restricted, or requires authentication.', 'error')
        else:
            flash('Unable to fetch video details. Ensure the URL is correct and public.', 'error')
        return redirect(url_for('index'))
        
    except Exception as e:
        flash('An unexpected error occurred while processing the video.', 'error')
        return redirect(url_for('index'))

@app.route('/download/<token>', methods=['GET'])
def download(token):
    """Step 2: Handle the actual video download using the validated token."""
    try:
        # Decode the token (max age: 1 hour)
        url = serializer.loads(token, max_age=3600)
    except BadSignature:
        flash('Your download link has expired or is invalid. Please start over.', 'error')
        return redirect(url_for('index'))

    temp_dir = tempfile.mkdtemp()
    
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'format': 'best',
        'quiet': False,
        'no_warnings': False,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }

    cookie_path = get_cookie_path()
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_title = info_dict.get('title', 'instagram_video')
            
            # Sanitize filename
            safe_title = "".join([c for c in video_title if c.isalnum() or c in ' -_']).strip()
            if not safe_title:
                safe_title = 'instagram_video'
                
            ext = info_dict.get('ext', 'mp4')
            
            files = os.listdir(temp_dir)
            if not files:
                raise Exception("Download completed but file could not be found.")
            
            file_path = os.path.join(temp_dir, files[0])
            
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            io_stream = BytesIO(file_data)
            io_stream.seek(0)
            
            shutil.rmtree(temp_dir)

            return send_file(
                io_stream,
                as_attachment=True,
                download_name=f"{safe_title[:50]}.{ext}",
                mimetype=f"video/{ext}"
            )
            
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        flash('Failed to download the video file. It may be restricted.', 'error')
        return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)