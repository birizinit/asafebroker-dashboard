from flask import Flask, render_template, request, jsonify
import requests
import os
import logging
# import random # Não é mais necessário para gerar dados fictícios
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

# Novo endpoint para saldos de usuários, agora buscando da API de depósitos
@app.route("/user-balances")
def user_balances():
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("pageSize", 10))
        order_by = request.args.get("orderBy", "user.balance") # Default para balance
        order_direction = request.args.get("orderDirection", "DESC") # Default para DESC
    except ValueError as e:
        logging.error(f"Erro de validação de parâmetro: {e}")
        return jsonify({"error": "Parâmetros de requisição inválidos", "details": str(e)}), 400

    logging.info(f"Requisição recebida para /user-balances com page={page}, pageSize={page_size}, orderBy={order_by}, orderDirection={order_direction}")

    all_users_with_balances = {}
    current_api_page = 1
    external_api_page_size = 100 # Tamanho da página para buscar da API externa (pode ser ajustado)
    has_more_data = True
    total_deposits_fetched = 0

    try:
        headers = {"api-token": API_TOKEN}
        while has_more_data:
            params = {
                "page": current_api_page,
                "pageSize": external_api_page_size,
                "status": "APPROVED", # Assumindo que saldos são relevantes para depósitos aprovados
                "orderBy": "createdAt", # Ordenar por data de criação para tentar pegar o saldo mais recente
                "orderDirection": "DESC" # Do mais recente para o mais antigo
            }
            logging.info(f"Fazendo requisição para API externa de depósitos para coletar saldos: {API_URL} com params: {params}")
            response = requests.get(API_URL, headers=headers, params=params, timeout=20) # Aumentado o timeout
            response.raise_for_status()
            data = response.json()

            deposits = data.get("data", [])
            total_deposits_from_api = data.get("count", 0) # Total de registros na API externa

            if not deposits:
                has_more_data = False
                break

            total_deposits_fetched += len(deposits)

            for deposit in deposits:
                user_info = deposit.get("user")
                if user_info and user_info.get("id"):
                    user_id = user_info["id"]
                    
                    real_balance = None
                    if user_info.get("wallets"):
                        for wallet in user_info["wallets"]:
                            if wallet.get("type") == "REAL":
                                real_balance = wallet.get("balance")
                                break

                    # Se o saldo do usuário na API de depósitos é o "real, atual",
                    # então a cada depósito, o user_info.wallets.balance deve refletir o saldo atual.
                    # Como estamos buscando do mais recente para o mais antigo (orderBy createdAt DESC),
                    # a primeira vez que vemos um usuário, seu saldo deve ser o mais atual.
                    # Se o usuário já foi adicionado, não precisamos atualizar, pois já temos o mais recente.
                    if user_id not in all_users_with_balances:
                        all_users_with_balances[user_id] = {
                            "id": user_id,
                            "name": user_info.get("name"),
                            "email": user_info.get("email"),
                            "nickname": user_info.get("nickname"),
                            "phone": user_info.get("phone"),
                            "country": user_info.get("country"),
                            "lastLoginAt": user_info.get("lastLoginAt"),
                            "user.balance": real_balance # Armazena o saldo real diretamente
                        }
                    # Se o usuário já está no dicionário, e o saldo que temos é None, mas o novo não é, atualiza.
                    elif all_users_with_balances[user_id].get("user.balance") is None and real_balance is not None:
                         all_users_with_balances[user_id]["user.balance"] = real_balance


            current_api_page += 1
            # Condição de parada: se já processamos todos os depósitos conhecidos ou atingimos um limite prático
            if total_deposits_fetched >= total_deposits_from_api and total_deposits_from_api > 0:
                 has_more_data = False
            if current_api_page > 50: # Limite de 50 páginas para evitar sobrecarga excessiva
                logging.warning("Limite de 50 páginas da API externa atingido para coletar saldos de usuários. Pode não ter todos os usuários.")
                has_more_data = False

    except requests.exceptions.Timeout:
        logging.error("Timeout ao conectar com a API externa para coletar saldos.")
        return jsonify({"error": "A API externa demorou muito para responder ao coletar saldos."}), 504
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Erro de conexão com a API externa ao coletar saldos: {e}")
        return jsonify({"error": "Não foi possível conectar à API externa para coletar saldos."}), 503
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar dados da API externa para coletar saldos: {e}, Resposta: {response.text if 'response' in locals() else 'N/A'}")
        return jsonify({"error": "Erro ao buscar dados da API externa para coletar saldos", "details": str(e)}), 500
    except Exception as e:
        logging.critical(f"Erro inesperado no endpoint /user-balances: {e}")
        return jsonify({"error": "Ocorreu um erro inesperado no servidor ao coletar saldos."}), 500

    users_list = list(all_users_with_balances.values())

    # Ordenar os usuários agregados
    if order_by == "user.balance":
        # Ordena por 'user.balance', tratando valores None (coloca-os no final)
        users_list.sort(key=lambda x: x.get("user.balance") if x.get("user.balance") is not None else (-float('inf') if order_direction == "ASC" else float('inf')),
                        reverse=(order_direction == "DESC"))
    elif order_by == "name":
        users_list.sort(key=lambda x: x.get("name", "").lower(), reverse=(order_direction == "DESC"))
    elif order_by == "lastLoginAt":
        users_list.sort(key=lambda x: x.get("lastLoginAt", ""), reverse=(order_direction == "DESC"))

    total_users = len(users_list)
    
    # Aplicar paginação à lista ordenada
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_users = users_list[start_index:end_index]

    response_data = {
        "data": paginated_users,
        "currentPage": page,
        "lastPage": (total_users + page_size - 1) // page_size,
        "count": total_users
    }
    logging.info(f"Retornando {len(paginated_users)} usuários paginados com saldos da API de depósitos.")
    return jsonify(response_data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
