#!/usr/bin/env python3
"""
ChirpStack CLI Tool

A command-line interface for managing ChirpStack gateways, device profiles, and devices.
Built with Typer for a better user experience.

Usage:
    python chirpstack_cli.py [COMMAND] [OPTIONS]

Commands:
    check-auth          Check if API authentication is working
    list-gateways       List all gateways
    add-gateway         Add a single gateway
    add-gateways        Add gateways from JSON file
    list-profiles       List all device profiles
    add-profiles        Add device profiles from JSON file
    list-devices        List all devices
    add-devices         Add devices from JSON file
    list-applications   List all applications

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
import requests
from chirpstack_api import api

# Initialize Typer app and Rich console
app = typer.Typer(help="ChirpStack CLI Tool for managing gateways, device profiles, and devices")
console = Console()

# Global configuration
# API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6ImQ3NmYzMzVmLWY0ZGEtNGRmNi05ODAwLWQ3ODkzOGMxYjdlNyIsInR5cCI6ImtleSJ9.Dr6Qbw4Kfr6rkoQQflQ9a5Hv8Nsa4PednO_4M3B8p5A"
API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6ImFhYjAwNjMzLTY1MTQtNDEzNy1hZmYwLWI1YTlmMjY1NTY1ZiIsInR5cCI6ImtleSJ9.zFnbjBbifzFybzkuifvZJ5Aa1hFBwpS_XY1I1QAKXEw"
SERVER_URL = "localhost:8080"

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
        api_key = os.getenv("CHIRPSTACK_API_KEY", API_KEY)
        server_url = os.getenv("CHIRPSTACK_SERVER", SERVER_URL)
        client = ChirpStackCLI(api_key, server_url)
    return client

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
            last_seen = "Never" if not gateway.last_seen_at else gateway.last_seen_at.strftime("%Y-%m-%d %H:%M:%S")
            location = f"{gateway.location.latitude:.6f}, {gateway.location.longitude:.6f}" if gateway.location else "Not set"
            
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
        
        # Set location if provided
        if latitude != 0.0 or longitude != 0.0:
            location = api.Location()
            location.latitude = latitude
            location.longitude = longitude
            location.altitude = altitude
            location.source = api.LocationSource.UNKNOWN
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
    file: str = typer.Option("gateways.json", "--file", "-f", help="JSON file with gateways"),
    force: bool = typer.Option(False, "--force", help="Force creation even if gateway exists")
):
    """Add gateways from JSON file"""
    console.print(f"📡 [bold blue]Adding Gateways from {file}[/bold blue]")
    
    if not os.path.exists(file):
        console.print(f"❌ [red]File {file} not found[/red]")
        raise typer.Exit(1)
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        # Load gateways
        with open(file, 'r') as f:
            gateways = json.load(f)
        
        console.print(f"📂 [cyan]Loaded {len(gateways)} gateways from {file}[/cyan]")
        
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
            location = api.Location()
            location.latitude = gateway_config['latitude']
            location.longitude = gateway_config['longitude']
            location.altitude = gateway_config.get('altitude', 0.0)
            location.source = api.LocationSource.UNKNOWN
            gateway.location.CopyFrom(location)
        
        # Add tags
        for key, value in gateway_config.get('tags', {}).items():
            gateway.tags[key] = str(value)
        
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
        
        for profile in resp.result:
            table.add_row(
                profile.id[:8] + "...",
                profile.name,
                profile.description or "No description",
                profile.region.name,
                profile.mac_version.name,
                "✅" if profile.supports_otaa else "❌"
            )
        
        console.print(table)
        console.print(f"\n📊 [green]Total device profiles: {len(resp.result)}[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to list device profiles: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def add_profiles(
    file: str = typer.Option("device_profiles.json", "--file", "-f", help="JSON file with device profiles"),
    force: bool = typer.Option(False, "--force", help="Force creation even if profile exists")
):
    """Add device profiles from JSON file"""
    console.print(f"📋 [bold blue]Adding Device Profiles from {file}[/bold blue]")
    
    if not os.path.exists(file):
        console.print(f"❌ [red]File {file} not found[/red]")
        raise typer.Exit(1)
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        # Load profiles
        with open(file, 'r') as f:
            profiles = json.load(f)
        
        console.print(f"📂 [cyan]Loaded {len(profiles)} profiles from {file}[/cyan]")
        
        # Get existing profiles
        existing_profiles = {}
        req = api.ListDeviceProfilesRequest()
        req.tenant_id = tenant_id
        req.limit = 100
        resp = cli.device_profile_client.List(req, metadata=cli.get_auth_metadata())
        
        for profile in resp.result:
            existing_profiles[profile.name] = profile.id
        
        created_count = 0
        skipped_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing profiles...", total=len(profiles))
            
            for profile_config in profiles:
                profile_name = profile_config['name']
                
                if profile_name in existing_profiles and not force:
                    console.print(f"⏭️  [yellow]Skipping existing profile: {profile_name}[/yellow]")
                    skipped_count += 1
                else:
                    if _create_device_profile(cli, tenant_id, profile_config):
                        created_count += 1
                        console.print(f"✅ [green]Created profile: {profile_name}[/green]")
                    else:
                        console.print(f"❌ [red]Failed to create profile: {profile_name}[/red]")
                
                progress.advance(task)
        
        console.print(f"\n📊 [green]Summary: {created_count} created, {skipped_count} skipped[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to add device profiles: {e}[/red]")
        raise typer.Exit(1)

def _create_device_profile(cli, tenant_id, profile_config):
    """Helper function to create a device profile"""
    try:
        # Download codec script if URL provided
        codec_script = ""
        if profile_config.get('codec_script_url'):
            response = requests.get(profile_config['codec_script_url'], timeout=30)
            response.raise_for_status()
            codec_script = response.text
        
        # Create device profile
        device_profile = api.DeviceProfile()
        device_profile.name = profile_config['name']
        device_profile.description = profile_config['description']
        device_profile.tenant_id = tenant_id
        device_profile.region = api.Region.Value(profile_config['region'])
        device_profile.mac_version = api.MacVersion.Value(profile_config['mac_version'])
        device_profile.reg_params_revision = api.RegParamsRevision.Value(profile_config['regional_parameters_revision'])
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
        device_profile.class_b_ping_slot_period = profile_config['class_b_ping_slot_period']
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
        
        req = api.CreateDeviceProfileRequest()
        req.device_profile.CopyFrom(device_profile)
        
        cli.device_profile_client.Create(req, metadata=cli.get_auth_metadata())
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
            status = "🔴 Disabled" if device.is_disabled else "🟢 Enabled"
            
            table.add_row(
                device.dev_eui,
                device.name,
                device.description or "No description",
                device.device_profile_name or "Unknown",
                status
            )
        
        console.print(table)
        console.print(f"\n📊 [green]Total devices: {len(resp.result)}[/green]")
        
    except Exception as e:
        console.print(f"❌ [red]Failed to list devices: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def add_devices(
    file: str = typer.Option("devices.json", "--file", "-f", help="JSON file with devices"),
    force: bool = typer.Option(False, "--force", help="Force creation even if device exists")
):
    """Add devices from JSON file"""
    console.print(f"📱 [bold blue]Adding Devices from {file}[/bold blue]")
    
    if not os.path.exists(file):
        console.print(f"❌ [red]File {file} not found[/red]")
        raise typer.Exit(1)
    
    try:
        cli = get_client()
        tenant_id = cli.get_tenant_id()
        
        if not tenant_id:
            raise typer.Exit(1)
        
        # Load devices
        with open(file, 'r') as f:
            devices = json.load(f)
        
        console.print(f"📂 [cyan]Loaded {len(devices)} devices from {file}[/cyan]")
        
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
        skipped_count = 0
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
                try:
                    req = api.GetDeviceRequest()
                    req.dev_eui = dev_eui
                    cli.device_client.Get(req, metadata=cli.get_auth_metadata())
                    
                    if not force:
                        console.print(f"⏭️  [yellow]Skipping existing device: {device_name} ({dev_eui})[/yellow]")
                        skipped_count += 1
                        progress.advance(task)
                        continue
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
                elif _create_device(cli, device_config, application_id, device_profile_id):
                    created_count += 1
                    console.print(f"✅ [green]Created device: {device_name} ({dev_eui})[/green]")
                else:
                    error_count += 1
                
                progress.advance(task)
        
        console.print(f"\n📊 [green]Summary: {created_count} created, {skipped_count} skipped, {error_count} errors[/green]")
        
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

def _create_device(cli, device_config, application_id, device_profile_id):
    """Helper function to create a device"""
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
        
        req = api.CreateDeviceRequest()
        req.device.CopyFrom(device)
        
        cli.device_client.Create(req, metadata=cli.get_auth_metadata())
        
        # Create device keys for OTAA
        device_keys = api.DeviceKeys()
        device_keys.dev_eui = device_config['dev_eui']
        device_keys.app_key = device_config['app_key']
        
        keys_req = api.CreateDeviceKeysRequest()
        keys_req.device_keys.CopyFrom(device_keys)
        
        cli.device_client.CreateKeys(keys_req, metadata=cli.get_auth_metadata())
        
        return True
    except Exception as e:
        console.print(f"❌ [red]Error creating device: {e}[/red]")
        return False

@app.callback()
def main(
    api_key: Optional[str] = typer.Option(None, "--api-key", help="ChirpStack API key"),
    server: Optional[str] = typer.Option(None, "--server", help="ChirpStack server URL"),
):
    """
    ChirpStack CLI Tool
    
    A command-line interface for managing ChirpStack gateways, device profiles, and devices.
    """
    global API_KEY, SERVER_URL, client
    
    if api_key:
        API_KEY = api_key
    if server:
        SERVER_URL = server
    
    # Override with environment variables
    API_KEY = os.getenv("CHIRPSTACK_API_KEY", API_KEY)
    SERVER_URL = os.getenv("CHIRPSTACK_SERVER", SERVER_URL)

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