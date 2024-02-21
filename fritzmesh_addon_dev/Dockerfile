ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
RUN \
  apk add --no-cache \
    python3 py3-requests py3-aiohttp

# Python 3 HTTP Server serves the current working dir
# So let's set it to our add-on persistent data directory.
WORKDIR /data

# Copy data for add-on
COPY fritzmesh.py /
RUN chmod a+x /fritzmesh.py

CMD [ "/fritzmesh.py", "-hassio", "-nocache" ]
