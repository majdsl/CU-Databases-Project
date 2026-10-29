CREATE TABLE benchmark_events (
    event_id INT NOT NULL,
    route_id INT NOT NULL,
    departure_epoch INT NOT NULL,
    delay_minutes SMALLINT NOT NULL,
    fare_cents INT NOT NULL,
    passengers SMALLINT NOT NULL,
    payload VARCHAR(64) NOT NULL,
    PRIMARY KEY (event_id) USING BTREE,
    INDEX route_departure (route_id, departure_epoch) USING BTREE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
