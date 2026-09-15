# Mine Detection Rover System

This repository contains the code and architecture for a mine detection rover system designed for underground mining safety. The system uses AI-powered human detection combined with sensor networks to detect miners and environmental hazards.

## System Architecture

```
+---------------------------------------------------------------------------------+
|                                 1. THE ROVER BRAIN                              |
|   [Raspberry Pi 4] <----(USB)---- [2x Independent Camera Modules]               |
|          |                                                                      |
|     (USB-Serial / UART)                                                         |
|          v                                                                      |
|  +---------------------------------------------------------------------------+  |
|  |                        2. THE ROVER ACTUATOR & SENSOR HUB                |  |
|  |   [ESP32 Rover Core] <---(Analog/Digital)--- [DHT11 + MQ Gas Sensors]       |  |
|  |          |                                                                |  |
|  |     (GPIO Pins)                                                           |  |
|  |          v                                                                |  |
|  |   [2x Ultrasonic Sensors] + [2x IR Sensors]                               |  |
|  |          |                                                                |  |
|  |     (PWM / Motor Pins)                                                    |  |
|  |          v                                                                |  |
|  |   [Rover Chassis + Motor Drivers]                                         |  |
|  +---------------------------------------------------------------------------+  |
|          |                                                                      |
|     (Internal ESP-NOW Protocol Layer)                                           |
|          v                                                                      |
|  +---------------------------------------------------------------------------+  |
|  |                     3. DEPLOYED COMMUNICATIONS BACKBONE                   |  |
|  |   [ESP32 Rover Core (Acts as Node 1)]                                     |  |
|  +---------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------+
                                      ||
                             (ESP-NOW Protocol)
                                      ||
                                      v
+---------------------------------------------------------------------------------+
|                       4. DEPLOYED COMMUNICATIONS BACKBONE                       |
|   [ESP32 Relay Node 2] ----> [ESP32 Relay Node 3] ----> [ESP32 Base Station]    |
|                                                                       |         |
|                                                                 (Serial)        |
|                                                                       v         |
|                                                            [ESP32-CAM Endpoint] |
+---------------------------------------------------------------------------------+
```

## Key Components

### 1. Rover Brain (Raspberry Pi 4)
- **File**: `brain_engine.py`
- **Function**: AI-powered human detection using YOLOv8
- **Features**:
  - Real-time video processing from dual cameras
  - Low-light enhancement using CLAHE
  - Human detection with confidence threshold of 0.40
  - Serial communication with ESP32 actuator hub
  - Receives telemetry data from ESP32

### 2. Rover Actuator & Sensor Hub (ESP32)
- **File**: `rover_core_esp32.ino`
- **Function**: Sensor data collection, motor control, and mesh networking
- **Sensors**:
  - DHT11: Temperature & Humidity
  - MQ Gas Sensor: Gas leak detection
  - Dual Ultrasonic Sensors: Obstacle detection
  - Dual IR Sensors: Edge/barrier detection
- **Actuators**: Motor drivers for rover movement
- **Communications**:
  - Serial to Pi Brain (receives 'H'/'N' commands)
  - ESP-NOW Mesh Network (broadcasts sensor data)

### 3. Communications Backbone
- ESP-NOW mesh network for robust wireless communication
- Multi-hop relay system: Rover → Relay Node 2 → Relay Node 3 → Base Station
- Base station connects to ESP32-CAM for visual monitoring

## System Operation

1. **Human Detection Mode**:
   - Pi 4 processes camera feed using YOLOv8
   - When human detected: Sends 'H' via serial to ESP32
   - ESP32 stops rover immediately and sets `globalAlarmState = true`
   - ESP-NOW broadcasts "EMERGENCY" status with sensor data

2. **Normal Operation Mode**:
   - When no human detected: Sends 'N' via serial to ESP32
   - ESP32 allows normal movement with obstacle avoidance
   - ESP-NOW broadcasts "NOMINAL" status with sensor data

3. **Sensor Data Flow**:
   - ESP32 continuously reads all sensors
   - Sends CSV telemetry via serial to Pi 4: `temp,humidity,gas,distLeft,distRight`
   - Packages sensor data + human alert status into ESP-NOW packets
   - Mesh network relays data hop-by-hop to base station

## Installation & Usage

### Prerequisites
- Raspberry Pi 4 with Python 3.x
- ESP32 development boards
- Required Python packages: `opencv-python`, `ultralytics`, `pyserial`
- Arduino IDE with ESP32 board support
- Required libraries: `ESPNow`, `WiFi`, `DHT sensor library`

### Setup Instructions

#### For Raspberry Pi 4 (brain_engine.py):
1. Install dependencies:
   ```bash
   pip install opencv-python ultralytics pyserial
   ```
2. Place YOLOv8 model files in the same directory:
   - `yolov8n.pt` (will be auto-converted to NCNN format)
   - Or place pre-converted `yolov8n_ncnn_model` directory
3. Adjust serial port if needed (typically `/dev/ttyUSB0` or `/dev/ttyAMA0`)
4. Run the script:
   ```bash
   python brain_engine.py
   ```

#### For ESP32 (rover_core_esp32.ino):
1. Install required libraries via Arduino Library Manager:
   - ESP32 Board Support
   - ESPNow
   - DHT sensor library
2. Adjust pin definitions according to your hardware wiring
3. Set the `nextRelayAddress` to your specific network configuration
   - For broadcasting: `{0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}`
   - For directed communication: MAC address of next node
4. Upload to your ESP32 Rover Core

## Architecture Advantages

1. **Dual-tasking ESP32**: The Rover ESP32 handles both:
   - Real-time sensor/actuator control
   - ESP-NOW mesh network communication
   (Eliminates need for separate communication module)

2. **Robust Communication**: ESP-NOW provides:
   - Low-latency, peer-to-peer wireless communication
   - No Wi-Fi dependency (works in underground environments)
   - Automatic mesh routing through relay nodes

3. **Safety Features**:
   - Immediate rover stop upon human detection
   - Multi-layer obstacle avoidance (ultrasonic + IR sensors)
   - Environmental hazard monitoring (gas, temperature, humidity)
   - Redundant communication paths

## Customization Points

### Detection Sensitivity
- Adjust confidence threshold in `brain_engine.py` line 81: `conf=0.40`
- Modify detection class ID (currently 0 for "person" in COCO dataset)

### Sensor Thresholds
- Obstacle detection distance in `rover_core_esp32.ino` line 214: `distL < 20 || distR < 20`
- IR sensor logic (active HIGH/LOW depending on your sensors)

### Communication Range
- ESP-NOW typically works up to 200m line-of-sight
- Adjust transmit power if needed using ESP-NOW API
- Modify relay node addresses for your specific network topology

## Safety Notes
- Always test in controlled environments before deployment
- Ensure proper ventilation when testing gas sensors
- Implement emergency stop mechanisms in hardware
- Regularly calibrate sensors for accurate readings

## Future Enhancements
- Add GPS for miner location tracking
- Implement battery monitoring and low-power modes
- Add ground penetration radar for void detection
- Integrate with mine management systems for real-time alerts
- Add thermal imaging for enhanced detection in smoke/dust