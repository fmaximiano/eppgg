import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.schemas import Parameters, Scenario
from app.main import create_app


@pytest.fixture
def parameters():
    return Parameters.model_validate_json((Path(__file__).parents[1] / 'data/demo.json').read_text())


@pytest.fixture
def scenario():
    return Scenario()


@pytest.fixture
def client(tmp_path):
    app = create_app('sqlite:///' + str(tmp_path / 'test.db'))
    with TestClient(app) as client:
        yield client
