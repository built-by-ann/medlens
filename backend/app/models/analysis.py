from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    summary = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="processing")
    processing_time_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="analyses")
    medication_discrepancies = relationship(
        "MedicationDiscrepancy",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )