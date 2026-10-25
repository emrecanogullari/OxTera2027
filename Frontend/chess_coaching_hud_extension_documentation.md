# ♟️ Lichess Coaching HUD Extension

A real-time behavioral metrics and coaching HUD for [Lichess.org](https://lichess.org). The extension injects an overlay into live Lichess games and analysis boards, using a local Python FastAPI backend to predict **Expected Thinking Time** and **Blunder Risk** based on game features.

---

## 🚀 Features

* **Real-time Metrics:** Displays predicted move times and blunder risk based on live board dynamics.
* **Interactive UI:** Features drag-and-drop HUD positioning and canvas art.
* **FastAPI Backend Integration:** Connects seamlessly with a local Python inference backend serving models over HTTP.
* **Non-Intrusive Overlay:** Injected cleanly into Lichess without breaking native UI functionality.

---

## 📁 Repository Structure

```text
.
├── app.py                  # FastAPI backend server
├── dummy_predict.json      # API schema reference / dummy data definition
├── requirements.txt        # Python package dependencies
├── manifest.json           # Chrome Extension Manifest V3 configuration
└── content.js              # HUD UI rendering, drag logic, and backend API client
```

---

## 🛠️ Setup Instructions

### 1. Python Backend Setup

Ensure you have **Python 3.8+** installed on your system.

1. Clone or open the project folder in your terminal:
   ```bash
   cd path/to/project-folder
   ```

2. Install backend dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

3. Start the local Uvicorn development server:
   ```bash
   uvicorn app:app --reload
   ```
   The backend server will run on `http://127.0.0.1:8000`.

---

### 2. Chrome Extension Setup

1. Open **Google Chrome** (or any Chromium-based browser like Brave or Edge).
2. Navigate to `chrome://extensions/` in your address bar.
3. Enable **Developer mode** using the toggle switch in the top-right corner.
4. Click **Load unpacked** in the top-left corner.
5. Select the folder containing `manifest.json` and `content.js`.

---

## 🎮 How to Use

1. Ensure the Python backend server is running (`http://127.0.0.1:8000`).
2. Open [Lichess.org](https://lichess.org) and start a game or open an analysis board.
3. The **Coaching HUD** will automatically render on top of your game interface.
4. Drag the HUD header to position it anywhere on your screen.

---

## 📡 API Endpoint Overview

The extension communicates with the backend via a POST request:

* **Endpoint:** `POST http://127.0.0.1:8000/predict`
* **Request Payload Example:**
  ```json
  {
    "speed": "blitz",
    "features": {
      "ply": 14,
      "move_time": 4.2
    }
  }
  ```
* **Response Payload Example:**
  ```json
  {
    "expected_thinking_time": 6.5,
    "blunder_risk": 0.18
  }
  ```

---

## 🤝 Contributing & License

Feel free to open issues or submit pull requests to extend feature extraction or improve model predictions. 

Distributed under the MIT License.