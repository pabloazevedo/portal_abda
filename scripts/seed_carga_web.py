#!/usr/bin/env python3
"""
Carga via interface web (formulários Jinja):
  POST /login → /musicians/new → /patrimonio/new → /patrimonio/{id}/vincular

Orquestra moderna (86) + Coral STAB (100) + 48 instrumentos emprestados
+ mesa de som / impressoras / cadeiras / estantes.
"""
from __future__ import annotations

import re
import sys
import time
from itertools import cycle

import requests

BASE = "http://127.0.0.1:8000"
TAG = "SEED-WEB-CARGA"

FIRST = [
    "Ana", "Bruno", "Carla", "Diego", "Elena", "Felipe", "Gabriela", "Hugo",
    "Isabela", "João", "Karina", "Lucas", "Marina", "Nicolas", "Olivia", "Pedro",
    "Rafaela", "Samuel", "Tatiana", "Vitor", "Amanda", "Bernardo", "Camila", "Daniel",
    "Eduarda", "Fernando", "Giovana", "Henrique", "Ingrid", "José", "Larissa", "Mateus",
    "Natália", "Otávio", "Patrícia", "Ricardo", "Sofia", "Thiago", "Úrsula", "Vinícius",
    "Yasmin", "André", "Beatriz", "Caio", "Débora", "Enzo", "Fernanda", "Gustavo",
]
LAST = [
    "Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Ferreira", "Almeida", "Costa",
    "Gomes", "Martins", "Araújo", "Melo", "Barbosa", "Ribeiro", "Carvalho", "Rocha",
    "Dias", "Nunes", "Moreira", "Cavalcanti", "Pinto", "Teixeira", "Azevedo", "Cardoso",
    "Correia", "Monteiro", "Nascimento", "Lima", "Pereira", "Mendes",
]

# Orquestra completa moderna = 86
# (instrumento_base_id, qtd, seção, chefe_naipe no 1º)
ORQUESTRA = [
    (1, 16, "1º Violino", True),
    (1, 14, "2º Violino", True),
    (2, 11, "Viola", True),
    (3, 8, "Violoncelo", True),
    (4, 6, "Contrabaixo", True),
    (16, 2, "Flauta", True),
    (17, 1, "Piccolo", False),
    (22, 2, "Oboé", True),
    (24, 1, "Corne Inglês", False),
    (26, 2, "Clarinete", True),
    (30, 1, "Clarinete Baixo", False),
    (32, 2, "Fagote", True),
    (33, 1, "Contrafagote", False),
    (45, 4, "Trompa", True),
    (40, 3, "Trompete", True),
    (47, 2, "Trombone", True),
    (49, 1, "Trombone Baixo", False),
    (53, 1, "Tuba", False),
    (58, 1, "Tímpanos", True),
    (67, 1, "Percussão", False),
    (69, 1, "Percussão", False),
    (68, 1, "Percussão", False),
    (62, 1, "Percussão", False),
    (59, 1, "Percussão", False),
    (6, 1, "Harpa", False),
    (89, 1, "Piano", False),
]

# Coral STAB ≥ 100
CORAL = [
    ("soprano", 28),
    ("alto", 26),
    ("tenor", 24),
    ("baixo", 22),
]

# 48 instrumentos de patrimônio a cadastrar e emprestar
# (instrumento_base_id, qtd, fabricante, modelo)
INSTRUMENTOS_PAT = [
    (1, 10, "Yamaha", "V5"),
    (2, 4, "Eastman", "VA305"),
    (3, 4, "Yamaha", "VC5"),
    (4, 3, "Engelhardt", "CC-50"),
    (16, 2, "Yamaha", "YFL-222"),
    (17, 1, "Yamaha", "YPC-32"),
    (22, 2, "Yamaha", "YOB-241"),
    (24, 1, "Fox", "550"),
    (26, 2, "Buffet", "E11"),
    (30, 1, "Yamaha", "YCL-221II"),
    (32, 2, "Fox", "Renard 222"),
    (33, 1, "Fox", "220"),
    (45, 4, "Conn", "8D"),
    (40, 3, "Bach", "TR300"),
    (47, 2, "Conn", "88H"),
    (49, 1, "Yamaha", "YBL-321"),
    (53, 1, "Miraphone", "186"),
    (58, 1, "Adams", "Professional"),
    (6, 1, "Lyon & Healy", "Style 85"),
    (89, 1, "Steinway", "Model B"),
    (35, 1, "Yamaha", "YAS-280"),
]


def check(cond: bool, msg: str, fails: list) -> bool:
    print(("PASS" if cond else "FAIL"), "-", msg)
    if not cond:
        fails.append(msg)
    return cond


def login() -> requests.Session:
    s = requests.Session()
    for i in range(12):
        r = s.post(
            f"{BASE}/login",
            data={"username": "admin", "password": "admin"},
            allow_redirects=False,
            timeout=30,
        )
        if r.status_code == 303:
            return s
        if r.status_code == 429:
            print(f"  rate-limit login, aguardando… ({i})")
            time.sleep(16)
            continue
        time.sleep(2)
    raise SystemExit("Falha no login web")


def person_name(seq: int) -> tuple[str, str]:
    return FIRST[seq % len(FIRST)], LAST[(seq * 7) % len(LAST)]


def celular(seq: int) -> str:
    # 11 dígitos, 3º = 9
    return f"119{80000000 + seq:08d}"


def birth(seq: int) -> str:
    year = 1978 + (seq % 28)
    month = 1 + (seq % 12)
    day = 1 + (seq % 28)
    return f"{year:04d}-{month:02d}-{day:02d}"


def create_musician(
    s: requests.Session,
    *,
    first: str,
    last: str,
    email: str,
    cel: str,
    birth_date: str,
    roles: list[str],
    instrumento_ids: list[int] | None = None,
    voice_type: str | None = None,
    apelido: str | None = None,
) -> int | None:
    data = [
        ("first_name", first),
        ("last_name", last),
        ("apelido", apelido or ""),
        ("celular", cel),
        ("telefone", ""),
        ("email", email),
        ("birth_date", birth_date),
    ]
    for role in roles:
        data.append(("roles", role))
    if voice_type:
        data.append(("voice_type", voice_type))
    for iid in instrumento_ids or []:
        data.append(("instrumento_ids", str(iid)))

    r = s.post(f"{BASE}/musicians/new", data=data, allow_redirects=False, timeout=60)
    if r.status_code != 303:
        snippet = re.sub(r"\s+", " ", r.text)[:240]
        print(f"  ERR musician {email}: {r.status_code} {snippet}")
        return None
    m = re.search(r"/musicians/(\d+)", r.headers.get("Location", ""))
    return int(m.group(1)) if m else None


def create_patrimonio(s: requests.Session, data: dict) -> str | None:
    r = s.post(f"{BASE}/patrimonio/new", data=data, allow_redirects=False, timeout=60)
    if r.status_code != 303:
        snippet = re.sub(r"\s+", " ", r.text)[:240]
        print(f"  ERR patrimonio {data.get('modelo')}: {r.status_code} {snippet}")
        return None
    m = re.search(r"/patrimonio/([0-9a-f-]+)", r.headers.get("Location", ""), re.I)
    return m.group(1) if m else None


def emprestar(s: requests.Session, item_id: str, musician_id: int) -> bool:
    r = s.post(
        f"{BASE}/patrimonio/{item_id}/vincular",
        data={"musician_id": str(musician_id), "observacoes": f"{TAG} empréstimo"},
        allow_redirects=False,
        timeout=60,
    )
    return r.status_code == 303 and "erro=" not in r.headers.get("Location", "")


def main() -> int:
    fails: list[str] = []
    assert sum(q for _, q, _, _ in ORQUESTRA) == 86, sum(q for _, q, _, _ in ORQUESTRA)
    assert sum(q for _, q in CORAL) == 100
    assert sum(q for _, q, _, _ in INSTRUMENTOS_PAT) == 48

    print("=== Login web ===")
    s = login()
    check("portal_session" in s.cookies, "sessão portal_session", fails)

    # smoke form pages
    r = s.get(f"{BASE}/musicians/new", timeout=30)
    check(r.status_code == 200 and 'name="first_name"' in r.text, "form Nova Membro", fails)
    r = s.get(f"{BASE}/patrimonio/new", timeout=30)
    check(r.status_code == 200 and 'name="tipo_item"' in r.text, "form Novo item", fails)

    orch_ids: list[int] = []
    print("\n=== Orquestra moderna (86) via /musicians/new ===")
    seq = 0
    for inst_id, qtd, secao, has_chefe in ORQUESTRA:
        for i in range(qtd):
            seq += 1
            fn, ln = person_name(seq)
            roles = ["musico"]
            if has_chefe and i == 0:
                roles.append("chefe_naipe")
            mid = create_musician(
                s,
                first=fn,
                last=ln,
                email=f"orch.{seq:03d}.{TAG.lower().replace('-', '.')}@abda.local",
                cel=celular(seq),
                birth_date=birth(seq),
                roles=roles,
                instrumento_ids=[inst_id],
                apelido=f"Orquestra · {secao} #{i + 1}",
            )
            if mid:
                orch_ids.append(mid)
            if seq % 20 == 0:
                print(f"  … {seq}/86")
    check(len(orch_ids) == 86, f"orquestra cadastrada ({len(orch_ids)}/86)", fails)

    coral_ids: list[int] = []
    print("\n=== Coral STAB (100) via /musicians/new ===")
    for voice, qtd in CORAL:
        for i in range(qtd):
            seq += 1
            fn, ln = person_name(seq + 50)
            mid = create_musician(
                s,
                first=fn,
                last=ln,
                email=f"coral.{voice}.{i + 1:03d}.{TAG.lower().replace('-', '.')}@abda.local",
                cel=celular(seq),
                birth_date=birth(seq),
                roles=["cantor"],
                voice_type=voice,
                apelido=f"Coral STAB · {voice.title()} #{i + 1}",
            )
            if mid:
                coral_ids.append(mid)
            if len(coral_ids) % 25 == 0:
                print(f"  … {len(coral_ids)}/100")
    check(len(coral_ids) == 100, f"coral STAB cadastrado ({len(coral_ids)}/100)", fails)

    print("\n=== 48 instrumentos + empréstimo via /patrimonio ===")
    inst_items: list[str] = []
    borrowers = cycle(orch_ids)
    for inst_id, qtd, fab, modelo in INSTRUMENTOS_PAT:
        for n in range(qtd):
            pid = create_patrimonio(
                s,
                {
                    "tipo_item": "Instrumento",
                    "fabricante": fab,
                    "modelo": f"{modelo} #{n + 1}",
                    "ano_compra": "2022",
                    "valor_mercado": "2500",
                    "observacoes": TAG,
                    "instrumento_base_id": str(inst_id),
                    "ano_fabricacao": "2020",
                    "avaliacao_condicao": "Bom",
                },
            )
            if not pid:
                continue
            inst_items.append(pid)
            mid = next(borrowers)
            if not emprestar(s, pid, mid):
                fails.append(f"empréstimo falhou {pid}→{mid}")
                print(f"  ERR loan {pid} → {mid}")
            if len(inst_items) % 12 == 0:
                print(f"  … {len(inst_items)}/48")
    check(len(inst_items) == 48, f"instrumentos ({len(inst_items)}/48)", fails)

    print("\n=== Equipamentos de estudo / impressoras / móveis ===")
    # Mesa de som + equipamentos de estudo
    study = [
        ("Eletronico", "Yamaha", "MG16XU Mesa de som", "Estúdio ABDA"),
        ("Eletronico", "KRK", "Rokit 5 Monitor estudo L", "Estúdio ABDA"),
        ("Eletronico", "KRK", "Rokit 5 Monitor estudo R", "Estúdio ABDA"),
        ("Eletronico", "Focusrite", "Scarlett 2i2 Interface", "Estúdio ABDA"),
    ]
    study_ok = 0
    for tipo, fab, modelo, local in study:
        pid = create_patrimonio(
            s,
            {
                "tipo_item": tipo,
                "fabricante": fab,
                "modelo": modelo,
                "ano_compra": "2023",
                "valor_mercado": "1800",
                "observacoes": f"{TAG} equipamento de estudo",
                "descricao_livre": modelo,
                "local_armazenamento": local,
            },
        )
        if pid:
            study_ok += 1
    check(study_ok == 4, f"equipamentos de estudo ({study_ok}/4)", fails)

    printers_ok = 0
    for i in range(4):
        pid = create_patrimonio(
            s,
            {
                "tipo_item": "Eletronico",
                "fabricante": "HP",
                "modelo": f"LaserJet Pro M404dn #{i + 1}",
                "ano_compra": "2024",
                "valor_mercado": "2200",
                "observacoes": f"{TAG} impressora",
                "descricao_livre": "Impressora administrativa",
                "local_armazenamento": "Secretaria" if i < 2 else "Arquivo",
            },
        )
        if pid:
            printers_ok += 1
    check(printers_ok == 4, f"impressoras ({printers_ok}/4)", fails)

    chairs_ok = 0
    print("  cadastrando 200 cadeiras…")
    for i in range(200):
        pid = create_patrimonio(
            s,
            {
                "tipo_item": "Movel",
                "fabricante": "Ortobom",
                "modelo": f"Cadeira coral/orquestra #{i + 1:03d}",
                "ano_compra": "2021",
                "valor_mercado": "180",
                "observacoes": f"{TAG} cadeira",
                "descricao_livre": "Cadeira empilhável sala de ensaio",
                "local_armazenamento": "Sala de ensaio",
            },
        )
        if pid:
            chairs_ok += 1
        if (i + 1) % 50 == 0:
            print(f"  … cadeiras {i + 1}/200")
    check(chairs_ok == 200, f"cadeiras ({chairs_ok}/200)", fails)

    stands_ok = 0
    print("  cadastrando 100 estantes…")
    for i in range(100):
        pid = create_patrimonio(
            s,
            {
                "tipo_item": "Movel",
                "fabricante": "König & Meyer",
                "modelo": f"Estante partitura #{i + 1:03d}",
                "ano_compra": "2021",
                "valor_mercado": "95",
                "observacoes": f"{TAG} estante",
                "descricao_livre": "Estante de partitura dobrável",
                "local_armazenamento": "Sala de ensaio",
            },
        )
        if pid:
            stands_ok += 1
        if (i + 1) % 25 == 0:
            print(f"  … estantes {i + 1}/100")
    check(stands_ok == 100, f"estantes ({stands_ok}/100)", fails)

    print("\n=== Verificação via páginas web ===")
    r = s.get(f"{BASE}/musicians", timeout=30)
    check(r.status_code == 200, "lista membros", fails)
    # stats may appear in page
    r = s.get(f"{BASE}/patrimonio", timeout=30)
    check(r.status_code == 200, "lista patrimônio", fails)

    print("\nSUMMARY", "FAIL" if fails else "ALL PASS", fails)
    print(
        f"created: orch={len(orch_ids)} coral={len(coral_ids)} "
        f"inst={len(inst_items)} study={study_ok} printers={printers_ok} "
        f"chairs={chairs_ok} stands={stands_ok}"
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
