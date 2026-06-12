"""Integration tests for CodeDNA daemon."""
import pytest
from fastapi.testclient import TestClient


class TestAPIContract:
    @pytest.fixture
    def client(self):
        from codedna.daemon.app import create_app
        app = create_app()
        return TestClient(app)

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "CodeDNA Dashboard" in response.text

    def test_status_endpoint(self, client):
        response = client.get("/api/v1/status", headers={"X-CodeDNA-Client": "test"})
        assert response.status_code == 200
        data = response.json()
        assert "db_version" in data
        assert "active_repos" in data

    def test_repos_list_endpoint(self, client):
        response = client.get("/api/v1/repos", headers={"X-CodeDNA-Client": "test"})
        assert response.status_code == 200


class TestErrorContract:
    @pytest.fixture
    def client(self):
        from codedna.daemon.app import create_app
        app = create_app()
        return TestClient(app)

    def test_export_requires_confirmation(self, client):
        response = client.post("/api/v1/export", headers={"X-CodeDNA-Client": "test"},
                               json={"repo_id": "test-id", "format": "json", "include": ["fingerprint"], "confirmed": False})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "EXPORT_NOT_CONFIRMED"


class TestLocalhostMiddleware:
    def test_middleware_exists(self):
        from codedna.daemon.middleware import LocalhostOnlyMiddleware
        assert LocalhostOnlyMiddleware is not None


class TestScanEndpoint:
    @pytest.fixture
    def client(self):
        from codedna.daemon.app import create_app
        app = create_app()
        return TestClient(app)

    def test_scan_file_returns_result(self, client):
        response = client.post("/api/v1/scan/file", headers={"X-CodeDNA-Client": "test"},
                               json={"repo_id": "test-repo", "file_path": "test.py", "language": "python"})
        assert response.status_code == 200
        data = response.json()
        assert "scan_id" in data

    def test_scan_file_with_active_baseline(self, client, sample_git_repo):
        with client:
            # 1. Register the repository
            response = client.post(
                "/api/v1/repos",
                headers={"X-CodeDNA-Client": "test"},
                json={"path": str(sample_git_repo), "language": "python"}
            )
            assert response.status_code == 201
            repo_data = response.json()
            repo_id = repo_data["id"]

            # 2. Trigger a baseline build
            response = client.post(
                f"/api/v1/repos/{repo_id}/build",
                headers={"X-CodeDNA-Client": "test"}
            )
            assert response.status_code == 200
            job_data = response.json()
            job_id = job_data["job_id"]

            # 3. Wait for the build job to complete
            import time
            max_attempts = 15
            for _ in range(max_attempts):
                response = client.get(f"/api/v1/jobs/{job_id}", headers={"X-CodeDNA-Client": "test"})
                assert response.status_code == 200
                job_status = response.json()["status"]
                if job_status == "COMPLETE":
                    break
                elif job_status == "FAILED":
                    pytest.fail(f"Job failed: {response.json().get('error')}")
                time.sleep(0.5)
            else:
                pytest.fail("Job build timed out")

            # 4. Scan a file in that repo
            scan_file_path = sample_git_repo / "main.py"
            response = client.post(
                "/api/v1/scan/file",
                headers={"X-CodeDNA-Client": "test"},
                json={"repo_id": repo_id, "file_path": str(scan_file_path), "language": "python"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "scan_id" in data
            assert data["degraded"] is False
            assert data["dna_score"] is not None
            assert data["dna_score"] >= 0.0


class TestConfigEndpoint:
    @pytest.fixture
    def client(self):
        from codedna.daemon.app import create_app
        app = create_app()
        return TestClient(app)

    def test_get_config(self, client):
        response = client.get("/api/v1/config", headers={"X-CodeDNA-Client": "test"})
        assert response.status_code == 200


class TestSchemaVersion:
    def test_schema_version_constant(self):
        from codedna.db.schema import CURRENT_SCHEMA_VERSION
        assert CURRENT_SCHEMA_VERSION >= 1
