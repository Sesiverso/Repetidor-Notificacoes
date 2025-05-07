# app.py
import os
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory
from pywebpush import webpush, WebPushException
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryStore # Usando MemoryStore para SIMPLIFICAR. Não persiste.
# Para produção, instale e use um JobStore persistente:
# from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
# from apscheduler.jobstores.mongodb import MongoDBJobStore


# --- Configuração da Aplicação Flask ---
# Configura para servir arquivos estáticos da pasta 'public'
app = Flask(__name__, static_folder='public')
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True # Formata JSON de resposta (opcional)

# --- Configuração das Chaves VAPID ---
# Substitua pelos seus emails e chaves VAPID geradas
# É ALTAMENTE RECOMENDADO LER ESTAS CHAVES DE VARIÁVEIS DE AMBIENTE EM PRODUÇÃO
# Chave Pública: Copiada do frontend/gerador
VAPID_PUBLIC_KEY = 'BAqiLyUbWPICFTpW4Gf_RpTKWAws6LxDy7Lu3Ch4bUb0OYooef7HG0rAVdLT32qAbtVbszdsIBJb5SjwQBFTm9M'
# Chave Privada: Copiada do gerador (NÃO COMPARTILHE!)
VAPID_PRIVATE_KEY = 'urJRRgLEkfejteAP1AAyed7lmvMAg-dTefB9wF5DVOM' # <-- **INSIRA SUA CHAVE PRIVADA AQUI**
VAPID_CLAIMS = {
    "sub": "mailto:seu.email@exemplo.com" # <-- Substitua pelo seu email de contato
}

print("Configuração VAPID carregada.")
print("Chave Pública (para o frontend):", VAPID_PUBLIC_KEY)
# **NÃO IMPRIMA A CHAVE PRIVADA EM PRODUÇÃO!**


# --- Simulação de Armazenamento de Assinaturas (NÃO USAR EM PRODUÇÃO!) ---
# Em produção, use um banco de dados real (SQLAlchemy com BD, MongoDB, etc.)
# Estrutura: { endpoint: { 'subscription': {...}, 'preferences': {...}, 'sent_count': 0, 'created_at': datetime } }
subscriptions_db = {} # Dicionário em memória - PERDE TUDO AO REINICIAR O SERVIDOR


# --- Configuração do Agendador APScheduler ---
# Usando MemoryStore - Jobs NÃO PERSISTEM se o servidor parar ou reiniciar!
jobstores = {'default': MemoryStore()}
# Exemplo com persistência SQLite (precisa instalar 'SQLAlchemy')
# jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')}

executors = {'default': {'type': 'threadpool', 'max_workers': 10}} # Configurações para executar jobs
job_defaults = {'coalesce': True, 'max_instances': 3} # Configurações padrão para jobs

scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults)

# Verifica se o agendador já está rodando (para evitar iniciar múltiplas vezes se o código for reexecutado)
if not scheduler.running:
    scheduler.start()
    print("Agendador APScheduler iniciado.")
else:
    print("Agendador APScheduler já está rodando.")

# --- Função para Enviar Notificação Push Individual ---
def send_push_notification(subscription_info, message_text, notification_index, total_notifications):
    """Envia uma única notificação push para uma assinatura."""
    if not subscription_info:
        print("Erro: Dados de assinatura nulos ao tentar enviar notificação.")
        return

    # Payload da notificação - o que o Service Worker no navegador vai receber
    # Use o texto do usuário como corpo principal
    payload = json.dumps({
        "title": f"Lembrete ({notification_index}/{total_notifications})", # Título
        "body": message_text, # <-- Texto do usuário como corpo
        "icon": "/icon-192x192.png", # Caminho para um ícone real na pasta public
        "badge": "/badge-72x72.png", # Caminho para um ícone de badge na pasta public
        "data": { # Dados adicionais que o Service Worker pode usar
            "url": "/", # Exemplo: Abrir a página inicial ao clicar
            "message_index": notification_index,
        }
    })

    try:
        print(f"[{datetime.now()}] Tentando enviar notificação {notification_index}/{total_notifications} para endpoint: {subscription_info['endpoint']}")
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS
        )
        print(f"[{datetime.now()}] Notificação {notification_index} enviada com sucesso.")

    except WebPushException as ex:
        print(f"[{datetime.now()}] Erro ao enviar notificação push: {ex}")
        # Tratamento de erros comuns:
        # 410 Gone (assinatura expirou) ou 404 Not Found (assinatura não existe mais)
        # Nestes casos, você deve REMOVER a assinatura do seu banco de dados!
        if ex.response and ex.response.status_code in [410, 404]:
             endpoint_to_remove = subscription_info.get('endpoint')
             if endpoint_to_remove and endpoint_to_remove in subscriptions_db:
                 print(f"[{datetime.now()}] Assinatura expirada ou não encontrada ({ex.response.status_code}). Removendo do DB simulado e cancelando jobs.")
                 # Em um BD real, você executaria uma query para deletar
                 del subscriptions_db[endpoint_to_remove]
                 # Opcional: Cancelar jobs futuros associados a este endpoint
                 for job in scheduler.get_jobs():
                     if hasattr(job.kwargs, 'subscription_info') and job.kwargs['subscription_info'].get('endpoint') == endpoint_to_remove:
                          print(f"[{datetime.now()}] Removendo job agendado: {job.id}")
                          scheduler.remove_job(job.id)

        else:
            # Outros erros (ex: 400 Bad Request, problemas de conexão)
            print(f"[{datetime.now()}] Outro erro de WebPush: Status={ex.response.status_code if ex.response else 'N/A'}, Resposta={ex.response.text if ex.response else 'N/A'}")
            # Você pode querer implementar lógica de retentativa aqui

    except Exception as ex:
        print(f"[{datetime.now()}] Ocorreu um erro inesperado ao enviar a notificação: {ex}")
        # Logar o erro


# --- Endpoint para servir arquivos estáticos (redundante com static_folder, mas explícito) ---
# Flask já faz isso com static_folder='public', mas mantenho como exemplo
# @app.route('/')
# def serve_index():
#     return send_from_directory(app.static_folder, 'index.html')

# @app.route('/<path:filename>')
# def serve_public_files(filename):
#      return send_from_directory(app.static_folder, filename)


# --- Endpoint para receber a assinatura e preferências ---
@app.route('/save-subscription-and-prefs', methods=['POST'])
def save_subscription():
    if not request.json:
        return jsonify({"message": "Requisição deve ser JSON"}), 415 # Unsupported Media Type

    data = request.json
    subscription = data.get('subscription')
    preferences = data.get('preferences') # { 'message', 'repeatCount', 'intervalSeconds' }

    if not subscription or not preferences:
        return jsonify({"message": "Dados de assinatura ou preferências ausentes"}), 400

    endpoint = subscription.get('endpoint')
    if not endpoint:
         return jsonify({"message": "Endpoint de assinatura ausente"}), 400

    message = preferences.get('message')
    repeat_count = preferences.get('repeatCount')
    interval_seconds = preferences.get('intervalSeconds')

    if not message or not isinstance(repeat_count, int) or repeat_count <= 0 or not isinstance(interval_seconds, int) or interval_seconds <= 0:
         return jsonify({"message": "Dados de preferência inválidos"}), 400

    # --- Salvar a assinatura e as preferências ---
    # Em um sistema real, você salvaria isso em um BANCO DE DADOS PERSISTENTE.
    # Usando endpoint como chave no dict é apenas uma simulação simples em memória.
    # Nota: Se o mesmo endpoint enviar uma nova assinatura (refresh, novo navegador),
    # esta lógica simples irá sobrescrever a anterior. Em um BD, você pode querer atualizar.
    subscriptions_db[endpoint] = {
        'subscription': subscription,
        'preferences': preferences,
        'sent_count': 0, # Inicializa contador de envios para este agendamento
        'created_at': datetime.now() # Marca o tempo de criação
    }
    print(f"[{datetime.now()}] Assinatura salva para endpoint: {endpoint}")
    print(f"[{datetime.now()}] Preferências salvas: {preferences}")


    # --- Lógica de Agendamento com APScheduler ---
    # Ao salvar a configuração, removemos agendamentos anteriores para este endpoint
    # e criamos os novos.
    # Em um BD, a lógica seria mais complexa, talvez lendo jobs persistidos.

    # Cancela quaisquer jobs existentes para este endpoint antes de recriar
    # Precisa encontrar jobs associados a este endpoint.
    # No nosso exemplo, podemos iterar sobre os jobs e verificar o endpoint nos kwargs
    for job in scheduler.get_jobs():
         if hasattr(job.kwargs, 'subscription_info') and job.kwargs['subscription_info'].get('endpoint') == endpoint:
              print(f"[{datetime.now()}] Removendo job agendado anterior: {job.id}")
              scheduler.remove_job(job.id)


    # Agora, agenda as novas notificações com APScheduler
    print(f"[{datetime.now()}] Criando {repeat_count} jobs agendados para o endpoint {endpoint}...")

    for i in range(repeat_count):
        # A primeira notificação pode ser enviada imediatamente (ou quase)
        # As subsequentes serão agendadas com o intervalo definido.
        # O tempo para a i-ésima notificação (começando de i=0)
        run_date = datetime.now() + timedelta(seconds=i * interval_seconds)
        notification_index = i + 1 # Índice da notificação (1, 2, ...)

        # Cria um ID único para o job (útil para depuração e gerenciamento)
        # Usa o timestamp para garantir unicidade se várias configs forem salvas rápido
        job_id = f"notif-{endpoint}-{notification_index}-{run_date.timestamp()}"

        # Adiciona o job ao agendador
        scheduler.add_job(
             send_push_notification, # A função a ser executada
             'date', # Tipo de gatilho: 'date' (data e hora específicas)
             run_date=run_date, # Quando executar (agora + offset)
             kwargs={ # Argumentos para a função send_push_notification
                'subscription_info': subscriptions_db[endpoint]['subscription'], # Passa a assinatura salva
                'message_text': message,
                'notification_index': notification_index,
                'total_notifications': repeat_count,
             },
             id=job_id, # ID do job
             replace_existing=True # Se já existir um job com este ID, substitui (útil em alguns cenários, mas com IDs baseados em timestamp e endpoint, deve ser único)
        )
        print(f"[{datetime.now()}] Job '{job_id}' agendado para executar em: {run_date}")


    print(f"[{datetime.now()}] Agendamento concluído. Total de {repeat_count} jobs criados para {endpoint}.")


    # Responde ao cliente que a configuração foi salva (não que as notificações foram enviadas ainda)
    return jsonify({"message": f"Configuração salva para {endpoint} e agendamento inicial criado ({repeat_count} jobs agendados)."}), 201


# --- Lógica para remover assinatura (se o usuário cancelar no navegador) ---
# O frontend (script.js) precisaria detectar quando a assinatura é cancelada
# (ex: pushManager.getSubscription() retorna null) e enviar uma requisição POST
# para este endpoint para informar o servidor para remover a assinatura.
@app.route('/remove-subscription', methods=['POST'])
def remove_subscription():
    if not request.json:
        return jsonify({"message": "Requisição deve ser JSON"}), 415

    # O cliente deve enviar o endpoint da assinatura para identificá-la
    endpoint = request.json.get('endpoint')
    if not endpoint:
        return jsonify({"message": "Endpoint ausente na requisição"}), 400

    if endpoint in subscriptions_db:
        print(f"[{datetime.now()}] Removendo assinatura simulada para endpoint: {endpoint}")
        del subscriptions_db[endpoint]
        # Em produção, removeria do BD persistente

        # Cancela quaisquer agendamentos ativos para este endpoint
        for job in scheduler.get_jobs():
            if hasattr(job.kwargs, 'subscription_info') and job.kwargs['subscription_info'].get('endpoint') == endpoint:
                 print(f"[{datetime.now()}] Removendo job agendado: {job.id}")
                 scheduler.remove_job(job.id)

        return jsonify({"message": "Assinatura removida com sucesso"}), 200
    else:
        print(f"[{datetime.now()}] Tentativa de remover assinatura não encontrada para endpoint: {endpoint}")
        return jsonify({"message": "Assinatura não encontrada"}), 404


# --- Executar o Servidor Flask ---
if __name__ == '__main__':
    # Cria a pasta 'public' se não existir (para colocar os arquivos frontend)
    if not os.path.exists('public'):
        os.makedirs('public')
        print("Criada pasta 'public'. Copie seus arquivos HTML/JS/SW para dentro dela.")

    PORT = 5000 # Porta padrão do Flask

    print("-" * 30)
    print(f"Servidor Flask rodando na porta {PORT}")
    print(f"Sirva os arquivos do frontend na pasta ./public")
    print("Para testar Web Push, você precisa acessar via HTTPS ou localhost.")
    print(f"Acesse no navegador: http://localhost:{PORT} (ou o endereço do seu servidor com HTTPS)")
    print("-" * 30)
    print("NOTA: Assinaturas e agendamentos são em memória neste exemplo e serão perdidos ao reiniciar o servidor.")
    print("APScheduler com MemoryStore NÃO PERSISTE JOBS.")
    print("-" * 30)


    # Para rodar a aplicação Flask:
    # Em produção, use um servidor WSGI como Gunicorn ou uWSGI.
    # Para desenvolvimento local, app.run() é suficiente.
    # Para testar Web Push localmente (precisa de HTTPS):
    # Gere um certificado SSL local (ex: mkcert) e use:
    # context = ('caminho/para/seu/cert.pem', 'caminho/para/sua/key.pem')
    # app.run(debug=True, port=PORT, ssl_context=context)

    # Rodar no modo de debug (útil para desenvolvimento, desative em produção)
    app.run(debug=True, port=PORT)

    # Se o agendador foi iniciado, ele continuará rodando jobs em segundo plano
    # mesmo que o servidor Flask principal esteja ocupado.