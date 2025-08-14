"""
MQTT Client for receiving IoT device data
"""

import json
import threading
import time
import asyncio
from datetime import datetime
from typing import Dict, Optional, Callable
import paho.mqtt.client as mqtt


class MQTTClient:
    """MQTT client for receiving ChirpStack device data"""
    
    def __init__(self, broker_host: str, broker_port: int = 1883, 
                 username: Optional[str] = None, password: Optional[str] = None,
                 application_id: Optional[str] = None, device_data: Dict = None,
                 update_callback: Optional[Callable] = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.application_id = application_id
        self.device_data = device_data or {}
        self.client = None
        self.connected = False
        self.running = False
        self.update_callback = update_callback
        
    def start(self):
        """Start the MQTT client"""
        print(f"🔌 Starting MQTT client for {self.broker_host}:{self.broker_port}")
        
        try:
            # Use the new callback API version to avoid deprecation warning
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            # Set authentication if provided
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)
                print(f"🔐 Using MQTT authentication: {self.username}")
            
            # Connect to broker
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.running = True
            
            # Start the network loop
            self.client.loop_forever()
            
        except Exception as e:
            print(f"❌ MQTT client error: {e}")
            self.running = False
    
    def stop(self):
        """Stop the MQTT client"""
        print("🛑 Stopping MQTT client...")
        self.running = False
        if self.client:
            self.client.disconnect()
            self.client.loop_stop()
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when the client connects to the MQTT broker"""
        if rc == 0:
            self.connected = True
            print("✅ Connected to MQTT broker!")
            
            # Subscribe to device events
            if self.application_id:
                topic = f"application/{self.application_id}/device/+/event/up"
                client.subscribe(topic)
                print(f"📡 Subscribed to: {topic}")
            else:
                # Subscribe to all applications if no specific app ID
                topic = "application/+/device/+/event/up"
                client.subscribe(topic)
                print(f"📡 Subscribed to all applications: {topic}")
        else:
            print(f"❌ Failed to connect to MQTT broker, return code {rc}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback for when the client disconnects from the MQTT broker"""
        self.connected = False
        print("🔌 Disconnected from MQTT broker")
        
        if self.running and rc != 0:
            print("🔄 Attempting to reconnect...")
            time.sleep(5)
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            # Only process uplink messages
            if "/event/up" not in msg.topic:
                return
            
            payload = json.loads(msg.payload.decode())
            self._process_device_message(payload)
            
        except Exception as e:
            print(f"❌ Error processing MQTT message: {e}")
    
    def _process_device_message(self, payload: Dict):
        """Process a device uplink message"""
        try:
            # Extract device information
            device_info = payload.get('deviceInfo', {})
            device_eui = device_info.get('devEui', '').lower()
            device_name = device_info.get('deviceName', 'Unknown')
            device_profile = device_info.get('deviceProfileName', 'Unknown')
            
            if not device_eui:
                return
            
            # Initialize device data if not exists
            if device_eui not in self.device_data:
                self.device_data[device_eui] = {'message_count': 0}
            
            # Update device data
            self.device_data[device_eui].update({
                'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'message_count': self.device_data[device_eui]['message_count'] + 1,
                'decoded_data': payload.get('object', {}),
                'device_name': device_name,
                'device_profile': device_profile
            })
            
            # Extract signal information
            rx_info = payload.get('rxInfo', [])
            if rx_info:
                first_rx = rx_info[0]
                self.device_data[device_eui].update({
                    'rssi': first_rx.get('rssi'),
                    'snr': first_rx.get('snr'),
                    'gateway_id': first_rx.get('gatewayId')
                })
            
            # Extract transmission information
            tx_info = payload.get('txInfo', {})
            if tx_info:
                self.device_data[device_eui].update({
                    'frequency': tx_info.get('frequency'),
                    'spreading_factor': tx_info.get('modulation', {}).get('lora', {}).get('spreadingFactor')
                })
            
            print(f"📊 Updated data for device {device_name} ({device_eui[-8:]})")
            
            # Call the update callback if provided (for WebSocket broadcast)
            if self.update_callback:
                try:
                    # Run callback in a thread-safe way
                    import threading
                    def run_callback():
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.update_callback(device_eui, {
                                'decoded_data': payload.get('object', {}),
                                'last_seen': self.device_data[device_eui]['last_seen'],
                                'message_count': self.device_data[device_eui]['message_count'],
                                'rssi': self.device_data[device_eui].get('rssi'),
                                'snr': self.device_data[device_eui].get('snr')
                            }))
                            loop.close()
                        except Exception as e:
                            print(f"⚠️ WebSocket callback error: {e}")
                    
                    # Run in a separate thread to avoid blocking MQTT
                    callback_thread = threading.Thread(target=run_callback, daemon=True)
                    callback_thread.start()
                    
                except Exception as cb_error:
                    print(f"⚠️ Error in update callback setup: {cb_error}")
            
        except Exception as e:
            print(f"❌ Error processing device message: {e}")
    
    def get_device_data(self) -> Dict:
        """Get current device data"""
        return self.device_data.copy()
    
    def is_connected(self) -> bool:
        """Check if MQTT client is connected"""
        return self.connected
