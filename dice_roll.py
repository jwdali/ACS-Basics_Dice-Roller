from flask import Flask, render_template_string, jsonify
import os
import random
import datetime
from collections import deque
import threading
import time

app = Flask(__name__)

# Global state (thread-safe)
counter = 0
roll_log = deque(maxlen=20)
start_time = datetime.datetime.now()
state_lock = threading.Lock()


def burn_cpu(seconds):
    """Burn CPU for approximately `seconds` seconds using a tight loop."""
    end_time = time.time() + seconds
    while time.time() < end_time:
        # Perform a lightweight but CPU-consuming operation
        # Used to simulate load on container
        _ = 3.141592653589793 ** 2  # Fast, no I/O, keeps CPU busy


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🎲 ACS Dice Roller Demo 🎲</title>
    <meta charset="utf-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 900px; margin: 30px auto; padding: 0 20px; background: #f9f9f9; }
        .header { text-align: center; margin-bottom: 30px; }
        .pod-info { 
            background: #e9ecef; padding: 15px; border-radius: 8px; 
            margin: 20px 0; font-size: 14px; text-align: center;
        }
        .dice-display { 
            font-size: 80px; text-align: center; margin: 20px 0; 
            transition: transform 0.3s ease; 
            cursor: default;
        }
        
        /* 🔥 Dice Rolling Animation */
        @keyframes rollDice {
            0%   { transform: rotateY(0deg)   rotateX(0deg); }
            12%  { transform: rotateY(90deg)  rotateX(0deg); }
            25%  { transform: rotateY(180deg) rotateX(0deg); }
            37%  { transform: rotateY(270deg) rotateX(0deg); }
            50%  { transform: rotateY(360deg) rotateX(0deg); }
            62%  { transform: rotateY(360deg) rotateX(90deg); }
            75%  { transform: rotateY(360deg) rotateX(180deg); }
            87%  { transform: rotateY(360deg) rotateX(270deg); }
            100% { transform: rotateY(360deg) rotateX(360deg); }
        }
        
        .rolling {
            animation: rollDice 1s ease-in-out;
            opacity: 0.7;
        }
        
        .dice-face {
            display: inline-block;
            width: 1.2em;
            text-align: center;
        }

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
        .note { 
            font-size: 12px; color: #666; margin-top: -10px; text-align: center; 
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎲 Alibaba Cloud ACS Dice Roller</h1>
        <div class="dice-display" id="dice">?</div>
    </div>

    <div class="pod-info">
        <strong>Current Pod:</strong> <span id="pod-name">{{ pod_name }}</span> | 
        <strong>Requests Handled by This Pod:</strong> <span id="request-count">{{ counter }}</span> | 
        <strong>Uptime:</strong> <span id="uptime">{{ uptime }}</span>
    </div>

    <div class="controls">
        <button class="btn" onclick="rollOnce()">Roll Dice Once</button>
        <button id="actionBtn" class="btn" onclick="toggleRolling()">
            Keep Rolling
        </button>
        
        <div class="rps-control">
            <label for="rps">Rolls/sec:</label>
            <input type="range" id="rps" min="1" max="30" value="10" 
                   oninput="updateRpsLabel()" style="width: 150px;">
            <span id="rps-value">10</span>
        </div>
    </div>

    <div class="status-bar status-idle" id="statusBar">
        Status: IDLE
    </div>

    <h3>Recent Rolls (from this pod only)</h3>
    <div class="log-container" id="log">
        {% for entry in roll_log|reverse %}
            <div>{{ entry }}</div>
        {% endfor %}
    </div>
    <p class="note">
        💡 Refresh the page to see a different pod. In a scaled deployment, 
        each pod tracks its own rolls independently!
    </p>

    <script>
        let autoRolling = false;
        let rps = 10;

        function updateUI() {
            const btn = document.getElementById('actionBtn');
            const status = document.getElementById('statusBar');
            const isRolling = autoRolling;

            if (isRolling) {
                btn.textContent = 'Stop Rolling';
                btn.className = 'btn btn-stop';
            } else {
                btn.textContent = 'Keep Rolling';
                btn.className = 'btn';
            }

            status.textContent = isRolling ? 'Status: ROLLING CONTINUOUSLY' : 'Status: IDLE';
            status.className = isRolling 
                ? 'status-bar status-active' 
                : 'status-bar status-idle';
        }

        function updateRpsLabel() {
            rps = parseInt(document.getElementById('rps').value);
            document.getElementById('rps-value').textContent = rps;
        }

        function updateMetrics() {
            fetch('/api/metrics')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('request-count').textContent = data.counter;
                    document.getElementById('uptime').textContent = data.uptime;
                })
                .catch(console.error);
        }

        function updateDice(value, isRolling = false) {
            const dice = document.getElementById('dice');
            
            if (isRolling) {
                dice.textContent = '🎲';
                dice.className = 'rolling';
            } else {
                const faces = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];
                dice.innerHTML = `<span class="dice-face">${faces[value - 1]}</span>`;
                dice.className = '';
            }
        }

        function rollOnce() {
            updateDice(null, true);
            fetch('/roll')
                .then(res => res.json())
                .then(data => {
                    updateDice(data.result);
                    updateLog();
                })
                .catch(console.error);
        }

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

                    if (data.log.length > 0) {
                        const lastEntry = data.log[data.log.length - 1];
                        const result = lastEntry.split('rolled: ')[1] || '?';
                        // Don't update dice if auto-rolling (to avoid race)
                        if (!autoRolling) {
                            updateDice(parseInt(result));
                        }
                    }
                })
                .catch(console.error);
        }

        function sendAutoRoll() {
            if (!autoRolling) return;
            
            updateDice(null, true);
            fetch('/roll')
                .then(res => res.json())
                .then(data => {
                    if (autoRolling) {
                        updateDice(data.result);
                        updateLog();
                    }
                })
                .catch(console.error)
                .finally(() => {
                    if (autoRolling) {
                        setTimeout(sendAutoRoll, 1000 / rps);
                    }
                });
        }

        function toggleRolling() {
            autoRolling = !autoRolling;
            updateUI();
            if (autoRolling) {
                sendAutoRoll();
            }
        }

        // Initialize
        updateRpsLabel();
        updateUI();
        updateLog();
        updateMetrics();
        
        setInterval(updateLog, 2000);
        setInterval(updateMetrics, 2000);
    </script>
</body>
</html>
'''


def get_uptime():
    return str(datetime.datetime.now() - start_time).split('.')[0]


@app.route('/')
def home():
    global counter, roll_log
    with state_lock:
        last_roll = roll_log[-1].split(': ')[-1] if roll_log else '?'
        current_counter = counter
        current_roll_log = list(roll_log)
    
    return render_template_string(
        HTML_TEMPLATE,
        pod_name=os.getenv('HOSTNAME', 'unknown'),
        counter=current_counter,
        uptime=get_uptime(),
        roll_log=current_roll_log,
        last_roll=last_roll
    )


@app.route('/roll')
def roll_dice():
    global counter, roll_log
    with state_lock:
        counter += 1
        result = random.randint(1, 6)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        roll_log.append(f"[{timestamp}] Pod {os.getenv('HOSTNAME')} rolled: {result}")
    
    # 🔥 Replace sleep with real CPU work (~0.9 seconds of 100% CPU on one core)
    burn_cpu(0.9)
    
    return jsonify({"result": result})


@app.route('/api/log')
def get_log():
    with state_lock:
        current_log = list(roll_log)
    return jsonify({"log": current_log})


@app.route('/api/metrics')
def get_metrics():
    with state_lock:
        current_counter = counter
    return jsonify({
        "counter": current_counter,
        "uptime": get_uptime()
    })


if __name__ == '__main__':
    # For local dev only (use Gunicorn in production)
    app.run(host='0.0.0.0', port=5000, threaded=True)
