"""
Test Configuration and Fixtures

Shared fixtures for ARCHON PRIME API tests.
Provides isolated database, authenticated clients, and mock services.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from archon_prime.api.main import create_app
from archon_prime.api.config import settings
from archon_prime.api.db.models import Base, User, MT5Profile, Position
from archon_prime.api.db.session import get_db
from archon_prime.api.auth.jwt import create_access_token
from archon_prime.api.auth.service import AuthService


# ==================== Database Fixtures ====================


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async SQLite engine for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for tests."""
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


# ==================== Application Fixtures ====================


@pytest.fixture(scope="function")
def app(db_session) -> FastAPI:
    """Create FastAPI app with test database."""
    test_app = create_app()

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture(scope="function")
def client(app) -> TestClient:
    """Create synchronous test client."""
    return TestClient(app)


@pytest_asyncio.fixture(scope="function")
async def async_client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ==================== User Fixtures ====================


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session) -> User:
    """Create a test user."""
    from passlib.hash import bcrypt

    user = User(
        id=uuid.uuid4(),
        email="test@archon.ai",
        password_hash=bcrypt.hash("TestPassword123!"),
        first_name="Test",
        last_name="User",
        subscription_tier="pro",
        is_active=True,
        is_admin=False,
        email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def admin_user(db_session) -> User:
    """Create an admin user."""
    from passlib.hash import bcrypt

    user = User(
        id=uuid.uuid4(),
        email="admin@archon.ai",
        password_hash=bcrypt.hash("AdminPassword123!"),
        first_name="Admin",
        last_name="User",
        subscription_tier="enterprise",
        is_active=True,
        is_admin=True,
        email_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def user_token(test_user) -> str:
    """Create JWT token for test user."""
    return create_access_token(
        user_id=test_user.id,
        email=test_user.email,
        is_admin=test_user.is_admin,
        subscription_tier=test_user.subscription_tier,
    )


@pytest.fixture(scope="function")
def admin_token(admin_user) -> str:
    """Create JWT token for admin user."""
    return create_access_token(
        user_id=admin_user.id,
        email=admin_user.email,
        is_admin=admin_user.is_admin,
        subscription_tier=admin_user.subscription_tier,
    )


@pytest.fixture(scope="function")
def auth_headers(user_token) -> dict:
    """Authorization headers for regular user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture(scope="function")
def admin_headers(admin_token) -> dict:
    """Authorization headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


# ==================== Profile Fixtures ====================


@pytest_asyncio.fixture(scope="function")
async def test_profile(db_session, test_user) -> MT5Profile:
    """Create a test MT5 profile."""
    from archon_prime.api.services.encryption import get_encryption_service

    encryption = get_encryption_service()

    profile = MT5Profile(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Test Profile",
        mt5_login="12345678",
        mt5_password_encrypted=encryption.encrypt("test_password"),
        mt5_server="Demo-Server",
        broker_name="Test Broker",
        account_type="demo",
        is_connected=True,
        is_trading_enabled=True,
        balance=Decimal("10000.00"),
        equity=Decimal("10500.00"),
        margin=Decimal("500.00"),
        free_margin=Decimal("10000.00"),
        leverage=100,
        currency="USD",
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


@pytest_asyncio.fixture(scope="function")
async def disconnected_profile(db_session, test_user) -> MT5Profile:
    """Create a disconnected MT5 profile."""
    from archon_prime.api.services.encryption import get_encryption_service

    encryption = get_encryption_service()

    profile = MT5Profile(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name="Disconnected Profile",
        mt5_login="87654321",
        mt5_password_encrypted=encryption.encrypt("test_password"),
        mt5_server="Demo-Server",
        broker_name="Test Broker",
        account_type="demo",
        is_connected=False,
        is_trading_enabled=False,
    )
    db_session.add(profile)
    await db_session.commit()
    await db_session.refresh(profile)
    return profile


# ==================== Position Fixtures ====================


@pytest_asyncio.fixture(scope="function")
async def test_position(db_session, test_profile) -> Position:
    """Create a test position."""
    position = Position(
        id=uuid.uuid4(),
        profile_id=test_profile.id,
        ticket=100001,
        symbol="EURUSD",
        position_type="buy",
        volume=Decimal("0.10"),
        open_price=Decimal("1.08500"),
        current_price=Decimal("1.08650"),
        stop_loss=Decimal("1.08000"),
        take_profit=Decimal("1.09000"),
        profit=Decimal("15.00"),
        open_time=datetime.now(timezone.utc),
    )
    db_session.add(position)
    await db_session.commit()
    await db_session.refresh(position)
    return position


# ==================== Mock Fixtures ====================


@pytest.fixture(scope="function")
def mock_mt5_pool():
    """Mock MT5 connection pool."""
    with patch("archon_prime.api.services.mt5_pool.get_mt5_pool") as mock:
        pool = MagicMock()
        pool.connect = AsyncMock(return_value=(True, "Connected"))
        pool.disconnect = AsyncMock(return_value=(True, "Disconnected"))
        pool.is_connected = MagicMock(return_value=True)
        pool.get_stats = MagicMock(return_value={
            "total_connections": 1,
            "active_connections": 1,
            "failed_connections": 0,
        })
        mock.return_value = pool
        yield pool


@pytest.fixture(scope="function")
def mock_websocket_manager():
    """Mock WebSocket connection manager."""
    with patch("archon_prime.api.websocket.manager.get_connection_manager") as mock:
        manager = MagicMock()
        manager.broadcast_to_profile = AsyncMock()
        manager.broadcast_to_user = AsyncMock()
        manager.get_stats = MagicMock(return_value={
            "total_connections": 0,
            "active_profiles": 0,
        })
        mock.return_value = manager
        yield manager


@pytest.fixture(scope="function")
def mock_broadcaster():
    """Mock WebSocket broadcaster."""
    with patch("archon_prime.api.websocket.handlers.get_broadcaster") as mock:
        broadcaster = MagicMock()
        broadcaster.signal_notification = AsyncMock()
        broadcaster.position_update = AsyncMock()
        broadcaster.account_update = AsyncMock()
        broadcaster.risk_alert = AsyncMock()
        mock.return_value = broadcaster
        yield broadcaster


# ==================== Signal Fixtures ====================


@pytest.fixture(scope="function")
def valid_signal_request() -> dict:
    """Valid signal submission request."""
    return {
        "idempotency_key": f"test-signal-{uuid.uuid4().hex[:8]}",
        "symbol": "EURUSD",
        "direction": "buy",
        "source": "strategy",
        "priority": "normal",
        "confidence": "0.85",
        "reasoning": "Test signal for E2E validation",
        "strategy_name": "test_strategy",
        "model_version": "1.0.0",
    }


@pytest.fixture(scope="function")
def low_confidence_signal() -> dict:
    """Signal with confidence below threshold."""
    return {
        "idempotency_key": f"low-conf-{uuid.uuid4().hex[:8]}",
        "symbol": "EURUSD",
        "direction": "buy",
        "source": "strategy",
        "priority": "normal",
        "confidence": "0.50",  # Below 0.7 threshold
    }


# ==================== Helpers ====================


class TestHelpers:
    """Helper methods for tests."""

    @staticmethod
    def generate_idempotency_key() -> str:
        """Generate unique idempotency key."""
        return f"test-{uuid.uuid4().hex[:16]}"

    @staticmethod
    def assert_signal_approved(response: dict) -> None:
        """Assert signal was approved."""
        assert response["decision"] == "approved"
        assert response["decision_reason"] is not None

    @staticmethod
    def assert_signal_rejected(response: dict, reason_contains: str = None) -> None:
        """Assert signal was rejected."""
        assert response["decision"] == "rejected"
        if reason_contains:
            assert reason_contains in response["decision_reason"]


@pytest.fixture(scope="function")
def helpers() -> TestHelpers:
    """Provide test helpers."""
    return TestHelpers()
