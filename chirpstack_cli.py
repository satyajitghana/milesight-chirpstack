#!/usr/bin/env python3
"""
ChirpStack CLI Tool

A command-line interface for managing ChirpStack gateways, device profiles, and devices.
Built with Typer for a better user experience.

Usage:
    python chirpstack_cli.py [COMMAND] [OPTIONS]

Commands:
    show-config         Show current configuration from config.json
    check-auth          Check if API authentication is working
    list-gateways       List all gateways
    add-gateway         Add a single gateway
    add-gateways        Add gateways from config.json or JSON file
    list-profiles       List all device profiles
    add-profiles        Add device profiles from config.json or JSON file
    list-devices        List all devices
    add-devices         Add devices from config.json or JSON file
    list-applications   List all applications
    switch-control      Interactive CLI switch control interface for WS502 devices

Author: AI Assistant
Date: 2025
"""

import json
import os
import sys
from typing import Optional, List
from datetime import datetime
import grpc
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
import requests
from chirpstack_api import api
from chirpstack_api.common import common_pb2 as common
import threading
import time
import paho.mqtt.client as mqtt
import json

# Initialize Typer app and Rich console
app = typer.Typer(help="ChirpStack CLI Tool for managing gateways, device profiles, and devices")
console = Console()

# Global configuration - will be loaded from config.json
CONFIG_FILE = "config.json"
config_data = None

def load_config():
    """Load configuration from config.json"""
    global config_data
    if config_data is None:
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
        except Exception as e:
            console.print(f"❌ [red]Failed to load config from {CONFIG_FILE}: {e}[/red]")
            raise typer.Exit(1)
    return config_data

class ChirpStackCLI:
    def __init__(self, api_key: str, server_url: str):
        """Initialize the ChirpStack CLI client"""
        self.api_key = api_key
        self.server_url = server_url
        self.channel = None
        self.setup_clients()
    
    def setup_clients(self):
        """Setup gRPC clients"""
        try:
            self.channel = grpc.insecure_channel(self.server_url)
            self.tenant_client = api.TenantServiceStub(self.channel)
            self.gateway_client = api.GatewayServiceStub(self.channel)
            self.device_profile_client = api.DeviceProfileServiceStub(self.channel)
            self.application_client = api.ApplicationServiceStub(self.channel)
            self.device_client = api.DeviceServiceStub(self.channel)
        except Exception as e:
            console.print(f"❌ [red]Failed to setup gRPC clients: {e}[/red]")
            raise typer.Exit(1)
    
    def get_auth_metadata(self):
        """Get authentication metadata"""
        return [("authorization", f"Bearer {self.api_key}")]
    
    def get_tenant_id(self):
        """Get the default tenant ID"""
        try:
            req = api.ListTenantsRequest()
            req.limit = 10  # Set a reasonable limit
            req.offset = 0  # Start from the beginning
            resp = self.tenant_client.List(req, metadata=self.get_auth_metadata())
            
            if resp.result and len(resp.result) > 0:
                return resp.result[0].id
            else:
                console.print("❌ [red]No tenants found[/red]")
                return None
        except Exception as e:
            console.print(f"❌ [red]Failed to get tenant ID: {e}[/red]")
            return None
    
    def cleanup(self):
        """Cleanup resources"""
        if self.channel:
            self.channel.close()

# Global client instance
client = None

def get_client():
    """Get or create the global client instance"""
    global client
    if client is None:
        config = load_config()
        api_key = os.getenv("CHIRPSTACK_API_KEY", config['chirpstack']['api_key'])
        server_url = os.getenv("CHIRPSTACK_SERVER", config['chirpstack']['server_url'])
        client = ChirpStackCLI(api_key, server_url)
    return client

@app.command()
def show_config():
    """Show current configuration from config.json"""
    console.print("⚙️  [bold blue]ChirpStack Configuration[/bold blue]")
    
    try:
        config = load_config()
        
        # Display ChirpStack configuration
        console.print(f"\n🔧 [cyan]ChirpStack Settings:[/cyan]")
        console.print(f"   Server URL: [green]{config['chirpstack']['server_url']}[/green]")
        console.print(f"   API Key: [green]{'*' * 20}...{config['chirpstack']['api_key'][-8:]}[/green]")
        console.print(f"   Region: [green]{config['chirpstack']['region_name']} ({config['chirpstack']['region_id']})[/green]")
        console.print(f"   Application Name: [green]{config['chirpstack']['application_name']}[/green]")
        console.print(f"   Join EUI: [green]{config['chirpstack']['join_eui']}[/green]")
        
        # Display gateways
        gateways = config.get('gateways', [])
        console.print(f"\n📡 [cyan]Gateways ({len(gateways)}):[/cyan]")
        for gateway in gateways:
            console.print(f"   - [green]{gateway['name']}[/green] ({gateway['gateway_id']})")
            console.print(f"     Location: {gateway.get('latitude', 'N/A')}, {gateway.get('longitude', 'N/A')}")
        
        # Display device profiles
        profiles = config.get('device_profiles', [])
        console.print(f"\n📋 [cyan]Device Profiles ({len(profiles)}):[/cyan]")
        for profile in profiles:
            console.print(f"   - [green]{profile['name']}[/green] - {profile['description']}")
        
        # Display devices
        devices = config.get('devices', [])
        console.print(f"\n📱 [cyan]Devices ({len(devices)}):[/cyan]")
        for device in devices:
            console.print(f"   - [green]{device['name']}[/green] ({device['dev_eui']})")
            console.print(f"     Location: {device.get('location', 'N/A')}, Type: {device.get('type', 'N/A')}")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to load configuration: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def check_auth():
    """Check if API authentication is working"""
    console.print("🔐 [bold blue]Checking ChirpStack Authentication[/bold blue]")
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if tenant_id:
            console.print(f"✅ [green]Authentication successful![/green]")
            console.print(f"📋 [cyan]Tenant ID: {tenant_id}[/cyan]")
            console.print(f"🌐 [cyan]Server: {cli.server_url}[/cyan]")
        else:
            console.print("❌ [red]Authentication failed or no tenants found[/red]")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"❌ [red]Authentication check failed: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def list_gateways():
    """List all gateways"""
    console.print("📡 [bold blue]Listing Gateways[/bold blue]")
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        req = api.ListGatewaysRequest()
        req.tenant_id = tenant_id
        req.limit = 100
        
        resp = cli.gateway_client.List(req, metadata=cli.get_auth_metadata())
        
        if not resp.result:
            console.print("📭 [yellow]No gateways found[/yellow]")
            return
        
        table = Table(title="ChirpStack Gateways")
        table.add_column("Gateway ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="yellow")
        table.add_column("Location", style="magenta")
        table.add_column("Last Seen", style="blue")
        
        for gateway in resp.result:
            try:
                if hasattr(gateway, 'last_seen_at') and gateway.last_seen_at and hasattr(gateway.last_seen_at, 'ToDatetime'):
                    last_seen = gateway.last_seen_at.ToDatetime().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    last_seen = "Never"
            except:
                last_seen = "Never"
            
            try:
                location = f"{gateway.location.latitude:.6f}, {gateway.location.longitude:.6f}" if gateway.location and hasattr(gateway.location, 'latitude') else "Not set"
            except:
                location = "Not set"
            
            table.add_row(
                gateway.gateway_id,
                gateway.name,
                gateway.description or "No description",
                location,
                last_seen
            )
        
        console.print(table)
        console.print(f"\n📊 [green]Total gateways: {len(resp.result)}[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to list gateways: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def add_gateway(
    gateway_id: str = typer.Option(..., "--id", help="Gateway ID (8 bytes hex)"),
    name: str = typer.Option(..., "--name", help="Gateway name"),
    description: str = typer.Option("", "--description", help="Gateway description"),
    latitude: float = typer.Option(0.0, "--lat", help="Gateway latitude"),
    longitude: float = typer.Option(0.0, "--lon", help="Gateway longitude"),
    altitude: float = typer.Option(0.0, "--alt", help="Gateway altitude"),
):
    """Add a new gateway"""
    console.print(f"📡 [bold blue]Adding Gateway: {name}[/bold blue]")
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        # Check if gateway already exists
        try:
            req = api.GetGatewayRequest()
            req.gateway_id = gateway_id
            cli.gateway_client.Get(req, metadata=cli.get_auth_metadata())
            console.print(f"✅ [yellow]Gateway {gateway_id} already exists[/yellow]")
            return
        except grpc.RpcError as e:
            if e.code() != grpc.StatusCode.NOT_FOUND:
                raise e
        
        # Create gateway
        gateway = api.Gateway()
        gateway.gateway_id = gateway_id
        gateway.name = name
        gateway.description = description
        gateway.tenant_id = tenant_id
        
        # Add region tags from config
        config = load_config()
        gateway.tags['region_id'] = config['chirpstack']['region_id']
        gateway.tags['region_name'] = config['chirpstack']['region_name']
        
        # Set stats interval to 30 seconds
        gateway.stats_interval = 30
        
        # Set location if provided
        if latitude != 0.0 or longitude != 0.0:
            location = common.Location()
            location.latitude = latitude
            location.longitude = longitude
            location.altitude = altitude
            location.source = common.LocationSource.UNKNOWN
            gateway.location.CopyFrom(location)
        
        req = api.CreateGatewayRequest()
        req.gateway.CopyFrom(gateway)
        
        cli.gateway_client.Create(req, metadata=cli.get_auth_metadata())
        
        console.print(f"✅ [green]Gateway '{name}' ({gateway_id}) created successfully![/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to add gateway: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def add_gateways(
    from_config: bool = typer.Option(True, "--from-config", help="Load gateways from config.json"),
    file: str = typer.Option("gateways.json", "--file", "-f", help="JSON file with gateways (if not using config)"),
    force: bool = typer.Option(False, "--force", help="Force creation even if gateway exists")
):
    """Add gateways from config.json or JSON file"""
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        # Load gateways from config.json or separate file
        if from_config:
            console.print(f"📡 [bold blue]Adding Gateways from {CONFIG_FILE}[/bold blue]")
            config = load_config()
            gateways = config.get('gateways', [])
        else:
            console.print(f"📡 [bold blue]Adding Gateways from {file}[/bold blue]")
            if not os.path.exists(file):
                console.print(f"❌ [red]File {file} not found[/red]")
                raise typer.Exit(1)
            with open(file, 'r') as f:
                gateways = json.load(f)
        
        if not gateways:
            console.print("❌ [red]No gateways found in configuration[/red]")
            raise typer.Exit(1)
        
        console.print(f"📂 [cyan]Loaded {len(gateways)} gateways from configuration[/cyan]")
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing gateways...", total=len(gateways))
            
            for gateway_config in gateways:
                gateway_id = gateway_config['gateway_id']
                gateway_name = gateway_config['name']
                
                # Check if gateway exists
                try:
                    req = api.GetGatewayRequest()
                    req.gateway_id = gateway_id
                    cli.gateway_client.Get(req, metadata=cli.get_auth_metadata())
                    
                    if not force:
                        console.print(f"⏭️  [yellow]Skipping existing gateway: {gateway_name} ({gateway_id})[/yellow]")
                        skipped_count += 1
                        progress.advance(task)
                        continue
                except grpc.RpcError as e:
                    if e.code() != grpc.StatusCode.NOT_FOUND:
                        console.print(f"❌ [red]Error checking gateway {gateway_id}: {e}[/red]")
                        error_count += 1
                        progress.advance(task)
                        continue
                
                # Create gateway
                if _create_gateway(cli, tenant_id, gateway_config):
                    created_count += 1
                    console.print(f"✅ [green]Created gateway: {gateway_name} ({gateway_id})[/green]")
                else:
                    error_count += 1
                
                progress.advance(task)
        
        console.print(f"\n📊 [green]Summary: {created_count} created, {skipped_count} skipped, {error_count} errors[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to add gateways: {e}[/red]")
        raise typer.Exit(1)

def _create_gateway(cli, tenant_id, gateway_config):
    """Helper function to create a gateway"""
    try:
        gateway = api.Gateway()
        gateway.gateway_id = gateway_config['gateway_id']
        gateway.name = gateway_config['name']
        gateway.description = gateway_config['description']
        gateway.tenant_id = tenant_id
        
        # Set location if provided
        if gateway_config.get('latitude') and gateway_config.get('longitude'):
            location = common.Location()
            location.latitude = gateway_config['latitude']
            location.longitude = gateway_config['longitude']
            location.altitude = gateway_config.get('altitude', 0.0)
            location.source = common.LocationSource.UNKNOWN
            gateway.location.CopyFrom(location)
        
        # Add tags (including region information)
        config = load_config()
        gateway.tags['region_id'] = config['chirpstack']['region_id']
        gateway.tags['region_name'] = config['chirpstack']['region_name']
        for key, value in gateway_config.get('tags', {}).items():
            gateway.tags[key] = str(value)
        
        # Set stats interval to 30 seconds
        gateway.stats_interval = 30
        
        req = api.CreateGatewayRequest()
        req.gateway.CopyFrom(gateway)
        
        cli.gateway_client.Create(req, metadata=cli.get_auth_metadata())
        return True
    except Exception as e:
        console.print(f"❌ [red]Error creating gateway: {e}[/red]")
        return False

@app.command()
def list_profiles():
    """List all device profiles"""
    console.print("📋 [bold blue]Listing Device Profiles[/bold blue]")
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        req = api.ListDeviceProfilesRequest()
        req.tenant_id = tenant_id
        req.limit = 100
        
        resp = cli.device_profile_client.List(req, metadata=cli.get_auth_metadata())
        
        if not resp.result:
            console.print("📭 [yellow]No device profiles found[/yellow]")
            return
        
        table = Table(title="ChirpStack Device Profiles")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="yellow")
        table.add_column("Region", style="magenta")
        table.add_column("MAC Version", style="blue")
        table.add_column("OTAA", style="red")
        
        for profile_item in resp.result:
            # Get full profile details to access description
            try:
                get_req = api.GetDeviceProfileRequest()
                get_req.id = profile_item.id
                full_profile_resp = cli.device_profile_client.Get(get_req, metadata=cli.get_auth_metadata())
                profile = full_profile_resp.device_profile
                
                # Get region and mac version names
                region_name = "Unknown"
                mac_version_name = "Unknown"
                
                try:
                    if hasattr(profile, 'region') and profile.region is not None:
                        region_name = common.Region.Name(profile.region)
                except:
                    region_name = "Unknown"
                    
                try:
                    if hasattr(profile, 'mac_version') and profile.mac_version is not None:
                        mac_version_name = common.MacVersion.Name(profile.mac_version)
                except:
                    mac_version_name = "Unknown"
                
                description = profile.description or "No description"
                
            except Exception as e:
                # Fallback to basic info if Get fails
                console.print(f"⚠️  [yellow]Warning: Could not fetch full details for profile {profile_item.name}: {e}[/yellow]")
                profile = profile_item
                region_name = common.Region.Name(profile_item.region) if hasattr(profile_item, 'region') else "Unknown"
                mac_version_name = common.MacVersion.Name(profile_item.mac_version) if hasattr(profile_item, 'mac_version') else "Unknown"
                description = "No description"
            
            table.add_row(
                profile_item.id[:8] + "...",
                profile_item.name,
                description,
                region_name,
                mac_version_name,
                "✅" if getattr(profile, 'supports_otaa', False) else "❌"
            )
        
        console.print(table)
        console.print(f"\n📊 [green]Total device profiles: {len(resp.result)}[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to list device profiles: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def add_profiles(
    from_config: bool = typer.Option(True, "--from-config", help="Load device profiles from config.json"),
    file: str = typer.Option("device_profiles.json", "--file", "-f", help="JSON file with device profiles (if not using config)"),
    force: bool = typer.Option(False, "--force", help="Force creation even if profile exists")
):
    """Add device profiles from config.json or JSON file"""
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        # Load profiles from config.json or separate file
        if from_config:
            console.print(f"📋 [bold blue]Adding Device Profiles from {CONFIG_FILE}[/bold blue]")
            config = load_config()
            profiles = config.get('device_profiles', [])
        else:
            console.print(f"📋 [bold blue]Adding Device Profiles from {file}[/bold blue]")
            if not os.path.exists(file):
                console.print(f"❌ [red]File {file} not found[/red]")
                raise typer.Exit(1)
            with open(file, 'r') as f:
                profiles = json.load(f)
        
        if not profiles:
            console.print("❌ [red]No device profiles found in configuration[/red]")
            raise typer.Exit(1)
        
        console.print(f"📂 [cyan]Loaded {len(profiles)} profiles from configuration[/cyan]")
        
        # Get existing profiles
        existing_profiles = {}
        req = api.ListDeviceProfilesRequest()
        req.tenant_id = tenant_id
        req.limit = 100
        resp = cli.device_profile_client.List(req, metadata=cli.get_auth_metadata())
        
        for profile in resp.result:
            existing_profiles[profile.name] = profile.id
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing profiles...", total=len(profiles))
            
            for profile_config in profiles:
                profile_name = profile_config['name']
                existing_profile_id = existing_profiles.get(profile_name)
                
                if _create_device_profile(cli, tenant_id, profile_config, existing_profile_id):
                    if existing_profile_id:
                        updated_count += 1
                    else:
                        created_count += 1
                else:
                    error_count += 1
                
                progress.advance(task)
        
        console.print(f"\n📊 [green]Summary: {created_count} created, {updated_count} updated, {error_count} errors[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to add device profiles: {e}[/red]")
        raise typer.Exit(1)

def _create_device_profile(cli, tenant_id, profile_config, existing_profile_id=None):
    """Helper function to create or update a device profile"""
    try:
        # Load codec script from local path (preferred) or URL (fallback)
        codec_script = ""
        if profile_config.get('codec_script_path'):
            console.print(f"📄 [cyan]Loading local codec for {profile_config['name']} from {profile_config['codec_script_path']}[/cyan]")
            try:
                codec_path = profile_config['codec_script_path'] if os.path.isabs(profile_config['codec_script_path']) else os.path.join(os.getcwd(), profile_config['codec_script_path'])
                with open(codec_path, "r", encoding="utf-8") as f:
                    codec_script = f.read()
                console.print(f"✅ [green]Loaded codec script ({len(codec_script)} characters)[/green]")
            except Exception as e:
                console.print(f"❌ [red]Failed to read codec from path '{profile_config['codec_script_path']}': {e}[/red]")
                codec_script = ""
        elif profile_config.get('codec_script_url'):
            console.print(f"📥 [cyan]Downloading codec script for {profile_config['name']}...[/cyan]")
            response = requests.get(profile_config['codec_script_url'], timeout=30)
            response.raise_for_status()
            codec_script = response.text
        
        # Create or update device profile
        device_profile = api.DeviceProfile()
        if existing_profile_id:
            device_profile.id = existing_profile_id
        device_profile.name = profile_config['name']
        device_profile.description = profile_config['description']
        device_profile.tenant_id = tenant_id
        device_profile.region = common.Region.Value(profile_config['region'])
        device_profile.mac_version = common.MacVersion.Value(profile_config['mac_version'])
        device_profile.reg_params_revision = common.RegParamsRevision.Value(profile_config['regional_parameters_revision'])
        device_profile.adr_algorithm_id = profile_config['adr_algorithm_id']
        device_profile.payload_codec_runtime = api.CodecRuntime.Value("JS")
        device_profile.payload_codec_script = codec_script
        device_profile.flush_queue_on_activate = profile_config['flush_queue_on_activate']
        device_profile.uplink_interval = profile_config['uplink_interval']
        device_profile.device_status_req_interval = profile_config['device_status_req_interval']
        device_profile.supports_otaa = profile_config['supports_otaa']
        device_profile.supports_class_b = profile_config['supports_class_b']
        device_profile.supports_class_c = profile_config['supports_class_c']
        device_profile.class_b_timeout = profile_config['class_b_timeout']
        device_profile.class_b_ping_slot_periodicity = profile_config['class_b_ping_slot_period']
        device_profile.class_b_ping_slot_dr = profile_config['class_b_ping_slot_dr']
        device_profile.class_b_ping_slot_freq = profile_config['class_b_ping_slot_freq']
        device_profile.class_c_timeout = profile_config['class_c_timeout']
        device_profile.abp_rx1_delay = profile_config['abp_rx1_delay']
        device_profile.abp_rx1_dr_offset = profile_config['abp_rx1_dr_offset']
        device_profile.abp_rx2_dr = profile_config['abp_rx2_dr']
        device_profile.abp_rx2_freq = profile_config['abp_rx2_freq']
        
        # Add tags
        for key, value in profile_config.get('tags', {}).items():
            device_profile.tags[key] = value
        
        # Add measurements
        for key, measurement in profile_config.get('measurements', {}).items():
            measurement_obj = api.Measurement()
            measurement_obj.kind = api.MeasurementKind.Value(measurement['kind'])
            measurement_obj.name = measurement['name']
            device_profile.measurements[key].CopyFrom(measurement_obj)
        
        # Enable automatic measurement detection
        device_profile.auto_detect_measurements = True
        
        if existing_profile_id:
            # Update existing profile
            req = api.UpdateDeviceProfileRequest()
            req.device_profile.CopyFrom(device_profile)
            cli.device_profile_client.Update(req, metadata=cli.get_auth_metadata())
            console.print(f"🔄 [green]Updated profile: {profile_config['name']} (ID: {existing_profile_id})[/green]")
        else:
            # Create new profile
            req = api.CreateDeviceProfileRequest()
            req.device_profile.CopyFrom(device_profile)
            cli.device_profile_client.Create(req, metadata=cli.get_auth_metadata())
            console.print(f"✅ [green]Created profile: {profile_config['name']}[/green]")
        return True
        
    except Exception as e:
        console.print(f"❌ [red]Error creating profile: {e}[/red]")
        return False

@app.command()
def list_applications():
    """List all applications"""
    console.print("🏢 [bold blue]Listing Applications[/bold blue]")
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        req = api.ListApplicationsRequest()
        req.tenant_id = tenant_id
        req.limit = 100
        
        resp = cli.application_client.List(req, metadata=cli.get_auth_metadata())
        
        if not resp.result:
            console.print("📭 [yellow]No applications found[/yellow]")
            return
        
        table = Table(title="ChirpStack Applications")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="yellow")
        
        for app in resp.result:
            table.add_row(
                app.id[:8] + "...",
                app.name,
                app.description or "No description"
            )
        
        console.print(table)
        console.print(f"\n📊 [green]Total applications: {len(resp.result)}[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to list applications: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def list_devices(
    application_id: Optional[str] = typer.Option(None, "--app-id", help="Filter by application ID")
):
    """List all devices"""
    console.print("📱 [bold blue]Listing Devices[/bold blue]")
    
    try:
        cli = get_client()
        
        if application_id:
            req = api.ListDevicesRequest()
            req.application_id = application_id
            req.limit = 100
            
            resp = cli.device_client.List(req, metadata=cli.get_auth_metadata())
        else:
            # If no application specified, we need to list all applications first
            tenant_id = cli.get_tenant_id()
            if not tenant_id:
                raise typer.Exit(1)
            
            app_req = api.ListApplicationsRequest()
            app_req.tenant_id = tenant_id
            app_req.limit = 100
            app_resp = cli.application_client.List(app_req, metadata=cli.get_auth_metadata())
            
            all_devices = []
            for app in app_resp.result:
                req = api.ListDevicesRequest()
                req.application_id = app.id
                req.limit = 100
                resp = cli.device_client.List(req, metadata=cli.get_auth_metadata())
                all_devices.extend(resp.result)
            
            # Create a mock response object
            class MockResponse:
                def __init__(self, devices):
                    self.result = devices
            resp = MockResponse(all_devices)
        
        if not resp.result:
            console.print("📭 [yellow]No devices found[/yellow]")
            return
        
        table = Table(title="ChirpStack Devices")
        table.add_column("Device EUI", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="yellow")
        table.add_column("Profile", style="magenta")
        table.add_column("Status", style="blue")
        
        for device in resp.result:
            status = "🔴 Disabled" if getattr(device, 'is_disabled', False) else "🟢 Enabled"
            
            table.add_row(
                device.dev_eui,
                device.name,
                getattr(device, 'description', 'No description') or "No description",
                getattr(device, 'device_profile_name', 'Unknown') or "Unknown",
                status
            )
        
        console.print(table)
        console.print(f"\n📊 [green]Total devices: {len(resp.result)}[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to list devices: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def get_device(
    dev_eui: str = typer.Argument(..., help="Device EUI to get details for"),
    show_keys: bool = typer.Option(True, "--show-keys/--no-keys", help="Show OTAA keys")
):
    """Get detailed information for a specific device including OTAA keys"""
    console.print(f"📱 [bold blue]Getting Device Details: {dev_eui}[/bold blue]")
    
    try:
        cli = get_client()
        
        # Get device details
        req = api.GetDeviceRequest()
        req.dev_eui = dev_eui
        resp = cli.device_client.Get(req, metadata=cli.get_auth_metadata())
        device = resp.device
        
        # Display device information
        console.print(f"\n📋 [cyan]Device Information:[/cyan]")
        console.print(f"   Device EUI: [green]{device.dev_eui}[/green]")
        console.print(f"   Name: [green]{device.name}[/green]")
        console.print(f"   Description: [green]{device.description or 'No description'}[/green]")
        console.print(f"   Application ID: [green]{device.application_id}[/green]")
        console.print(f"   Device Profile ID: [green]{device.device_profile_id}[/green]")
        console.print(f"   Join EUI: [green]{device.join_eui}[/green]")
        console.print(f"   Skip FCnt Check: [green]{device.skip_fcnt_check}[/green]")
        console.print(f"   Is Disabled: [green]{device.is_disabled}[/green]")
        
        # Display timestamps
        console.print(f"\n⏰ [cyan]Timestamps:[/cyan]")
        console.print(f"   Created: [green]{resp.created_at.ToDatetime().strftime('%Y-%m-%d %H:%M:%S') if resp.created_at else 'Unknown'}[/green]")
        console.print(f"   Updated: [green]{resp.updated_at.ToDatetime().strftime('%Y-%m-%d %H:%M:%S') if resp.updated_at else 'Unknown'}[/green]")
        console.print(f"   Last Seen: [green]{resp.last_seen_at.ToDatetime().strftime('%Y-%m-%d %H:%M:%S') if resp.last_seen_at else 'Never'}[/green]")
        
        # Display tags if any
        if device.tags:
            console.print(f"\n🏷️  [cyan]Tags:[/cyan]")
            for key, value in device.tags.items():
                console.print(f"   {key}: [green]{value}[/green]")
        
        # Display variables if any
        if device.variables:
            console.print(f"\n🔧 [cyan]Variables:[/cyan]")
            for key, value in device.variables.items():
                console.print(f"   {key}: [green]{value}[/green]")
        
        # Get and display OTAA keys if requested
        if show_keys:
            try:
                keys_req = api.GetDeviceKeysRequest()
                keys_req.dev_eui = dev_eui
                keys_resp = cli.device_client.GetKeys(keys_req, metadata=cli.get_auth_metadata())
                
                console.print(f"\n🔑 [cyan]OTAA Keys:[/cyan]")
                console.print(f"   Device EUI: [green]{keys_resp.device_keys.dev_eui}[/green]")
                console.print(f"   App Key: [green]{keys_resp.device_keys.app_key or 'Not set'}[/green]")
                console.print(f"   Network Key: [green]{keys_resp.device_keys.nwk_key or 'Not set'}[/green]")
                console.print(f"   Gen App Key: [green]{keys_resp.device_keys.gen_app_key or 'Not set'}[/green]")
                
                console.print(f"\n⏰ [cyan]Key Timestamps:[/cyan]")
                console.print(f"   Keys Created: [green]{keys_resp.created_at.ToDatetime().strftime('%Y-%m-%d %H:%M:%S') if keys_resp.created_at else 'Unknown'}[/green]")
                console.print(f"   Keys Updated: [green]{keys_resp.updated_at.ToDatetime().strftime('%Y-%m-%d %H:%M:%S') if keys_resp.updated_at else 'Unknown'}[/green]")
                
            except grpc.RpcError as e:
                if e.code() == grpc.StatusCode.NOT_FOUND:
                    console.print(f"\n🔑 [yellow]OTAA Keys: Not found (device may not have keys configured)[/yellow]")
                else:
                    console.print(f"\n❌ [red]Error getting OTAA keys: {e}[/red]")
        
        # Display device status if available
        if hasattr(resp, 'device_status') and resp.device_status:
            console.print(f"\n📊 [cyan]Device Status:[/cyan]")
            console.print(f"   Margin: [green]{resp.device_status.margin}[/green]")
            console.print(f"   External Power: [green]{resp.device_status.external_power_source}[/green]")
            console.print(f"   Battery Level: [green]{resp.device_status.battery_level}%[/green]")
        
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            console.print(f"❌ [red]Device not found: {dev_eui}[/red]")
        else:
            console.print(f"❌ [red]Error getting device: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"❌ [red]Failed to get device details: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def delete_all_devices(
    confirm: bool = typer.Option(False, "--confirm", help="Skip confirmation prompt")
):
    """Delete ALL devices from ChirpStack"""
    if not confirm:
        console.print("⚠️  [bold red]WARNING: This will delete ALL devices from ChirpStack![/bold red]")
        confirm_delete = typer.confirm("Are you sure you want to continue?")
        if not confirm_delete:
            console.print("❌ [yellow]Operation cancelled[/yellow]")
            raise typer.Exit(0)
    
    console.print("🗑️  [bold red]Deleting All Devices...[/bold red]")
    
    # Get device EUIs from config instead of API
    config = load_config()
    devices_config = config.get('devices', [])
    
    if not devices_config:
        console.print("ℹ️  [cyan]No devices found in config to delete[/cyan]")
        return
    
    console.print(f"Found {len(devices_config)} devices in config to delete...")
    
    try:
        cli = get_client()
        deleted_count = 0
        failed_count = 0
        
        for device_config in devices_config:
            try:
                # Delete device (ChirpStack will automatically delete associated keys)
                delete_req = api.DeleteDeviceRequest()
                delete_req.dev_eui = device_config['dev_eui']
                cli.device_client.Delete(delete_req, metadata=cli.get_auth_metadata())
                
                console.print(f"🗑️  [red]Deleted: {device_config['name']} ({device_config['dev_eui']})[/red]")
                deleted_count += 1
                
            except grpc.RpcError as e:
                if "NOT_FOUND" in str(e):
                    console.print(f"⚠️  [yellow]Device not found (already deleted): {device_config['name']} ({device_config['dev_eui']})[/yellow]")
                else:
                    console.print(f"❌ [red]Failed to delete {device_config['name']} ({device_config['dev_eui']}): {e}[/red]")
                    failed_count += 1
        
        console.print(f"\n📊 [cyan]Summary:[/cyan]")
        console.print(f"   Deleted: [green]{deleted_count}[/green]")
        console.print(f"   Failed: [red]{failed_count}[/red]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to delete devices: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def update_device_keys(
    dev_eui: str = typer.Argument(..., help="Device EUI to update keys for"),
    app_key: str = typer.Option(None, help="New application key (if not provided, uses config default)")
):
    """Update OTAA keys for a specific device"""
    console.print(f"🔑 [bold blue]Updating OTAA Keys for Device: {dev_eui}[/bold blue]")
    
    try:
        cli = get_client()
        config = load_config()
        
        # Use provided app_key or default from config
        if not app_key:
            app_key = config['chirpstack']['app_key']
        
        # Create device keys
        device_keys = api.DeviceKeys()
        device_keys.dev_eui = dev_eui
        device_keys.app_key = app_key
        
        try:
            # Try to update existing keys first
            keys_req = api.UpdateDeviceKeysRequest()
            keys_req.device_keys.CopyFrom(device_keys)
            cli.device_client.UpdateKeys(keys_req, metadata=cli.get_auth_metadata())
            console.print(f"🔄 [green]Updated OTAA keys for device: {dev_eui}[/green]")
            console.print(f"   App Key: [cyan]{app_key}[/cyan]")
            
        except grpc.RpcError as e:
            if "NOT_FOUND" in str(e):
                # Keys don't exist, create them
                keys_req = api.CreateDeviceKeysRequest()
                keys_req.device_keys.CopyFrom(device_keys)
                cli.device_client.CreateKeys(keys_req, metadata=cli.get_auth_metadata())
                console.print(f"✅ [green]Created OTAA keys for device: {dev_eui}[/green]")
                console.print(f"   App Key: [cyan]{app_key}[/cyan]")
            else:
                raise e
        
        # Verify the keys were set correctly
        console.print("\n🔍 [cyan]Verifying keys...[/cyan]")
        try:
            verify_req = api.GetDeviceKeysRequest()
            verify_req.dev_eui = dev_eui
            verify_resp = cli.device_client.GetKeys(verify_req, metadata=cli.get_auth_metadata())
            
            console.print(f"✅ [green]Verification successful:[/green]")
            console.print(f"   Device EUI: [cyan]{verify_resp.device_keys.dev_eui}[/cyan]")
            console.print(f"   App Key: [cyan]{verify_resp.device_keys.app_key}[/cyan]")
            console.print(f"   Network Key: [cyan]{verify_resp.device_keys.nwk_key}[/cyan]")
            
        except Exception as verify_error:
            console.print(f"⚠️  [yellow]Could not verify keys: {verify_error}[/yellow]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to update device keys: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def refresh_device_keys(
    dev_eui: str = typer.Argument(..., help="Device EUI to refresh keys for"),
    app_key: str = typer.Option(None, help="New application key (if not provided, uses config default)")
):
    """Force refresh OTAA keys by deleting and recreating them"""
    console.print(f"🔄 [bold blue]Force Refreshing OTAA Keys for Device: {dev_eui}[/bold blue]")
    
    try:
        cli = get_client()
        config = load_config()
        
        # Use provided app_key or default from config
        if not app_key:
            app_key = config['chirpstack']['app_key']
        
        # Step 1: Delete existing keys
        console.print("🗑️  [yellow]Deleting existing keys...[/yellow]")
        try:
            delete_req = api.DeleteDeviceKeysRequest()
            delete_req.dev_eui = dev_eui
            cli.device_client.DeleteKeys(delete_req, metadata=cli.get_auth_metadata())
            console.print("✅ [green]Existing keys deleted[/green]")
        except grpc.RpcError as e:
            if "NOT_FOUND" in str(e):
                console.print("ℹ️  [cyan]No existing keys found to delete[/cyan]")
            else:
                console.print(f"⚠️  [yellow]Warning: Could not delete existing keys: {e}[/yellow]")
        
        # Step 2: Wait a moment for the deletion to propagate
        import time
        time.sleep(1)
        
        # Step 3: Create new keys
        console.print("🔑 [cyan]Creating new keys...[/cyan]")
        device_keys = api.DeviceKeys()
        device_keys.dev_eui = dev_eui
        device_keys.app_key = app_key
        
        keys_req = api.CreateDeviceKeysRequest()
        keys_req.device_keys.CopyFrom(device_keys)
        cli.device_client.CreateKeys(keys_req, metadata=cli.get_auth_metadata())
        console.print(f"✅ [green]Created new OTAA keys for device: {dev_eui}[/green]")
        console.print(f"   App Key: [cyan]{app_key}[/cyan]")
        
        # Step 4: Verify the keys were set correctly
        console.print("\n🔍 [cyan]Verifying new keys...[/cyan]")
        try:
            verify_req = api.GetDeviceKeysRequest()
            verify_req.dev_eui = dev_eui
            verify_resp = cli.device_client.GetKeys(verify_req, metadata=cli.get_auth_metadata())
            
            console.print(f"✅ [green]Verification successful:[/green]")
            console.print(f"   Device EUI: [cyan]{verify_resp.device_keys.dev_eui}[/cyan]")
            console.print(f"   App Key: [cyan]{verify_resp.device_keys.app_key}[/cyan]")
            console.print(f"   Network Key: [cyan]{verify_resp.device_keys.nwk_key}[/cyan]")
            
            # Additional verification
            if verify_resp.device_keys.app_key == app_key:
                console.print("🎉 [bold green]App Key matches expected value![/bold green]")
            else:
                console.print("❌ [red]App Key mismatch![/red]")
                console.print(f"   Expected: [red]{app_key}[/red]")
                console.print(f"   Actual: [red]{verify_resp.device_keys.app_key}[/red]")
            
        except Exception as verify_error:
            console.print(f"⚠️  [yellow]Could not verify keys: {verify_error}[/yellow]")
        
        console.print(f"\n💡 [cyan]Please check the ChirpStack Web UI 'Keys (OTAA)' tab for device {dev_eui}[/cyan]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to refresh device keys: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def lights_on():
    """Turn ON all lights (WS502 devices)"""
    console.print("💡 [bold green]Turning ON all lights...[/bold green]")
    _control_all_lights("on")

@app.command()
def lights_off():
    """Turn OFF all lights (WS502 devices)"""
    console.print("🔌 [bold red]Turning OFF all lights...[/bold red]")
    _control_all_lights("off")

@app.command()
def control_light(
    dev_eui: str = typer.Argument(..., help="Device EUI of the WS502 switch"),
    action: str = typer.Argument(..., help="Action: 'on' or 'off'"),
    switch: str = typer.Option("both", "--switch", "-s", help="Which switch: 'switch_1', 'switch_2', or 'both'")
):
    """Control a specific light switch"""
    if action not in ["on", "off"]:
        console.print("❌ [red]Action must be 'on' or 'off'[/red]")
        raise typer.Exit(1)
    
    if switch not in ["switch_1", "switch_2", "both"]:
        console.print("❌ [red]Switch must be 'switch_1', 'switch_2', or 'both'[/red]")
        raise typer.Exit(1)
    
    console.print(f"💡 [cyan]Controlling light {dev_eui}: {action} ({switch})[/cyan]")
    
    if switch == "both":
        # Send separate commands for each switch
        _send_switch_command(dev_eui, action, "switch_1")
        _send_switch_command(dev_eui, action, "switch_2")
    else:
        _send_switch_command(dev_eui, action, switch)

def _control_all_lights(action):
    """Helper function to control all WS502 light switches"""
    try:
        config = load_config()
        devices = config.get('devices', [])
        
        # Filter for WS502 devices (smart switches)
        ws502_devices = []
        for device in devices:
            # Check if device has WS502 in the name or tags
            if ('WS502' in device.get('name', '') or 
                'WS502' in device.get('description', '') or
                any('WS502' in str(v) for v in device.get('tags', {}).values())):
                ws502_devices.append(device)
        
        if not ws502_devices:
            console.print("⚠️  [yellow]No WS502 light switches found in configuration[/yellow]")
            return
        
        console.print(f"Found {len(ws502_devices)} light switches to control...")
        
        success_count = 0
        failed_count = 0
        
        for device in ws502_devices:
            try:
                console.print(f"💡 [cyan]Controlling {device['name']} ({device['dev_eui']}): {action}[/cyan]")
                
                # Send separate commands for each switch since payload doesn't support both together
                _send_switch_command(device['dev_eui'], action, "switch_1")
                _send_switch_command(device['dev_eui'], action, "switch_2")
                
                success_count += 1
            except Exception as e:
                console.print(f"❌ [red]Failed to control {device['name']}: {e}[/red]")
                failed_count += 1
        
        console.print(f"\n📊 [cyan]Summary:[/cyan]")
        console.print(f"   Successful: [green]{success_count}[/green]")
        console.print(f"   Failed: [red]{failed_count}[/red]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to control lights: {e}[/red]")
        raise typer.Exit(1)

def _send_switch_command(dev_eui, action, switch_type):
    """Send switch command to a specific device"""
    try:
        cli = get_client()
        
        # Prepare the payload - only one switch at a time
        payload = {switch_type: action}
        
        # Create queue item
        queue_item = api.DeviceQueueItem()
        queue_item.dev_eui = dev_eui
        queue_item.confirmed = True
        queue_item.f_port = 85  # Standard fPort for downlink commands
        
        # Convert payload to JSON for the object field
        import json
        from google.protobuf.struct_pb2 import Struct
        
        # Use the object field which will be encoded by ChirpStack using the device profile codec
        payload_struct = Struct()
        payload_struct.update(payload)
        queue_item.object.CopyFrom(payload_struct)
        
        # Enqueue the message
        req = api.EnqueueDeviceQueueItemRequest()
        req.queue_item.CopyFrom(queue_item)
        
        resp = cli.device_client.Enqueue(req, metadata=cli.get_auth_metadata())
        
        console.print(f"✅ [green]Command sent successfully to {dev_eui}[/green]")
        console.print(f"   Queue ID: [cyan]{resp.id}[/cyan]")
        console.print(f"   Switch: [cyan]{switch_type} → {action}[/cyan]")
        console.print(f"   Payload: [cyan]{json.dumps(payload)}[/cyan]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to send command to {dev_eui}: {e}[/red]")
        raise e

@app.command()
def switch_control():
    """Interactive CLI switch control interface for WS502 devices with real-time status"""
    console.print("🎛️  [bold blue]Interactive Switch Control Interface[/bold blue]")
    console.print("🔌 [cyan]Loading WS502 smart switches...[/cyan]")
    
    try:
        config = load_config()
        devices = config.get('devices', [])
        
        # Filter for WS502 devices
        ws502_devices = []
        for device in devices:
            if ('WS502' in device.get('name', '') or 
                'WS502' in device.get('description', '') or
                any('WS502' in str(v) for v in device.get('tags', {}).values())):
                # Initialize device with unknown switch states
                device['switch_1_status'] = 'Unknown'
                device['switch_2_status'] = 'Unknown'
                device['last_update'] = 'Never'
                ws502_devices.append(device)
        
        if not ws502_devices:
            console.print("⚠️  [yellow]No WS502 smart switches found in configuration[/yellow]")
            return
        
        console.print(f"Found {len(ws502_devices)} smart switches")
        
        # Start interactive control loop with MQTT monitoring
        _interactive_switch_control_with_mqtt(ws502_devices, config)
        
    except Exception as e:
        console.print(f"❌ [red]Failed to load switch control interface: {e}[/red]")
        raise typer.Exit(1)

def _interactive_switch_control_with_mqtt(devices, config):
    """Interactive switch control with MQTT status monitoring"""
    
    # Global state for device status updates
    mqtt_connected = False
    last_mqtt_update = "Never"
    
    def on_mqtt_connect(client, userdata, flags, rc, properties=None):
        nonlocal mqtt_connected, last_mqtt_update
        if rc == 0:
            mqtt_connected = True
            last_mqtt_update = time.strftime("%H:%M:%S")
            # Subscribe to device uplink messages for all WS502 devices
            app_id = config.get('chirpstack', {}).get('application_id')
            if app_id:
                topic = f"application/{app_id}/device/+/event/up"
                client.subscribe(topic)
                console.print(f"🔔 [cyan]Subscribed to: {topic}[/cyan]")
        
    def on_mqtt_message(client, userdata, msg):
        nonlocal last_mqtt_update
        try:
            # Only process uplink messages
            if "/event/up" not in msg.topic:
                return
                
            payload = json.loads(msg.payload.decode())
            device_info = payload.get('deviceInfo', {})
            device_eui = device_info.get('devEui', '').lower()
            device_name = device_info.get('deviceName', '')
            decoded_data = payload.get('object', {})
            
            # Update device status if it's one of our WS502 devices and has switch data
            for device in devices:
                if device['dev_eui'].lower() == device_eui:
                    updated = False
                    if 'switch_1' in decoded_data:
                        device['switch_1_status'] = decoded_data['switch_1'].title()
                        updated = True
                    if 'switch_2' in decoded_data:
                        device['switch_2_status'] = decoded_data['switch_2'].title()
                        updated = True
                    
                    if updated:
                        device['last_update'] = time.strftime("%H:%M:%S")
                        last_mqtt_update = time.strftime("%H:%M:%S")
                        # Debug: Print status update
                        console.print(f"🔄 [green]Status updated for {device_name}: S1={device.get('switch_1_status', '?')}, S2={device.get('switch_2_status', '?')}[/green]", end='\r')
                    break
        except Exception as e:
            # Debug: show MQTT parsing errors
            console.print(f"🔧 [dim]MQTT parse error: {e}[/dim]", end='\r')
    
    def create_switch_panel():
        """Create the enhanced switch control panel with status"""
        layout = Layout()
        
        # Split into header, devices, and footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="devices"),
            Layout(name="footer", size=8)
        )
        
        # Header with MQTT status
        mqtt_status = "🟢 Connected" if mqtt_connected else "🔴 Disconnected"
        header_text = Text(f"🎛️  WS502 Smart Switch Control Panel - MQTT: {mqtt_status}", 
                          style="bold magenta", justify="center")
        layout["header"].update(Panel(header_text, style="bold blue"))
        
        # Device controls with current status - clearer mapping
        device_table = Table(title="🎛️  Switch Controls & Status (Device Commands Shown Clearly)", 
                            show_header=True, header_style="bold cyan")
        device_table.add_column("Device #", style="bold magenta", min_width=8)
        device_table.add_column("Device Name", style="cyan", min_width=25)
        device_table.add_column("Location", style="yellow", min_width=12)
        device_table.add_column("Switch 1", style="white", min_width=18)
        device_table.add_column("Switch 2", style="white", min_width=18)
        device_table.add_column("All Switches", style="white", min_width=15)
        device_table.add_column("Last Update", style="dim", min_width=10)
        
        for i, device in enumerate(devices):
            device_num = i + 1
            device_name = device['name']
            location = device.get('tags', {}).get('zone', 'Unknown')
            
            # Format current status with colors
            s1_status = device.get('switch_1_status', 'Unknown')
            s2_status = device.get('switch_2_status', 'Unknown')
            
            if s1_status.lower() == 'on':
                s1_status_display = f"[bold green]🟢 ON[/bold green]"
            elif s1_status.lower() == 'off':
                s1_status_display = f"[dim]⚪ OFF[/dim]"
            else:
                s1_status_display = f"[yellow]❓ {s1_status}[/yellow]"
                
            if s2_status.lower() == 'on':
                s2_status_display = f"[bold green]🟢 ON[/bold green]"
            elif s2_status.lower() == 'off':
                s2_status_display = f"[dim]⚪ OFF[/dim]"
            else:
                s2_status_display = f"[yellow]❓ {s2_status}[/yellow]"
            
            # Create VERY clear command mapping
            s1_commands = f"{s1_status_display}\n[bold green]a{device_num}[/bold green]=ON [bold red]b{device_num}[/bold red]=OFF"
            s2_commands = f"{s2_status_display}\n[bold green]c{device_num}[/bold green]=ON [bold red]d{device_num}[/bold red]=OFF"
            all_commands = f"[bold green]on{device_num}[/bold green]=ALL ON\n[bold red]off{device_num}[/bold red]=ALL OFF"
            
            device_table.add_row(
                f"[bold magenta]#{device_num}[/bold magenta]",
                device_name,
                location,
                s1_commands,
                s2_commands,
                all_commands,
                device.get('last_update', 'Never')
            )
        
        layout["devices"].update(device_table)
        
        # Footer with instructions
        footer_text = Text()
        footer_text.append("📝 Quick Command Reference (case insensitive):\n", style="bold cyan")
        footer_text.append("• Look at the table above - each switch shows its exact command next to the status\n", style="white")
        footer_text.append("• Example: For Device #1, use 'a1' to turn Switch 1 ON, 'b1' to turn it OFF\n", style="green")
        footer_text.append("• Example: For Device #2, use 'on2' to turn ALL switches ON, 'off2' to turn all OFF\n", style="green")
        footer_text.append("• General: 'h'=help, 'r'=refresh, 'q'=quit\n", style="white")
        footer_text.append(f"• MQTT Status: {mqtt_status} | Last Update: {last_mqtt_update}\n", style="cyan")
        footer_text.append("• Status updates automatically when devices report their state", style="green")
        
        layout["footer"].update(Panel(footer_text, title="Control Instructions", border_style="green"))
        
        return layout
    
    # Setup MQTT client for status monitoring
    mqtt_client = None
    try:
        mqtt_config = config.get('mqtt', {})
        if mqtt_config:
            # Use the new callback API version to avoid deprecation warning
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            mqtt_client.on_connect = on_mqtt_connect
            mqtt_client.on_message = on_mqtt_message
            
            if mqtt_config.get('username') and mqtt_config.get('password'):
                mqtt_client.username_pw_set(mqtt_config['username'], mqtt_config['password'])
            
            console.print(f"🔌 [cyan]Connecting to MQTT broker: {mqtt_config.get('broker_host', 'localhost')}:{mqtt_config.get('broker_port', 1883)}[/cyan]")
            
            # Connect in background
            mqtt_client.connect_async(
                mqtt_config.get('broker_host', 'localhost'),
                mqtt_config.get('broker_port', 1883),
                mqtt_config.get('keepalive', 60)
            )
            mqtt_client.loop_start()
    except Exception as e:
        console.print(f"⚠️  [yellow]MQTT setup failed: {e}. Status updates disabled.[/yellow]")
    
    # Start interactive loop
    try:
        console.print("\n🎮 [bold green]Starting Interactive Control with Live Status Updates...[/bold green]")
        console.print("💡 [yellow]Tip: Use simple commands like 'a1' for switch 1 ON, 'b1' for switch 1 OFF[/yellow]")
        
        # Give MQTT a moment to connect
        console.print("⏳ [cyan]Waiting for MQTT connection...[/cyan]")
        time.sleep(2)
        console.print()
        
        while True:
            # Display current interface
            layout = create_switch_panel()
            console.print(layout)
            
            # Get user input
            console.print("\n🎯 [cyan]Enter command (or 'h' for help, 'q' to quit):[/cyan]")
            choice = Prompt.ask("Command").strip().lower()
            
            if choice in ['q', 'quit', 'exit']:
                console.print("👋 [yellow]Goodbye![/yellow]")
                break
            elif choice in ['h', 'help']:
                _show_enhanced_help(devices)
                continue
            elif choice in ['r', 'refresh']:
                console.clear()
                continue
            
            # Process control commands with new simplified system
            try:
                success = _process_switch_command(choice, devices)
                if not success:
                    console.print(f"❌ [red]Invalid command: {choice}. Type 'h' for help.[/red]")
                    
            except Exception as e:
                console.print(f"❌ [red]Error processing command: {e}[/red]")
            
            # Brief pause before next iteration
            time.sleep(0.5)
            console.print("\n" + "="*100 + "\n")
    
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Control interface interrupted[/yellow]")
    except Exception as e:
        console.print(f"❌ [red]Error in control interface: {e}[/red]")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()

def _process_switch_command(command, devices):
    """Process switch control commands with new simplified system"""
    try:
        # Parse device number from command
        device_num = None
        
        # Extract device number from end of command
        if command[-1].isdigit():
            device_num = int(command[-1])
            command_prefix = command[:-1]
        else:
            return False
        
        # Check if device number is valid
        if device_num < 1 or device_num > len(devices):
            console.print(f"❌ [red]Invalid device number: {device_num}. Valid range: 1-{len(devices)}[/red]")
            return False
            
        device = devices[device_num - 1]
        device_name = device['name']
        dev_eui = device['dev_eui']
        
        # Process command
        if command_prefix == 'a':  # Switch 1 ON
            _send_switch_command(dev_eui, "on", "switch_1")
            console.print(f"✅ [green]Switch 1 ON sent to {device_name}[/green]")
            return True
        elif command_prefix == 'b':  # Switch 1 OFF
            _send_switch_command(dev_eui, "off", "switch_1")
            console.print(f"🔴 [red]Switch 1 OFF sent to {device_name}[/red]")
            return True
        elif command_prefix == 'c':  # Switch 2 ON
            _send_switch_command(dev_eui, "on", "switch_2")
            console.print(f"✅ [green]Switch 2 ON sent to {device_name}[/green]")
            return True
        elif command_prefix == 'd':  # Switch 2 OFF
            _send_switch_command(dev_eui, "off", "switch_2")
            console.print(f"🔴 [red]Switch 2 OFF sent to {device_name}[/red]")
            return True
        elif command_prefix == 'on':  # All ON
            _send_switch_command(dev_eui, "on", "switch_1")
            _send_switch_command(dev_eui, "on", "switch_2")
            console.print(f"✅ [bold green]ALL switches ON sent to {device_name}[/bold green]")
            return True
        elif command_prefix == 'off':  # All OFF
            _send_switch_command(dev_eui, "off", "switch_1")
            _send_switch_command(dev_eui, "off", "switch_2")
            console.print(f"🔴 [bold red]ALL switches OFF sent to {device_name}[/bold red]")
            return True
        
        return False
        
    except Exception as e:
        console.print(f"❌ [red]Error processing command: {e}[/red]")
        return False

def _show_enhanced_help(devices):
    """Show detailed help for enhanced switch control"""
    console.print("\n" + "="*100)
    console.print("📚 [bold blue]Enhanced Switch Control Help[/bold blue]\n")
    
    console.print("🎯 [cyan]Command Format:[/cyan]")
    console.print("   • Commands are simple: [letter][device_number]")
    console.print("   • Example: 'a1' = Turn ON Switch 1 on Device 1")
    console.print("   • Commands are case insensitive\n")
    
    console.print("🎯 [cyan]Individual Switch Control:[/cyan]")
    for i, device in enumerate(devices):
        device_num = i + 1
        console.print(f"   Device {device_num}: [green]{device['name']}[/green]")
        console.print(f"   • Switch 1: [bold green]a{device_num}[/bold green] = ON, [bold red]b{device_num}[/bold red] = OFF")
        console.print(f"   • Switch 2: [bold green]c{device_num}[/bold green] = ON, [bold red]d{device_num}[/bold red] = OFF")
        console.print()
    
    console.print("🎯 [cyan]Device-wide Control (Both Switches):[/cyan]")
    for i, device in enumerate(devices):
        device_num = i + 1
        console.print(f"   {device['name']}: [bold green]on{device_num}[/bold green] = ALL ON, [bold red]off{device_num}[/bold red] = ALL OFF")
    
    console.print("\n🎯 [cyan]General Commands:[/cyan]")
    console.print("   • 'h' or 'help' - Show this help")
    console.print("   • 'r' or 'refresh' - Refresh the interface")
    console.print("   • 'q' or 'quit' - Exit the interface")
    
    console.print("\n🎯 [cyan]Status Information:[/cyan]")
    console.print("   • Switch status updates automatically via MQTT")
    console.print("   • 🟢 ON = Switch is currently on")
    console.print("   • ⚪ OFF = Switch is currently off")
    console.print("   • ❓ Unknown = Status not yet received")
    
    console.print("\n" + "="*100)
    input("Press Enter to continue...")

@app.command()
def add_devices(
    from_config: bool = typer.Option(True, "--from-config", help="Load devices from config.json"),
    file: str = typer.Option("devices.json", "--file", "-f", help="JSON file with devices (if not using config)"),
    force: bool = typer.Option(False, "--force", help="Force creation even if device exists")
):
    """Add devices from config.json or JSON file"""
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        # Load devices from config.json or separate file
        if from_config:
            console.print(f"📱 [bold blue]Adding Devices from {CONFIG_FILE}[/bold blue]")
            config = load_config()
            devices = config.get('devices', [])
            # Get application info from config
            app_name = config['chirpstack']['application_name']
            app_description = config['chirpstack']['application_description']
            join_eui = config['chirpstack']['join_eui']
            app_key = config['chirpstack']['app_key']
            
            # Add application info to each device if not present
            for device in devices:
                if 'application_name' not in device:
                    device['application_name'] = app_name
                if 'application_description' not in device:
                    device['application_description'] = app_description
                if 'join_eui' not in device:
                    device['join_eui'] = join_eui
                if 'app_key' not in device:
                    device['app_key'] = app_key
        else:
            console.print(f"📱 [bold blue]Adding Devices from {file}[/bold blue]")
            if not os.path.exists(file):
                console.print(f"❌ [red]File {file} not found[/red]")
                raise typer.Exit(1)
            with open(file, 'r') as f:
                devices = json.load(f)
        
        if not devices:
            console.print("❌ [red]No devices found in configuration[/red]")
            raise typer.Exit(1)
        
        console.print(f"📂 [cyan]Loaded {len(devices)} devices from configuration[/cyan]")
        
        # Get existing applications and device profiles
        app_req = api.ListApplicationsRequest()
        app_req.tenant_id = tenant_id
        app_req.limit = 100
        app_resp = cli.application_client.List(app_req, metadata=cli.get_auth_metadata())
        
        applications = {app.name: app.id for app in app_resp.result}
        
        profile_req = api.ListDeviceProfilesRequest()
        profile_req.tenant_id = tenant_id
        profile_req.limit = 100
        profile_resp = cli.device_profile_client.List(profile_req, metadata=cli.get_auth_metadata())
        
        device_profiles = {profile.name: profile.id for profile in profile_resp.result}
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing devices...", total=len(devices))
            
            for device_config in devices:
                device_name = device_config['name']
                dev_eui = device_config['dev_eui']
                
                # Check if device exists
                existing_device = None
                try:
                    req = api.GetDeviceRequest()
                    req.dev_eui = dev_eui
                    resp = cli.device_client.Get(req, metadata=cli.get_auth_metadata())
                    existing_device = resp.device
                except grpc.RpcError as e:
                    if e.code() != grpc.StatusCode.NOT_FOUND:
                        console.print(f"❌ [red]Error checking device {dev_eui}: {e}[/red]")
                        error_count += 1
                        progress.advance(task)
                        continue
                
                # Create application if it doesn't exist
                app_name = device_config['application_name']
                if app_name not in applications:
                    app_id = _create_application(cli, tenant_id, app_name, device_config['application_description'])
                    if app_id:
                        applications[app_name] = app_id
                    else:
                        console.print(f"❌ [red]Failed to create application: {app_name}[/red]")
                        error_count += 1
                        progress.advance(task)
                        continue
                
                # Get required IDs
                application_id = applications.get(app_name)
                device_profile_id = device_profiles.get(device_config['device_profile_name'])
                
                if not application_id:
                    console.print(f"❌ [red]Application not found: {app_name}[/red]")
                    error_count += 1
                elif not device_profile_id:
                    console.print(f"❌ [red]Device profile not found: {device_config['device_profile_name']}[/red]")
                    error_count += 1
                elif _create_device(cli, device_config, application_id, device_profile_id, existing_device):
                    if existing_device:
                        updated_count += 1
                    else:
                        created_count += 1
                else:
                    error_count += 1
                
                progress.advance(task)
        
        console.print(f"\n📊 [green]Summary: {created_count} created, {updated_count} updated, {error_count} errors[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to add devices: {e}[/red]")
        raise typer.Exit(1)

def _create_application(cli, tenant_id, app_name, app_description):
    """Helper function to create an application"""
    try:
        application = api.Application()
        application.name = app_name
        application.description = app_description
        application.tenant_id = tenant_id
        
        req = api.CreateApplicationRequest()
        req.application.CopyFrom(application)
        
        resp = cli.application_client.Create(req, metadata=cli.get_auth_metadata())
        console.print(f"✅ [green]Created application: {app_name}[/green]")
        return resp.id
    except Exception as e:
        console.print(f"❌ [red]Error creating application {app_name}: {e}[/red]")
        return None

def _create_device(cli, device_config, application_id, device_profile_id, existing_device=None):
    """Helper function to create or update a device"""
    try:
        # Create device
        device = api.Device()
        device.name = device_config['name']
        device.description = device_config['description']
        device.dev_eui = device_config['dev_eui']
        device.device_profile_id = device_profile_id
        device.application_id = application_id
        device.skip_fcnt_check = device_config['skip_fcnt_check']
        device.is_disabled = device_config['is_disabled']
        device.join_eui = device_config['join_eui']
        
        # Add tags
        for key, value in device_config.get('tags', {}).items():
            device.tags[key] = value
        
        # Add variables
        for key, value in device_config.get('variables', {}).items():
            device.variables[key] = value
        
        if existing_device:
            # Update existing device
            req = api.UpdateDeviceRequest()
            req.device.CopyFrom(device)
            cli.device_client.Update(req, metadata=cli.get_auth_metadata())
            console.print(f"🔄 [green]Updated device: {device_config['name']} ({device_config['dev_eui']})[/green]")
        else:
            # Create new device
            req = api.CreateDeviceRequest()
            req.device.CopyFrom(device)
            cli.device_client.Create(req, metadata=cli.get_auth_metadata())
            console.print(f"✅ [green]Created device: {device_config['name']} ({device_config['dev_eui']})[/green]")
        
        # Create or update device keys for OTAA
        device_keys = api.DeviceKeys()
        # Both dev_eui and app_key are strings according to the protobuf definition
        device_keys.dev_eui = device_config['dev_eui']
        device_keys.app_key = device_config['app_key']

        
        try:
            if existing_device:
                # Try to update existing keys
                keys_req = api.UpdateDeviceKeysRequest()
                keys_req.device_keys.CopyFrom(device_keys)
                cli.device_client.UpdateKeys(keys_req, metadata=cli.get_auth_metadata())
                console.print(f"🔑 [cyan]Updated OTAA keys for device: {device_config['dev_eui']}[/cyan]")
            else:
                # Create new keys
                keys_req = api.CreateDeviceKeysRequest()
                keys_req.device_keys.CopyFrom(device_keys)
                cli.device_client.CreateKeys(keys_req, metadata=cli.get_auth_metadata())
                console.print(f"🔑 [cyan]Created OTAA keys for device: {device_config['dev_eui']}[/cyan]")
        except Exception as key_error:
            # If update fails, try to create (might be missing keys)
            if existing_device:
                try:
                    keys_req = api.CreateDeviceKeysRequest()
                    keys_req.device_keys.CopyFrom(device_keys)
                    cli.device_client.CreateKeys(keys_req, metadata=cli.get_auth_metadata())
                    console.print(f"🔑 [cyan]Created OTAA keys for existing device: {device_config['dev_eui']}[/cyan]")
                except Exception as create_key_error:
                    console.print(f"⚠️  [yellow]Warning: Could not create/update OTAA keys for {device_config['dev_eui']}: {create_key_error}[/yellow]")
            else:
                console.print(f"⚠️  [yellow]Warning: Could not create OTAA keys for {device_config['dev_eui']}: {key_error}[/yellow]")
        
        return True
    except Exception as e:
        console.print(f"❌ [red]Error creating device: {e}[/red]")
        return False

@app.callback()
def main(
    api_key: Optional[str] = typer.Option(None, "--api-key", help="ChirpStack API key"),
    server: Optional[str] = typer.Option(None, "--server", help="ChirpStack server URL"),
    config_file: Optional[str] = typer.Option(None, "--config", help="Configuration file path"),
):
    """
    ChirpStack CLI Tool
    
    A command-line interface for managing ChirpStack gateways, device profiles, and devices.
    
    Configuration is loaded from config.json by default, but can be overridden with command line options.
    """
    global CONFIG_FILE, client
    
    # Update config file path if provided
    if config_file:
        CONFIG_FILE = config_file
    
    # Override client settings if provided via command line
    if api_key or server:
        config = load_config()
        if api_key:
            config['chirpstack']['api_key'] = api_key
        if server:
            config['chirpstack']['server_url'] = server

if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n💥 [bold red]Unexpected error: {e}[/bold red]")
        sys.exit(1)
    finally:
        if client:
            client.cleanup() 