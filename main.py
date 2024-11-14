import time
import re
import telnetlib
from flask import Flask, render_template, jsonify, request
import logging
import ipaddress
import subprocess  # Needed for running Kasa commands
import os

# Set up logging
logging.basicConfig(filename='/home/jason/light-control/log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Flask web app setup
app = Flask(__name__)
# Set up environment with modified PATH
env = os.environ.copy()
env["PATH"] += ":/home/jason/.local/bin"
# Function to read config.txt and return a dictionary of lights
def load_config():
    config = {}
    try:
        with open('/home/jason/light-control/config.txt', 'r') as file:
            for line in file:
                if '-' in line:
                    light_name, ip_address = map(str.strip, line.split('-'))
                    try:
                        # Validate IP address
                        ip = str(ipaddress.ip_address(ip_address))
                        is_kasa = light_name.startswith('$')
                        config[light_name] = {'ip': ip, 'is_kasa': is_kasa}
                    except ValueError:
                        logging.error(f"Invalid IP address '{ip_address}' for light '{light_name}'.")
    except FileNotFoundError:
        logging.error("config.txt file not found.")
    return config

# Function to send Kasa on/off commands using subprocess
def send_kasa_command(ip, action):
    try:
        logging.info(f"Sending '{action}' command to Kasa device at {ip}")
        subprocess.run(["kasa", "--host", ip, action], check=True, env=env)
        logging.info(f"Successfully sent '{action}' command to {ip}")
        if action == 'off' and ip == '10.0.0.132':
            time.sleep(2)
            subprocess.run(["kasa", "--host", ip, "on"], check=True, env=env)
        return True, f"Kasa device {action} successfully"
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to send '{action}' command to Kasa device at {ip}: {e}")
        return False, str(e)

# Telnet command function
def send_command(ip, command, is_kasa=False):
    if is_kasa:
        logging.info(f"Sending Kasa command '{command}' to {ip}")
        action = "on" if command == "0" else "off"
        return send_kasa_command(ip, action)  # Send Kasa-specific on/off command
    try:
        tn = telnetlib.Telnet(ip, 23, timeout=5)
        tn.write(command.encode('ascii') + b"\n")
        response = tn.read_until(b"\n", timeout=5).decode('ascii').strip()
        logging.info(f"Sent command '{command}' to {ip}; Received response: {response}")
        tn.close()
        return True, response
    except Exception as e:
        logging.error(f"Error sending command to {ip}: {e}")
        return False, str(e)

# Telnet command function for all lights
def send_command_to_all(command):
    lights = load_config()
    results = {}
    for name, info in lights.items():
        success, response = send_command(info['ip'], command, info['is_kasa'])
        time.sleep(0.5)
        results[name] = {'ip': info['ip'], 'success': success, 'response': response}
    return results

# Flask routes for the web interface
@app.route('/')
def index():
    lights = load_config()
    buttons_html = ""

    for light_name, info in lights.items():
        # Remove the $ symbol from the light name if it exists
        display_name = light_name.lstrip('$')
        buttons_html += f'''
        <div class="light-control">
          <h2>{display_name}</h2>
          <button class="btn btn-on" data-ip="{info['ip']}" data-action="on">ON</button>
          <button class="btn btn-off" data-ip="{info['ip']}" data-action="off">OFF</button>
        </div>
        '''

    # Adding the All ON and All OFF buttons
    all_buttons_html = '''
        <div class="light-control">
          <h2>All Lights</h2>
          <button class="btn btn-on" id="all-on">ALL ON</button>
          <button class="btn btn-off" id="all-off">ALL OFF</button>
        </div>
    '''

    return render_template('index.html', all_buttons_html=all_buttons_html, buttons_html=buttons_html)

@app.route('/on/<ip>', methods=['POST'])
def turn_on(ip):
    lights = load_config()
    # Find the light that matches the IP and retrieve the is_kasa flag
    for name, info in lights.items():
        if info['ip'] == ip:
            is_kasa = info['is_kasa']
            break
    else:
        logging.error(f"IP address {ip} not found in configuration.")
        return jsonify({'success': False, 'error': 'IP address not found'})

    success, response = send_command(ip, "0", is_kasa)
    if success:
        logging.info(f"Web interface: ON button pressed for {ip}. Response: {response}")
        return jsonify({'success': True, 'response': response})
    else:
        logging.error(f"Web interface: Failed to turn ON {ip}. Error: {response}")
        return jsonify({'success': False, 'error': response})

@app.route('/off/<ip>', methods=['POST'])
def turn_off(ip):
    lights = load_config()
    # Find the light that matches the IP and retrieve the is_kasa flag
    for name, info in lights.items():
        if info['ip'] == ip:
            is_kasa = info['is_kasa']
            break
    else:
        logging.error(f"IP address {ip} not found in configuration.")
        return jsonify({'success': False, 'error': 'IP address not found'})

    success, response = send_command(ip, "180", is_kasa)
    if success:
        logging.info(f"Web interface: OFF button pressed for {ip}. Response: {response}")
        return jsonify({'success': True, 'response': response})
    else:
        logging.error(f"Web interface: Failed to turn OFF {ip}. Error: {response}")
        return jsonify({'success': False, 'error': response})


@app.route('/on_all', methods=['POST'])
def turn_on_all():
    results = send_command_to_all("0")
    all_success = all(result['success'] for result in results.values())
    if all_success:
        logging.info("Web interface: ALL ON buttons pressed successfully.")
        return jsonify({'success': True})  # Return JSON response here
    else:
        failed_lights = [name for name, result in results.items() if not result['success']]
        error_message = f"Failed to turn on: {', '.join(failed_lights)}"
        logging.error(f"Web interface: Failed to turn ALL lights ON. {error_message}")
        return jsonify({'success': False, 'error': error_message})

@app.route('/off_all', methods=['POST'])
def turn_off_all():
    results = send_command_to_all("180")
    all_success = all(result['success'] for result in results.values())
    if all_success:
        logging.info("Web interface: ALL OFF buttons pressed successfully.")
        return jsonify({'success': True})
    else:
        failed_lights = [name for name, result in results.items() if not result['success']]
        error_message = f"Failed to turn off: {', '.join(failed_lights)}"
        logging.error(f"Web interface: Failed to turn ALL lights OFF. {error_message}")
        return jsonify({'success': False, 'error': error_message})

if __name__ == '__main__':
    # Start the Flask web server in debug mode
    logging.info("Starting Flask web server in debug mode.")
    app.run(host='0.0.0.0', port=5069, debug=True)
