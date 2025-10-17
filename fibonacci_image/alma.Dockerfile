# Use specific Alma Linux base image
FROM docker.io/library/almalinux:10-minimal

# Set working directory to a custom app one
WORKDIR /usr/src/app/

# Copy components into working directory
COPY components/ .

# Ensure packages are updated
RUN microdnf update -y && microdnf upgrade -y

# Install Python, Pip, and Shadow Utils
RUN microdnf install -y python3 python3-pip shadow-utils

# Install Pip requirements
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
RUN pip install --no-cache-dir -r /usr/src/app/requirements.txt

# Create the app user
RUN useradd --create-home --user-group app

# Make the app user owner of that directory
RUN chown --recursive app:app /usr/src/app/

# Set the user to app
USER app

# Setup the healthcheck
HEALTHCHECK --start-period=10s --interval=10s --timeout=5s --retries=3 CMD python3 /usr/src/app/send_healthcheck.py

# Run the server
ENTRYPOINT ["gunicorn"]
