-- user_inspection_table_scopes 表：用户可查看的检查表数据范围
-- 用途：
-- 1. 支持质安部、发展计划部等账号按检查表限制巡检问题、巡检记录和巡检计划数据
-- 2. 每个页面单独保存范围，不再一套检查表范围同时限制所有页面
-- 3. 也可由 root 在用户数据管理页面给任意非 root 用户配置检查表范围

CREATE TABLE user_inspection_table_scopes (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope_key TEXT NOT NULL,                                           -- 范围类型：问题列表 / 巡检记录 / 巡检计划
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE CASCADE,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, scope_key, inspection_table_id)
);

-- role_inspection_table_scopes 表：角色通用检查表数据范围
-- 用途：
-- 1. 支持在用户数据管理的“角色通用权限”里统一配置角色默认检查表范围
-- 2. 用户个性化范围优先，未配置个性化范围时才继承角色通用范围
-- 3. 每个页面单独保存范围，避免问题、记录、计划互相串联

CREATE TABLE role_inspection_table_scopes (
    role TEXT NOT NULL,
    scope_key TEXT NOT NULL,                                           -- 范围类型：问题列表 / 巡检记录 / 巡检计划
    inspection_table_id INTEGER NOT NULL REFERENCES inspection_tables(id) ON DELETE CASCADE,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role, scope_key, inspection_table_id)
);

-- user_station_region_scopes 表：用户可查看的站点片区/归属地数据范围
-- 用途：
-- 1. 支持片区账号按 stations.region 限制巡检问题、巡检记录和巡检计划数据
-- 2. 每个页面单独保存范围，避免一个片区范围同时强制限制所有页面
-- 3. 也可由 root 在用户数据管理页面给任意非 root 用户配置片区范围

CREATE TABLE user_station_region_scopes (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scope_key TEXT NOT NULL,                                           -- 范围类型：问题列表 / 巡检记录 / 巡检计划
    station_region TEXT NOT NULL,                                      -- stations.region；空值统一按“未填写片区”处理
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, scope_key, station_region)
);

-- role_station_region_scopes 表：角色通用站点片区/归属地数据范围
-- 用途：
-- 1. 支持在用户数据管理的“角色通用权限”里统一配置角色默认片区范围
-- 2. 用户个性化范围优先，未配置个性化范围时才继承角色通用范围
-- 3. 每个页面单独保存范围，避免问题、记录、计划互相串联

CREATE TABLE role_station_region_scopes (
    role TEXT NOT NULL,
    scope_key TEXT NOT NULL,                                           -- 范围类型：问题列表 / 巡检记录 / 巡检计划
    station_region TEXT NOT NULL,                                      -- stations.region；空值统一按“未填写片区”处理
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role, scope_key, station_region)
);
