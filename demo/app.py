from sqlalchemy import create_engine
from sqlalchemy.orm import Session

engine = create_engine("sqlite:///app.db")
session = Session(engine)
rows = session.query(User).filter_by(active=True).all()
result = engine.execute("SELECT 1")