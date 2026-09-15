# pyrefly: ignore [missing-import]
import cv2
# pyrefly: ignore [missing-import]
import numpy as np
import time
import threading
import json
from collections import deque
import random
try:
    # pyrefly: ignore [missing-import]
    from ultralytics import YOLO
    HAVE_ULTRALYTICS = True
except ImportError:
    HAVE_ULTRALYTICS = False
    YOLO = None

class DummySerial:
    """Simulates serial communication for testing"""
    def __init__(self):
        self.in_waiting = 0
        self._buffer = ""
        self._lock = threading.Lock()
        self.last_write_time = 0
        self.write_delay = 0.1  # Minimum time between writes

        # Test scenario controls
        self.scenario = "NORMAL"  # NORMAL, HAZARD, OBSTACLE, HUMAN, EXIT_TEST
        self.scenario_time = 0
        self.scenario_duration = 10  # seconds per scenario

        # Base sensor values
        self.base_temp = 25.0
        self.base_humid = 60.0
        self.base_gas = 50
        self.base_distL = 100.0
        self.base_distR = 100.0

    def write(self, data):
        """Simulate writing to serial (commands from brain to ESP32)"""
        cmd = data.decode('utf-8').strip()
        print(f"[TEST] Brain -> ESP32: '{cmd}'")
        # In real scenario, this would control the rover
        # For testing, we just log it

    def read(self, size=1):
        """Simulate reading from serial (ESP32 to brain)"""
        with self._lock:
            if not self._buffer:
                return b""
            # Return up to size characters
            to_read = min(size, len(self._buffer))
            result = self._buffer[:to_read]
            self._buffer = self._buffer[to_read:]
            self.in_waiting = len(self._buffer)
            return result.encode('utf-8')

    def generate_telemetry(self):
        """Generate dummy telemetry data based on current scenario"""
        current_time = time.time()

        # Change scenario periodically for demo
        if current_time - self.scenario_time > self.scenario_duration:
            self.cycle_scenario()
            self.scenario_time = current_time

        # Generate values based on scenario
        if self.scenario == "NORMAL":
            temp = self.base_temp + random.uniform(-2, 2)
            humid = self.base_humid + random.uniform(-5, 5)
            gas = max(0, self.base_gas + random.randint(-10, 10))
            distL = self.base_distL + random.uniform(-10, 10)
            distR = self.base_distR + random.uniform(-10, 10)

        elif self.scenario == "HAZARD":
            # Simulate gas leak or temperature rise
            temp = self.base_temp + random.uniform(5, 15)  # Rising temp
            humid = self.base_humid + random.uniform(0, 20)  # Rising humidity
            gas = self.base_gas + random.randint(100, 300)  # Gas spike
            distL = self.base_distL + random.uniform(-5, 5)
            distR = self.base_distR + random.uniform(-5, 5)

        elif self.scenario == "OBSTACLE":
            # Simulate close obstacles
            temp = self.base_temp + random.uniform(-2, 2)
            humid = self.base_humid + random.uniform(-5, 5)
            gas = self.base_gas + random.randint(-10, 10)
            distL = max(5, self.base_distL * random.uniform(0.1, 0.5))  # Close obstacle left
            distR = self.base_distR + random.uniform(-10, 10)

        elif self.scenario == "HUMAN":
            # Normal sensors but we'll trigger human detection via vision
            temp = self.base_temp + random.uniform(-2, 2)
            humid = self.base_humid + random.uniform(-5, 5)
            gas = self.base_gas + random.randint(-10, 10)
            distL = self.base_distL + random.uniform(-10, 10)
            distR = self.base_distR + random.uniform(-10, 10)

        elif self.scenario == "EXIT_TEST":
            # Test exit calculation
            temp = self.base_temp + random.uniform(-2, 2)
            humid = self.base_humid + random.uniform(-5, 5)
            gas = self.base_gas + random.randint(-10, 10)
            # Simulate finding an exit by having one sensor show open path
            distL = self.base_distL + random.uniform(50, 150)  # Open left
            distR = max(10, self.base_distR * random.uniform(0.2, 0.6))  # Blocked right

        # Add some noise
        temp += random.uniform(-0.5, 0.5)
        humid += random.uniform(-1, 1)
        gas += random.randint(-5, 5)

        # Format as CSV: temp,humidity,gas,distL,distR
        telemetry = f"{temp:.1f},{humid:.1f},{int(gas)},{distL:.1f},{distR:.1f}\n"

        # Occasionally send JSON extended data (neighbors, map info)
        if random.random() < 0.1:  # 10% chance
            extended_data = self.generate_extended_telemetry()
            with self._lock:
                self._buffer += extended_data
                self.in_waiting = len(self._buffer)
        else:
            with self._lock:
                self._buffer += telemetry
                self.in_waiting = len(self._buffer)

    def generate_extended_telemetry(self):
        """Generate JSON extended telemetry for neighbor/map data"""
        data_types = ["neighbor_info", "map_update", "exit_info"]
        data_type = random.choice(data_types)

        if data_type == "neighbor_info":
            return json.dumps({
                "type": "neighbor_info",
                "node_id": f"RELAY_{random.randint(1,3)}",
                "rssi": random.randint(-70, -40),
                "status": random.choice(["NOMINAL", "ALERT", "LOW_BATTERY"]),
                "position": [random.uniform(-10, 10), random.uniform(-10, 10)],
                "battery": random.randint(20, 100)
            }) + "\n"

        elif data_type == "exit_info":
            return json.dumps({
                "type": "exit_info",
                "exit_position": [random.uniform(-20, 20), random.uniform(-20, 20)]
            }) + "\n"

        else:  # map_update
            return json.dumps({
                "type": "map_update",
                "map_data": {"placeholder": "map_data"}
            }) + "\n"

    def cycle_scenario(self):
        """Cycle through test scenarios"""
        scenarios = ["NORMAL", "HAZARD", "OBSTACLE", "HUMAN", "EXIT_TEST"]
        current_idx = scenarios.index(self.scenario)
        next_idx = (current_idx + 1) % len(scenarios)
        self.scenario = scenarios[next_idx]
        print(f"[TEST] Switching to scenario: {self.scenario}")

class TestMineBrain:
    def __init__(self, use_webcam=True):
        # Load YOLOv8 Model
        self.model = None
        if HAVE_ULTRALYTICS:
            try:
                self.model = YOLO('yolov8n_ncnn_model')
            except:
                print("NCNN model not found. Using standard YOLOv8n (will download if needed)...")
                try:
                    self.model = YOLO('yolov8n.pt')
                except Exception as e:
                    print(f"Could not load YOLO model: {e}. Fallback to simulated detections.")
                    self.model = None
        else:
            print("[INFO] ultralytics not installed. Running in simulated test mode.")

        # Use dummy serial for testing
        self.ser = DummySerial()
        print("Using DUMMY serial for testing - no hardware required")

        # Camera setup
        self.use_webcam = use_webcam
        if use_webcam:
            self.cam_forward = cv2.VideoCapture(0)
            if not self.cam_forward.isOpened():
                print("Warning: Could not open webcam. Using blank frame.")
                self.use_webcam = False
            else:
                self.cam_forward.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cam_forward.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                print("Webcam initialized successfully")
        else:
            self.cam_forward = None
            print("Running in blank frame mode (no webcam)")

        # Sensor data storage
        self.sensor_data = {
            'temperature': 0.0,
            'humidity': 0.0,
            'gas_level': 0,
            'distance_left': 0.0,
            'distance_right': 0.0,
            'timestamp': time.time()
        }

        # Sensor thresholds
        self.SENSOR_THRESHOLDS = {
            'temperature_high': 45.0,
            'humidity_high': 85.0,
            'methane_high': 500,
            'co_high': 100,
            'distance_min': 30,
            'gas_spike_rate': 50
        }

        # Neighbor tracking
        self.neighbors = {}
        self.own_node_id = "TEST_ROVER"

        # Mapping and navigation
        self.map_grid = {}
        self.current_position = (0, 0)
        self.heading = 0
        self.known_exits = []
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

        # Threading for dummy serial
        self.serial_thread = None
        self.serial_running = False
        self.telemetry_buffer = deque(maxlen=100)

        # Start serial reading thread
        self.start_serial_thread()

        # Frame processing
        self.frame_count = 0
        self.last_detection_time = 0
        self.detection_cooldown = 2.0
        self.force_human_detection = False  # For testing via keyboard

        # Test mode indicators
        self.show_help = True
        self.help_timer = 0

    def start_serial_thread(self):
        """Start background thread for generating dummy serial data"""
        self.serial_running = True
        self.serial_thread = threading.Thread(target=self.generate_dummy_data, daemon=True)
        self.serial_thread.start()
        print("Dummy serial data generation started")

    def generate_dummy_data(self):
        """Background thread to continuously generate dummy telemetry"""
        while self.serial_running:
            self.ser.generate_telemetry()
            time.sleep(0.1)  # 10Hz update rate

    def process_telemetry_line(self, line):
        """Parse incoming telemetry data (same as enhanced version)"""
        try:
            line = line.strip()
            if not line:
                return

            if line.startswith('{') and line.endswith('}'):
                # JSON format for extended data
                data = json.loads(line)
                self.process_extended_telemetry(data)
            else:
                # CSV format: temp,humidity,gas,distL,distR
                parts = line.split(',')
                if len(parts) >= 5:
                    self.sensor_data['temperature'] = float(parts[0])
                    self.sensor_data['humidity'] = float(parts[1])
                    self.sensor_data['gas_level'] = int(parts[2])
                    self.sensor_data['distance_left'] = float(parts[3])
                    self.sensor_data['distance_right'] = float(parts[4])
                    self.sensor_data['timestamp'] = time.time()

                    # Add to buffer
                    self.telemetry_buffer.append({
                        'timestamp': self.sensor_data['timestamp'],
                        'temperature': self.sensor_data['temperature'],
                        'humidity': self.sensor_data['humidity'],
                        'gas_level': self.sensor_data['gas_level'],
                        'dist_left': self.sensor_data['distance_left'],
                        'dist_right': self.sensor_data['distance_right']
                    })

                    # Update hazard detection
                    self.update_jharkhand_hazards()

        except Exception as e:
            print(f"Telemetry parse error: {e} - Line: {line}")

    def process_extended_telemetry(self, data):
        """Process JSON extended telemetry"""
        msg_type = data.get('type', 'sensor')

        if msg_type == 'neighbor_info':
            node_id = data.get('node_id')
            if node_id:
                self.neighbors[node_id] = {
                    'last_seen': time.time(),
                    'signal_strength': data.get('rssi', 0),
                    'status': data.get('status', 'UNKNOWN'),
                    'position': data.get('position', None),
                    'battery': data.get('battery', 100)
                }

        elif msg_type == 'exit_info':
            exit_pos = data.get('exit_position')
            if exit_pos and exit_pos not in self.known_exits:
                self.known_exits.append(tuple(exit_pos))

    def update_jharkhand_hazards(self):
        """Update Jharkhand-specific hazard detection"""
        if len(self.telemetry_buffer) < 2:
            return

        recent = list(self.telemetry_buffer)[-10:]
        current = recent[-1]

        # Temperature anomaly
        if len(recent) >= 10:
            temp_trend = np.mean([r['temperature'] for r in recent[-5:]]) - np.mean([r['temperature'] for r in recent[-10:-5]])
            self.jharkhand_hazards['temperature_anomaly'] = temp_trend > 2.0

        # Methane accumulation
        self.jharkhand_hazards['methane_accumulation'] = current['gas_level'] > self.SENSOR_THRESHOLDS['methane_high']

        # CO buildup
        self.jharkhand_hazards['co_buildup'] = current['gas_level'] > self.SENSOR_THRESHOLDS['co_high']

        # Humidity anomaly
        if len(recent) >= 5:
            humidity_avg = np.mean([r['humidity'] for r in recent[-5:]])
            self.jharkhand_hazards['humidity_anomaly'] = humidity_avg > self.SENSOR_THRESHOLDS['humidity_high']

        # Coal dust explosion risk
        dist_avg = (current['dist_left'] + current['dist_right']) / 2
        self.jharkhand_hazards['coal_dust_explosion_risk'] = (
            current['gas_level'] > 300 and
            dist_avg < 40
        )

    def get_optimal_exit(self):
        """Calculate optimal exit path"""
        if not self.known_exits:
            return None

        best_exit = None
        min_distance = float('inf')

        for exit_pos in self.known_exits:
            distance = np.sqrt((exit_pos[0] - self.current_position[0])**2 +
                             (exit_pos[1] - self.current_position[1])**2)
            if distance < min_distance:
                min_distance = distance
                best_exit = exit_pos

        return best_exit

    def draw_dummy_detections(self, frame):
        """Draw dummy human detections for testing when no real person is present"""
        if self.force_human_detection or (self.ser.scenario == "HUMAN" and random.random() < 0.3):
            # Draw 1-2 fake human detections
            num_detections = random.randint(1, 2)
            for _ in range(num_detections):
                x1 = random.randint(50, frame.shape[1] - 150)
                y1 = random.randint(50, frame.shape[0] - 150)
                w = random.randint(80, 120)
                h = random.randint(150, 200)
                x2 = x1 + w
                y2 = y1 + h

                confidence = random.uniform(0.6, 0.95)
                color = (0, int(255 * confidence), 0)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"MINER: {confidence:.2f}", (x1, y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # Trigger serial command occasionally
                current_time = time.time()
                if current_time - self.last_detection_time > self.detection_cooldown:
                    self.ser.write(b'H\n')
                    self.last_detection_time = current_time

    def run_inference(self):
        print("\n" + "="*60)
        print("MINE BRAIN TEST MODE - LAPTOP TESTING")
        print("="*60)
        print("Controls:")
        print("  'q' - Quit")
        print("  'h' - Toggle help display")
        print("  'f' - Force human detection (for testing)")
        print("  '1-5' - Jump to scenario: 1=NORMAL, 2=HAZARD, 3=OBSTACLE, 4=HUMAN, 5=EXIT_TEST")
        print("  's' - Step through scenarios manually")
        print("  'c' - Clear known exits")
        print("  'e' - Add dummy exit")
        print("="*60)
        print("Features active:")
        print("- YOLOv8 human detection (real or forced)")
        print("- Dummy serial sensor simulation")
        print("- Jharkhand hazard detection")
        print("- Neighbor tracking (simulated)")
        print("- Exit calculation")
        print("- Press keys above to control test scenarios")
        print("="*60 + "\n")

        manual_scenario_mode = False

        while True:
            # Get frame
            if self.use_webcam and self.cam_forward:
                ret, frame = self.cam_forward.read()
                if not ret:
                    print("Warning: Lost webcam feed")
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, "WEBCAM ERROR", (50, 240),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            else:
                # Create blank frame
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                # Add some texture to make it less boring
                for i in range(0, 480, 20):
                    cv2.line(frame, (0, i), (640, i), (20, 20, 20), 1)
                cv2.putText(frame, "NO WEBCAM - BLANK FRAME", (50, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2)

            self.frame_count += 1

            # Process every frame for testing (usually we'd skip for performance)
            enhanced = frame.copy()

            # Apply low-light enhancement (makes blank frame more visible)
            if not self.use_webcam or np.mean(frame) < 30:  # If dark
                enhanced = self.enhance_low_light(enhanced)

            # 1. Human Detection (real or forced)
            human_found = False
            detection_confidence = 0.0

            if self.model is not None:
                results = self.model(enhanced, stream=True, conf=0.25)  # Lower conf for testing
                for result in results:
                    for box in result.boxes:
                        if int(box.cls) == 0: # Human class
                            human_found = True
                            confidence = float(box.conf[0])
                            detection_confidence = max(detection_confidence, confidence)
                            x1, y1, x2, y2 = map(int, box.xyxy[0])

                            color = (0, int(255 * confidence), 0)
                            cv2.rectangle(enhanced, (x1, y1), (x2, y2), color, 2)
                            cv2.putText(enhanced, f"MINER: {confidence:.2f}", (x1, y1-10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # 2. Force dummy detections if enabled or in human scenario
            self.draw_dummy_detections(enhanced)

            # 3. Handle forced human detection via 'f' key
            if self.force_human_detection:
                # Draw a prominent detection in center
                h, w = enhanced.shape[:2]
                x1, y1 = w//4, h//4
                x2, y2 = 3*w//4, 3*h//4
                cv2.rectangle(enhanced, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(enhanced, "FORCED HUMAN DETECTION", (x1, y1-20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                # Trigger serial command
                current_time = time.time()
                if current_time - self.last_detection_time > 0.5:
                    self.ser.write(b'H\n')
                    self.last_detection_time = current_time

            # 4. Send normal signal periodically when no human
            if not human_found and not self.force_human_detection and self.ser.scenario != "HUMAN":
                current_time = time.time()
                if current_time - self.last_detection_time > 2.0:  # Less frequent in test
                    self.ser.write(b'N\n')
                    self.last_detection_time = current_time

            # 5. Process any received serial data
            # (handled by background thread, but we check buffer directly too)
            # In test mode, the background thread handles it, but we can also poll
            if self.ser.in_waiting > 0:
                try:
                    data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                    lines = data.strip().split('\n')
                    for line in lines:
                        if line.strip():
                            self.process_telemetry_line(line)
                except:
                    pass

            # 6. Display overlays
            self.display_sensor_overlay(enhanced)
            self.display_navigation_overlay(enhanced)
            self.display_neighbor_overlay(enhanced)
            self.display_jharkhand_hazards_overlay(enhanced)
            self.display_test_info(enhanced)

            cv2.imshow("Mine Brain Test - Underground AI Hub", enhanced)

            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('h'):
                self.show_help = not self.show_help
                self.help_timer = time.time() + 5  # Show help for 5 seconds
            elif key == ord('f'):
                self.force_human_detection = not self.force_human_detection
                status = "ON" if self.force_human_detection else "OFF"
                print(f"[TEST] Forced human detection: {status}")
            elif key == ord('s'):
                # Step to next scenario manually
                self.ser.cycle_scenario()
                manual_scenario_mode = True
                print(f"[TEST] Manual scenario step to: {self.ser.scenario}")
            elif key == ord('c'):
                self.known_exits.clear()
                print("[TEST] Cleared known exits")
            elif key == ord('e'):
                # Add a dummy exit
                dummy_exit = (random.uniform(-15, 15), random.uniform(-15, 15))
                if dummy_exit not in self.known_exits:
                    self.known_exits.append(dummy_exit)
                    print(f"[TEST] Added dummy exit at {dummy_exit}")
            elif ord('1') <= key <= ord('5'):
                scenario_map = {ord('1'): "NORMAL", ord('2'): "HAZARD", ord('3'): "OBSTACLE",
                              ord('4'): "HUMAN", ord('5'): "EXIT_TEST"}
                self.ser.scenario = scenario_map[key]
                self.ser.scenario_time = time.time()  # Reset timer
                manual_scenario_mode = True
                print(f"[TEST] Jumped to scenario: {self.ser.scenario}")
            elif key == ord('r'):
                # Reset to auto-cycling
                manual_scenario_mode = False
                self.ser.scenario = "NORMAL"
                self.ser.scenario_time = time.time()
                print("[TEST] Reset to auto-cycling scenarios")

            # Auto-cycle scenarios if not in manual mode
            if not manual_scenario_mode:
                # The DummySerial handles its own cycling
                pass
            else:
                # In manual mode, prevent auto-cycling
                pass

        self.cleanup()

    def display_sensor_overlay(self, frame):
        """Display sensor readings on frame"""
        y_offset = 30
        line_height = 25
        bg_color = (0, 0, 0)
        text_color = (0, 255, 255)  # Cyan

        # Semi-transparent background
        overlay = frame.copy()
        cv2.rectangle(overlay, (5, 5), (200, y_offset + 5*line_height + 5), bg_color, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        cv2.putText(frame, f"TEMP: {self.sensor_data['temperature']:.1f}°C",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
        y_offset += line_height

        cv2.putText(frame, f"HUM: {self.sensor_data['humidity']:.1f}%",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
        y_offset += line_height

        cv2.putText(frame, f"GAS: {self.sensor_data['gas_level']}",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
        y_offset += line_height

        cv2.putText(frame, f"L: {self.sensor_data['distance_left']:.0f}cm",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
        y_offset += line_height

        cv2.putText(frame, f"R: {self.sensor_data['distance_right']:.0f}cm",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

    def display_navigation_overlay(self, frame):
        """Display navigation and exit information"""
        y_offset = frame.shape[0] - 80
        x_offset = 10
        bg_color = (0, 0, 0)
        text_color = (0, 255, 255)

        overlay = frame.copy()
        cv2.rectangle(overlay, (x_offset-5, y_offset-20),
                     (x_offset+250, y_offset+30), bg_color, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        optimal_exit = self.get_optimal_exit()
        if optimal_exit:
            cv2.putText(frame, f"EXIT: ({optimal_exit[0]:.1f}, {optimal_exit[1]:.1f})m",
                       (x_offset, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
        else:
            cv2.putText(frame, "EXIT: SEARCHING...",
                       (x_offset, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

        cv2.putText(frame, f"NEIGHBORS: {len(self.neighbors)}",
                   (x_offset, y_offset + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

    def display_neighbor_overlay(self, frame):
        """Display detected neighbors"""
        y_offset = 30
        x_offset = frame.shape[1] - 280
        bg_color = (0, 0, 0)
        text_color = (255, 255, 0)  # Yellow

        overlay = frame.copy()
        cv2.rectangle(overlay, (x_offset-5, y_offset-5),
                     (x_offset+270, y_offset+5*len(list(self.neighbors.values())[-3:])+20),
                     bg_color, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        cv2.putText(frame, f"NEIGHBORS: {len(self.neighbors)}",
                   (x_offset, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)

        # Show last 3 neighbors
        for i, (node_id, info) in enumerate(list(self.neighbors.items())[-3:]):
            age = time.time() - info['last_seen']
            if age < 30:  # Only show recently seen
                status_color = (0, 255, 0) if info['status'] == 'NOMINAL' else (0, 165, 255)
                cv2.putText(frame, f"{node_id}: {info['status']} ({info['signal_strength']}dBm)",
                           (x_offset, y_offset + 25*(i+1)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 1)

    def display_jharkhand_hazards_overlay(self, frame):
        """Display Jharkhand-specific hazard warnings"""
        hazard_y = 30
        x_offset = frame.shape[1] // 2
        bg_color = (80, 0, 0)  # Dark red background
        text_color = (0, 0, 255)  # Red text
        alert_color = (0, 0, 255)  # Bright red for active alerts

        # Count active hazards
        active_hazards = [k for k, v in self.jharkhand_hazards.items() if v]
        alert_count = len(active_hazards)

        if alert_count > 0 or self.show_help and self.help_timer > time.time():
            # Pulsing background for alerts
            if alert_count > 0:
                alpha = 0.3 + 0.2 * np.sin(time.time() * 4)  # Faster pulse for hazards
            else:
                alpha = 0.2  # Dimmer for help

            overlay = frame.copy()
            cv2.rectangle(overlay, (x_offset - 10, 10), (frame.shape[1] - 10, 90), bg_color, -1)
            cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

            if alert_count > 0:
                cv2.putText(frame, "⚠️ JHARKHAND MINE HAZARDS ⚠️",
                           (x_offset, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, alert_color, 2)
            else:
                cv2.putText(frame, "💡 TEST MODE HELP 💡",
                           (x_offset, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # List active hazards or help text
            if alert_count > 0:
                hazard_text = []
                if self.jharkhand_hazards['methane_accumulation']:
                    hazard_text.append("CH4 HIGH")
                if self.jharkhand_hazards['co_buildup']:
                    hazard_text.append("CO HIGH")
                if self.jharkhand_hazards['temperature_anomaly']:
                    hazard_text.append("TEMP RISE")
                if self.jharkhand_hazards['humidity_anomaly']:
                    hazard_text.append("HUMIDITY HIGH")
                if self.jharkhand_hazards['coal_dust_explosion_risk']:
                    hazard_text.append("EXPLOSION RISK")
                if self.jharkhand_hazards['structural_weakness']:
                    hazard_text.append("WEAK STRUCTURE")

                if hazard_text:
                    cv2.putText(frame, " | ".join(hazard_text),
                               (x_offset, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, alert_color, 2)
            else:
                # Show help text
                help_lines = [
                    "CONTROLS:",
                    "Q - Quit",
                    "F - Force human detection",
                    "H - Toggle help",
                    "1-5 - Jump scenarios",
                    "S - Step scenario",
                    "C - Clear exits",
                    "E - Add exit"
                ]
                for i, line in enumerate(help_lines):
                    cv2.putText(frame, line,
                               (x_offset, 55 + i*18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    def display_test_info(self, frame):
        """Display test-specific information"""
        y_offset = frame.shape[0] - 30
        x_offset = frame.shape[1] - 200
        bg_color = (0, 0, 80)  # Dark blue
        text_color = (255, 255, 0)  # Yellow

        overlay = frame.copy()
        cv2.rectangle(overlay, (x_offset-5, y_offset-20),
                     (x_offset+195, y_offset+5), bg_color, -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

        scenario = self.ser.scenario if hasattr(self.ser, 'scenario') == False else getattr(self.ser, 'scenario', 'UNKNOWN')
        cv2.putText(frame, f"SCENARIO: {scenario}",
                   (x_offset, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, text_color, 1)

        cv2.putText(frame, f"FRAME: {self.frame_count}",
                   (x_offset, y_offset + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, text_color, 1)

    def enhance_low_light(self, frame):
        yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        yuv[:,:,0] = clahe.apply(yuv[:,:,0])
        return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

    def cleanup(self):
        """Clean up resources"""
        print("\nShutting down Mine Brain Test...")
        self.serial_running = False
        if self.serial_thread:
            self.serial_thread.join(timeout=1.0)
        if self.use_webcam and self.cam_forward:
            self.cam_forward.release()
        cv2.destroyAllWindows()
        print("Mine Brain Test shutdown complete.")

if __name__ == "__main__":
    import sys

    # Check if user wants to disable webcam
    use_webcam = True
    if len(sys.argv) > 1 and sys.argv[1] == "--no-cam":
        use_webcam = False
        print("Starting in NO CAMERA mode (blank frame)")

    brain = TestMineBrain(use_webcam=use_webcam)
    brain.run_inference()