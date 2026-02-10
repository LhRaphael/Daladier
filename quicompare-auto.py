#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUICompare-mpeg v4.1.5 - AUTO

Modo orquestrador:
 - Executa automaticamente um conjunto de modos:
      SUPERLIGHT, LIGHT MONO, LIGHT MULTI, MONO FULL, MULTI FULL
 - Reutiliza os mesmos parâmetros de tráfego (url, duration, clients, unit, sample-rate)
 - Chama os scripts individuais:
      quicompare-mpeg-superlight.py
      quicompare-mpeg-light-mono.py
      quicompare-mpeg-light-multi.py
      quicompare-mpeg-mono-plots.py
      quicompare-mpeg-multi-plots.py
 - Ao final, imprime um sumário dizendo onde estão os summary_*.json
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

from quicompare_fractal_utils import print_logo, print_summary


MODE_TO_SCRIPT = {
    "superlight": "quicompare-mpeg-superlight.py",
    "light-mono": "quicompare-mpeg-light-mono.py",
    "light-multi": "quicompare-mpeg-light-multi.py",
    "mono-full": "quicompare-mpeg-mono-plots.py",
    "multi-full": "quicompare-mpeg-multi-plots.py",
}


def run_mode(base_dir, mode, args_common, extra_args):
    """
    Executa um dos scripts de modo individual.
    Retorna caminho do summary JSON se encontrado.
    """
    script_name = MODE_TO_SCRIPT[mode]
    script_path = (base_dir / script_name).resolve()

    if not script_path.exists():
        print(f"[AUTO] ERRO: Script {script_path} não encontrado. Pulando modo {mode}.", file=sys.stderr)
        return None

    cmd = [sys.executable, str(script_path)] + args_common + extra_args
    print(f"[AUTO] Executando modo {mode}:")
    print("       ", " ".join(cmd))
    rc = subprocess.call(cmd)
    if rc != 0:
        print(f"[AUTO] Modo {mode} terminou com código {rc}.", file=sys.stderr)

    # Tentar localizar o summary mais recente desse modo
    # Cada script cria diretórios quicompare-mpeg-<modo>-<timestamp>/
    pattern_prefix = script_name.replace(".py", "") + "-"
    candidates = [p for p in base_dir.glob(f"{pattern_prefix}*") if p.is_dir()]
    if not candidates:
        print(f"[AUTO] Não encontrei diretório de saída para {mode}.", file=sys.stderr)
        return None

    # pega o mais recente por mtime
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    run_dir = candidates[0]
    meta_dir = run_dir / "meta"
    if not meta_dir.exists():
        print(f"[AUTO] {run_dir} não tem pasta meta/.", file=sys.stderr)
        return None

    summaries = sorted(meta_dir.glob("summary_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not summaries:
        print(f"[AUTO] Não há summary_*.json em {meta_dir}.", file=sys.stderr)
        return None

    latest_summary = summaries[0]
    print(f"[AUTO] Modo {mode} summary: {latest_summary}")
    return latest_summary


def main():
    parser = argparse.ArgumentParser(description="QUICompare-mpeg v4.1.5 AUTO")

    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["superlight", "light-mono", "light-multi", "mono-full", "multi-full", "all"],
        default=["all"],
        help="Modos a executar automaticamente. Use 'all' ou uma lista: superlight light-mono ..."
    )

    parser.add_argument("--traffic-mode", choices=["ffmpeg", "curl"], default="ffmpeg",
                        help="ffmpeg (streaming) ou curl (HTTP).")
    parser.add_argument("--dut-host", help="IP/host do DUT (necessário no modo ffmpeg).")
    parser.add_argument("--dut-user", help="Usuário SSH do DUT (modo ffmpeg).")
    parser.add_argument("--dut-iface", help="Interface de captura no DUT (modo ffmpeg).")
    parser.add_argument("--port", type=int, default=443, help="Porta de tráfego (para filtro do tcpdump/tshark).")

    parser.add_argument("--url", required=True, help="URL de teste (ffmpeg/curl).")
    parser.add_argument("--duration", type=int, required=True, help="Duração do teste (segundos).")
    parser.add_argument("--clients", type=int, default=1, help="Número de clientes ffmpeg simultâneos.")
    parser.add_argument("--unit", choices=["kbps", "mbps", "gbps"], default="kbps",
                        help="Unidade de throughput (kbps/mbps/gbps).")
    parser.add_argument("--sample-rate", type=int, default=1,
                        help="Amostras por segundo (1, 10, 100, 1000). Default = 1.")
    parser.add_argument("--curl-insecure", action="store_true",
                        help="Passa -k para curl (ignora erros de certificado).")

    parser.add_argument("--quiet", action="store_true",
                        help="Não imprimir logo nem mensagens extras (apenas saída dos modos).")
    parser.add_argument("--no-progress", action="store_true",
                        help="Desabilita barra de progresso nos modos internos.")

    args = parser.parse_args()

    print_logo(quiet=args.quiet)

    base_dir = Path(__file__).resolve().parent

    # Traduz "all" em lista completa
    if "all" in args.modes:
        modes_list = ["superlight", "light-mono", "light-multi", "mono-full", "multi-full"]
    else:
        modes_list = [m for m in args.modes if m != "all"]

    if not modes_list:
        print("[AUTO] Nenhum modo válido selecionado.", file=sys.stderr)
        sys.exit(1)

    # Monta argumentos comuns que serão passados aos scripts de modo
    args_common = [
        "--traffic-mode", args.traffic_mode,
        "--url", args.url,
        "--duration", str(args.duration),
        "--clients", str(args.clients),
        "--unit", args.unit,
        "--sample-rate", str(args.sample_rate),
    ]

    if args.traffic_mode == "ffmpeg":
        # Para ffmpeg, precisamos repassar dut-host/user/iface/port
        if not (args.dut_host and args.dut_user and args.dut_iface):
            print("[AUTO] Para traffic-mode=ffmpeg, é necessário informar --dut-host, --dut-user e --dut-iface.",
                  file=sys.stderr)
            sys.exit(1)
        args_common += [
            "--dut-host", args.dut_host,
            "--dut-user", args.dut_user,
            "--dut-iface", args.dut_iface,
            "--port", str(args.port),
        ]

    if args.curl_insecure:
        args_common.append("--curl-insecure")
    if args.quiet:
        args_common.append("--quiet")
    if args.no_progress:
        args_common.append("--no-progress")

    all_summaries = {}

    for m in modes_list:
        sum_json = run_mode(base_dir, m, args_common, [])
        all_summaries[m] = str(sum_json) if sum_json else None

    # Imprime meta-sumário
    meta_summary = {
        "version": "QUICompare AUTO v4.1.5",
        "url": args.url,
        "traffic_mode": args.traffic_mode,
        "duration_seconds": args.duration,
        "clients": args.clients,
        "unit": args.unit,
        "sample_rate": args.sample_rate,
        "modes_executed": modes_list,
        "summaries": all_summaries,
    }

    # Salvar meta-summary em arquivo
    ts = time.strftime("%Y%m%d_%H%M%S")
    auto_dir = base_dir / f"quicompare-auto-{ts}"
    auto_dir.mkdir(exist_ok=True)
    meta_json = auto_dir / f"auto_summary_{ts}.json"
    with open(meta_json, "w") as f:
        json.dump(meta_summary, f, indent=4)

    print_summary("QUICompare AUTO", meta_summary)
    print(f"[AUTO] Meta-summary salvo em: {meta_json}")


if __name__ == "__main__":
    main()
