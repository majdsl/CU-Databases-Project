-- Step 6: run this AFTER restarting the server.
--   source /tutorial/06-after-restart.sql

SELECT 'innodb' AS engine, COUNT(*) AS rows_after_restart FROM tut_innodb
UNION ALL SELECT 'aria',   COUNT(*) FROM tut_aria
UNION ALL SELECT 'myisam', COUNT(*) FROM tut_myisam
UNION ALL SELECT 'memory', COUNT(*) FROM tut_memory;

-- Path A: source /tutorial/06b-myrocks-after-restart.sql for MyRocks.

-- The update counters from step 5 survived on the persistent engines.
SELECT 'aria' AS engine, id, hits FROM tut_aria WHERE id IN (1, 2)
UNION ALL SELECT 'innodb', id, hits FROM tut_innodb WHERE id IN (1, 2);

-- The MEMORY table definition survived; only its rows are gone.
SHOW CREATE TABLE tut_memory\G
