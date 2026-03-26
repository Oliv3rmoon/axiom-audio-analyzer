FROM python:3.10-slim

WORKDIR /

# Install system deps (ffmpeg for audio conversion, essentia deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libfftw3-dev \
    libyaml-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir \
    runpod \
    essentia==2.1b6.dev1110 \
    numpy

# Copy handler
COPY handler.py /

CMD ["python3", "-u", "handler.py"]
