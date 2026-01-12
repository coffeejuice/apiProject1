# Port Change Notice

## Issue
Port 8000 is being used by a Windows service (DEF_SC.EXE) on your system.

## Solution
The server now runs on **port 8001** instead of port 8000.

## Updated URLs

### API Base URL
- **Old:** http://localhost:8000
- **New:** http://localhost:8001

### Interactive Documentation
- **Old:** http://localhost:8000/docs
- **New:** http://localhost:8001/docs

### Health Check
- **Old:** http://localhost:8000/health
- **New:** http://localhost:8001/health

## Usage

### Starting the Server
```cmd
python run.py
```

Server will start on: http://localhost:8001

### Using the Python Client

Update the base URL in your client code:

```python
from client.api_client import NotionClient

# Use port 8001
client = NotionClient("http://localhost:8001")
```

### CLI Commands

The CLI uses localhost:8000 by default. You have two options:

**Option 1: Update client/api_client.py**

Change the default base URL:
```python
def __init__(self, base_url: str = "http://localhost:8001"):
```

**Option 2: Specify URL when using CLI**

Modify the client initialization in your scripts to use port 8001.

## Troubleshooting

### If you want to use port 8000

You can stop the service using port 8000:

1. Identify the service:
   ```cmd
   netstat -ano | findstr :8000
   ```

2. Stop the process (requires admin):
   ```cmd
   taskkill /PID 24108 /F
   ```

   **⚠️ Warning:** Only do this if you know what the service is!

3. Change port back in `run.py`:
   ```python
   port=8000,
   ```

### Check if port 8001 is available

```cmd
netstat -ano | findstr :8001
```

If nothing is returned, port 8001 is free.

## Updated Documentation

The following files should reference port 8001:
- README.md
- START_HERE.md
- QUICKSTART_WINDOWS.md
- SETUP.md
- example.py
- client/api_client.py

## Summary

✅ **Server now runs on port 8001**
✅ **All functionality remains the same**
✅ **Update your bookmarks and client code**

Access your API at: **http://localhost:8001/docs**
