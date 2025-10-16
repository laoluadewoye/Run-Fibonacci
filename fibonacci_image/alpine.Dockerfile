# Use specific alpine linux base image
FROM docker.io/library/alpine:3.22

# Ensure packages are updated
RUN apk update

# Install python and pip
RUN apk add python3 py3-pip curl

# Install flask and gunicorn
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --no-cache-dir flask==3.1.2 gunicorn==23.0.0

# Create the app user
RUN adduser -D app

# Set working directory to a custom app one
WORKDIR /usr/src/app/

# Copy necessary items into working directory
COPY components/gunicorn.conf.py .
COPY components/rest.py .
COPY components/send_next_fib.sh .
COPY components/send_healthcheck.sh .

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
