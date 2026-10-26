-- Step 5: make table-level locking visible.
-- Creates a procedure that updates ONE row in a loop for N seconds, then
-- shows the server's lock counters. You will call it from two terminals.
--   source /tutorial/05-lock-demo.sql

-- Static SQL per engine: no table names are built from strings.
DELIMITER //
CREATE OR REPLACE PROCEDURE tut_hammer(IN engine_name VARCHAR(16), IN row_id INT, IN run_seconds INT)
BEGIN
  DECLARE updates BIGINT DEFAULT 0;
  DECLARE stop_at DATETIME(6);
  IF run_seconds NOT BETWEEN 1 AND 60 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'run_seconds must be between 1 and 60';
  END IF;
  IF engine_name NOT IN ('innodb', 'aria', 'myisam', 'memory', 'rocksdb') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'engine_name must be innodb, aria, myisam, memory or rocksdb';
  END IF;
  SET stop_at = SYSDATE(6) + INTERVAL run_seconds SECOND;
  WHILE SYSDATE(6) < stop_at DO
    CASE engine_name
      WHEN 'innodb'  THEN UPDATE tut_innodb  SET hits = hits + 1 WHERE id = row_id;
      WHEN 'aria'    THEN UPDATE tut_aria    SET hits = hits + 1 WHERE id = row_id;
      WHEN 'myisam'  THEN UPDATE tut_myisam  SET hits = hits + 1 WHERE id = row_id;
      WHEN 'memory'  THEN UPDATE tut_memory  SET hits = hits + 1 WHERE id = row_id;
      WHEN 'rocksdb' THEN UPDATE tut_rocksdb SET hits = hits + 1 WHERE id = row_id;
    END CASE;
    SET updates = updates + 1;
  END WHILE;
  SELECT engine_name AS engine, row_id AS row_updated, updates,
         ROUND(updates / run_seconds) AS updates_per_second;
END //
DELIMITER ;

-- Counter snapshot. Run this line again after each experiment and subtract.
SHOW GLOBAL STATUS WHERE Variable_name IN ('Table_locks_waited', 'Innodb_row_lock_waits');
