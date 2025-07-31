#!/usr/bin/env python3
"""
Simple runner script for ChirpStack configuration

Usage:
    python configure_chirpstack.py

This script will configure ChirpStack with:
- WS202 and WS203 device profiles
- Milesight IoT Sensors application
- PIR and Light sensor device
- Temperature and Humidity sensor device
"""

import os
import sys
from chirpstack_configurator import ChirpStackConfigurator
from rich.console import Console

console = Console()

def main():
    """Main function to run ChirpStack configuration"""
    
    console.print("🚀 [bold blue]ChirpStack Configurator[/bold blue]")
    console.print("📡 [cyan]Configuring ChirpStack with Milesight IoT devices...[/cyan]\n")
    
    # Check if configuration files exist
    if not os.path.exists("device_profiles.json"):
        console.print("❌ [red]device_profiles.json not found![/red]")
        sys.exit(1)
    
    if not os.path.exists("devices.json"):
        console.print("❌ [red]devices.json not found![/red]")
        sys.exit(1)
    
    # Configuration
    API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjIzMWFhZjYxLTA2NmEtNDZjZi04ZDYxLTcxY2UzM2E2NDIzOSIsInR5cCI6ImtleSJ9.-bZpgLUMjtZUq_Z8AT23Tzze-jPTHiiZfsSyzww7fXE"
    SERVER_URL = "localhost:8080"  # Default ChirpStack gRPC endpoint
    
    # Allow override from environment variables
    API_KEY = os.getenv("CHIRPSTACK_API_KEY", API_KEY)
    SERVER_URL = os.getenv("CHIRPSTACK_SERVER", SERVER_URL)
    
    console.print(f"🔑 [yellow]Using API Key: {API_KEY[:20]}...[/yellow]")
    console.print(f"🌐 [yellow]ChirpStack Server: {SERVER_URL}[/yellow]\n")
    
    # Initialize configurator
    try:
        configurator = ChirpStackConfigurator(API_KEY, SERVER_URL)
        
        # Run configuration
        success = configurator.configure_from_files()
        
        if success:
            console.print("\n🎉 [bold green]Configuration completed successfully![/bold green]")
            console.print("📱 [cyan]Your Milesight devices are ready to join the network![/cyan]")
            console.print("\n📋 [bold]Next Steps:[/bold]")
            console.print("1. Power on your WS202 and WS203 devices")
            console.print("2. They will automatically join using OTAA")
            console.print("3. Check ChirpStack web UI for device activity")
            console.print("4. Monitor sensor data using the IoT dashboard")
        else:
            console.print("\n❌ [bold red]Configuration failed![/bold red]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"\n💥 [bold red]Error: {e}[/bold red]")
        sys.exit(1)
    finally:
        if 'configurator' in locals():
            configurator.cleanup()

if __name__ == "__main__":
    main() 