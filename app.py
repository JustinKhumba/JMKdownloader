import os
import re
import shutil
import tempfile
import urllib.parse
import random
from io import BytesIO
from flask import Flask, render_template, request, send_file, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from itsdangerous import URLSafeTimedSerializer, BadSignature
import yt_dlp

app = Flask(__name__)

# SECURITY: Limit incoming request payload size to 1MB to prevent DoS attacks
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024

# SECURITY: Strict CORS configuration specifying exactly which domains can access the API
ALLOWED_ORIGINS = [
    "https://check-love-tools.blogspot.com",
    "http://check-love-tools.blogspot.com",
    "https://www.check-love-tools.blogspot.com",
    "https://jmkdownloader.up.railway.app",
    "http://localhost:5000",
    "http://127.0.0.1:5000"
]

# Enable CORS restricted to the allowed origins
CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS}})

# SECURITY: Initialize Rate Limiter to prevent spam and abuse
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://" 
)

app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_for_development_environment')
serializer = URLSafeTimedSerializer(app.secret_key)

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        'success': False, 
        'message': f"Too many requests. Please slow down. {e.description}"
    }), 429

@app.errorhandler(413)
def payload_too_large(e):
    return jsonify({
        'success': False, 
        'message': "Request payload is too large. Maximum size is 1MB."
    }), 413

@app.after_request
def set_secure_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    csp = (
        "default-src 'self' *; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https: blob: *; "
        "frame-ancestors 'self' https://*.blogspot.com http://*.blogspot.com https://check-love-tools.blogspot.com https://jmkdownloader.up.railway.app/;"
    )
    response.headers['Content-Security-Policy'] = csp
    return response

def validate_instagram_url(url):
    if not url or not isinstance(url, str):
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

def validate_youtube_url(url):
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        if parsed.netloc not in ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com']:
            return False
        return True
    except Exception:
        return False

def get_cookie_path(platform):
    """
    Dynamically scans the respective platform's cookie directory
    and returns a random cookie file path for rotation.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cookie_dir = os.path.join(base_dir, f"{platform} cookies")
    
    if not os.path.exists(cookie_dir):
        return None
        
    available_cookies = []
    for f in os.listdir(cookie_dir):
        full_path = os.path.join(cookie_dir, f)
        if os.path.isfile(full_path) and f.endswith('.txt'):
            available_cookies.append(full_path)
            
    if not available_cookies:
        return None
        
    return random.choice(available_cookies)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/checklovetools.png', methods=['GET'])
def serve_logo():
    return send_from_directory('templates', 'checklovetools.png')

# ==========================================
# INSTAGRAM ROUTES
# ==========================================

@app.route('/process/instagram', methods=['POST', 'OPTIONS'])
@limiter.limit("10 per minute")
def process_instagram():
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    data = request.get_json(silent=True)
    url = data.get('url', '').strip() if data else request.form.get('url', '').strip()
    
    if not validate_instagram_url(url):
        return jsonify({'success': False, 'message': 'Please provide a valid Instagram URL.'}), 400

    if '?' in url:
        url = url.split('?')[0]
    url = url.replace('/reels/', '/reel/')

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }

    cookie_path = get_cookie_path('instagram')
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            title = info_dict.get('title') or info_dict.get('description') or 'Instagram Video'
            if len(title) > 65:
                title = title[:62] + '...'
                
            thumbnail = info_dict.get('thumbnail')
            if not thumbnail and info_dict.get('thumbnails'):
                thumbnail = info_dict['thumbnails'][-1].get('url')
                
            size_bytes = info_dict.get('filesize') or info_dict.get('filesize_approx') or 0
            filesize_formatted = f"{round(size_bytes / (1024 * 1024), 2)} MB" if size_bytes > 0 else "Size Unknown"
            
            token = serializer.dumps(url)
            
            return jsonify({'success': True, 'data': {
                'title': title,
                'thumbnail': thumbnail,
                'filesize': filesize_formatted,
                'token': token
            }})
            
    except Exception as e:
        error_msg = str(e).lower()
        print(f"[INSTAGRAM FETCH ERROR]: {error_msg}")
        if 'private video' in error_msg or 'login' in error_msg:
            return jsonify({'success': False, 'message': 'This video is private or requires authentication.'}), 403
        return jsonify({'success': False, 'message': f'Unable to fetch video details: {str(e)}'}), 400

@app.route('/download/instagram/<token>', methods=['GET', 'OPTIONS'])
@limiter.limit("5 per minute")
def download_instagram(token):
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        url = serializer.loads(token, max_age=3600)
    except BadSignature:
        return jsonify({'success': False, 'message': 'Your download link has expired.'}), 400

    temp_dir = tempfile.mkdtemp()
    
    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    }

    cookie_path = get_cookie_path('instagram')
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
            raw_title = info_dict.get('title') or info_dict.get('description') or 'InstaGrabber_Video'
            safe_title = re.sub(r'[^\w\s-]', '', raw_title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title) or 'InstaGrabber_Video'
                
            files = os.listdir(temp_dir)
            if not files:
                raise Exception("Download completed but file could not be found.")
            
            file_path = os.path.join(temp_dir, files[0])
            ext = file_path.split('.')[-1]
            
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
        print(f"[INSTAGRAM DOWNLOAD ERROR]: {str(e)}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return jsonify({'success': False, 'message': f'Failed to download the video file: {str(e)}'}), 500


# ==========================================
# YOUTUBE ROUTES
# ==========================================

@app.route('/process/youtube', methods=['POST', 'OPTIONS'])
@limiter.limit("10 per minute")
def process_youtube():
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    data = request.get_json(silent=True)
    url = data.get('url', '').strip() if data else request.form.get('url', '').strip()
    
    if not validate_youtube_url(url):
        return jsonify({'success': False, 'message': 'Please provide a valid YouTube URL.'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        'extractor_args': {
            'youtube': {
                # This bypasses the "No video formats found!" error by using the android/web client combination
                'player_client': ['android', 'web']
            }
        }
    }

    cookie_path = get_cookie_path('youtube')
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            title = info_dict.get('title', 'YouTube Video')
            if len(title) > 65:
                title = title[:62] + '...'
                
            thumbnail = info_dict.get('thumbnail')
            if not thumbnail and info_dict.get('thumbnails'):
                thumbnail = info_dict['thumbnails'][-1].get('url')

            # Extract available video qualities
            available_formats = []
            seen_heights = set()
            for f in reversed(info_dict.get('formats', [])):
                h = f.get('height')
                vcodec = f.get('vcodec')
                if h and vcodec and vcodec != 'none':
                    if h not in seen_heights:
                        seen_heights.add(h)
                        size = f.get('filesize') or f.get('filesize_approx') or 0
                        size_str = f"{round(size / (1024 * 1024), 2)} MB" if size > 0 else "Unknown Size"
                        available_formats.append({
                            'format_id': f.get('format_id'),
                            'resolution': f"{h}p",
                            'height': h,
                            'size': size_str,
                            'ext': f.get('ext', 'mp4')
                        })
            
            available_formats.sort(key=lambda x: x['height'], reverse=True)
            if not available_formats:
                available_formats = [{'format_id': 'best', 'resolution': 'Best Available', 'height': 0, 'size': 'Unknown Size', 'ext': 'mp4'}]
            
            token = serializer.dumps(url)
            
            return jsonify({'success': True, 'data': {
                'title': title,
                'thumbnail': thumbnail,
                'formats': available_formats,
                'token': token
            }})
            
    except Exception as e:
        print(f"[YOUTUBE FETCH ERROR]: {str(e)}")
        return jsonify({'success': False, 'message': f'Unable to fetch YouTube video details: {str(e)}'}), 400

@app.route('/download/youtube/<token>', methods=['GET', 'OPTIONS'])
@limiter.limit("5 per minute")
def download_youtube(token):
    if request.method == 'OPTIONS':
        return jsonify({'success': True}), 200

    try:
        url = serializer.loads(token, max_age=3600)
    except BadSignature:
        return jsonify({'success': False, 'message': 'Your download link has expired.'}), 400

    format_id = request.args.get('format_id', 'best')
    temp_dir = tempfile.mkdtemp()
    
    # Download requested video format and combine with best audio if needed
    dl_format = f"{format_id}+bestaudio/best" if format_id != 'best' else 'best'

    ydl_opts = {
        'outtmpl': os.path.join(temp_dir, 'video.%(ext)s'),
        'format': dl_format,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        }
    }

    cookie_path = get_cookie_path('youtube')
    if cookie_path:
        ydl_opts['cookiefile'] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
            raw_title = info_dict.get('title', 'YouTube_Video')
            safe_title = re.sub(r'[^\w\s-]', '', raw_title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title) or 'YouTube_Video'
                
            files = os.listdir(temp_dir)
            if not files:
                raise Exception("Download completed but file could not be found.")
            
            file_path = os.path.join(temp_dir, files[0])
            ext = file_path.split('.')[-1]
            
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
        print(f"[YOUTUBE DOWNLOAD ERROR]: {str(e)}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return jsonify({'success': False, 'message': f'Failed to download the video file: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)