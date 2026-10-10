export interface User {
  id: string;
  username: string;
}

export interface FaceSample {
  id: string;
  person_id: string;
  thumbnail_path: string;
  source: string;
  camera_id?: string;
  created_at: string;
}

export interface Person {
  id: string;
  name: string;
  notes?: string;
  is_household?: boolean;
  sample_count: number;
  primary_thumbnail?: string;
  created_at: string;
  updated_at: string;
  samples?: FaceSample[];
}

export interface Detection {
  id: string;
  thumbnail_path: string;
  thumbnail_url?: string;
  camera_id: string;
  timestamp: string | number;
  confidence: number;
  similarity?: number;
  matched_person_id?: string;
  matched_name?: string;
  is_household?: boolean | null;
  status: 'matched' | 'unrecognized' | 'dismissed';
  bbox?: number[];
}

export interface RecentActivity {
  id: string;
  thumbnail_path: string;
  thumbnail_url?: string;
  camera_id: string;
  matched_name?: string;
  is_household?: boolean;
  status: string;
  similarity?: number;
  timestamp: string;
}

export interface SystemStats {
  total_persons: number;
  household_count?: number;
  visitor_count?: number;
  total_samples: number;
  unrecognized_count: number;
  accuracy_rate: number;
  recent_activity: RecentActivity[];
}

export interface SystemSettings {
  detection_confidence: number;
  similarity_threshold: number;
  notification_threshold: number;
  notify_on_unknown: boolean;
  unknown_min_confidence: number;
  det_size: number;
  ort_num_threads: number;
  max_samples_per_person: number;
  unrecognized_track_window_seconds?: number;
  rtsp_enabled: boolean;
  rtsp_url: string;
  rtsp_camera_name: string;
  rtsp_fps: number;
  rtsp_cooldown_seconds: number;
  rtsp_webhook_url: string;
  webhook_only_known_faces: boolean;
  mqtt_enabled: boolean;
  mqtt_host: string;
  mqtt_port: number;
  mqtt_topic: string;
  mqtt_user?: string;
  mqtt_password?: string;
  mqtt_only_known_faces?: boolean;
}

export interface MqttStatus {
  enabled: boolean;
  host: string;
  port: number;
  topic: string;
  user?: string;
  connected: boolean;
  last_error?: string | null;
  only_known_faces?: boolean;
}

export interface RtspStatus {
  is_running: boolean;
  is_connected: boolean;
  url: string;
  camera_name: string;
  target_fps: number;
  actual_fps?: number;
  fps_actual?: number;
  last_error?: string | null;
  active_cooldowns?: Record<string, number>;
  last_detection?: {
    person_name: string;
    match: boolean;
    is_household?: boolean;
    similarity: number;
    timestamp: number;
    thumbnail_url?: string;
  } | null;
  webhook_url?: string;
  webhook_only_known_faces?: boolean;
  mqtt_only_known_faces?: boolean;
  mqtt?: MqttStatus;
}

export interface MigrationStep {
  migration_id: number;
  version_tag: string;
  name: string;
  description: string;
  applied_at?: string;
  status?: string;
}

export interface MigrationStatus {
  status: string;
  current_app_version: string;
  target_app_version: string;
  applied_count: number;
  applied_migrations: MigrationStep[];
  pending_count: number;
  pending_migrations: MigrationStep[];
  backups_count: number;
}

export interface FaceBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width: number;
  height: number;
}

export interface SandboxFace {
  bbox: FaceBox | [number, number, number, number];
  detection_confidence: number;
  name: string;
  similarity: number;
  distance: number;
  match: boolean;
  is_household?: boolean;
  thumbnail_url?: string;
  sample_count?: number;
  person_id?: string | null;
  detection_id?: string | null;
}

export interface SandboxResult {
  count: number;
  latency_ms: number;
  faces: SandboxFace[];
  unrecognized_count?: number;
}
