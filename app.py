from flask import Flask, render_template, request, jsonify
import requests
import os
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_URL_DEPOSITS = os.environ.get("API_URL_DEPOSITS", "https://api.asafebroker.com/admin-token/deposits")
# Assumindo que existe um endpoint para usuários. Se não, precisará ser adaptado.
API_URL_USERS = os.environ.get("API_URL_USERS", "https://api.asafebroker.com/admin-token/users")
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
        logging.info(f"Fazendo requisição para API externa de depósitos: {API_URL_DEPOSITS} com params: {params}")
        response = requests.get(API_URL_DEPOSITS, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        logging.info("Dados de depósitos da API externa recebidos com sucesso.")
        return jsonify(data)
    except requests.exceptions.Timeout:
        logging.error("Timeout ao conectar com a API externa de depósitos.")
        return jsonify({"error": "A API externa de depósitos demorou muito para responder."}), 504
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Erro de conexão com a API externa de depósitos: {e}")
        return jsonify({"error": "Não foi possível conectar à API externa de depósitos."}), 503
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar dados de depósitos da API externa: {e}, Resposta: {response.text if 'response' in locals() else 'N/A'}")
        return jsonify({"error": "Erro ao buscar dados de depósitos da API externa", "details": str(e)}), 500
    except Exception as e:
        logging.critical(f"Erro inesperado no endpoint /data: {e}")
        return jsonify({"error": "Ocorreu um erro inesperado no servidor."}), 500

@app.route("/user-balances")
def user_balances():
    try:
        top_n = int(request.args.get("topN", 10))
        order_by = request.args.get("orderBy", "balance")
        order_direction = request.args.get("orderDirection", "DESC")
    except ValueError as e:
        logging.error(f"Erro de validação de parâmetro para saldos: {e}")
        return jsonify({"error": "Parâmetros de requisição de saldos inválidos", "details": str(e)}), 400

    logging.info(f"Requisição recebida para /user-balances com topN={top_n}, orderBy={order_by}, orderDirection={order_direction}")

    all_users_data = []
    current_page_users = 1
    page_size_users = 100 # Tamanho de página para buscar usuários

    try:
        headers = {"api-token": API_TOKEN}
        
        # Loop para buscar todas as páginas de usuários
        while True:
            params = {
                "page": current_page_users,
                "pageSize": page_size_users,
            }
            logging.info(f"Buscando página de usuários {current_page_users} da API externa: {API_URL_USERS}")
            response = requests.get(API_URL_USERS, headers=headers, params=params, timeout=15) # Timeout maior para agregação
            response.raise_for_status()
            result = response.json()
            
            users_on_page = result.get('data', [])
            all_users_data.extend(users_on_page)

            if current_page_users >= result.get('pages', 1):
                break # Sai do loop se não houver mais páginas
            current_page_users += 1

        processed_users = []
        for user in all_users_data:
            real_balance = 0
            if 'wallets' in user and isinstance(user['wallets'], list):
                for wallet in user['wallets']:
                    if wallet.get('type') == 'REAL':
                        real_balance = wallet.get('balance', 0)
                        break # Encontrou a carteira REAL, pode parar de procurar

            processed_users.append({
                "id": user.get('id'),
                "name": user.get('name'),
                "email": user.get('email'),
                "nickname": user.get('nickname'),
                "lastLoginAt": user.get('lastLoginAt'),
                "balance": real_balance # Saldo da carteira REAL
            })
        
        # Ordenar os usuários
        if order_by == "balance":
            processed_users.sort(key=lambda x: x.get('balance', 0), reverse=(order_direction == "DESC"))
        elif order_by == "name":
            processed_users.sort(key=lambda x: x.get('name', '').lower(), reverse=(order_direction == "DESC"))
        elif order_by == "email":
            processed_users.sort(key=lambda x: x.get('email', '').lower(), reverse=(order_direction == "DESC"))

        # Retornar apenas o top N
        top_users = processed_users[:top_n]
        
        logging.info(f"Saldos de usuários processados. Retornando Top {len(top_users)}.")
        return jsonify({"data": top_users})

    except requests.exceptions.Timeout:
        logging.error("Timeout ao conectar com a API externa de usuários.")
        return jsonify({"error": "A API externa de usuários demorou muito para responder."}), 504
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Erro de conexão com a API externa de usuários: {e}")
        return jsonify({"error": "Não foi possível conectar à API externa de usuários."}), 503
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar dados de usuários da API externa: {e}, Resposta: {response.text if 'response' in locals() else 'N/A'}")
        return jsonify({"error": "Erro ao buscar dados de usuários da API externa", "details": str(e)}), 500
    except Exception as e:
        logging.critical(f"Erro inesperado no endpoint /user-balances: {e}")
        return jsonify({"error": "Ocorreu um erro inesperado no servidor."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
