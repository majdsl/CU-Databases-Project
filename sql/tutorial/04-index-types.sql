-- Step 4: MEMORY with a HASH index versus a BTREE index.
-- Self-contained: creates its own two tables.
--   source /tutorial/04-index-types.sql

SET SESSION max_heap_table_size = 67108864;

CREATE OR REPLACE TABLE tut_idx_btree (
  id INT NOT NULL,
  airport_id INT NOT NULL,
  PRIMARY KEY (id) USING BTREE,
  KEY by_airport (airport_id) USING BTREE
) ENGINE=MEMORY;

CREATE OR REPLACE TABLE tut_idx_hash (
  id INT NOT NULL,
  airport_id INT NOT NULL,
  PRIMARY KEY (id) USING BTREE,
  KEY by_airport (airport_id) USING HASH
) ENGINE=MEMORY;

-- 100,000 rows; every airport_id value appears 20 times.
INSERT INTO tut_idx_btree SELECT seq, 1 + seq % 5000 FROM seq_1_to_100000;
INSERT INTO tut_idx_hash  SELECT seq, 1 + seq % 5000 FROM seq_1_to_100000;

-- ANALYZE runs the query and reports what actually happened:
-- compare the "type" and "r_rows" (rows really read) columns.

-- Equality: both indexes can answer it directly.
ANALYZE SELECT COUNT(*) FROM tut_idx_btree WHERE airport_id = 100;
ANALYZE SELECT COUNT(*) FROM tut_idx_hash  WHERE airport_id = 100;

-- Range (200 matching rows): a hash cannot be walked in order.
ANALYZE SELECT COUNT(*) FROM tut_idx_btree WHERE airport_id BETWEEN 100 AND 109;
ANALYZE SELECT COUNT(*) FROM tut_idx_hash  WHERE airport_id BETWEEN 100 AND 109;
