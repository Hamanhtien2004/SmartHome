#!/usr/bin/env python3
"""
Supabase IoT Integration Client for Smart Home System
---------------------------------------------------
Author: Autonomous IoT & Automation Engineer
Description:
  - Synchronizes access logs (Facial recognition matches).
  - Uploads intruder and visitor snapshots to Supabase Storage.
  - Logs security alarms and sensor metrics in real-time.
"""

import os
import io
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any

# Setup Logging
logger = logging.getLogger("SmartHomeSupabase")

# Supabase Credentials
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project-id.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "your-supabase-service-role-or-anon-key")
STORAGE_BUCKET = os.getenv("SUPABASE_BUCKET_NAME", "security-snapshots")

# Optional Supabase import with fallback
try:
    from supabase import create_client, Client
    if not SUPABASE_URL.startswith("https://your-"):
        supabase_client: Optional[Client] = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    else:
        supabase_client = None
        logger.warning("Supabase URL is placeholder. Database sync is in mock/dry-run mode.")
except Exception as e:
    supabase_client = None
    logger.warning("Supabase library not ready or init error: %s. Running in offline mode.", e)

def upload_snapshot(image_bytes: bytes, filename: str) -> Optional[str]:
    """Uploads an image to Supabase Storage and returns its public URL."""
    if not supabase_client or not image_bytes:
        return None

    try:
        file_path = f"snapshots/{datetime.utcnow().strftime('%Y%m%d')}/{filename}"
        res = supabase_client.storage.from_(STORAGE_BUCKET).upload(
            path=file_path,
            file=image_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        # Get public URL
        public_url = supabase_client.storage.from_(STORAGE_BUCKET).get_public_url(file_path)
        logger.info("Snapshot uploaded to Supabase Storage: %s", public_url)
        return public_url
    except Exception as exc:
        logger.error("Failed to upload snapshot to Supabase: %s", exc)
        return None

def log_access_event(
    location: str,
    person_name: str,
    access_granted: bool,
    confidence_score: float = 0.0,
    auth_method: str = "face_recognition",
    image_bytes: Optional[bytes] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Logs an entry event (Family member or stranger) into Supabase."""
    snapshot_url = None
    if image_bytes:
        safe_name = person_name.replace(" ", "_").lower()
        filename = f"{int(time.time())}_{safe_name}.jpg"
        snapshot_url = upload_snapshot(image_bytes, filename)

    record = {
        "location": location,
        "person_name": person_name,
        "access_granted": access_granted,
        "confidence_score": round(confidence_score, 2),
        "auth_method": auth_method,
        "snapshot_url": snapshot_url,
        "notes": notes,
        "timestamp": datetime.utcnow().isoformat()
    }

    if supabase_client:
        try:
            resp = supabase_client.table("access_logs").insert(record).execute()
            logger.info("Access log saved to Supabase (User: %s, Granted: %s)", person_name, access_granted)
            return resp.data
        except Exception as exc:
            logger.error("Error inserting access log into Supabase: %s", exc)

    logger.debug("[DRY-RUN] Access log record: %s", record)
    return record

def log_security_alert(
    alert_type: str,
    location: str,
    severity: str = "HIGH",
    details: Optional[Dict[str, Any]] = None,
    image_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    """Logs a security intruder or unauthorized movement alert into Supabase."""
    snapshot_url = None
    if image_bytes:
        filename = f"alert_{int(time.time())}_{alert_type}.jpg"
        snapshot_url = upload_snapshot(image_bytes, filename)

    record = {
        "alert_type": alert_type,
        "location": location,
        "severity": severity,
        "details": details or {},
        "snapshot_url": snapshot_url,
        "resolved": False,
        "timestamp": datetime.utcnow().isoformat()
    }

    if supabase_client:
        try:
            resp = supabase_client.table("security_alerts").insert(record).execute()
            logger.info("Security alert saved to Supabase: %s at %s", alert_type, location)
            return resp.data
        except Exception as exc:
            logger.error("Error inserting security alert into Supabase: %s", exc)

    logger.debug("[DRY-RUN] Security alert record: %s", record)
    return record

def log_sensor_telemetry(
    device_id: str,
    temperature: Optional[float] = None,
    humidity: Optional[float] = None,
    radar_presence: bool = False,
    radar_distance: Optional[float] = None
) -> None:
    """Logs temperature, humidity and mmWave radar metrics to Supabase."""
    record = {
        "device_id": device_id,
        "temperature": temperature,
        "humidity": humidity,
        "radar_has_target": radar_presence,
        "radar_target_distance": radar_distance,
        "timestamp": datetime.utcnow().isoformat()
    }

    if supabase_client:
        try:
            supabase_client.table("sensor_telemetry").insert(record).execute()
        except Exception as exc:
            logger.error("Failed to insert telemetry to Supabase: %s", exc)

def get_authorized_family_members():
    """Fetch active family members and their allowed rooms from Supabase."""
    if not supabase_client:
        # Default local fallback
        return [
            {"name": "Admin", "face_id": "admin_face_01", "allowed_rooms": ["front_door", "bedroom"]},
            {"name": "Member", "face_id": "member_face_02", "allowed_rooms": ["front_door"]}
        ]
    try:
        resp = supabase_client.table("family_members").select("*").eq("is_active", True).execute()
        return resp.data
    except Exception as exc:
        logger.error("Error fetching family members from Supabase: %s", exc)
        return []
