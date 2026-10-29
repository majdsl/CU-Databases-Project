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
  DECLARE started_at DATETIME(6);
  DECLARE finished_at DATETIME(6);
  DECLARE affected_rows INT DEFAULT 0;
  DECLARE elapsed_us BIGINT;
  IF run_seconds IS NULL OR run_seconds NOT BETWEEN 1 AND 60 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'run_seconds must be between 1 and 60';
  END IF;
  IF engine_name IS NULL OR engine_name NOT IN ('innodb', 'aria', 'myisam', 'memory', 'rocksdb') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'engine_name must be innodb, aria, myisam, memory or rocksdb';
  END IF;
  IF row_id IS NULL OR row_id < 1 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'row_id must be positive and identify an existing tutorial row';
  END IF;
  SET started_at = SYSDATE(6);
  SET stop_at = started_at + INTERVAL run_seconds SECOND;
  WHILE SYSDATE(6) < stop_at DO
    CASE engine_name
      WHEN 'innodb'  THEN UPDATE tut_innodb  SET hits = hits + 1 WHERE id = row_id;
        SET affected_rows = ROW_COUNT();
      WHEN 'aria'    THEN UPDATE tut_aria    SET hits = hits + 1 WHERE id = row_id;
        SET affected_rows = ROW_COUNT();
      WHEN 'myisam'  THEN UPDATE tut_myisam  SET hits = hits + 1 WHERE id = row_id;
        SET affected_rows = ROW_COUNT();
      WHEN 'memory'  THEN UPDATE tut_memory  SET hits = hits + 1 WHERE id = row_id;
        SET affected_rows = ROW_COUNT();
      WHEN 'rocksdb' THEN UPDATE tut_rocksdb SET hits = hits + 1 WHERE id = row_id;
        SET affected_rows = ROW_COUNT();
    END CASE;
    IF affected_rows <> 1 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'row_id must identify exactly one existing tutorial row';
    END IF;
    SET updates = updates + 1;
  END WHILE;
  SET finished_at = SYSDATE(6);
  SET elapsed_us = TIMESTAMPDIFF(MICROSECOND, started_at, finished_at);
  SELECT engine_name AS engine, row_id AS row_updated, updates,
         elapsed_us * 0.000001 AS elapsed_seconds,
         ROUND(updates * 1000000 / NULLIF(elapsed_us, 0)) AS updates_per_second,
         DATE_FORMAT(started_at, '%Y-%m-%d %H:%i:%s.%f') AS server_started_at,
         DATE_FORMAT(finished_at, '%Y-%m-%d %H:%i:%s.%f') AS server_finished_at;
END //
DELIMITER ;

-- Counter snapshot. Run this line again after each experiment and subtract.
SHOW GLOBAL STATUS WHERE Variable_name IN ('Table_locks_waited', 'Innodb_row_lock_waits');
