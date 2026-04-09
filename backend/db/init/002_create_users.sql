

-- users 表：系统登录用户表
-- 用途：
-- 1. 保存系统账号信息
-- 2. 区分角色（督导组 / 站点账号）
-- 3. 通过 station_id 关联所属站点
--
-- 说明：
-- - supervisor：督导组账号，station_id 可为空
-- - station_manager：站点账号，station_id 必须关联具体站点

CREATE TABLE users (
    id SERIAL PRIMARY KEY,                              -- 用户ID，主键，自增
    username TEXT UNIQUE NOT NULL,                      -- 登录用户名，唯一
    password TEXT NOT NULL,                             -- 登录密码（当前阶段先明文，后续可改哈希密码）
    role TEXT NOT NULL,                                 -- 用户角色：supervisor / station_manager
    real_name TEXT NOT NULL,                            -- 用户姓名
    phone TEXT,                                         -- 联系手机号
    station_id INTEGER REFERENCES stations(id),         -- 所属站点ID；督导组可为空，站点账号关联具体站点
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,     -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP      -- 更新时间
);