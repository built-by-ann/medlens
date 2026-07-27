from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class AnalysisInconsistency(Base):
    """A possible inconsistency as observed by the AI summary service.

    This is an unstructured AI observation, not a deterministic finding. It
    has no severity, no discrepancy type, and no link to a Medication or
    MedicationMention. Structured, deterministic findings are represented by
    MedicationDiscrepancy, produced by the reconciliation engine, not here.
    """

    __tablename__ = "analysis_inconsistencies"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)

    description = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    analysis = relationship("Analysis", back_populates="possible_inconsistencies")
