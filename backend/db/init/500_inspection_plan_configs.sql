-- inspection_plan_configs 表：巡检计划配置主表
-- 用途：
-- 1. 按“检查表 + 覆盖要求 + 周期”保存一条计划配置
-- 2. 作为巡检计划主记录，供前端“任务总览 / 历史计划 / 管理计划”使用
-- 3. 后续通过 inspection_plan_station_items 关联纳入本计划的站点明细
--
-- 说明：
-- - 一张检查表只能保留一种覆盖要求：monthly / quarterly / yearly
-- - 后端在新建或编辑计划时会删除同一检查表旧覆盖要求下的计划
-- - 一张检查表在同一个 coverage_type + period_key 下只允许存在一条计划配置
-- - created_by / updated_by 记录计划配置责任人
-- - 计划创建即发布，不存在草稿；完成状态由站点明细 completion_status 汇总计算
--
-- coverage_type 说明：
-- - monthly：月度覆盖
-- - quarterly：季度覆盖
-- - yearly：年度覆盖
--
-- status 说明：
-- - active：兼容保留字段，表示计划已发布；不用于判断未完成 / 已完成

CREATE TABLE inspection_plan_configs (
    id SERIAL PRIMARY KEY,                                                        -- 计划配置主键ID

    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id),        -- 对应检查表ID
    coverage_type TEXT NOT NULL,                                                  -- 覆盖要求：monthly / quarterly / yearly
    period_key TEXT NOT NULL,                                                     -- 周期标识：如 2026年4月 / 2026年第二季度 / 2026年

    created_by INTEGER NOT NULL REFERENCES users(id),                             -- 创建人ID
    updated_by INTEGER REFERENCES users(id),                                      -- 最后更新人ID

    status TEXT NOT NULL DEFAULT 'active',                                        -- 创建即发布，固定为 active
    remark TEXT,                                                                  -- 备注说明

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                               -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                               -- 最后更新时间

    CONSTRAINT chk_inspection_plan_configs_coverage_type
        CHECK (coverage_type IN ('monthly', 'quarterly', 'yearly')),

    CONSTRAINT chk_inspection_plan_configs_status
        CHECK (status IN ('active')),

    CONSTRAINT uq_inspection_plan_configs_table_period
        UNIQUE (inspection_table_id, coverage_type, period_key)
);

-- 常用查询索引
CREATE INDEX idx_inspection_plan_configs_table_id
    ON inspection_plan_configs(inspection_table_id);

CREATE INDEX idx_inspection_plan_configs_coverage_period
    ON inspection_plan_configs(coverage_type, period_key);

CREATE INDEX idx_inspection_plan_configs_status
    ON inspection_plan_configs(status);
