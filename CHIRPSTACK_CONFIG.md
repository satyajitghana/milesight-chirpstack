# ChirpStack Configuration Script

This repository contains a comprehensive script to configure ChirpStack with Milesight IoT device profiles and devices using the gRPC API.

## 🚀 Features

- **Automatic Device Profile Creation**: Creates WS202 and WS203 device profiles with proper LoRaWAN configuration
- **Codec Integration**: Downloads and integrates Milesight decoder scripts automatically
- **Application Management**: Creates applications for organizing devices
- **Device Registration**: Registers devices with OTAA configuration
- **Duplicate Detection**: Skips existing profiles, applications, and devices
- **Progress Tracking**: Beautiful CLI interface with progress bars and status updates

## 📋 Prerequisites

- ChirpStack server running (v4.x)
- Python 3.13+
- Valid ChirpStack API key with appropriate permissions
- Access to ChirpStack gRPC API (default: `localhost:8080`)

## 🛠️ Installation

1. **Install uv and dependencies**:
   ```bash
   # Install uv (if not already installed)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Set up Python environment
   uv venv
   source .venv/bin/activate
   uv sync
   ```

2. **Verify ChirpStack is running**:
   ```bash
   # Check if ChirpStack is accessible
   curl -I http://localhost:8080
   ```

## 📁 Configuration Files

### Device Profiles (`device_profiles.json`)

Contains configuration for Milesight device profiles:

```json
[
  {
    "name": "WS202-868M",
    "description": "Milesight WS202 PIR and Light Sensor - Region: IN865",
    "region": "IN865",
    "mac_version": "LORAWAN_MAC_VERSION_1_0_3",
    "codec_script_url": "https://raw.githubusercontent.com/Milesight-IoT/SensorDecoders/main/WS_Series/WS202/WS202_Decoder.js"
    // ... additional configuration
  }
]
```

### Devices (`devices.json`)

Contains device configuration with OTAA settings:

```json
[
  {
    "name": "PIR and Light",
    "dev_eui": "24e124538f256619",
    "device_profile_name": "WS202-868M",
    "application_name": "Milesight IoT Sensors",
    "join_eui": "24e124c0002a0001",
    "app_key": "5572404c696e6b4c6f52613230313823"
    // ... additional configuration
  }
]
```

## 🔧 Usage

### Simple Configuration

Run the configuration script:

```bash
python configure_chirpstack.py
```

### Advanced Usage

Use the main configurator directly:

```bash
python chirpstack_configurator.py
```

### Environment Variables

You can override default settings using environment variables:

```bash
export CHIRPSTACK_API_KEY="your_api_key_here"
export CHIRPSTACK_SERVER="your_server:port"
python configure_chirpstack.py
```

## 📖 Configuration Details

### Device Profiles Created

#### WS202-868M (PIR and Light Sensor)
- **Region**: IN865 (India)
- **MAC Version**: LoRaWAN 1.0.3
- **Sensors**: PIR motion detection, daylight level, battery
- **Codec**: Milesight WS202 decoder
- **Class**: Class A
- **Activation**: OTAA

#### WS203-868M (Temperature and Humidity Sensor)
- **Region**: IN865 (India)  
- **MAC Version**: LoRaWAN 1.0.3
- **Sensors**: Temperature, humidity, occupancy, battery
- **Codec**: Milesight WS203 decoder
- **Class**: Class A
- **Activation**: OTAA

### Default OTAA Configuration

All Milesight devices use the same default OTAA configuration:
- **App EUI**: `24E124C0002A0001`
- **App Key**: `5572404c696e6b4c6f52613230313823`

Each device has a unique Device EUI:
- **PIR and Light**: `24e124538f256619`
- **Temperature and Humidity**: `24e124791f178752`

## 🔍 Script Workflow

1. **Initialize gRPC Clients**: Connects to ChirpStack API
2. **Get Tenant ID**: Retrieves the default tenant
3. **Create Device Profiles**: 
   - Downloads codec scripts from GitHub
   - Creates profiles if they don't exist
   - Returns existing profile IDs if found
4. **Create Application**:
   - Creates "Milesight IoT Sensors" application
   - Returns existing application ID if found
5. **Register Devices**:
   - Creates devices with OTAA configuration
   - Registers device keys for OTAA join
   - Skips existing devices

## 🛡️ Error Handling

The script includes comprehensive error handling:

- **Connection Errors**: Validates gRPC connection to ChirpStack
- **Authentication**: Checks API key validity
- **Duplicate Detection**: Safely handles existing resources
- **Codec Download**: Gracefully handles network failures
- **Rollback**: Partial failures don't affect existing configuration

## 📊 Monitoring

After configuration, you can monitor your devices:

1. **ChirpStack Web UI**: Check device status and data
2. **IoT Dashboard**: Use the included `iot_client.py` for real-time monitoring
3. **MQTT**: Subscribe to device data streams

```bash
# Start the IoT dashboard
python iot_client.py
```

## 🔧 Troubleshooting

### Common Issues

1. **gRPC Connection Failed**
   ```
   Error: Failed to setup gRPC clients
   ```
   - Check if ChirpStack is running
   - Verify the server URL (default: `localhost:8080`)
   - Ensure gRPC API is enabled

2. **Authentication Failed**
   ```
   Error: Authentication failed
   ```
   - Verify your API key is valid
   - Check API key permissions in ChirpStack
   - Ensure key has tenant access

3. **Codec Download Failed**
   ```
   Error: Failed to download codec
   ```
   - Check internet connectivity
   - Verify GitHub URLs are accessible
   - Script continues with empty codec (can be added manually)

4. **Device Already Exists**
   ```
   Warning: Device already exists
   ```
   - This is normal behavior
   - Script skips existing devices
   - No action required

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🔄 Updates and Maintenance

### Adding New Devices

1. Add device configuration to `devices.json`
2. Run the configuration script
3. Existing devices won't be affected

### Updating Device Profiles

1. Modify `device_profiles.json`
2. Delete existing profiles in ChirpStack (if needed)
3. Run the configuration script

### Backup Configuration

Before major changes:

```bash
# Export existing configuration
python -c "
import json
from chirpstack_configurator import ChirpStackConfigurator
config = ChirpStackConfigurator('your_api_key')
# Export and save configuration
"
```

## 📝 License

This configuration script is provided as-is for ChirpStack integration with Milesight IoT devices.

## 🤝 Support

For issues related to:
- **ChirpStack**: Check [ChirpStack documentation](https://www.chirpstack.io/docs/)
- **Milesight Devices**: Consult [Milesight documentation](https://www.milesight-iot.com/)
- **This Script**: Review error messages and logs

## 📚 Additional Resources

- [ChirpStack API Documentation](https://www.chirpstack.io/docs/chirpstack/api/api.html)
- [ChirpStack Python Examples](https://www.chirpstack.io/docs/chirpstack/api/python-examples.html)
- [Milesight Sensor Decoders](https://github.com/Milesight-IoT/SensorDecoders)
- [LoRaWAN Regional Parameters](https://lora-alliance.org/resource_hub/rp2-1-0-3-lorawan-regional-parameters/) 