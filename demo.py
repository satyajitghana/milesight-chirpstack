#!/usr/bin/env python3
"""
ChirpStack CLI Demo Script

This script demonstrates the step-by-step usage of the ChirpStack CLI tool.
It shows the recommended workflow for setting up a complete ChirpStack environment.

Usage:
    python demo.py
    
This will show you the commands to run manually, or you can uncomment
the subprocess calls to run them automatically.
"""

import subprocess
import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

def run_command(cmd, description):
    """Display and optionally run a command"""
    console.print(f"\n🔧 [bold cyan]{description}[/bold cyan]")
    console.print(f"💻 [yellow]Command:[/yellow] {cmd}")
    
    # Uncomment the lines below to actually run the commands
    # console.print("▶️  [green]Running...[/green]")
    # result = subprocess.run(cmd.split(), capture_output=True, text=True)
    # if result.returncode == 0:
    #     console.print("✅ [green]Success![/green]")
    #     if result.stdout:
    #         console.print(result.stdout)
    # else:
    #     console.print("❌ [red]Error![/red]")
    #     if result.stderr:
    #         console.print(f"[red]{result.stderr}[/red]")
    
    console.print("⏸️  [blue]Press Enter to continue...[/blue]")
    input()

def main():
    """Main demo function"""
    
    welcome_text = """
# ChirpStack CLI Demo 🚀

This demo will walk you through the step-by-step process of configuring 
ChirpStack with gateways, device profiles, and Milesight IoT devices.

**What we'll set up:**
- ✅ Gateways for LoRaWAN network coverage  
- ✅ Device profiles for WS202 (PIR/Light) and WS203 (Temp/Humidity)
- ✅ Applications to organize devices
- ✅ Individual devices with OTAA configuration

**Prerequisites:**
- ChirpStack server running on localhost:8080
- Valid API key configured
- JSON configuration files in current directory
"""
    
    console.print(Panel(Markdown(welcome_text), title="Welcome", border_style="blue"))
    
    console.print("\n🎯 [bold]Let's get started![/bold] Each step will show you the command to run.\n")
    input("Press Enter to begin...")
    
    # Step 1: Check Authentication
    console.print(Panel("Step 1: Verify API Authentication", style="bold green"))
    run_command(
        "python chirpstack_cli.py check-auth",
        "Check if your API key and server connection work"
    )
    
    # Step 2: Add Gateways
    console.print(Panel("Step 2: Add Gateways", style="bold green"))
    run_command(
        "python chirpstack_cli.py add-gateways --file gateways.json",
        "Add gateways from JSON configuration (creates network coverage)"
    )
    
    run_command(
        "python chirpstack_cli.py list-gateways",
        "Verify gateways were created successfully"
    )
    
    # Step 3: Add Device Profiles
    console.print(Panel("Step 3: Add Device Profiles", style="bold green"))
    run_command(
        "python chirpstack_cli.py add-profiles --file device_profiles.json",
        "Add WS202 and WS203 device profiles with Milesight decoders"
    )
    
    run_command(
        "python chirpstack_cli.py list-profiles",
        "Verify device profiles were created with codecs"
    )
    
    # Step 4: Add Devices
    console.print(Panel("Step 4: Add Devices and Applications", style="bold green"))
    run_command(
        "python chirpstack_cli.py add-devices --file devices.json",
        "Add devices (this also creates applications automatically)"
    )
    
    run_command(
        "python chirpstack_cli.py list-applications",
        "Verify applications were created"
    )
    
    run_command(
        "python chirpstack_cli.py list-devices",
        "Verify devices were created and configured for OTAA"
    )
    
    # Final Summary
    summary_text = """
# 🎉 Configuration Complete!

Your ChirpStack instance is now fully configured with:

✅ **Gateways**: Network infrastructure for LoRaWAN coverage
✅ **Device Profiles**: WS202 and WS203 with Milesight decoders  
✅ **Applications**: "Milesight IoT Sensors" application created
✅ **Devices**: PIR/Light and Temperature/Humidity sensors ready

## Next Steps:

1. **Power on your devices**: WS202 and WS203 sensors
2. **Check device activation**: Devices will join via OTAA automatically
3. **Monitor data**: Use ChirpStack web UI to see sensor data
4. **Set up integrations**: Connect to your IoT platform or dashboard

## Default Configuration:

- **App EUI**: 24E124C0002A0001
- **App Key**: 5572404c696e6b4c6f52613230313823  
- **Device EUIs**: 
  - PIR/Light: 24e124538f256619
  - Temp/Humidity: 24e124791f178752

## Useful Commands:

```bash
# Monitor devices
python chirpstack_cli.py list-devices

# Check gateways  
python chirpstack_cli.py list-gateways

# Add more devices
python chirpstack_cli.py add-devices --file new_devices.json
```
"""
    
    console.print(Panel(Markdown(summary_text), title="Success! 🚀", border_style="green"))
    
    console.print("\n📱 [bold blue]Your Milesight devices are ready to join the network![/bold blue]")
    console.print("🔗 [cyan]Access ChirpStack web UI to monitor device activity[/cyan]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Demo cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n💥 [bold red]Demo error: {e}[/bold red]")
        sys.exit(1) 