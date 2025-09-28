# Set build args
ARG BASE_IMAGE="docker.io/library/python:3.13-alpine3.22"
ARG FLASK_VERSION="3.1.2"
ARG GUNICORN_VERSION="23.0.0"
ARG HEALTH_START_PERIOD="10s"
ARG HEALTH_CHECK_INTERVAL="10s"
ARG HEALTH_CHECK_TIMEOUT="10s"
ARG HEALTH_CHECK_RETRIES="3"

# Use specific alpine based python
FROM ${BASE_IMAGE}

# Install neccessary packages
RUN pip install --no-cache-dir flask==${FLASK_VERSION} gunicorn==${GUNICORN_VERSION}

# Create the app user
RUN adduser -D app

# Set working directory to a custom app one
WORKDIR /usr/src/app/

# Copy necessary items into working directory
COPY gunicorn.conf.py .
COPY server.py .
COPY send_next_fib.sh .
COPY send_healthcheck.sh .

# Make the bash scripts executable
RUN chmod +x send_next_fib.sh
RUN chmod +x send_healthcheck.sh

# Make the app user owner of that directory
RUN chown --recursive app:app /usr/src/app/

# Set the user to app
USER app

# Setup the healthcheck
HEALTHCHECK --start-period=${HEALTH_START_PERIOD} \
    --interval=${HEALTH_CHECK_INTERVAL} \
    --timeout=${HEALTH_CHECK_TIMEOUT} \
    --retries=${HEALTH_CHECK_RETRIES} \
    CMD /usr/src/app/send_healthcheck.sh

# Run the server
ENTRYPOINT ["gunicorn"]
