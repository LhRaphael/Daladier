#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUICompare-mpeg v4.1.5 - utilitários compartilhados
Este arquivo contém:
 - Logo ASCII
 - Progress bar leve (não trava terminal)
 - SSH helpers para DUT
 - Extração de PCAP via tshark
 - Agregação por sample-rate (1, 10, 100, 1000 Hz)
 - Curl high-resolution sampler
 - Métricas fractais (Hurst, madogram, Hill, alfa-tail)
 - MFDFA simplificado
 - Lyapunov exponent
 - KDE para PDFs
 - Classificação ETrap (mice/moderate/chaotic/hard)
"""

import math
import subprocess
import numpy as np
import pandas as pd
import paramiko
import time
from pathlib import Path

# ================================================================
# ASCII LOGO
# ================================================================

# Caso queira ler de "ascii_logo.txt":
# ASCII_LOGO = Path("ascii_logo.txt").read_text(encoding="utf-8")
ASCII_LOGO = r"""
 ██████╗ ██╗   ██╗██╗ ██████╗ ██████╗ ███╗   ███╗██████╗  █████╗ ██████╗ ███████╗
██╔═══██╗██║   ██║██║██╔════╝██╔═══██╗████╗ ████║██╔══██╗██╔══██╗██╔══██╗██╔════╝
██║   ██║██║   ██║██║██║     ██║   ██║██╔████╔██║██████╔╝███████║██████╔╝█████╗  
██║▄▄ ██║██║   ██║██║██║     ██║   ██║██║╚██╔╝██║██╔═══╝ ██╔══██║██╔══██╗██╔══╝  
╚██████╔╝╚██████╔╝██║╚██████╗╚██████╔╝██║ ╚═╝ ██║██║     ██║  ██║██║  ██║███████╗
 ╚══▀▀═╝  ╚═════╝ ╚═╝ ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝

  QUICompare — Active HTTP/1.1 + HTTP/2 + HTTP/3 (QUIC) Load + Mono & Multi fractals Analysis
      © 2025 Professor Daladier Júnior (daladierjr@ifpb.edu.br) - IFPB/Campus Cajazeiras
"""


# ================================================================
# PRINT LOGO
# ================================================================

def print_logo(quiet: bool = False):
    """Imprime o logo ASCII, a não ser que quiet=True."""
    if not quiet:
        print(ASCII_LOGO)


# ================================================================
# PROGRESS BAR — NÃO TRAVA O TERMINAL
# ================================================================

def progress_bar(elapsed: int, total: int, prefix: str = "[PROGRESS]", enabled: bool = True):
    """
    Barra de progresso leve — atualiza somente a cada 2 segundos,
    evitando travar o terminal quando há muitos processos ffmpeg/curl.
    """
    if not enabled:
        return
    if elapsed < 0:
        elapsed = 0
    # Apenas imprime de 2 em 2 segundos
    if elapsed % 2 != 0:
        return

    width = 30
    total = max(total, 1)
    frac = max(0.0, min(1.0, elapsed / float(total)))
    filled = int(width * frac)
    bar = "#" * filled + "-" * (width - filled)
    pct = int(frac * 100)
    print(f"\r{prefix} {elapsed:4d}s |{bar}| {pct:3d}%", end="", flush=True)


# ================================================================
# SUMMARY FORMAT B
# ================================================================

def print_summary(title: str, summary: dict):
    """Imprime o sumário no formato B."""
    print(f"\n===== {title} - SUMMARY =====")
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("==========================================")


# ================================================================
# SSH HELPERS (para DUT)
# ================================================================

def ssh_connect(host, user, password):
    """Abre sessão SSH no DUT."""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=host, username=user, password=password)
    return c


def ssh_exec(c, cmd):
    """Executa comando remoto via SSH."""
    stdin, stdout, stderr = c.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()


def ssh_scp_get(c, remote, local):
    """Faz download de arquivo remoto via SFTP."""
    sftp = c.open_sftp()
    sftp.get(remote, local)
    sftp.close()

# ================================================================
# PCAP -> SÉRIES TEMPORAIS (tshark)
# ================================================================

def extract_timeseries_from_pcap(pcap_path: str):
    """
    Lê um PCAP usando tshark e retorna:
        df_raw: dataframe com colunas (t, len)
        df_s:   agregado por segundo (t_sec, len)
    """
    cmd = [
        "tshark", "-r", pcap_path,
        "-T", "fields",
        "-e", "frame.time_epoch",
        "-e", "frame.len",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"tshark failed: {res.stderr}")
    rows = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        try:
            t = float(parts[0])
            l = int(parts[1])
            rows.append((t, l))
        except ValueError:
            continue
    if not rows:
        raise RuntimeError("No frames parsed from PCAP.")
    df_raw = pd.DataFrame(rows, columns=["t", "len"])
    df_raw["t_sec"] = df_raw["t"].astype(int)
    df_s = df_raw.groupby("t_sec")["len"].sum().reset_index()
    return df_raw, df_s


# ================================================================
# AGREGAÇÃO POR SAMPLE-RATE (1, 10, 100, 1000 Hz)
# ================================================================

def aggregate_with_sample_rate(df_raw: pd.DataFrame, sample_rate: int):
    """
    Agrupa frames em bins temporais conforme sample_rate (amostras por segundo).
    Retorna df_bins com colunas: t_idx, len
    """
    sample_rate = max(1, int(sample_rate))
    df = df_raw.copy()
    # bin = floor(t * sample_rate)
    df["bin"] = (df["t"] * sample_rate).astype(int)
    df_bins = df.groupby("bin")["len"].sum().reset_index()
    df_bins.rename(columns={"bin": "t_idx"}, inplace=True)
    return df_bins


# ================================================================
# CURL -> SÉRIES TEMPORAIS
# ================================================================

def build_timeseries_from_curl(url, samples, interval, unit="kbps", insecure=False):
    """
    Coleta (latência, throughput) usando curl N vezes, com intervalo em segundos.
    Retorna DataFrame com colunas: t_idx, latency, throughput.
    """
    rows = []
    for i in range(samples):
        cmd = ["curl", "-s", "-o", "/dev/null", "-w", "%{time_total} %{speed_download}"]
        if insecure:
            cmd.append("-k")
        cmd.append(url)
        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=max(5, int(interval * 5))
            )
            if res.returncode != 0:
                continue
            parts = res.stdout.strip().split()
            if len(parts) != 2:
                continue
            time_total = float(parts[0])       # segundos
            speed_download = float(parts[1])  # bytes/s
            bits_per_s = speed_download * 8.0
            if unit == "kbps":
                thr = bits_per_s / 1_000.0
            elif unit == "mbps":
                thr = bits_per_s / 1_000_000.0
            elif unit == "gbps":
                thr = bits_per_s / 1_000_000_000.0
            else:
                thr = bits_per_s
            rows.append((i, time_total, thr))
            time.sleep(interval)
        except Exception:
            continue

    if not rows:
        raise RuntimeError("No curl samples collected.")
    return pd.DataFrame(rows, columns=["t_idx", "latency", "throughput"])


# ================================================================
# MÉTRICAS FRACTAIS - HURST (R/S)
# ================================================================

def hurst_rs(series):
    """
    Estima o expoente de Hurst via R/S.
    Requer N >= 30 amostras. Retorna NaN se não houver dados suficientes.
    """
    X = np.array(series, dtype=float)
    N = len(X)
    if N < 30:
        return float("nan")
    cuts = np.floor(np.logspace(1, math.log10(N / 2), 20)).astype(int)
    RS = []
    for c in cuts:
        if c < 10:
            continue
        nb = N // c
        vals = []
        for i in range(nb):
            seg = X[i * c:(i + 1) * c]
            Z = seg - np.mean(seg)
            Y = np.cumsum(Z)
            R = np.max(Y) - np.min(Y)
            S = np.std(seg)
            if S > 0:
                vals.append(R / S)
        if vals:
            RS.append([c, np.mean(vals)])
    if len(RS) < 3:
        return float("nan")
    RS = np.array(RS)
    # slope da reta em log-log
    return float(np.polyfit(np.log(RS[:, 0]), np.log(RS[:, 1]), 1)[0])


# ================================================================
# FD via MADOGRAM
# ================================================================

def madogram_fd(series):
    """
    Dimensão fractal via madograma.
    """
    x = np.array(series, dtype=float)
    if len(x) < 3:
        return float("nan")
    d1 = np.abs(np.diff(x))
    if np.mean(d1) == 0:
        return float("nan")
    v1 = np.mean(d1)
    v2 = np.mean(np.abs(x[2:] - x[:-2])) / 2.0
    if v1 <= 0 or v2 <= 0:
        return float("nan")
    beta = math.log(v2 / v1) / math.log(2.0)
    return float(2.0 - beta)


# ================================================================
# HILL ESTIMATOR & ALFA TAIL SHAPE
# ================================================================

def hill_tail(series):
    """
    Estimador de Hill para cauda pesada.
    Usa ~10% das maiores observações.
    """
    x = np.sort(np.array(series, dtype=float))
    if len(x) < 5:
        return float("nan")
    k = max(5, len(x) // 10)
    xk = x[-k:]
    if len(xk) < 5:
        return float("nan")
    return float(np.mean(np.log(xk) - np.log(xk[0])))


def alpha_tail_shape(series):
    """
    Converte Hill em alfa-tail shape = 1 / Hill.
    """
    h = hill_tail(series)
    if not np.isfinite(h) or h <= 0:
        return float("nan")
    return float(1.0 / h)


# ================================================================
# WHITTLE ESTIMATOR (APROXIMADO)
# ================================================================

def whittle_estimator(series):
    """
    Estimador espectral (Whittle-like) para processos com memória longa.
    Aproximação simples usando FFT.
    """
    X = np.array(series, dtype=float)
    N = len(X)
    if N < 50:
        return float("nan")
    fx = np.fft.rfft(X - np.mean(X))
    S = (np.abs(fx) ** 2) / N
    if len(S) < 3:
        return float("nan")
    f = np.arange(1, len(S))
    try:
        d = -np.polyfit(np.log(f), np.log(S[1:]), 1)[0] / 2.0
        return float(d)
    except Exception:
        return float("nan")
# ================================================================
# MFDFA SIMPLIFICADO (MULTIFRACTALIDADE)
# ================================================================

def simple_mfdfa(series):
    """
    MFDFA simplificado:
      - Calcula Fq(s) para q em {-2, -1, 0, 1, 2}
      - Usa janelas (scales) log-espaçadas
      - Retorna (tau_min, tau_max) como medida da multifractalidade
    """
    X = np.array(series, dtype=float)
    N = len(X)
    if N < 100:
        return float("nan"), float("nan")
    q_list = [-2, -1, 0, 1, 2]
    scales = np.unique(np.floor(np.logspace(1, math.log10(N / 4), 8)).astype(int))
    taus = []
    for q in q_list:
        Fq_vals = []
        valid_scales = []
        for s in scales:
            if s < 5:
                continue
            nb = N // s
            if nb <= 0:
                continue
            seg_vals = []
            for i in range(nb):
                seg = X[i * s:(i + 1) * s]
                seg_vals.append(np.std(seg))
            seg_vals = np.array(seg_vals)
            if seg_vals.size == 0:
                continue
            if q == 0:
                Fq = np.exp(np.mean(np.log(seg_vals + 1e-12)))
            else:
                Fq = (np.mean(seg_vals ** q)) ** (1.0 / q)
            Fq_vals.append(Fq)
            valid_scales.append(s)
        if len(Fq_vals) < 3:
            continue
        tau = np.polyfit(np.log(valid_scales), np.log(Fq_vals), 1)[0]
        taus.append(tau)
    if not taus:
        return float("nan"), float("nan")
    return float(min(taus)), float(max(taus))


# ================================================================
# ESTIMATIVA DE LYAPUNOV (SIMPLIFICADA)
# ================================================================

def estimate_lyapunov(series, emb_dim=2, delay=1, max_iter=10):
    """
    Estimativa simplificada do expoente de Lyapunov.
    Não é “state-of-the-art”, mas serve como indicador qualitativo.
    """
    x = np.array(series, dtype=float)
    N = len(x)
    m = emb_dim
    tau = delay
    if N < (m + max_iter) * tau + 1:
        return float("nan")
    M = N - (m - 1) * tau
    Y = np.empty((M, m))
    for i in range(m):
        Y[:, i] = x[i * tau:i * tau + M]
    eps = 1e-8
    lambdas = []
    for i in range(M - max_iter - 1):
        dists = np.linalg.norm(Y - Y[i], axis=1)
        dists[i] = np.inf
        j = np.argmin(dists)
        d0 = dists[j]
        if not np.isfinite(d0) or d0 < eps:
            continue
        for k in range(1, max_iter):
            if i + k >= M or j + k >= M:
                break
            d = np.linalg.norm(Y[i + k] - Y[j + k])
            if d <= 0:
                continue
            lambdas.append(math.log(d / d0) / k)
    if not lambdas:
        return float("nan")
    return float(np.mean(lambdas))


# ================================================================
# KDE 1D PARA PDF (LATÊNCIA / THROUGHPUT)
# ================================================================

def gaussian_kde_1d(x, num_points=200):
    """
    Kernel Density Estimation 1D via núcleo Gaussiano.
    Retorna:
      grid: pontos no eixo x
      pdf:  valores estimados da densidade
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return np.array([]), np.array([])
    n = x.size
    std = np.std(x)
    if std <= 0:
        grid = np.linspace(x.min() - 1e-9, x.max() + 1e-9, num_points)
        pdf = np.zeros_like(grid)
        mid = num_points // 2
        pdf[mid] = 1.0
        return grid, pdf
    # Banda de Silverman
    h = 1.06 * std * (n ** (-1 / 5))
    grid = np.linspace(x.min(), x.max(), num_points)
    diffs = (grid[:, None] - x[None, :]) / h
    pdf = np.exp(-0.5 * diffs ** 2).sum(axis=1) / (n * h * math.sqrt(2 * math.pi))
    return grid, pdf


# ================================================================
# CLASSIFICAÇÃO ETRAP (Mice / Moderate / Chaotic / Hard)
# ================================================================

def classify_etrap(alpha):
    """
    Classificação ETrap simplificada com base no alfa tail shape.
      - alpha < 1.0   -> "elephant: hard"
      - 1.0 <= alpha < 1.5 -> "elephant: chaotic (WARNING)"
      - 1.5 <= alpha < 2.0 -> "moderated"
      - alpha >= 2.0       -> "mice"
    """
    if alpha is None or not np.isfinite(alpha):
        return "unknown"
    if alpha < 1.0:
        return "elephant: hard"
    elif alpha < 1.5:
        return "elephant: chaotic (WARNING)"
    elif alpha < 2.0:
        return "moderated"
    else:
        return "mice"
