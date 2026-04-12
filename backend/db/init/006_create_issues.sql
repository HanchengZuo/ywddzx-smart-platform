-- issues 表：巡检问题主表
-- 用途：
-- 1. 保存督导组录入的具体问题
-- 2. 绑定所属巡检主记录 inspections
-- 3. 绑定所属站点 stations
-- 4. 绑定所属检查表 inspection_tables
-- 5. 记录所选规范的全局唯一 standard_id
-- 6. 保存规范详情快照，便于统一展示与后续追溯
-- 7. 保存站点整改反馈与督导组复核反馈
--
-- 说明：
-- - 每条 issues 记录对应一次“发现问题”
-- - 不再使用 inspection_categories / inspection_category_records
-- - 不同检查表拥有不同属性，因此问题表不直接依赖统一规范表
-- - 规范详情统一落为 standard_detail_text，供问题列表/我的问题统一展示
--
-- status 说明：
-- - 待整改：问题刚录入，或督导组反馈仍未完成整改
-- - 待复核：站点已提交整改，等待督导组复核
-- - 已闭环：督导组确认已整改，问题关闭

CREATE TABLE issues (
    id SERIAL PRIMARY KEY,                                                    -- 问题ID，主键，自增
    inspection_id INTEGER NOT NULL REFERENCES inspections(id),                -- 所属巡检主记录ID
    station_id INTEGER NOT NULL REFERENCES stations(id),                      -- 所属站点ID
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id),    -- 所属检查表ID
    standard_id BIGINT NOT NULL,                                              -- 全局唯一规范ID
    standard_detail_text TEXT NOT NULL,                                       -- 规范详情快照（统一文本展示）

    description TEXT NOT NULL,                                                -- 实际问题描述（督导组必须填写）
    photo_path TEXT NOT NULL,                                                 -- 问题原始照片路径（督导组必须上传，一问题一张）
    status TEXT NOT NULL DEFAULT '待整改',                                     -- 问题当前状态
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                           -- 创建时间

    rectification_result TEXT,                                                -- 站点整改结果：未整改 / 已整改 / 站级无法完成整改
    rectification_note TEXT,                                                  -- 站点整改说明
    rectification_photo_path TEXT,                                            -- 站点整改照片路径

    review_result TEXT,                                                       -- 督导组复核结果：未整改 / 已整改 / 站级无法完成整改
    review_note TEXT,                                                         -- 督导组复核说明
    review_photo_path TEXT                                                    -- 督导组复核照片路径
);