-- Path A only: complete the same comparison for MyRocks.
--   source /tutorial/03b-myrocks-compare.sql
SELECT COUNT(*), SUM(delay_min) FROM tut_rocksdb;
