-- Path A only: check MyRocks after the clean restart.
--   source /tutorial/06b-myrocks-after-restart.sql
SELECT 'rocksdb' AS engine, COUNT(*) AS rows_after_restart FROM tut_rocksdb;
