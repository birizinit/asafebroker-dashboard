from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

API_URL = "https://api.asafebroker.com/admin-token/deposits"
API_TOKEN = "o7efkbcw58"

def fetch_data(params):
    headers = {"api-token": API_TOKEN}
    response = requests.get(API_URL, headers=headers, params=params)
    response.raise_for_status()  # levanta erro em caso de problema
    return response.json()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    # Pegando parâmetros da query string, com defaults
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("pageSize", 10))
    is_influencer = request.args.get("isInfluencer", "false").lower() == "true"
    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")
    order_by = request.args.get("orderBy", "amount")
    order_direction = request.args.get("orderDirection", "DESC")
    status = request.args.get("status", "APPROVED")

    # Monta params para API externa
    params = {
        "page": page,
        "pageSize": page_size,
        "isInfluencer": str(is_influencer).lower(),
        "startDate": start_date,
        "endDate": end_date,
        "orderBy": order_by,
        "orderDirection": order_direction,
        "status": status,
    }

    try:
        data = fetch_data(params)
    except requests.RequestException as e:
        return jsonify({"error": "Erro ao buscar dados da API externa", "details": str(e)}), 500

    return jsonify(data)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
