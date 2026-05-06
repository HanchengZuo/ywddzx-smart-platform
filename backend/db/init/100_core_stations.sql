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
    asset_type TEXT DEFAULT '全资' CHECK (asset_type IN ('全资', '股权')),    -- 资产类型，仅允许：全资 / 股权
    is_consolidated TEXT DEFAULT '否' CHECK (is_consolidated IN ('是', '否')), -- 是否并表，仅允许：是 / 否
    online_3_status TEXT DEFAULT '未上线'
        CHECK (online_3_status IN ('上线', '上线参股模式', '未上线')),         -- 是否上线3.0
    hos_station_code TEXT UNIQUE NOT NULL,                                    -- HOS加油站编码，站点主数据唯一标识，例如：PQ04
    landline_phone TEXT,                                                     -- 固定电话，例如：021-67220331
    status TEXT DEFAULT '营业中' CHECK (status IN ('营业中', '停业')),        -- 站点状态，仅允许：营业中 / 停业
    operating_hours TEXT DEFAULT '24小时',                                  -- 营运时间，例如：24小时 / 06:00-22:00
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,                         -- 创建时间
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP                          -- 更新时间
);
