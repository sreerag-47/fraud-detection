from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func

from database import Base


class DeviceLog(Base):
    __tablename__ = "device_logs"

    id = Column(Integer, primary_key=True, index=True)

    account_id = Column(Integer, ForeignKey("accounts.id"))

    device_id = Column(String, nullable=False)

    browser = Column(String, nullable=True)

    os = Column(String, nullable=True)

    ip_address = Column(String, nullable=False)

    first_seen = Column(DateTime(timezone=True), server_default=func.now())

    last_seen = Column(DateTime(timezone=True), server_default=func.now())