#!/bin/bash

# --- Arquivo de Configuração Persistente ---
CONFIG_FILE=".config_dut"

# 1. Lógica para definir ou ler o IP persistente
if [ -f "$CONFIG_FILE" ]; then
    # Se o arquivo existe, carrega a variável DUT_HOST dele
    source "$CONFIG_FILE"
    echo "========================================="
    echo "IP do servidor recuperado: $DUT_HOST"
    read -p "Deseja manter este IP? [S/n]: " KEEP_IP
    KEEP_IP=${KEEP_IP:-S} # Padrão é Sim

    if [[ "$KEEP_IP" =~ ^[Nn] ]]; then
        read -p "Digite o novo IP do servidor (DUT_HOST): " DUT_HOST
        echo "DUT_HOST=\"$DUT_HOST\"" > "$CONFIG_FILE"
        echo "Novo IP salvo permanentemente."
    fi
else
    # Se o arquivo não existe, pergunta e cria
    echo "========================================="
    echo "Nenhum IP configurado anteriormente."
    read -p "Digite o IP do servidor (DUT_HOST) para salvar: " DUT_HOST
    echo "DUT_HOST=\"$DUT_HOST\"" > "$CONFIG_FILE"
    echo "IP salvo em $CONFIG_FILE."
fi

# --- Configurações Fixas e Derivadas ---
DUT_USER="root"
DUT_IFACE="ens18"
# A URL agora é montada dinamicamente usando o IP salvo
URL="https://${DUT_HOST}:8443/video.mkv"
export DUT_PASSWORD="a_senha_do_servidor"

# --- Configurações Interativas da Bateria ---
echo "========================================="
echo "      CONFIGURAÇÃO DA BATERIA DE TESTES"
echo "========================================="
read -p "Digite o nome do servidor (ex: nginx): " SERVER_NAME
read -p "Digite o algoritmo TCP (ex: cubic): " ALGO_NAME

# 2. Lógica para quantidade de repetições
read -p "Digite a quantidade de repetições (Padrão: 10): " REPEAT_COUNT
# Se o usuário der Enter sem digitar nada, define como 10
REPEAT_COUNT=${REPEAT_COUNT:-10}

echo ""
echo "Iniciando bateria de $REPEAT_COUNT testes..."
echo "Alvo: $DUT_HOST | URL: $URL"
echo "Os resultados serão salvos no formato: ${SERVER_NAME}_${ALGO_NAME}_<numero>"
echo "========================================="

for i in $(seq 1 $REPEAT_COUNT)
do
    echo ""
    echo "[*] Executando teste $i de $REPEAT_COUNT..."
    
    # Executa o quicompare usando as variáveis
    quicompare --mono-light \
      --traffic-mode ffmpeg \
      --dut-host $DUT_HOST \
      --dut-user $DUT_USER \
      --dut-iface $DUT_IFACE \
      --port 8443 \
      --url "$URL" \
      --duration 20 \
      --clients 10 \
      --unit mbps \
      --sample-rate 100

    # Pausa curta para garantir I/O
    sleep 1

    # Identifica a pasta mais recente
    LATEST_DIR=$(ls -td -- */ | head -n 1 | sed 's/\///g')

    # Define o novo nome desejado
    NEW_NAME="${SERVER_NAME}_${ALGO_NAME}_${i}"

    # Renomeia a pasta
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

    # Pausa de segurança, exceto na última execução
    if [ "$i" -ne "$REPEAT_COUNT" ]; then
        sleep 2
    fi
done

echo ""
echo "=== BATERIA DE TESTES FINALIZADA ==="
ls -d ${SERVER_NAME}_${ALGO_NAME}_* 2>/dev/null