# Use specific Alpine Linux base image
FROM docker.io/library/alpine:3.22 AS build

# Install Python, Pip and base for PostgreSQL
RUN apk add --no-cache postgresql-dev gcc python3-dev musl-dev

# Copy requirements into working directory
COPY components/requirements.txt .

# Set virtual enviornment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install pip requirements
RUN pip install --no-cache-dir -r ./requirements.txt

# Use specific Alpine Linux base image
FROM docker.io/library/alpine:3.22 AS final

# Ensure packages are updated and upgraded
RUN apk update && apk upgrade

# Install Python, Pip, and PostgreSQL library
RUN apk add --no-cache python3 py3-pip libpq

# Set working directory to a custom app one
WORKDIR /usr/src/app/

# Copy components into working directory
COPY components/ .

# Set virtual enviornment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy python virtual enviornment
COPY --from=build /opt/venv/ /opt/venv/

# Create the app user
RUN adduser -D app

# Make the app user owner of that directory
RUN chown --recursive app:app /usr/src/app/

# Set the user to app
USER app

# Setup the healthcheck
HEALTHCHECK --start-period=10s --interval=10s --timeout=5s --retries=3 CMD python3 /usr/src/app/send_healthcheck.py

# Set default enviornmental variables
ENV SERVER_CONFIG_FILEPATH="/usr/src/app/server_config.json"
ENV DEFAULT_SERVER_CONFIG_FILEPATH="/usr/src/app/server_config.json"

# Run the server
ENTRYPOINT ["gunicorn"]
