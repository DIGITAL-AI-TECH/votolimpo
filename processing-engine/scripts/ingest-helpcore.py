#!/usr/bin/env python3
"""
ingest-helpcore.py — Script de ingestão de artigos TXT no PE Help Core.

Lê arquivos .txt de um diretório, agrupa em batches e envia via POST /v1/jobs
ao Processing Engine Help Core. Suporta encodings brasileiros (UTF-8, latin-1).

USO:
    python scripts/ingest-helpcore.py <pasta_txts> [opcoes]

EXEMPLOS:
    # Listar arquivos sem ingerir
    python scripts/ingest-helpcore.py /data/kb_bradesco --dry-run

    # Ingestão completa
    python scripts/ingest-helpcore.py /data/kb_bradesco \\
        --pipeline helpcore-inventory \\
        --batch-size 200 \\
        --pe-url http://localhost:8001 \\
        --api-key hc-dev-api-key

    # Pipeline de quality scoring
    python scripts/ingest-helpcore.py /data/kb_bradesco \\
        --pipeline helpcore-quality-score \\
        --api-key hc-dev-api-key

AUTENTICAÇÃO:
    A chave da API é lida de (em ordem de prioridade):
    1. Argumento --api-key
    2. Variável de ambiente HC_API_KEY
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    print("ERRO: módulo 'requests' não encontrado.")
    print("Instale com: pip install requests")
    sys.exit(1)


# =============================================================================
# CONSTANTES
# =============================================================================

DEFAULT_PIPELINE = "helpcore-inventory"
DEFAULT_BATCH_SIZE = 200
DEFAULT_PE_URL = "http://localhost:8001"
COST_PER_ARTICLE_USD = 0.0006  # estimativa conservadora para gpt-4.1-mini


# =============================================================================
# ENCODING
# =============================================================================

def read_file_safe(path: Path) -> Optional[str]:
    """
    Lê um arquivo de texto com fallback de encoding.
    Tenta utf-8-sig (cobre UTF-8 com e sem BOM), depois latin-1 (nunca levanta UnicodeDecodeError).
    Retorna None se o arquivo estiver vazio ou ilegível.
    """
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            content = path.read_text(encoding=encoding)
            content = content.strip()
            if not content:
                return None
            return content
        except (UnicodeDecodeError, OSError):
            continue
    return None


def count_words(text: str) -> int:
    """Conta palavras simples por split de whitespace."""
    return len(text.split())


# =============================================================================
# PROGRESS
# =============================================================================

def progress_bar(current: int, total: int, width: int = 40) -> str:
    """
    Retorna uma barra de progresso ASCII.
    Ex: [========>           ] 100/500 artigos
    """
    if total == 0:
        return f"[{'=' * width}] {current}/{total} artigos"
    filled = int(width * current / total)
    bar = "=" * filled
    if filled < width:
        bar += ">"
        bar += " " * (width - filled - 1)
    else:
        bar = "=" * width
    return f"[{bar}] {current}/{total} artigos"


# =============================================================================
# HTTP / INGESTÃO
# =============================================================================

def ingest_batch(
    items: list[dict],
    pipeline_id: str,
    pe_url: str,
    api_key: str,
    max_retries: int = 3,
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Envia um batch de itens para POST /v1/jobs.

    Retorna (success, job_id, error_message).
    Faz retry com backoff exponencial (2s, 4s, 8s) apenas em erros 5xx.
    """
    url = f"{pe_url.rstrip('/')}/v1/jobs"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "pipeline_id": pipeline_id,
        "items": items,
        "skip_cache": False,
        "skip_dedup": False,
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)

            if resp.status_code in (200, 201, 202):
                try:
                    data = resp.json()
                    job_id = data.get("id") or data.get("job_id")
                    return True, job_id, None
                except (ValueError, KeyError):
                    return True, None, None

            elif resp.status_code >= 500:
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if attempt < max_retries:
                    wait = 2 ** attempt  # 2s, 4s, 8s
                    print(f"\r  Tentativa {attempt}/{max_retries} falhou ({last_error}). Aguardando {wait}s...", end="", flush=True)
                    time.sleep(wait)
                continue

            elif resp.status_code == 401:
                return False, None, f"Autenticação falhou (HTTP 401). Verifique --api-key ou HC_API_KEY."

            elif resp.status_code == 422:
                return False, None, f"Payload inválido (HTTP 422): {resp.text[:300]}"

            else:
                return False, None, f"HTTP {resp.status_code}: {resp.text[:200]}"

        except requests.exceptions.ConnectionError:
            last_error = f"Conexão recusada em {url}. PE está rodando?"
            if attempt < max_retries:
                wait = 2 ** attempt
                time.sleep(wait)
        except requests.exceptions.Timeout:
            last_error = "Timeout (30s). PE está sobrecarregado?"
            if attempt < max_retries:
                time.sleep(2 ** attempt)
        except Exception as e:
            return False, None, f"Erro inesperado: {e}"

    return False, None, last_error


# =============================================================================
# RELATÓRIO
# =============================================================================

def print_report(total: int, sent: int, errors: int, skipped: int, elapsed: float) -> None:
    """Imprime relatório final em formato de tabela ASCII."""
    cost_est = sent * COST_PER_ARTICLE_USD
    print("\n")
    print("┌─────────────────────────────────────────────────────┐")
    print("│ RELATÓRIO DE INGESTÃO                               │")
    print("├───────────────────────┬─────────────────────────────┤")
    print(f"│ Total encontrado      │ {total:<27} │")
    print(f"│ Enviados              │ {sent:<27} │")
    print(f"│ Erros de ingestão     │ {errors:<27} │")
    print(f"│ Ignorados (vazios)    │ {skipped:<27} │")
    print(f"│ Tempo total           │ {elapsed:.1f}s{'':<23} │")
    print(f"│ Custo estimado        │ ~${cost_est:.4f} ({sent} × ${COST_PER_ARTICLE_USD})    │")
    print("└───────────────────────┴─────────────────────────────┘")

    if errors > 0:
        print(f"\nATENÇÃO: {errors} arquivo(s) com erro de ingestão.")
        print("Verifique os logs acima para detalhes.")


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ingere arquivos TXT no Processing Engine Help Core via POST /v1/jobs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "pasta_txts",
        help="Diretório contendo os arquivos TXT a ingerir (busca recursiva)",
    )
    parser.add_argument(
        "--pipeline",
        default=DEFAULT_PIPELINE,
        help=f"ID do pipeline no PE (padrão: {DEFAULT_PIPELINE})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Tamanho de cada batch de ingestão (padrão: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--pe-url",
        default=DEFAULT_PE_URL,
        help=f"URL base do PE Help Core (padrão: {DEFAULT_PE_URL})",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("HC_API_KEY", ""),
        help="Chave de autenticação do PE (padrão: env HC_API_KEY)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lista arquivos encontrados sem enviar ao PE",
    )
    parser.add_argument(
        "--ext",
        default=".txt",
        help="Extensão dos arquivos a processar (padrão: .txt)",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=10,
        help="Mínimo de palavras para incluir um artigo (padrão: 10)",
    )

    args = parser.parse_args()

    # Validações
    pasta = Path(args.pasta_txts)
    if not pasta.exists():
        print(f"ERRO: Diretório não encontrado: {pasta}", file=sys.stderr)
        return 1
    if not pasta.is_dir():
        print(f"ERRO: Não é um diretório: {pasta}", file=sys.stderr)
        return 1

    if not args.dry_run and not args.api_key:
        print("ERRO: --api-key não fornecida e HC_API_KEY não está definida.", file=sys.stderr)
        print("  Use: --api-key <chave>  ou  export HC_API_KEY=<chave>", file=sys.stderr)
        return 1

    # Descoberta de arquivos
    ext = args.ext if args.ext.startswith(".") else f".{args.ext}"
    files = sorted(pasta.rglob(f"*{ext}"))

    if not files:
        print(f"Nenhum arquivo {ext} encontrado em: {pasta}")
        return 0

    print(f"Encontrados {len(files)} arquivo(s) {ext} em: {pasta}")

    # Modo dry-run
    if args.dry_run:
        print(f"\nMODO DRY-RUN — listando arquivos (sem envio ao PE)\n")
        skipped = 0
        for f in files:
            content = read_file_safe(f)
            if content is None or count_words(content) < args.min_words:
                print(f"  IGNORADO (vazio/curto): {f.name}")
                skipped += 1
            else:
                print(f"  OK: {f.name} ({count_words(content)} palavras)")
        valid = len(files) - skipped
        print(f"\nResumo dry-run: {valid} válidos, {skipped} ignorados")
        print_report(len(files), 0, 0, skipped, 0.0)
        return 0

    # Ingestão real
    print(f"Pipeline: {args.pipeline}")
    print(f"PE URL:   {args.pe_url}")
    print(f"Batch:    {args.batch_size} artigos por requisição")
    print()

    start_time = time.time()
    total = len(files)
    sent = 0
    errors = 0
    skipped = 0
    error_files: list[str] = []

    # Processar em batches
    batch_items: list[dict] = []
    processed = 0

    for file_path in files:
        processed += 1

        # Ler conteúdo
        content = read_file_safe(file_path)
        if content is None or count_words(content) < args.min_words:
            skipped += 1
            print(f"\r{progress_bar(processed, total)}  (ignorados: {skipped})", end="", flush=True)
            continue

        # Construir item
        source_url = f"file://{file_path.stem}"
        item = {
            "content": content,
            "source_url": source_url,
            "metadata": {
                "filename": file_path.name,
                "filepath": str(file_path),
                "word_count": count_words(content),
            },
        }
        batch_items.append(item)

        # Enviar quando batch completo ou último arquivo
        is_last = processed == total
        if len(batch_items) >= args.batch_size or (is_last and batch_items):
            success, job_id, error_msg = ingest_batch(
                items=batch_items,
                pipeline_id=args.pipeline,
                pe_url=args.pe_url,
                api_key=args.api_key,
            )
            if success:
                sent += len(batch_items)
                print(f"\r{progress_bar(processed, total)}  job: {job_id or 'ok'}", end="", flush=True)
            else:
                errors += len(batch_items)
                for item in batch_items:
                    error_files.append(item["metadata"]["filename"])
                print(f"\r{progress_bar(processed, total)}  ERRO batch: {error_msg}", end="", flush=True)
            batch_items = []
        else:
            print(f"\r{progress_bar(processed, total)}", end="", flush=True)

    elapsed = time.time() - start_time

    # Relatório final
    if error_files:
        print(f"\n\nArquivos com erro ({len(error_files)}):")
        for fname in error_files[:20]:
            print(f"  - {fname}")
        if len(error_files) > 20:
            print(f"  ... e mais {len(error_files) - 20} arquivos")

    print_report(total, sent, errors, skipped, elapsed)

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
