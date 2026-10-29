-- Step 5c: COMMIT and ROLLBACK are SQL; their guarantees depend on the engine.
-- Run in the reserved tutorial database after checking for existing tut_* objects.
-- CREATE refuses an existing transaction-demo table; no user table is replaced.
-- Nontransactional ROLLBACK can issue warning1196; its writes remain.
-- This is a deterministic semantics lesson, not a timing or power-loss experiment.
SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';
SET SESSION autocommit=1;

-- InnoDB: identical statements, different rollback guarantees.
CREATE TABLE tut_tx_innodb (id INT NOT NULL PRIMARY KEY, balance INT NOT NULL) ENGINE=InnoDB;
SELECT 'innodb', 'engine', ENGINE FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_tx_innodb';
INSERT INTO tut_tx_innodb VALUES (1,100),(2,100);
SELECT 'innodb', 'before', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_innodb;
START TRANSACTION;
UPDATE tut_tx_innodb SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_innodb SET balance=balance-25 WHERE id=2;
SELECT 'innodb', 'during', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_innodb;
ROLLBACK;
SELECT 'innodb', 'after_rollback', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_innodb;
-- Reset outside a transaction so both engine types start the commit example alike.
UPDATE tut_tx_innodb SET balance=100;
START TRANSACTION;
UPDATE tut_tx_innodb SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_innodb SET balance=balance-25 WHERE id=2;
COMMIT;
SELECT 'innodb', 'after_commit', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_innodb;
DROP TABLE tut_tx_innodb;

-- Aria: identical statements, different rollback guarantees.
CREATE TABLE tut_tx_aria (id INT NOT NULL PRIMARY KEY, balance INT NOT NULL) ENGINE=Aria;
SELECT 'aria', 'engine', ENGINE FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_tx_aria';
INSERT INTO tut_tx_aria VALUES (1,100),(2,100);
SELECT 'aria', 'before', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_aria;
START TRANSACTION;
UPDATE tut_tx_aria SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_aria SET balance=balance-25 WHERE id=2;
SELECT 'aria', 'during', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_aria;
ROLLBACK;
SELECT 'aria', 'after_rollback', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_aria;
-- Reset outside a transaction so both engine types start the commit example alike.
UPDATE tut_tx_aria SET balance=100;
START TRANSACTION;
UPDATE tut_tx_aria SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_aria SET balance=balance-25 WHERE id=2;
COMMIT;
SELECT 'aria', 'after_commit', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_aria;
DROP TABLE tut_tx_aria;

-- MyISAM: identical statements, different rollback guarantees.
CREATE TABLE tut_tx_myisam (id INT NOT NULL PRIMARY KEY, balance INT NOT NULL) ENGINE=MyISAM;
SELECT 'myisam', 'engine', ENGINE FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_tx_myisam';
INSERT INTO tut_tx_myisam VALUES (1,100),(2,100);
SELECT 'myisam', 'before', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_myisam;
START TRANSACTION;
UPDATE tut_tx_myisam SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_myisam SET balance=balance-25 WHERE id=2;
SELECT 'myisam', 'during', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_myisam;
ROLLBACK;
SELECT 'myisam', 'after_rollback', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_myisam;
-- Reset outside a transaction so both engine types start the commit example alike.
UPDATE tut_tx_myisam SET balance=100;
START TRANSACTION;
UPDATE tut_tx_myisam SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_myisam SET balance=balance-25 WHERE id=2;
COMMIT;
SELECT 'myisam', 'after_commit', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_myisam;
DROP TABLE tut_tx_myisam;

-- MEMORY: identical statements, different rollback guarantees.
CREATE TABLE tut_tx_memory (id INT NOT NULL PRIMARY KEY, balance INT NOT NULL) ENGINE=MEMORY;
SELECT 'memory', 'engine', ENGINE FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_tx_memory';
INSERT INTO tut_tx_memory VALUES (1,100),(2,100);
SELECT 'memory', 'before', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_memory;
START TRANSACTION;
UPDATE tut_tx_memory SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_memory SET balance=balance-25 WHERE id=2;
SELECT 'memory', 'during', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_memory;
ROLLBACK;
SELECT 'memory', 'after_rollback', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_memory;
-- Reset outside a transaction so both engine types start the commit example alike.
UPDATE tut_tx_memory SET balance=100;
START TRANSACTION;
UPDATE tut_tx_memory SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_memory SET balance=balance-25 WHERE id=2;
COMMIT;
SELECT 'memory', 'after_commit', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_memory;
DROP TABLE tut_tx_memory;
