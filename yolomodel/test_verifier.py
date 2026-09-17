import sys
import time
import json
import numpy as np
import brain_engine_test as bet

def run_tests():
    print("=" * 60)
    print("RUNNING COMPREHENSIVE BRAIN ENGINE ACCURACY TESTS")
    print("=" * 60)

    # 1. Initialize
    print("[1/6] Initializing TestMineBrain (no webcam mode)...")
    brain = bet.TestMineBrain(use_webcam=False)
    assert brain.model is not None or not bet.HAVE_ULTRALYTICS, "Model initialization failed"
    print("  -> Initialized successfully. YOLO Model:", type(brain.model))

    # 2. Normal Telemetry Processing
    print("[2/6] Testing Normal Telemetry Parsing...")
    brain.process_telemetry_line("25.0,60.0,40,100.0,100.0\n")
    assert brain.sensor_data['temperature'] == 25.0
    assert brain.sensor_data['humidity'] == 60.0
    assert brain.sensor_data['gas_level'] == 40
    assert brain.sensor_data['distance_left'] == 100.0
    assert brain.sensor_data['distance_right'] == 100.0
    print("  -> Normal telemetry parsed accurately.")

    # 3. Jharkhand Hazard Detection Logic
    print("[3/6] Testing Jharkhand Hazard Detection Logic...")
    # Inject 10 historical readings to establish baseline
    for _ in range(10):
        brain.process_telemetry_line("25.0,60.0,40,100.0,100.0\n")
    
    # Check no hazard initially
    assert not brain.jharkhand_hazards['methane_accumulation']
    assert not brain.jharkhand_hazards['co_buildup']
    assert not brain.jharkhand_hazards['coal_dust_explosion_risk']

    # Now inject high gas spike (gas > 500 triggers methane, > 100 triggers CO, gas > 300 & dist < 40 triggers explosion risk)
    brain.process_telemetry_line("32.0,75.0,550,25.0,25.0\n")
    assert brain.jharkhand_hazards['methane_accumulation'], "Methane accumulation alert failed!"
    assert brain.jharkhand_hazards['co_buildup'], "CO buildup alert failed!"
    assert brain.jharkhand_hazards['coal_dust_explosion_risk'], "Explosion risk alert failed!"
    print("  -> Hazard detection (Methane, CO, Explosion Risk) working accurately.")

    # 4. Extended JSON Telemetry & Neighbors
    print("[4/6] Testing Extended JSON Telemetry (Neighbors & Exits)...")
    neighbor_json = json.dumps({
        "type": "neighbor_info",
        "node_id": "RELAY_ALPHA",
        "rssi": -58,
        "status": "NOMINAL",
        "position": [5.0, 10.0],
        "battery": 92
    })
    brain.process_telemetry_line(neighbor_json + "\n")
    assert "RELAY_ALPHA" in brain.neighbors, "Neighbor tracking failed!"
    assert brain.neighbors["RELAY_ALPHA"]["signal_strength"] == -58

    exit_json = json.dumps({
        "type": "exit_info",
        "exit_position": [12.0, 15.0]
    })
    brain.process_telemetry_line(exit_json + "\n")
    assert (12.0, 15.0) in brain.known_exits, "Exit registration failed!"
    print("  -> Neighbor tracking & Exit registration working accurately.")

    # 5. Optimal Exit Routing
    print("[5/6] Testing Optimal Exit Calculation...")
    brain.known_exits.append((50.0, 50.0))
    optimal = brain.get_optimal_exit()
    assert optimal == (12.0, 15.0), f"Expected (12.0, 15.0), got {optimal}"
    print("  -> Optimal exit calculation working accurately.")

    # 6. Computer Vision Frame Pipeline
    print("[6/6] Testing Frame Processing, CLAHE Enhancement & Overlays...")
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    enhanced = brain.enhance_low_light(dummy_frame)
    assert enhanced.shape == (480, 640, 3)

    # Test overlays
    brain.display_sensor_overlay(enhanced)
    brain.display_navigation_overlay(enhanced)
    brain.display_neighbor_overlay(enhanced)
    brain.display_jharkhand_hazards_overlay(enhanced)
    brain.display_test_info(enhanced)
    print("  -> Visual pipelines and graphic overlays generated successfully.")

    # Clean up
    brain.cleanup()
    print("=" * 60)
    print("ALL 6 CORE SUBSYSTEMS VERIFIED AND FUNCTIONING ACCURATELY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
