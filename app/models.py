from sqlalchemy import Column, Integer, String, Date, ForeignKey, UniqueConstraint, DateTime
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
    role = Column(String(32), nullable=False, default="admin") # admin, super_admin

class Office(Base):
    __tablename__ = "offices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, index=True, nullable=False)

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
    remark = Column(String(256), nullable=True)
    exit_date = Column(Date, nullable=True)
    exit_mode = Column(String(64), nullable=True) # Posted Out, Deceased, Retired, etc.
    role = Column(String(32), nullable=False, default="staff") # staff, office_admin, super_admin
    state = relationship("State")
    lga = relationship("LGA")
    leaves = relationship("Leave", back_populates="staff", cascade="all, delete-orphan")

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
