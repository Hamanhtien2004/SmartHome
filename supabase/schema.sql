-- ==============================================================================
-- SMART HOME & FACIAL RECOGNITION DATABASE SCHEMA (SUPABASE / POSTGRESQL)
-- ==============================================================================

-- 1. Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==============================================================================
-- TABLE: family_members (Danh sách thành viên gia đình & Cấu hình cá nhân)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.family_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    role VARCHAR(30) NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'guest')),
    face_id VARCHAR(100) UNIQUE, -- ID liên kết với CompreFace / Double-Take
    phone_number VARCHAR(20),
    email VARCHAR(100),
    avatar_url TEXT,
    allowed_rooms TEXT[] DEFAULT ARRAY['front_door', 'living_room', 'bedroom'],
    preferred_temp NUMERIC(4, 1) DEFAULT 25.0,     -- Nhiệt độ điều hòa yêu thích (°C)
    preferred_light_level INT DEFAULT 80,          -- Độ sáng đèn yêu thích (%)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- ==============================================================================
-- TABLE: devices (Danh sách thiết bị phần cứng trong nhà)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.devices (
    id VARCHAR(50) PRIMARY KEY, -- vd: esp32_livingroom_relay, esp32_cam_doorbell
    device_name VARCHAR(100) NOT NULL,
    device_type VARCHAR(50) NOT NULL CHECK (device_type IN ('relay', 'sensor', 'camera', 'lock', 'radar', 'hub')),
    location VARCHAR(50) NOT NULL CHECK (location IN ('front_door', 'living_room', 'bedroom', 'kitchen', 'outdoor')),
    ip_address INET,
    mac_address MACADDR,
    firmware_version VARCHAR(30),
    is_online BOOLEAN DEFAULT TRUE,
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- ==============================================================================
-- TABLE: access_logs (Nhật ký ra vào cửa chính và các phòng)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.access_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    location VARCHAR(50) NOT NULL, -- 'front_door', 'bedroom_door', etc.
    person_name VARCHAR(100) DEFAULT 'Unknown',
    family_member_id UUID REFERENCES public.family_members(id) ON DELETE SET NULL,
    access_granted BOOLEAN NOT NULL DEFAULT FALSE,
    confidence_score NUMERIC(5, 2), -- Tỉ lệ nhận diện khuôn mặt (%) vd: 92.45
    auth_method VARCHAR(30) NOT NULL DEFAULT 'face_recognition' 
        CHECK (auth_method IN ('face_recognition', 'pin_code', 'rfid_tag', 'remote_app', 'manual_switch')),
    snapshot_url TEXT, -- Link ảnh lưu trữ trên Supabase Storage
    notes TEXT
);

-- ==============================================================================
-- TABLE: security_alerts (Cảnh báo an ninh, đột nhập & người lạ)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.security_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    alert_type VARCHAR(50) NOT NULL 
        CHECK (alert_type IN ('stranger_detected', 'unauthorized_movement', 'door_forced_open', 'anti_spoof_trigger', 'tamper')),
    severity VARCHAR(20) NOT NULL DEFAULT 'HIGH' CHECK (severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    source_device_id VARCHAR(50) REFERENCES public.devices(id) ON DELETE SET NULL,
    location VARCHAR(50) NOT NULL,
    snapshot_url TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolved_by VARCHAR(100)
);

-- ==============================================================================
-- TABLE: sensor_telemetry (Lưu trữ chỉ số môi trường & Radar mmWave theo thời gian)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS public.sensor_telemetry (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    device_id VARCHAR(50) REFERENCES public.devices(id) ON DELETE CASCADE,
    temperature NUMERIC(4, 2), -- °C
    humidity NUMERIC(4, 2),    -- %
    radar_has_target BOOLEAN DEFAULT FALSE,
    radar_has_moving BOOLEAN DEFAULT FALSE,
    radar_target_distance NUMERIC(6, 2), -- cm
    radar_energy INT
);

-- ==============================================================================
-- INDEXES FOR FAST QUERYING
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON public.access_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_access_logs_location ON public.access_logs (location);
CREATE INDEX IF NOT EXISTS idx_security_alerts_timestamp ON public.security_alerts (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_telemetry_timestamp ON public.sensor_telemetry (timestamp DESC);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
ALTER TABLE public.family_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.devices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.access_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.security_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sensor_telemetry ENABLE ROW LEVEL SECURITY;

-- Allow read access for authenticated users
CREATE POLICY "Allow read access for authenticated users" 
ON public.family_members FOR SELECT USING (auth.role() = 'authenticated' OR auth.role() = 'anon');

CREATE POLICY "Allow read access for devices" 
ON public.devices FOR SELECT USING (true);

CREATE POLICY "Allow read access for access_logs" 
ON public.access_logs FOR SELECT USING (true);

CREATE POLICY "Allow read access for security_alerts" 
ON public.security_alerts FOR SELECT USING (true);

-- Allow service role (Backend IoT Bot) full read/write
CREATE POLICY "Service role full access on access_logs" 
ON public.access_logs FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access on security_alerts" 
ON public.security_alerts FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access on sensor_telemetry" 
ON public.sensor_telemetry FOR ALL USING (true) WITH CHECK (true);

-- ==============================================================================
-- SAMPLE INITIAL DATA
-- ==============================================================================
INSERT INTO public.devices (id, device_name, device_type, location) VALUES
('esp32_cam_doorbell', 'Chuông cửa AI Camera', 'camera', 'front_door'),
('esp32_livingroom_relay', 'Rơ-le Phòng khách & Khóa từ', 'relay', 'living_room'),
('esp32_bedroom_sensor', 'Cảm biến Nhiệt ẩm & Radar mmWave', 'sensor', 'bedroom')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.family_members (name, role, face_id, allowed_rooms, preferred_temp) VALUES
('Chủ hộ (Admin)', 'owner', 'admin_face_01', ARRAY['front_door', 'living_room', 'bedroom'], 24.5),
('Thành viên gia đình', 'member', 'member_face_02', ARRAY['front_door', 'living_room'], 26.0)
ON CONFLICT (face_id) DO NOTHING;

-- ==============================================================================
-- STORAGE BUCKET CONFIGURATION (Run in Supabase Dashboard if not automated)
-- Bucket name: 'security-snapshots' (Public or Authenticated)
-- ==============================================================================
INSERT INTO storage.buckets (id, name, public) 
VALUES ('security-snapshots', 'security-snapshots', true)
ON CONFLICT (id) DO NOTHING;
