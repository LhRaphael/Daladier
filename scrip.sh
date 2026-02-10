#!/bin/bash

# --- Configurações Fixas ---
DUT_HOST="192.168.0.102"
DUT_USER="root"
DUT_IFACE="ens18"
URL="https://192.168.0.102:8443/video.mkv"
export DUT_PASSWORD="a_senha_do_servidor"

# --- Configurações Interativas ---
echo "========================================="
echo "      CONFIGURAÇÃO DA BATERIA DE TESTES"
echo "========================================="
read -p "Digite o nome do servidor (ex: nginx): " SERVER_NAME
read -p "Digite o algoritmo TCP (ex: cubic): " ALGO_NAME

echo ""
echo "Iniciando bateria de 9 testes..."
echo "Os resultados serão salvos no formato: ${SERVER_NAME}_${ALGO_NAME}_<numero>"
echo "========================================="

# Loop de 1 a 9
for i in {1..9}
do
    echo ""
    echo "[*] Executando teste $i de 9..."
    
    # 1. Executa o quicompare
    # Ele vai gerar uma pasta no diretório atual (ex: 2023-10-27_15-30-00_quic...)
    quicompare --mono-light \
      --traffic-mode ffmpeg \
      --dut-host $DUT_HOST \
      --dut-user $DUT_USER \
      --dut-iface $DUT_IFACE \
      --port 8443 \
      --url $URL \
      --duration 20 \
      --clients 10 \
      --unit mbps \
      --sample-rate 100

    # Pausa curta para garantir que o sistema de arquivos registrou a pasta
    sleep 1

    # 2. Identifica a pasta mais recente criada no diretório atual
    # ls -td -- */  -> Lista apenas diretórios, ordenados por data (mais recente primeiro)
    # head -n 1     -> Pega apenas o primeiro da lista
    LATEST_DIR=$(ls -td -- */ | head -n 1 | sed 's/\///g')

    # Define o novo nome desejado
    NEW_NAME="${SERVER_NAME}_${ALGO_NAME}_${i}"

    # 3. Renomeia a pasta
    if [ -d "$LATEST_DIR" ]; then
        if [ "$LATEST_DIR" != "$NEW_NAME" ]; then
            mv "$LATEST_DIR" "$NEW_NAME"
            echo "[SUCESSO] Pasta '$LATEST_DIR' renomeada para -> '$NEW_NAME'"
        else
             echo "[AVISO] A pasta já está com o nome correto."
        fi
    else
        echo "[ERRO] Não foi possível encontrar a pasta de resultados gerada."
    fi

    # Pausa de segurança entre testes para limpar conexões TCP
    sleep 2
done

echo ""
echo "=== BATERIA DE TESTES FINALIZADA ==="
ls -d ${SERVER_NAME}_${ALGO_NAME}_*