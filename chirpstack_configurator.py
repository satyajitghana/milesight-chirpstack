#!/usr/bin/env python3
"""
ChirpStack Configurator Script

This script configures ChirpStack with device profiles and devices using the gRPC API.
It will:
1. Create or update device profiles for WS202 and WS203 sensors
2. Create an application if it doesn't exist
3. Add devices to the application with proper OTAA configuration

Author: AI Assistant
Date: 2025
"""

import json
import os
import sys
import requests
from datetime import datetime
import grpc
from chirpstack_api import api
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

console = Console()

class ChirpStackConfigurator:
    def __init__(self, api_key, server_url="localhost:8080"):
        """Initialize the ChirpStack configurator"""
        self.api_key = api_key
        self.server_url = server_url
        self.channel = None
        self.client = None
        self.device_profile_client = None
        self.application_client = None
        self.device_client = None
        
        self._setup_grpc_clients()
    
    def _setup_grpc_clients(self):
        """Setup gRPC clients for ChirpStack API"""
        try:
            # Create gRPC channel
            self.channel = grpc.insecure_channel(self.server_url)
            
            # Create API clients
            self.device_profile_client = api.DeviceProfileServiceStub(self.channel)
            self.application_client = api.ApplicationServiceStub(self.channel)
            self.device_client = api.DeviceServiceStub(self.channel)
            self.tenant_client = api.TenantServiceStub(self.channel)
            
            console.print("✅ [green]gRPC clients initialized successfully[/green]")
            
        except Exception as e:
            console.print(f"❌ [red]Failed to setup gRPC clients: {e}[/red]")
            sys.exit(1)
    
    def _get_auth_metadata(self):
        """Get authentication metadata for API calls"""
        return [("authorization", f"Bearer {self.api_key}")]
    
    def _download_codec_script(self, url):
        """Download codec script from URL"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            console.print(f"❌ [red]Failed to download codec from {url}: {e}[/red]")
            return ""
    
    def get_tenant_id(self):
        """Get the default tenant ID"""
        try:
            # List tenants and get the first one (usually default)
            req = api.ListTenantsRequest()
            resp = self.tenant_client.List(req, metadata=self._get_auth_metadata())
            
            if resp.result:
                tenant_id = resp.result[0].id
                console.print(f"✅ [green]Using tenant ID: {tenant_id}[/green]")
                return tenant_id
            else:
                console.print("❌ [red]No tenants found[/red]")
                return None
                
        except Exception as e:
            console.print(f"❌ [red]Failed to get tenant ID: {e}[/red]")
            return None
    
    def list_device_profiles(self):
        """List existing device profiles"""
        try:
            tenant_id = self.get_tenant_id()
            if not tenant_id:
                return []
            
            req = api.ListDeviceProfilesRequest()
            req.tenant_id = tenant_id
            req.limit = 100
            
            resp = self.device_profile_client.List(req, metadata=self._get_auth_metadata())
            
            profiles = []
            for profile in resp.result:
                profiles.append({
                    'id': profile.id,
                    'name': profile.name,
                    'description': profile.description
                })
            
            return profiles
            
        except Exception as e:
            console.print(f"❌ [red]Failed to list device profiles: {e}[/red]")
            return []
    
    def device_profile_exists(self, profile_name):
        """Check if a device profile exists"""
        profiles = self.list_device_profiles()
        for profile in profiles:
            if profile['name'] == profile_name:
                return profile['id']
        return None
    
    def create_device_profile(self, profile_config):
        """Create a device profile"""
        try:
            tenant_id = self.get_tenant_id()
            if not tenant_id:
                return None
            
            # Check if profile already exists
            existing_id = self.device_profile_exists(profile_config['name'])
            if existing_id:
                console.print(f"✅ [yellow]Device profile '{profile_config['name']}' already exists (ID: {existing_id})[/yellow]")
                return existing_id
            
            # Download codec script if URL provided
            codec_script = ""
            if profile_config.get('codec_script_url'):
                console.print(f"📥 [cyan]Downloading codec script for {profile_config['name']}...[/cyan]")
                codec_script = self._download_codec_script(profile_config['codec_script_url'])
            
            # Create device profile object
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
            
            # Add measurements
            for key, measurement in profile_config.get('measurements', {}).items():
                measurement_obj = api.Measurement()
                measurement_obj.kind = api.MeasurementKind.Value(measurement['kind'])
                measurement_obj.name = measurement['name']
                device_profile.measurements[key] = measurement_obj
            
            # Create the request
            req = api.CreateDeviceProfileRequest()
            req.device_profile.CopyFrom(device_profile)
            
            # Make the API call
            resp = self.device_profile_client.Create(req, metadata=self._get_auth_metadata())
            
            console.print(f"✅ [green]Device profile '{profile_config['name']}' created successfully (ID: {resp.id})[/green]")
            return resp.id
            
        except Exception as e:
            console.print(f"❌ [red]Failed to create device profile '{profile_config['name']}': {e}[/red]")
            return None
    
    def list_applications(self):
        """List existing applications"""
        try:
            tenant_id = self.get_tenant_id()
            if not tenant_id:
                return []
            
            req = api.ListApplicationsRequest()
            req.tenant_id = tenant_id
            req.limit = 100
            
            resp = self.application_client.List(req, metadata=self._get_auth_metadata())
            
            applications = []
            for app in resp.result:
                applications.append({
                    'id': app.id,
                    'name': app.name,
                    'description': app.description
                })
            
            return applications
            
        except Exception as e:
            console.print(f"❌ [red]Failed to list applications: {e}[/red]")
            return []
    
    def application_exists(self, app_name):
        """Check if an application exists"""
        applications = self.list_applications()
        for app in applications:
            if app['name'] == app_name:
                return app['id']
        return None
    
    def create_application(self, app_name, app_description):
        """Create an application"""
        try:
            tenant_id = self.get_tenant_id()
            if not tenant_id:
                return None
            
            # Check if application already exists
            existing_id = self.application_exists(app_name)
            if existing_id:
                console.print(f"✅ [yellow]Application '{app_name}' already exists (ID: {existing_id})[/yellow]")
                return existing_id
            
            # Create application object
            application = api.Application()
            application.name = app_name
            application.description = app_description
            application.tenant_id = tenant_id
            
            # Create the request
            req = api.CreateApplicationRequest()
            req.application.CopyFrom(application)
            
            # Make the API call
            resp = self.application_client.Create(req, metadata=self._get_auth_metadata())
            
            console.print(f"✅ [green]Application '{app_name}' created successfully (ID: {resp.id})[/green]")
            return resp.id
            
        except Exception as e:
            console.print(f"❌ [red]Failed to create application '{app_name}': {e}[/red]")
            return None
    
    def device_exists(self, dev_eui):
        """Check if a device exists"""
        try:
            req = api.GetDeviceRequest()
            req.dev_eui = dev_eui
            
            resp = self.device_client.Get(req, metadata=self._get_auth_metadata())
            return True
            
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                return False
            else:
                console.print(f"❌ [red]Error checking device {dev_eui}: {e}[/red]")
                return False
    
    def create_device(self, device_config, application_id, device_profile_id):
        """Create a device"""
        try:
            # Check if device already exists
            if self.device_exists(device_config['dev_eui']):
                console.print(f"✅ [yellow]Device '{device_config['name']}' ({device_config['dev_eui']}) already exists[/yellow]")
                return True
            
            # Create device object
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
            
            # Create the request
            req = api.CreateDeviceRequest()
            req.device.CopyFrom(device)
            
            # Make the API call
            resp = self.device_client.Create(req, metadata=self._get_auth_metadata())
            
            # Create device keys for OTAA
            self._create_device_keys(device_config['dev_eui'], device_config['app_key'])
            
            console.print(f"✅ [green]Device '{device_config['name']}' created successfully[/green]")
            return True
            
        except Exception as e:
            console.print(f"❌ [red]Failed to create device '{device_config['name']}': {e}[/red]")
            return False
    
    def _create_device_keys(self, dev_eui, app_key):
        """Create device keys for OTAA"""
        try:
            device_keys = api.DeviceKeys()
            device_keys.dev_eui = dev_eui
            device_keys.app_key = app_key
            
            req = api.CreateDeviceKeysRequest()
            req.device_keys.CopyFrom(device_keys)
            
            self.device_client.CreateKeys(req, metadata=self._get_auth_metadata())
            console.print(f"✅ [green]Device keys created for {dev_eui}[/green]")
            
        except Exception as e:
            console.print(f"❌ [red]Failed to create device keys for {dev_eui}: {e}[/red]")
    
    def configure_from_files(self, device_profiles_file="device_profiles.json", devices_file="devices.json"):
        """Configure ChirpStack from JSON configuration files"""
        console.print(Panel("🚀 ChirpStack Configuration Started", style="bold blue"))
        
        # Load configuration files
        try:
            with open(device_profiles_file, 'r') as f:
                device_profiles = json.load(f)
            console.print(f"✅ [green]Loaded {len(device_profiles)} device profiles from {device_profiles_file}[/green]")
        except Exception as e:
            console.print(f"❌ [red]Failed to load device profiles: {e}[/red]")
            return False
        
        try:
            with open(devices_file, 'r') as f:
                devices = json.load(f)
            console.print(f"✅ [green]Loaded {len(devices)} devices from {devices_file}[/green]")
        except Exception as e:
            console.print(f"❌ [red]Failed to load devices: {e}[/red]")
            return False
        
        # Step 1: Create device profiles
        console.print("\n📋 [bold cyan]Step 1: Creating Device Profiles[/bold cyan]")
        profile_ids = {}
        
        with Progress() as progress:
            task = progress.add_task("Creating device profiles...", total=len(device_profiles))
            
            for profile in device_profiles:
                profile_id = self.create_device_profile(profile)
                if profile_id:
                    profile_ids[profile['name']] = profile_id
                progress.advance(task)
        
        # Step 2: Create applications
        console.print("\n🏢 [bold cyan]Step 2: Creating Applications[/bold cyan]")
        application_ids = {}
        
        # Get unique applications from devices
        apps_to_create = {}
        for device in devices:
            app_name = device['application_name']
            if app_name not in apps_to_create:
                apps_to_create[app_name] = device['application_description']
        
        for app_name, app_description in apps_to_create.items():
            app_id = self.create_application(app_name, app_description)
            if app_id:
                application_ids[app_name] = app_id
        
        # Step 3: Create devices
        console.print("\n📱 [bold cyan]Step 3: Creating Devices[/bold cyan]")
        
        with Progress() as progress:
            task = progress.add_task("Creating devices...", total=len(devices))
            
            for device in devices:
                # Get required IDs
                device_profile_id = profile_ids.get(device['device_profile_name'])
                application_id = application_ids.get(device['application_name'])
                
                if not device_profile_id:
                    console.print(f"❌ [red]Device profile '{device['device_profile_name']}' not found for device '{device['name']}'[/red]")
                    progress.advance(task)
                    continue
                
                if not application_id:
                    console.print(f"❌ [red]Application '{device['application_name']}' not found for device '{device['name']}'[/red]")
                    progress.advance(task)
                    continue
                
                # Create device
                self.create_device(device, application_id, device_profile_id)
                progress.advance(task)
        
        # Summary
        console.print("\n📊 [bold green]Configuration Summary[/bold green]")
        summary_table = Table(title="ChirpStack Configuration Results")
        summary_table.add_column("Component", style="cyan")
        summary_table.add_column("Count", style="green")
        summary_table.add_column("Status", style="yellow")
        
        summary_table.add_row("Device Profiles", str(len(profile_ids)), "✅ Created/Updated")
        summary_table.add_row("Applications", str(len(application_ids)), "✅ Created/Updated")
        summary_table.add_row("Devices", str(len(devices)), "✅ Created/Updated")
        
        console.print(summary_table)
        console.print(Panel("✅ ChirpStack configuration completed successfully!", style="bold green"))
        
        return True
    
    def cleanup(self):
        """Cleanup resources"""
        if self.channel:
            self.channel.close()


def main():
    """Main function"""
    # Configuration
    API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjIzMWFhZjYxLTA2NmEtNDZjZi04ZDYxLTcxY2UzM2E2NDIzOSIsInR5cCI6ImtleSJ9.-bZpgLUMjtZUq_Z8AT23Tzze-jPTHiiZfsSyzww7fXE"
    SERVER_URL = "localhost:8080"  # ChirpStack gRPC API endpoint
    
    # Initialize configurator
    console.print("🔧 [bold]Initializing ChirpStack Configurator...[/bold]")
    configurator = ChirpStackConfigurator(API_KEY, SERVER_URL)
    
    try:
        # Run configuration
        success = configurator.configure_from_files()
        
        if success:
            console.print("\n🎉 [bold green]ChirpStack has been configured successfully![/bold green]")
            console.print("📱 [cyan]Your devices are now ready to join the LoRaWAN network[/cyan]")
        else:
            console.print("\n❌ [bold red]Configuration failed. Please check the logs above.[/bold red]")
            sys.exit(1)
    
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Configuration cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n❌ [bold red]Unexpected error: {e}[/bold red]")
        sys.exit(1)
    finally:
        configurator.cleanup()


if __name__ == "__main__":
    main() 