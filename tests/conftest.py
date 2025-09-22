import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ------------------------------
# Ensure project root on sys.path (keep your original logic)
# ------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import auth  # to override get_current_user in tests

# ------------------------------
# Import app and project components
# ------------------------------
from backend.app.main import app  # assumes app = FastAPI() is defined here
from backend.app.models import Base  # declarative base for creating/dropping tables
from backend.app.routers import device as device_router  # to override get_db used by this router

# ------------------------------
# Test database (SQLite file)
# ------------------------------
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_ci.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _reset_db():
    """
    Recreate all tables before each test, and drop after.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """
    Provide a dedicated DB session per test.
    """
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """
    TestClient with dependency overrides:
    - Override routers.device.get_db to use the testing session.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Apply overrides
    app.dependency_overrides[device_router.get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    # Cleanup overrides
    app.dependency_overrides.pop(device_router.get_db, None)


@pytest.fixture
def as_admin():
    """
    Override auth.get_current_user to act as an admin user.
    """

    class _User:
        id = 1
        username = "admin"
        role = "admin"

    def _override():
        return _User()

    app.dependency_overrides[auth.get_current_user] = _override
    yield
    app.dependency_overrides.pop(auth.get_current_user, None)


@pytest.fixture
def as_user():
    """
    Override auth.get_current_user to act as a normal user.
    """

    class _User:
        id = 2
        username = "user"
        role = "user"

    def _override():
        return _User()

    app.dependency_overrides[auth.get_current_user] = _override
    yield
    app.dependency_overrides.pop(auth.get_current_user, None)
