#!/usr/bin/env python3
"""
ChirpStack IoT Web Dashboard
A FastAPI-based web dashboard for visualizing IoT device data and controlling smart switches
"""

import os
import json
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Session, create_engine, select
from passlib.context import CryptContext

import paho.mqtt.client as mqtt
import grpc
from chirpstack_api import api

from .database import get_session, init_db
from .models import User, UserCreate, UserLogin, Token, DeviceState
from .auth import get_password_hash, verify_password, create_access_token, get_current_user, authenticate_user, ACCESS_TOKEN_EXPIRE_MINUTES
from .mqtt_client import MQTTClient

# Configuration
ENABLE_ACCOUNT_CREATION = False  # Set to True to allow new user registrations

# Global config data cache
config_data = None

def load_config():
    """Load configuration from config.json"""
    global config_data
    if config_data is None:
        try:
            with open("config.json", 'r') as f:
                config_data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load config.json: {e}")
            config_data = {}
    return config_data

class ChirpStackClient:
    """ChirpStack API client for fetching devices with tags"""
    
    def __init__(self):
        self.config = load_config()
        self.chirpstack_config = self.config.get('chirpstack', {})
        
    def get_auth_metadata(self):
        """Get authentication metadata for gRPC calls"""
        return [('authorization', f"Bearer {self.chirpstack_config.get('api_key', '')}")]
    
    def get_channel(self):
        """Get gRPC channel"""
        server = self.chirpstack_config.get('api_server', 'localhost:8080')
        if self.chirpstack_config.get('api_secure', False):
            channel = grpc.secure_channel(server, grpc.ssl_channel_credentials())
        else:
            channel = grpc.insecure_channel(server)
        return channel
    
    def list_devices_with_tags(self):
        """List all devices with their tags from ChirpStack or fallback to config.json"""
        
        # First try ChirpStack API, then fallback to config.json
        try:
            print("🔗 Attempting ChirpStack API connection...")
            channel = self.get_channel()
            device_client = api.DeviceServiceStub(channel)
            
            # Get application ID from config
            application_id = self.chirpstack_config.get('application_id', '')
            print(f"📱 Using application ID: {application_id}")
            
            if application_id:
                # List devices in the application
                req = api.ListDevicesRequest()
                req.application_id = application_id
                req.limit = 1000
                
                resp = device_client.List(req, metadata=self.get_auth_metadata())
                print(f"📡 Found {len(resp.result)} devices from ChirpStack API")
                
                if len(resp.result) > 0:
                    # Process ChirpStack devices
                    all_devices = []
                    for device in resp.result:
                        device_req = api.GetDeviceRequest()
                        device_req.dev_eui = device.dev_eui
                        device_detail = device_client.Get(device_req, metadata=self.get_auth_metadata())
                        
                        device_tags = {}
                        if hasattr(device_detail.device, 'tags'):
                            device_tags = dict(device_detail.device.tags)
                        
                        device_info = {
                            'dev_eui': device.dev_eui,
                            'name': device.name,
                            'description': device.description,
                            'application_id': application_id,
                            'device_profile_id': device.device_profile_id,
                            'skip_fcnt_check': device.skip_fcnt_check,
                            'is_disabled': device.is_disabled,
                            'tags': device_tags,
                            'variables': dict(device_detail.device.variables) if hasattr(device_detail.device, 'variables') else {}
                        }
                        all_devices.append(device_info)
                    
                    channel.close()
                    print(f"✅ Successfully fetched {len(all_devices)} devices from ChirpStack API")
                    return all_devices
            
            channel.close()
            
        except Exception as e:
            print(f"⚠️ ChirpStack API failed: {e}")
        
        # Fallback to config.json devices
        print("📁 Falling back to config.json devices...")
        try:
            config_devices = self.config.get('devices', [])
            print(f"📁 Found {len(config_devices)} devices in config.json")
            
            all_devices = []
            for device in config_devices:
                device_info = {
                    'dev_eui': device.get('dev_eui', ''),
                    'name': device.get('name', 'Unknown'),
                    'description': device.get('description', ''),
                    'application_id': 'config',
                    'device_profile_id': device.get('device_profile_name', ''),
                    'skip_fcnt_check': device.get('skip_fcnt_check', False),
                    'is_disabled': device.get('is_disabled', False),
                    'tags': device.get('tags', {}),
                    'variables': {}
                }
                all_devices.append(device_info)
                print(f"📁 Added device: {device_info['name']} with tags: {device_info['tags']}")
            
            print(f"✅ Successfully loaded {len(all_devices)} devices from config.json")
            
            # Log summary of all devices and their tags
            print("📋 DEVICE SUMMARY:")
            for i, device in enumerate(all_devices):
                print(f"   {i+1}. {device['name']} ({device['dev_eui']}) - Tags: {device['tags']}")
            
            return all_devices
            
        except Exception as config_error:
            print(f"❌ Error loading devices from config.json: {config_error}")
            return []

# Initialize ChirpStack client
chirpstack_client = ChirpStackClient()

# Initialize FastAPI app
app = FastAPI(
    title="Inkers Office IoT Dashboard",
    description="Advanced IoT device monitoring and control dashboard",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Initialize templates
templates = Jinja2Templates(directory="app/templates")

# Global variables for IoT data
device_data = {}
mqtt_client_instance = None

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"🔌 WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(f"🔌 WebSocket client disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            print(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast_device_update(self, device_eui: str, data: dict):
        message = json.dumps({
            "type": "device_data",
            "device_eui": device_eui,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        await self.broadcast(message)

    async def broadcast_stats_update(self, stats: dict):
        message = json.dumps({
            "type": "stats_update",
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        await self.broadcast(message)

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    """Initialize database and MQTT client on startup"""
    global mqtt_client_instance
    
    # Initialize database
    init_db()
    
    # Load saved device states from database
    with next(get_session()) as session:
        saved_states = load_device_states(session)
        device_data.update(saved_states)
        print(f"📥 Loaded {len(saved_states)} saved device states")
    
    # Load config and start MQTT client with save callback
    config = load_config()
    mqtt_config = config.get('mqtt', {})
    chirpstack_config = config.get('chirpstack', {})
    
    # Create callback that saves to database AND broadcasts via WebSocket
    async def enhanced_update_callback(device_eui: str, data: dict):
        # Save to database
        with next(get_session()) as session:
            save_device_state(
                session=session,
                device_eui=device_eui,
                device_name=data.get('device_name', device_data.get(device_eui, {}).get('device_name', 'Unknown')),
                decoded_data=data.get('decoded_data', {}),
                message_count=data.get('message_count', 0),
                rssi=data.get('rssi'),
                snr=data.get('snr')
            )
        
        # Broadcast via WebSocket
        await manager.broadcast_device_update(device_eui, data)
    
    if mqtt_config:
        mqtt_client_instance = MQTTClient(
            broker_host=mqtt_config.get('broker_host', 'localhost'),
            broker_port=mqtt_config.get('broker_port', 1883),
            username=mqtt_config.get('username'),
            password=mqtt_config.get('password'),
            application_id=chirpstack_config.get('application_id'),
            device_data=device_data,
            update_callback=enhanced_update_callback  # Enhanced callback with database save
        )
        # Start MQTT client in background thread
        mqtt_thread = threading.Thread(target=mqtt_client_instance.start)
        mqtt_thread.daemon = True
        mqtt_thread.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global mqtt_client_instance
    if mqtt_client_instance:
        mqtt_client_instance.stop()

# Authentication endpoints following FastAPI OAuth2 JWT tutorial
@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
) -> Token:
    """Login endpoint following FastAPI tutorial"""
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate, session: Session = Depends(get_session)):
    """Register a new user"""
    if not ENABLE_ACCOUNT_CREATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account creation is currently disabled"
        )
    
    # Check if user already exists
    existing_user = session.exec(select(User).where(User.email == user_data.email)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hashed_password
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Legacy login endpoint for API compatibility
@app.post("/api/auth/login", response_model=Token)
async def api_login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """API login endpoint for compatibility"""
    return await login_for_access_token(form_data, session)

@app.get("/users/me/")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information following FastAPI tutorial"""
    return {
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active
    }

@app.get("/users/me/items/")
async def read_own_items(current_user: User = Depends(get_current_user)):
    """Get user's own items following FastAPI tutorial"""
    return [{"item_id": "IoT Dashboard", "owner": current_user.username}]

@app.get("/api/auth/me")
async def api_read_users_me(current_user: User = Depends(get_current_user)):
    """API endpoint for user information (compatibility)"""
    return await read_users_me(current_user)

# Web routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page"""
    return templates.TemplateResponse("register.html", {"request": request})

# API endpoints for device data
@app.get("/api/devices")
async def get_devices(current_user: User = Depends(get_current_user)):
    """Get all device data from ChirpStack with tags"""
    # Fetch devices from ChirpStack with tags
    print("🔍 Fetching devices from ChirpStack API...")
    chirpstack_devices = chirpstack_client.list_devices_with_tags()
    print(f"📊 ChirpStack devices count: {len(chirpstack_devices)}")
    
    if chirpstack_devices:
        print(f"🔧 Sample device: {chirpstack_devices[0].get('name', 'No name')} - Tags: {chirpstack_devices[0].get('tags', {})}")
    
    # Get live data from MQTT client
    mqtt_device_data = {}
    if mqtt_client_instance:
        mqtt_device_data = mqtt_client_instance.get_device_data()
        print(f"📡 MQTT device_data keys: {list(mqtt_device_data.keys())}")
    
    # Enhance device data with live information
    enhanced_devices = []
    for device in chirpstack_devices:
        dev_eui = device['dev_eui'].lower()  # Ensure lowercase for comparison
        
        # Get live data from MQTT client
        live_data = mqtt_device_data.get(dev_eui, {})
        
        if not live_data:
            # Create minimal live data structure
            live_data = {
                'last_seen': 'Never',
                'message_count': 0,
                'decoded_data': {},
                'device_name': device.get('name', 'Unknown'),
                'device_profile': device.get('device_profile_id', 'Unknown')
            }
        
        # Extract location from tags or use fallback
        location = device['tags'].get('location', device['tags'].get('zone', ''))
        
        enhanced_device = {
            **device,
            'live_data': live_data,
            'status': _get_device_status(live_data),
            'last_seen': live_data.get('last_seen', 'Never'),
            'location': location,
            'device_profile': live_data.get('device_profile', device.get('device_profile_id', 'Unknown'))
        }
        enhanced_devices.append(enhanced_device)
    
    print(f"✅ Returning {len(enhanced_devices)} enhanced devices")
    return {"devices": enhanced_devices}

@app.get("/api/grouping-options")
async def get_grouping_options(current_user: User = Depends(get_current_user)):
    """Get available grouping options from device tags"""
    print("🔍 Fetching grouping options from ChirpStack...")
    chirpstack_devices = chirpstack_client.list_devices_with_tags()
    print(f"📊 Found {len(chirpstack_devices)} devices for grouping analysis")
    
    # Collect all unique tag keys and values
    tag_keys = set()
    tag_values = {}
    
    for device in chirpstack_devices:
        device_tags = device.get('tags', {})
        print(f"🏷️ Device {device.get('name', 'Unknown')} tags: {device_tags}")
        for key, value in device_tags.items():
            tag_keys.add(key)
            if key not in tag_values:
                tag_values[key] = set()
            tag_values[key].add(value)
    
    print(f"🏷️ All tag keys found: {list(tag_keys)}")
    print(f"🏷️ Tag values: {tag_values}")
    
    # Convert sets to lists for JSON serialization
    grouping_options = {
        'available_tags': list(tag_keys),
        'tag_values': {k: list(v) for k, v in tag_values.items()}
    }
    
    print(f"✅ Returning grouping options: {grouping_options}")
    return grouping_options

@app.get("/api/devices/{dev_eui}")
async def get_device(dev_eui: str, current_user: User = Depends(get_current_user)):
    """Get specific device data"""
    live_data = device_data.get(dev_eui, {})
    config = load_config()
    device_config = None
    
    for device in config.get('devices', []):
        if device['dev_eui'] == dev_eui:
            device_config = device
            break
    
    if not device_config:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return {
        **device_config,
        'live_data': live_data,
        'status': _get_device_status(live_data),
        'last_seen': live_data.get('last_seen', 'Never')
    }

@app.post("/api/devices/{dev_eui}/control")
async def control_device(
    dev_eui: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Control device switches"""
    # Parse request body
    try:
        body = await request.json()
        action = body.get("action")
        switch = body.get("switch")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")
    
    if action not in ["on", "off"]:
        raise HTTPException(status_code=400, detail="Action must be 'on' or 'off'")
    
    # Import and use ChirpStack CLI functionality
    try:
        import sys
        import os
        
        # Add the project root to sys.path to import chirpstack_cli
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.append(project_root)
        
        from chirpstack_cli import get_client, _send_switch_command
        
        if switch and switch in ["switch_1", "switch_2"]:
            # Control specific switch
            _send_switch_command(dev_eui, action, switch)
            return {"message": f"Command sent: {switch} {action}", "success": True}
        else:
            # Control both switches
            _send_switch_command(dev_eui, action, "switch_1")
            _send_switch_command(dev_eui, action, "switch_2")
            return {"message": f"Command sent: both switches {action}", "success": True}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send command: {str(e)}")

@app.get("/api/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    """Get dashboard statistics"""
    config = load_config()
    total_devices = len(config.get('devices', []))
    
    # Get live data from MQTT client instead of old device_data
    mqtt_device_data = {}
    if mqtt_client_instance:
        mqtt_device_data = mqtt_client_instance.get_device_data()
    
    # Count active devices based on MQTT data
    active_devices = len([d for d in mqtt_device_data.values() if _is_device_active(d)])
    total_messages = sum(d.get('message_count', 0) for d in mqtt_device_data.values())
    
    print(f"📊 Stats calculation: {total_devices} total, {active_devices} active, {total_messages} messages")
    print(f"📊 MQTT device data keys: {list(mqtt_device_data.keys())}")
    
    return {
        "total_devices": total_devices,
        "active_devices": active_devices,
        "total_messages": total_messages,
        "gateways": len(config.get('gateways', [])),
        "last_update": datetime.now(timezone.utc).isoformat()
    }

def _get_device_status(live_data: Dict) -> str:
    """Determine device status based on live data"""
    if not live_data or not live_data.get('last_seen'):
        return "offline"
    
    try:
        # Handle both ISO format and the old format
        last_seen_str = live_data['last_seen']
        if 'T' in last_seen_str:
            # ISO format with timezone info
            last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
        else:
            # Old format - assume UTC
            last_seen = datetime.strptime(last_seen_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        
        # Ensure both times are timezone-aware for comparison
        now_utc = datetime.now(timezone.utc)
        time_diff = (now_utc - last_seen).total_seconds()
        
        if time_diff < 120:  # 2 minutes
            return "online"
        elif time_diff < 600:  # 10 minutes
            return "recent"
        else:
            return "offline"
    except:
        return "offline"

def _is_device_active(live_data: Dict) -> bool:
    """Check if device is currently active"""
    return _get_device_status(live_data) in ["online", "recent"]

def save_device_state(session: Session, device_eui: str, device_name: str, decoded_data: dict, 
                     message_count: int = 0, rssi: float = None, snr: float = None):
    """Save or update device state in SQLite"""
    try:
        # Check if device already exists
        existing_device = session.exec(select(DeviceState).where(DeviceState.device_eui == device_eui)).first()
        
        if existing_device:
            # Update existing device
            existing_device.device_name = device_name
            existing_device.last_seen = datetime.now(timezone.utc)
            existing_device.decoded_data = json.dumps(decoded_data)
            existing_device.message_count = message_count
            existing_device.rssi = rssi
            existing_device.snr = snr
            existing_device.updated_at = datetime.now(timezone.utc)
        else:
            # Create new device state
            new_device = DeviceState(
                device_eui=device_eui,
                device_name=device_name,
                last_seen=datetime.now(timezone.utc),
                decoded_data=json.dumps(decoded_data),
                message_count=message_count,
                rssi=rssi,
                snr=snr
            )
            session.add(new_device)
        
        session.commit()
        print(f"💾 Saved device state for {device_eui} to database")
        
    except Exception as e:
        print(f"❌ Error saving device state: {e}")
        session.rollback()

def load_device_states(session: Session) -> dict:
    """Load all device states from SQLite"""
    try:
        device_states = session.exec(select(DeviceState)).all()
        loaded_data = {}
        
        for device in device_states:
            try:
                decoded_data = json.loads(device.decoded_data) if device.decoded_data else {}
                loaded_data[device.device_eui] = {
                    'device_name': device.device_name,
                    'device_profile': 'Unknown',  # Will be updated from config
                    'message_count': device.message_count,
                    'last_seen': device.last_seen.replace(tzinfo=timezone.utc).isoformat(),
                    'decoded_data': decoded_data,
                    'rssi': device.rssi,
                    'snr': device.snr
                }
            except Exception as e:
                print(f"⚠️ Error parsing device data for {device.device_eui}: {e}")
                continue
        
        print(f"📥 Loaded {len(loaded_data)} device states from database")
        return loaded_data
        
    except Exception as e:
        print(f"❌ Error loading device states: {e}")
        return {}

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive
            data = await websocket.receive_text()
            # Echo back or handle any client messages if needed
            print(f"📨 Received WebSocket message: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=4000,
        reload=True,
        log_level="info"
    )
