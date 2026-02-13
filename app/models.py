from sqlalchemy import Column, Integer, String, Date, ForeignKey, UniqueConstraint, DateTime, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    target = Column(String(256), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    details = Column(String(512), nullable=True)
    formation_id = Column(Integer, ForeignKey("formations.id"), nullable=True)
    office_id = Column(Integer, ForeignKey("offices.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(64), nullable=True)

class Formation(Base):
    __tablename__ = "formations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, index=True, nullable=False)
    code = Column(String(32), unique=True, index=True, nullable=False) # e.g. 'NIS'
    formation_type = Column(String(32), nullable=True) # Directorate, Zonal Command, State Command
    parent_id = Column(Integer, ForeignKey("formations.id"), nullable=True)
    parent = relationship("Formation", remote_side=[id], backref="children")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    users = relationship("User", back_populates="formation")
    offices = relationship("Office", back_populates="formation")
    staff = relationship("Staff", back_populates="formation")

class State(Base):
    __tablename__ = "states"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, index=True, nullable=False)
    lgas = relationship("LGA", back_populates="state", cascade="all, delete-orphan")

class LGA(Base):
    __tablename__ = "lgas"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True)
    state = relationship("State", back_populates="lgas")
    __table_args__ = (UniqueConstraint("state_id", "name", name="uq_lga_state_name"),)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="admin") # admin, special_admin
    formation_id = Column(Integer, ForeignKey("formations.id"), nullable=True)
    formation = relationship("Formation", back_populates="users")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(String(512), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean, default=False)
    
    # Target can be a User (Special/Formation Admin) or Staff (Office/Main Admin)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    
    user = relationship("User")
    staff = relationship("Staff")

class Office(Base):
    __tablename__ = "offices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), index=True, nullable=False)
    formation_id = Column(Integer, ForeignKey("formations.id"), nullable=True)
    formation = relationship("Formation", back_populates="offices")
    
    office_type = Column(String(32), nullable=True)
    parent_id = Column(Integer, ForeignKey("offices.id"), nullable=True)
    parent = relationship("Office", remote_side=[id], backref="children")

    __table_args__ = (UniqueConstraint("formation_id", "name", name="uq_office_formation_name"),)


class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, index=True)
    nis_no = Column(String(64), unique=True, index=True, nullable=False)
    surname = Column(String(128), nullable=False, index=True)
    other_names = Column(String(128), nullable=False)
    rank = Column(String(64), nullable=False, index=True)
    gender = Column(String(16), nullable=True, index=True)
    dofa = Column(Date, nullable=True)
    dopa = Column(Date, nullable=True)
    dopp = Column(Date, nullable=True)
    dob = Column(Date, nullable=True)
    state_id = Column(Integer, ForeignKey("states.id", ondelete="SET NULL"), nullable=True, index=True)
    lga_id = Column(Integer, ForeignKey("lgas.id", ondelete="SET NULL"), nullable=True, index=True)
    home_town = Column(String(128), nullable=True)
    qualification = Column(String(64), nullable=True, index=True)
    phone_no = Column(String(32), nullable=True, index=True)
    next_of_kin = Column(String(128), nullable=True)
    nok_phone = Column(String(32), nullable=True)
    office = Column(String(64), nullable=True, index=True)
    email = Column(String(128), nullable=True, index=True)
    remark = Column(String(256), nullable=True)
    exit_date = Column(Date, nullable=True)
    exit_mode = Column(String(64), nullable=True) # Posted Out, Deceased, Retired, etc.
    
    # Out Request Fields
    out_request_status = Column(String(32), nullable=True, default=None) # Pending, Approved, Rejected
    out_request_date = Column(Date, nullable=True)
    out_request_reason = Column(String(64), nullable=True)

    password_hash = Column(String(128), nullable=True) # For custom passwords
    role = Column(String(32), nullable=False, default="staff") # staff, office_admin, main_admin
    login_count = Column(Integer, default=0, nullable=False)
    allow_login = Column(Integer, default=1, nullable=False)
    allow_edit_rank = Column(Integer, default=0, nullable=False)
    allow_edit_dopp = Column(Integer, default=0, nullable=False)
    state = relationship("State")
    lga = relationship("LGA")
    leaves = relationship("Leave", back_populates="staff", cascade="all, delete-orphan")
    posting_history = relationship("PostingHistory", back_populates="staff", cascade="all, delete-orphan")
    formation_id = Column(Integer, ForeignKey("formations.id"), nullable=True)
    formation = relationship("Formation", back_populates="staff")
    formation_dopp = Column(Date, nullable=True)
    custom_data = Column(Text, nullable=True) # JSON string for custom fields

class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), unique=True, nullable=False) # key, e.g. "blood_group"
    label = Column(String(128), nullable=False) # Label, e.g. "Blood Group"
    field_type = Column(String(32), nullable=False, default="text") # text, date, number
    is_active = Column(Boolean, default=True)

class Leave(Base):
    __tablename__ = "leaves"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    leave_type = Column(String(64), nullable=False)
    reason = Column(String(256), nullable=True)
    status = Column(String(32), nullable=False, default="Pending", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    staff = relationship("Staff", back_populates="leaves")


class PostingHistory(Base):
    __tablename__ = "posting_history"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type = Column(String(32), nullable=False)  # MOVE, EXIT, RETURN, POSTED_OUT
    from_office = Column(String(128), nullable=True)
    to_office = Column(String(128), nullable=True)
    action_date = Column(Date, nullable=False)
    remarks = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    staff = relationship("Staff", back_populates="posting_history")


class StaffEditRequest(Base):
    __tablename__ = "staff_edit_requests"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="CASCADE"), nullable=False, index=True)
    data = Column(String(4096), nullable=False) # JSON string of changes
    status = Column(String(32), nullable=False, default="pending", index=True) # pending, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String(64), nullable=True) # Username of reviewer
    
    staff = relationship("Staff")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    message = Column(String(512), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean, default=False)
    
    # Target can be a User (Special/Formation Admin) or Staff (Office/Main Admin)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    
    # Deprecated fields (kept for migration safety if needed, but we prefer new fields)
    formation_id = Column(Integer, ForeignKey("formations.id"), nullable=True) 
    office_name = Column(String(128), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now()) # Alias for timestamp if code uses it
    
    user = relationship("User")
    staff = relationship("Staff")
