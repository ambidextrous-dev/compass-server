**Compass Server**

A Python-based reimplementation of Aaron’s [Compass](https://github.com/aaronpk/Compass) service, compatible with the Overland iOS app.
Provides secure write and read APIs for storing and querying GeoJSON location data.

---

## Features

* **POST** `/api/input` – Securely upload GeoJSON FeatureCollections
* **GET** `/api/query` – Retrieve all features for a given date (full or linestring)
* **GET** `/api/last` – Fetch the most recent feature
* **GET** `/api/find-from-localtime` – Fetch all features since a local datetime
* **Ping health check** at `/ping`

---

## Prerequisites

* Python 3.12+
* [Poetry](https://python-poetry.org/) for dependency management

---

## Installation

1. **Clone the repo**

   ```bash
   git clone https://github.com/yourusername/compass-server.git
   cd compass-server
   ```

2. **Install dependencies**

   ```bash
   poetry install
   ```

3. **Set up environment**

   * Copy `.env.example` to `.env`
   * Fill in `WRITE_TOKEN` and `READ_TOKEN` with secure random strings

4. **Create storage directory**
   ```bash
   mkdir data
   ```

---

## Running Locally

```bash
poetry run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

* Visit `http://localhost:8000/ping` to verify the server is up.
* Use the API endpoints documented below.

---

## API Endpoints

### POST `/api/input`

Upload a GeoJSON FeatureCollection.

**Headers**:

* `Content-Type: application/json`
* `X-Write-Token: <your write token>`

**Body**:

```json
{
  "type": "FeatureCollection",
  "features": [ ... ]
}
```

**Response**:

```json
{ "status": "success", "file": "<generated-filename>.json" }
```

### GET `/api/query`

Retrieve all features for a specific date.

**Query Parameters**:

* `token` (string, required) – your read token
* `date` (YYYY-MM-DD, required)
* `tz` (string, default `UTC`)
* `format` (`full` or `linestring`, default `full`)

**Response**:

* `full`: GeoJSON FeatureCollection
* `linestring`: a single Feature with LineString

### GET `/api/last`

Fetch the most recent feature.

**Query Parameters**:

* `token` (string, required)

**Response**:

* A single GeoJSON Feature

### GET `/api/find-from-localtime`

Fetch all features since a local datetime.

**Query Parameters**:

* `token` (string, required)
* `datetime_str` (YYYY-MM-DDTHH\:MM\:SS, required)
* `tz` (string, default `UTC`)

**Response**:

* GeoJSON FeatureCollection

---

## Import Sorting & Code Style
We recommend using Ruff for both linting and automatic import sorting in one tool:

1. **Install**

   ```bash
   poetry add --dev ruff
   ```
2. **Configure** in `pyproject.toml`:

   ```toml
   [tool.ruff]
   line-length = 88
   select = ["E", "F", "I"]       # E = pycodestyle, F = pyflakes, I = imports
   fixable = ["I"] 
   ```
3. **Run formatting**

   ```bash
   poetry run ruff check src/
   poetry run ruff check --fix src/
   ```
---

## License

MIT
