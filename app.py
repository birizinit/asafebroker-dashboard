from flask import Flask, render_template, request, jsonify
import requests
import os
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_URL_DEPOSITS = os.environ.get("API_URL_DEPOSITS", "https://api.asafebroker.com/admin-token/deposits")
# Removido API_URL_USERS, pois usaremos os dados de depósitos para saldos
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

    unique_users = {}
    current_page_deposits = 1
    page_size_deposits = 100 # Tamanho de página para buscar depósitos em massa

    try:
        headers = {"api-token": API_TOKEN}
        
        # Loop para buscar todas as páginas de depósitos
        # ATENÇÃO: Esta abordagem pode ser LENTA e consumir muitos recursos
        # se houver um grande volume de depósitos na API externa.
        # A solução ideal seria uma API que forneça saldos de usuários diretamente.
        while True:
            params = {
                "page": current_page_deposits,
                "pageSize": page_size_deposits,
                "status": "APPROVED" # Apenas depósitos aprovados para garantir dados de usuários válidos
            }
            logging.info(f"Buscando página de depósitos {current_page_deposits} para agregação de saldos.")
            response = requests.get(API_URL_DEPOSITS, headers=headers, params=params, timeout=30) # Timeout maior
            response.raise_for_status()
            result = response.json()
            
            deposits_on_page = result.get('data', [])
            
            for deposit in deposits_on_page:
                user_data = deposit.get('user')
                if user_data and user_data.get('id'):
                    user_id = user_data['id']
                    real_balance = 0
                    if 'wallets' in user_data and isinstance(user_data['wallets'], list):
                        for wallet in user_data['wallets']:
                            if wallet.get('type') == 'REAL':
                                real_balance = wallet.get('balance', 0)
                                break # Encontrou a carteira REAL

                    # Armazena ou atualiza o usuário com o saldo mais recente
                    # (assumindo que o saldo no registro do depósito é o saldo atual do usuário)
                    unique_users[user_id] = {
                        "id": user_id,
                        "name": user_data.get('name'),
                        "email": user_data.get('email'),
                        "nickname": user_data.get('nickname'),
                        "lastLoginAt": user_data.get('lastLoginAt'),
                        "balance": real_balance
                    }

            if current_page_deposits >= result.get('pages', 1):
                break # Sai do loop se não houver mais páginas
            current_page_deposits += 1

        processed_users = list(unique_users.values())
        
        # Ordenar os usuários
        if order_by == "balance":
            processed_users.sort(key=lambda x: x.get('balance', 0), reverse=(order_direction == "DESC"))
        elif order_by == "name":
            processed_users.sort(key=lambda x: x.get('name', '').lower() if x.get('name') else '', reverse=(order_direction == "DESC"))
        elif order_by == "email":
            processed_users.sort(key=lambda x: x.get('email', '').lower() if x.get('email') else '', reverse=(order_direction == "DESC"))

        # Retornar apenas o top N
        top_users = processed_users[:top_n]
        
        logging.info(f"Saldos de usuários processados a partir de depósitos. Retornando Top {len(top_users)}.")
        return jsonify({"data": top_users})

    except requests.exceptions.Timeout:
        logging.error("Timeout ao conectar com a API externa de depósitos para saldos.")
        return jsonify({"error": "A API externa de depósitos demorou muito para responder ao buscar saldos."}), 504
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Erro de conexão com a API externa de depósitos para saldos: {e}")
        return jsonify({"error": "Não foi possível conectar à API externa de depósitos ao buscar saldos."}), 503
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar dados de depósitos para saldos da API externa: {e}, Resposta: {response.text if 'response' in locals() else 'N/A'}")
        return jsonify({"error": "Erro ao buscar dados de depósitos para saldos da API externa", "details": str(e)}), 500
    except Exception as e:
        logging.critical(f"Erro inesperado no endpoint /user-balances: {e}")
        return jsonify({"error": "Ocorreu um erro inesperado no servidor ao buscar saldos."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
