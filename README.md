# QUICompare-mpeg v4.1.5 — README

## 🔥 O que é o QUICompare-mpeg?

O **QUICompare-mpeg v4.1.5** é uma suíte de teste e análise **fractal** e **multifractal** de tráfego MPEG/HTTP/QUIC.  
Ele permite:

- Geração de tráfego ativo com **ffmpeg** (streaming) ou **curl** (HTTP downloads)
- Medição de **vazão** (throughput) e **latência** (curl)
- Estudo de **caudas pesadas**, **dependência de longo alcance** e **multifractalismo**
- Classificação de fluxos em **mice / moderated / chaotic / hard**, inspirada no **ETrap**

---

## 📂 Arquivos principais

- `quicompare_fractal_utils.py` — funções comuns de:
  - extração de séries temporais a partir de PCAP (tshark)
  - agregação por `--sample-rate`
  - coleta com curl
  - Hurst (R/S)
  - madogram fractal dimension
  - Hill estimator
  - alpha tail shape
  - Whittle estimator
  - MFDFA simplificado
  - Lyapunov (indicador de caos)
  - KDE 1D (PDF)
  - classificação ETrap

- `quicompare-mpeg-superlight.py` — modo SUPERLIGHT  
- `quicompare-mpeg-light-mono.py` — modo LIGHT MONO  
- `quicompare-mpeg-light-multi.py` — modo LIGHT MULTI  
- `quicompare-mpeg-mono-plots.py` — modo MONO FULL (com plots)  
- `quicompare-mpeg-multi-plots.py` — modo MULTI FULL (com plots)  
- `quicompare-auto.py` — modo AUTO (orquestra múltiplos modos)  
- `quicompare` — wrapper CLI unificado  
- `ascii_logo.txt` — logo ASCII exibido em todos os modos  

---

## 🧱 Organização das saídas

Cada execução gera uma pasta com timestamp, por exemplo:

- `quicompare-mpeg-superlight-20251118_153000/`
- `quicompare-mpeg-light-mono-20251118_153045/`
- `quicompare-mpeg-mono-plots-20251118_153200/`
- etc.

Dentro de cada uma:

```text
series/   -> séries temporais CSV (throughput, latency, curl_raw, etc.)
pcap/     -> arquivos .pcap (somente quando em modo ffmpeg)
fractal/  -> métricas fractais em JSON (mono/multi, conforme o modo)
plots/    -> gráficos PNG (somente modos *-plots.py)
meta/     -> sumários TXT + JSON (formato B)
logs/     -> espaço reservado para logs futuros
