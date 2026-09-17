import cv2
try:
    import serial
except ImportError:
    serial = None
from ultralytics import YOLO
import time
import numpy as np
import json
import threading
from collections import deque, defaultdict
import heapq

class MineBrain:
    def __init__(self, serial_port='/dev/ttyUSB0', baud_rate=115200):
        # Load YOLOv8 Model - Pre-converted to NCNN for optimized Pi 4 CPU frames
        try:
            self.model = YOLO('yolov8n_ncnn_model')
        except:
            print("NCNN model not found. Attempting fallback to standard YOLOv8n...")
            try:
                self.model = YOLO('yolov8n.pt')
            except Exception as e:
                print(f"Could not load YOLO model: {e}")
                self.model = None

        # Serial connection to the Rover ESP32
        try:
            if serial is not None:
                self.ser = serial.Serial(serial_port, baud_rate, timeout=1)
                print(f"Serial connection established on {serial_port}")
            else:
                print("pyserial not installed. Running in standalone vision mode.")
                self.ser = None
        except Exception as e:
            print(f"Serial link failed: {e}. Running in standalone vision mode.")
            self.ser = None

        # Camera Array Initialization
        self.cam_forward = cv2.VideoCapture(0)
        self.cam_forward.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cam_forward.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # Sensor data storage and processing
        self.sensor_data = {
            'temperature': 0.0,
            'humidity': 0.0,
            'gas_level': 0,
            'distance_left': 0,
            'distance_right': 0,
            'timestamp': time.time()
        }

        # Sensor thresholds (Jharkhand mine specific)
        self.SENSOR_THRESHOLDS = {
            'temperature_high': 45.0,  # Celsius - underground heat
            'humidity_high': 85.0,     # Percentage
            'methane_high': 500,       # PPM - explosive threshold
            'co_high': 100,            # PPM - toxic
            'distance_min': 30,        # cm - obstacle threshold
            'gas_spike_rate': 50       # PPM per second - sudden increase
        }

        # Neighbor tracking (mesh network nodes)
        self.neighbors = {}  # {node_id: {'last_seen': time, 'signal_strength': int, 'status': str}}
        self.own_node_id = "ROVER_MAIN"  # This rover's identifier

        # Mapping and navigation
        self.map_grid = defaultdict(lambda: defaultdict(int))  # Simple occupancy grid
        self.current_position = (0, 0)  # (x, y) in meters
        self.heading = 0  # degrees, 0 = forward
        self.known_exits = []  # List of known exit coordinates
        self.target_exit = None

        # Jharkhand-specific hazard detection
        self.jharkhand_hazards = {
            'coal_dust_explosion_risk': False,
            'methane_accumulation': False,
            'co_buildup': False,
            'temperature_anomaly': False,
            'humidity_anomaly': False,
            'structural_weakness': False
        }

        # Threading for serial reading
        self.serial_thread = None
        self.serial_running = False
        self.telemetry_buffer = deque(maxlen=100)  # Store recent telemetry

        # Start serial reading thread if serial available
        if self.ser:
            self.start_serial_thread()

        # Frame processing
        self.frame_count = 0
        self.last_detection_time = 0
        self.detection_cooldown = 2.0  # seconds between alerts

    def start_serial_thread(self):
        """Start background thread for reading serial data"""
        self.serial_running = True
        self.serial_thread = threading.Thread(target=self.read_serial_data, daemon=True)
        self.serial_thread.start()
        print("Serial reading thread started")

    def read_serial_data(self):
        """Background thread to read and parse serial data from ESP32"""
        buffer = ""
        while self.serial_running and self.ser and self.ser.is_open:
            try:
                if self.ser.in_waiting > 0:
                    data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data

                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self.process_telemetry_line(line)

            except Exception as e:
                print(f"Serial read error: {e}")
                time.sleep(0.1)

    def process_telemetry_line(self, line):
        """Parse incoming telemetry data from ESP32"""
        try:
            # Expected format: "temp,humidity,gas,distL,distR" or JSON for extended data
            if line.startswith('{') and line.endswith('}'):
                # JSON format for extended data (neighbors, map data, etc.)
                data = json.loads(line)
                self.process_extended_telemetry(data)
            else:
                # CSV format: temp,humidity,gas,distL,distR
                parts = line.split(',')
                if len(parts) >= 5:
                    self.sensor_data['temperature'] = float(parts[0])
                    self.sensor_data['humidity'] = float(parts[1])
                    self.sensor_data['gas_level'] = int(parts[2])  # Assuming MQ sensor analog value
                    self.sensor_data['distance_left'] = float(parts[3])
                    self.sensor_data['distance_right'] = float(parts[4])
                    self.sensor_data['timestamp'] = time.time()

                    # Add to buffer for trend analysis
                    self.telemetry_buffer.append({
                        'timestamp': self.sensor_data['timestamp'],
                        'temperature': self.sensor_data['temperature'],
                        'humidity': self.sensor_data['humidity'],
                        'gas_level': self.sensor_data['gas_level'],
                        'dist_left': self.sensor_data['distance_left'],
                        'dist_right': self.sensor_data['distance_right']
                    })

                    # Update Jharkhand-specific hazard detection
                    self.update_jharkhand_hazards()

        except Exception as e:
            print(f"Telemetry parse error: {e} - Line: {line}")

    def process_extended_telemetry(self, data):
        """Process JSON extended telemetry (neighbors, mapping data, etc.)"""
        msg_type = data.get('type', 'sensor')

        if msg_type == 'neighbor_info':
            # Update neighbor information from mesh network
            node_id = data.get('node_id')
            if node_id:
                self.neighbors[node_id] = {
                    'last_seen': time.time(),
                    'signal_strength': data.get('rssi', 0),
                    'status': data.get('status', 'UNKNOWN'),
                    'position': data.get('position', None),
                    'battery': data.get('battery', 100)
                }
                print(f"Updated neighbor {node_id}: RSSI={data.get('rssi', 0)}, Status={data.get('status')}")

        elif msg_type == 'map_update':
            # Update local map with shared information
            self.update_shared_map(data.get('map_data', {}))

        elif msg_type == 'exit_info':
            # Receive exit location information from other nodes
            exit_pos = data.get('exit_position')
            if exit_pos and exit_pos not in self.known_exits:
                self.known_exits.append(tuple(exit_pos))
                print(f"New exit discovered at {exit_pos}")

    def update_jharkhand_hazards(self):
        """Update Jharkhand-specific hazard detection based on sensor trends"""
        if len(self.telemetry_buffer) < 2:
            return

        recent = list(self.telemetry_buffer)[-10:]  # Last 10 readings
        current = recent[-1]

        # Temperature anomaly (sudden increase could indicate fire)
        if len(recent) >= 10:
            temp_trend = np.mean([r['temperature'] for r in recent[-5:]]) - np.mean([r['temperature'] for r in recent[-10:-5]])
            self.jharkhand_hazards['temperature_anomaly'] = temp_trend > 2.0  # >2°C increase

        # Methane accumulation (Jharkhand coal mines have methane risks)
        # Assuming gas_level correlates with methane - needs calibration
        self.jharkhand_hazards['methane_accumulation'] = current['gas_level'] > self.SENSOR_THRESHOLDS['methane_high']

        # CO buildup (from incomplete combustion)
        # Would need specific CO sensor, but using gas_level as proxy for now
        self.jharkhand_hazards['co_buildup'] = current['gas_level'] > self.SENSOR_THRESHOLDS['co_high']

        # Humidity anomaly (water inundation risk)
        if len(recent) >= 5:
            humidity_avg = np.mean([r['humidity'] for r in recent[-5:]])
            self.jharkhand_hazards['humidity_anomaly'] = humidity_avg > self.SENSOR_THRESHOLDS['humidity_high']

        # Coal dust explosion risk (combination of dust, methane, and ignition source)
        # Simplified: high methane + restricted ventilation (close obstacles)
        dist_avg = (current['dist_left'] + current['dist_right']) / 2
        self.jharkhand_hazards['coal_dust_explosion_risk'] = (
            current['gas_level'] > 300 and  # Elevated methane
            dist_avg < 40  # Confined space
        )

        # Structural weakness (based on inconsistent obstacle detection)
        # Would need more sophisticated analysis - placeholder for now

    def get_optimal_exit(self):
        """Calculate optimal exit path using simple greedy algorithm"""
        if not self.known_exits:
            return None

        # Simple distance-based selection (would be enhanced with actual mapping)
        best_exit = None
        min_distance = float('inf')

        for exit_pos in self.known_exits:
            # Euclidean distance (simplified)
            distance = np.sqrt((exit_pos[0] - self.current_position[0])**2 +
                             (exit_pos[1] - self.current_position[1])**2)
            if distance < min_distance:
                min_distance = distance
                best_exit = exit_pos

        return best_exit

    def detect_neighbors_in_view(self, frame):
        """Use computer vision to detect visual markers of neighboring rovers"""
        # This would look for specific visual identifiers (LED patterns, markers, etc.)
        # Placeholder implementation
        neighbors_detected = []

        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Example: detect specific color markers (adjust for your marker colors)
        # Red markers for neighboring rovers
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 50, 50])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = mask1 + mask2

        # Find contours
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 100:  # Minimum area threshold
                x, y, w, h = cv2.boundingRect(contour)
                neighbors_detected.append({
                    'position': (x + w//2, y + h//2),
                    'area': area,
                    'bounding_box': (x, y, w, h)
                })
                # Draw detection on frame
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                cv2.putText(frame, 'NEIGHBOR', (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        return neighbors_detected

    def enhance_low_light(self, frame):
        yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        yuv[:,:,0] = clahe.apply(yuv[:,:,0])
        return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

    def run_inference(self):
        print("Starting Mine Brain AI Processing...")
        print("Features enabled:")
        print("- YOLOv8 human detection")
        print("- Sensor data processing & Jharkhand hazard analysis")
        print("- Neighbor detection (visual & mesh network)")
        print("- Optimal exit calculation")
        print("- Jharkhand-specific safety monitoring")
        print("- Press 'q' to quit")

        while self.cam_forward.isOpened():
            ret, frame = self.cam_forward.read()
            if not ret:
                print("Failed to grab frame")
                break

            self.frame_count += 1

            # Process every 3rd pixel for performance on Pi 4
            if self.frame_count % 3 != 0:
                # Still show frame but skip heavy processing
                cv2.imshow("Underground AI Hub - Mine Brain", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'): break
                continue

            enhanced = self.enhance_low_light(frame)

            # 1. Human Detection (YOLOv8)
            results = self.model(enhanced, stream=True, conf=0.40)
            human_found = False
            detection_confidence = 0.0

            for result in results:
                for box in result.boxes:
                    if int(box.cls) == 0: # Human identified (COCO class 0 = person)
                        human_found = True
                        confidence = float(box.conf[0])
                        detection_confidence = max(detection_confidence, confidence)
                        x1, y1, x2, y2 = map(int, box.xyxy[0])

                        # Color coding based on confidence
                        color = (0, int(255 * confidence), 0)  # Green intensity based on confidence
                        cv2.rectangle(enhanced, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(enhanced, f"MINER: {confidence:.2f}", (x1, y1-10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                        # Trigger alert with cooldown
                        current_time = time.time()
                        if human_found and self.ser and (current_time - self.last_detection_time) > self.detection_cooldown:
                            self.ser.write(b'H\n') # Flag: Human found
                            self.last_detection_time = current_time
                            print(f"🚨 HUMAN DETECTED! Confidence: {confidence:.2f}")

            # 2. Visual Neighbor Detection
            visual_neighbors = self.detect_neighbors_in_view(enhanced)

            # 3. Display Sensor Data and Hazards
            self.display_sensor_overlay(enhanced)

            # 4. Display Navigation Info
            self.display_navigation_overlay(enhanced)

            # 5. Display Neighbor Info
            self.display_neighbor_overlay(enhanced, visual_neighbors)

            # 6. Check and display Jharkhand-specific hazards
            self.display_jharkhand_hazards_overlay(enhanced)

            # 7. Normal operation signal if no human detected recently
            if not human_found and self.ser:
                current_time = time.time()
                if current_time - self.last_detection_time > 1.0:  # Send N periodically when clear
                    self.ser.write(b'N\n') # Flag: Normal
                    self.last_detection_time = current_time

            # 8. Ingest serial telemetry (handled by background thread)
            # Display latest telemetry
            if self.ser and self.ser.in_waiting > 0:
                # Handled by background thread, just show latest
                pass

            cv2.imshow("Underground AI Hub - Mine Brain", enhanced)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

        self.cleanup()

    def display_sensor_overlay(self, frame):
        """Display sensor readings on frame"""
        y_offset = 30
        line_height = 25

        cv2.putText(frame, f"TEMP: {self.sensor_data['temperature']:.1f}°C",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        y_offset += line_height

        cv2.putText(frame, f"HUM: {self.sensor_data['humidity']:.1f}%",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        y_offset += line_height

        cv2.putText(frame, f"GAS: {self.sensor_data['gas_level']}",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        y_offset += line_height

        cv2.putText(frame, f"L: {self.sensor_data['distance_left']:.0f}cm R: {self.sensor_data['distance_right']:.0f}cm",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    def display_navigation_overlay(self, frame):
        """Display navigation and exit information"""
        y_offset = frame.shape[0] - 80

        optimal_exit = self.get_optimal_exit()
        if optimal_exit:
            cv2.putText(frame, f"EXIT: ({optimal_exit[0]:.1f}, {optimal_exit[1]:.1f})m",
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        else:
            cv2.putText(frame, "EXIT: SEARCHING...",
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.putText(frame, f"NEIGHBORS: {len(self.neighbors)}",
                   (10, y_offset + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    def display_neighbor_overlay(self, frame, visual_neighbors):
        """Display detected neighbors"""
        y_offset = 30
        x_offset = frame.shape[1] - 250

        cv2.putText(frame, f"VISUAL NEIGHBORS: {len(visual_neighbors)}",
                   (x_offset, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # Show mesh network neighbors
        mesh_y = y_offset + 25
        cv2.putText(frame, f"MESH NEIGHBORS: {len(self.neighbors)}",
                   (x_offset, mesh_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

        # List recent neighbors
        for i, (node_id, info) in enumerate(list(self.neighbors.items())[-3:]):  # Last 3
            age = time.time() - info['last_seen']
            if age < 30:  # Only show recently seen
                cv2.putText(frame, f"{node_id}: {info['status']} ({info['signal_strength']}dBm)",
                           (x_offset, mesh_y + 25*(i+1)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def display_jharkhand_hazards_overlay(self, frame):
        """Display Jharkhand-specific hazard warnings"""
        hazard_y = 30
        x_offset = frame.shape[1] // 2

        hazards = self.jharkhand_hazards
        alert_count = sum(1 for v in hazards.values() if v)

        if alert_count > 0:
            # pulsing red background for alerts
            alpha = 0.3 + 0.2 * np.sin(time.time() * 5)  # Pulse effect
            overlay = frame.copy()
            cv2.rectangle(overlay, (x_offset - 10, 10), (frame.shape[1] - 10, 80), (0, 0, 150), -1)
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

            cv2.putText(frame, "⚠️ JHARKHAND MINE HAZARDS ⚠️",
                       (x_offset, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # List active hazards
            hazard_text = []
            if hazards['methane_accumulation']:
                hazard_text.append("CH4 HIGH")
            if hazards['co_buildup']:
                hazard_text.append("CO HIGH")
            if hazards['temperature_anomaly']:
                hazard_text.append("TEMP RISE")
            if hazards['humidity_anomaly']:
                hazard_text.append("HUMIDITY HIGH")
            if hazards['coal_dust_explosion_risk']:
                hazard_text.append("EXPLOSION RISK")
            if hazards['structural_weakness']:
                hazard_text.append("WEAK STRUCTURE")

            if hazard_text:
                cv2.putText(frame, " | ".join(hazard_text),
                           (x_offset, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    def update_shared_map(self, map_data):
        """Update local map with shared data from neighbors"""
        # Placeholder for map merging logic
        pass

    def cleanup(self):
        """Clean up resources"""
        print("Shutting down Mine Brain...")
        self.serial_running = False
        if self.serial_thread:
            self.serial_thread.join(timeout=1.0)
        if self.ser:
            self.ser.close()
        self.cam_forward.release()
        cv2.destroyAllWindows()
        print("Mine Brain shutdown complete.")

if __name__ == "__main__":
    brain = MineBrain()
    brain.run_inference()