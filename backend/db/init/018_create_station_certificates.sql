-- station_certificates 表：站点证照有效期台账
-- 用途：
-- 1. 保存各站点已录入的证照有效期信息
-- 2. 支持一个站点只维护实际拥有的部分证照
-- 3. 支持督导查看全部站点、站点账号查看本站点

CREATE TABLE IF NOT EXISTS station_certificates (
    id SERIAL PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    certificate_type TEXT NOT NULL,
    certificate_name TEXT NOT NULL,
    start_date DATE,
    expiry_date DATE NOT NULL,
    remark TEXT,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (station_id, certificate_type)
);

CREATE INDEX IF NOT EXISTS idx_station_certificates_expiry_date
ON station_certificates (expiry_date);
