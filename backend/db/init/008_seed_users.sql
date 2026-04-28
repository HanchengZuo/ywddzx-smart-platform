-- 初始化测试账号
-- 说明：
-- 1. 督导组账号不绑定站点
-- 2. 站点主数据后续仅通过“站点数据管理”页面维护，因此这里不再预置站点账号
-- 3. 当前阶段密码统一使用明文 123456，后续再改为哈希密码

INSERT INTO users (username, password, role, real_name, phone, station_id)
VALUES
('supervisor', '123456', 'supervisor', '督导组开发测试账号', '13800000000', NULL),
('kongdechen', '123456', 'supervisor', '孔德辰', '13800000000', NULL),
('yangquanyong', '123456', 'supervisor', '杨权涌', '13800000000', NULL);
