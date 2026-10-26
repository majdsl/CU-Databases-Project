-- Step 3: same rows, same schema - what does each engine report?
--   source /tutorial/03-compare.sql

-- Engine-reported metadata. These are each engine's own statistics, not
-- measured disk usage (see docs/storage-findings.md for real file sizes).
SELECT TABLE_NAME, ENGINE, ROW_FORMAT, TABLE_ROWS,
       ROUND(DATA_LENGTH  / 1048576, 2) AS data_mib,
       ROUND(INDEX_LENGTH / 1048576, 2) AS index_mib
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('tut_innodb', 'tut_aria', 'tut_myisam', 'tut_memory', 'tut_rocksdb')
ORDER BY TABLE_NAME;

-- Engines add their own options to an identical CREATE TABLE.
SHOW CREATE TABLE tut_aria\G

-- The same full scan on each engine. Watch the time the client prints
-- after each result. One run on a laptop is a demo, not a benchmark.
SELECT COUNT(*), SUM(delay_min) FROM tut_innodb;
SELECT COUNT(*), SUM(delay_min) FROM tut_aria;
SELECT COUNT(*), SUM(delay_min) FROM tut_myisam;
SELECT COUNT(*), SUM(delay_min) FROM tut_memory;
-- Path A: source /tutorial/03b-myrocks-compare.sql for the fifth scan.
