-- 初始化检查表字段配置数据
-- 用途：
-- 1. 记录每张检查表有哪些字段
-- 2. 标记这些字段可用于前端高级筛选
-- 3. 前端可根据 inspection_table_id 动态渲染筛选项

INSERT INTO inspection_table_fields (
    inspection_table_id,
    field_key,
    field_label,
    is_filterable,
    sort_order
)
VALUES
-- 计质量检查表（inspection_table_id = 1）
(1, 'serial_no', '序号', TRUE, 1),
(1, 'business_process', '业务流程', TRUE, 2),
(1, 'check_item', '检查项目', TRUE, 3),
(1, 'requirement', '规范要求', TRUE, 4),
(1, 'check_method', '检查方法', TRUE, 5),
(1, 'issue_code', '问题编号', TRUE, 6),
(1, 'common_issue', '常见问题', TRUE, 7),
(1, 'inspection_path', '检查路径', TRUE, 8),
(1, 'is_forbidden', '是否禁止项', TRUE, 9),

-- 服务及卫生管理方面检查表（inspection_table_id = 2）
(2, 'project_name', '项目', TRUE, 1),
(2, 'check_category', '检查类别', TRUE, 2),
(2, 'check_content', '检查内容', TRUE, 3),
(2, 'evaluation_standard', '检查评比标准', TRUE, 4),
(2, 'check_method', '检查方式', TRUE, 5);