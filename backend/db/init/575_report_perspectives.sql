-- Move existing department grants/denials without changing other roles or data scopes.
INSERT INTO role_permissions (role, permission_key, is_allowed, updated_by)
SELECT role, 'view_department_inspection_reports', is_allowed, updated_by
FROM role_permissions
WHERE permission_key = 'view_inspection_reports'
  AND role IN ('quality_safety', 'development_plan', 'oil_gas', 'non_oil', 'finance')
ON CONFLICT (role, permission_key) DO NOTHING;

INSERT INTO user_permissions (user_id, permission_key, is_allowed, updated_by)
SELECT p.user_id, 'view_department_inspection_reports', p.is_allowed, p.updated_by
FROM user_permissions p JOIN users u ON u.id = p.user_id
WHERE p.permission_key = 'view_inspection_reports'
  AND u.role IN ('quality_safety', 'development_plan', 'oil_gas', 'non_oil', 'finance')
ON CONFLICT (user_id, permission_key) DO NOTHING;

UPDATE role_permissions SET is_allowed = FALSE, updated_at = CURRENT_TIMESTAMP
WHERE permission_key = 'view_inspection_reports' AND is_allowed
  AND role IN ('quality_safety', 'development_plan', 'oil_gas', 'non_oil', 'finance');

UPDATE user_permissions p SET is_allowed = FALSE, updated_at = CURRENT_TIMESTAMP
FROM users u WHERE u.id = p.user_id
  AND p.permission_key = 'view_inspection_reports' AND p.is_allowed
  AND u.role IN ('quality_safety', 'development_plan', 'oil_gas', 'non_oil', 'finance');
