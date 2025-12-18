from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from config import get_config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get configuration
config = get_config()

# Database configuration - use centralized config
if not config.DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# Create engine with connection pooling using config values
engine = create_engine(
    config.DATABASE_URL,
    pool_pre_ping=config.SQLALCHEMY_ENGINE_OPTIONS.get('pool_pre_ping', True),
    pool_recycle=config.SQLALCHEMY_ENGINE_OPTIONS.get('pool_recycle', 300),
    pool_size=10,
    max_overflow=20,
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables with retry logic for transient SSL errors"""
    import time
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            logger.info("Creating database tables...")
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully")
            return
        except Exception as e:
            if attempt < max_retries - 1 and "SSL" in str(e):
                logger.warning(f"Database connection attempt {attempt + 1} failed (SSL error), retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Failed to create database tables: {e}")
                raise

def get_db():
    """Get database session (for Flask dependency injection)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session():
    """
    Context manager for database sessions with automatic cleanup.
    
    Usage:
        with db_session() as db:
            db.query(Model).all()
            db.commit()  # Explicit commit when needed
    
    Automatically rolls back on exception and closes session.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error, rolled back: {e}")
        raise
    finally:
        db.close()

def init_database():
    """Initialize database with tables"""
    create_tables()
    logger.info("Database initialized successfully")

if __name__ == "__main__":
    init_database()