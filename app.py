from flask import Flask, render_template, request, jsonify
import requests
import os
import logging

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_URL = os.environ.get("API_URL", "https://api.asafebroker.com/admin-token/deposits")
API_TOKEN = os.environ.get("API_TOKEN", "o7efkbcw58")

def fetch_all_deposits_for_aggregation(start_date, end_date, status="APPROVED"):
    """
    Fetches all approved deposits within a date range for aggregation.
    This function will make multiple API calls if necessary to get all pages.
    """
    headers = {"api-token": API_TOKEN}
    all_data = []
    current_page_agg = 1
    page_size_agg = 100 # Usar um tamanho de página maior para agregação

    try:
        # Primeira chamada para obter o total de páginas e os primeiros dados
        initial_params = {
            "page": 1,
            "pageSize": page_size_agg,
            "startDate": start_date,
            "endDate": end_date,
            "status": status,
            "orderBy": "createdAt",
            "orderDirection": "ASC"
        }
        logging.info(f"Iniciando busca para agregação (página 1) com params: {initial_params}")
        response = requests.get(API_URL, headers=headers, params=initial_params, timeout=20) # Aumentado timeout
        response.raise_for_status()
        initial_result = response.json()
        
        total_pages_agg = initial_result.get('pages', 1)
        all_data.extend(initial_result.get('data', []))

        # Iterar pelas páginas restantes, se houver
        for current_page_agg in range(2, total_pages_agg + 1):
            params = {
                "page": current_page_agg,
                "pageSize": page_size_agg,
                "startDate": start_date,
                "endDate": end_date,
                "status": status,
                "orderBy": "createdAt",
                "orderDirection": "ASC"
            }
            logging.info(f"Buscando página de agregação {current_page_agg}/{total_pages_agg} com params: {params}")
            response = requests.get(API_URL, headers=headers, params=params, timeout=20)
            response.raise_for_status()
            result = response.json()
            all_data.extend(result.get('data', []))

        total_amount = sum(item['amount'] for item in all_data)
        max_deposit = max((item['amount'] for item in all_data), default=0)
        
        logging.info(f"Agregação concluída: Total {total_amount:.2f}, Max {max_deposit:.2f}, Count {len(all_data)}")
        return {
            "total_amount_all_pages": total_amount,
            "max_deposit_all_pages": max_deposit,
            "total_deposits_count_aggregated": len(all_data) # Pode ser útil para verificar
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar dados para agregação da API externa: {e}")
        raise # Re-lança o erro para ser tratado pela rota principal

@app.route("/")
def index():
    logging.info("Servindo index.html")
    return render_template("index.html")

@app.route("/data")
def data():
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("pageSize", 10)) # Agora lendo o pageSize do frontend
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
        "pageSize": page_size, # Usando o pageSize do frontend
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
        
        # 1. Buscar dados paginados
        logging.info(f"Fazendo requisição paginada para API externa: {API_URL} com params: {params}")
        response_paginated = requests.get(API_URL, headers=headers, params=params, timeout=10)
        response_paginated.raise_for_status()
        paginated_data = response_paginated.json()

        # 2. Buscar dados para agregação (totais)
        aggregation_data = fetch_all_deposits_for_aggregation(start_date, end_date, status)

        # 3. Combinar os resultados
        # O 'count' da API paginada já é o total de registros filtrados, então o usamos.
        # Adicionamos os totais de amount e max deposit calculados.
        final_result = {
            **paginated_data, # Inclui data, currentPage, lastPage, count, etc.
            "total_amount_all_pages": aggregation_data["total_amount_all_pages"],
            "max_deposit_all_pages": aggregation_data["max_deposit_all_pages"]
        }
        
        logging.info("Dados da API externa e agregação recebidos com sucesso.")
        return jsonify(final_result)
    except requests.exceptions.Timeout:
        logging.error("Timeout ao conectar com a API externa.")
        return jsonify({"error": "A API externa demorou muito para responder."}), 504
    except requests.exceptions.ConnectionError as e:
        logging.error(f"Erro de conexão com a API externa: {e}")
        return jsonify({"error": "Não foi possível conectar à API externa."}), 503
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao buscar dados da API externa: {e}, Resposta: {response_paginated.text if 'response_paginated' in locals() else 'N/A'}")
        return jsonify({"error": "Erro ao buscar dados da API externa", "details": str(e)}), 500
    except Exception as e:
        logging.critical(f"Erro inesperado no endpoint /data: {e}")
        return jsonify({"error": "Ocorreu um erro inesperado no servidor."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
