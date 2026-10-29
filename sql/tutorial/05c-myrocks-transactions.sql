-- Step 5c: COMMIT and ROLLBACK are SQL; their guarantees depend on the engine.
-- Run in the reserved tutorial database after checking for existing tut_* objects.
-- CREATE refuses an existing transaction-demo table; no user table is replaced.
-- Nontransactional ROLLBACK can issue warning1196; its writes remain.
-- This is a deterministic semantics lesson, not a timing or power-loss experiment.
SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION';
SET SESSION autocommit=1;

-- ROCKSDB: identical statements, different rollback guarantees.
CREATE TABLE tut_tx_rocksdb (id INT NOT NULL PRIMARY KEY, balance INT NOT NULL) ENGINE=ROCKSDB;
SELECT 'rocksdb', 'engine', ENGINE FROM information_schema.TABLES
  WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_tx_rocksdb';
INSERT INTO tut_tx_rocksdb VALUES (1,100),(2,100);
SELECT 'rocksdb', 'before', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_rocksdb;
START TRANSACTION;
UPDATE tut_tx_rocksdb SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_rocksdb SET balance=balance-25 WHERE id=2;
SELECT 'rocksdb', 'during', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_rocksdb;
ROLLBACK;
SELECT 'rocksdb', 'after_rollback', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_rocksdb;
-- Reset outside a transaction so both engine types start the commit example alike.
UPDATE tut_tx_rocksdb SET balance=100;
START TRANSACTION;
UPDATE tut_tx_rocksdb SET balance=balance+25 WHERE id=1;
UPDATE tut_tx_rocksdb SET balance=balance-25 WHERE id=2;
COMMIT;
SELECT 'rocksdb', 'after_commit', GROUP_CONCAT(CONCAT(id, ':', balance) ORDER BY id SEPARATOR ',') FROM tut_tx_rocksdb;
DROP TABLE tut_tx_rocksdb;
