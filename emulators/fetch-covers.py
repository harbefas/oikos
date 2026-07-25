#!/usr/bin/env python3
"""Baixa capas do libretro-thumbnails por nome direto (sem listar o repo).

Tenta o nome do jogo com variacoes de regiao. Best-effort: o que nao casar
fica sem capa. Guarda em /media/roms/.covers/<system>/<rom-stem>.png
"""
import os, re, urllib.parse, urllib.request

ROMS = os.environ.get("OIKOS_ROMS", "/media/roms")
COVERS = os.path.join(ROMS, ".covers")
BASE = "https://raw.githubusercontent.com/libretro-thumbnails"

REPOS = {
    "ps2": "Sony_-_PlayStation_2",
    "n64": "Nintendo_-_Nintendo_64",
}
EXTS = {"ps2": (".iso", ".chd", ".bin"), "n64": (".n64", ".z64", ".v64")}
REGIONS = ["(USA)", "(Europe)", "(Japan)", "(World)", "(USA, Europe)",
           "(USA) (v2.01)", ""]


def clean(stem):
    # tira (v2.01), (Europe), [!] e afins, mantendo o titulo
    s = re.sub(r"\s*\((?!USA|Europe|Japan|World)[^)]*\)", "", stem)
    s = re.sub(r"\s*\[[^\]]*\]", "", s).strip()
    return s


def try_download(repo, name, dest):
    url = f"{BASE}/{repo}/master/Named_Boxarts/{urllib.parse.quote(name)}.png"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "homelab-hub"})
        data = urllib.request.urlopen(req, timeout=20).read()
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            with open(dest, "wb") as fh:
                fh.write(data)
            return True
    except Exception:
        pass
    return False


def main():
    total = ok = 0
    for system, repo in REPOS.items():
        sysdir = os.path.join(ROMS, system)
        if not os.path.isdir(sysdir):
            continue
        outdir = os.path.join(COVERS, system)
        os.makedirs(outdir, exist_ok=True)
        for f in sorted(os.listdir(sysdir)):
            if not f.lower().endswith(EXTS[system]):
                continue
            total += 1
            stem = os.path.splitext(f)[0]
            dest = os.path.join(outdir, stem + ".png")
            if os.path.exists(dest):
                ok += 1
                continue
            base = clean(stem)
            # tenta: nome exato do arquivo, depois nome limpo + regioes
            candidates = [stem, base] + [f"{base} {r}".strip() for r in REGIONS]
            for cand in dict.fromkeys(candidates):   # sem duplicatas, mantem ordem
                if try_download(repo, cand, dest):
                    ok += 1
                    print(f"[{system}] OK: {stem}  <- {cand}")
                    break
            else:
                print(f"[{system}] sem capa: {stem}")
    print(f"\n{ok}/{total} capas")


if __name__ == "__main__":
    main()
