# Use the official Python slim image as a base
FROM python:3.11-slim

# Set environment variables to prevent Python from writing .pyc files
# and to ensure stdout/stderr are flushed straight to the terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install FFmpeg (required by yt-dlp to merge best video and best audio streams)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the rest of the application source code (including api, services, utils, templates)
COPY . .

# Expose the port (Railway typically provides the PORT environment variable)
ENV PORT=8000
EXPOSE $PORT

# Run the FastAPI application using Uvicorn
# We use 'sh -c' to ensure the PORT environment variable is evaluated at runtime
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]