-- ================================================
-- 重複データクリーンアップSQL
-- サーバーで一度だけ実行してください
-- 実行方法：
--   sqlite3 /data/allowance.db < cleanup_db.sql
-- ================================================

-- chore_typesの重複を削除（id最小のものを残す）
DELETE FROM chore_records WHERE chore_type_id NOT IN (
    SELECT MIN(id) FROM chore_types GROUP BY name
);
DELETE FROM chore_types WHERE id NOT IN (
    SELECT MIN(id) FROM chore_types GROUP BY name
);

-- subjectsの重複を削除（id最小のものを残す）
DELETE FROM grade_records WHERE subject_id NOT IN (
    SELECT MIN(id) FROM subjects GROUP BY name
);
DELETE FROM grade_subjects WHERE subject_id NOT IN (
    SELECT MIN(id) FROM subjects GROUP BY name
);
DELETE FROM subjects WHERE id NOT IN (
    SELECT MIN(id) FROM subjects GROUP BY name
);

-- grade_subjectsの重複を削除
DELETE FROM grade_subjects WHERE id NOT IN (
    SELECT MIN(id) FROM grade_subjects GROUP BY grade, subject_id
);

-- pay_ratesの重複を削除
DELETE FROM pay_rates WHERE id NOT IN (
    SELECT MIN(id) FROM pay_rates GROUP BY key
);

-- UNIQUEインデックスを追加（今後の重複防止）
CREATE UNIQUE INDEX IF NOT EXISTS idx_chore_types_name ON chore_types(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_subjects_name ON subjects(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pay_rates_key ON pay_rates(key);

SELECT 'クリーンアップ完了' as status;
SELECT '家事種類数: ' || COUNT(*) as info FROM chore_types;
SELECT '教科数: ' || COUNT(*) as info FROM subjects;
