#!/usr/bin/env python3
"""
Help Bradesco — Script de ingestao dos artigos TXT no Processing Engine.

Uso:
  # Dry-run com amostra de 100 artigos (apenas parser, sem enviar ao PE)
  python scripts/help_bradesco_ingest.py --dry-run --sample 100 /path/to/help-bradesco/conteudos

  # Enviar amostra de 100 artigos ao PE
  python scripts/help_bradesco_ingest.py --sample 100 /path/to/help-bradesco/conteudos

  # Enviar todos os artigos ao PE
  python scripts/help_bradesco_ingest.py /path/to/help-bradesco/conteudos

Env vars:
  PE_URL       — URL do Processing Engine (default: https://processing-engine.digital-ai.tech)
  PE_API_KEY   — API key do PE
  PIPELINE_ID  — UUID do pipeline helpcore-inventory (buscar via GET /v1/pipelines)
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None

SKIP_CLASSIFICACOES = {"EMPTY_OR_ORPHAN", "MEDIA_OR_ATTACHMENT"}
BATCH_SIZE = 200


def parse_txt(filepath: Path) -> dict | None:
    """Parse um arquivo TXT do Help Bradesco e retorna um item para o PE."""
    try:
        content = filepath.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            content = filepath.read_text(encoding="cp1252")
        except UnicodeDecodeError:
            content = filepath.read_text(encoding="latin-1")

    if "===== CONTEUDO =====" not in content:
        return None

    # Split nas 3 secoes
    parts = content.split("===== LINKS =====")
    header_section = parts[0] if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    parts2 = rest.split("===== CONTEUDO =====")
    links_section = parts2[0] if parts2 else ""
    body = parts2[1].strip() if len(parts2) > 1 else ""

    # Parse header
    meta = {}
    for line in header_section.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip().lower()] = val.strip()

    classificacao = meta.get("classificacao", "UNKNOWN")
    if classificacao in SKIP_CLASSIFICACOES:
        return None

    iid = meta.get("iid", "0").split(",")[0]
    area = meta.get("area", "desconhecida")
    titulo = meta.get("titulo", "")
    subtitulo = meta.get("subtitulo", "")

    # Conteudo enriquecido para o LLM
    full_content = f"AREA: {area}\nTITULO: {titulo}\nSUBTITULO: {subtitulo}\n\n{body}"

    # Links internos
    links = [l.strip() for l in links_section.splitlines() if l.strip()]

    return {
        "source_url": f"bradesco-help://{area}/{iid}",
        "content": full_content[:50000],
        "content_type": "text/plain",
        "metadata": {
            "area": area,
            "lista": meta.get("lista", ""),
            "titulo": titulo,
            "subtitulo": subtitulo,
            "nivel3": meta.get("nivel3", ""),
            "iid": iid,
            "modified": meta.get("modified", ""),
            "classificacao": classificacao,
            "help_name": meta.get("help", ""),
            "list_url": meta.get("list_url", ""),
            "links": links,
            "source_filename": filepath.name,
            "source_area_path": f"{area}/{meta.get('lista', '')}/{titulo}",
        },
    }


def send_batch(items: list, batch_num: int, pe_url: str, api_key: str, pipeline_id: str) -> dict:
    """Envia um batch de items ao PE via POST /v1/jobs."""
    if httpx is None:
        raise ImportError("httpx nao instalado. Instale com: pip install httpx")

    payload = {
        "pipeline_id": pipeline_id,
        "items": items,
        "skip_dedup": True,
        "skip_cache": True,
        "idempotency_key": f"help-bradesco-batch-{batch_num:05d}",
        "metadata": {"batch_num": batch_num, "source": "help-bradesco-ingest"},
    }
    r = httpx.post(
        f"{pe_url}/v1/jobs",
        json=payload,
        headers={"x-api-key": api_key},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Ingestao dos artigos Help Bradesco no PE")
    parser.add_argument("conteudos_dir", help="Diretorio raiz com os TXTs (ex: /workspace/help-bradesco/conteudos)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas parseia, nao envia ao PE")
    parser.add_argument("--sample", type=int, default=0, help="Processar apenas N artigos (0 = todos)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help=f"Items por batch (default: {BATCH_SIZE})")
    parser.add_argument("--output", type=str, default="", help="Arquivo JSON para salvar resultado do dry-run")
    args = parser.parse_args()

    base = Path(args.conteudos_dir)
    if not base.exists():
        print(f"ERRO: Diretorio nao encontrado: {base}")
        sys.exit(1)

    pe_url = os.environ.get("PE_URL", "https://processing-engine.digital-ai.tech")
    api_key = os.environ.get("PE_API_KEY", "")
    pipeline_id = os.environ.get("PIPELINE_ID", "")

    if not args.dry_run and (not api_key or not pipeline_id):
        print("ERRO: PE_API_KEY e PIPELINE_ID sao obrigatorios (exceto em --dry-run)")
        sys.exit(1)

    # Coletar todos os TXT
    all_txts = sorted(base.rglob("*.txt"))
    print(f"Total de arquivos TXT encontrados: {len(all_txts)}")

    if args.sample > 0:
        # Amostra diversificada: pegar de areas diferentes
        by_area: dict[str, list] = {}
        for txt in all_txts:
            area = txt.parent.parent.name if txt.parent.parent != base else txt.parent.name
            by_area.setdefault(area, []).append(txt)

        sampled = []
        per_area = max(1, args.sample // len(by_area))
        for area_name, area_txts in sorted(by_area.items()):
            sampled.extend(area_txts[:per_area])
            if len(sampled) >= args.sample:
                break
        # Completar se necessario
        if len(sampled) < args.sample:
            remaining = [t for t in all_txts if t not in sampled]
            sampled.extend(remaining[: args.sample - len(sampled)])
        all_txts = sampled[:args.sample]
        print(f"Amostra selecionada: {len(all_txts)} artigos de {len(by_area)} areas")

    # Parser
    parsed_items = []
    skipped = {"no_content": 0, "classification": 0, "parse_error": 0}
    stats_by_class: dict[str, int] = {}
    stats_by_area: dict[str, int] = {}

    for txt_path in all_txts:
        try:
            item = parse_txt(txt_path)
        except Exception as e:
            skipped["parse_error"] += 1
            print(f"  ERRO parsing {txt_path.name}: {e}")
            continue

        if item is None:
            # Verificar motivo do skip
            try:
                raw = txt_path.read_text(encoding="utf-8-sig", errors="replace")
                if "===== CONTEUDO =====" not in raw:
                    skipped["no_content"] += 1
                else:
                    skipped["classification"] += 1
            except Exception:
                skipped["parse_error"] += 1
            continue

        parsed_items.append(item)
        cls = item["metadata"]["classificacao"]
        area = item["metadata"]["area"]
        stats_by_class[cls] = stats_by_class.get(cls, 0) + 1
        stats_by_area[area] = stats_by_area.get(area, 0) + 1

    print(f"\n=== Resultado do Parser ===")
    print(f"Parseados com sucesso: {len(parsed_items)}")
    print(f"Skipped (sem CONTEUDO): {skipped['no_content']}")
    print(f"Skipped (classificacao): {skipped['classification']}")
    print(f"Skipped (erro parser): {skipped['parse_error']}")
    print(f"\nPor classificacao:")
    for cls, count in sorted(stats_by_class.items(), key=lambda x: -x[1]):
        print(f"  {cls}: {count}")
    print(f"\nPor area:")
    for area, count in sorted(stats_by_area.items(), key=lambda x: -x[1]):
        print(f"  {area}: {count}")

    # Estimar custo
    total_chars = sum(len(item["content"]) for item in parsed_items)
    est_tokens_in = total_chars / 4  # ~4 chars por token
    est_tokens_out = len(parsed_items) * 200  # ~200 tokens output por artigo
    est_cost = (est_tokens_in * 0.40 / 1_000_000) + (est_tokens_out * 1.60 / 1_000_000)
    print(f"\nEstimativa de custo LLM (gpt-4.1-mini):")
    print(f"  Tokens input: ~{int(est_tokens_in):,}")
    print(f"  Tokens output: ~{int(est_tokens_out):,}")
    print(f"  Custo estimado: ~${est_cost:.2f}")

    if args.dry_run:
        print(f"\n[DRY-RUN] Nenhum dado enviado ao PE.")
        if args.output:
            output_data = {
                "total_parsed": len(parsed_items),
                "skipped": skipped,
                "stats_by_class": stats_by_class,
                "stats_by_area": stats_by_area,
                "cost_estimate_usd": round(est_cost, 2),
                "sample_items": [
                    {
                        "source_url": item["source_url"],
                        "content_preview": item["content"][:500],
                        "metadata": item["metadata"],
                    }
                    for item in parsed_items[:5]
                ],
            }
            Path(args.output).write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
            print(f"Resultado salvo em: {args.output}")
        return

    # Enviar ao PE em batches
    print(f"\nEnviando {len(parsed_items)} artigos ao PE em batches de {args.batch_size}...")
    batch, batch_num = [], 1
    results = []
    errors = []

    for i, item in enumerate(parsed_items):
        batch.append(item)
        if len(batch) >= args.batch_size:
            try:
                result = send_batch(batch, batch_num, pe_url, api_key, pipeline_id)
                results.append(result)
                print(f"  Batch {batch_num}: job_id={result.get('job_id', result.get('id', '?'))}, items={len(batch)}")
            except Exception as e:
                errors.append({"batch": batch_num, "error": str(e)})
                print(f"  Batch {batch_num}: ERRO — {e}")
            batch, batch_num = [], batch_num + 1
            time.sleep(0.5)  # rate limiting gentil

    if batch:
        try:
            result = send_batch(batch, batch_num, pe_url, api_key, pipeline_id)
            results.append(result)
            print(f"  Batch {batch_num}: job_id={result.get('job_id', result.get('id', '?'))}, items={len(batch)}")
        except Exception as e:
            errors.append({"batch": batch_num, "error": str(e)})
            print(f"  Batch {batch_num}: ERRO — {e}")

    print(f"\n=== Resultado da Ingestao ===")
    print(f"Batches enviados: {len(results)}")
    print(f"Batches com erro: {len(errors)}")
    print(f"Jobs criados: {[r.get('job_id', r.get('id', '?')) for r in results]}")

    if errors:
        print(f"\nErros:")
        for e in errors:
            print(f"  Batch {e['batch']}: {e['error']}")


if __name__ == "__main__":
    main()
