from flask import Flask
app = Flask(__name__)

@app.route("/ping")
def ping():
    return "pong from vercel_test"

@app.route("/")
def index():
    return "Index from vercel_test"
