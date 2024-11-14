import time
import re
import telnetlib
import threading

# Set up Telnet connection
HOST = "10.0.0.176"  # Replace with your ESP32's IP address
PORT = 23

# Telnet command function
def send_command(command):
    try:
        tn = telnetlib.Telnet(HOST, PORT)
        tn.write(command.encode('ascii') + b"\n")
        response = tn.read_until(b"\n").decode('ascii').strip()
        print(response)
        tn.close()
    except Exception as e:
        print(f"Error: {e}")

# Function to clear file contents
def clear_file_contents(filename):
    with open(filename, 'w') as file:
        file.truncate(0)
    print(f"Cleared the contents of {filename}.")

# Function to scan entire content for phrases
def scan_file_for_phrases(filename):
    with open(filename, 'r') as file:
        content = file.read()

    # Updated regex patterns to account for any whitespace, line breaks, and optional punctuation
    light_on_pattern = re.compile(r'light\s*[.,;!?]*\s*on\s*[.,;!?]*\s', re.IGNORECASE | re.DOTALL)
    light_off_pattern = re.compile(r'light\s*[.,;!?]*\s*off\s*[.,;!?]*\s', re.IGNORECASE | re.DOTALL)

    # Search for patterns in the content
    light_on_match = light_on_pattern.search(content)
    light_off_match = light_off_pattern.search(content)

    if light_on_match:
        print("Got 'light on'")
        send_command("0")  # Send "on" command via Telnet
        clear_file_contents(filename)  # Clear the file after detection

    elif light_off_match:
        print("Got 'light off'")
        send_command("180")  # Send "off" command via Telnet
        clear_file_contents(filename)  # Clear the file after detection

# Function to continuously monitor the file
def monitor_file(filename, check_interval=1):
    clear_file_contents(filename)  # Clear the file at the start

    try:
        while True:
            scan_file_for_phrases(filename)
            time.sleep(check_interval)

    except FileNotFoundError:
        print(f"The file {filename} does not exist.")

if __name__ == '__main__':
    # Start the transcription monitoring in a separate thread
    transcription_thread = threading.Thread(target=monitor_file, args=('transcription.txt',))
    transcription_thread.start()

    # Keep the script running
    transcription_thread.join()
