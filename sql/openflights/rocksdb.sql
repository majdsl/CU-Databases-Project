CREATE TABLE openflights_routes (
    route_row_id INT NOT NULL,
    airline VARCHAR(3) NOT NULL,
    airline_id INT NULL,
    source_code VARCHAR(4) NOT NULL,
    source_id INT NULL,
    destination_code VARCHAR(4) NOT NULL,
    destination_id INT NULL,
    codeshare VARCHAR(1) NOT NULL,
    stops TINYINT UNSIGNED NOT NULL,
    equipment VARCHAR(64) NOT NULL,
    PRIMARY KEY (route_row_id) USING BTREE,
    KEY source_destination (source_id, destination_id) USING BTREE
) ENGINE=ROCKSDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
