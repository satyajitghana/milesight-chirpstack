# Milesight IoT Web Dashboard

A modern, responsive web dashboard for monitoring and controlling IoT devices through ChirpStack. Built with FastAPI, Tailwind CSS v4.1, BoxIcons, and real-time MQTT integration.

## 🌟 Features

- **Real-time Device Monitoring**: Live data visualization from IoT sensors
- **Smart Switch Control**: Interactive controls for WS502 smart switches
- **User Authentication**: Secure JWT-based authentication system
- **Modern UI Design**: Sleek, mobile-friendly interface with Tailwind CSS v4.1 and BoxIcons
- **Real-time Data Visualization**: Beautiful sensor data display with color-coded values
- **MQTT Integration**: Real-time data updates via MQTT subscriptions
- **SQLite Database**: Lightweight, file-based user storage
- **RESTful API**: Well-documented API endpoints following FastAPI best practices
- **Smooth Animations**: No-jitter refresh with elegant transitions

## 🏗️ Architecture

```
📁 app/
├── 📄 main.py              # FastAPI application entry point
├── 📄 models.py            # SQLModel database models
├── 📄 database.py          # Database configuration
├── 📄 auth.py              # Authentication utilities
├── 📄 mqtt_client.py       # MQTT client for real-time data
├── 📁 static/              # Static assets
│   ├── 📁 css/
│   │   └── 📄 styles.css   # Custom CSS styles
│   └── 📁 js/
│       ├── 📄 auth.js      # Authentication JavaScript
│       └── 📄 dashboard.js # Dashboard functionality
└── 📁 templates/           # Jinja2 HTML templates
    ├── 📄 base.html        # Base template
    ├── 📄 dashboard.html   # Main dashboard
    ├── 📄 login.html       # Login page
    └── 📄 register.html    # Registration page
```

## 🚀 Quick Start

### Prerequisites

- Python 3.13+
- ChirpStack server running
- MQTT broker configured
- `config.json` file with your ChirpStack and MQTT settings

### Installation

1. **Clone or navigate to your project directory**:
   ```bash
   cd milesight-chirpstack
   ```

2. **Install dependencies** (already installed via pyproject.toml):
   ```bash
   pip install -e .
   ```

3. **Ensure your `config.json` is properly configured**:
   ```json
   {
     "chirpstack": {
       "server_url": "localhost:8080",
       "api_key": "your-api-key",
       "application_id": "your-app-id",
       "application_name": "IoT Devices",
       "application_description": "Smart building IoT devices"
     },
     "mqtt": {
       "broker_host": "localhost",
       "broker_port": 1883,
       "username": "your-mqtt-username",
       "password": "your-mqtt-password"
     },
     "devices": [
       {
         "dev_eui": "device-eui-here",
         "name": "Smart Switch 1",
         "description": "WS502 Smart Switch",
         "tags": {
           "zone": "office",
           "function": "lighting_control"
         }
       }
     ]
   }
   ```

4. **Start the web server**:
   ```bash
   python -m app.main
   ```

   Or using uvicorn directly:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload
   ```

5. **Access the dashboard**:
   Open your browser and navigate to: `http://localhost:4000`

## 👤 User Authentication

### First Time Setup

1. **Navigate to the registration page**: `http://localhost:4000/register`
2. **Create your account** with:
   - Email address
   - Username
   - Full name (optional)
   - Password
3. **You'll be automatically logged in** and redirected to the dashboard

### Subsequent Logins

1. **Go to**: `http://localhost:4000/login`
2. **Enter your credentials** and sign in
3. **Your session will persist** for 7 days

## 📊 Dashboard Features

### Device Status Monitoring

- **Real-time status indicators**:
  - 🟢 **Online**: Last seen < 2 minutes ago
  - 🟡 **Recent**: Last seen < 10 minutes ago
  - 🔴 **Offline**: Last seen > 10 minutes ago

- **Device information display**:
  - Device name and description
  - EUI (last 8 characters)
  - Message count
  - Signal strength (RSSI/SNR)
  - Last seen timestamp

### Smart Switch Controls

For WS502 smart switch devices, the dashboard provides:

- **Individual switch control**: Turn each switch ON/OFF independently
- **Bulk control**: Turn all switches ON/OFF simultaneously
- **Real-time status**: See current switch states
- **Visual feedback**: Color-coded status indicators

### Sensor Data Visualization

- **Automatic data formatting** for common sensor types:
  - Temperature (°C)
  - Humidity (%)
  - Voltage (V)
  - Current (A)
  - Power (W)
  - Battery level (%)

### Auto-refresh

- **Automatic updates** every 30 seconds
- **Manual refresh** button available
- **Toggle auto-refresh** on/off
- **Real-time MQTT updates** for immediate data

## 🔧 API Endpoints

### Authentication

- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/me` - Get current user info

### Device Management

- `GET /api/devices` - Get all devices with live data
- `GET /api/devices/{dev_eui}` - Get specific device
- `POST /api/devices/{dev_eui}/control` - Control device switches

### System Statistics

- `GET /api/stats` - Get dashboard statistics

### Example API Usage

```bash
# Login
curl -X POST "http://localhost:4000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=your-email@example.com&password=your-password"

# Control a switch (requires authentication token)
curl -X POST "http://localhost:4000/api/devices/YOUR_DEVICE_EUI/control" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "on", "switch": "switch_1"}'
```

## 🎨 Customization

### Styling

The dashboard uses Tailwind CSS v4.1 with custom themes defined in:
- `app/static/css/styles.css` - Custom CSS and animations
- `app/templates/base.html` - Base Tailwind configuration

### Custom Colors

```css
@theme {
  --color-primary: #3b82f6;    /* Blue */
  --color-secondary: #10b981;  /* Green */
  --color-danger: #ef4444;     /* Red */
  --color-warning: #f59e0b;    /* Yellow */
  --color-success: #22c55e;    /* Green */
}
```

### Adding New Device Types

To support new device types, modify:

1. **Frontend**: Update `app/static/js/dashboard.js`
   - Add device detection logic
   - Create custom render functions
   - Add specific control interfaces

2. **Backend**: Update `app/main.py`
   - Add device-specific API endpoints
   - Implement control logic

## 🔒 Security

### Authentication Security

- **JWT tokens** with 7-day expiration
- **bcrypt password hashing** with automatic salting
- **Secure token storage** in localStorage
- **Automatic token validation** on all protected routes

### Production Security Recommendations

1. **Change the secret key** in `app/auth.py`:
   ```python
   SECRET_KEY = "your-super-secret-production-key-change-this"
   ```

2. **Use HTTPS** in production
3. **Set secure environment variables**:
   ```bash
   export CHIRPSTACK_API_KEY="your-production-api-key"
   export JWT_SECRET_KEY="your-production-jwt-secret"
   ```

4. **Configure proper CORS** for your domain
5. **Use a production database** (PostgreSQL recommended)

## 🐛 Troubleshooting

### Common Issues

1. **"Authentication required" errors**:
   - Clear browser localStorage: `localStorage.clear()`
   - Re-register or login again

2. **No device data showing**:
   - Check MQTT broker connection
   - Verify `config.json` has correct MQTT settings
   - Ensure devices are sending data to ChirpStack

3. **Switch controls not working**:
   - Check ChirpStack CLI integration
   - Verify device EUI matches configuration
   - Ensure device profile supports downlinks

4. **Database errors**:
   - Delete `iot_dashboard.db` to reset database
   - Check file permissions in project directory

### Debug Mode

Enable debug logging by setting:

```python
# In app/database.py
engine = create_engine(DATABASE_URL, echo=True)  # Set to False for production
```

### MQTT Debug

Check MQTT connection status in browser console and server logs:

```bash
# Start server with debug logging
uvicorn app.main:app --host 0.0.0.0 --port 4000 --log-level debug
```

## 📈 Performance

### Optimization Tips

1. **Database**: Use indexes for large device datasets
2. **MQTT**: Filter subscriptions to specific applications
3. **Frontend**: Enable gzip compression for static files
4. **Caching**: Implement Redis for session storage in production

### Monitoring

- **Device status**: Monitor via dashboard statistics
- **MQTT health**: Check connection status in footer
- **API performance**: Use FastAPI's built-in metrics
- **Database**: Monitor SQLite file size and queries

## 🤝 Integration

### With Existing ChirpStack CLI

The web dashboard integrates seamlessly with your existing `chirpstack_cli.py`:

- Uses the same `config.json` file
- Leverages switch control functions
- Shares device and gateway configurations

### With External Systems

- **REST API**: All data available via JSON endpoints
- **MQTT**: Subscribe to device events directly
- **Webhooks**: Extend API to send notifications
- **Database**: Direct SQLite access for reporting

## 📝 Development

### Local Development

```bash
# Start with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 4000 --reload

# Run with debug logging
uvicorn app.main:app --host 0.0.0.0 --port 4000 --log-level debug
```

### Adding Features

1. **New API endpoints**: Add to `app/main.py`
2. **Database models**: Extend `app/models.py`
3. **Frontend features**: Update templates and JavaScript
4. **Authentication**: Modify `app/auth.py`

## 📄 License

This project is part of the ChirpStack IoT Dashboard suite. Built with FastAPI, Tailwind CSS, and modern web technologies.

---

**🎉 Enjoy your new Milesight IoT dashboard!** 

For questions or issues, check the troubleshooting section above or refer to the ChirpStack and FastAPI documentation.

## 🎨 UI Features

### BoxIcons Integration
- **Modern Icons**: Uses BoxIcons for beautiful, consistent iconography
- **Temperature**: Thermometer icon with color-coded values
- **Humidity**: Droplet icon with humidity-based colors
- **Battery**: Battery icon with charge level colors
- **Voltage**: Zap icon with safe/warning/danger colors
- **Current**: Trending icon with load-based colors
- **Motion/PIR**: Walk icon with detection states
- **Occupancy**: User-check icon with occupancy status

### Responsive Design
- **Mobile-first**: Optimized for all screen sizes
- **Touch-friendly**: Large touch targets for mobile devices
- **Gradient Themes**: Beautiful gradient backgrounds and buttons
- **Smooth Animations**: Fade-in effects and hover transitions
