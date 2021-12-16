from sqlalchemy.orm import declarative_base

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Boolean
)

valorant_scrapy_base = declarative_base()

class Matches(valorant_scrapy_base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer)
    url = Column(String)
    timestamp = Column(DateTime)
    stakes = Column(String)
    event = Column(String)
    map_stats = Column(Boolean)
    player_stats = Column(Boolean)
    page = Column(Integer)
