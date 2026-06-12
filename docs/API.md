# CodeDNA API Reference

Complete API documentation for the CodeDNA daemon.

## Base URL

```
http://127.0.0.1:7842
```

All endpoints (except health checks) require the `X-CodeDNA-Client` header:

```
X-CodeDNA-Client: <client-name>
```

**Valid client identifiers:**
- `cli` - Command-line interface
- `vscode-extension` - VS Code extension
- `dashboard` - Web dashboard
- `pre-commit-hook` - Git pre-commit hook
- `api-test` - API testing client

## Endpoints

### Health Check

**GET** `/health`

Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy"
}
```

---

### Get Status

**GET** `/api/v1/status`

Get daemon status, database version, and tracked repositories.

**Headers:**
- `X-CodeDNA-Client: cli`

**Response:**
```json
{
  "status": "running",
  "db_version": 1,
  "expected_schema_version": 1,
  "rebuild_required": false,
  "active_repos": [
    {
      "id": "uuid",
      "path": "/path/to/repo",
      "name": "repo-name",
      "language": "python",
      "created_at": 1234567890,
      "updated_at": 1234567890
    }
  ],
  "interrupted_jobs": []
}
```

---

### List Repositories

**GET** `/api/v1/repos`

List all tracked repositories.

**Response:**
```json
[
  {
    "id": "uuid",
    "path": "/path/to/repo",
    "name": "repo-name",
    "language": "python",
    "created_at": 1234567890,
    "updated_at": 1234567890
  }
]
```

---

### Add Repository

**POST** `/api/v1/repos`

Track a new repository.

**Headers:**
- `X-CodeDNA-Client: cli`
- `Content-Type: application/json`

**Request Body:**
```json
{
  "path": "/path/to/repo",
  "language": "python"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "path": "/path/to/repo",
  "name": "repo-name",
  "language": "python"
}
```

**Error Responses:**
- `400` - Path does not exist
- `400` - Not a git repository
- `409` - Repository already tracked

---

### Delete Repository

**DELETE** `/api/v1/repos/{repo_id}`

Remove a repository from tracking (soft delete).

**Response:** `204 No Content`

**Error Responses:**
- `404` - Repository not found

---

### Erase Repository Data

**DELETE** `/api/v1/repos/{repo_id}/data`

Erase all data for a repository (fingerprints, scan results, jobs) without removing the repository itself.

**Response:** `200 OK`
```json
{
  "repo_id": "uuid",
  "erased": {
    "scan_results_deleted": 150,
    "feature_vectors_deleted": 200,
    "fingerprints_deleted": 3,
    "jobs_deleted": 5
  }
}
```

**Error Responses:**
- `404` - Repository not found

---

### Enqueue Baseline Build

**POST** `/api/v1/repos/{repo_id}/build`

Start a baseline fingerprint build for a repository.

**Response:** `200 OK`
```json
{
  "job_id": "uuid",
  "status": "QUEUED"
}
```

**Error Responses:**
- `404` - Repository not found
- `409` - Build already running

---

### Get Job Status

**GET** `/api/v1/jobs/{job_id}`

Get the status of a background job.

**Response:**
```json
{
  "id": "uuid",
  "repo_id": "uuid",
  "type": "FULL_BUILD",
  "status": "RUNNING",
  "progress": 0.45,
  "started_at": 1234567890,
  "completed_at": null,
  "error": null,
  "created_at": 1234567890
}
```

**Status values:** `QUEUED`, `RUNNING`, `COMPLETE`, `FAILED`

**Error Responses:**
- `404` - Job not found

---

### Scan File

**POST** `/api/v1/scan/file`

Scan a file and compare against the repository's baseline fingerprint.

**Headers:**
- `X-CodeDNA-Client: cli`
- `Content-Type: application/json`

**Request Body:**
```json
{
  "repo_id": "uuid",
  "file_path": "/path/to/file.py",
  "language": "python",
  "content_hash": "sha256-hash"  // optional
}
```

**Response:**
```json
{
  "scan_id": "uuid",
  "dna_score": 0.87,
  "explanation": {
    "summary": "Consistent with your established patterns.",
    "patterns": [
      {"name": "Type-annotated", "description": "Uses type hints extensively", "confidence": 0.8}
    ],
    "changes": []
  },
  "latency_ms": 45.2,
  "degraded": false
}
```

**DNA Score Interpretation:**
- `>= 0.85` - High confidence match
- `0.70 - 0.85` - Minor style deviation
- `< 0.70` - Significant deviation

**Error Responses:**
- `400` - Missing required fields

**Notes:**
- If no baseline exists, `dna_score` will be `null` and `degraded` will be `true`
- The file content is read from disk if not provided

---

### Get Evolution

**GET** `/api/v1/evolution/{repo_id}`

Get scan history and trend analysis for a repository.

**Response:**
```json
{
  "repo_id": "uuid",
  "scan_count": 150,
  "average_score": 0.82,
  "trend": "stable",
  "scans": [
    {
      "timestamp": 1234567890,
      "score": 0.85,
      "degraded": false
    }
  ]
}
```

**Trend values:**
- `insufficient_data` - Less than 2 scans
- `stable` - Score variance < 0.1
- `improving` - Recent scores trending up
- `degrading` - Recent scores trending down

---

### SSE Event Stream

**GET** `/api/v1/events`

Server-Sent Events stream for real-time updates.

**Headers:**
- `X-CodeDNA-Client: cli`
- `Accept: text/event-stream`

**Event Types:**

`job.queued`:
```json
{"job_id": "uuid", "repo_id": "uuid", "type": "FULL_BUILD"}
```

`job.started`:
```json
{"job_id": "uuid", "repo_id": "uuid", "type": "FULL_BUILD"}
```

`job.progress`:
```json
{"job_id": "uuid", "repo_id": "uuid", "progress": 0.5}
```

`job.complete`:
```json
{"job_id": "uuid", "repo_id": "uuid"}
```

`job.failed`:
```json
{"job_id": "uuid", "repo_id": "uuid", "error": "error message"}
```

`daemon.status`:
```json
{"status": "running", "db_version": 1, "expected_schema_version": 1, "active_repos": 2}
```

`scan.complete`:
```json
{"scan_id": "uuid", "repo_id": "uuid", "dna_score": 0.85, "file_path": "/path/to/file.py"}
```

`build.complete`:
```json
{"job_id": "uuid", "repo_id": "uuid", "success": true}
```

---

### Get Configuration

**GET** `/api/v1/config`

Get current configuration (reads from `~/.codedna/config.json`).

**Response:**
```json
{
  "daemon": {
    "host": "127.0.0.1",
    "port": 7842
  },
  "scanner": {
    "timeout_ms": 2000
  }
}
```

---

### Export Data

**POST** `/api/v1/export`

Export repository data.

**Request Body:**
```json
{
  "repo_id": "uuid",
  "format": "json",
  "include": ["fingerprint", "evolution", "scan_history"],
  "confirmed": true
}
```

**Response:**
```json
{
  "format": "json",
  "data": {
    "fingerprint": {...},
    "scans": [...]
  },
  "exported_at": 1234567890
}
```

**Error Responses:**
- `400` - `confirmed` must be `true`

---

## Error Response Format

All error responses follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message"
  }
}
```

**Error Codes:**
- `MISSING_CLIENT_HEADER` - X-CodeDNA-Client header missing
- `NON_LOCALHOST_REJECTED` - Request from non-loopback address
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `INVALID_PATH` - Path does not exist
- `NOT_A_GIT_REPO` - Not a git repository
- `REPO_ALREADY_TRACKED` - Repository already tracked
- `REPO_NOT_FOUND` - Repository not found
- `BUILD_ALREADY_RUNNING` - Build already in progress
- `JOB_NOT_FOUND` - Job not found
- `EXPORT_NOT_CONFIRMED` - Export not confirmed
- `INTERNAL_ERROR` - Unexpected server error

---

## Rate Limits

| Client Type | Limit | Window |
|-------------|-------|--------|
| Per-client | 100 requests | 1 minute |
| Per-IP | 1000 requests | 1 minute |

Rate-limited responses include a `Retry-After` header.

---

## Example Usage

### cURL

```bash
# Health check
curl http://127.0.0.1:7842/health

# Add repository
curl -X POST http://127.0.0.1:7842/api/v1/repos \
  -H "X-CodeDNA-Client: cli" \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/repo", "language": "python"}'

# Scan file
curl -X POST http://127.0.0.1:7842/api/v1/scan/file \
  -H "X-CodeDNA-Client: cli" \
  -H "Content-Type: application/json" \
  -d '{"repo_id": "uuid", "file_path": "/path/to/file.py"}'

# Start baseline build
curl -X POST http://127.0.0.1:7842/api/v1/repos/uuid/build \
  -H "X-CodeDNA-Client: cli"
```

### Python

```python
import requests

headers = {"X-CodeDNA-Client": "cli"}

# Scan a file
response = requests.post(
    "http://127.0.0.1:7842/api/v1/scan/file",
    headers=headers,
    json={
        "repo_id": "uuid",
        "file_path": "/path/to/file.py",
        "language": "python"
    }
)
result = response.json()
print(f"DNA Score: {result['dna_score']}")
print(f"Explanation: {result['explanation']['summary']}")
```

### JavaScript (Node.js)

```javascript
const fetch = require('http');

const options = {
  hostname: '127.0.0.1',
  port: 7842,
  path: '/api/v1/scan/file',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-CodeDNA-Client': 'cli'
  }
};

const req = fetch.request(options, (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    const result = JSON.parse(data);
    console.log(`DNA Score: ${result.dna_score}`);
  });
});
req.write(JSON.stringify({repo_id: 'uuid', file_path: '/path/to/file.py'}));
req.end();
```