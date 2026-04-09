

-- 初始化测试账号
-- 说明：
-- 1. 督导组账号不绑定站点
-- 2. 站点账号通过 station_id 关联站点
-- 3. 当前阶段密码先使用明文，后续再改为哈希密码

INSERT INTO users (username, password, role, real_name, phone, station_id)
VALUES
('supervisor1', '123456', 'supervisor', '督导组测试账号', '13800000000', NULL),
('manager_hh', '123456', 'station_manager', '曹红', '13802663088', (SELECT id FROM stations WHERE station_name = '华辉加油站')),
('manager_bydy', '123456', 'station_manager', '柳洪慧', '15802113010', (SELECT id FROM stations WHERE station_name = '宝杨第一加油站')),
('manager_cdl', '123456', 'station_manager', '张猛', '13817024103', (SELECT id FROM stations WHERE station_name = '常德路加油站'));