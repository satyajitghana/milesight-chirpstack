// Dashboard JavaScript functionality

class IoTDashboard {
    constructor() {
        this.devices = [];
        this.stats = {};
        this.updateInterval = null;
        this.isUpdating = false;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.disabledSwitches = new Set(); // Track switches that are in 5-second disable period
        this.statsValues = { // Track current stats values for smooth animation
            'total-devices': 0,
            'active-devices': 0,
            'total-messages': 0
        };
        
        this.init();
        this.initAnimatedWeather();
        this.loadWeatherData();
    }

    async init() {
        console.log('🚀 Initializing IoT Dashboard...');
        
        // Load initial data from ChirpStack
        await this.loadInitialDeviceStates();
        
        // Set up WebSocket connection for real-time updates
        this.setupWebSocket();
        
        // Setup grouping dropdown listener
        this.setupGroupingControls();
        
        // Set up event listeners
        this.setupEventListeners();
        
        console.log('✅ Dashboard initialized successfully');
    }

    async loadInitialDeviceStates() {
        try {
            this.showLoadingState();
            
            // Load devices and stats in parallel
            const [devicesResponse, statsResponse] = await Promise.all([
                authManager.makeAuthenticatedRequest('/api/devices'),
                authManager.makeAuthenticatedRequest('/api/stats')
            ]);

            if (devicesResponse.ok && statsResponse.ok) {
                const devicesData = await devicesResponse.json();
                const statsData = await statsResponse.json();
                
                this.devices = devicesData.devices;
                this.stats = statsData;
                
                // Initialize stats values on first load to avoid animation from 0
                this.initializeStatsValues();
                
                this.updateDevicesGrid();
                this.updateStatsCards();
                this.hideLoadingState();
                
                console.log('📡 Initial device states loaded:', this.devices.length, 'devices');
            } else {
                throw new Error('Failed to load initial device states');
            }
        } catch (error) {
            console.error('Error loading initial device states:', error);
            this.showError('Failed to load initial device states');
        }
    }

    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('🔌 WebSocket connected');
                this.reconnectAttempts = 0;
                this.updateMqttStatus('connected');
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.ws.onclose = () => {
                console.log('🔌 WebSocket disconnected');
                this.updateMqttStatus('disconnected');
                this.attemptReconnection();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateMqttStatus('error');
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.updateMqttStatus('error');
        }
    }

    handleWebSocketMessage(data) {
        if (data.type === 'device_data') {
            this.updateDeviceData(data.device_eui, data.data);
        } else if (data.type === 'stats_update') {
            this.updateStats(data.stats);
        }
    }

    updateDeviceData(deviceEui, newData) {
        const deviceIndex = this.devices.findIndex(d => d.dev_eui.toLowerCase() === deviceEui.toLowerCase());
        
        if (deviceIndex !== -1) {
            // Check if any switches for this device are in disabled state
            const switchKey1 = `${deviceEui}-switch_1`;
            const switchKey2 = `${deviceEui}-switch_2`;
            const hasDisabledSwitch = this.disabledSwitches.has(switchKey1) || this.disabledSwitches.has(switchKey2);
            
            // Update device with new data
            this.devices[deviceIndex].live_data = {
                ...this.devices[deviceIndex].live_data,
                ...newData,
                last_seen: new Date().toISOString()
            };
            
            // If we have disabled switches and new data contains switch states, it means 
            // the device confirmed the switch state change - clear the disabled state
            if (hasDisabledSwitch && newData.decoded_data) {
                if (newData.decoded_data.switch_1 !== undefined) {
                    this.disabledSwitches.delete(switchKey1);
                    console.log('🔄 Switch 1 state confirmed by device, re-enabling early');
                    this.clearSwitchTimeout(deviceEui, 'switch_1');
                }
                if (newData.decoded_data.switch_2 !== undefined) {
                    this.disabledSwitches.delete(switchKey2);
                    console.log('🔄 Switch 2 state confirmed by device, re-enabling early');
                    this.clearSwitchTimeout(deviceEui, 'switch_2');
                }
            }
            
            // Update device status
            this.devices[deviceIndex].status = this.getDeviceStatus(this.devices[deviceIndex].live_data);
            this.devices[deviceIndex].last_seen = new Date().toISOString();
            
            // Update the device card in the UI
            this.updateSingleDeviceCard(this.devices[deviceIndex]);
            
            // Update stats
            this.updateStatsCards();
            
            console.log('📡 Device data updated via WebSocket:', deviceEui);
        }
    }

    updateSingleDeviceCard(device) {
        const deviceCard = document.querySelector(`[data-device-eui="${device.dev_eui}"]`);
        if (deviceCard) {
            deviceCard.outerHTML = this.createDeviceCard(device);
        }
    }

    getDeviceStatus(liveData) {
        if (!liveData || !liveData.last_seen) return 'offline';
        
        const lastSeen = new Date(liveData.last_seen);
        const now = new Date();
        const diffMinutes = (now - lastSeen) / (1000 * 60);
        
        if (diffMinutes < 2) return 'online';
        if (diffMinutes < 10) return 'recent';
        return 'offline';
    }

    updateMqttStatus(status) {
        const mqttStatus = document.getElementById('mqtt-status');
        if (!mqttStatus) return;
        
        const statusSpan = mqttStatus.querySelector('span:last-child');
        if (!statusSpan) return;
        
        switch (status) {
            case 'connected':
                statusSpan.textContent = 'Connected';
                statusSpan.className = 'text-green-600 font-medium';
                break;
            case 'disconnected':
                statusSpan.textContent = 'Disconnected';
                statusSpan.className = 'text-red-600 font-medium';
                break;
            case 'error':
                statusSpan.textContent = 'Error';
                statusSpan.className = 'text-red-600 font-medium';
                break;
            default:
                statusSpan.textContent = 'Connecting...';
                statusSpan.className = 'text-yellow-600 font-medium';
        }
    }

    attemptReconnection() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.pow(2, this.reconnectAttempts) * 1000; // Exponential backoff
            
            console.log(`🔄 Attempting WebSocket reconnection (${this.reconnectAttempts}/${this.maxReconnectAttempts}) in ${delay}ms`);
            
            setTimeout(() => {
                this.setupWebSocket();
            }, delay);
        } else {
            console.error('❌ Max WebSocket reconnection attempts reached');
            this.showError('Real-time updates unavailable. Please refresh the page.');
        }
    }

    updateDevicesGrid() {
        const grid = document.getElementById('devices-grid');
        if (!grid) return;
        
        // Get current grouping selection
        const groupingSelect = document.getElementById('grouping-select');
        const currentGrouping = groupingSelect ? groupingSelect.value : 'location';
        
        // Group devices by selected option
        const groupedDevices = this.groupDevices(this.devices, currentGrouping);
        
        let gridHtml = '';
        
        Object.entries(groupedDevices).forEach(([groupName, devices]) => {
            if (devices.length > 0) {
                gridHtml += `
                    <div class="col-span-full">
                        <h3 class="text-lg font-semibold text-slate-900 mb-4">
                            ${groupName}
                            <span class="text-sm font-normal text-slate-500 ml-2">(${devices.length} device${devices.length > 1 ? 's' : ''})</span>
                        </h3>
                    </div>
                `;
                gridHtml += devices.map(device => this.createDeviceCard(device)).join('');
            }
        });
        
        grid.innerHTML = gridHtml;
        
        console.log(`📱 Updated ${this.devices.length} device cards in ${Object.keys(groupedDevices).length} groups by ${currentGrouping}`);
    }

    groupDevices(devices, groupBy = 'location') {
        const groups = {};
        
        devices.forEach(device => {
            // Determine group based on selected grouping option
            let groupName = this.getDeviceGroup(device, groupBy);
            
            if (!groups[groupName]) {
                groups[groupName] = [];
            }
            groups[groupName].push(device);
        });
        
        return groups;
    }

    getDeviceGroup(device, groupBy) {
        const tags = device.tags || {};
        const name = device.name.toLowerCase();
        
        // Group by the selected tag
        switch (groupBy) {
            case 'location':
                return tags.location || device.location || 'Unknown Location';
            
            case 'function':
                return tags.function || this.inferFunction(device) || 'Unknown Function';
            
            case 'type':
                return tags.type || this.inferType(device) || 'Unknown Type';
            
            case 'zone':
                return tags.zone || 'Unknown Zone';
            
            case 'manufacturer':
                return tags.manufacturer || 'Unknown Manufacturer';
            
            case 'priority':
                return tags.priority || 'Normal Priority';
            
            default:
                return tags[groupBy] || 'Unknown';
        }
    }

    inferFunction(device) {
        const name = device.name.toLowerCase();
        if (name.includes('switch')) return 'Lighting Control';
        if (name.includes('temperature') || name.includes('humidity')) return 'Environmental Monitoring';
        if (name.includes('power') || name.includes('current')) return 'Power Monitoring';
        if (name.includes('pir') || name.includes('motion')) return 'Security & Motion';
        return 'General IoT';
    }

    inferType(device) {
        const name = device.name.toLowerCase();
        if (name.includes('switch')) return 'Smart Switch';
        if (name.includes('temperature')) return 'Environmental Sensor';
        if (name.includes('power')) return 'Power Monitor';
        if (name.includes('pir')) return 'Motion Sensor';
        return 'IoT Device';
    }

    createDeviceCard(device) {
        const statusIcon = this.getStatusIcon(device.status);
        const liveData = device.live_data || {};
        const decodedData = liveData.decoded_data || {};
        
        // Check if this is a WS502 switch device
        const isSwitch = device.name.includes('WS502') || 
                        device.description.includes('WS502') ||
                        Object.values(device.tags || {}).some(v => v.includes('WS502'));

        return `
            <div class="stats-card device-card no-animation" data-device-eui="${device.dev_eui}">
                <div class="stats-title device-title">
                    <div class="flex-1 pr-2">
                        <p class="stats-title-text">${device.name}</p>
                        <p class="text-xs text-slate-500 mt-1 leading-relaxed">${device.location || device.description || 'No description'}</p>
                    </div>
                    <div class="flex flex-col items-end gap-2 flex-shrink-0">
                        ${statusIcon}
                        <span class="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600 whitespace-nowrap">
                            ${this.getDeviceTypeLabel(device)}
                        </span>
                    </div>
                </div>
                <div class="stats-data">
                    ${this.renderSensorData(decodedData, device.device_profile, device.name)}
                    ${isSwitch ? this.renderSwitchControls(device, decodedData) : ''}
                    <div class="text-xs text-slate-500 mt-4 pt-3 border-t border-slate-200">
                        Updated ${this.getRelativeTime(device.last_seen)}
                    </div>
                </div>
            </div>
        `;
    }

    getDeviceTypeLabel(device) {
        const name = device.name.toLowerCase();
        if (name.includes('switch')) return 'Smart Switch';
        if (name.includes('pir') && name.includes('light')) return 'PIR & Light Sensor';
        if (name.includes('temperature')) return 'Temp & Humidity';
        if (name.includes('current')) return 'Current Sensor';
        return device.device_profile || 'Unknown Type';
    }

    renderSensorData(decodedData, deviceProfile, deviceName) {
        if (!decodedData || Object.keys(decodedData).length === 0) {
            return `
                <div class="text-sm text-muted text-center py-4">
                    No sensor data available
                </div>
            `;
        }

        // Check for special device types
        const isPowerDevice = deviceName.toLowerCase().includes('power') || deviceName.toLowerCase().includes('current');
        const isPirLightDevice = deviceName.toLowerCase().includes('pir') && deviceName.toLowerCase().includes('light');
        const isSwitchDevice = deviceName.toLowerCase().includes('switch');
        const isTemperatureDevice = deviceName.toLowerCase().includes('temperature') || deviceName.toLowerCase().includes('temp');
        
        if (isPowerDevice) {
            return this.renderPowerData(decodedData);
        }
        
        if (isPirLightDevice) {
            return this.renderPirLightData(decodedData);
        }

        if (isTemperatureDevice && decodedData.temperature !== undefined) {
            return this.renderTemperatureData(decodedData);
        }

        // For switch devices, don't render sensor data here - it's handled in renderSwitchControls
        if (isSwitchDevice) {
            return '';
        }

        let sensorHtml = '<div class="grid grid-cols-2 gap-3">';

        for (const [key, value] of Object.entries(decodedData)) {
            // Skip switch-related fields for sensor data display
            if (key.includes('switch') || key.includes('change')) continue;

            const sensorInfo = this.getSensorDisplayInfo(key, value, deviceProfile);
            if (sensorInfo) {
                sensorHtml += `
                    <div class="power-metric">
                        <div class="flex items-center justify-center mb-2">
                            ${sensorInfo.icon}
                        </div>
                        <div class="power-metric-label">${sensorInfo.label}</div>
                        <div class="power-metric-value ${sensorInfo.colorClass}">${sensorInfo.value}</div>
                    </div>
                `;
            }
        }

        sensorHtml += '</div>';
        return sensorHtml;
    }

    renderPowerData(decodedData) {
        let powerHtml = '<div class="grid grid-cols-2 gap-3">';
        
        // Current readings with icons
        if (decodedData.current !== undefined) {
            powerHtml += `
                <div class="power-metric">
                    <div class="flex items-center justify-center mb-2">
                        <box-icon name="trending-up" size="16px" color="#8b5cf6"></box-icon>
                    </div>
                    <div class="power-metric-label">Current</div>
                    <div class="power-metric-value">${decodedData.current.toFixed(1)}A</div>
                </div>
            `;
        }
        
        if (decodedData.total_current !== undefined) {
            powerHtml += `
                <div class="power-metric">
                    <div class="flex items-center justify-center mb-2">
                        <box-icon name="plus-circle" size="16px" color="#22c55e"></box-icon>
                    </div>
                    <div class="power-metric-label">Accumulated Current</div>
                    <div class="power-metric-value">${decodedData.total_current.toFixed(1)}A</div>
                </div>
            `;
        }
        
        if (decodedData.temperature !== undefined) {
            powerHtml += `
                <div class="power-metric">
                    <div class="flex items-center justify-center mb-2">
                        <box-icon type="solid" name="thermometer" size="16px" color="#ef4444"></box-icon>
                    </div>
                    <div class="power-metric-label">Temperature</div>
                    <div class="power-metric-value">${decodedData.temperature}°C</div>
                </div>
            `;
        }
        
        powerHtml += '</div>';
        return powerHtml;
    }

    renderPirLightData(decodedData) {
        let sensorHtml = '<div class="grid grid-cols-2 gap-4">';
        
        // PIR Motion Sensor
        if (decodedData.pir !== undefined) {
            const isMotion = decodedData.pir.toLowerCase().includes('trigger') || decodedData.pir.toLowerCase().includes('motion');
            const motionClass = isMotion ? 'motion-switch motion-detected' : 'motion-switch';
            sensorHtml += `
                <div class="text-center">
                    <label class="text-xs font-medium text-muted mb-2 block">Motion</label>
                    <input id="motion-checkbox-${Math.random().toString(36).substr(2, 9)}" type="checkbox" ${isMotion ? 'checked' : ''} disabled>
                    <label class="${motionClass}" style="margin: 0 auto;">
                        <svg viewBox="0 0 448 512" class="motion-svg">
                            <path d="M320 48a48 48 0 1 0 -96 0 48 48 0 1 0 96 0zM125.7 175.5c9.9-9.9 23.4-15.5 37.5-15.5c1.9 0 3.8 .1 5.6 .3L137.6 254c-9.3 28 1.7 58.8 26.8 74.5l86.2 53.9-25.4 88.8c-4.9 17 5 34.7 22 39.6s34.7-5 39.6-22l28.7-100.4c5.9-20.6-2.6-42.6-20.7-53.9L238 299l30.9-82.4 5.1 12.3C289 264.7 323.9 288 362.7 288H384c17.7 0 32-14.3 32-32s-14.3-32-32-32H362.7c-12.9 0-24.6-7.8-29.5-19.7l-6.3-15c-14.6-35.1-44.1-61.9-80.5-73.1l-48.7-15c-11.1-3.4-22.7-5.2-34.4-5.2c-31 0-60.8 12.3-82.7 34.3L57.4 153.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0l23.1-23.1zM91.2 352H32c-17.7 0-32 14.3-32 32s14.3 32 32 32h69.6c19 0 36.2-11.2 43.9-28.5L157 361.6l-9.5-6c-17.5-10.9-30.5-26.8-37.9-44.9L91.2 352z"></path>
                        </svg>
                        ${isMotion ? 'MOTION' : 'None'}
                    </label>
                </div>
            `;
        }
        
        // Daylight Sensor
        if (decodedData.daylight !== undefined) {
            const isDim = decodedData.daylight.toLowerCase() === 'dim';
            const uniqueId = `light-${Math.random().toString(36).substr(2, 9)}`;
            // When it's dim, show night mode (checked). When bright, show day mode (unchecked)
            sensorHtml += `
                <div class="text-center" style="display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 0.5rem 0;">
                    <label class="text-xs font-medium text-muted mb-2 block">Light</label>
                    <div style="width: 7em; height: 3em; display: flex; align-items: center; justify-content: center; overflow: visible;">
                        <label class="theme-toggle-button" style="font-size: 17px; position: relative; display: inline-block; width: 100%; cursor: pointer;">
                        <input type="checkbox" id="${uniqueId}" ${isDim ? 'checked' : ''} disabled style="opacity: 0; width: 0; height: 0;">
                        <svg viewBox="0 0 69.667 44" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns="http://www.w3.org/2000/svg" style="transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1); width: 100%; height: auto; max-width: 100%; overflow: visible;">
                            <defs>
                                <filter id="container-${uniqueId}">
                                    <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="rgba(0,0,0,0.3)"/>
                                </filter>
                            </defs>
                            <g transform="translate(3.5 3.5)" data-name="Component 15 – 1">
                                <g filter="url(#container-${uniqueId})" transform="matrix(1, 0, 0, 1, -3.5, -3.5)">
                                    <rect fill="${isDim ? '#2b4360' : '#83cbd8'}" transform="translate(3.5 3.5)" rx="17.5" height="35" width="60.667" class="container"></rect>
                                </g>
                                <g transform="translate(${isDim ? '30.333' : '2.333'} 2.333)" class="button" style="transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);">
                                    <g class="sun" style="opacity: ${isDim ? '0' : '1'}; transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1);">
                                        <circle fill="#f8e664" r="15.167" cy="15.167" cx="15.167"></circle>
                                        <circle fill="#fcf4b9" transform="translate(8.167 8.167)" r="7" cy="7" cx="7"></circle>
                                    </g>
                                    <g class="moon" style="opacity: ${isDim ? '1' : '0'}; transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1);">
                                        <circle fill="#cce6ee" r="15.167" cy="15.167" cx="15.167"></circle>
                                        <g fill="#a6cad0" transform="translate(-24.415 -1.009)">
                                            <circle transform="translate(43.009 4.496)" r="2" cy="2" cx="2"></circle>
                                            <circle transform="translate(39.366 17.952)" r="2" cy="2" cx="2"></circle>
                                            <circle transform="translate(33.016 8.044)" r="1" cy="1" cx="1"></circle>
                                            <circle transform="translate(51.081 18.888)" r="1" cy="1" cx="1"></circle>
                                            <circle transform="translate(33.016 22.503)" r="1" cy="1" cx="1"></circle>
                                            <circle transform="translate(50.081 10.53)" r="1.5" cy="1.5" cx="1.5"></circle>
                                        </g>
                                    </g>
                                </g>
                                <g fill="#fff" class="cloud" style="opacity: ${isDim ? '0' : '1'}; transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1);">
                                    <path d="M12,20 Q8,16 14,16 Q18,12 22,16 Q26,14 24,20 Q20,24 12,20 Z" />
                                </g>
                                <g fill="#def8ff" transform="translate(3.585 1.325)" class="stars" style="opacity: ${isDim ? '1' : '0'}; transition: opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1);">
                                    <circle r="1" cy="5" cx="10"></circle>
                                    <circle r="1" cy="15" cx="20"></circle>
                                    <circle r="1" cy="25" cx="15"></circle>
                                    <circle r="0.5" cy="8" cx="25"></circle>
                                    <circle r="0.5" cy="18" cx="5"></circle>
                                </g>
                            </g>
                        </svg>
                    </label>
                    </div>
                    <div class="text-xs font-medium mt-2 ${isDim ? 'text-blue-400' : 'text-yellow-600'}">${decodedData.daylight.charAt(0).toUpperCase() + decodedData.daylight.slice(1)}</div>
                </div>
            `;
        }
        
        // Battery if available
        if (decodedData.battery !== undefined) {
            sensorHtml += `
                <div class="power-metric col-span-2">
                    <div class="flex items-center justify-center mb-2">
                        <box-icon name="battery" size="16px" color="#22c55e"></box-icon>
                    </div>
                    <div class="power-metric-label">Battery</div>
                    <div class="power-metric-value text-green-600">${decodedData.battery}%</div>
                </div>
            `;
        }
        
        sensorHtml += '</div>';
        return sensorHtml;
    }

    renderTemperatureData(decodedData) {
        const temperature = decodedData.temperature || 0;
        const tempId = Math.random().toString(36).substr(2, 9);
        
        let sensorHtml = '<div class="grid grid-cols-2 gap-4">';
        
        // Beautiful Temperature Dial
        sensorHtml += `
            <div class="col-span-2 flex justify-center">
                <div class="temp" id="temp-${tempId}">
                    <div class="temp__logo">Inkers</div>
                    <div class="temp__comet"></div>
                    <canvas class="temp__fizz"></canvas>
                    <div class="temp__label">Temp</div>
                    <div class="temp__value">${Math.round(temperature)}</div>
                    <div class="temp__dial"></div>
                </div>
            </div>
        `;
        
        // Other sensors if available
        if (decodedData.humidity !== undefined) {
            sensorHtml += `
                <div class="power-metric">
                    <div class="flex items-center justify-center mb-2">
                        <box-icon name="droplet" size="16px" color="#3b82f6"></box-icon>
                    </div>
                    <div class="power-metric-label">Humidity</div>
                    <div class="power-metric-value text-blue-600">${decodedData.humidity}%</div>
                </div>
            `;
        }
        
        if (decodedData.battery !== undefined) {
            sensorHtml += `
                <div class="power-metric">
                    <div class="flex items-center justify-center mb-2">
                        <box-icon name="battery" size="16px" color="#22c55e"></box-icon>
                    </div>
                    <div class="power-metric-label">Battery</div>
                    <div class="power-metric-value text-green-600">${decodedData.battery}%</div>
                </div>
            `;
        }
        
        // Occupancy status
        if (decodedData.occupancy !== undefined) {
            const isOccupied = decodedData.occupancy.toLowerCase() === 'occupied';
            sensorHtml += `
                <div class="power-metric col-span-2">
                    <div class="flex items-center justify-center mb-2">
                        <div class="occupancy-indicator ${isOccupied ? 'occupied' : 'vacant'}">
                            <box-icon name="user" size="16px" color="${isOccupied ? '#22c55e' : '#64748b'}"></box-icon>
                        </div>
                    </div>
                    <div class="power-metric-label">Occupancy</div>
                    <div class="power-metric-value ${isOccupied ? 'text-green-600' : 'text-gray-500'}">${decodedData.occupancy.toUpperCase()}</div>
                </div>
            `;
        }
        
        sensorHtml += '</div>';
        
        // Initialize the temperature dial after rendering
        setTimeout(() => {
            this.initTemperatureDial(tempId, temperature);
        }, 100);
        
        return sensorHtml;
    }

    initTemperatureDial(tempId, temperature) {
        const tempEl = document.getElementById(`temp-${tempId}`);
        if (!tempEl) return;
        
        const tempMin = 0;
        const tempMax = 50;
        const tempRange = tempMax - tempMin;
        const relTemp = Math.max(0, Math.min(temperature - tempMin, tempRange));
        const frac = relTemp / tempRange;
        const angle = frac * 360;
        const hueStart = 240;
        const hueEnd = 360;
        const newHue = hueStart + (frac * (hueEnd - hueStart));
        
        tempEl.style.setProperty("--angle", angle);
        tempEl.style.setProperty("--hue", newHue);
        
        // Initialize canvas fizz effect
        const fizz = tempEl.querySelector('.temp__fizz');
        if (fizz) {
            const fc = fizz.getContext('2d');
            const fW = 160;
            const fH = 160;
            fizz.width = fW;
            fizz.height = fH;
            
            fc.clearRect(0, 0, fW, fH);
            fc.fillStyle = `hsla(${newHue},100%,50%,0.5)`;
            fc.globalAlpha = 0.25 + (0.75 * frac);
            
            const centerX = fW / 2;
            const centerY = fH / 2;
            
            // Create fizz particles
            for (let i = 0; i < 100; i++) {
                const pd = 75 + frac * 20;
                const pa = Math.random() * 360;
                const x = centerX + pd * Math.sin(pa * Math.PI / 180);
                const y = centerY + pd * Math.cos(pa * Math.PI / 180);
                
                fc.beginPath();
                fc.arc(x, y, 1, 0, Math.PI * 2);
                fc.fill();
                fc.closePath();
            }
        }
    }

    getSensorDisplayInfo(key, value, deviceProfile) {
        const lowerKey = key.toLowerCase();
        let icon, label, formattedValue, colorClass = '';

        // Temperature
        if (lowerKey.includes('temperature')) {
            icon = '<box-icon type="solid" name="thermometer" size="14px" color="#ef4444"></box-icon>';
            label = 'Temperature';
            formattedValue = `${value}°C`;
            if (value < 0) colorClass = 'text-blue-600';
            else if (value < 20) colorClass = 'text-cyan-600';
            else if (value > 30) colorClass = 'text-red-600';
        }
        // Humidity
        else if (lowerKey.includes('humidity')) {
            icon = '<box-icon name="droplet" size="14px" color="#3b82f6"></box-icon>';
            label = 'Humidity';
            formattedValue = `${value}%`;
            if (value < 30) colorClass = 'text-yellow-600';
            else if (value > 60) colorClass = 'text-blue-600';
        }
        // Battery
        else if (lowerKey.includes('battery')) {
            icon = '<box-icon name="battery" size="14px" color="#22c55e"></box-icon>';
            label = 'Battery';
            formattedValue = `${value}%`;
            if (value >= 75) colorClass = 'text-green-600';
            else if (value >= 25) colorClass = 'text-yellow-600';
            else colorClass = 'text-red-600';
        }
        // Voltage
        else if (lowerKey.includes('voltage')) {
            icon = '<box-icon type="solid" name="zap" size="16px" color="#eab308"></box-icon>';
            label = 'Voltage';
            formattedValue = `${value}V`;
        }
        // Current
        else if (lowerKey.includes('current')) {
            icon = '<box-icon name="trending-up" size="14px" color="#8b5cf6"></box-icon>';
            label = 'Current';
            const currentA = deviceProfile && deviceProfile.includes('CT10') ? value : value / 1000;
            formattedValue = `${currentA.toFixed(2)}A`;
        }
        // Power
        else if (lowerKey.includes('power') && !lowerKey.includes('factor')) {
            icon = '<box-icon name="bolt-circle" size="14px" color="#f97316"></box-icon>';
            label = 'Power';
            formattedValue = `${value}W`;
        }
        // PIR/Motion
        else if (lowerKey.includes('pir') || lowerKey.includes('motion')) {
            const isTriggered = value.toLowerCase().includes('trigger') || value.toLowerCase().includes('motion');
            icon = `<box-icon name="walk" size="14px" color="${isTriggered ? '#ef4444' : '#64748b'}"></box-icon>`;
            label = 'Motion';
            formattedValue = isTriggered ? 'Detected' : 'None';
            colorClass = isTriggered ? 'text-red-600' : 'text-muted';
        }
        // Occupancy
        else if (lowerKey.includes('occupancy')) {
            const isOccupied = value.toLowerCase() === 'occupied';
            icon = `<box-icon name="user-check" size="14px" color="${isOccupied ? '#ef4444' : '#64748b'}"></box-icon>`;
            label = 'Occupancy';
            formattedValue = isOccupied ? 'Occupied' : 'Vacant';
            colorClass = isOccupied ? 'text-red-600' : 'text-muted';
        }
        // Daylight
        else if (lowerKey.includes('daylight')) {
            const isBright = value.toLowerCase() === 'bright';
            icon = `<box-icon name="sun" size="14px" color="${isBright ? '#eab308' : '#64748b'}"></box-icon>`;
            label = 'Light';
            formattedValue = value.charAt(0).toUpperCase() + value.slice(1);
            colorClass = isBright ? 'text-yellow-600' : 'text-muted';
        }
        else {
            return null; // Skip unknown sensor types
        }

        return { icon, label, value: formattedValue, colorClass };
    }

    renderSwitchControls(device, decodedData) {
        const switch1State = decodedData.switch_1;
        const switch2State = decodedData.switch_2;
        // Handle both numeric (0/1) and string ('on'/'off') states
        const switch1On = switch1State === 1 || switch1State === '1' || (typeof switch1State === 'string' && switch1State.toLowerCase() === 'on');
        const switch2On = switch2State === 1 || switch2State === '1' || (typeof switch2State === 'string' && switch2State.toLowerCase() === 'on');

        return `
            <div class="mt-4 space-y-4">
                <div class="grid grid-cols-2 gap-6">
                    <div class="text-center">
                        <label class="text-xs font-medium text-muted mb-3 block">Switch 1</label>
                        <label class="panel" id="switch-${device.dev_eui}-1-container">
                            <input 
                                class="input" 
                                type="checkbox" 
                                ${switch1On ? 'checked' : ''}
                                onchange="dashboard.toggleSwitch3D('${device.dev_eui}', this.checked ? 'on' : 'off', 'switch_1')"
                                id="switch-${device.dev_eui}-1" />
                            <div class="hole">
                                <div class="switch">
                                    <div class="shadow-box top">
                                        <div class="shadow top"></div>
                                    </div>
                                    <div class="shadow-box bottom">
                                        <div class="shadow bottom"></div>
                                    </div>
                                    <div class="switch_top">
                                        <div class="outsetTop"></div>
                                    </div>
                                    <div class="switch_bottom">
                                        <div class="outsetBottom"></div>
                                    </div>
                                    <div class="indicators_container">
                                        <div class="indicator indicator-off"></div>
                                        <div class="indicator indicator-on"></div>
                                    </div>
                                </div>
                            </div>
                        </label>
                        <div class="text-xs font-medium mt-2 ${switch1On ? 'text-green-600' : 'text-red-600'}">
                            ${switch1On ? 'ON' : 'OFF'}
                        </div>
                    </div>
                    
                    <div class="text-center">
                        <label class="text-xs font-medium text-muted mb-3 block">Switch 2</label>
                        <label class="panel" id="switch-${device.dev_eui}-2-container">
                            <input 
                                class="input" 
                                type="checkbox" 
                                ${switch2On ? 'checked' : ''}
                                onchange="dashboard.toggleSwitch3D('${device.dev_eui}', this.checked ? 'on' : 'off', 'switch_2')"
                                id="switch-${device.dev_eui}-2" />
                            <div class="hole">
                                <div class="switch">
                                    <div class="shadow-box top">
                                        <div class="shadow top"></div>
                                    </div>
                                    <div class="shadow-box bottom">
                                        <div class="shadow bottom"></div>
                                    </div>
                                    <div class="switch_top">
                                        <div class="outsetTop"></div>
                                    </div>
                                    <div class="switch_bottom">
                                        <div class="outsetBottom"></div>
                                    </div>
                                    <div class="indicators_container">
                                        <div class="indicator indicator-off"></div>
                                        <div class="indicator indicator-on"></div>
                                    </div>
                                </div>
                            </div>
                        </label>
                        <div class="text-xs font-medium mt-2 ${switch2On ? 'text-green-600' : 'text-red-600'}">
                            ${switch2On ? 'ON' : 'OFF'}
                        </div>
                    </div>
                </div>
                ${this.renderPowerMetrics(decodedData)}
            </div>
        `;
    }

    renderPowerMetrics(decodedData) {
        // Only show Voltage, Current, and Power Factor (not duplicate power readings)
        if (!decodedData.voltage && !decodedData.current && !decodedData.power_factor) {
            return '';
        }

        let metricsHtml = '<div class="grid grid-cols-3 gap-2">';
        
        if (decodedData.voltage) {
            metricsHtml += `
                <div class="power-metric">
                    <div class="flex items-center justify-center mb-1">
                        <box-icon type="solid" name="zap" size="12px" color="#eab308"></box-icon>
                    </div>
                    <div class="power-metric-label">Voltage</div>
                    <div class="power-metric-value">${decodedData.voltage}V</div>
                </div>
            `;
        }
        
        if (decodedData.current) {
            metricsHtml += `
                <div class="power-metric">
                    <div class="flex items-center justify-center mb-1">
                        <box-icon name="trending-up" size="12px" color="#8b5cf6"></box-icon>
                    </div>
                    <div class="power-metric-label">Current</div>
                    <div class="power-metric-value">${decodedData.current}mA</div>
                </div>
            `;
        }
        
        // Only show power factor, not active_power
        if (decodedData.power_factor !== undefined) {
            metricsHtml += `
                <div class="power-metric">
                    <div class="flex items-center justify-center mb-1">
                        <box-icon name="math" size="12px" color="#6366f1"></box-icon>
                    </div>
                    <div class="power-metric-label">Power Factor</div>
                    <div class="power-metric-value">${decodedData.power_factor}</div>
                </div>
            `;
        }
        
        metricsHtml += '</div>';
        return metricsHtml;
    }

    formatSensorValue(key, value, deviceProfile) {
        const lowerKey = key.toLowerCase();
        
        if (typeof value === 'number') {
            if (lowerKey.includes('temperature')) {
                return `${value}°C`;
            } else if (lowerKey.includes('humidity')) {
                return `${value}%`;
            } else if (lowerKey.includes('voltage')) {
                return `${value}V`;
            } else if (lowerKey.includes('current')) {
                if (deviceProfile && deviceProfile.includes('CT10')) {
                    return `${value.toFixed(3)}A`;
                } else {
                    return `${(value / 1000).toFixed(3)}A`;
                }
            } else if (lowerKey.includes('power')) {
                return `${value}W`;
            } else if (lowerKey.includes('battery')) {
                return `${value}%`;
            }
            return value.toString();
        }
        
        return value.toString();
    }

    initializeStatsValues() {
        // Get current DOM values to preserve any existing state
        const elements = ['total-devices', 'active-devices', 'total-messages'];
        elements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                // Try to get existing value from DOM, fallback to stats, then 0
                const domValue = parseInt(element.textContent.replace(/,/g, '')) || 0;
                const statsValue = this.stats[id.replace('-', '_')] || 0;
                
                // Use the DOM value if it exists and is reasonable, otherwise use stats
                this.statsValues[id] = domValue > 0 ? domValue : statsValue;
                
                // Set DOM to the tracked value to ensure consistency
                element.textContent = this.statsValues[id].toLocaleString();
            }
        });
        
        console.log('📊 Initialized stats values:', this.statsValues);
    }

    updateStatsCards() {
        const newValues = {
            'total-devices': this.stats.total_devices || 0,
            'active-devices': this.stats.active_devices || 0,
            'total-messages': this.stats.total_messages || 0
        };

        Object.entries(newValues).forEach(([id, newValue]) => {
            const element = document.getElementById(id);
            if (element) {
                const currentValue = this.statsValues[id];
                console.log(`📊 Stats update - ${id}: ${currentValue} → ${newValue}`);
                
                // Only animate if the value has actually changed
                if (currentValue !== newValue) {
                    console.log(`🎬 Animating ${id} from ${currentValue} to ${newValue}`);
                    this.animateNumber(element, currentValue, newValue);
                    this.statsValues[id] = newValue; // Update tracked value
                } else {
                    console.log(`⏸️ No change for ${id}, skipping animation`);
                }
            }
        });

        // Update percentages and progress bars for beautiful stats cards
        const totalDevices = this.stats.total_devices || 0;
        const activeDevices = this.stats.active_devices || 0;
        const totalMessages = this.stats.total_messages || 0;
        
        // Calculate online percentage
        const onlinePercentage = totalDevices > 0 ? Math.round((activeDevices / totalDevices) * 100) : 0;
        const onlinePercentEl = document.getElementById('online-percent');
        const onlineFillEl = document.getElementById('online-fill');
        
        if (onlinePercentEl) {
            onlinePercentEl.innerHTML = `
                <box-icon name="up-arrow" size="14px" color="#02972f"></box-icon>
                ${onlinePercentage}%
            `;
        }
        
        if (onlineFillEl) {
            onlineFillEl.style.width = `${onlinePercentage}%`;
        }
        
        // Update message count with k suffix
        const messagePercentEl = document.getElementById('message-percent');
        if (messagePercentEl) {
            const messageK = Math.round(totalMessages / 1000);
            messagePercentEl.textContent = messageK;
        }
        
        const messageFillEl = document.getElementById('message-fill');
        if (messageFillEl) {
            // Calculate message fill based on some arbitrary max (e.g., 10k messages = 100%)
            const messagePercentage = Math.min((totalMessages / 10000) * 100, 100);
            messageFillEl.style.width = `${messagePercentage}%`;
        }

        // Update last update time
        const lastUpdateElement = document.getElementById('last-update');
        if (lastUpdateElement) {
            lastUpdateElement.textContent = new Date().toLocaleTimeString();
        }
    }

    animateNumber(element, start, end) {
        // Cancel any existing animation for this element
        if (element.animationId) {
            cancelAnimationFrame(element.animationId);
        }
        
        const duration = 800; // Slightly faster animation
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Use easing function for smoother animation
            const easeProgress = progress < 0.5 
                ? 2 * progress * progress 
                : 1 - Math.pow(-2 * progress + 2, 3) / 2;
            
            const current = Math.floor(start + (end - start) * easeProgress);
            element.textContent = current.toLocaleString();
            
            if (progress < 1) {
                element.animationId = requestAnimationFrame(animate);
            } else {
                // Ensure final value is exact
                element.textContent = end.toLocaleString();
                element.animationId = null;
            }
        };

        element.animationId = requestAnimationFrame(animate);
    }

    async toggleSwitch(devEui, action, switchType) {
        const buttonId = `switch-${devEui}-${switchType === 'switch_1' ? '1' : '2'}`;
        const button = document.getElementById(buttonId);
        
        if (!button) return;
        
        try {
            // Disable button immediately
            button.disabled = true;
            button.innerHTML = '<div class="loading-spinner"></div>Sending...';
            
            const response = await authManager.makeAuthenticatedRequest(`/api/devices/${devEui}/control`, {
                method: 'POST',
                body: JSON.stringify({
                    action: action,
                    switch: switchType
                })
            });

            if (response.ok) {
                const result = await response.json();
                this.showToast(`${switchType.replace('_', ' ')} turned ${action}`, 'success');
                
                // Update button state immediately
                const isOn = action === 'on';
                button.className = `btn btn-sm w-full ${isOn ? 'btn-switch-on' : 'btn-switch-off'}`;
                button.innerHTML = `<box-icon name="power-off" size="14px" color="white"></box-icon>${isOn ? 'ON' : 'OFF'}`;
                
            } else {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to send command');
            }
        } catch (error) {
            console.error('Switch control error:', error);
            this.showToast(`Error: ${error.message}`, 'error');
            
            // Reset button to previous state
            const currentState = button.classList.contains('btn-switch-on');
            button.className = `btn btn-sm w-full ${currentState ? 'btn-switch-on' : 'btn-switch-off'}`;
            button.innerHTML = `<box-icon name="power-off" size="14px" color="white"></box-icon>${currentState ? 'ON' : 'OFF'}`;
        } finally {
            // Re-enable button after 5 seconds
            setTimeout(() => {
                button.disabled = false;
                
                // Update onclick for next toggle
                const currentlyOn = button.classList.contains('btn-switch-on');
                const nextAction = currentlyOn ? 'off' : 'on';
                button.setAttribute('onclick', `dashboard.toggleSwitch('${devEui}', '${nextAction}', '${switchType}')`);
            }, 5000);
        }
    }

    async toggleSwitch3D(devEui, action, switchType) {
        const checkbox = document.getElementById(`switch-${devEui}-${switchType === 'switch_1' ? '1' : '2'}`);
        const container = document.getElementById(`switch-${devEui}-${switchType === 'switch_1' ? '1' : '2'}-container`);
        
        if (!checkbox || !container) return;
        
        try {
            // Disable the switch immediately and visually indicate it's disabled
            checkbox.disabled = true;
            container.style.pointerEvents = 'none';
            container.style.opacity = '0.6';
            container.style.filter = 'grayscale(0.3)';
            
            // Add a visual indicator that it's processing
            const processingIndicator = document.createElement('div');
            processingIndicator.className = 'absolute inset-0 flex items-center justify-center bg-black bg-opacity-20 rounded-lg';
            processingIndicator.innerHTML = '<div class="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>';
            processingIndicator.id = `processing-${devEui}-${switchType}`;
            container.style.position = 'relative';
            container.appendChild(processingIndicator);
            
            const response = await authManager.makeAuthenticatedRequest(`/api/devices/${devEui}/control`, {
                method: 'POST',
                body: JSON.stringify({
                    action: action,
                    switch: switchType
                })
            });

            if (response.ok) {
                const result = await response.json();
                this.showToast(`${switchType.replace('_', ' ')} turned ${action}`, 'success');
                
                // Update the device data to reflect the switch state change
                const deviceIndex = this.devices.findIndex(d => d.dev_eui === devEui);
                if (deviceIndex !== -1) {
                    // Update the switch state in device data
                    if (!this.devices[deviceIndex].live_data) {
                        this.devices[deviceIndex].live_data = {};
                    }
                    if (!this.devices[deviceIndex].live_data.decoded_data) {
                        this.devices[deviceIndex].live_data.decoded_data = {};
                    }
                    
                    // Update the switch state while preserving ALL existing data
                    const existingData = { ...this.devices[deviceIndex].live_data.decoded_data };
                    
                    // Create a new decoded_data object with preserved data and updated switch state
                    this.devices[deviceIndex].live_data.decoded_data = {
                        ...existingData,
                        [switchType]: action === 'on' ? 1 : 0
                    };
                    
                    console.log('🔄 Updated device data:', this.devices[deviceIndex].live_data.decoded_data);
                    
                    // Re-render the device card to show updated state with preserved power data
                    this.updateSingleDeviceCard(this.devices[deviceIndex]);
                }
                
                // Update the label text as backup
                const labelText = container.parentElement.querySelector('.text-xs.font-medium.mt-2');
                if (labelText) {
                    const isOn = action === 'on';
                    labelText.textContent = isOn ? 'ON' : 'OFF';
                    labelText.className = `text-xs font-medium mt-2 ${isOn ? 'text-green-600' : 'text-red-600'}`;
                }
                
            } else {
                const error = await response.json();
                // Revert checkbox state on error
                checkbox.checked = !checkbox.checked;
                throw new Error(error.detail || 'Failed to send command');
            }
        } catch (error) {
            console.error('Switch control error:', error);
            this.showToast(`Error: ${error.message}`, 'error');
            
            // Revert checkbox state on error
            checkbox.checked = !checkbox.checked;
        } finally {
            // Remove processing indicator immediately
            const processingIndicator = document.getElementById(`processing-${devEui}-${switchType}`);
            if (processingIndicator) {
                processingIndicator.remove();
            }
            
            // Track this switch as disabled for optimistic updates
            const switchKey = `${devEui}-${switchType}`;
            this.disabledSwitches.add(switchKey);
            
            // Re-enable switch after 5 seconds with countdown
            let countdown = 5;
            const countdownElement = document.createElement('div');
            countdownElement.className = 'absolute top-0 right-0 bg-red-500 text-white text-xs px-2 py-1 rounded-bl-lg font-bold';
            countdownElement.textContent = countdown;
            countdownElement.id = `countdown-${devEui}-${switchType}`;
            container.appendChild(countdownElement);
            
            const countdownInterval = setInterval(() => {
                countdown--;
                if (countdownElement) {
                    countdownElement.textContent = countdown;
                }
                if (countdown <= 0) {
                    clearInterval(countdownInterval);
                    if (countdownElement) {
                        countdownElement.remove();
                    }
                }
            }, 1000);
            
            // Store timeout ID for potential early clearing
            const timeoutId = setTimeout(() => {
                this.clearSwitchTimeout(devEui, switchType);
            }, 5000);
            
            // Store timeout ID for early clearing if device confirms the state
            container.setAttribute('data-timeout-id', timeoutId);
        }
    }

    clearSwitchTimeout(devEui, switchType) {
        const checkbox = document.getElementById(`switch-${devEui}-${switchType === 'switch_1' ? '1' : '2'}`);
        const container = document.getElementById(`switch-${devEui}-${switchType === 'switch_1' ? '1' : '2'}-container`);
        const switchKey = `${devEui}-${switchType}`;
        
        if (container) {
            // Clear the stored timeout if it exists
            const timeoutId = container.getAttribute('data-timeout-id');
            if (timeoutId) {
                clearTimeout(parseInt(timeoutId));
                container.removeAttribute('data-timeout-id');
            }
            
            // Re-enable the switch
            if (checkbox) {
                checkbox.disabled = false;
            }
            container.style.pointerEvents = 'auto';
            container.style.opacity = '1';
            container.style.filter = 'none';
            
            // Remove countdown if it exists
            const countdownElement = document.getElementById(`countdown-${devEui}-${switchType}`);
            if (countdownElement) {
                countdownElement.remove();
            }
        }
        
        // Remove from disabled switches tracking
        this.disabledSwitches.delete(switchKey);
    }

    // Keep the old method for compatibility
    async controlSwitch(devEui, action, switchType = null) {
        return this.toggleSwitch(devEui, action, switchType);
    }

    // Real-time updates are now handled by WebSocket, no need for polling

    async refreshData() {
        const refreshBtn = document.getElementById('refresh-btn');
        const refreshIcon = refreshBtn.querySelector('box-icon');
        
        try {
            // Add loading state
            refreshBtn.disabled = true;
            refreshIcon.style.animation = 'spin 1s linear infinite';
            
            // Load fresh data without showing loading state for entire grid
            const [devicesResponse, statsResponse] = await Promise.all([
                authManager.makeAuthenticatedRequest('/api/devices'),
                authManager.makeAuthenticatedRequest('/api/stats')
            ]);

            if (devicesResponse.ok && statsResponse.ok) {
                const devicesData = await devicesResponse.json();
                const statsData = await statsResponse.json();
                
                this.devices = devicesData.devices;
                this.stats = statsData;
                
                this.updateDevicesGrid();
                this.updateStatsCards();
                
                this.showToast('Dashboard refreshed successfully', 'success');
            } else {
                throw new Error('Failed to refresh dashboard data');
            }
        } catch (error) {
            console.error('Refresh error:', error);
            this.showToast('Failed to refresh dashboard', 'error');
        } finally {
            // Remove loading state
            refreshBtn.disabled = false;
            refreshIcon.style.animation = '';
        }
    }

    setupEventListeners() {
        // Manual refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.refreshData();
            });
        }

        // Auto-refresh toggle (now controls WebSocket connection)
        const autoRefreshToggle = document.getElementById('auto-refresh-toggle');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    if (!this.ws || this.ws.readyState === WebSocket.CLOSED) {
                        this.setupWebSocket();
                    }
                } else {
                    if (this.ws) {
                        this.ws.close();
                        this.updateMqttStatus('disconnected');
                    }
                }
            });
        }
    }

    setupGroupingControls() {
        const groupingSelect = document.getElementById('grouping-select');
        if (groupingSelect) {
            groupingSelect.addEventListener('change', () => {
                console.log(`🔄 Changing grouping to: ${groupingSelect.value}`);
                this.updateDevicesGrid();
            });
        }
    }

    getStatusClass(status) {
        switch (status) {
            case 'online': return 'border-green-500';
            case 'recent': return 'border-yellow-500';
            case 'offline': return 'border-red-500';
            default: return 'border-gray-300';
        }
    }

    getStatusIcon(status) {
        switch (status) {
            case 'online': 
                return '<div class="status-dot status-online"></div>';
            case 'recent': 
                return '<div class="status-dot status-recent"></div>';
            case 'offline': 
                return '<div class="status-dot status-offline"></div>';
            default: 
                return '<div class="status-dot status-offline"></div>';
        }
    }

    getRelativeTime(timestamp) {
        if (!timestamp || timestamp === 'Never') return 'never';
        
        try {
            // Parse the timestamp - should handle UTC format properly
            const date = new Date(timestamp);
            
            // Validate the parsed date
            if (isNaN(date.getTime())) {
                console.warn('Invalid timestamp:', timestamp);
                return 'unknown';
            }
            
            const now = new Date();
            const diffMinutes = Math.floor((now - date) / (1000 * 60));
            
            // Debug logging to help troubleshoot timezone issues
            console.log('🕒 Time calculation:', {
                original: timestamp,
                parsedUTC: date.toISOString(),
                parsedLocal: date.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }),
                nowLocal: now.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' }),
                diffMinutes,
                browserTimezone: Intl.DateTimeFormat().resolvedOptions().timeZone
            });
            
            if (diffMinutes < 1) return 'just now';
            if (diffMinutes < 60) return `${diffMinutes}m ago`;
            
            const diffHours = Math.floor(diffMinutes / 60);
            if (diffHours < 24) return `${diffHours}h ago`;
            
            const diffDays = Math.floor(diffHours / 24);
            if (diffDays < 7) return `${diffDays}d ago`;
            
            return date.toLocaleDateString();
        } catch (error) {
            console.error('Error parsing timestamp:', timestamp, error);
            return 'unknown';
        }
    }

    formatLastSeen(lastSeen) {
        if (lastSeen === 'Never' || !lastSeen) return 'Never';
        
        try {
            const date = new Date(lastSeen);
            const now = new Date();
            const diffMinutes = Math.floor((now - date) / (1000 * 60));
            
            if (diffMinutes < 1) return 'Just now';
            if (diffMinutes < 60) return `${diffMinutes}m ago`;
            
            const diffHours = Math.floor(diffMinutes / 60);
            if (diffHours < 24) return `${diffHours}h ago`;
            
            return date.toLocaleDateString();
        } catch {
            return lastSeen;
        }
    }

    showLoadingState() {
        this.isUpdating = true;
        const grid = document.getElementById('devices-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="col-span-full flex items-center justify-center py-12">
                    <div class="loading-spinner"></div>
                    <span class="ml-3 text-gray-600">Loading devices...</span>
                </div>
            `;
        }
    }

    hideLoadingState() {
        this.isUpdating = false;
    }

    showToast(message, type = 'info', subtitle = '') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        // Create toast element with beautiful design
        const toast = document.createElement('div');
        toast.className = 'toast-card';
        
        toast.innerHTML = `
            <svg class="toast-wave ${type}" viewBox="0 0 1440 320" xmlns="http://www.w3.org/2000/svg">
                <path d="M0,256L11.4,240C22.9,224,46,192,69,192C91.4,192,114,224,137,234.7C160,245,183,235,206,213.3C228.6,192,251,160,274,149.3C297.1,139,320,149,343,181.3C365.7,213,389,267,411,282.7C434.3,299,457,277,480,250.7C502.9,224,526,192,549,181.3C571.4,171,594,181,617,208C640,235,663,277,686,256C708.6,235,731,149,754,122.7C777.1,96,800,128,823,165.3C845.7,203,869,245,891,224C914.3,203,937,117,960,112C982.9,107,1006,181,1029,197.3C1051.4,213,1074,171,1097,144C1120,117,1143,107,1166,133.3C1188.6,160,1211,224,1234,218.7C1257.1,213,1280,139,1303,133.3C1325.7,128,1349,192,1371,192C1394.3,192,1417,128,1429,96L1440,64L1440,320L1428.6,320C1417.1,320,1394,320,1371,320C1348.6,320,1326,320,1303,320C1280,320,1257,320,1234,320C1211.4,320,1189,320,1166,320C1142.9,320,1120,320,1097,320C1074.3,320,1051,320,1029,320C1005.7,320,983,320,960,320C937.1,320,914,320,891,320C868.6,320,846,320,823,320C800,320,777,320,754,320C731.4,320,709,320,686,320C662.9,320,640,320,617,320C594.3,320,571,320,549,320C525.7,320,503,320,480,320C457.1,320,434,320,411,320C388.6,320,366,320,343,320C320,320,297,320,274,320C251.4,320,229,320,206,320C182.9,320,160,320,137,320C114.3,320,91,320,69,320C45.7,320,23,320,11,320L0,320Z" fill-opacity="1"></path>
            </svg>
            
            <div class="toast-icon-container ${type}">
                <box-icon name="${this.getToastIcon(type)}" class="toast-icon ${type}"></box-icon>
            </div>
            
            <div class="toast-message-text-container">
                <p class="toast-message-text ${type}">${this.getToastTitle(type)}</p>
                <p class="toast-sub-text">${subtitle || message}</p>
            </div>
            
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 15 15" class="toast-cross-icon" onclick="this.parentElement.remove()">
                <path fill="currentColor" d="M11.7816 4.03157C12.0062 3.80702 12.0062 3.44295 11.7816 3.2184C11.5571 2.99385 11.193 2.99385 10.9685 3.2184L7.50005 6.68682L4.03164 3.2184C3.80708 2.99385 3.44301 2.99385 3.21846 3.2184C2.99391 3.44295 2.99391 3.80702 3.21846 4.03157L6.68688 7.49999L3.21846 10.9684C2.99391 11.193 2.99391 11.557 3.21846 11.7816C3.44301 12.0061 3.80708 12.0061 4.03164 11.7816L7.50005 8.31316L10.9685 11.7816C11.193 12.0061 11.5571 12.0061 11.7816 11.7816C12.0062 11.557 12.0062 11.193 11.7816 10.9684L8.31322 7.49999L11.7816 4.03157Z" clip-rule="evenodd" fill-rule="evenodd"></path>
            </svg>
        `;
        
        container.appendChild(toast);
        
        // Auto remove after 4 seconds
        setTimeout(() => {
            toast.classList.add('toast-fadeout');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 4000);
    }

    getToastIcon(type) {
        switch (type) {
            case 'success': return 'check-circle';
            case 'error': return 'x-circle';
            case 'warning': return 'error';
            default: return 'info-circle';
        }
    }

    getToastTitle(type) {
        switch (type) {
            case 'success': return 'Success';
            case 'error': return 'Error';
            case 'warning': return 'Warning';
            default: return 'Info';
        }
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    initAnimatedWeather() {
        // Wait for DOM to be ready and libraries to load
        setTimeout(() => {
            this.setupAnimatedWeather();
        }, 500);
    }

    setupAnimatedWeather() {
        try {
            // Initialize animated weather widget
            this.weatherWidget = new AnimatedWeatherWidget();
            console.log('🌤️ Animated weather widget initialized');
        } catch (error) {
            console.error('Failed to initialize animated weather:', error);
        }
    }

    async loadWeatherData() {
        try {
            // Use wttr.in API for weather data (no API key needed)
            const response = await fetch('https://wttr.in/Bangalore?format=j1');
            
            if (response.ok) {
                const data = await response.json();
                this.updateWeatherDisplay(data);
            } else {
                throw new Error('Weather API failed');
            }
        } catch (error) {
            console.error('Weather loading error:', error);
            this.showWeatherError();
        }
    }

    updateWeatherDisplay(data) {
        try {
            const current = data.current_condition[0];
            const today = data.weather[0];
            
            // Update main weather data
            document.getElementById('weather-temp-value').textContent = current.temp_C;
            document.getElementById('weather-feels-value').textContent = current.FeelsLikeC;
            document.getElementById('weather-summary').textContent = current.weatherDesc[0].value;
            
            // Update detailed metrics
            document.getElementById('weather-humidity').textContent = `${current.humidity}%`;
            document.getElementById('weather-pressure').textContent = `${current.pressure} hPa`;
            document.getElementById('weather-uv').textContent = current.uvIndex || '--';
            
            // Calculate precipitation (use today's data for more accuracy)
            let precipitation = '0 mm';
            if (today && today.hourly && today.hourly.length > 0) {
                // Get current hour or closest
                const currentHour = new Date().getHours();
                const hourlyData = today.hourly.find(h => parseInt(h.time) / 100 >= currentHour) || today.hourly[0];
                
                if (hourlyData.precipMM && parseFloat(hourlyData.precipMM) > 0) {
                    precipitation = `${hourlyData.precipMM} mm`;
                }
            }
            document.getElementById('weather-precipitation').textContent = precipitation;
            
            // Determine weather type for animation
            const condition = current.weatherDesc[0].value.toLowerCase();
            let weatherType = 'sun'; // default
            
            if (condition.includes('rain') || condition.includes('shower') || condition.includes('drizzle')) {
                weatherType = 'rain';
            } else if (condition.includes('thunder') || condition.includes('storm')) {
                weatherType = 'thunder';
            } else if (condition.includes('snow')) {
                weatherType = 'snow';
            } else if (condition.includes('wind')) {
                weatherType = 'wind';
            } else if (condition.includes('cloud') || condition.includes('overcast')) {
                weatherType = 'rain'; // cloudy weather shows as light rain
            }
            
            // Update animated weather if widget is initialized
            if (this.weatherWidget) {
                this.weatherWidget.changeWeather(weatherType);
            }
            
            console.log('🌤️ Weather data loaded successfully:', weatherType, {
                temp: current.temp_C,
                feelsLike: current.FeelsLikeC,
                humidity: current.humidity,
                pressure: current.pressure,
                uv: current.uvIndex,
                precip: precipitation
            });
        } catch (error) {
            console.error('Weather display error:', error);
            this.showWeatherError();
        }
    }

    showWeatherError() {
        // Show error state
        document.getElementById('weather-temp-value').textContent = '--';
        document.getElementById('weather-feels-value').textContent = '--';
        document.getElementById('weather-summary').textContent = 'Unable to load weather';
        document.getElementById('weather-humidity').textContent = '--';
        document.getElementById('weather-pressure').textContent = '--';
        document.getElementById('weather-uv').textContent = '--';
        document.getElementById('weather-precipitation').textContent = '--';
    }
}

// Animated Weather Widget Class
class AnimatedWeatherWidget {
    constructor() {
        this.currentWeather = { type: 'sun', name: 'Sunny' };
        this.settings = {
            windSpeed: 2,
            rainCount: 0,
            leafCount: 0,
            snowCount: 0,
            cloudHeight: 50,
            cloudSpace: 15,
            cloudArch: 25,
            renewCheck: 10,
            splashBounce: 40
        };
        
        this.tickCount = 0;
        this.rain = [];
        this.leafs = [];
        this.snow = [];
        this.lightningTimeout = null;
        
        this.sizes = {
            container: { width: 0, height: 0 },
            card: { width: 0, height: 0 }
        };
        
        this.init();
    }
    
    init() {
        // Get DOM elements
        this.container = document.querySelector('.weather-inner');
        this.card = document.getElementById('weather-card');
        
        if (!this.container || !this.card) {
            console.error('Weather widget elements not found');
            return;
        }
        
        // Initialize Snap SVG elements
        this.innerSVG = Snap('#weather-inner');
        this.outerSVG = Snap('#weather-outer');
        this.backSVG = Snap('#weather-back');
        
        if (!this.innerSVG || !this.outerSVG || !this.backSVG) {
            console.error('Weather SVG elements not found');
            return;
        }
        
        this.sun = Snap.select('#weather-sun');
        this.sunburst = Snap.select('#weather-sunburst');
        
        // Get cloud groups
        this.clouds = [
            { group: Snap.select('#weather-cloud1') },
            { group: Snap.select('#weather-cloud2') },
            { group: Snap.select('#weather-cloud3') }
        ];
        
        // Initialize weather containers
        this.weatherContainer1 = Snap.select('#weather-layer1');
        this.weatherContainer2 = Snap.select('#weather-layer2');
        this.weatherContainer3 = Snap.select('#weather-layer3');
        
        this.innerRainHolder1 = this.weatherContainer1.group();
        this.innerRainHolder2 = this.weatherContainer2.group();
        this.innerRainHolder3 = this.weatherContainer3.group();
        this.innerSnowHolder = this.weatherContainer1.group();
        this.outerSplashHolder = this.outerSVG.group();
        this.outerSnowHolder = this.outerSVG.group();
        
        this.onResize();
        this.initClouds();
        this.startAnimation();
        
        // Set initial sunny weather
        this.changeWeather('sun');
    }
    
    onResize() {
        this.sizes.container.width = 320; // stats card width (restored for weather widget)
        this.sizes.container.height = 240; // weather widget height
        this.sizes.card.width = 320;
        this.sizes.card.height = 240;
        this.sizes.card.offset = { top: 0, left: 0 };
        
        // Update SVG sizes
        this.innerSVG.attr({
            width: this.sizes.card.width,
            height: this.sizes.card.height
        });
        
        this.outerSVG.attr({
            width: this.sizes.container.width,
            height: this.sizes.container.height
        });
        
        this.backSVG.attr({
            width: this.sizes.container.width,
            height: this.sizes.container.height
        });
        
        // Position sunburst
        if (this.sunburst) {
            gsap.set(this.sunburst.node, {
                transformOrigin: "50% 50%",
                x: this.sizes.container.width / 2,
                y: this.sizes.card.height / 2
            });
            gsap.fromTo(this.sunburst.node, { rotation: 0 }, {
                rotation: 360,
                duration: 20,
                repeat: -1,
                ease: "none"
            });
        }
    }
    
    initClouds() {
        for (let i = 0; i < this.clouds.length; i++) {
            this.clouds[i].offset = Math.random() * this.sizes.card.width;
            this.drawCloud(this.clouds[i], i);
        }
    }
    
    drawCloud(cloud, i) {
        const space = this.settings.cloudSpace * i;
        const height = space + this.settings.cloudHeight;
        const arch = height + this.settings.cloudArch + (Math.random() * this.settings.cloudArch);
        const width = this.sizes.card.width;
        
        const points = [
            `M${-width},0`,
            `${width},0`,
            `Q${width * 2},${height / 2}`,
            `${width},${height}`,
            `Q${width * 0.5},${arch}`,
            `0,${height}`,
            `Q${width * -0.5},${arch}`,
            `${-width},${height}`,
            `Q${-(width * 2)},${height / 2}`,
            `${-width},0`
        ];
        
        const path = points.join(' ');
        if (!cloud.path) cloud.path = cloud.group.path();
        cloud.path.animate({ d: path }, 0);
    }
    
    startAnimation() {
        this.tick();
    }
    
    tick() {
        this.tickCount++;
        const check = this.tickCount % this.settings.renewCheck;
        
        if (check) {
            if (this.rain.length < this.settings.rainCount) this.makeRain();
            if (this.snow.length < this.settings.snowCount) this.makeSnow();
        }
        
        // Animate clouds
        for (let i = 0; i < this.clouds.length; i++) {
            this.clouds[i].offset += this.settings.windSpeed / (i + 1);
            if (this.clouds[i].offset > this.sizes.card.width) {
                this.clouds[i].offset = 0 + (this.clouds[i].offset - this.sizes.card.width);
            }
            this.clouds[i].group.transform('t' + this.clouds[i].offset + ',' + 0);
        }
        
        requestAnimationFrame(() => this.tick());
    }
    
    makeRain() {
        const lineWidth = Math.random() * 3;
        const lineLength = this.currentWeather.type === 'thunder' ? 18 : 7;
        const x = Math.random() * (this.sizes.card.width - 20) + 10;
        
        const line = this['innerRainHolder' + (3 - Math.floor(lineWidth))].path(`M0,0 0,${lineLength}`).attr({
            fill: 'none',
            stroke: this.currentWeather.type === 'thunder' ? '#777' : '#0099ff',
            strokeWidth: lineWidth
        });
        
        this.rain.push(line);
        
        gsap.fromTo(line.node, {
            x: x,
            y: -lineLength
        }, {
            y: this.sizes.card.height,
            duration: 1,
            delay: Math.random(),
            ease: "power2.in",
            onComplete: () => this.onRainEnd(line, lineWidth, x)
        });
    }
    
    onRainEnd(line, width, x) {
        line.remove();
        this.rain = this.rain.filter(r => r.paper);
        
        if (this.rain.length < this.settings.rainCount) {
            this.makeRain();
        }
    }
    
    makeSnow() {
        const scale = 0.5 + (Math.random() * 0.5);
        const x = 10 + (Math.random() * (this.sizes.card.width - 20));
        const y = -5;
        const endY = this.sizes.card.height + 5;
        
        const newSnow = this.innerSnowHolder.circle(0, 0, 3).attr({
            fill: 'white'
        });
        
        this.snow.push(newSnow);
        
        gsap.fromTo(newSnow.node, {
            x: x,
            y: y,
            scale: 0
        }, {
            y: endY,
            scale: scale,
            duration: 3 + (Math.random() * 2),
            ease: "power0.inOut",
            onComplete: () => this.onSnowEnd(newSnow)
        });
        
        gsap.to(newSnow.node, {
            x: x + ((Math.random() * 75) - 37.5),
            duration: 1.5,
            repeat: -1,
            yoyo: true,
            ease: "power1.inOut"
        });
    }
    
    onSnowEnd(flake) {
        flake.remove();
        this.snow = this.snow.filter(s => s.paper);
        
        if (this.snow.length < this.settings.snowCount) {
            this.makeSnow();
        }
    }
    
    changeWeather(weatherType) {
        const weatherTypes = {
            'snow': { type: 'snow', name: 'Snow' },
            'wind': { type: 'wind', name: 'Windy' },
            'rain': { type: 'rain', name: 'Rain' },
            'thunder': { type: 'thunder', name: 'Storms' },
            'sun': { type: 'sun', name: 'Sunny' }
        };
        
        const weather = weatherTypes[weatherType] || weatherTypes['sun'];
        this.currentWeather = weather;
        
        // Reset classes
        this.container.className = 'weather-inner';
        this.container.classList.add(weather.type);
        
        // Animate settings based on weather type
        switch (weather.type) {
            case 'wind':
                gsap.to(this.settings, { windSpeed: 1.5, duration: 3 });
                break;
            case 'sun':
                gsap.to(this.settings, { windSpeed: 10, duration: 3 });
                break;
            default:
                gsap.to(this.settings, { windSpeed: 0.25, duration: 3 });
                break;
        }
        
        // Rain count
        switch (weather.type) {
            case 'rain':
                gsap.to(this.settings, { rainCount: 5, duration: 3 });
                break;
            case 'thunder':
                gsap.to(this.settings, { rainCount: 15, duration: 3 });
                break;
            default:
                gsap.to(this.settings, { rainCount: 0, duration: 1 });
                break;
        }
        
        // Snow count
        switch (weather.type) {
            case 'snow':
                gsap.to(this.settings, { snowCount: 10, duration: 3 });
                break;
            default:
                gsap.to(this.settings, { snowCount: 0, duration: 1 });
                break;
        }
        
        // Sun position
        if (this.sun) {
            switch (weather.type) {
                case 'sun':
                    gsap.to(this.sun.node, {
                        x: this.sizes.card.width / 2,
                        y: this.sizes.card.height / 2,
                        duration: 4
                    });
                    if (this.sunburst) {
                        gsap.to(this.sunburst.node, {
                            scale: 0.6,
                            opacity: 0.8,
                            duration: 4
                        });
                    }
                    break;
                default:
                    gsap.to(this.sun.node, {
                        x: this.sizes.card.width / 2,
                        y: -50,
                        duration: 2
                    });
                    if (this.sunburst) {
                        gsap.to(this.sunburst.node, {
                            scale: 0.2,
                            opacity: 0,
                            duration: 2
                        });
                    }
                    break;
            }
        }
        
        console.log('🌤️ Weather changed to:', weather.type);
    }
}

// Initialize dashboard when DOM is ready
let dashboard;

document.addEventListener('DOMContentLoaded', () => {
    if (window.location.pathname === '/') {
        dashboard = new IoTDashboard();
    }
});

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

