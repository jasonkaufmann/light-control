import time
import re
import telnetlib
from flask import Flask, render_template_string, redirect, url_for

# Set up Telnet connection
HOST = "10.0.0.74"  # Replace with your ESP32's IP address
PORT = 23

# Flask web app setup
app = Flask(__name__)

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

# Flask routes for the web interface
@app.route('/')
def index():
    return render_template_string('''
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
            <title>Servo Control</title>
            <style>
              body {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                font-family: Arial, sans-serif;
                background-color: #f8f9fa;
              }
              .container {
                text-align: center;
              }
              h1 {
                font-size: 2.5em;
                margin-bottom: 1.5em;
                color: #343a40;
              }
              .btn {
                display: block;
                width: 80vw;
                max-width: 300px;
                padding: 20px;
                margin: 10px auto;
                font-size: 2em;
                font-weight: bold;
                color: #fff;
                text-align: center;
                border-radius: 10px;
                text-decoration: none;
                transition: background-color 0.3s ease;
              }
              .btn-on {
                background-color: #28a745;
              }
              .btn-on:hover {
                background-color: #218838;
              }
              .btn-off {
                background-color: #dc3545;
              }
              .btn-off:hover {
                background-color: #c82333;
              }
            </style>
          </head>
          <body>
            <div class="container">
              <h1>Will's Office Light</h1>
              <form action="/on" method="post">
                <button type="submit" class="btn btn-on">ON</button>
              </form>
              <form action="/off" method="post">
                <button type="submit" class="btn btn-off">OFF</button>
              </form>
            </div>
          </body>
        </html>
    ''')

@app.route('/on', methods=['POST'])
def turn_on():
    send_command("0")
    return redirect(url_for('index'))

@app.route('/off', methods=['POST'])
def turn_off():
    send_command("180")
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Start the transcription monitoring in a separate thread
    import threading
    transcription_thread = threading.Thread(target=monitor_file, args=('transcription.txt',))
    transcription_thread.start()

    # Run the Flask web server
    app.run(host='0.0.0.0', port=5069)
