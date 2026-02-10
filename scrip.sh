#!/bin/bash

# --- Configurações Fixas ---
DUT_HOST="192.168.0.102"
DUT_USER="root"
DUT_IFACE="ens18"
URL="https://192.168.0.102:8443/video.mkv"
export DUT_PASSWORD="a_senha_do_servidor"

# --- Configurações Interativas (Inputs do Usuário) ---
echo "=== CONFIGURAÇÃO DO TESTE ==="
read -p "Digite o nome do servidor (ex: nginx, apache): " SERVER_NAME
read -p "Digite o algoritmo TCP usado (ex: cubic, bbr): " ALGO_NAME

# Cria uma pasta para salvar os arquivos (opcional, mas recomendado)
mkdir -p resultados

echo ""
echo "=== INICIANDO BATERIA DE 9 TESTES ==="
echo "Arquivos serão salvos como: resultados/${SERVER_NAME}_${ALGO_NAME}_<numero>.log"

for i in {1..9}
do
    # Constrói o nome do arquivo dinamicamente
    # Exemplo: resultados/nginx_bbr_1.log
    FILE_NAME="resultados/${SERVER_NAME}_${ALGO_NAME}_${i}.log"

    echo ""
    echo "---------------------------------------------"
    echo "[*] Rodando teste $i de 9..."
    echo "[*] Salvando em: $FILE_NAME"
    echo "---------------------------------------------"

    # Executa o comando e redireciona (>) a saída para o arquivo
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
      --sample-rate 100 > "$FILE_NAME" 2>&1

    # Nota: O '2>&1' acima garante que erros também sejam salvos no arquivo.
    # Se o 'quicompare' tiver uma flag própria de output (ex: --output), 
    # substitua o '> "$FILE_NAME"' pela flag correspondente.

    echo "[OK] Teste $i finalizado."
    
    # Pequena pausa para garantir o fechamento de sockets
    sleep 2
done

echo ""
echo "=== BATERIA FINALIZADA ==="
echo "Verifique a pasta 'resultados' para ver os arquivos."