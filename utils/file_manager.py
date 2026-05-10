import os

def cleanup_file(filepath: str):
    """
    Background task to safely remove the file after it has been served.
    Prevents the server from running out of disk space over time.
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"Error cleaning up file {filepath}: {e}")