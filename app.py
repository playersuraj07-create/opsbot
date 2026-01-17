from flask import Flask
from flask_jwt_extended import JWTManager
import json, os, time
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data", "analytics")

app = Flask(__name__)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "change_me")
jwt = JWTManager(app)

def load(name):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)

@app.route("/")
def home():
    return "OPSBOT DASHBOARD ONLINE"

@app.route("/charts/activity")
def activity_chart():
    data = load("messages")
    if not data:
        return "No data"

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["timestamp"], unit="s")
    counts = df["username"].value_counts().head(10)

    plt.figure(figsize=(8,4))
    counts.plot(kind="bar")
    plt.title("Most Active Users")
    plt.tight_layout()

    img = os.path.join(BASE_DIR, "activity.png")
    plt.savefig(img)
    plt.close()

    return open(img, "rb").read(), 200, {"Content-Type": "image/png"}

@app.route("/charts/warnings")
def warnings_chart():
    data = load("warnings")
    if not data:
        return "No data"

    df = pd.DataFrame(data)
    counts = df["type"].value_counts()

    plt.figure(figsize=(5,4))
    counts.plot(kind="bar")
    plt.title("Warnings Distribution")
    plt.tight_layout()

    img = os.path.join(BASE_DIR, "warnings.png")
    plt.savefig(img)
    plt.close()

    return open(img, "rb").read(), 200, {"Content-Type": "image/png"}

@app.route("/charts/timeouts")
def timeout_chart():
    data = load("timeouts")
    if not data:
        return "No data"

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["timestamp"], unit="s").dt.date
    counts = df["date"].value_counts().sort_index()

    plt.figure(figsize=(6,4))
    counts.plot(kind="line")
    plt.title("Timeouts Over Time")
    plt.tight_layout()

    img = os.path.join(BASE_DIR, "timeouts.png")
    plt.savefig(img)
    plt.close()

    return open(img, "rb").read(), 200, {"Content-Type": "image/png"}

if __name__ == "__main__":
    app.run(port=5000)
