-- 初始化检查表注册数据

INSERT INTO inspection_tables (
    table_code,
    table_name,
    description,
    is_active
)
VALUES
(
    'quality_check',
    '计质量检查表',
    '用于计质量相关巡检问题登记与规范库查询',
    TRUE
),
(
    'service_hygiene_check',
    '服务及卫生管理方面检查表',
    '用于服务及卫生管理方面巡检问题登记与规范库查询',
    TRUE
);