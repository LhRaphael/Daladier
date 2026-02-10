#!/bin/bash

# Configurações fixas
DUT_HOST="192.168.0.102"
DUT_USER="root"
DUT_IFACE="ens18"
URL="https://192.168.0.102:8443/video.mkv"
# A senha do servidor
export DUT_PASSWORD="654123"

echo "=== INICIANDO BATERIA DE TESTES (9 Repetições) ==="

# Inicia o loop de 1 até 9
for i in {1..9}
do
    echo ""
    echo "---------------------------------------------"
    echo "[*] Rodando teste número $i de 9..."
    echo "---------------------------------------------"

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

    echo "[*] Teste $i concluído."
    
    # Pausa de 2 segundos entre execuções (opcional, mas recomendado)
    sleep 2
done

echo ""
echo "=== FIM DA BATERIA DE TESTES ==="