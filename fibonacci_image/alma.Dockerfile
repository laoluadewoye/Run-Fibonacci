# Use specific Alma Linux base image
FROM docker.io/library/almalinux:10-minimal AS build

# Install Python, Pip and base for PostgreSQL
RUN microdnf install --setopt=keepcache=0 -y postgresql-libs gcc python3-devel libpq-devel

# Copy requirements into working directory
COPY components/requirements.txt .

# Set virtual enviornment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install pip requirements
RUN pip install --no-cache-dir -r ./requirements.txt

# Use specific Alma Linux base image
FROM docker.io/library/almalinux:10-minimal AS final

# Ensure packages are updated and upgraded
RUN microdnf update -y && microdnf upgrade -y

# Install Python, Pip, Shadow Utils, and PostgreSQL library
RUN microdnf install --setopt=keepcache=0 -y python3 python3-pip shadow-utils postgresql-libs

# Set working directory to a custom app one
WORKDIR /usr/src/app/

# Copy components into working directory
COPY components/ .

# Install Pip requirements
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy python virtual enviornment
COPY --from=build /opt/venv/ /opt/venv/

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
