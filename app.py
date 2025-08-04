from flask import Flask, render_template, request, jsonify
import requests
import csv
from datetime import datetime

app = Flask(__name__)

API_URL = "https://api.asafebroker.com/admin-token/deposits"
API_TOKEN = "o7efkbcw58"

def fetch_data(params):
    headers = {"api-token": API_TOKEN}
    response = requests.get(API_URL, headers=headers, params=params)
    return response.json()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    params = {
        "page": request.args.get("page", 1),
        "pageSize": request.args.get("pageSize", 10),
        "isInfluencer": request.args.get("isInfluencer", "false"),
        "startDate": request.args.get("startDate"),
        "endDate": request.args.get("endDate"),
        "orderBy": request.args.get("orderBy", "amount"),
        "orderDirection": request.args.get("orderDirection", "DESC"),
        "status": request.args.get("status", "APPROVED"),
    }
    return jsonify(fetch_data(params))

if __name__ == "__main__":
    app.run(debug=True)
