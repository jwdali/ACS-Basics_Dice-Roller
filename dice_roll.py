from flask import Flask, render_template_string, jsonify
import os
import random
import datetime
from collections import deque
import threading

app = Flask(__name__)

# Global state (now thread-safe)
counter = 0
roll_log = deque(maxlen=20)
auto_rolling = False
auto_rps = 5
start_time = datetime.datetime.now()
state_lock = threading.Lock()  # Protects shared state


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎲 ACS Dice Roller</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 900px; margin: 30px auto; padding: 0 20px; background: #f9f9f9; }
        .header { text-align: center; margin-bottom: 30px; }
        .pod-info { background: #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0; font-size: 14px; }
        .dice-display { 
            font-size: 80px; text-align: center; margin: 20px 0; 
            transition: transform 0.3s ease; 
        }
        .roll-active { transform: rotate(360deg); }
        .btn { 
            background: #0070cc; color: white; border: none; padding: 12px 24px; 
            border-radius: 6px; cursor: pointer; font-size: 16px; margin: 5px;
        }
        .btn:hover { background: #005199; }
        .btn:disabled { background: #cccccc; cursor: not-allowed; }
        .btn-stop { background: #d9534f; }
        .btn-stop:hover { background: #c9302c; }
        .log-container { 
            background: white; border: 1px solid #ddd; border-radius: 8px; 
            height: 200px; overflow-y: auto; padding: 10px; margin: 20px 0;
            font-family: monospace; font-size: 14px;
        }
        .status-bar { 
            padding: 12px; border-radius: 6px; margin: 15px 0; text-align: center;
            font-weight: bold;
        }
        .status-idle { background: #d4edda; color: #155724; }
        .status-active { background: #fff3cd; color: #856404; }
        .controls { text-align: center; margin: 20px 0; }
        .rps-control { margin-top: 10px; }
        .rps-control label { margin-right: 10px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎲 Alibaba Cloud ACS Dice Roller</h1>
        <div class="dice-display" id="dice">{{ last_roll if last_roll else '?' }}</div>
    </div>

    <div class="pod-info">
        <strong>Pod:</strong> {{ pod_name }} | 
        <strong>Requests:</strong> {{ counter }} | 
        <strong>Uptime:</strong> {{ uptime }}
    </div>

    <div class="controls">
        <button class="btn" onclick="rollOnce()">Roll Dice Once</button>
        
        {% if auto_rolling %}
            <button class="btn btn-stop" onclick="stopAutoRoll()">Stop Rolling</button>
        {% else %}
            <button class="btn" onclick="startAutoRoll()">Keep Rolling ({{ auto_rps }} RPS)</button>
        {% endif %}
        
        <div class="rps-control">
            <label for="rps">Rolls/sec:</label>
            <input type="range" id="rps" min="1" max="30" value="{{ auto_rps }}" 
                   oninput="updateRps(this.value)" style="width: 150px;">
            <span id="rps-value">{{ auto_rps }}</span>
        </div>
    </div>

    <div class="status-bar {{ 'status-active' if auto_rolling else 'status-idle' }}">
        Status: {{ 'ROLLING CONTINUOUSLY' if auto_rolling else 'IDLE' }}
    </div>

    <h3>Recent Rolls</h3>
    <div class="log-container" id="log">
        {% for entry in roll_log|reverse %}
            <div>{{ entry }}</div>
        {% endfor %}
    </div>

    <script>
        let autoRolling = {{ 'true' if auto_rolling else 'false' }};
        let rps = {{ auto_rps }};

        function updateLog() {
            fetch('/api/log')
                .then(res => res.json())
                .then(data => {
                    const logDiv = document.getElementById('log');
                    logDiv.innerHTML = '';
                    data.log.forEach(entry => {
                        const div = document.createElement('div');
                        div.textContent = entry;
                        logDiv.appendChild(div);
                    });
                    logDiv.scrollTop = logDiv.scrollHeight;
                });
        }

        function updateDice(value) {
            const dice = document.getElementById('dice');
            dice.textContent = value;
            dice.classList.add('roll-active');
            setTimeout(() => dice.classList.remove('roll-active'), 300);
        }

        function rollOnce() {
            fetch('/roll')
                .then(res => res.json())
                .then(data => {
                    updateDice(data.result);
                    updateLog();
                });
        }

        function startAutoRoll() {
            rps = parseInt(document.getElementById('rps').value);
            autoRolling = true;
            document.getElementById('rps-value').textContent = rps;
            sendAutoRoll();
        }

        function sendAutoRoll() {
            if (!autoRolling) return;
            fetch('/roll')
                .then(() => updateLog())
                .catch(console.error);
            setTimeout(sendAutoRoll, 1000 / rps);
        }

        function stopAutoRoll() {
            autoRolling = false;
        }

        function updateRps(value) {
            document.getElementById('rps-value').textContent = value;
            if (autoRolling) {
                rps = parseInt(value);
            }
        }

        // Initial load
        updateLog();
        setInterval(updateLog, 2000);
    </script>
</body>
</html>
'''


def get_uptime():
    return str(datetime.datetime.now() - start_time).split('.')[0]


@app.route('/')
def home():
    global counter, roll_log, auto_rolling, auto_rps
    with state_lock:
        last_roll = roll_log[-1].split(': ')[-1] if roll_log else '?'
        current_counter = counter
        current_auto_rolling = auto_rolling
        current_auto_rps = auto_rps
        current_roll_log = list(roll_log)
    
    return render_template_string(
        HTML_TEMPLATE,
        pod_name=os.getenv('HOSTNAME', 'unknown'),
        counter=current_counter,
        uptime=get_uptime(),
        roll_log=current_roll_log,
        last_roll=last_roll,
        auto_rolling=current_auto_rolling,
        auto_rps=current_auto_rps
    )


@app.route('/roll')
def roll_dice():
    global counter, roll_log
    with state_lock:
        counter += 1
        result = random.randint(1, 6)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        roll_log.append(f"[{timestamp}] Pod {os.getenv('HOSTNAME')} rolled: {result}")
    return jsonify({"result": result})


@app.route('/api/log')
def get_log():
    with state_lock:
        current_log = list(roll_log)
    return jsonify({"log": current_log})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
