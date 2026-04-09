-- issues 表：巡检问题主表
-- 用途：
-- 1. 保存督导组录入的具体问题
-- 2. 绑定所属巡检主记录 inspections
-- 3. 绑定所属巡检大类记录 inspection_category_records
-- 4. 绑定所属站点 stations
-- 5. 绑定对应规范标准 inspection_standards
-- 6. 保存站点整改反馈与督导组复核反馈
--
-- 说明：
-- - 只有“发现问题”时，才会生成 issues 记录
-- - “未发现问题”不会生成 issues 记录，只记录在 inspection_category_records 表中
--
-- status 说明：
-- - 待整改：问题刚录入，或督导组反馈仍未完成整改
-- - 待复核：站点已提交整改，等待督导组复核
-- - 已闭环：督导组确认已整改，问题关闭

CREATE TABLE issues (
    id SERIAL PRIMARY KEY,                                                        -- 问题ID，主键，自增
    inspection_id INTEGER NOT NULL REFERENCES inspections(id),                    -- 所属巡检主记录ID
    category_record_id INTEGER NOT NULL REFERENCES inspection_category_records(id), -- 所属巡检大类结果记录ID
    station_id INTEGER NOT NULL REFERENCES stations(id),                          -- 所属站点ID
    standard_id INTEGER NOT NULL REFERENCES inspection_standards(id),             -- 对应规范标准ID

    description TEXT NOT NULL,                                                    -- 实际问题描述（督导组必须填写）
    photo_path TEXT NOT NULL,                                                     -- 问题原始照片路径（督导组必须上传，一问题一张）
    status TEXT NOT NULL DEFAULT '待整改',                                         -- 问题当前状态
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                               -- 创建时间

    rectification_result TEXT,                                                    -- 站点整改结果：未整改 / 已整改 / 站级无法完成整改
    rectification_note TEXT,                                                      -- 站点整改说明
    rectification_photo_path TEXT,                                                -- 站点整改照片路径

    review_result TEXT,                                                           -- 督导组复核结果：未整改 / 已整改 / 站级无法完成整改
    review_note TEXT,                                                             -- 督导组复核说明
    review_photo_path TEXT                                                        -- 督导组复核照片路径
);