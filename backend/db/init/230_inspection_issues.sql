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
-- - 待整改：问题刚录入，尚未由站点提交整改反馈
-- - 待复核：站点已提交整改，等待督导组复核
-- - 已闭环：督导组确认问题已经整改，流程关闭
-- - 站经无法整改：督导组确认该问题属于站经理无法整改事项

CREATE TABLE issues (
    id SERIAL PRIMARY KEY,                                                    -- 问题ID，主键，自增
    inspection_id INTEGER NOT NULL REFERENCES inspections(id),                -- 所属巡检主记录ID
    inspector_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,             -- 本条问题实际录入检查人ID
    station_id INTEGER NOT NULL REFERENCES stations(id),                      -- 所属站点ID
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id),    -- 所属检查表ID
    standard_id BIGINT NOT NULL,                                              -- 全局唯一规范ID
    standard_detail_text TEXT NOT NULL,                                       -- 规范详情快照（统一文本展示）
    internal_standard_id TEXT,                                                -- 关联内部规范ID，可为空
    internal_standard_detail_text TEXT,                                       -- 内部规范字段详情快照，可为空

    description TEXT NOT NULL,                                                -- 实际问题描述（督导组必须填写）
    photo_path TEXT NOT NULL,                                                 -- 问题原始照片路径（督导组必须上传，一问题一张）
    status TEXT NOT NULL DEFAULT '待整改',                                     -- 问题当前状态
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                           -- 创建时间

    rectification_result TEXT,                                                -- 站点整改结果：已整改 / 站经无法整改
    rectification_note TEXT,                                                  -- 站点整改说明
    rectification_at TIMESTAMP,                                               -- 站点提交整改时间
    rectification_photo_path TEXT,                                            -- 站点整改照片路径

    review_result TEXT,                                                       -- 督导组复核结果：已整改 / 站经无法整改
    review_note TEXT,                                                         -- 督导组复核说明
    review_at TIMESTAMP,                                                      -- 督导组提交复核时间
    review_photo_path TEXT,                                                   -- 督导组复核照片路径

    audit_status TEXT NOT NULL DEFAULT 'pending',                             -- 审核状态：pending / approved / rejected
    audited_by INTEGER REFERENCES users(id) ON DELETE SET NULL,               -- 审核人
    audited_at TIMESTAMP,                                                     -- 审核时间
    
    is_excellent BOOLEAN NOT NULL DEFAULT FALSE                               -- 是否优秀问题，否决问题不能标记
);

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS inspector_id INTEGER REFERENCES users(id) ON DELETE RESTRICT;

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS internal_standard_id TEXT;

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS internal_standard_detail_text TEXT;

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS audit_status TEXT NOT NULL DEFAULT 'pending';

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS audited_by INTEGER REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS audited_at TIMESTAMP;

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS is_excellent BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS rectification_at TIMESTAMP;

ALTER TABLE issues
ADD COLUMN IF NOT EXISTS review_at TIMESTAMP;

UPDATE issues
SET is_excellent = FALSE
WHERE is_excellent IS NULL
   OR COALESCE(audit_status, 'pending') = 'rejected';

UPDATE issues i
SET inspector_id = ins.inspector_id
FROM inspections ins
WHERE i.inspection_id = ins.id
  AND i.inspector_id IS NULL;

-- 兼容旧数据：站经理已签字确认的历史问题默认视为审核通过，审核时间沿用签字时间。
UPDATE issues i
SET audit_status = 'approved',
    audited_at = COALESCE(ins.station_manager_signed_at, i.audited_at, i.created_at, CURRENT_TIMESTAMP)
FROM inspections ins
WHERE i.inspection_id = ins.id
  AND (
      COALESCE(ins.sign_status, '') = '已签名确认'
      OR ins.station_manager_signed_at IS NOT NULL
      OR NULLIF(ins.station_manager_signature_path, '') IS NOT NULL
      OR NULLIF(ins.station_manager_signed_name, '') IS NOT NULL
  )
  AND COALESCE(i.audit_status, 'pending') = 'pending';

CREATE INDEX IF NOT EXISTS idx_issues_inspector_id
ON issues (inspector_id);

CREATE INDEX IF NOT EXISTS idx_issues_internal_standard_id
ON issues (internal_standard_id);

CREATE INDEX IF NOT EXISTS idx_issues_audit_status
ON issues (audit_status);

CREATE INDEX IF NOT EXISTS idx_issues_is_excellent
ON issues (is_excellent);

CREATE INDEX IF NOT EXISTS idx_issues_station_status_audit
ON issues (station_id, status, audit_status);

CREATE INDEX IF NOT EXISTS idx_issues_created_at
ON issues (created_at DESC);
