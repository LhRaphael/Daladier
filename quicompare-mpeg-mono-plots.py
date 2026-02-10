#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUICompare-mpeg v4.1.5 - MONO FULL (com plots)

Modo monofractal completo:
 - Pode usar ffmpeg (streaming) ou curl (HTTP download)
 - Gera séries temporais de vazão e latência
 - Calcula métricas monofractais:
      - Hurst (R/S)
      - Alfa tail shape (Hill)
      - Hill estimator
      - FD via madogram
      - Whittle estimator
      - Classificação ETrap (mice / moderated / chaotic / hard)
 - Gera plots fractais das séries agregadas de vazão/latência:
      - LLCD (log-log complementary distribution)
      - Periodograma
      - ACF
      - Histograma
      - PDF (KDE)
 - Salva sumário formato B + JSON
 - Organiza tudo em pastas por execução: quicompare-mpeg-mono-plots-<timestamp>/
"""

import os
import sys
import time
import json
import argparse
import subprocess
import getpass
import numpy as np
import matplotlib.pyplot as plt

from quicompare_fractal_utils import (
    print_logo,
    progress_bar,
    print_summary,
    ssh_connect,
    ssh_exec,
    ssh_scp_get,
    extract_timeseries_from_pcap,
    aggregate_with_sample_rate,
    build_timeseries_from_curl,
    hurst_rs,
    madogram_fd,
    hill_tail,
    alpha_tail_shape,
    whittle_estimator,
    gaussian_kde_1d,
    classify_etrap,
)


def _acf(series, max_lag=200):
    """ACF simplificada."""
    x = np.array(series, dtype=float)
    x = x - np.mean(x)
    n = len(x)
    if n < 2:
        return np.array([0]), np.array([1.0])
    var = np.var(x)
    if var == 0:
        return np.arange(0, min(max_lag, n)), np.ones(min(max_lag, n))
    corr = np.correlate(x, x, mode="full")
    corr = corr[corr.size // 2:] / (var * np.arange(n, 0, -1))
    lags = np.arange(min(max_lag, n))
    return lags, corr[:len(lags)]


def _periodogram(series, fs=1.0):
    """Periodograma simples via FFT."""
    x = np.array(series, dtype=float)
    n = len(x)
    if n < 2:
        return np.array([0.0]), np.array([0.0])
    x = x - np.mean(x)
    fx = np.fft.rfft(x)
    psd = (np.abs(fx) ** 2) / n
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    return freqs, psd


def _llcd(series):
    """LLCD (log-log complementary distribution)."""
    x = np.array(series, dtype=float)
    x = x[np.isfinite(x)]
    x = x[x > 0]
    if x.size == 0:
        return np.array([]), np.array([])
    x_sorted = np.sort(x)
    n = x_sorted.size
    # tail prob: P(X >= x_i) = (n - i + 1)/n
    ranks = np.arange(1, n + 1)
    tail_prob = (n - ranks + 1) / n
    return x_sorted, tail_prob


def _plot_all_for_series(x, label, unit, plots_dir, ts, sample_rate):
    """
    Gera plots:
      - histograma
      - ACF
      - periodograma
      - LLCD
      - PDF (KDE)
    para a série x.
    """
    x = np.array(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 5:
        return

    # Histograma
    try:
        plt.figure()
        plt.hist(x, bins=50, density=True)
        plt.xlabel(f"{label} [{unit}]")
        plt.ylabel("Density")
        plt.title(f"Histogram of {label}")
        out = os.path.join(plots_dir, f"{label.lower()}_hist_{ts}.png")
        plt.tight_layout()
        plt.savefig(out)
        plt.close()
    except Exception:
        pass

    # ACF
    try:
        lags, ac = _acf(x)
        plt.figure()
        plt.stem(lags, ac, use_line_collection=True)
        plt.xlabel("Lag")
        plt.ylabel("ACF")
        plt.title(f"ACF of {label}")
        out = os.path.join(plots_dir, f"{label.lower()}_acf_{ts}.png")
        plt.tight_layout()
        plt.savefig(out)
        plt.close()
    except Exception:
        pass

    # Periodograma
    try:
        freqs, psd = _periodogram(x, fs=float(sample_rate))
        positive = freqs > 0
        freqs = freqs[positive]
        psd = psd[positive]
        if freqs.size > 0:
            plt.figure()
            plt.loglog(freqs, psd)
            plt.xlabel("Frequency [Hz]")
            plt.ylabel("Power")
            plt.title(f"Periodogram of {label}")
            out = os.path.join(plots_dir, f"{label.lower()}_periodogram_{ts}.png")
            plt.tight_layout()
            plt.savefig(out)
            plt.close()
    except Exception:
        pass

    # LLCD
    try:
        xs, tail = _llcd(x)
        if xs.size > 0:
            plt.figure()
            plt.loglog(xs, tail)
            plt.xlabel(f"{label} [{unit}]")
            plt.ylabel("P(X >= x)")
            plt.title(f"LLCD of {label}")
            out = os.path.join(plots_dir, f"{label.lower()}_llcd_{ts}.png")
            plt.tight_layout()
            plt.savefig(out)
            plt.close()
    except Exception:
        pass

    # PDF via KDE
    try:
        grid, pdf = gaussian_kde_1d(x)
        if grid.size > 0:
            plt.figure()
            plt.plot(grid, pdf)
            plt.xlabel(f"{label} [{unit}]")
            plt.ylabel("PDF (KDE)")
            plt.title(f"PDF (KDE) of {label}")
            out = os.path.join(plots_dir, f"{label.lower()}_pdf_{ts}.png")
            plt.tight_layout()
            plt.savefig(out)
            plt.close()
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="QUICompare-mpeg v4.1.5 MONO FULL (plots)")

    parser.add_argument("--traffic-mode", choices=["ffmpeg", "curl"], default="ffmpeg",
                        help="Modo de tráfego: ffmpeg (streaming) ou curl (HTTP).")
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
                        help="Usar -k no curl (ignora erros de certificado).")
    parser.add_argument("--quiet", action="store_true",
                        help="Não imprimir logo nem mensagens extras.")
    parser.add_argument("--no-progress", action="store_true",
                        help="Desabilita barra de progresso.")

    args = parser.parse_args()

    # -------------------------------------------------------------
    # Logo
    # -------------------------------------------------------------
    print_logo(quiet=args.quiet)

    # -------------------------------------------------------------
    # Diretórios da execução (um por run)
    # -------------------------------------------------------------
    ts = time.strftime("%Y%m%d_%H%M%S")
    script_name = os.path.basename(__file__).replace(".py", "")
    run_dir = f"{script_name}-{ts}"

    series_dir = os.path.join(run_dir, "series")
    pcap_dir = os.path.join(run_dir, "pcap")
    meta_dir = os.path.join(run_dir, "meta")
    logs_dir = os.path.join(run_dir, "logs")
    fractal_dir = os.path.join(run_dir, "fractal")
    plots_dir = os.path.join(run_dir, "plots")

    for d in [series_dir, pcap_dir, meta_dir, logs_dir, fractal_dir, plots_dir]:
        os.makedirs(d, exist_ok=True)

    show_progress = (not args.no_progress) and (not args.quiet)

    # -------------------------------------------------------------
    # Coleta de dados
    # -------------------------------------------------------------
    if args.traffic_mode == "ffmpeg":
        # ---------------------- MODO FFMPEG --------------------------------
        if not (args.dut_host and args.dut_user and args.dut_iface):
            print("ERROR: --dut-host, --dut-user e --dut-iface são obrigatórios no modo ffmpeg.", file=sys.stderr)
            sys.exit(1)

        if not args.quiet:
            print("🔐 Senha SSH do DUT:")
        password = getpass.getpass("> ")

        ssh = ssh_connect(args.dut_host, args.dut_user, password)

        remote_pcap = f"/tmp/quicompare_mono_full_{ts}.pcap"
        local_pcap = os.path.join(pcap_dir, os.path.basename(remote_pcap))

        # inicia tcpdump no DUT
        cmd_tcpdump = (
            f"nohup tcpdump -i {args.dut_iface} "
            f"'(tcp port {args.port} or udp port {args.port})' "
            f"-w {remote_pcap} > /dev/null 2>&1 & echo $!"
        )
        out, err = ssh_exec(ssh, cmd_tcpdump)
        if err and not args.quiet:
            print(f"[WARN] tcpdump stderr: {err}")
        pid = out.strip()

        # inicia clientes ffmpeg locais
        procs = []
        for _ in range(args.clients):
            p_cli = subprocess.Popen(
                [
                    "ffmpeg",
                    "-loglevel", "error",
                    "-threads", "1",
                    "-nostdin",
                    "-i", args.url,
                    "-t", str(args.duration),
                    "-f", "null", "-",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            procs.append(p_cli)

        start = time.time()
        while True:
            elapsed = int(time.time() - start)
            if elapsed > args.duration:
                elapsed = args.duration
            progress_bar(elapsed, args.duration, prefix="[MONO FULL]", enabled=show_progress)
            if elapsed >= args.duration:
                break
            time.sleep(1)
        if show_progress:
            print()

        # espera ffmpeg terminar
        for p_cli in procs:
            p_cli.wait()

        # mata tcpdump no DUT
        if pid:
            ssh_exec(ssh, f"kill {pid}")
        # traz o pcap
        ssh_scp_get(ssh, remote_pcap, local_pcap)

        # extrai séries temporais
        df_raw, _ = extract_timeseries_from_pcap(local_pcap)
        df_bins = aggregate_with_sample_rate(df_raw, args.sample_rate)

        # converte len -> bits/s e escala para unidade desejada
        factor = {"kbps": 8 / 1_000, "mbps": 8 / 1_000_000, "gbps": 8 / 1_000_000_000}[args.unit]
        df_bins["throughput"] = df_bins["len"] * factor

        throughput_csv = os.path.join(series_dir, f"throughput_{ts}.csv")
        df_bins[["t_idx", "throughput"]].to_csv(throughput_csv, index=False)

        # latência inexistente nesse modo -> CSV vazio
        latency_csv = os.path.join(series_dir, f"latency_{ts}.csv")
        with open(latency_csv, "w") as f:
            f.write("t_idx,latency\n")

        thr = df_bins["throughput"].values
        lat = None

    else:
        # ---------------------- MODO CURL ----------------------------------
        samples = max(1, args.duration * max(1, args.sample_rate))
        interval = 1.0 / max(1, args.sample_rate)

        from quicompare_fractal_utils import build_timeseries_from_curl  # já importado no topo, redundante mas seguro

        df_curl = build_timeseries_from_curl(
            url=args.url,
            samples=samples,
            interval=interval,
            unit=args.unit,
            insecure=args.curl_insecure,
        )

        raw_csv = os.path.join(series_dir, f"raw_curl_{ts}.csv")
        df_curl.to_csv(raw_csv, index=False)

        throughput_csv = os.path.join(series_dir, f"throughput_{ts}.csv")
        df_curl[["t_idx", "throughput"]].to_csv(throughput_csv, index=False)

        latency_csv = os.path.join(series_dir, f"latency_{ts}.csv")
        df_curl[["t_idx", "latency"]].to_csv(latency_csv, index=False)

        thr = df_curl["throughput"].values
        lat = df_curl["latency"].values

    if len(thr) == 0:
        raise RuntimeError("No throughput samples collected.")

    # -------------------------------------------------------------
    # Métricas fractais monofractais
    # -------------------------------------------------------------
    H = hurst_rs(thr)
    alpha = alpha_tail_shape(thr)
    hill = hill_tail(thr)
    fd_mado = madogram_fd(thr)
    whittle = whittle_estimator(thr)
    cls = classify_etrap(alpha)
    avg = float(np.mean(thr))

    fractal_json = os.path.join(fractal_dir, f"fractal_metrics_{ts}.json")
    fractal_metrics = {
        "hurst_rs": H,
        "alpha_tail_shape": alpha,
        "hill_estimator": hill,
        "fd_madogram": fd_mado,
        "whittle_estimator": whittle,
        "classification": cls,
    }
    with open(fractal_json, "w") as f:
        json.dump(fractal_metrics, f, indent=4)

    # -------------------------------------------------------------
    # Plots fractais para throughput/latência
    # -------------------------------------------------------------
    _plot_all_for_series(thr, label="Throughput", unit=args.unit, plots_dir=plots_dir, ts=ts,
                         sample_rate=args.sample_rate)
    if lat is not None:
        _plot_all_for_series(lat, label="Latency", unit="s", plots_dir=plots_dir, ts=ts,
                             sample_rate=args.sample_rate)

    # -------------------------------------------------------------
    # Sumário (formato B + JSON)
    # -------------------------------------------------------------
    summary = {
        "version": "QUICompare MONO FULL v4.1.5",
        "traffic_mode": args.traffic_mode,
        "target_url": args.url,
        "dut_host": args.dut_host,
        "dut_iface": args.dut_iface,
        "port": args.port,
        "duration_seconds": args.duration,
        "clients": args.clients,
        "unit": args.unit,
        "sample_rate": args.sample_rate,
        "avg_throughput": avg,
        "hurst_rs": H,
        "alpha_tail_shape": alpha,
        "hill_estimator": hill,
        "fd_madogram": fd_mado,
        "whittle_estimator": whittle,
        "flow_classification": cls,
        "throughput_series_csv": throughput_csv,
        "latency_series_csv": latency_csv,
        "fractal_metrics_json": fractal_json,
        "plots_dir": plots_dir,
        "run_dir": run_dir,
    }

    txt = os.path.join(meta_dir, f"summary_{ts}.txt")
    js = os.path.join(meta_dir, f"summary_{ts}.json")

    with open(txt, "w") as f:
        f.write("--- QUICompare MONO FULL ---\n")
        for k, v in summary.items():
            f.write(f"{k}: {v}\n")

    with open(js, "w") as f:
        json.dump(summary, f, indent=4)

    summary["saved_to"] = js
    print_summary("QUICompare MONO FULL", summary)


if __name__ == "__main__":
    main()
