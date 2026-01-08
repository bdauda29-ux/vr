from app.database import engine
from sqlalchemy import inspect

insp = inspect(engine)
print("Tables:", insp.get_table_names())
