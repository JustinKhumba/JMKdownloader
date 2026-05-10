import os
import yt_dlp

def get_video_metadata(url: str) -> dict:
    """
    Extracts video metadata and available qualities using yt-dlp without downloading.
    """
    ydl_opts = {
        'quiet': True, 
        'noplaylist': True
    }
    
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
                
                # Estimate file size
                filesize = f.get('filesize') or f.get('filesize_approx')
                size_str = ""
                if filesize:
                    size_mb = filesize / (1024 * 1024)
                    if size_mb > 1000:
                        size_str = f"~{size_mb/1024:.1f} GB"
                    else:
                        size_str = f"~{size_mb:.1f} MB"
                else:
                    size_str = "Size Unknown"
                    
                video_formats.append({
                    "format_id": f.get('format_id'),
                    "resolution": f"{height}p",
                    "fps": f.get('fps'),
                    "ext": f.get('ext'),
                    "size": size_str
                })
                
        # Fallback if no specific resolutions were extracted cleanly
        if not video_formats:
            video_formats.append({
                "format_id": "best",
                "resolution": "Best Quality",
                "fps": None,
                "ext": "mp4",
                "size": "Auto"
            })

        # Limit to top 6 qualities to keep the mobile UI clean and uncluttered
        return {
            "title": info.get('title', 'Unknown Title'),
            "thumbnail": info.get('thumbnail', ''),
            "formats": video_formats[:6] 
        }

def download_video_file(url: str, format_id: str, temp_dir: str) -> str:
    """
    Downloads the specified format, merges audio, and returns the final file path.
    """
    # Construct the format string based on user selection.
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

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Download and merge
        info_dict = ydl.extract_info(url, download=True)
        
        # Identify output file
        filename = ydl.prepare_filename(info_dict)
        base, _ = os.path.splitext(filename)
        final_filename = base + ".mp4"
        
        if not os.path.exists(final_filename) and os.path.exists(filename):
            final_filename = filename
            
        return final_filename