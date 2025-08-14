"""
Database configuration and connection handling
"""

from sqlmodel import SQLModel, create_engine, Session

# Database URL - SQLite file in the current directory
DATABASE_URL = "sqlite:///./iot_dashboard.db"

# Create engine with echo=True for development (set to False for production)
engine = create_engine(DATABASE_URL, echo=True, connect_args={"check_same_thread": False})


def init_db():
    """Initialize database and create all tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session"""
    with Session(engine) as session:
        yield session
