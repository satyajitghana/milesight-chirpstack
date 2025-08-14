#!/usr/bin/env python3
"""
Simple script to run the ChirpStack IoT Web Dashboard
"""

import os
import sys
import subprocess

def main():
    print("🌐 Starting ChirpStack IoT Web Dashboard...")
    print("📡 Server will be available at: http://localhost:4000")
    print("🔑 You'll need to register/login on first use")
    print("📄 See README_WEB.md for detailed instructions")
    print("⏹️  Press Ctrl+C to stop the server")
    print("-" * 60)
    
    # Check if config.json exists
    if not os.path.exists("config.json"):
        print("⚠️  Warning: config.json not found!")
        print("   The dashboard will work but device control may not function")
        print("   without proper ChirpStack and MQTT configuration.")
        print()
    
    # Change to app directory and run server
    try:
        cmd = [
            sys.executable, "-m", "uvicorn", 
            "app.main:app", 
            "--host", "0.0.0.0", 
            "--port", "4000", 
            "--reload"
        ]
        
        subprocess.run(cmd, check=True)
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down web server...")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error starting server: {e}")
        print("\n💡 Try installing dependencies:")
        print("   pip install -e .")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")

if __name__ == "__main__":
    main()
