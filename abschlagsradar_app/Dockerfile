FROM python:3.12.15-slim-bookworm
ARG BUILD_VERSION=0.4.4
ARG BUILD_ARCH=amd64
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="${BUILD_ARCH}" \
      io.hass.name="AbschlagsRadar" \
      org.opencontainers.image.source="https://github.com/OrbitNestLab/AbschlagsRadar" \
      org.opencontainers.image.authors="AbschlagsRadar"
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-lock.txt /app/
RUN pip install --no-cache-dir --upgrade pip==26.2.1 && pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
WORKDIR /app
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1
EXPOSE 8099
CMD ["python", "server.py"]
