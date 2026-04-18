-- stations 表：站点主数据表
-- 用途：
-- 1. 保存站点基础信息
-- 2. 供巡检系统、考核系统、培训系统统一复用
-- 3. 支持地址、地图坐标、资产类型、站点类型等扩展信息

CREATE TABLE stations (
    id SERIAL PRIMARY KEY,                                                  -- 站点ID，主键，自增
    station_name TEXT UNIQUE NOT NULL,                                      -- 站点名称，唯一
    region TEXT,                                                            -- 所属片区/归属地，例如：宝静片区、闵普徐片区
    address TEXT,                                                           -- 站点地址
    longitude NUMERIC(10, 6),                                               -- 经度
    latitude NUMERIC(10, 6),                                                -- 纬度
    station_manager_name TEXT,                                              -- 站点负责人姓名
    station_manager_phone TEXT,                                             -- 站点负责人手机号
    station_type TEXT NOT NULL CHECK (station_type IN ('加油站', '充电站')),  -- 站点类型，仅允许：加油站 / 充电站
    asset_type TEXT,                                                        -- 资产类型，例如：全资 / 控股 / 参股
    status TEXT DEFAULT '营业中',                                            -- 站点状态，例如：营业中 / 停业 / 改造中
    operating_hours TEXT DEFAULT '24小时',                                  -- 营运时间，例如：24小时 / 06:00-22:00
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                         -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP                          -- 更新时间
);