from flask import Flask, render_template, request, jsonify
import requests
import os
import logging
import random
from datetime import datetime, timedelta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_URL = os.environ.get("API_URL", "https://api.asafebroker.com/admin-token/deposits")
API_TOKEN = os.environ.get("API_TOKEN", "o7efkbcw58")

@app.route("/")
def index():
    logging.info("Servindo index.html")
    return render_template("index.html")

@app.route("/data")
def data():
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("pageSize", 10))
        is_influencer = request.args.get("isInfluencer", "false").lower() == "true"
        start_date = request.args.get("startDate")
        end_date = request.args.get("endDate")
        order_by = request.args.get("orderBy", "amount")
        order_direction = request.args.get("orderDirection", "DESC")
        status = request.args.get("status", "APPROVED")
    except ValueError as e:
        logging.error(f"Erro de validação de parâmetro: {e}")
        return jsonify({"error": "Parâmetros de requisição inválidos", "details": str(e)}), 400

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
    logging.info(f"Requisição recebida para /data com parâmetros: {params}")

    try:
        headers = {"api-token": API_TOKEN}
        logging.info(f"Fazendo requisição para API externa: {API_URL} com params: {params}")
        response = requests.get(API_URL, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info("Dados da API externa recebidos com sucesso.")
        return jsonify(data) # Retorna apenas os dados paginados da API
    except requests.exceptions.Timeout:
        logging.error("Timeout ao conectar com a API externa.")
        return jsonify({"error": "A API externa demorou muito para responder."}), 504
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Erro de conexão com a API externa: {e}")
        return jsonify({"error": "Não foi possível conectar à API externa."}), 503
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar dados da API externa: {e}, Resposta: {response.text if 'response' in locals() else 'N/A'}")
        return jsonify({"error": "Erro ao buscar dados da API externa", "details": str(e)}), 500
    except Exception as e:
        logging.critical(f"Erro inesperado no endpoint /data: {e}")
        return jsonify({"error": "Ocorreu um erro inesperado no servidor."}), 500

# Novo endpoint para saldos de usuários
@app.route("/user-balances")
def user_balances():
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("pageSize", 10))
        order_by = request.args.get("orderBy", "balance") # Default para balance
        order_direction = request.args.get("orderDirection", "DESC") # Default para DESC
    except ValueError as e:
        logging.error(f"Erro de validação de parâmetro: {e}")
        return jsonify({"error": "Parâmetros de requisição inválidos", "details": str(e)}), 400

    logging.info(f"Requisição recebida para /user-balances com page={page}, pageSize={page_size}, orderBy={order_by}, orderDirection={order_direction}")

    # Simular dados de usuários com saldos
    total_users = 100
    users = []
    for i in range(1, total_users + 1):
        balance = round(random.uniform(10.0, 5000.0), 2)
        last_login = (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat() + "Z"
        users.append({
            "id": f"user_{i}",
            "name": f"Usuário {i}",
            "email": f"usuario{i}@example.com",
            "nickname": f"nick{i}",
            "phone": f"+55{random.randint(10000000000, 99999999999)}",
            "country": "BR",
            "lastLoginAt": last_login,
            "wallets": [
                {"type": "REAL", "balance": balance},
                {"type": "BONUS", "balance": round(random.uniform(0, 100), 2)}
            ]
        })

    # Ordenar os usuários
    if order_by == "balance":
        users.sort(key=lambda x: x["wallets"][0]["balance"] if x["wallets"] and x["wallets"][0]["type"] == "REAL" else 0,
                   reverse=(order_direction == "DESC"))
    elif order_by == "name":
        users.sort(key=lambda x: x["name"], reverse=(order_direction == "DESC"))
    elif order_by == "lastLoginAt":
        users.sort(key=lambda x: x["lastLoginAt"], reverse=(order_direction == "DESC"))

    # Paginação
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_users = users[start_index:end_index]

    response_data = {
        "data": paginated_users,
        "currentPage": page,
        "lastPage": (total_users + page_size - 1) // page_size,
        "count": total_users # Total de registros disponíveis
    }
    logging.info(f"Retornando {len(paginated_users)} usuários paginados.")
    return jsonify(response_data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
