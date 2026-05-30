import pytest
from db.client import Database
from schema.migrate import migrate


@pytest.fixture
def db():
    """In-memory DB with schema applied."""
    database = Database(":memory:")
    migrate(database)
    yield database
    database.close()
