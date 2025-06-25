import time
import re
import telnetlib
from flask import Flask, render_template, jsonify, request
import logging
import ipaddress
import subprocess  # Needed for running Kasa commands
import os
import requests
import sqlite3
import threading
from datetime import datetime
import schedule

# Set up logging
logging.basicConfig(filename='/home/jason/light-control/log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Flask web app setup
app = Flask(__name__)
# Set up environment with modified PATH
env = os.environ.copy()
env["PATH"] += ":/home/jason/.local/bin"

# Database setup
DB_PATH = '/home/jason/light-control/schedules.db'

def init_database():
    """Initialize the database with schedules table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            action TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            days TEXT DEFAULT 'daily',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("Database initialized")

# Initialize database on startup
init_database()
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
def send_kasa_command(ip, action, max_retries=3, retry_delay=1):
    """
    Send command to a Kasa device with retry functionality.
    
    Args:
        ip: IP address of the Kasa device
        action: Action to perform ("on" or "off")
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay between retries in seconds (default: 1)
    
    Returns:
        Tuple of (success, response)
    """
    retries = 0
    while retries <= max_retries:
        try:
            logging.info(f"Sending '{action}' command to Kasa device at {ip} (attempt {retries+1}/{max_retries+1})")
            subprocess.run(["kasa", "--host", ip, action], check=True, env=env)
            logging.info(f"Successfully sent '{action}' command to {ip}")
            if action == 'off' and (ip == '10.0.0.132' or ip == "10.0.0.218"):
                time.sleep(2)
                subprocess.run(["kasa", "--host", ip, "on"], check=True, env=env)
            return True, f"Kasa device {action} successfully"
        except subprocess.CalledProcessError as e:
            if retries < max_retries:
                logging.warning(f"Failed to send '{action}' command to Kasa device at {ip}: {e}. Retry {retries+1}/{max_retries}")
                retries += 1
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to send '{action}' command to Kasa device at {ip} after {max_retries} retries: {e}")
                return False, str(e)
    
    # This line should not be reached, but just in case
    return False, "Maximum retries exceeded"

# Telnet command function
def send_command(ip, command, is_kasa=False, max_retries=3, retry_delay=1):
    """
    Send command to a light with retry functionality.
    
    Args:
        ip: IP address of the light
        command: Command to send ("0" for on, "180" for off)
        is_kasa: Whether this is a Kasa device
        max_retries: Maximum number of retry attempts (default: 3)
        retry_delay: Delay between retries in seconds (default: 1)
    
    Returns:
        Tuple of (success, response)
    """
    if is_kasa:
        logging.info(f"Sending Kasa command '{command}' to {ip}")
        action = "on" if command == "0" else "off"
        return send_kasa_command(ip, action)  # Send Kasa-specific on/off command
    
    # For regular lights, implement retry logic
    retries = 0
    while retries <= max_retries:
        try:
            url = f"http://{ip}/servo"
            response = requests.post(url, data={"position": command})
            if response.status_code == 200:
                logging.info(f"Sent command '{command}' to {ip}; Response: {response.json()}")
                return True, response.json()
            else:
                if retries < max_retries:
                    logging.warning(f"Error sending command to {ip}: {response.status_code}, {response.text}. Retry {retries+1}/{max_retries}")
                    retries += 1
                    time.sleep(retry_delay)
                else:
                    logging.error(f"Error sending command to {ip} after {max_retries} retries: {response.status_code}, {response.text}")
                    return False, response.text
        except Exception as e:
            if retries < max_retries:
                logging.warning(f"Error sending command to {ip}: {e}. Retry {retries+1}/{max_retries}")
                retries += 1
                time.sleep(retry_delay)
            else:
                logging.error(f"Error sending command to {ip} after {max_retries} retries: {e}")
                return False, str(e)
    
    # This line should not be reached, but just in case
    return False, "Maximum retries exceeded"

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

@app.route('/status', methods=['GET'])
def status():
    """
    Endpoint for ESP32 to check if the server is operational.
    Returns a simple JSON response with status.
    """
    return jsonify({'status': 'online', 'message': 'Server is operational'}), 200

# Scheduling functions
def get_schedules():
    """Get all schedules from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM schedules WHERE enabled = 1')
    schedules = cursor.fetchall()
    conn.close()
    return schedules

def execute_scheduled_action(action):
    """Execute a scheduled action (ON or OFF)"""
    logging.info(f"Executing scheduled action: ALL {action}")
    if action == "ON":
        results = send_command_to_all("0")
    else:  # OFF
        results = send_command_to_all("180")
    
    all_success = all(result['success'] for result in results.values())
    if all_success:
        logging.info(f"Scheduled {action} executed successfully")
    else:
        failed_lights = [name for name, result in results.items() if not result['success']]
        logging.error(f"Scheduled {action} failed for: {', '.join(failed_lights)}")

def load_schedules():
    """Load all active schedules and set them up"""
    schedule.clear()  # Clear existing scheduled jobs
    schedules = get_schedules()
    
    for sched in schedules:
        sched_id, time_str, action, enabled, days, created_at = sched
        if enabled:
            # Schedule the job
            schedule.every().day.at(time_str).do(execute_scheduled_action, action).tag(f'schedule_{sched_id}')
            logging.info(f"Loaded schedule {sched_id}: {action} at {time_str}")

def run_scheduler():
    """Background thread to run scheduled tasks"""
    while True:
        schedule.run_pending()
        time.sleep(1)  # Check every second for more accurate timing

# Schedule management API endpoints
@app.route('/schedules', methods=['GET'])
def get_all_schedules():
    """Get all schedules"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM schedules ORDER BY time')
    schedules = []
    for row in cursor.fetchall():
        schedules.append({
            'id': row[0],
            'time': row[1],
            'action': row[2],
            'enabled': bool(row[3]),
            'days': row[4],
            'created_at': row[5]
        })
    conn.close()
    return jsonify(schedules)

@app.route('/schedules', methods=['POST'])
def create_schedule():
    """Create a new schedule"""
    data = request.json
    time_str = data.get('time')
    action = data.get('action')
    days = data.get('days', 'daily')
    
    if not time_str or not action:
        return jsonify({'error': 'Missing required fields'}), 400
    
    if action not in ['ON', 'OFF']:
        return jsonify({'error': 'Action must be ON or OFF'}), 400
    
    # Validate time format
    try:
        datetime.strptime(time_str, '%H:%M')
    except ValueError:
        return jsonify({'error': 'Invalid time format. Use HH:MM'}), 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO schedules (time, action, days) VALUES (?, ?, ?)',
                   (time_str, action, days))
    schedule_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Reload schedules
    load_schedules()
    
    logging.info(f"Created new schedule {schedule_id}: {action} at {time_str}")
    return jsonify({'id': schedule_id, 'message': 'Schedule created successfully'})

@app.route('/schedules/<int:schedule_id>', methods=['DELETE'])
def delete_schedule(schedule_id):
    """Delete a schedule"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM schedules WHERE id = ?', (schedule_id,))
    conn.commit()
    conn.close()
    
    # Reload schedules
    load_schedules()
    
    logging.info(f"Deleted schedule {schedule_id}")
    return jsonify({'message': 'Schedule deleted successfully'})

@app.route('/schedules/<int:schedule_id>/toggle', methods=['PUT'])
def toggle_schedule(schedule_id):
    """Enable/disable a schedule"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get current state
    cursor.execute('SELECT enabled FROM schedules WHERE id = ?', (schedule_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({'error': 'Schedule not found'}), 404
    
    new_state = 0 if result[0] else 1
    cursor.execute('UPDATE schedules SET enabled = ? WHERE id = ?', (new_state, schedule_id))
    conn.commit()
    conn.close()
    
    # Reload schedules
    load_schedules()
    
    logging.info(f"Toggled schedule {schedule_id} to {'enabled' if new_state else 'disabled'}")
    return jsonify({'enabled': bool(new_state)})

if __name__ == '__main__':
    # Load existing schedules
    load_schedules()
    
    # Start scheduler thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logging.info("Started scheduler thread")
    
    # Start the Flask web server in debug mode
    logging.info("Starting Flask web server in debug mode.")
    app.run(host='0.0.0.0', port=5069, debug=True)
