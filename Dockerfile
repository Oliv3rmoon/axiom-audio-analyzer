FROM python:3.10-slim

WORKDIR /

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libfftw3-dev \
    libyaml-dev \
    libsamplerate0 \
    && rm -rf /var/lib/apt/lists/*

# Pin numpy first, then install essentia
RUN pip install --no-cache-dir numpy==1.24.4
RUN pip install --no-cache-dir essentia==2.1b6.dev1110
RUN pip install --no-cache-dir runpod

COPY handler.py /

CMD ["python3", "-u", "handler.py"]
