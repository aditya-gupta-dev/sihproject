import cv2
import serial
from ultralytics import YOLO
import time

class MineBrain:
    def __init__(self, serial_port='/dev/ttyUSB0', baud_rate=115200):
        # Load YOLOv8 Model - Pre-converted to NCNN for optimized Pi 4 CPU frames
        try:
            self.model = YOLO('yolov8n_ncnn_model')
        except:
            print("NCNN model not found. Compiling original model to NCNN format...")
            base_model = YOLO('yolov8n.pt')
            base_model.export(format='ncnn')
            self.model = YOLO('yolov8n_ncnn_model')

        # Serial connection to the Rover ESP32
        try:
            self.ser = serial.Serial(serial_port, baud_rate, timeout=1)
        except Exception as e:
            print(f"Serial link failed: {e}. Running in standalone vision mode.")
            self.ser = None

        # Camera Array Initialization
        self.cam_forward = cv2.VideoCapture(0)
        self.cam_forward.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cam_forward.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    def enhance_low_light(self, frame):
        yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        yuv[:,:,0] = clahe.apply(yuv[:,:,0])
        return cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

    def run_inference(self):
        while self.cam_forward.isOpened():
            ret, frame = self.cam_forward.read()
            if not ret: break

            enhanced = self.enhance_low_light(frame)
            results = self.model(enhanced, stream=True, conf=0.40)
            human_found = False

            for result in results:
                for box in result.boxes:
                    if int(box.cls) == 0: # Human identified
                        human_found = True
                        x1, y1, x2, y2 = map(int, box.xyxy)
                        cv2.rectangle(enhanced, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(enhanced, "MINER LOCATED", (x1, y1-10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Transmit localized event flags down to the ESP32 Actuator
            if human_found and self.ser:
                self.ser.write(b'H\n') # Flag: Human found
            elif self.ser:
                self.ser.write(b'N\n') # Flag: Normal

            # Ingest and display real-time sensor data relayed from the ESP32
            if self.ser and self.ser.in_waiting > 0:
                telemetry = self.ser.readline().decode('utf-8').rstrip()
                print(f"Live Telemetry Packet: {telemetry}")

            cv2.imshow("Underground AI Hub", enhanced)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

        self.cam_forward.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    brain = MineBrain()
    brain.run_inference()