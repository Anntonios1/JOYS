// Gamepad Monitor Frontend Application

const API_URL = 'http://localhost:8000';
let ws = null;
let devices = {};
let charts = {};

// WebSocket Connection
function connectWebSocket() {
    ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
        setTimeout(connectWebSocket, 3000); // Reconnect after 3 seconds
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };
}

function updateConnectionStatus(connected) {
    const indicator = document.getElementById('wsIndicator');
    const status = document.getElementById('wsStatus');
    
    if (connected) {
        indicator.className = 'w-3 h-3 rounded-full bg-green-500 animate-pulse';
        status.textContent = 'Connected to server';
    } else {
        indicator.className = 'w-3 h-3 rounded-full bg-red-500';
        status.textContent = 'Disconnected from server';
    }
}

function handleWebSocketMessage(data) {
    console.log('WebSocket message:', data);
    
    switch (data.type) {
        case 'scan_complete':
            loadDevices();
            break;
        case 'device_connected':
            updateDeviceCard(data.mac_address, { connected: true });
            break;
        case 'device_disconnected':
            updateDeviceCard(data.mac_address, { connected: false });
            break;
        case 'battery_update':
            updateBatteryDisplay(data.mac_address, data.battery);
            break;
        case 'latency_update':
            updateLatencyDisplay(data.mac_address, data.latency);
            break;
    }
}

// API Calls
async function apiCall(endpoint, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    
    if (body) {
        options.body = JSON.stringify(body);
    }
    
    try {
        const response = await fetch(`${API_URL}${endpoint}`, options);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

async function loadDevices() {
    try {
        const deviceList = await apiCall('/devices');
        devices = {};
        deviceList.forEach(device => {
            devices[device.mac_address] = device;
        });
        renderDevices();
    } catch (error) {
        console.error('Failed to load devices:', error);
    }
}

async function scanDevices() {
    const scanBtn = document.getElementById('scanBtn');
    const indicator = document.getElementById('scanningIndicator');
    
    scanBtn.disabled = true;
    indicator.classList.remove('hidden');
    
    try {
        await apiCall('/scan', 'POST');
        await loadDevices();
    } catch (error) {
        alert('Scan failed: ' + error.message);
    } finally {
        scanBtn.disabled = false;
        indicator.classList.add('hidden');
    }
}

async function connectDevice(macAddress) {
    try {
        await apiCall('/connect', 'POST', { mac_address: macAddress });
        await loadDevices();
        startMonitoring(macAddress);
    } catch (error) {
        alert('Failed to connect: ' + error.message);
    }
}

async function disconnectDevice(macAddress) {
    try {
        await apiCall('/disconnect', 'POST', { mac_address: macAddress });
        await loadDevices();
        stopMonitoring(macAddress);
    } catch (error) {
        alert('Failed to disconnect: ' + error.message);
    }
}

async function resetBluetooth() {
    if (confirm('Reset Bluetooth service? This may disconnect all devices.')) {
        try {
            await apiCall('/reset_bluetooth', 'POST');
            alert('Bluetooth service reset successfully');
            await loadDevices();
        } catch (error) {
            alert('Failed to reset Bluetooth: ' + error.message);
        }
    }
}

async function getBattery(macAddress) {
    try {
        const battery = await apiCall(`/battery/${macAddress}`);
        updateBatteryDisplay(macAddress, battery);
    } catch (error) {
        console.error('Failed to get battery:', error);
    }
}

async function getLatency(macAddress) {
    try {
        const latency = await apiCall(`/latency/${macAddress}`);
        updateLatencyDisplay(macAddress, latency);
    } catch (error) {
        console.error('Failed to get latency:', error);
    }
}

async function getSignal(macAddress) {
    try {
        const signal = await apiCall(`/signal/${macAddress}`);
        updateSignalDisplay(macAddress, signal);
    } catch (error) {
        console.error('Failed to get signal:', error);
    }
}

// UI Rendering
function renderDevices() {
    const grid = document.getElementById('devicesGrid');
    grid.innerHTML = '';
    
    Object.values(devices).forEach(device => {
        const card = createDeviceCard(device);
        grid.appendChild(card);
    });
}

function createDeviceCard(device) {
    const card = document.createElement('div');
    card.id = `device-${device.mac_address}`;
    card.className = 'bg-gray-800 rounded-lg p-6 shadow-lg border-2 ' + 
        (device.connected ? 'border-green-500' : 'border-gray-700');
    
    const typeEmoji = getControllerEmoji(device.controller_type);
    const statusColor = device.connected ? 'text-green-500' : 'text-gray-500';
    
    card.innerHTML = `
        <div class="flex justify-between items-start mb-4">
            <div>
                <h3 class="text-2xl font-bold mb-1">${typeEmoji} ${device.name}</h3>
                <p class="text-sm text-gray-400">${device.mac_address}</p>
                <p class="text-sm ${statusColor} font-semibold mt-1">
                    ${device.connected ? '● Connected' : '○ Disconnected'}
                </p>
            </div>
            <div class="flex flex-col gap-2">
                ${device.connected ? 
                    `<button onclick="disconnectDevice('${device.mac_address}')" 
                        class="bg-red-600 hover:bg-red-700 px-4 py-2 rounded text-sm font-semibold transition">
                        Disconnect
                    </button>` :
                    `<button onclick="connectDevice('${device.mac_address}')" 
                        class="bg-green-600 hover:bg-green-700 px-4 py-2 rounded text-sm font-semibold transition">
                        Connect
                    </button>`
                }
            </div>
        </div>
        
        ${device.connected ? `
            <div class="space-y-4">
                <!-- Battery -->
                <div class="bg-gray-700 rounded-lg p-4">
                    <h4 class="text-sm font-semibold mb-2 text-gray-300">🔋 Battery</h4>
                    <div id="battery-${device.mac_address}" class="text-2xl font-bold">
                        Loading...
                    </div>
                </div>
                
                <!-- Latency -->
                <div class="bg-gray-700 rounded-lg p-4">
                    <h4 class="text-sm font-semibold mb-2 text-gray-300">⚡ Latency</h4>
                    <div id="latency-${device.mac_address}" class="text-2xl font-bold">
                        Loading...
                    </div>
                </div>
                
                <!-- Signal -->
                <div class="bg-gray-700 rounded-lg p-4">
                    <h4 class="text-sm font-semibold mb-2 text-gray-300">📶 Signal</h4>
                    <div id="signal-${device.mac_address}" class="text-xl font-bold">
                        ${device.rssi !== null ? `${device.rssi} dBm` : 'N/A'}
                    </div>
                </div>
                
                <!-- Latency Chart -->
                <div class="bg-gray-700 rounded-lg p-4">
                    <h4 class="text-sm font-semibold mb-2 text-gray-300">📊 Latency History</h4>
                    <canvas id="chart-${device.mac_address}" height="150"></canvas>
                </div>
            </div>
        ` : `
            <div class="text-center text-gray-500 py-8">
                Click Connect to start monitoring
            </div>
        `}
    `;
    
    return card;
}

function getControllerEmoji(type) {
    const emojis = {
        'Joy-Con (L)': '🎮',
        'Joy-Con (R)': '🎮',
        'Pro Controller': '🎮',
        'DualShock 4': '🎮',
        'DualSense': '🎮',
        'Unknown': '❓'
    };
    return emojis[type] || '🎮';
}

function updateDeviceCard(macAddress, updates) {
    if (devices[macAddress]) {
        Object.assign(devices[macAddress], updates);
        renderDevices();
    }
}

function updateBatteryDisplay(macAddress, battery) {
    const element = document.getElementById(`battery-${macAddress}`);
    if (element) {
        const icon = battery.charging ? '⚡' : '🔋';
        element.innerHTML = `
            ${icon} ${battery.percentage}%
            <span class="text-sm text-gray-400">${battery.level}</span>
        `;
    }
}

function updateLatencyDisplay(macAddress, latency) {
    const element = document.getElementById(`latency-${macAddress}`);
    if (element) {
        const color = latency.current_ms < 10 ? 'text-green-500' : 
                     latency.current_ms < 20 ? 'text-yellow-500' : 'text-red-500';
        element.innerHTML = `
            <span class="${color}">${latency.current_ms.toFixed(1)} ms</span>
            <div class="text-sm text-gray-400 mt-1">
                Avg: ${latency.average_ms.toFixed(1)} ms | Jitter: ${latency.jitter_ms.toFixed(1)} ms
            </div>
        `;
        
        updateLatencyChart(macAddress, latency);
    }
}

function updateSignalDisplay(macAddress, signal) {
    const element = document.getElementById(`signal-${macAddress}`);
    if (element) {
        const colorMap = {
            'Excellent': 'text-green-500',
            'Good': 'text-blue-500',
            'Fair': 'text-yellow-500',
            'Poor': 'text-red-500'
        };
        const color = colorMap[signal.quality] || 'text-gray-500';
        element.innerHTML = `
            <span class="${color}">${signal.rssi} dBm</span>
            <div class="text-sm text-gray-400">${signal.quality}</div>
        `;
    }
}

function updateLatencyChart(macAddress, latency) {
    const canvas = document.getElementById(`chart-${macAddress}`);
    if (!canvas) return;
    
    if (!charts[macAddress]) {
        const ctx = canvas.getContext('2d');
        charts[macAddress] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Latency (ms)',
                    data: [],
                    borderColor: 'rgb(59, 130, 246)',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: 'rgba(255, 255, 255, 0.7)' }
                    },
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: 'rgba(255, 255, 255, 0.7)' }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
    
    const chart = charts[macAddress];
    const now = new Date().toLocaleTimeString();
    
    chart.data.labels.push(now);
    chart.data.datasets[0].data.push(latency.current_ms);
    
    if (chart.data.labels.length > 20) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    
    chart.update('none');
}

// Monitoring
const monitoringIntervals = {};

function startMonitoring(macAddress) {
    if (monitoringIntervals[macAddress]) return;
    
    // Initial fetch
    getBattery(macAddress);
    getLatency(macAddress);
    getSignal(macAddress);
    
    // Periodic updates
    monitoringIntervals[macAddress] = setInterval(() => {
        getBattery(macAddress);
        getLatency(macAddress);
        getSignal(macAddress);
    }, 5000); // Update every 5 seconds
}

function stopMonitoring(macAddress) {
    if (monitoringIntervals[macAddress]) {
        clearInterval(monitoringIntervals[macAddress]);
        delete monitoringIntervals[macAddress];
    }
    
    if (charts[macAddress]) {
        charts[macAddress].destroy();
        delete charts[macAddress];
    }
}

// Event Listeners
document.getElementById('scanBtn').addEventListener('click', scanDevices);
document.getElementById('resetBtBtn').addEventListener('click', resetBluetooth);

// Initialize
connectWebSocket();
loadDevices();

// Auto-start monitoring for connected devices
setInterval(() => {
    Object.values(devices).forEach(device => {
        if (device.connected && !monitoringIntervals[device.mac_address]) {
            startMonitoring(device.mac_address);
        }
    });
}, 1000);
