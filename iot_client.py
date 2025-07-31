import paho.mqtt.client as mqtt
import json
import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
import threading
import time

# Global variables
device_data = {}
config = {}
console = Console()
message_count = 0

def load_config(config_file="config.json"):
    """Load configuration from JSON file"""
    global config
    
    if not os.path.exists(config_file):
        console.print(f"❌ [red]Configuration file '{config_file}' not found![/red]")
        console.print(f"💡 [yellow]Please create a config.json file with your settings[/yellow]")
        return False
    
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        console.print(f"✅ [green]Loaded configuration from '{config_file}'[/green]")
        return True
    except json.JSONDecodeError as e:
        console.print(f"❌ [red]Invalid JSON in config file: {e}[/red]")
        return False
    except Exception as e:
        console.print(f"❌ [red]Error loading config: {e}[/red]")
        return False

def get_device_config(dev_eui):
    """Get device configuration by EUI"""
    for device in config.get('devices', []):
        if device['dev_eui'] == dev_eui:
            return device
    return None

def format_sensor_value(key, value, device_config):
    """Format sensor values using device configuration"""
    if not device_config:
        return f"{key}: {value}"
    
    # Find sensor config
    sensor_config = None
    for sensor in device_config.get('sensors', []):
        if sensor['key'].lower() == key.lower():
            sensor_config = sensor
            break
    
    if not sensor_config:
        return f"{key}: {value}"
    
    icon = sensor_config.get('icon', '📊')
    unit = sensor_config.get('unit', '')
    
    # Special formatting based on sensor type
    if key.lower() == 'battery' and isinstance(value, (int, float)):
        color = "green" if value >= 75 else "yellow" if value >= 25 else "red"
        return f"{icon} {value}% [{color}]({color})[/{color}]"
    elif key.lower() in ['pir', 'motion'] and isinstance(value, str):
        if value.lower() in ['trigger', 'triggered', 'motion']:
            return f"{icon} Motion Detected"
        else:
            return f"{icon} {value}"
    elif key.lower() == 'occupancy' and isinstance(value, str):
        if value.lower() == 'occupied':
            return f"{icon} Occupied"
        elif value.lower() == 'vacant':
            return f"{icon} Vacant"
        else:
            return f"{icon} {value}"
    elif key.lower() in ['daylight', 'light'] and isinstance(value, str):
        if value.lower() == 'bright':
            return f"☀️  Bright"
        elif value.lower() == 'dim':
            return f"🌙 Dim"
        else:
            return f"{icon} {value}"
    else:
        # Standard formatting
        if unit and unit != 'state':
            return f"{icon} {value}{unit}"
        else:
            return f"{icon} {value}"

def create_gateway_table():
    """Create a table showing gateway information"""
    table = Table(title="📡 ChirpStack Gateways", show_header=True, header_style="bold cyan")
    
    table.add_column("Gateway ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Status", style="green")
    table.add_column("Location", style="yellow")
    table.add_column("Devices", style="white")
    table.add_column("Last Activity", style="blue")
    
    # Add gateways from config
    for gateway in config.get('gateways', []):
        active_devices = len(device_data)
        last_activity = max([data.get('last_seen', '') for data in device_data.values()]) if device_data else 'Never'
        
        table.add_row(
            gateway['id'],
            gateway.get('name', 'Unknown'),
            "🟢 Online",
            gateway.get('location', 'Unknown'),
            f"{active_devices} active",
            last_activity
        )
    
    if not config.get('gateways'):
        table.add_row("No gateways", "configured", "", "", "", "")
    
    return table

def create_devices_table():
    """Create a table showing all devices and their latest data"""
    table = Table(title="🌐 IoT Devices - Live Sensor Data", show_header=True, header_style="bold magenta")
    
    table.add_column("Device", style="cyan", min_width=20)
    table.add_column("Status", style="green", min_width=8)
    table.add_column("Sensor Data", style="white", min_width=30)
    table.add_column("Signal", style="orange1", min_width=15)
    table.add_column("Messages", style="blue", min_width=8)
    table.add_column("Last Seen", style="dim", min_width=12)
    
    if not device_data:
        table.add_row("No devices", "Waiting for data...", "", "", "", "")
        return table
    
    dashboard_config = config.get('dashboard', {})
    active_threshold = dashboard_config.get('active_threshold_seconds', 120)
    recent_threshold = dashboard_config.get('recent_threshold_seconds', 600)
    
    for dev_eui, data in device_data.items():
        device_config = get_device_config(dev_eui)
        
        if device_config:
            device_name = f"[bold]{device_config['name']}[/bold]\n[dim]{device_config['type']}[/dim]\n[dim]{device_config.get('location', 'Unknown')}[/dim]\n[dim]{dev_eui[-8:]}[/dim]"
        else:
            device_name = f"[bold]Unknown Device[/bold]\n[dim]{dev_eui[-8:]}[/dim]"
        
        # Status indicator based on config thresholds
        time_diff = (datetime.now() - datetime.strptime(data.get('last_seen', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S')).seconds
        if time_diff < active_threshold:
            status = "🟢 Active"
        elif time_diff < recent_threshold:
            status = "🟡 Recent"
        else:
            status = "🔴 Inactive"
        
        # Format sensor data using device config
        sensor_data = []
        if 'decoded_data' in data and data['decoded_data']:
            for key, value in data['decoded_data'].items():
                formatted_value = format_sensor_value(key, value, device_config)
                sensor_data.append(formatted_value)
        
        data_str = "\n".join(sensor_data) if sensor_data else "No data"
        
        # Signal quality
        rssi = data.get('rssi', 'N/A')
        snr = data.get('snr', 'N/A')
        if rssi != 'N/A':
            signal_quality = "🔴 Poor" if rssi < -80 else "🟡 Fair" if rssi < -60 else "🟢 Good"
            signal_str = f"{signal_quality}\nRSSI: {rssi} dBm\nSNR: {snr} dB"
        else:
            signal_str = "No signal data"
        
        # Message count
        msg_count = data.get('message_count', 0)
        
        # Time formatting
        last_seen_time = data.get('last_seen', 'Never')
        if last_seen_time != 'Never':
            last_seen_time = last_seen_time.split(' ')[1]  # Just the time part
        
        table.add_row(
            device_name,
            status,
            data_str,
            signal_str,
            str(msg_count),
            last_seen_time
        )
    
    return table

def create_stats_panel():
    """Create a panel showing system statistics"""
    stats_text = Text()
    
    # Calculate stats
    total_messages = sum(data.get('message_count', 0) for data in device_data.values())
    
    dashboard_config = config.get('dashboard', {})
    active_threshold = dashboard_config.get('active_threshold_seconds', 120)
    
    active_devices = len([d for d in device_data.values() 
                         if (datetime.now() - datetime.strptime(d.get('last_seen', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S')).seconds < active_threshold])
    
    configured_devices = len(config.get('devices', []))
    configured_gateways = len(config.get('gateways', []))
    
    stats_text.append("📊 System Statistics\n\n", style="bold cyan")
    stats_text.append(f"📈 Total Messages: ", style="white")
    stats_text.append(f"{total_messages}\n", style="bold green")
    stats_text.append(f"🌐 Active Devices: ", style="white")
    stats_text.append(f"{active_devices}/{configured_devices}\n", style="bold blue")
    stats_text.append(f"📡 Gateways Online: ", style="white")
    stats_text.append(f"{configured_gateways}\n", style="bold green")
    stats_text.append(f"⏰ Last Update: ", style="white")
    stats_text.append(f"{datetime.now().strftime('%H:%M:%S')}", style="bold yellow")
    
    return Panel(stats_text, title="📈 Dashboard", border_style="green", expand=False)

def create_connection_panel():
    """Create a panel showing connection information"""
    conn_text = Text()
    
    mqtt_config = config.get('mqtt', {})
    chirpstack_config = config.get('chirpstack', {})
    
    broker_host = mqtt_config.get('broker_host', 'localhost')
    broker_port = mqtt_config.get('broker_port', 1883)
    app_id = chirpstack_config.get('application_id', 'N/A')
    
    conn_text.append("🔗 MQTT Connection\n\n", style="bold blue")
    conn_text.append("📡 Broker: ", style="white")
    conn_text.append(f"{broker_host}:{broker_port}\n", style="cyan")
    conn_text.append("🔐 Auth: ", style="white")
    
    if mqtt_config.get('username'):
        conn_text.append("Enabled\n", style="green")
    else:
        conn_text.append("None\n", style="yellow")
    
    conn_text.append("📋 App ID: ", style="white")
    conn_text.append(f"{app_id[:8]}...\n", style="dim")
    conn_text.append("📊 Status: ", style="white")
    conn_text.append("🟢 Connected", style="bold green")
    
    return Panel(conn_text, title="🌐 Connection", border_style="blue", expand=False)

def create_layout():
    """Create the main layout"""
    layout = Layout()
    
    # Split into header, main content, and footer
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="gateways", size=8),
        Layout(name="devices", ratio=1),
        Layout(name="footer", size=12)
    )
    
    # Split footer into two columns
    layout["footer"].split_row(
        Layout(name="stats"),
        Layout(name="connection")
    )
    
    # Get dashboard title from config
    dashboard_title = config.get('dashboard', {}).get('title', 'ChirpStack IoT Dashboard')
    
    # Add content to each section
    layout["header"].update(Panel(
        Text(f"🌐 {dashboard_title}", justify="center", style="bold magenta"), 
        style="bold magenta"
    ))
    layout["gateways"].update(create_gateway_table())
    layout["devices"].update(create_devices_table())
    layout["stats"].update(create_stats_panel())
    layout["connection"].update(create_connection_panel())
    
    return layout

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        console.print("✅ [bold green]Connected to ChirpStack MQTT broker![/bold green]")
        
        # Build topic from config
        app_id = config.get('chirpstack', {}).get('application_id')
        if app_id:
            topic = f"application/{app_id}/#"
            client.subscribe(topic)
            console.print(f"📡 [cyan]Subscribed to application events[/cyan]")
        else:
            console.print("❌ [red]No application ID configured![/red]")
    else:
        console.print(f"❌ [red]Connection failed with code {rc}[/red]")

def on_message(client, userdata, msg):
    global message_count, device_data
    
    try:
        message_count += 1
        payload = json.loads(msg.payload.decode())
        
        # Extract device information
        device_info = payload.get('deviceInfo', {})
        device_eui = device_info.get('devEui', 'Unknown')
        
        # Update device data
        if device_eui not in device_data:
            device_data[device_eui] = {'message_count': 0}
        
        device_data[device_eui].update({
            'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'message_count': device_data[device_eui]['message_count'] + 1,
            'decoded_data': payload.get('object', {}),
            'rssi': payload.get('rxInfo', [{}])[0].get('rssi') if payload.get('rxInfo') else None,
            'snr': payload.get('rxInfo', [{}])[0].get('snr') if payload.get('rxInfo') else None,
            'gateway_id': payload.get('rxInfo', [{}])[0].get('gatewayId') if payload.get('rxInfo') else None,
            'frequency': payload.get('txInfo', {}).get('frequency'),
            'spreading_factor': payload.get('txInfo', {}).get('modulation', {}).get('lora', {}).get('spreadingFactor')
        })
        
    except Exception as e:
        console.print(f"❌ [red]Error processing message: {e}[/red]")

def main():
    console.print("🚀 [bold]Starting ChirpStack IoT Dashboard...[/bold]")
    
    # Load configuration
    if not load_config():
        return
    
    # Get MQTT config
    mqtt_config = config.get('mqtt', {})
    broker_host = mqtt_config.get('broker_host', 'localhost')
    broker_port = mqtt_config.get('broker_port', 1883)
    username = mqtt_config.get('username')
    password = mqtt_config.get('password')
    keepalive = mqtt_config.get('keepalive', 60)
    
    # Create MQTT client
    client = mqtt.Client()
    
    # Set authentication if configured
    if username and password:
        client.username_pw_set(username, password)
        console.print(f"🔐 [yellow]Using authentication: {username}[/yellow]")
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect to broker
    try:
        console.print(f"🔄 [yellow]Connecting to {broker_host}:{broker_port}...[/yellow]")
        client.connect(broker_host, broker_port, keepalive)
    except Exception as e:
        console.print(f"❌ [bold red]Failed to connect: {e}[/bold red]")
        return
    
    # Start MQTT client in background
    mqtt_thread = threading.Thread(target=client.loop_forever)
    mqtt_thread.daemon = True
    mqtt_thread.start()
    
    console.print("📺 [cyan]Starting live dashboard... Press Ctrl+C to exit[/cyan]")
    
    # Get dashboard config
    dashboard_config = config.get('dashboard', {})
    refresh_rate = dashboard_config.get('refresh_rate', 2)
    
    # Start live display
    with Live(create_layout(), refresh_per_second=refresh_rate, screen=True) as live:
        try:
            while True:
                live.update(create_layout())
                time.sleep(0.5)
        except KeyboardInterrupt:
            console.print("\n👋 [yellow]Shutting down dashboard...[/yellow]")
            client.disconnect()

if __name__ == "__main__":
    main()
