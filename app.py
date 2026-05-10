import os
import re
import shutil
import tempfile
import urllib.parse
from io import BytesIO
from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from itsdangerous import URLSafeTimedSerializer, BadSignature
import yt_dlp

app = Flask(__name__)
# Enable CORS for all routes and allow all origins
CORS(app, resources={r"/*": {"origins": "*"}})

# A secret key is required for token serialization
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_for_development_environment')

# Serializer for creating secure, temporary download tokens (expires in 1 hour)
serializer = URLSafeTimedSerializer(app.secret_key)

@app.after_request
def set_secure_headers(response):
    """Implement robust security headers and explicit CORS to prevent blocking."""
    # Force explicit CORS headers on every response to ensure the browser never blocks it
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept'
    
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Strict CSP allowing framing only from approved ancestors and restricting resources
    csp = (
        "default-src 'self' *; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https: blob: *; "
        "frame-ancestors 'self' https://*.blogspot.com http://*.blogspot.com https://jmkdownloader.up.railway.app/;"
    )
    response.headers['Content-Security-Policy'] = csp
    return response

def validate_instagram_url(url):
    """Strictly validate the URL to ensure it is a safe Instagram link to prevent SSRF."""
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https':
            return False
        if parsed.netloc not in ['instagram.com', 'www.instagram.com']:
            return False
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
    """Render the main SPA homepage."""
    return render_template('index.html')

@app.route('/checklovetools.png', methods=['GET'])
def serve_logo():
    """Serve the copyright logo directly from the templates directory."""
    return send_from_directory('templates', 'checklovetools.png')

@app.route('/process', methods=['POST', 'OPTIONS'])
def process():
    """Step 1: Extract video metadata (thumbnail, title, size) without downloading."""
    # Explicitly handle CORS preflight OPTIONS requests
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    # Parse basic JSON payload from the frontend
    if request.is_json:
        data = request.get_json()
        url = data.get('url', '').strip()
    else:
        # Fallback for standard form submissions
        url = request.form.get('url', '').strip()
    
    if not validate_instagram_url(url):
        return jsonify({'success': False, 'message': 'Please provide a valid, secure Instagram URL (e.g., https://www.instagram.com/reel/...).'})

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
                
            # Extract approximate filesize using yt-dlp metadata
            size_bytes = info_dict.get('filesize') or info_dict.get('filesize_approx') or 0
            if size_bytes > 0:
                size_mb = round(size_bytes / (1024 * 1024), 2)
                filesize_formatted = f"{size_mb} MB"
            else:
                filesize_formatted = "Size Unknown"
                
            # Generate a secure, time-limited token for the actual download
            token = serializer.dumps(url)
            
            video_data = {
                'title': title,
                'thumbnail': thumbnail,
                'filesize': filesize_formatted,
                'token': token
            }
            
            return jsonify({'success': True, 'data': video_data})
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if 'private video' in error_msg or 'login' in error_msg:
            return jsonify({'success': False, 'message': 'This video is private, restricted, or requires authentication.'})
        else:
            return jsonify({'success': False, 'message': 'Unable to fetch video details. Ensure the URL is correct and public.'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'An unexpected error occurred while processing the video.'})

@app.route('/download/<token>', methods=['GET', 'OPTIONS'])
def download(token):
    """Step 2: Handle the actual video download using the validated token."""
    # Explicitly handle CORS preflight OPTIONS requests
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        # Decode the token (max age: 1 hour)
        url = serializer.loads(token, max_age=3600)
    except BadSignature:
        return jsonify({'success': False, 'message': 'Your download link has expired or is invalid. Please start over.'}), 400

    temp_dir = tempfile.mkdtemp()
    
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
        'format': 'best',
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
            # Explicitly sanitize and map post title/description to filename
            raw_title = info_dict.get('title') or info_dict.get('description') or 'InstaGrabber_Video'
            safe_title = re.sub(r'[^\w\s-]', '', raw_title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            
            if not safe_title:
                safe_title = 'InstaGrabber_Video'
                
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
                download_name=f"{safe_title[:60]}.{ext}",
                mimetype=f"video/{ext}"
            )
            
    except Exception as e:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return jsonify({'success': False, 'message': 'Failed to download the video file. It may be restricted.'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)