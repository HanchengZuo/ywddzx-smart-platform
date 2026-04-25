-- inspection_plan_station_items 表：巡检计划站点明细表
-- 用途：
-- 1. 保存某一条巡检计划配置下纳入的站点
-- 2. 记录每个站点在当前计划中的完成状态
-- 3. 可关联实际完成该计划的 inspections 记录
--
-- 说明：
-- - 每条记录表示：某计划配置下的一个站点
-- - plan_config_id + station_id 全局唯一，避免同一计划重复纳入同一站点
-- - is_included 用于表示该站点是否纳入当前计划
--   （如后续你更倾向“只有纳入的才落表”，也可以始终写 TRUE）
-- - completion_status 用于保存当前计划维度下的站点完成情况
--
-- completion_status 说明：
-- - pending：未完成
-- - completed：已完成
--
-- completed_inspection_id 说明：
-- - 对应完成本计划的 inspections 主记录ID
-- - 若当前站点尚未完成，则为空

CREATE TABLE inspection_plan_station_items (
    id SERIAL PRIMARY KEY,                                                        -- 计划站点明细主键ID

    plan_config_id INTEGER NOT NULL REFERENCES inspection_plan_configs(id) ON DELETE CASCADE, -- 所属计划配置ID
    station_id INTEGER NOT NULL REFERENCES stations(id),                          -- 站点ID

    is_included BOOLEAN NOT NULL DEFAULT TRUE,                                    -- 是否纳入当前计划
    completion_status TEXT NOT NULL DEFAULT 'pending',                            -- 完成状态：pending / completed
    completed_inspection_id INTEGER REFERENCES inspections(id),                   -- 完成该计划对应的巡检主记录ID
    completed_at TIMESTAMP,                                                       -- 计划完成时间

    note TEXT,                                                                    -- 备注

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                               -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                               -- 最后更新时间

    CONSTRAINT chk_inspection_plan_station_items_completion_status
        CHECK (completion_status IN ('pending', 'completed')),

    CONSTRAINT uq_inspection_plan_station_items_plan_station
        UNIQUE (plan_config_id, station_id)
);

-- 常用查询索引
CREATE INDEX idx_inspection_plan_station_items_plan_config_id
    ON inspection_plan_station_items(plan_config_id);

CREATE INDEX idx_inspection_plan_station_items_station_id
    ON inspection_plan_station_items(station_id);

CREATE INDEX idx_inspection_plan_station_items_completion_status
    ON inspection_plan_station_items(completion_status);

CREATE INDEX idx_inspection_plan_station_items_completed_inspection_id
    ON inspection_plan_station_items(completed_inspection_id);