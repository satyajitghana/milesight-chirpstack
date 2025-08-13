import paho.mqtt.client as mqtt
import json
import os
import sys
import argparse
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
    """Load minimal configuration from JSON file (optional)"""
    global config
    
    # Set defaults for basic operation
    config = {
        "mqtt": {
            "broker_host": "localhost",
            "broker_port": 1883,
            "username": None,
            "password": None,
            "keepalive": 60
        },
        "dashboard": {
            "title": "ChirpStack IoT Dashboard",
            "refresh_rate": 2,
            "active_threshold_seconds": 120,
            "recent_threshold_seconds": 600
        }
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                file_config = json.load(f)
            
            # Merge file config with defaults
            config.update(file_config)
            console.print(f"✅ [green]Loaded configuration from '{config_file}'[/green]")
        except json.JSONDecodeError as e:
            console.print(f"❌ [yellow]Invalid JSON in config file: {e}. Using defaults.[/yellow]")
        except Exception as e:
            console.print(f"❌ [yellow]Error loading config: {e}. Using defaults.[/yellow]")
    else:
        console.print(f"💡 [yellow]No config file found. Using defaults. MQTT broker: {config['mqtt']['broker_host']}[/yellow]")
    
    return True

def device_matches_filters(device_data, filters):
    """Check if device matches the current filters"""
    if not filters:
        return True
    
    # Get device config for tag filtering
    device_config = None
    for device in config.get('devices', []):
        if device['dev_eui'].lower() == device_data.get('dev_eui', '').lower():
            device_config = device
            break
    
    if not device_config:
        return True  # Show devices without config
    
    tags = device_config.get('tags', {})
    
    # Check zone filter
    if filters.get('zone') and tags.get('zone') != filters['zone']:
        return False
    
    # Check function filter
    if filters.get('function') and tags.get('function') != filters['function']:
        return False
    
    # Check priority filter
    if filters.get('priority') and tags.get('priority') != filters['priority']:
        return False
    
    return True

def format_ws502_data(decoded_data):
    """Create a compact display for WS502 smart switch data"""
    lines = []
    
    # Switch status line
    switch_states = []
    for i in [1, 2]:
        switch_key = f'switch_{i}'
        if switch_key in decoded_data:
            state = decoded_data[switch_key]
            if state.lower() == 'on':
                switch_states.append(f"S{i}:[green]ON[/green]🟢")
            else:
                switch_states.append(f"S{i}:[dim]OFF[/dim]⚪")
    
    if switch_states:
        lines.append(f"💡 {' | '.join(switch_states)}")
    
    # Electrical measurements line
    electrical = []
    voltage = decoded_data.get('voltage')
    current = decoded_data.get('current')
    power = decoded_data.get('active_power')
    pf = decoded_data.get('power_factor')
    
    if isinstance(voltage, (int, float)):
        if 220 <= voltage <= 250:
            color = "green"
        elif (200 <= voltage < 220) or (250 < voltage <= 260):
            color = "yellow"
        else:
            color = "red"
        electrical.append(f"⚡[{color}]{voltage}V[/{color}]")
    
    if isinstance(current, (int, float)):
        if current < 10:
            color = "green"
        elif current <= 20:
            color = "yellow"
        else:
            color = "red"
        electrical.append(f"🔌[{color}]{current}A[/{color}]")
    
    if isinstance(power, (int, float)):
        if power < 1000:
            color = "green"
        elif power <= 2000:
            color = "yellow"
        else:
            color = "red"
        electrical.append(f"🔆[{color}]{power}W[/{color}]")
    
    if isinstance(pf, (int, float)):
        pf_percent = pf if pf > 2 else pf * 100
        if pf_percent >= 95:
            color = "green"
        elif pf_percent >= 85:
            color = "yellow"
        else:
            color = "red"
        electrical.append(f"📐[{color}]{pf_percent:.0f}%[/{color}]")
    
    if electrical:
        lines.append(" ".join(electrical))
    
    # Energy consumption
    energy = decoded_data.get('power_consumption')
    if isinstance(energy, (int, float)):
        if energy >= 1000:
            lines.append(f"🔋 {energy/1000:.1f}kWh")
        else:
            lines.append(f"🔋 {energy}Wh")
    
    # Change notifications
    changes = []
    for i in [1, 2]:
        change_key = f'switch_{i}_change'
        if decoded_data.get(change_key, '').lower() == 'yes':
            changes.append(f"🔁[yellow]S{i}[/yellow]")
    if changes:
        lines.append(" ".join(changes))
    
    return "\n".join(lines) if lines else None

def format_ct105_data(decoded_data):
    """Create a compact display for CT105 current sensor data"""
    lines = []
    measurements = []
    
    current = decoded_data.get('current')
    total_current = decoded_data.get('total_current')
    temperature = decoded_data.get('temperature')
    
    if isinstance(current, (int, float)):
        if current < 10:
            color = "green"
        elif current <= 20:
            color = "yellow"
        else:
            color = "red"
        measurements.append(f"🔌[{color}]{current}A[/{color}]")
    
    if isinstance(total_current, (int, float)):
        measurements.append(f"∑[cyan]{total_current}A[/cyan]")
    
    if isinstance(temperature, (int, float)):
        if temperature < 30:
            color = "green"
        elif temperature <= 50:
            color = "yellow"
        else:
            color = "red"
        measurements.append(f"🌡️[{color}]{temperature}°C[/{color}]")
    
    if measurements:
        lines.append(" | ".join(measurements))
    
    return "\n".join(lines) if lines else None

def format_sensor_value(key, value, device_profile=None):
    """Format sensor values based on key and device profile"""
    # Default icon mapping
    icon_map = {
        'battery': '🔋',
        'temperature': '🌡️',
        'humidity': '💧',
        'pir': '🚶',
        'motion': '🚶',
        'occupancy': '👤',
        'daylight': '💡',
        'light': '💡'
    }
    
    icon = icon_map.get(key.lower(), '📊')
    
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
    # WS502 Smart Switch specific fields
    elif key.lower() == 'voltage' and isinstance(value, (int, float)):
        # Color code voltage: green (220-250V), yellow (200-220V or 250-260V), red (outside)
        if 220 <= value <= 250:
            color = "green"
        elif (200 <= value < 220) or (250 < value <= 260):
            color = "yellow"
        else:
            color = "red"
        return f"⚡ [{color}]{value}V[/{color}]"
    elif key.lower() == 'current' and isinstance(value, (int, float)):
        # Color code current: green (<10A), yellow (10-20A), red (>20A)
        if value < 10:
            color = "green"
        elif value <= 20:
            color = "yellow"
        else:
            color = "red"
        return f"🔌 [{color}]{value}A[/{color}]"
    elif key.lower() == 'active_power' and isinstance(value, (int, float)):
        # Color code power: green (<1000W), yellow (1000-2000W), red (>2000W)
        if value < 1000:
            color = "green"
        elif value <= 2000:
            color = "yellow"
        else:
            color = "red"
        return f"🔆 [{color}]{value}W[/{color}]"
    elif key.lower() == 'power_factor' and isinstance(value, (int, float)):
        pf_percent = value if value > 2 else value * 100
        # Color code power factor: green (>95%), yellow (85-95%), red (<85%)
        if pf_percent >= 95:
            color = "green"
        elif pf_percent >= 85:
            color = "yellow"
        else:
            color = "red"
        return f"📐 PF:[{color}]{pf_percent:.0f}%[/{color}]"
    elif key.lower() == 'power_consumption' and isinstance(value, (int, float)):
        # Format energy consumption with units
        if value >= 1000:
            return f"🔋 {value/1000:.1f}kWh"
        else:
            return f"🔋 {value}Wh"
    elif key.lower() in ['switch_1', 'switch_2'] and isinstance(value, str):
        switch_num = key.split('_')[-1]
        if value.lower() == 'on':
            return f"💡 S{switch_num}:[green]ON[/green] 🟢"
        else:
            return f"💡 S{switch_num}:[dim]OFF[/dim] ⚪"
    elif key.lower() in ['switch_1_change', 'switch_2_change'] and isinstance(value, str):
        # Only show if 'yes'
        if value.lower() == 'yes':
            switch_num = key.split('_')[1]
            return f"🔁 [yellow]S{switch_num} Changed[/yellow]"
        return ""
    # CT105 specific fields
    elif key.lower() == 'total_current' and isinstance(value, (int, float)):
        return f"∑ [cyan]{value}A[/cyan] (Total)"
    elif key.lower() == 'temperature' and isinstance(value, (int, float)):
        # Standard temperature formatting
        if value < 0:
            color = "blue"
        elif value < 10:
            color = "cyan"
        elif value < 30:
            color = "green"
        elif value <= 50:
            color = "yellow"
        else:
            color = "red"
        return f"🌡️ [{color}]{value}°C[/{color}]"
    elif key.lower() == 'humidity' and isinstance(value, (int, float)):
        if value < 30:
            color = "yellow"  # Too dry
        elif value <= 60:
            color = "green"   # Comfortable
        else:
            color = "blue"    # High humidity
        return f"💧 [{color}]{value}%[/{color}]"
    else:
        # Standard formatting
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
    
    table.add_column("Device", style="cyan", min_width=22)
    table.add_column("Status", style="green", min_width=8)
    table.add_column("Sensor Data", style="white", min_width=35)
    table.add_column("Signal", style="orange1", min_width=15)
    table.add_column("Messages", style="blue", min_width=8)
    table.add_column("Last Seen", style="dim", min_width=10)
    
    if not device_data:
        table.add_row("No devices", "Waiting for data...", "", "", "", "")
        return table
    
    dashboard_config = config.get('dashboard', {})
    active_threshold = dashboard_config.get('active_threshold_seconds', 120)
    recent_threshold = dashboard_config.get('recent_threshold_seconds', 600)
    
    # Apply filters
    filters = config.get('filters', {})
    filtered_devices = {}
    for dev_eui, data in device_data.items():
        if device_matches_filters({**data, 'dev_eui': dev_eui}, filters):
            filtered_devices[dev_eui] = data
    
    for dev_eui, data in filtered_devices.items():
        # Use device info from MQTT messages directly
        device_name_str = data.get('device_name', 'Unknown Device')
        device_profile = data.get('device_profile', 'Unknown Profile')
        
        # Add tags if requested
        display_name = f"[bold]{device_name_str}[/bold]\n[dim]{device_profile}[/dim]"
        
        if filters.get('show_tags'):
            device_config = None
            for device in config.get('devices', []):
                if device['dev_eui'].lower() == dev_eui.lower():
                    device_config = device
                    break
            
            if device_config and device_config.get('tags'):
                tags = device_config['tags']
                zone = tags.get('zone', '')
                function = tags.get('function', '')
                priority = tags.get('priority', '')
                tag_display = []
                if zone:
                    tag_display.append(f"🏢{zone}")
                if function:
                    tag_display.append(f"⚙️{function}")
                if priority:
                    tag_display.append(f"🔥{priority}")
                
                if tag_display:
                    display_name += f"\n[dim cyan]{' | '.join(tag_display)}[/dim cyan]"
        
        device_name = f"{display_name}\n[dim]{dev_eui[-8:]}[/dim]"
        
        # Status indicator based on config thresholds
        time_diff = (datetime.now() - datetime.strptime(data.get('last_seen', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S')).seconds
        if time_diff < active_threshold:
            status = "🟢 Active"
        elif time_diff < recent_threshold:
            status = "🟡 Recent"
        else:
            status = "🔴 Inactive"
        
        # Format sensor data with compact formatting for known device types
        decoded_data = data.get('decoded_data', {})
        
        # Use compact formatting for specific device types
        if decoded_data:
            if 'WS502' in device_profile:
                data_str = format_ws502_data(decoded_data)
                if not data_str:
                    data_str = "No WS502 data"
            elif 'CT105' in device_profile or 'CT10' in device_profile or 'current' in device_profile.lower():
                data_str = format_ct105_data(decoded_data)
                if not data_str:
                    data_str = "No CT105 data"
            else:
                # Standard formatting for other devices
                sensor_data = []
                for key, value in decoded_data.items():
                    formatted_value = format_sensor_value(key, value, device_profile)
                    if formatted_value:
                        sensor_data.append(formatted_value)
                data_str = "\n".join(sensor_data) if sensor_data else "No data"
        else:
            data_str = "No data"
        
        # Signal quality
        rssi = data.get('rssi', 'N/A')
        snr = data.get('snr', 'N/A')
        if isinstance(rssi, (int, float)):
            signal_quality = "🔴 Poor" if rssi < -80 else "🟡 Fair" if rssi < -60 else "🟢 Good"
            snr_str = f"{snr} dB" if isinstance(snr, (int, float)) else str(snr)
            signal_str = f"{signal_quality}\nRSSI: {rssi} dBm\nSNR: {snr_str}"
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
        
        # Try to get application ID from config, otherwise subscribe to all
        app_id = config.get('chirpstack', {}).get('application_id')
        if app_id:
            topic = f"application/{app_id}/#"
            client.subscribe(topic)
            console.print(f"📡 [cyan]Subscribed to application events: {app_id}[/cyan]")
        else:
            # Subscribe to all applications if no specific app ID
            topic = "application/+/device/+/event/up"
            client.subscribe(topic)
            console.print(f"📡 [cyan]Subscribed to all application events[/cyan]")
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
        device_name = device_info.get('deviceName')
        device_profile = device_info.get('deviceProfileName')
        
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
            'spreading_factor': payload.get('txInfo', {}).get('modulation', {}).get('lora', {}).get('spreadingFactor'),
            'device_name': device_name,
            'device_profile': device_profile
        })
        
    except Exception as e:
        console.print(f"❌ [red]Error processing message: {e}[/red]")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='ChirpStack IoT Dashboard - Generic MQTT Reader')
    parser.add_argument('--broker', '-b', default='localhost', help='MQTT broker host (default: localhost)')
    parser.add_argument('--port', '-p', type=int, default=1883, help='MQTT broker port (default: 1883)')
    parser.add_argument('--username', '-u', help='MQTT username')
    parser.add_argument('--password', '-P', help='MQTT password')
    parser.add_argument('--app-id', '-a', help='ChirpStack application ID (if omitted, listens to all)')
    parser.add_argument('--config', '-c', default='config.json', help='Config file path (default: config.json)')
    parser.add_argument('--zone', '-z', help='Filter devices by zone (e.g., executive, workspace, meeting)')
    parser.add_argument('--function', '-f', help='Filter devices by function (e.g., lighting_control, power_monitoring)')
    parser.add_argument('--priority', help='Filter devices by priority (e.g., high, critical)')
    parser.add_argument('--show-tags', action='store_true', help='Show device tags in the display')
    
    args = parser.parse_args()
    
    console.print("🚀 [bold]Starting ChirpStack IoT Dashboard...[/bold]")
    console.print(f"📡 [cyan]Connecting to MQTT broker: {args.broker}:{args.port}[/cyan]")
    
    # Show active filters
    active_filters = []
    if args.zone:
        active_filters.append(f"Zone: {args.zone}")
    if args.function:
        active_filters.append(f"Function: {args.function}")
    if args.priority:
        active_filters.append(f"Priority: {args.priority}")
    if args.show_tags:
        active_filters.append("Tags: ON")
    
    if active_filters:
        console.print(f"🔍 [yellow]Active filters: {' | '.join(active_filters)}[/yellow]")
    else:
        console.print("🌐 [green]Showing all devices (no filters)[/green]")
    
    # Load configuration (optional) and override with command line args
    load_config(args.config)
    
    # Override config with command line arguments
    if args.broker != 'localhost':
        config.setdefault('mqtt', {})['broker_host'] = args.broker
    if args.port != 1883:
        config.setdefault('mqtt', {})['broker_port'] = args.port
    if args.username:
        config.setdefault('mqtt', {})['username'] = args.username
    if args.password:
        config.setdefault('mqtt', {})['password'] = args.password
    if args.app_id:
        config.setdefault('chirpstack', {})['application_id'] = args.app_id
    
    # Store filter options
    config['filters'] = {
        'zone': args.zone,
        'function': args.function,
        'priority': args.priority,
        'show_tags': args.show_tags
    }
    
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
