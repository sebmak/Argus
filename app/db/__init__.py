"""Database initialization and access layer"""
from .database import (
    init_db,
    get_db,
    get_all_persons,
    get_person_by_id,
    get_person_by_name,
    create_person,
    delete_person,
    add_face_sample,
    get_person_samples,
    get_all_active_embeddings,
    delete_face_sample,
    record_detection,
    get_unrecognized_detections,
    assign_detection_to_person,
    dismiss_detection,
    get_system_stats,
    get_user_by_username,
    create_user,
    verify_user_credentials
)
from .migrations import (
    run_migrations,
    rollback_migrations,
    get_migration_status
)
