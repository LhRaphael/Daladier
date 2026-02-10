#!/bin/bash

# Configurações fixas
DUT_HOST="192.168.0.102"
DUT_USER="root"
DUT_IFACE="ens18"
URL="https://192.168.0.102:8443/video.mkv"
# A senha do servidor (ajuste se necessário)
export DUT_PASSWORD="a_senha_do_servidor"

echo "=== INICIANDO BATERIA DE TESTES ==="

# 1. Teste Atual (O algoritmo que já estiver configurado no servidor)
echo "[*] Rodando teste..."
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

echo "=== FIM DO TESTE ==="