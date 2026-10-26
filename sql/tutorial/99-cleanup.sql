-- Remove everything the tutorial created. Benchmark tables are not touched.
--   source /tutorial/99-cleanup.sql
DROP TABLE IF EXISTS tut_innodb, tut_aria, tut_myisam, tut_memory, tut_rocksdb,
                     tut_idx_btree, tut_idx_hash;
DROP PROCEDURE IF EXISTS tut_hammer;
