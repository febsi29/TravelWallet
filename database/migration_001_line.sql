-- migration_001_line.sql
-- 新增 LINE 使用者相關欄位至 users 資料表
-- 若欄位已存在，SQLite 會回傳錯誤，呼叫端應忽略 "duplicate column name" 錯誤

ALTER TABLE users ADD COLUMN line_user_id TEXT;
ALTER TABLE users ADD COLUMN line_display_name TEXT;
ALTER TABLE users ADD COLUMN line_picture_url TEXT;

-- 建立 line_user_id 的索引以加速查詢
CREATE INDEX IF NOT EXISTS idx_users_line ON users(line_user_id);
