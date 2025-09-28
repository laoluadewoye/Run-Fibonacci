# Use specific alpine based python
FROM docker.io/library/python:3.13-alpine3.22

# Ensure packages are updated
RUN apk update

# Install curl
RUN apk add curl

# Install flask and gunicorn
RUN pip install --no-cache-dir flask==3.1.2 gunicorn==23.0.0

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
HEALTHCHECK --start-period=10s --interval=10s --timeout=5s --retries=3 CMD /usr/src/app/send_healthcheck.sh

# Run the server
ENTRYPOINT ["gunicorn"]
