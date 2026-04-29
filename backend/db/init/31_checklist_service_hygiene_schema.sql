-- 服务及卫生管理方面检查表
-- 用途：
-- 1. 存储“服务及卫生管理方面检查表”中的规范条目
-- 2. 每条规范拥有全局唯一 standard_id
-- 3. 本表字段固定，对应服务及卫生管理方面检查表本身的结构

CREATE TABLE inspection_table_service_hygiene_check (
    id SERIAL PRIMARY KEY,                                   -- 主键，自增
    standard_id BIGINT UNIQUE NOT NULL,                      -- 全局唯一规范ID
    project_name TEXT,                                       -- 项目，例如：加油区 / 营业厅 / 洗手间 / 其他管理
    check_category TEXT,                                     -- 检查类别，例如：整洁舒心 / 快捷服务 / 暖心服务
    check_content TEXT NOT NULL,                             -- 检查内容
    evaluation_standard TEXT,                                -- 检查评比标准
    check_method TEXT,                                       -- 检查方式
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP           -- 创建时间
);