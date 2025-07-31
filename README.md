# ChirpStack Docker Setup with Milesight IoT Integration 🚀

[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![ChirpStack](https://img.shields.io/badge/ChirpStack-v4-00D4AA?style=flat-square&logo=chirpstack&logoColor=white)](https://www.chirpstack.io)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LoRaWAN](https://img.shields.io/badge/LoRaWAN-1.0.3-FF6B35?style=flat-square&logo=lora&logoColor=white)](https://lora-alliance.org)
[![Milesight](https://img.shields.io/badge/Milesight-IoT-0066CC?style=flat-square&logo=milesight&logoColor=white)](https://www.milesight-iot.com)
[![License](https://img.shields.io/badge/License-GPL--3.0-blue?style=flat-square)](LICENSE.md)

This repository contains a complete solution for setting up [ChirpStack](https://www.chirpstack.io) LoRaWAN Network Server (v4) with [Docker Compose](https://docs.docker.com/compose/) and comprehensive CLI tools for managing Milesight IoT devices.

## 🎯 Features

- **🐳 Docker-based ChirpStack**: Easy deployment with Docker Compose
- **🛠️ CLI Management Tools**: Comprehensive command-line interface for device management
- **📡 Milesight Integration**: Pre-configured device profiles for WS202/WS203 sensors  
- **🔄 Automated Configuration**: Step-by-step setup scripts with duplicate detection
- **📊 Live Dashboard**: Real-time IoT data monitoring with beautiful UI
- **🔐 Security**: API key management and secure MQTT connections
- **📱 OTAA Support**: Automatic device activation with proper key management

## 📋 Quick Start

### 1. Start ChirpStack Server

```bash
# Clone this repository
git clone <repository-url>
cd chirpstack-docker

# Start ChirpStack with Docker Compose
docker-compose up -d

# Verify services are running
docker-compose ps
```

Access ChirpStack web UI at: **http://localhost:8080**

### 2. Configure Your Environment

```bash
# Install uv (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Set up Python environment
uv venv
source .venv/bin/activate
uv sync

# Set your API key (get from ChirpStack web UI)
export CHIRPSTACK_API_KEY="your_api_key_here"
export CHIRPSTACK_SERVER="localhost:8080"
```

### 3. Run the Configuration Demo

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Interactive step-by-step setup guide
python demo.py

# Or use individual CLI commands
python chirpstack_cli.py check-auth
python chirpstack_cli.py add-gateways
python chirpstack_cli.py add-profiles  
python chirpstack_cli.py add-devices
```

## 🏗️ Complete Setup Workflow

### Step 1: ChirpStack Server Setup

1. **Start ChirpStack Docker**:
   ```bash
   docker-compose up -d
   ```

2. **Access Web UI**: Open http://localhost:8080 
   - Default login: `admin` / `admin`

3. **Create API Key**: 
   - Go to **Tenants** → **Default** → **API Keys**
   - Create new key with full permissions
   - Copy the JWT token for CLI usage

### Step 2: Milesight Gateway Configuration (UG63)

1. **Access Gateway Web Interface**:
   - Connect to your Milesight UG63 gateway
   - Login to the web interface

2. **Configure Packet Forwarding**:
   - Navigate to **LoRaWAN** → **Packet Forwarder**
   - Set **Server Address**: `beast2.local` (or your ChirpStack server IP)
   - Set **Server Port**: `1700` (UDP)
   - Set **Protocol**: `Semtech UDP`
   - Enable packet forwarding

3. **Network Settings**:
   - **Frequency Plan**: Select your region (e.g., IN865 for India)
   - **Gateway EUI**: Note this for ChirpStack registration

### Step 3: Register Gateway in ChirpStack

Using the CLI tool:

```bash
# Add your gateway to ChirpStack
python chirpstack_cli.py add-gateway \
  --id "your_gateway_eui" \
  --name "Main Building Gateway" \
  --description "Milesight UG63 Gateway" \
  --lat 28.6139 --lon 77.2090

# Verify gateway is connected
python chirpstack_cli.py list-gateways
```

Or edit `gateways.json` and run:
```bash
python chirpstack_cli.py add-gateways
```

### Step 4: Add Device Profiles

Device profiles contain the decoders for your IoT sensors:

```bash
# Add Milesight WS202 and WS203 profiles with decoders
python chirpstack_cli.py add-profiles

# Verify profiles were created
python chirpstack_cli.py list-profiles
```

This automatically downloads and integrates decoders from the [Milesight SensorDecoders repository](https://github.com/Milesight-IoT/SensorDecoders).

### Step 5: Add IoT Devices

Configure your Milesight sensors:

```bash
# Add devices with OTAA configuration
python chirpstack_cli.py add-devices

# Check device status
python chirpstack_cli.py list-devices
```

### Step 6: Activate Your Sensors

1. **Power on your Milesight sensors** (WS202, WS203, etc.)
2. **Automatic OTAA Join**: Devices will automatically join using:
   - **App EUI**: `24E124C0002A0001` (same for all Milesight devices)
   - **App Key**: `5572404c696e6b4c6f52613230313823` (same for all Milesight devices)
   - **Device EUI**: Unique per device (printed on device label)

3. **Monitor in ChirpStack**: Check **Applications** → **Milesight IoT Sensors** → **Devices**

## 🛠️ CLI Tools Reference

### ChirpStack CLI (`chirpstack_cli.py`)

Complete command-line interface for ChirpStack management:

```bash
# Authentication & Testing
python chirpstack_cli.py check-auth

# Gateway Management  
python chirpstack_cli.py list-gateways
python chirpstack_cli.py add-gateway --id "..." --name "..."
python chirpstack_cli.py add-gateways --file gateways.json

# Device Profile Management
python chirpstack_cli.py list-profiles
python chirpstack_cli.py add-profiles --file device_profiles.json

# Application Management
python chirpstack_cli.py list-applications

# Device Management
python chirpstack_cli.py list-devices
python chirpstack_cli.py add-devices --file devices.json

# Get help for any command
python chirpstack_cli.py [command] --help
```

### Configuration Scripts

- **`configure_chirpstack.py`**: Simple all-in-one configuration script
- **`chirpstack_configurator.py`**: Advanced configuration with detailed logging
- **`demo.py`**: Interactive step-by-step setup guide

### IoT Dashboard (`iot_client.py`)

Real-time monitoring dashboard for your IoT devices:

```bash
# Start the live dashboard
python iot_client.py
```

Features:
- 📊 Live sensor data display
- 📡 Gateway status monitoring  
- 🔋 Battery level tracking
- 📶 Signal quality indicators
- 🎨 Beautiful terminal UI with Rich

## 📁 Configuration Files

### Device Profiles (`device_profiles.json`)

Pre-configured profiles for Milesight sensors:

- **WS202-868M**: PIR motion and light sensor
- **WS203-868M**: Temperature and humidity sensor

Each profile includes:
- LoRaWAN 1.0.3 configuration for IN865 region
- Automatic codec download from GitHub
- Proper measurement definitions
- OTAA activation settings

### Devices (`devices.json`)

Device configurations with OTAA settings:

```json
{
  "name": "PIR and Light",
  "dev_eui": "24e124538f256619",
  "device_profile_name": "WS202-868M",
  "application_name": "Milesight IoT Sensors",
  "join_eui": "24e124c0002a0001",
  "app_key": "5572404c696e6b4c6f52613230313823"
}
```

### Gateways (`gateways.json`)

Gateway definitions with location data:

```json
{
  "gateway_id": "0016c001f15f5e6d",
  "name": "Main Building Gateway", 
  "description": "Primary LoRaWAN gateway",
  "latitude": 28.6139,
  "longitude": 77.2090,
  "altitude": 10.0
}
```

## 🔧 Directory Structure

```
chirpstack-docker/
├── docker-compose.yml              # ChirpStack services
├── configuration/                  # ChirpStack configuration files
│   ├── chirpstack/                # Server configuration
│   ├── chirpstack-gateway-bridge/ # Gateway bridge config
│   ├── mosquitto/                 # MQTT broker config
│   └── postgresql/                # Database initialization
├── chirpstack_cli.py              # Main CLI tool
├── chirpstack_configurator.py     # Configuration library
├── configure_chirpstack.py        # Simple setup script
├── iot_client.py                  # Live dashboard
├── demo.py                        # Interactive setup guide
├── device_profiles.json           # Milesight device profiles
├── devices.json                   # Device configurations
├── gateways.json                  # Gateway definitions
├── config.json                    # Dashboard configuration
├── CLI_USAGE.md                   # Detailed CLI documentation
├── CHIRPSTACK_CONFIG.md           # Configuration guide
└── README.md                      # This file
```

## 🌐 Regional Configuration

This setup is pre-configured for **IN865** (India) region. To use other regions:

1. **Update device profiles**: Change `"region": "IN865"` to your region
2. **Modify gateway bridge**: Update MQTT topic prefixes in `docker-compose.yml`
3. **Check frequency plan**: Ensure your gateway supports the region

Supported regions: `EU868`, `US915`, `AU915`, `AS923`, `IN865`, `KR920`, `RU864`

## 📡 MQTT Integration

Connect to the MQTT broker to receive real-time sensor data:

```bash
# MQTT broker details
Host: localhost
Port: 1883
Topic: application/{application_id}/device/{device_eui}/event/up

# Example mosquitto subscription
mosquitto_sub -h localhost -p 1883 -t "application/+/device/+/event/up"
```

## 🔍 Supported Milesight Devices

| Device | Model | Sensors | Profile |
|--------|-------|---------|---------|
| WS202 | PIR & Light | Motion, Light Level, Battery | WS202-868M |
| WS203 | Temp & Humidity | Temperature, Humidity, Occupancy, Battery | WS203-868M |

Device decoders are automatically downloaded from the [official Milesight repository](https://github.com/Milesight-IoT/SensorDecoders).

## 🐛 Troubleshooting

### Gateway Connection Issues

```bash
# Check if gateway is sending data
docker-compose logs chirpstack-gateway-bridge

# Verify gateway configuration
python chirpstack_cli.py list-gateways
```

### Device Join Issues

```bash
# Check device configuration
python chirpstack_cli.py list-devices

# Verify device profile exists
python chirpstack_cli.py list-profiles

# Check ChirpStack logs
docker-compose logs chirpstack
```

### Authentication Problems

```bash
# Test API connectivity
python chirpstack_cli.py check-auth

# Regenerate API key in ChirpStack web UI if needed
```

### Python Environment Issues

```bash
# If commands fail, ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies if needed
uv sync

# Check if uv is installed
uv --version
```

### MQTT Connection Issues

```bash
# Check MQTT broker status  
docker-compose logs mosquitto

# Test MQTT connection
mosquitto_sub -h localhost -p 1883 -t "application/+/device/+/event/up"
```

## 📚 Additional Resources

- **[CLI Usage Guide](CLI_USAGE.md)**: Detailed CLI documentation
- **[Configuration Guide](CHIRPSTACK_CONFIG.md)**: Advanced configuration options
- **[ChirpStack Documentation](https://www.chirpstack.io/docs/)**: Official ChirpStack docs
- **[Milesight Documentation](https://www.milesight-iot.com/)**: Device manuals and specs
- **[LoRaWAN Specification](https://lora-alliance.org/)**: LoRaWAN technical details

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the GPL-3.0 License - see the [LICENSE.md](LICENSE.md) file for details.

## 🆘 Support

- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Discussions**: Use GitHub Discussions for questions and community support
- **ChirpStack**: Check [ChirpStack Community](https://forum.chirpstack.io/)
- **Milesight**: Contact [Milesight Support](https://www.milesight-iot.com/support/)

---

Made with ❤️ for the LoRaWAN and IoT community
