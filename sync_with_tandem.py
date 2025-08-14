#!/usr/bin/env python3
"""
Tandem IoT Data Sync Script

This script syncs real IoT device data from ChirpStack MQTT to Autodesk Tandem.
It reads device mappings from a Google Spreadsheet and monitors MQTT for real device data.

Usage:
    python sync_with_tandem.py [options]

Requirements:
    - Google Service Account JSON file
    - MQTT access to ChirpStack
    - Internet connectivity for Tandem API
"""

import base64
import json
import os
import sys
import argparse
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import paho.mqtt.client as mqtt
import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text

# --- Constants ---
SERVICE_ACCOUNT_FILE = "inkers-prj-prod-d4938382ee15.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]  # Write access needed for updating last_updated
SPREADSHEET_ID = "1CkkPYp2TC_REGmOgwdtggdu0UJiT2zhudIm0apiTmtA"
RANGE_NAME = "Sheet1!A2:F"  # Skip header row: type, eui, location, sensor_type, tandem_url, last_updated

# --- Timezone ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- Global Variables ---
console = Console()
device_mappings = {}  # EUI -> device config mapping
device_data = {}      # Real-time device data from MQTT
sync_stats = {
    'total_synced': 0,
    'total_errors': 0,
    'last_sync_time': None,
    'active_devices': set(),
    'configured_devices': 0
}
mqtt_connected = False

def update_iot_dashboard(eui: str, real_data: Dict, device_config: Dict, sync_time: str) -> bool:
    """Update the IoT Dashboard worksheet with current sensor states grouped by location."""
    try:
        # Authenticate with Google Sheets API
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=creds)
        
        # Check if IoT Dashboard worksheet exists, create if not
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheet_names = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
        
        dashboard_sheet_name = "IoT Dashboard"
        if dashboard_sheet_name not in sheet_names:
            # Create the IoT Dashboard worksheet
            create_dashboard_worksheet(service)
        
        # Get current dashboard data
        dashboard_range = f"{dashboard_sheet_name}!A:Z"
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=dashboard_range
        ).execute()
        
        values = result.get("values", [])
        
        # Find or create row for this device
        device_name = real_data.get('device_name', 'Unknown Device')
        location = device_config.get('location', 'Unknown Location')
        sensor_type = device_config.get('sensor_type', 'Unknown Type')
        decoded_data = real_data.get('decoded_data', {})
        
        # Find existing row for this device (search by EUI in column B)
        target_row = None
        
        for row_idx, row in enumerate(values):
            if len(row) > 1 and row[1] == eui:  # EUI is in column B (index 1)
                target_row = row_idx + 1  # +1 because sheets are 1-indexed
                break
        
        # Prepare the row data
        sensor_values = []
        for key, value in decoded_data.items():
            if key not in ['timestamp']:  # Skip timestamp as we have our own
                sensor_values.append(f"{key}: {value}")
        
        signal_quality = ""
        if real_data.get('rssi') is not None and real_data.get('snr') is not None:
            signal_quality = f"RSSI: {real_data['rssi']}dBm, SNR: {real_data['snr']}dB"
        
        device_row = [
            location,
            eui,
            device_name,
            sensor_type,
            " | ".join(sensor_values) if sensor_values else "No data",
            signal_quality,
            sync_time,
            "🟢 Active"
        ]
        
        if target_row:
            # Update existing row
            update_range = f"{dashboard_sheet_name}!A{target_row}:H{target_row}"
            update_body = {'values': [device_row]}
            
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=update_range,
                valueInputOption='RAW',
                body=update_body
            ).execute()
        else:
            # Add new device - find the right location section or create it
            insert_device_in_dashboard(service, dashboard_sheet_name, device_row, location)
        
        console.print(f"✅ [dim]Updated dashboard for {eui}[/dim]")
        return True
        
    except Exception as e:
        console.print(f"❌ [red]Dashboard update error for {eui}: {str(e)}[/red]")
        return False

def create_dashboard_worksheet(service) -> bool:
    """Create the IoT Dashboard worksheet with headers and formatting."""
    try:
        # Create new worksheet
        body = {
            'requests': [{
                'addSheet': {
                    'properties': {
                        'title': 'IoT Dashboard',
                        'gridProperties': {
                            'rowCount': 1000,
                            'columnCount': 10
                        }
                    }
                }
            }]
        }
        
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body=body
        ).execute()
        
        # Add headers and initial structure
        headers = [
            ["🌐 INKERS OFFICE IoT SYSTEM DASHBOARD", "", "", "", "", "", "", ""],
            [f"Last Updated: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')}", "", "", "", "", "", "", ""],
            ["", "", "", "", "", "", "", ""],
            ["Location", "Device EUI", "Device Name", "Sensor Type", "Current Values", "Signal Quality", "Last Sync", "Status"]
        ]
        
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range="IoT Dashboard!A1:H4",
            valueInputOption='RAW',
            body={'values': headers}
        ).execute()
        
        console.print("✅ [green]Created IoT Dashboard worksheet[/green]")
        return True
        
    except Exception as e:
        console.print(f"❌ [red]Error creating dashboard worksheet: {e}[/red]")
        return False

def insert_device_in_dashboard(service, sheet_name: str, device_row: list, location: str) -> bool:
    """Insert a new device into the dashboard at the appropriate location."""
    try:
        # Get current dashboard data
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A5:H1000"  # Skip headers
        ).execute()
        
        values = result.get("values", [])
        
        # Find where to insert this device
        location_header = f"📍 {location.upper()}"
        insert_row = None
        
        # Look for existing location section
        for row_idx, row in enumerate(values):
            if len(row) > 0 and row[0] == location_header:
                # Found location header, find the end of this section
                section_end = row_idx + 2  # Skip header and spacing row
                while section_end < len(values) and len(values[section_end]) > 0 and not values[section_end][0].startswith("📍"):
                    section_end += 1
                insert_row = section_end + 5  # +5 to account for header offset
                break
        
        if insert_row is None:
            # Location doesn't exist, add it at the end
            last_row = len(values) + 5  # +5 for header offset
            
            # Add location header and device
            new_rows = [
                ["", "", "", "", "", "", "", ""],  # Spacing
                [location_header, "", "", "", "", "", "", ""],
                ["", "", "", "", "", "", "", ""],  # Spacing
                device_row
            ]
            
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!A{last_row}:H{last_row + len(new_rows) - 1}",
                valueInputOption='RAW',
                body={'values': new_rows}
            ).execute()
        else:
            # Insert device in existing location section
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!A{insert_row}:H{insert_row}",
                valueInputOption='RAW',
                body={'values': [device_row]}
            ).execute()
        
        return True
        
    except Exception as e:
        console.print(f"⚠️  [yellow]Error inserting device in dashboard: {e}[/yellow]")
        return False

def update_dashboard_structure(service, sheet_name: str) -> bool:
    """Reorganize the dashboard to group devices by location."""
    try:
        # Get all current device data
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A5:H"  # Skip headers
        ).execute()
        
        device_rows = result.get("values", [])
        
        # Group devices by location
        locations = {}
        for row in device_rows:
            if len(row) >= 8 and not row[0].startswith("📍"):
                location = row[0]
                if location not in locations:
                    locations[location] = []
                locations[location].append(row)
        
        # Rebuild the sheet structure
        new_rows = []
        
        for location, devices in sorted(locations.items()):
            # Add location header
            new_rows.append([f"📍 {location.upper()}", "", "", "", "", "", "", ""])
            new_rows.append(["", "", "", "", "", "", "", ""])  # Spacing
            
            # Add devices for this location
            for device_row in devices:
                new_rows.append(device_row)
            
            new_rows.append(["", "", "", "", "", "", "", ""])  # Spacing between locations
        
        # Clear existing data and write new structure
        if new_rows:
            # Clear old data
            service.spreadsheets().values().clear(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!A5:H1000"
            ).execute()
            
            # Write new structure
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{sheet_name}!A5:H{5 + len(new_rows) - 1}",
                valueInputOption='RAW',
                body={'values': new_rows}
            ).execute()
        
        return True
        
    except Exception as e:
        console.print(f"⚠️  [yellow]Error updating dashboard structure: {e}[/yellow]")
        return False

def update_spreadsheet_last_updated(eui: str, timestamp: str) -> bool:
    """Update the last_updated column in Google Spreadsheet for a specific device."""
    try:
        # Authenticate with Google Sheets API
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
        
        # First, find the row for this EUI
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID, 
            range="Sheet1!A2:F"  # Include all columns to find EUI
        ).execute()
        
        values = result.get("values", [])
        
        # Find the row containing this EUI
        target_row = None
        for row_idx, row in enumerate(values, start=2):  # Start from row 2 (after header)
            if len(row) >= 2 and row[1].lower() == eui.lower():  # EUI is in column B (index 1)
                target_row = row_idx
                break
        
        if target_row is None:
            console.print(f"⚠️  [yellow]Device {eui} not found in spreadsheet[/yellow]")
            return False
        
        # Update the last_updated column (column F)
        update_range = f"Sheet1!F{target_row}"
        update_body = {
            'values': [[timestamp]]
        }
        
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=update_range,
            valueInputOption='RAW',
            body=update_body
        ).execute()
        
        return True
        
    except Exception as e:
        # Don't spam errors for spreadsheet updates
        if not hasattr(update_spreadsheet_last_updated, '_error_logged'):
            console.print(f"⚠️  [yellow]Error updating spreadsheet: {e}[/yellow]")
            update_spreadsheet_last_updated._error_logged = True
        return False

def load_device_mappings() -> bool:
    """Load device mappings from Google Spreadsheet."""
    global device_mappings, sync_stats
    
    console.print("📊 [cyan]Loading device mappings from Google Spreadsheet...[/cyan]")
    
    try:
        # Authenticate with Google Sheets API
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=creds)
        
        # Read data from spreadsheet
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID, 
            range=RANGE_NAME
        ).execute()
        
        values = result.get("values", [])
        
        if not values:
            console.print("⚠️  [yellow]No device mappings found in spreadsheet[/yellow]")
            return False
        
        # Parse device mappings
        device_mappings.clear()
        valid_mappings = 0
        
        for row_idx, row in enumerate(values, start=2):  # Start from row 2 (after header)
            if len(row) < 5:  # Need at least type, eui, location, sensor_type, tandem_url
                console.print(f"⚠️  [yellow]Skipping incomplete row {row_idx}: {row}[/yellow]")
                continue
            
            device_type, eui, location, sensor_type, tandem_url = row[:5]
            last_updated = row[5] if len(row) > 5 else ""
            
            # Validate required fields
            if not eui or not tandem_url:
                console.print(f"⚠️  [yellow]Skipping row {row_idx} - missing EUI or Tandem URL[/yellow]")
                continue
            
            # Store mapping
            device_mappings[eui.lower()] = {
                'type': device_type,
                'eui': eui,
                'location': location,
                'sensor_type': sensor_type,
                'tandem_url': tandem_url,
                'last_updated': last_updated,
                'last_sync': None,
                'sync_count': 0,
                'error_count': 0
            }
            valid_mappings += 1
        
        sync_stats['configured_devices'] = valid_mappings
        console.print(f"✅ [green]Loaded {valid_mappings} device mappings from spreadsheet[/green]")
        
        return valid_mappings > 0
        
    except FileNotFoundError:
        console.print(f"❌ [red]Service account file not found: {SERVICE_ACCOUNT_FILE}[/red]")
        return False
    except HttpError as err:
        console.print(f"❌ [red]Google Sheets API error: {err}[/red]")
        return False
    except Exception as e:
        console.print(f"❌ [red]Error loading device mappings: {e}[/red]")
        return False

def send_to_tandem(device_config: Dict, real_data: Dict) -> bool:
    """Send real device data to Tandem API."""
    eui = device_config['eui']
    tandem_url = device_config['tandem_url']
    
    try:
        # Parse URL to extract credentials
        parsed_url = urlparse(tandem_url)
        secret = parsed_url.password
        
        if not secret:
            console.print(f"❌ [red]No secret found in Tandem URL for device {eui}[/red]")
            return False
        
        # Prepare API URL and authentication
        api_url = f"{parsed_url.scheme}://{parsed_url.hostname}{parsed_url.path}"
        auth_str = f":{secret}"
        b64_auth_str = base64.b64encode(auth_str.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {b64_auth_str}",
            "Content-Type": "application/json",
        }
        
        # Prepare payload with only decoded sensor data
        decoded_data = real_data.get('decoded_data', {})
        if not decoded_data:
            console.print(f"⚠️  [yellow]No decoded data available for device {eui}[/yellow]")
            return False
        
        # Send decoded sensor data with timestamp
        payload = decoded_data.copy()
        payload['timestamp'] = datetime.now(IST).isoformat()
        
        # Send to Tandem
        response = requests.post(api_url, headers=headers, json=payload, timeout=10)
        
        if response.ok:
            # Update sync statistics
            sync_time = datetime.now(IST).isoformat()
            device_config['last_sync'] = sync_time
            device_config['sync_count'] += 1
            sync_stats['total_synced'] += 1
            sync_stats['last_sync_time'] = sync_time
            
            # Update spreadsheet with last_updated timestamp
            update_spreadsheet_last_updated(eui, sync_time)
            
            # Update IoT Dashboard with current sensor state
            dashboard_success = update_iot_dashboard(eui, real_data, device_config, sync_time)
            if not dashboard_success and not hasattr(send_to_tandem, '_dashboard_mode'):
                console.print(f"⚠️  [yellow]Dashboard update failed for {eui}[/yellow]")
            
            # Only print success message if not in dashboard mode
            if not hasattr(send_to_tandem, '_dashboard_mode') or not send_to_tandem._dashboard_mode:
                console.print(f"✅ [green]Synced data for {eui} to Tandem[/green]")
            return True
        else:
            # Always print errors
            console.print(f"❌ [red]Failed to sync {eui} to Tandem: {response.status_code} - {response.text}[/red]")
            device_config['error_count'] += 1
            sync_stats['total_errors'] += 1
            return False
            
    except requests.exceptions.RequestException as e:
        console.print(f"❌ [red]Network error syncing {eui}: {e}[/red]")
        device_config['error_count'] += 1
        sync_stats['total_errors'] += 1
        return False
    except Exception as e:
        console.print(f"❌ [red]Error syncing {eui}: {e}[/red]")
        device_config['error_count'] += 1
        sync_stats['total_errors'] += 1
        return False

def on_connect(client, userdata, flags, rc):
    """MQTT connection callback."""
    global mqtt_connected
    
    if rc == 0:
        mqtt_connected = True
        console.print("✅ [bold green]Connected to ChirpStack MQTT broker![/bold green]")
        
        # Subscribe to all device events
        topic = "application/+/device/+/event/up"
        client.subscribe(topic)
        console.print(f"📡 [cyan]Subscribed to all device events: {topic}[/cyan]")
    else:
        mqtt_connected = False
        console.print(f"❌ [red]MQTT connection failed with code {rc}[/red]")

def on_disconnect(client, userdata, rc):
    """MQTT disconnection callback."""
    global mqtt_connected
    mqtt_connected = False
    console.print(f"🔌 [yellow]Disconnected from MQTT broker (rc={rc})[/yellow]")

def on_message(client, userdata, msg):
    """MQTT message callback - processes real device data."""
    global device_data, sync_stats
    
    try:
        payload = json.loads(msg.payload.decode())
        
        # Extract device information
        device_info = payload.get('deviceInfo', {})
        device_eui = device_info.get('devEui', '').lower()
        device_name = device_info.get('deviceName', 'Unknown')
        device_profile = device_info.get('deviceProfileName', 'Unknown')
        
        if not device_eui:
            return
        
        # Update device data
        device_data[device_eui] = {
            'device_name': device_name,
            'device_profile': device_profile,
            'last_seen': datetime.now(IST).isoformat(),
            'decoded_data': payload.get('object', {}),
            'rssi': payload.get('rxInfo', [{}])[0].get('rssi') if payload.get('rxInfo') else None,
            'snr': payload.get('rxInfo', [{}])[0].get('snr') if payload.get('rxInfo') else None,
            'gateway_id': payload.get('rxInfo', [{}])[0].get('gatewayId') if payload.get('rxInfo') else None,
            'frequency': payload.get('txInfo', {}).get('frequency'),
            'spreading_factor': payload.get('txInfo', {}).get('modulation', {}).get('lora', {}).get('spreadingFactor'),
        }
        
        sync_stats['active_devices'].add(device_eui)
        
        # Check if this device should be synced to Tandem
        if device_eui in device_mappings:
            device_config = device_mappings[device_eui]
            real_data = device_data[device_eui]
            
            # Sync to Tandem in a separate thread to avoid blocking MQTT
            sync_thread = threading.Thread(
                target=send_to_tandem, 
                args=(device_config, real_data),
                daemon=True
            )
            sync_thread.start()
        
    except Exception as e:
        console.print(f"❌ [red]Error processing MQTT message: {e}[/red]")

def create_dashboard_layout():
    """Create dashboard layout showing sync status."""
    layout = Layout()
    
    # Split into sections
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="devices", ratio=1),
        Layout(name="footer", size=10)
    )
    
    # Split footer into stats and connection
    layout["footer"].split_row(
        Layout(name="stats"),
        Layout(name="status")
    )
    
    # Header
    layout["header"].update(Panel(
        Text("🔄 Tandem IoT Data Sync Dashboard", justify="center", style="bold cyan"), 
        style="bold cyan"
    ))
    
    # Device sync table
    layout["devices"].update(create_devices_table())
    
    # Stats panel
    layout["stats"].update(create_stats_panel())
    
    # Status panel
    layout["status"].update(create_status_panel())
    
    return layout

def create_devices_table():
    """Create table showing device sync status."""
    table = Table(title="📱 Device Sync Status", show_header=True, header_style="bold green")
    
    table.add_column("Device EUI", style="cyan", min_width=16)
    table.add_column("Location", style="yellow", min_width=15)
    table.add_column("Type", style="magenta", min_width=12)
    table.add_column("MQTT Status", style="green", min_width=12)
    table.add_column("Last Sync", style="blue", min_width=12)
    table.add_column("Sync Count", style="white", min_width=8)
    table.add_column("Errors", style="red", min_width=6)
    
    if not device_mappings:
        table.add_row("No devices", "configured", "", "", "", "", "")
        return table
    
    for eui, config in device_mappings.items():
        # MQTT status
        if eui in device_data:
            mqtt_status = "🟢 Active"
        else:
            mqtt_status = "🔴 No Data"
        
        # Last sync time
        last_sync = config.get('last_sync', 'Never')
        if last_sync != 'Never':
            try:
                sync_time = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
                last_sync = sync_time.strftime('%H:%M:%S')
            except:
                pass
        
        table.add_row(
            eui[:16] + "..." if len(eui) > 16 else eui,
            config['location'][:15],
            config['sensor_type'][:12],
            mqtt_status,
            last_sync,
            str(config.get('sync_count', 0)),
            str(config.get('error_count', 0))
        )
    
    return table

def create_stats_panel():
    """Create statistics panel."""
    stats_text = Text()
    
    stats_text.append("📊 Sync Statistics\n\n", style="bold cyan")
    stats_text.append(f"🔄 Total Synced: ", style="white")
    stats_text.append(f"{sync_stats['total_synced']}\n", style="bold green")
    stats_text.append(f"❌ Total Errors: ", style="white")
    stats_text.append(f"{sync_stats['total_errors']}\n", style="bold red")
    stats_text.append(f"📱 Active Devices: ", style="white")
    stats_text.append(f"{len(sync_stats['active_devices'])}\n", style="bold blue")
    stats_text.append(f"⚙️  Configured: ", style="white")
    stats_text.append(f"{sync_stats['configured_devices']}\n", style="bold yellow")
    
    last_sync = sync_stats.get('last_sync_time', 'Never')
    if last_sync != 'Never':
        try:
            sync_time = datetime.fromisoformat(last_sync.replace('Z', '+00:00'))
            last_sync = sync_time.strftime('%H:%M:%S')
        except:
            pass
    
    stats_text.append(f"⏰ Last Sync: ", style="white")
    stats_text.append(f"{last_sync}", style="bold magenta")
    
    return Panel(stats_text, title="📈 Statistics", border_style="green")

def create_status_panel():
    """Create connection status panel."""
    status_text = Text()
    
    status_text.append("🌐 Connection Status\n\n", style="bold blue")
    
    # MQTT Status
    mqtt_status = "🟢 Connected" if mqtt_connected else "🔴 Disconnected"
    status_text.append("📡 MQTT: ", style="white")
    status_text.append(f"{mqtt_status}\n", style="bold green" if mqtt_connected else "bold red")
    
    # Google Sheets Status
    sheets_status = "🟢 Loaded" if device_mappings else "🔴 Failed"
    status_text.append("📊 Sheets: ", style="white")
    status_text.append(f"{sheets_status}\n", style="bold green" if device_mappings else "bold red")
    
    # Tandem API Status
    recent_syncs = sum(1 for config in device_mappings.values() 
                      if config.get('last_sync') and 
                      (datetime.now(IST) - datetime.fromisoformat(config['last_sync'].replace('Z', '+00:00'))).seconds < 300)
    tandem_status = "🟢 Active" if recent_syncs > 0 else "🟡 Waiting"
    status_text.append("🔄 Tandem: ", style="white")
    status_text.append(f"{tandem_status}\n", style="bold green" if recent_syncs > 0 else "bold yellow")
    
    status_text.append(f"⏰ Runtime: ", style="white")
    status_text.append(f"{datetime.now().strftime('%H:%M:%S')}", style="bold cyan")
    
    return Panel(status_text, title="🔌 Status", border_style="blue")

def load_mqtt_config(config_file="config.json"):
    """Load MQTT configuration from config.json file."""
    mqtt_config = {
        "broker_host": "localhost",
        "broker_port": 1883,
        "username": None,
        "password": None,
        "keepalive": 60
    }
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Extract MQTT config
            if 'mqtt' in config_data:
                mqtt_section = config_data['mqtt']
                mqtt_config.update({
                    "broker_host": mqtt_section.get("broker_host", "localhost"),
                    "broker_port": mqtt_section.get("broker_port", 1883),
                    "username": mqtt_section.get("username"),
                    "password": mqtt_section.get("password"),
                    "keepalive": mqtt_section.get("keepalive", 60)
                })
                console.print(f"✅ [green]Loaded MQTT config from '{config_file}'[/green]")
            else:
                console.print(f"⚠️  [yellow]No MQTT section found in '{config_file}', using defaults[/yellow]")
                
        except json.JSONDecodeError as e:
            console.print(f"❌ [yellow]Invalid JSON in config file: {e}. Using defaults.[/yellow]")
        except Exception as e:
            console.print(f"❌ [yellow]Error loading config: {e}. Using defaults.[/yellow]")
    else:
        console.print(f"💡 [yellow]No config file found. Using defaults.[/yellow]")
    
    return mqtt_config

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Sync IoT data from ChirpStack to Autodesk Tandem')
    parser.add_argument('--broker', '-b', help='MQTT broker host (overrides config.json)')
    parser.add_argument('--port', '-p', type=int, help='MQTT broker port (overrides config.json)')
    parser.add_argument('--username', '-u', help='MQTT username (overrides config.json)')
    parser.add_argument('--password', '-P', help='MQTT password (overrides config.json)')
    parser.add_argument('--no-dashboard', action='store_true', help='Run without dashboard UI')
    parser.add_argument('--sync-interval', type=int, default=30, help='Dashboard refresh interval (seconds)')
    parser.add_argument('--config', '-c', default='config.json', help='Config file path (default: config.json)')
    
    args = parser.parse_args()
    
    console.print("🚀 [bold]Starting Tandem IoT Data Sync...[/bold]")
    
    # Load MQTT configuration from config.json
    mqtt_config = load_mqtt_config(args.config)
    
    # Override with command line arguments if provided
    if args.broker:
        mqtt_config['broker_host'] = args.broker
    if args.port:
        mqtt_config['broker_port'] = args.port
    if args.username:
        mqtt_config['username'] = args.username
    if args.password:
        mqtt_config['password'] = args.password
    
    # Load device mappings from Google Sheets
    if not load_device_mappings():
        console.print("❌ [red]Failed to load device mappings. Exiting.[/red]")
        return 1
    
    # Set up MQTT client
    client = mqtt.Client()
    if mqtt_config['username'] and mqtt_config['password']:
        client.username_pw_set(mqtt_config['username'], mqtt_config['password'])
        console.print(f"🔐 [yellow]Using MQTT authentication: {mqtt_config['username']}[/yellow]")
    else:
        console.print("🔓 [yellow]No MQTT authentication configured[/yellow]")
    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # Connect to MQTT broker
    try:
        console.print(f"🔄 [yellow]Connecting to MQTT broker: {mqtt_config['broker_host']}:{mqtt_config['broker_port']}[/yellow]")
        client.connect(mqtt_config['broker_host'], mqtt_config['broker_port'], mqtt_config['keepalive'])
    except Exception as e:
        console.print(f"❌ [red]Failed to connect to MQTT broker: {e}[/red]")
        return 1
    
    # Start MQTT client in background
    mqtt_thread = threading.Thread(target=client.loop_forever, daemon=True)
    mqtt_thread.start()
    
    if args.no_dashboard:
        # Run without dashboard - verbose mode
        send_to_tandem._dashboard_mode = False
        console.print("📈 [cyan]Monitoring and syncing data... Press Ctrl+C to exit[/cyan]")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n👋 [yellow]Shutting down...[/yellow]")
    else:
        # Run with live dashboard - quiet mode
        send_to_tandem._dashboard_mode = True
        console.print("📺 [cyan]Starting live dashboard... Press Ctrl+C to exit[/cyan]")
        
        # Give MQTT a moment to connect before starting dashboard
        time.sleep(2)
        
        with Live(create_dashboard_layout(), refresh_per_second=0.5, screen=True) as live:
            try:
                while True:
                    live.update(create_dashboard_layout())
                    time.sleep(2)  # Update every 2 seconds
            except KeyboardInterrupt:
                console.print("\n👋 [yellow]Shutting down dashboard...[/yellow]")
    
    client.disconnect()
    return 0

if __name__ == "__main__":
    sys.exit(main())
