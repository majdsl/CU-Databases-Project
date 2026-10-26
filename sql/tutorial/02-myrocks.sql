-- Step 2: the same table on MyRocks (SQL engine name ROCKSDB).
-- Needs the project's five-engine image (amd64). On the ARM path, skip this file.
--   source /tutorial/02-myrocks.sql

CREATE OR REPLACE TABLE tut_rocksdb (
  id          INT         NOT NULL,
  airport_id  INT         NOT NULL,
  delay_min   SMALLINT    NOT NULL,
  hits        BIGINT      NOT NULL DEFAULT 0,
  note        VARCHAR(32) NOT NULL,
  PRIMARY KEY (id) USING BTREE,
  KEY by_airport (airport_id) USING BTREE
) ENGINE=ROCKSDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

INSERT INTO tut_rocksdb (id, airport_id, delay_min, note)
  SELECT seq, 1 + seq % 500, CAST(seq % 196 AS SIGNED) - 15, CONCAT('row-', seq) FROM seq_1_to_50000;

SELECT 'rocksdb' AS engine, COUNT(*) AS row_count FROM tut_rocksdb;
