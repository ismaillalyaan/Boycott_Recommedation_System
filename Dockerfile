# Use a slim Python base image
FROM python:3.10-slim

# Install system dependencies for OpenCV and others
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx libglib2.0-0 wget unzip && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data needed by match.py
RUN python -m nltk.downloader wordnet

# Expose the port for Flask
EXPOSE 8000

# Start Flask app
CMD ["python", "backend/app.py"]
