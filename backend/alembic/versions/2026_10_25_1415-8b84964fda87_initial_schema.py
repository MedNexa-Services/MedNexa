from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8b84964fda87"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hospital",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("opening_time", sa.Time(), nullable=False),
        sa.Column("closing_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Kolkata", nullable=False),
        sa.Column(
            "languages",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text('\'["en", "hi"]\''),
            nullable=False,
        ),
        sa.Column("general_instructions", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hospital")),
    )
    op.create_table(
        "call_session",
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column("caller_phone", sa.String(length=20), nullable=False),
        sa.Column(
            "call_start",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("call_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language_detected", sa.String(length=10), nullable=True),
        sa.Column(
            "call_outcome",
            sa.Enum(
                "BOOKED",
                "CANCELLED",
                "RESCHEDULED",
                "INFO_PROVIDED",
                "ESCALATED",
                "ABANDONED",
                "OTHER",
                name="call_outcome",
            ),
            nullable=True,
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "escalated_to_human", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("total_turns", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id"],
            ["hospital.id"],
            name=op.f("fk_call_session_hospital_id_hospital"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_call_session")),
    )
    op.create_index(
        op.f("ix_call_session_caller_phone"), "call_session", ["caller_phone"], unique=False
    )
    op.create_index(
        op.f("ix_call_session_hospital_id"), "call_session", ["hospital_id"], unique=False
    )
    op.create_table(
        "doctor",
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("speciality", sa.String(length=100), nullable=False),
        sa.Column("qualification", sa.String(length=200), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("max_daily_appointments", sa.Integer(), nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("available_days", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("slot_start_time", sa.Time(), nullable=False),
        sa.Column("slot_end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("max_daily_appointments > 0", name=op.f("ck_doctor_max_daily_positive")),
        sa.CheckConstraint(
            "slot_duration_minutes > 0", name=op.f("ck_doctor_slot_duration_positive")
        ),
        sa.CheckConstraint(
            "slot_end_time > slot_start_time", name=op.f("ck_doctor_slot_window_valid")
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"],
            ["hospital.id"],
            name=op.f("fk_doctor_hospital_id_hospital"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_doctor")),
    )
    op.create_index(
        "ix_doctor_hospital_speciality", "doctor", ["hospital_id", "speciality"], unique=False
    )
    op.create_table(
        "hospital_info",
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"],
            ["hospital.id"],
            name=op.f("fk_hospital_info_hospital_id_hospital"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hospital_info")),
    )
    op.create_index(
        op.f("ix_hospital_info_hospital_id"), "hospital_info", ["hospital_id"], unique=False
    )
    op.create_table(
        "patient",
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.Enum("MALE", "FEMALE", "OTHER", name="gender"), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "age IS NULL OR (age >= 0 AND age <= 150)", name=op.f("ck_patient_age_range")
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"],
            ["hospital.id"],
            name=op.f("fk_patient_hospital_id_hospital"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patient")),
        sa.UniqueConstraint(
            "hospital_id",
            "phone",
            "normalized_name",
            name=op.f("uq_patient_hospital_id_phone_normalized_name"),
        ),
    )
    op.create_index(op.f("ix_patient_phone"), "patient", ["phone"], unique=False)
    op.create_table(
        "appointment",
        sa.Column("patient_id", sa.Uuid(), nullable=False),
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("hospital_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("appointment_time", sa.Time(), nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "BOOKED",
                "CANCELLED",
                "COMPLETED",
                "NO_SHOW",
                "RESCHEDULED",
                name="appointment_status",
            ),
            server_default="BOOKED",
            nullable=False,
        ),
        sa.Column(
            "booking_source",
            sa.Enum("AI_CALL", "DASHBOARD", "WALK_IN", name="booking_source"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("token_number", sa.Integer(), nullable=False),
        sa.Column("rescheduled_from_id", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctor.id"],
            name=op.f("fk_appointment_doctor_id_doctor"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hospital_id"],
            ["hospital.id"],
            name=op.f("fk_appointment_hospital_id_hospital"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patient.id"],
            name=op.f("fk_appointment_patient_id_patient"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rescheduled_from_id"],
            ["appointment.id"],
            name=op.f("fk_appointment_rescheduled_from_id_appointment"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointment")),
        sa.UniqueConstraint(
            "doctor_id",
            "appointment_date",
            "token_number",
            name=op.f("uq_appointment_doctor_id_appointment_date_token_number"),
        ),
    )
    op.create_index(
        "ix_appointment_doctor_date", "appointment", ["doctor_id", "appointment_date"], unique=False
    )
    op.create_index(
        "ix_appointment_hospital_date",
        "appointment",
        ["hospital_id", "appointment_date"],
        unique=False,
    )
    op.create_index(op.f("ix_appointment_patient_id"), "appointment", ["patient_id"], unique=False)
    op.create_index(
        "uq_appointment_doctor_slot_booked",
        "appointment",
        ["doctor_id", "appointment_date", "appointment_time"],
        unique=True,
        postgresql_where=sa.text("status = 'BOOKED'"),
    )
    op.create_table(
        "schedule",
        sa.Column("doctor_id", sa.Uuid(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("override_reason", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "start_time IS NULL OR end_time IS NULL OR end_time > start_time",
            name=op.f("ck_schedule_window_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctor.id"],
            name=op.f("fk_schedule_doctor_id_doctor"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_schedule")),
        sa.UniqueConstraint("doctor_id", "date", name=op.f("uq_schedule_doctor_id_date")),
    )
    op.create_table(
        "call_log",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=True),
        sa.Column(
            "role", sa.Enum("USER", "ASSISTANT", "TOOL", "SYSTEM", name="call_role"), nullable=False
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_called", sa.String(length=100), nullable=True),
        sa.Column("tool_result", sa.Text(), nullable=True),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointment.id"],
            name=op.f("fk_call_log_appointment_id_appointment"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["call_session.id"],
            name=op.f("fk_call_log_session_id_call_session"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_call_log")),
    )
    op.create_index(op.f("ix_call_log_session_id"), "call_log", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_call_log_session_id"), table_name="call_log")
    op.drop_table("call_log")
    op.drop_table("schedule")
    op.drop_index(
        "uq_appointment_doctor_slot_booked",
        table_name="appointment",
        postgresql_where=sa.text("status = 'BOOKED'"),
    )
    op.drop_index(op.f("ix_appointment_patient_id"), table_name="appointment")
    op.drop_index("ix_appointment_hospital_date", table_name="appointment")
    op.drop_index("ix_appointment_doctor_date", table_name="appointment")
    op.drop_table("appointment")
    op.drop_index(op.f("ix_patient_phone"), table_name="patient")
    op.drop_table("patient")
    op.drop_index(op.f("ix_hospital_info_hospital_id"), table_name="hospital_info")
    op.drop_table("hospital_info")
    op.drop_index("ix_doctor_hospital_speciality", table_name="doctor")
    op.drop_table("doctor")
    op.drop_index(op.f("ix_call_session_hospital_id"), table_name="call_session")
    op.drop_index(op.f("ix_call_session_caller_phone"), table_name="call_session")
    op.drop_table("call_session")
    op.drop_table("hospital")
    for enum_name in (
        "call_role",
        "booking_source",
        "appointment_status",
        "gender",
        "call_outcome",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
