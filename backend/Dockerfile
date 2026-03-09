# ==========================================================================
# PostRabbit Backend — Dockerfile
#
# Builds a single image used for both the API server and the worker.
#
#   API  (default):  uvicorn app.main:app --host 0.0.0.0 --port 8000
#   Worker (override): python -m worker.worker
#
# On Railway, create two services from this image and override the start
# command for the worker service.
# ==========================================================================

# ------------------------------------------------------------------
# 1. Base image — Python 3.11 on Debian slim for a small footprint
# ------------------------------------------------------------------
FROM python:3.11-slim

# ------------------------------------------------------------------
# 2. Install minimal system-level dependencies
#    - ffmpeg : audio normalisation (normalize.py) and segment
#               extraction (transcribe.py)
#    - git    : required by torch.hub to download the Silero VAD model
#    - curl   : useful for health-check probes and debugging
#    - libgl1 : OpenGL library required by some audio/video
#               processing packages
# ------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        curl \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# 3. Set the working directory inside the container
# ------------------------------------------------------------------
WORKDIR /app

# ------------------------------------------------------------------
# 4. Install Python dependencies
#    Copy requirements.txt first so Docker can cache this layer when
#    only application code changes.
# ------------------------------------------------------------------
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Install lightweight CPU-only PyTorch to avoid the ~4 GB CUDA bundle
# that ships with the default torch wheel.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Ensure yt-dlp is at the latest version (it updates frequently to
# keep up with site changes).
RUN pip install --no-cache-dir yt-dlp

# ------------------------------------------------------------------
# 5. Copy the rest of the project into the image
# ------------------------------------------------------------------
COPY . .

# ------------------------------------------------------------------
# 6. Create the temp directory used by the audio pipeline
# ------------------------------------------------------------------
RUN mkdir -p /tmp/postrabbit

# ------------------------------------------------------------------
# 7. Expose the port that uvicorn will listen on
# ------------------------------------------------------------------
EXPOSE 8000

# ------------------------------------------------------------------
# 8. Default start command — FastAPI API server
#    Override this with "python -m worker.worker" for the worker service.
# ------------------------------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
