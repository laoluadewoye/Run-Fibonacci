-- init-db.sql

CREATE TABLE IF NOT EXISTS datastore (
    log_id SERIAL PRIMARY KEY,
    log_time TIMESTAMP NOT NULL,
    log_server VARCHAR(320) NOT NULL,
    log_type VARCHAR(20) NOT NULL,
    log_kinds VARCHAR(20) NOT NULL,
    log_details VARCHAR(320) NOT NULL,
    log_hash VARCHAR(70) NOT NULL
);
