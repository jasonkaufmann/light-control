import argparse
import subprocess
import sys

# Path to espota.py
espota_path = "espota.py"  # Replace with the actual path to espota.py

# Paths to binaries for each device type
binaries = {
    "Flat": "binaries/flat-light.ino.bin",
    "Rocker": "binaries/rocker-light.ino.bin"
}

# Compile both binaries only once with verbose output
def compile_sketch(sketch_path, fqbn="esp32:esp32:esp32c3", output_dir="binaries"):
    try:
        print(f"Compiling {sketch_path}...")
        subprocess.run(
            ["arduino-cli", "compile", "--fqbn", fqbn, "--output-dir", output_dir, "--verbose", sketch_path],
            check=True
        )
        print(f"Compilation successful for {sketch_path}!\n")
    except subprocess.CalledProcessError as e:
        print(f"Compilation failed for {sketch_path} with exit code {e.returncode}")
        sys.exit(e.returncode)

# Function to ping the device and return immediately if successful
def ping_device(ip, max_attempts=5):
    print(f"Pinging {ip} to check connectivity...")
    for _ in range(max_attempts):
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],  # -W 1 sets timeout to 1 second per ping
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode == 0:
            print(f"Ping successful for {ip}")
            return True
    print(f"Ping failed for {ip} after {max_attempts} attempts.")
    return False

# Function to run espota.py for OTA update with verbose output
def ota_update(ip, binary_path):
    try:
        print(f"Starting OTA update for {ip} with binary {binary_path}...")
        subprocess.run(
            ["python3", espota_path, "--ip", ip, "--port", "3232", "--file", binary_path, "--auth", "password"],  # replace "password" if authentication is set
            check=True
        )
        print(f"Update successful for {ip}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to update {ip} with error: {e}")

# Argument parsing to handle --light-type, --location, and --skip-compile
parser = argparse.ArgumentParser(description="Compile and update ESP32 devices selectively based on light type or location.")
parser.add_argument("--light-type", choices=["rocker", "flat"], help="Specify the light type to compile and update (rocker or flat).")
parser.add_argument("--location", help="Specify the device location to update.")
parser.add_argument("--skip-compile", action="store_true", help="Skip compilation step if binaries are already compiled.")
args = parser.parse_args()

# Compile the selected sketch based on --light-type unless --skip-compile is used
if not args.skip_compile:
    if args.light_type:
        if args.light_type.lower() == "flat":
            compile_sketch("flat-light/flat-light.ino")
        elif args.light_type.lower() == "rocker":
            compile_sketch("rocker-light/rocker-light.ino")
    else:
        # Compile both if no light type is specified
        compile_sketch("flat-light/flat-light.ino")
        compile_sketch("rocker-light/rocker-light.ino")
else:
    print("Skipping compilation step as --skip-compile is specified.")

# Load device configurations
devices = []
with open("config.txt", "r") as f:
    for line in f:
        parts = line.strip().split(" - ")
        if len(parts) == 3:
            location, ip, device_type = parts
            devices.append({"location": location, "ip": ip, "type": device_type})

# Perform OTA updates for each device that matches the specified --light-type and/or --location
for device in devices:
    device_type = device["type"]
    device_location = device["location"]
    binary_path = binaries.get(device_type)

    # Filter based on --light-type
    if args.light_type and args.light_type.lower() != device_type.lower():
        print(f"Skipping {device_location} ({device['ip']}) as it is not of type {args.light_type.capitalize()}.")
        continue

    # Filter based on --location
    if args.location and args.location.lower() != device_location.lower():
        print(f"Skipping {device_location} ({device['ip']}) as it does not match the specified location {args.location}.")
        continue

    if binary_path:
        print(f"Attempting to update {device_location} ({device['ip']}) with {device_type} firmware...")
        # Check if the device is reachable before trying OTA
        if ping_device(device["ip"]):
            ota_update(device["ip"], binary_path)
        else:
            print(f"Skipping OTA for {device_location} as it is not reachable.")
    else:
        print(f"No binary found for device type: {device_type}")
    print("")  # Add a newline for better readability
