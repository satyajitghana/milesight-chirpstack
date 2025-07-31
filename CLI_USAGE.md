# ChirpStack CLI Tool 🚀

A powerful command-line interface for managing ChirpStack gateways, device profiles, and devices with step-by-step configuration.

## 🎯 Features

- **Step-by-step configuration**: Add gateways → device profiles → devices
- **Intelligent duplicate detection**: Only adds new items, skips existing ones
- **Beautiful CLI interface**: Rich formatting with progress bars and tables
- **JSON-based configuration**: Easy to manage and version control
- **Environment variable support**: Secure API key management

## 📋 Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Or using Poetry
poetry install

# Set environment variables (optional)
export CHIRPSTACK_API_KEY="your-api-key-here"
export CHIRPSTACK_SERVER="localhost:8080"
```

## 🎪 Quick Start

### 1. Check Authentication
```bash
# Test if your API key works
python chirpstack_cli.py check-auth
```

### 2. Add Gateways (Step 1)
```bash
# Add a single gateway
python chirpstack_cli.py add-gateway \
  --id "0016c001f15f5e6d" \
  --name "Main Building Gateway" \
  --description "Primary LoRaWAN gateway" \
  --lat 28.6139 --lon 77.2090 --alt 10.0

# Or add multiple gateways from JSON
python chirpstack_cli.py add-gateways --file gateways.json

# List all gateways to verify
python chirpstack_cli.py list-gateways
```

### 3. Add Device Profiles (Step 2)
```bash
# Add device profiles from JSON (includes Milesight WS202/WS203)
python chirpstack_cli.py add-profiles --file device_profiles.json

# List all device profiles to verify
python chirpstack_cli.py list-profiles
```

### 4. Add Devices (Step 3)
```bash
# Add devices from JSON
python chirpstack_cli.py add-devices --file devices.json

# List all devices to verify
python chirpstack_cli.py list-devices
```

## 📁 Configuration Files

### `gateways.json`
```json
[
  {
    "gateway_id": "0016c001f15f5e6d",
    "name": "Main Building Gateway",
    "description": "Primary gateway for the main building",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "altitude": 10.0,
    "tags": {
      "location": "Main Building",
      "floor": "Roof"
    }
  }
]
```

### `device_profiles.json`
Contains WS202 and WS203 device profiles with Milesight decoders.

### `devices.json`
Contains device configurations with EUIs, app keys, and profile associations.

## 🔧 Available Commands

### Authentication
```bash
# Check if API authentication works
python chirpstack_cli.py check-auth
```

### Gateway Management
```bash
# List all gateways
python chirpstack_cli.py list-gateways

# Add a single gateway
python chirpstack_cli.py add-gateway --id "..." --name "..." [options]

# Add multiple gateways from JSON
python chirpstack_cli.py add-gateways [--file gateways.json] [--force]
```

### Device Profile Management
```bash
# List all device profiles
python chirpstack_cli.py list-profiles

# Add device profiles from JSON
python chirpstack_cli.py add-profiles [--file device_profiles.json] [--force]
```

### Application Management
```bash
# List all applications
python chirpstack_cli.py list-applications
```

### Device Management
```bash
# List all devices
python chirpstack_cli.py list-devices [--app-id "..."]

# Add devices from JSON
python chirpstack_cli.py add-devices [--file devices.json] [--force]
```

## 🎛️ Command Options

### Global Options
```bash
# Override API key and server
python chirpstack_cli.py --api-key "your-key" --server "your-server:8080" [command]
```

### Common Flags
- `--force`: Force creation even if item already exists
- `--file`, `-f`: Specify JSON configuration file
- `--help`: Show help for any command

## 🔐 Environment Variables

```bash
# Set these to avoid passing sensitive data as command arguments
export CHIRPSTACK_API_KEY="eyJ0eXAiOiJKV1Q..."
export CHIRPSTACK_SERVER="localhost:8080"
```

## 📖 Step-by-Step Workflow

### Complete Setup Flow
```bash
# 1. Verify connection
python chirpstack_cli.py check-auth

# 2. Add gateways
python chirpstack_cli.py add-gateways
python chirpstack_cli.py list-gateways

# 3. Add device profiles (includes codec download)
python chirpstack_cli.py add-profiles
python chirpstack_cli.py list-profiles

# 4. Add devices (creates applications automatically)
python chirpstack_cli.py add-devices
python chirpstack_cli.py list-devices

# 5. Verify everything
python chirpstack_cli.py list-applications
```

## 🐛 Troubleshooting

### Connection Issues
```bash
# Test authentication first
python chirpstack_cli.py check-auth

# Check server URL (should include port)
export CHIRPSTACK_SERVER="your-server:8080"
```

### File Not Found
```bash
# Make sure JSON files exist in current directory
ls -la *.json

# Use custom file paths
python chirpstack_cli.py add-profiles --file /path/to/profiles.json
```

### Permission Errors
```bash
# Verify API key has proper permissions
# Check ChirpStack web UI → API Keys → Permissions
```

## 📊 Example Output

```bash
$ python chirpstack_cli.py add-gateways
📡 Adding Gateways from gateways.json
📂 Loaded 2 gateways from gateways.json
✅ Created gateway: Main Building Gateway (0016c001f15f5e6d)
✅ Created gateway: Secondary Building Gateway (0016c001f15f5e6e)

📊 Summary: 2 created, 0 skipped, 0 errors
```

## 🎉 Success!

Your ChirpStack instance is now configured with:
- ✅ Gateways for network coverage
- ✅ Device profiles with Milesight decoders
- ✅ Applications for device organization  
- ✅ Devices ready for OTAA activation

Power on your Milesight WS202/WS203 devices and they should automatically join the network! 🚀 