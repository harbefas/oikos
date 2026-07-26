#!/usr/bin/env python3
"""Console Hub: controle + lancador de jogos/apps pelo navegador do celular.

Estende o padserver. Alem de servir os gamepads virtuais (uinput), oferece:
  - aba Jogos: grid com capas, toca -> lanca na TV
  - aba Apps:  Kodi, Jellyfin, Stremio -> lanca na TV
  - aba Controle: os dois gamepads (P1 / ?p=2 P2)

Lanca via `swaymsg exec` na sessao Sway. Sem app no celular.
"""
import hashlib, json, os, socket, struct, subprocess, urllib.parse, urllib.request, zlib
from urllib.parse import urlparse, parse_qs

MPV_SOCK = "/tmp/mpv.sock"
# Paths and the optional auth token are env-configurable so you don't have to edit
# code. Defaults are English; override any of them in the systemd unit or shell.
MEDIA = os.environ.get("OIKOS_MEDIA", "/media")
# Auth (all optional; unset both = open on LAN):
#   OIKOS_PASSWORD -> a login screen with a password field
#   OIKOS_TOKEN    -> a URL token (?t=), handy for a bookmark, no form
# Either one, once accepted, is remembered in the `oikos` cookie.
TOKEN = os.environ.get("OIKOS_TOKEN", "")
PASSWORD = os.environ.get("OIKOS_PASSWORD", "")
PWHASH = hashlib.sha256(PASSWORD.encode()).hexdigest() if PASSWORD else ""
STATE = {"cover": None, "mkind": None}   # do que esta tocando (setado no /api/play)


def mpv_cmd(command):
    """Manda um comando pro mpv via socket IPC; retorna o campo data ou None."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(MPV_SOCK)
        s.send((json.dumps({"command": command}) + "\n").encode())
        for line in s.recv(65536).decode().splitlines():
            obj = json.loads(line)
            if "data" in obj or obj.get("error") == "success":
                s.close()
                return obj.get("data")
        s.close()
    except Exception:
        pass
    return None


def mpv_now_playing():
    if not os.path.exists(MPV_SOCK):
        return None
    return {
        "title": mpv_cmd(["get_property", "media-title"]),
        "pos": mpv_cmd(["get_property", "time-pos"]) or 0,
        "duration": mpv_cmd(["get_property", "duration"]) or 0,
        "paused": bool(mpv_cmd(["get_property", "pause"])),
        "subdelay": mpv_cmd(["get_property", "sub-delay"]) or 0,
        "audiodelay": mpv_cmd(["get_property", "audio-delay"]) or 0,
    }


MPV_ACTIONS = {
    "playpause": ["cycle", "pause"],
    "fwd":       ["seek", 10],
    "back":      ["seek", -10],
    "fwd60":     ["seek", 60],
    "back60":    ["seek", -60],
    "volup":     ["add", "volume", 5],
    "voldown":   ["add", "volume", -5],
    "sub":       ["cycle", "sub"],
    "audio":     ["cycle", "audio"],
    "next":      ["playlist-next"],
    "prev":      ["playlist-prev"],
    # sincronia de legenda/audio (dessincronizacao e comum)
    "subdelay+":   ["add", "sub-delay", 0.1],
    "subdelay-":   ["add", "sub-delay", -0.1],
    "subdelay0":   ["set", "sub-delay", 0],
    "audiodelay+": ["add", "audio-delay", 0.1],
    "audiodelay-": ["add", "audio-delay", -0.1],
    "audiodelay0": ["set", "audio-delay", 0],
}


def tv_frame():
    """Captura o frame atual da sessao Sway (grim), JPEG reduzido pra caber no wifi."""
    env = {**os.environ, "WAYLAND_DISPLAY": "wayland-1",
           "XDG_RUNTIME_DIR": "/run/user/1000"}
    try:
        r = subprocess.run(["grim", "-s", "0.5", "-t", "jpeg", "-q", "55", "-"],
                           capture_output=True, env=env, timeout=5)
        return r.stdout if r.returncode == 0 else b""
    except Exception:
        return b""


def list_resume(n=12):
    """Filmes com posicao salva pelo mpv (--save-position-on-quit) = continuar de onde parou.
    O mpv nomeia cada watch_later por md5(path).upper(); casamos pela biblioteca, o que
    tambem devolve o poster do Jellyfin. OIKOS_HOME = home do usuario que roda o mpv."""
    home = os.environ.get("OIKOS_HOME", os.path.expanduser("~"))
    wl = os.path.join(home, ".local/state/mpv/watch_later")
    if not os.path.isdir(wl):
        wl = os.path.join(home, ".config/mpv/watch_later")
    if not os.path.isdir(wl):
        return []
    files = set(os.listdir(wl))
    try:
        movies = list_movies()
    except Exception:
        movies = []
    out = []
    for m in movies:
        p = m.get("path")
        if not p:
            continue
        h = hashlib.md5(p.encode()).hexdigest().upper()
        if h not in files:
            continue
        fp = os.path.join(wl, h)
        pos = 0.0
        try:
            for line in open(fp, encoding="utf-8", errors="ignore"):
                if line.startswith("start="):
                    pos = float(line.split("=", 1)[1])
                    break
        except (OSError, ValueError):
            continue
        out.append({"name": m.get("name") or os.path.basename(p), "path": p,
                    "pos": pos, "cover": m.get("cover"), "type": "movie",
                    "mtime": os.path.getmtime(fp)})
    out.sort(key=lambda x: x["mtime"], reverse=True)
    return out[:n]
MUSIC = os.environ.get("OIKOS_MUSIC", f"{MEDIA}/music")


def list_albums():
    albums = []
    if not os.path.isdir(MUSIC):
        return albums
    for artist in sorted(os.listdir(MUSIC)):
        apath = os.path.join(MUSIC, artist)
        if not os.path.isdir(apath):
            continue
        # cada subpasta = album; se nao houver, o proprio artista vira "album"
        subs = [d for d in sorted(os.listdir(apath))
                if os.path.isdir(os.path.join(apath, d))]
        targets = [(f"{artist} — {d}", os.path.join(apath, d)) for d in subs] or [(artist, apath)]
        for name, path in targets:
            has_audio = any(f.lower().endswith((".flac", ".mp3", ".m4a", ".ogg", ".opus"))
                            for f in os.listdir(path))
            if not has_audio:
                continue
            cover = next((os.path.join(path, c) for c in
                          ("cover.jpg", "folder.jpg", "cover.png", "front.jpg")
                          if os.path.exists(os.path.join(path, c))), None)
            albums.append({"name": name, "path": path,
                           "cover": f"/acover/{urllib.parse.quote(path)}" if cover else None})
    return albums
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from evdev import UInput, AbsInfo, ecodes as e


def make_icon(size=512):
    """PNG do icone (Python puro): fundo escuro + gamepad estilizado simples."""
    bg = (15, 17, 21)       # #0f1115
    fg = (79, 140, 255)     # #4f8cff
    px = bytearray()
    cx, cy = size / 2, size / 2
    for y in range(size):
        px.append(0)        # filtro de linha
        for x in range(size):
            # forma tosca de gamepad: elipse larga central
            dx = (x - cx) / (size * 0.32)
            dy = (y - cy) / (size * 0.20)
            px += bytes(fg if dx * dx + dy * dy <= 1 else bg)
    idat = zlib.compress(bytes(px), 9)

    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


ICON_PNG = make_icon()
MANIFEST = json.dumps({
    "name": "Homelab", "short_name": "Homelab",
    "start_url": "/", "display": "fullscreen", "orientation": "landscape",
    "background_color": "#0f1115", "theme_color": "#0f1115",
    "icons": [
        {"src": "/icon.png", "sizes": "512x512", "type": "image/png"},
        {"src": "/icon.png", "sizes": "192x192", "type": "image/png"},
    ],
}).encode()

PORT = 8100
AMAX = 32767
ROMS = os.environ.get("OIKOS_ROMS", f"{MEDIA}/roms")
COVERS = f"{ROMS}/.covers"

# --- sistemas e como lancar ---
SYSTEMS = {
    "ps2": {"label": "PS2",  "exts": (".iso", ".chd", ".bin"), "cmd": "run-ps2"},
    "n64": {"label": "N64",  "exts": (".n64", ".z64", ".v64"),  "cmd": "run-n64"},
}
APPS = [
    {"id": "kodi",     "label": "Kodi",     "icon": "📺", "cmd": "kodi"},
    {"id": "jellyfin",  "label": "Filmes", "icon": "🎬",
     "cmd": "librewolf --kiosk http://localhost:8096"},
    {"id": "navidrome", "label": "Música", "icon": "🎵",
     "cmd": "librewolf --kiosk http://localhost:4533"},
]

# --- gamepads (identicos ao padserver de 2 jogadores) ---
BUTTONS = {
    "b": e.BTN_SOUTH, "a": e.BTN_EAST, "x": e.BTN_NORTH, "y": e.BTN_WEST,
    "l": e.BTN_TL, "r": e.BTN_TR, "z": e.BTN_TL2, "r2": e.BTN_TR2,
    "select": e.BTN_SELECT, "start": e.BTN_START, "l3": e.BTN_THUMBL,
    "r3": e.BTN_THUMBR, "up": e.BTN_DPAD_UP, "down": e.BTN_DPAD_DOWN,
    "left": e.BTN_DPAD_LEFT, "right": e.BTN_DPAD_RIGHT,
}
ai = AbsInfo(value=0, min=-AMAX, max=AMAX, fuzz=0, flat=512, resolution=0)
CAPS = {e.EV_KEY: list(BUTTONS.values()),
        e.EV_ABS: [(e.ABS_X, ai), (e.ABS_Y, ai), (e.ABS_RX, ai), (e.ABS_RY, ai)]}
def _mkpad():
    """Cria um gamepad uinput; None se /dev/uinput nao estiver acessivel
    (sem grupo input / sem regra udev). Assim o hub ainda sobe pra midia/UI."""
    try:
        return UInput(CAPS, name="Homelab Virtual Gamepad",
                      vendor=0x1234, product=0x5678, version=1)
    except Exception as ex:
        print(f"[warn] uinput indisponivel ({ex}); gamepad off (midia/UI seguem). "
              f"Pra ligar: usuario no grupo 'input' + regra udev em /dev/uinput.")
        return None


PADS = {1: _mkpad(), 2: _mkpad()}


# --- helpers de lancamento ---
def swaysock():
    out = subprocess.run(["pgrep", "-x", "sway"], capture_output=True, text=True).stdout.split()
    xdg = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
    return f"{xdg}/sway-ipc.1000.{out[0]}.sock" if out else ""


def sway_exec(cmd):
    """Lanca cmd na sessao grafica. Suporta Hyprland (hyprctl) e Sway (swaymsg)."""
    env = {**os.environ,
           "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY", "wayland-1"),
           "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")}
    dn = subprocess.DEVNULL
    if subprocess.run(["pgrep", "-x", "Hyprland"], capture_output=True).returncode == 0:
        subprocess.run(["hyprctl", "dispatch", "exec", cmd], env=env, stdout=dn, stderr=dn)
    else:
        env["SWAYSOCK"] = swaysock()
        subprocess.run(["swaymsg", "exec", cmd], env=env, stdout=dn, stderr=dn)


def list_games():
    games = []
    for sysname, conf in SYSTEMS.items():
        d = os.path.join(ROMS, sysname)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(conf["exts"]):
                continue
            stem = os.path.splitext(f)[0]
            cover = os.path.join(COVERS, sysname, stem + ".png")
            games.append({
                "system": sysname, "label": conf["label"],
                "name": stem, "path": os.path.join(d, f),
                "cover": f"/cover/{sysname}/{urllib.parse.quote(stem)}" if os.path.exists(cover) else None,
            })
    return games


def running_game():
    # match por comm (substring, sem -x): cobre binario nativo, flatpak e AppImage
    # (ex.: PCSX2 via AppImage aparece como "pcsx2.AppImage", nao "pcsx2-qt").
    for pat, name in (("mpv", "mpv"), ("pcsx2", "pcsx2-qt"), ("retroarch", "retroarch")):
        if subprocess.run(["pgrep", pat], capture_output=True).returncode == 0:
            return name
    return None


def list_recent(n=12):
    """Itens adicionados/modificados mais recentemente (jogos + filmes)."""
    items = []
    for g in list_games():
        try:
            items.append({**g, "type": "game", "mtime": os.path.getmtime(g["path"])})
        except OSError:
            pass
    try:
        for m in list_movies():
            if m.get("path") and os.path.exists(m["path"]):
                items.append({**m, "type": "movie", "mtime": os.path.getmtime(m["path"])})
    except Exception:
        pass
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items[:n]


# --- biblioteca de midia via API do Jellyfin ---
JF = os.environ.get("OIKOS_JF", "http://localhost:8096")
# a key pode vir direta (OIKOS_JF_KEY) ou de um arquivo (OIKOS_JF_KEY_FILE)
try:
    JF_KEY = (os.environ.get("OIKOS_JF_KEY", "").strip()
              or open(os.environ.get("OIKOS_JF_KEY_FILE",
                                     "/srv/jellyfin/console-hub.key")).read().strip())
except Exception:
    JF_KEY = ""


def jf_get(path):
    sep = "&" if "?" in path else "?"
    url = f"{JF}{path}{sep}api_key={JF_KEY}"
    return json.load(urllib.request.urlopen(url, timeout=15))


def list_movies():
    d = jf_get("/Items?IncludeItemTypes=Movie&Recursive=true&SortBy=SortName&Fields=Path")
    return [{"name": m["Name"], "path": m.get("Path"),
             "cover": f"/jf/{m['Id']}" if "Primary" in m.get("ImageTags", {}) else None}
            for m in d["Items"] if m.get("Path")]


def list_series():
    d = jf_get("/Items?IncludeItemTypes=Series&Recursive=true&SortBy=SortName")
    return [{"name": s["Name"], "id": s["Id"],
             "cover": f"/jf/{s['Id']}" if "Primary" in s.get("ImageTags", {}) else None}
            for s in d["Items"]]


RADARR = "http://localhost:7878/api/v3"
try:
    RADARR_KEY = os.environ.get("OIKOS_RADARR_KEY", "").strip()
    if not RADARR_KEY:
        _f = os.environ.get("OIKOS_RADARR_KEY_FILE",
                            "/home/nfvelten/docker/arr-stack/radarr/config.xml")
        RADARR_KEY = open(_f).read().split("<ApiKey>")[1].split("</ApiKey>")[0]
except Exception:
    RADARR_KEY = ""


def radarr(path, data=None, method=None):
    r = urllib.request.Request(RADARR + path,
        data=json.dumps(data).encode() if data else None,
        headers={"X-Api-Key": RADARR_KEY, "Content-Type": "application/json"},
        method=method or ("POST" if data else "GET"))
    b = urllib.request.urlopen(r, timeout=30).read()
    return json.loads(b) if b else None


def search_movies(term):
    hits = radarr("/movie/lookup?term=" + urllib.parse.quote(term))
    out = []
    for m in hits[:20]:
        poster = next((i["remoteUrl"] for i in m.get("images", [])
                       if i.get("coverType") == "poster"), None)
        out.append({"title": m["title"], "year": m.get("year"),
                    "tmdbId": m.get("tmdbId"),
                    "poster": f"/img?u={urllib.parse.quote(poster)}" if poster else None,
                    "have": m.get("id", 0) > 0})
    return out


def request_movie(tmdb_id):
    hits = radarr(f"/movie/lookup/tmdb?tmdbId={tmdb_id}")
    m = hits[0] if isinstance(hits, list) else hits
    qp = radarr("/qualityprofile")[0]["id"]
    root = radarr("/rootfolder")[0]["path"]   # o que estiver configurado, nao hardcode
    body = {
        "title": m["title"], "tmdbId": m["tmdbId"], "year": m.get("year"),
        "titleSlug": m["titleSlug"], "images": m.get("images", []),
        "qualityProfileId": qp, "rootFolderPath": root,
        "monitored": True, "minimumAvailability": "released",
        "addOptions": {"searchForMovie": True},
    }
    return radarr("/movie", body)


SONARR = "http://localhost:8989/api/v3"
try:
    SONARR_KEY = os.environ.get("OIKOS_SONARR_KEY", "").strip()
    if not SONARR_KEY and os.environ.get("OIKOS_SONARR_KEY_FILE"):
        SONARR_KEY = open(os.environ["OIKOS_SONARR_KEY_FILE"]).read() \
            .split("<ApiKey>")[1].split("</ApiKey>")[0]
    if not SONARR_KEY:
        SONARR_KEY = subprocess.run(
            ["docker", "exec", "sonarr", "sh", "-c",
             'grep -o "<ApiKey>[^<]*" /config/config.xml'],
            capture_output=True, text=True).stdout.replace("<ApiKey>", "").strip()
except Exception:
    SONARR_KEY = ""


def sonarr(path, data=None, method=None):
    r = urllib.request.Request(SONARR + path,
        data=json.dumps(data).encode() if data else None,
        headers={"X-Api-Key": SONARR_KEY, "Content-Type": "application/json"},
        method=method or ("POST" if data else "GET"))
    b = urllib.request.urlopen(r, timeout=30).read()
    return json.loads(b) if b else None


def search_series(term):
    hits = sonarr("/series/lookup?term=" + urllib.parse.quote(term))
    out = []
    for m in hits[:20]:
        poster = next((i["remoteUrl"] for i in m.get("images", [])
                       if i.get("coverType") == "poster"), None)
        out.append({"title": m["title"], "year": m.get("year"),
                    "tvdbId": m.get("tvdbId"),
                    "poster": f"/img?u={urllib.parse.quote(poster)}" if poster else None,
                    "have": m.get("id", 0) > 0})
    return out


def request_series(tvdb_id):
    hits = sonarr(f"/series/lookup?term=tvdb:{tvdb_id}")
    m = hits[0]
    qp = sonarr("/qualityprofile")[0]["id"]
    # monitora so a 1a temporada (piloto). Baixar a serie inteira sem querer
    # ja custou 56GB de The Wire. Se gostar, pede o resto pelo Sonarr.
    seasons = [{"seasonNumber": s["seasonNumber"],
                "monitored": s["seasonNumber"] == 1}
               for s in m.get("seasons", [])]
    body = {
        "title": m["title"], "tvdbId": m["tvdbId"], "titleSlug": m["titleSlug"],
        "images": m.get("images", []), "seasons": seasons,
        "qualityProfileId": qp, "rootFolderPath": sonarr("/rootfolder")[0]["path"],
        "monitored": True, "seasonFolder": True,
        "addOptions": {"searchForMissingEpisodes": True, "monitor": "firstSeason"},
    }
    return sonarr("/series", body)


def get_downloads():
    """Agrega a fila de Radarr + Sonarr: o que esta baixando, com progresso."""
    out = []
    for label, fn in (("filme", radarr), ("série", sonarr)):
        try:
            q = fn("/queue?pageSize=50")
            for r in q.get("records", []):
                size = r.get("size", 0) or 1
                left = r.get("sizeleft", 0)
                out.append({
                    "title": r.get("title", "?"),
                    "kind": label,
                    "percent": round(100 * (1 - left / size), 1),
                    "status": r.get("status", ""),
                    "eta": r.get("timeleft", ""),
                })
        except Exception:
            pass
    return out


def list_episodes(sid):
    d = jf_get(f"/Items?ParentId={sid}&IncludeItemTypes=Episode&Recursive=true"
               f"&SortBy=ParentIndexNumber,IndexNumber&Fields=Path")
    out = []
    for ep in d["Items"]:
        if not ep.get("Path"):
            continue
        s = ep.get("ParentIndexNumber", 0)
        n = ep.get("IndexNumber", 0)
        out.append({"name": f"S{s:02d}E{n:02d}  {ep['Name']}", "path": ep["Path"]})
    return out


PAGE = r"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<title>Homelab</title>
<link rel=manifest href=/manifest.json>
<meta name=theme-color content=#0f1115>
<meta name=mobile-web-app-capable content=yes>
<meta name=apple-mobile-web-app-capable content=yes>
<meta name=apple-mobile-web-app-status-bar-style content=black-translucent>
<meta name=apple-mobile-web-app-title content=Homelab>
<link rel=apple-touch-icon href=/icon.png>
<link rel=preconnect href=https://fonts.googleapis.com>
<link rel=preconnect href=https://fonts.gstatic.com crossorigin>
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,500;0,600;1,500&family=Inter:wght@400;500;600;700&display=swap" rel=stylesheet>
<style>
/* ===== paleta Yerba Mate — Tererê (dia) / Cimarrão (noite), igual ao site ===== */
:root{
  --bg:#fbf1c7; --bg2:#f0e4b8; --surface:#ebdfb0; --ui:#ddd2a0; --ui-2:#cbbe8a;
  --tx:#3c3836; --tx-2:#504945; --tx-3:#7c6f64;
  --accent:#c88010; --accent-2:#79740e; --p2:#9d0006;
  --border:#00000018; --bar:#fbf1c7d8; --overlay:#fbf1c7f2; --nm-grad:#f0e4b8ee;
  --serif:'EB Garamond',Georgia,serif; --sans:'Inter',system-ui,sans-serif;
}
:root[data-theme=dark]{
  --bg:#282d1c; --bg2:#2f3521; --surface:#363c26; --ui:#4f5b4a; --ui-2:#5a6a54;
  --tx:#dce0d9; --tx-2:#a8b09f; --tx-3:#7a8573;
  --accent:#d4a033; --accent-2:#7a9e38; --p2:#c25d44;
  --border:#ffffff16; --bar:#282d1cd8; --overlay:#282d1cf2; --nm-grad:#1d2114ee;
}
*{box-sizing:border-box;-webkit-user-select:none;user-select:none;
  -webkit-touch-callout:none;-webkit-tap-highlight-color:transparent;margin:0}
html,body{height:100%;color:#eef1f6;overflow:hidden;
  font:500 15px -apple-system,system-ui,"Segoe UI",Roboto,sans-serif;overscroll-behavior:none;
  background:#0c0e13;
  background-image:radial-gradient(1200px 600px at 80% -10%,#1a2740 0%,transparent 55%),
                   radial-gradient(900px 500px at -10% 110%,#241a33 0%,transparent 50%)}
#app{position:fixed;inset:0 0 64px 0;overflow-y:auto;-webkit-overflow-scrolling:touch}
.view{display:none;min-height:100%}
.view.on{display:block}
/* tab bar translucida (glass) */
#tabs{position:fixed;bottom:0;left:0;right:0;height:64px;display:flex;
  background:#12151cd8;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  border-top:1px solid #ffffff12;padding-bottom:env(safe-area-inset-bottom)}
#tabs button{flex:1;background:0;border:0;color:#7d8595;font:inherit;font-size:11px;font-weight:600;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;letter-spacing:.02em}
#tabs button .i{font-size:21px}
#tabs button.on{color:#5b9bff}
/* jogos */
#games{padding:16px 14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(108px,1fr));gap:14px}
.card{background:#161a22;border-radius:14px;overflow:hidden;position:relative;
  aspect-ratio:3/4;display:flex;flex-direction:column;border:1px solid #ffffff0d}
.card:active{border-color:#5b9bff}
.card .cov{flex:1;background:#0f1218 center/cover no-repeat;display:flex;
  align-items:center;justify-content:center;font-size:34px;color:#3a4150}
.card .nm{padding:8px 9px;font-size:11.5px;font-weight:600;line-height:1.25;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  position:absolute;bottom:0;left:0;right:0;
  background:linear-gradient(transparent,#0d0f14ee 45%);padding-top:24px}
.card .sys{position:absolute;top:6px;right:6px;background:#0009;backdrop-filter:blur(4px);
  border-radius:6px;font-size:8.5px;font-weight:700;padding:3px 6px;letter-spacing:.06em}
.sec{padding:18px 15px 6px;font-size:12px;font-weight:700;color:#6b7280;
  letter-spacing:.1em;text-transform:uppercase}
/* faixa horizontal de recentes / continuar */
#recent,#resume{display:flex;gap:12px;overflow-x:auto;padding:4px 14px 6px;scroll-snap-type:x proximity;
  -webkit-overflow-scrolling:touch;scrollbar-width:none}
#recent::-webkit-scrollbar,#resume::-webkit-scrollbar{display:none}
.rcard{flex:0 0 128px;scroll-snap-align:start;background:#161a22;border-radius:14px;
  overflow:hidden;position:relative;aspect-ratio:3/4;border:1px solid #ffffff0d;
  box-shadow:0 4px 16px #0006;transition:transform .13s}
.rcard:active{transform:scale(.95)}
.rcard .rc{position:absolute;inset:0;background:#0f1218 center/cover no-repeat;
  display:flex;align-items:center;justify-content:center;font-size:36px;color:#3a4150}
.rcard .rn{position:absolute;bottom:0;left:0;right:0;padding:20px 9px 8px;font-size:11.5px;
  font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  background:linear-gradient(transparent,#0d0f14f2 50%)}
.rcard .rt{position:absolute;top:7px;left:7px;background:#5b9bffcc;backdrop-filter:blur(4px);
  color:#fff;font-size:8.5px;font-weight:700;padding:3px 7px;border-radius:6px;letter-spacing:.05em}
/* barra de busca (filme/serie) */
.searchbar{position:sticky;top:0;z-index:5;display:flex;gap:8px;padding:12px 14px;
  background:#0f1115;border-bottom:1px solid #1e232c}
.searchbar input{flex:1;background:#1b1f28;border:1px solid #2b323d;border-radius:10px;
  color:#e8e8e8;font:inherit;font-size:15px;padding:11px 14px;outline:none}
.searchbar input:focus{border-color:#4f8cff}
.searchbar button{background:#2b303c;border:0;color:#e8e8e8;border-radius:10px;width:44px;font-size:16px}
/* botao e painel de downloads */
#dlbtn{position:fixed;top:10px;right:12px;z-index:15;width:44px;height:44px;border-radius:50%;
  background:#1b2130;border:1px solid #2a3550;color:#e8e8e8;font-size:20px;display:none}
#dlbtn.on{display:block}
#dlbadge{position:absolute;top:-3px;right:-3px;background:#4f8cff;color:#fff;font-size:11px;
  min-width:18px;height:18px;border-radius:9px;padding:0 4px;line-height:18px;font-weight:700}
#dllist{position:fixed;inset:0;background:#0f1115ee;z-index:25;display:none;flex-direction:column}
#dllist.on{display:flex}
#dls{overflow-y:auto;padding:10px 14px 24px}
.dl{padding:12px 4px;border-bottom:1px solid #1e232c}
.dl .dh{display:flex;justify-content:space-between;font-size:13px;margin-bottom:7px;gap:10px}
.dl .dh .t{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dl .dh .p{opacity:.7;flex:none}
.dl .bar{height:6px;background:#2b303c;border-radius:99px;overflow:hidden}
.dl .bar>i{display:block;height:100%;background:#4f8cff}
.poster .badge{position:absolute;top:6px;left:6px;background:#3d5a3daa;color:#cfe;
  font-size:9px;padding:2px 6px;border-radius:5px;letter-spacing:.03em}
.poster .req{position:absolute;top:6px;right:6px;background:#4f8cffcc;color:#fff;
  font-size:9px;padding:2px 6px;border-radius:5px}
/* toast */
#toast{position:fixed;bottom:78px;left:50%;transform:translateX(-50%) translateY(20px);
  background:#222833;color:#e8e8e8;padding:12px 20px;border-radius:10px;font-size:14px;
  box-shadow:0 6px 24px #0009;opacity:0;pointer-events:none;transition:.25s;z-index:30;max-width:88vw;text-align:center}
#toast.on{opacity:1;transform:translateX(-50%) translateY(0)}
/* grid de posteres (filmes/series) */
.pgrid{padding:16px 14px;display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:14px}
.poster{background:#161a22;border-radius:14px;overflow:hidden;position:relative;
  aspect-ratio:2/3;border:1px solid #ffffff0d;display:flex;flex-direction:column}
.poster:active{border-color:#5b9bff}
.poster .pc{flex:1;background:#0f1218 center/cover no-repeat;display:flex;
  align-items:center;justify-content:center;font-size:30px;color:#3a4150}
.poster .pn{padding:8px 8px;font-size:11px;font-weight:600;line-height:1.25;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  position:absolute;bottom:0;left:0;right:0;
  background:linear-gradient(transparent,#0d0f14ee 45%);padding-top:24px}
/* modal episodios */
#eplist{position:fixed;inset:0;background:#0f1115ee;z-index:20;display:none;flex-direction:column}
#eplist.on{display:flex}
#ephead{display:flex;align-items:center;justify-content:space-between;padding:14px;
  border-bottom:1px solid #262b36;font-size:16px;font-weight:600}
#ephead button{background:#2b303c;border:0;color:#e8e8e8;width:34px;height:34px;border-radius:50%;font-size:16px}
#eps{overflow-y:auto;padding:8px 14px 20px}
.ep{padding:14px 12px;border-bottom:1px solid #1e232c;font-size:14px}
.ep:active{background:#1b2130}
/* apps */
#apps{padding:16px;display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:14px}
.app{background:#1b1f28;border:1px solid #262b36;border-radius:12px;padding:22px 14px;
  display:flex;flex-direction:column;align-items:center;gap:10px;font-size:14px}
.app:active{border-color:#4f8cff}
.app .i{font-size:38px}
/* mini-player fixo acima da tab bar (o que esta tocando/rodando) */
#miniplayer{position:fixed;left:0;right:0;bottom:62px;z-index:12;display:none;
  align-items:center;gap:10px;padding:8px 12px;background:#161a22;
  border-top:1px solid #242a35;box-shadow:0 -4px 20px #0006}
#miniplayer.on{display:flex;animation:mpup .3s cubic-bezier(.2,.7,.3,1)}
@keyframes mpup{from{transform:translateY(100%)}to{transform:none}}
#mp-art{width:42px;height:42px;border-radius:7px;object-fit:cover;flex:none;background:#222}
#mp-info{flex:1;min-width:0}
#mp-title{font-size:13px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#mp-sub{font-size:11px;opacity:.55;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#mp-pp{background:#4f8cff;border:0;color:#fff;width:40px;height:40px;border-radius:50%;font-size:17px;flex:none}
#mp-stop{background:#2b303c;border:0;color:#e8e8e8;width:36px;height:36px;border-radius:50%;font-size:14px;flex:none}
/* no modo controle (pad) o mini-player some (ja tem o painel completo) */
body[data-mode=media] #miniplayer,body[data-inpad=1] #miniplayer{display:none!important}
/* controle: reaproveita o gamepad; escondido ate a aba */
#pad{position:fixed;inset:0;background:#111318;display:none}
#pad.on{display:block}
/* --- estilos do gamepad (copiado do padserver) --- */
#pad *{touch-action:none}
.p{position:absolute}
#ls{left:2vw;top:calc(20vh - 30px);width:44vh;height:44vh;max-width:300px;max-height:300px;
  border-radius:50%;background:radial-gradient(circle,#232833,#1a1e26);border:2px solid #333a47}
#lk{width:40%;height:40%;background:#4f8cff;box-shadow:0 3px 14px #0009}
#rs{right:24vw;bottom:2vh;width:28vh;height:28vh;max-width:185px;max-height:185px;
  border-radius:50%;background:radial-gradient(circle,#2a2618,#201d14);border:2px solid #46402a}
#rk{width:42%;height:42%;background:#e8c33a;box-shadow:0 3px 14px #0009}
.knob{position:absolute;left:50%;top:50%;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none}
#face{right:2vw;top:calc(17vh - 30px);display:grid;grid-template-columns:repeat(3,13vh);grid-template-rows:repeat(3,13vh);gap:1.1vh}
#face button{border-radius:50%;font-size:3.7vh;background:#333a47}
#face button[data-b=a]{background:#3d5a3d}#face button[data-b=b]{background:#5a3d3d}
#dpad{position:absolute;left:26vw;bottom:2vh;display:grid;grid-template-columns:repeat(3,8.5vh);grid-template-rows:repeat(3,8.5vh);gap:.6vh}
#dpad button{font-size:2.8vh;border-radius:1.5vh;opacity:.9}
#tl{left:2vw;top:2vh;display:flex;gap:1.2vh}#tr{right:2vw;top:2vh}
.trig{width:16vh;height:9vh;font-size:2.8vh;border-radius:2.4vh}#bz{background:#7a4de8}
#mid{left:50%;top:3vh;transform:translateX(-50%);display:flex;gap:1.4vh;align-items:center}
#mid button[data-b]{width:16vh;height:6vh;font-size:2vh;border-radius:3vh}
#tomenu{width:6vh;height:6vh;font-size:3vh;border-radius:50%;background:#3a4150!important;opacity:.75}
#pnum{font-size:2.2vh;font-weight:800;padding:0 1.5vh;opacity:.5}
#pad button{border:0;color:#e6e6e6;font:inherit;font-weight:700;background:#2b303c}
#pad button:active,#pad button.on{background:#4f8cff;color:#fff}
.lbl{position:absolute;bottom:.6vh;left:50%;transform:translateX(-50%);font-size:1.3vh;opacity:.35}
body[data-p="2"] #pnum{color:#e8552d}
/* controle de midia (mpv) — substitui o gamepad quando toca filme/musica.
   usa vmin (escala pela MENOR dimensao) + clamp: fica bom em paisagem e retrato */
#mediactl{position:absolute;inset:0;display:none;flex-direction:column;
  align-items:center;justify-content:center;
  gap:clamp(14px,3vmin,28px);padding:clamp(16px,4vmin,40px) 5vw clamp(16px,3vmin,32px)}
body[data-mode=media] #mediactl{display:flex}
body[data-mode=media] #pad>.p,
body[data-mode=media] #dpad{display:none}   /* esconde TODO o gamepad (incl. d-pad) */
.mc-corner{position:absolute!important;top:clamp(10px,3vmin,22px);left:4vw;
  width:clamp(40px,9vmin,60px);height:clamp(40px,9vmin,60px);
  border-radius:50%;font-size:clamp(18px,4vmin,26px);background:#2b303c!important;opacity:.8}
/* imagem completa (contain): filme (2:3) e capa de album (1:1) aparecem inteiros.
   altura fixa responsiva, largura acompanha a proporcao real */
#mc-art{height:clamp(130px,30vh,340px);width:auto;max-width:86vw;object-fit:contain;
  border-radius:12px;flex:none;box-shadow:0 8px 30px #0007;display:none}
#mc-art.on{display:block}
/* em paisagem a altura da tela e curta: limita pela altura */
@media (orientation:landscape){#mc-art{height:clamp(90px,38vh,220px)}}
#mc-title{font-size:clamp(17px,4.2vmin,30px);font-weight:600;text-align:center;
  max-width:92vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding:0 8vw}
#mc-time{display:flex;align-items:center;gap:3vw;width:min(560px,86vw);
  font-size:clamp(12px,2.6vmin,17px);opacity:.8}
#mc-bar{flex:1;height:clamp(5px,1.1vmin,9px);background:#2b303c;border-radius:99px;overflow:hidden}
#mc-fill{height:100%;width:0;background:#4f8cff}
#mc-row,#mc-row2{display:flex;gap:clamp(8px,2.4vmin,20px);align-items:center;
  justify-content:center;flex-wrap:wrap;max-width:96vw}
#mediactl button{background:#2b303c;border:0;color:#e8e8e8;font:inherit;font-weight:700}
#mc-row button{width:clamp(46px,13vmin,84px);height:clamp(46px,13vmin,84px);
  border-radius:50%;font-size:clamp(15px,3vmin,22px)}
#mc-pp{background:#4f8cff!important;font-size:clamp(22px,5vmin,38px)!important;
  width:clamp(58px,16vmin,100px)!important;height:clamp(58px,16vmin,100px)!important}
#mc-row2 button{height:clamp(40px,10vmin,64px);padding:0 clamp(12px,3vw,26px);
  border-radius:99px;font-size:clamp(13px,2.6vmin,18px)}
#mediactl button:active{background:#4f8cff}
/* prev/next so em serie e musica; filme nao tem faixa anterior/proxima */
body[data-media=movie] .mc-track{display:none}

/* ---- now-playing backdrop: capa borrada atras do controle de midia ---- */
#np-bg{position:absolute;inset:0;background-size:cover;background-position:center;
  filter:blur(38px) brightness(.4) saturate(1.25);transform:scale(1.3);
  opacity:0;transition:opacity .5s;pointer-events:none;z-index:0}
body[data-mode=media] #np-bg.on{opacity:1}
#mediactl{z-index:1}
/* ---- sincronia legenda/audio (so em video) ---- */
#mc-sync{display:flex;flex-direction:column;gap:8px;align-items:center;width:min(560px,90vw)}
body[data-media=music] #mc-sync{display:none}
.mc-syncrow{display:flex;align-items:center;gap:10px;justify-content:center;
  font-size:clamp(12px,2.5vmin,16px);opacity:.9}
.mc-syncrow .lb{width:clamp(66px,16vmin,96px);text-align:right;opacity:.7}
.mc-syncrow .vv{width:clamp(52px,13vmin,74px);text-align:center;font-variant-numeric:tabular-nums;font-weight:700}
.mc-syncrow button{width:clamp(34px,9vmin,48px);height:clamp(34px,9vmin,48px);
  border-radius:50%;font-size:clamp(14px,3vmin,20px)}
/* ---- ver a TV (grim) ---- */
#tvbtn{position:absolute;top:clamp(10px,3vmin,22px);right:4vw;
  width:clamp(40px,9vmin,60px);height:clamp(40px,9vmin,60px);border-radius:50%;
  background:#2b303c;border:0;color:#e8e8e8;font-size:clamp(18px,4vmin,26px);opacity:.8;z-index:3}
body[data-inpad="1"] #tvbtn{display:block}
#tvbtn{display:none}
#tvview{position:fixed;inset:0;z-index:50;background:#000d;display:none;
  align-items:center;justify-content:center;flex-direction:column;gap:14px}
#tvview.on{display:flex}
#tvimg{max-width:96vw;max-height:82vh;border-radius:10px;box-shadow:0 10px 40px #000a;background:#111}
#tvclose{width:54px;height:54px;border-radius:50%;border:0;background:#2b303c;color:#fff;font-size:22px}

/* ===================== POLISH ===================== */
/* transicao suave ao trocar de aba */
.view.on{animation:fadeup .28s cubic-bezier(.2,.7,.3,1)}
@keyframes fadeup{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
/* cards e posteres: press-scale, sombra, gradiente sobre o nome */
.card,.poster{box-shadow:0 3px 12px #0005;transition:transform .13s ease,box-shadow .13s}
.card:active,.poster:active{transform:scale(.95);box-shadow:0 1px 6px #0006}
.card .nm{background:linear-gradient(180deg,#1b1f2800,#1b1f28 55%);position:relative;margin-top:-14px;padding-top:14px}
.card .cov,.poster .pc{transition:transform .2s ease}
/* skeleton shimmer (loading) */
.skwrap{padding:14px;display:grid;gap:12px}
.skwrap.games{grid-template-columns:repeat(auto-fill,minmax(105px,1fr))}
.skwrap.post{grid-template-columns:repeat(auto-fill,minmax(100px,1fr))}
.sk{border-radius:10px;background:#1a1e26;position:relative;overflow:hidden}
.skwrap.games .sk{aspect-ratio:3/4}.skwrap.post .sk{aspect-ratio:2/3}
.sk::after{content:'';position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,#ffffff10,transparent);animation:shine 1.3s infinite}
@keyframes shine{100%{transform:translateX(100%)}}
/* modais deslizam em vez de piscar */
#eplist,#dllist{transition:opacity .2s;opacity:0}
#eplist.on,#dllist.on{opacity:1}
#eplist.on #eps,#dllist.on #dls{animation:slideup .28s cubic-bezier(.2,.7,.3,1)}
@keyframes slideup{from{transform:translateY(24px);opacity:0}to{transform:none;opacity:1}}
/* tab bar: indicador e realce do ativo */
#tabs button{transition:color .15s;position:relative}
#tabs button.on::before{content:'';position:absolute;top:0;left:22%;right:22%;height:3px;
  background:#4f8cff;border-radius:0 0 3px 3px}
#tabs button .i{transition:transform .15s}
#tabs button.on .i{transform:translateY(-1px) scale(1.08)}

/* ===================== TEMA YERBA MATE (re-skin) ===================== */
html,body{background:var(--bg)!important;background-image:none!important;color:var(--tx)!important;
  font-family:var(--sans)}
.sec{color:var(--accent);font-family:var(--serif);font-weight:700;text-transform:none;
  letter-spacing:.01em;font-size:16px}
#tabs{background:var(--bar);border-top:1px solid var(--border)}
#tabs button{color:var(--tx-3)}
#tabs button.on{color:var(--accent)}
#tabs button.on::before{background:var(--accent)}
.card,.poster,.rcard{background:var(--surface);border:1px solid var(--border);border-radius:10px}
.card:active,.poster:active{border-color:var(--accent);box-shadow:0 1px 6px #0002}
.card .cov,.rcard .rc,.poster .pc{background-color:var(--ui);color:var(--tx-3)}
.card .nm,.rcard .rn{background:linear-gradient(transparent,var(--nm-grad) 55%);color:var(--tx)}
.card .sys,.rcard .rt{background:var(--accent);color:#fff}
.searchbar{background:var(--bg);border-bottom:1px solid var(--border)}
.searchbar input{background:var(--surface);border:1px solid var(--border);color:var(--tx)}
.searchbar input:focus{border-color:var(--accent)}
.searchbar button,#mediactl button,.mc-corner,#tvbtn{background:var(--ui)!important;color:var(--tx)!important}
#mediactl button:active,.searchbar button:active{background:var(--accent)!important;color:#fff!important}
#mc-pp{background:var(--accent)!important;color:#fff}
#mc-title{font-family:var(--serif)}
#mc-bar,.dl .bar{background:var(--ui)}
#mc-fill{background:var(--accent)}
#miniplayer{background:var(--surface);border-top:1px solid var(--border);color:var(--tx)}
#dlbtn{background:var(--surface);border:1px solid var(--border);color:var(--tx)}
#dlbadge{background:var(--accent);color:#fff}
#dllist,#eplist{background:var(--overlay)}
#np-bg{filter:blur(38px) brightness(.5) saturate(1.15)}
body[data-p="2"] #pnum{color:var(--p2)}
/* gamepad */
#pad{background:var(--bg)!important}
#pad button{background:var(--ui)!important;color:var(--tx)!important}
#pad button:active,#pad button.on{background:var(--accent)!important;color:#fff!important}
#tomenu{background:var(--ui)!important}
#face button[data-b=a]{background:var(--accent-2)!important}
#face button[data-b=b]{background:var(--p2)!important}
#pad button#bz{background:var(--accent-2)!important}
#ls{background:radial-gradient(circle,var(--surface),var(--bg2))!important;border:2px solid var(--ui)!important}
#rs{background:radial-gradient(circle,var(--surface),var(--bg2))!important;border:2px solid var(--ui)!important}
#lk{background:var(--accent)!important}
#rk{background:var(--accent-2)!important}
.lbl,#pnum{color:var(--tx-2)}
/* apps */
.app{background:var(--surface)!important;border:1px solid var(--border)!important;color:var(--tx)}
</style></head><body>

<div id=app>
  <div class="view on" id=v-games>
    <div id=recent-wrap style=display:none>
      <div class=sec>Recentes</div>
      <div id=recent></div>
    </div>
    <div class=sec>Biblioteca</div>
    <div id=games></div>
  </div>

  <div class="view" id=v-movies>
    <div class=searchbar><input class=si type=search data-kind=movie placeholder="Buscar filme para baixar…" enterkeyhint=search><button class=sx style=display:none>✕</button></div>
    <div id=resume-wrap style=display:none>
      <div class=sec>Continuar</div>
      <div id=resume></div>
    </div>
    <div id=movies class=pgrid></div>
  </div>
  <div class="view" id=v-series>
    <div class=searchbar><input class=si type=search data-kind=series placeholder="Buscar série para baixar…" enterkeyhint=search><button class=sx style=display:none>✕</button></div>
    <div id=series class=pgrid></div>
  </div>
  <div class="view" id=v-music><div id=music class=pgrid></div></div>

  <div class="view" id=v-apps>
    <div id=apps></div>
  </div>
</div>

<div id=eplist><div id=ephead><span id=eptitle></span><button onclick="closeEps()">✕</button></div><div id=eps></div></div>
<button id=dlbtn onclick="openDl()">📥<span id=dlbadge></span></button>
<div id=dllist><div id=ephead style="border-bottom:1px solid #262b36"><span>Downloads</span><button onclick="closeDl()">✕</button></div><div id=dls></div></div>
<div id=toast></div>

<div id=pad>
  <div id=np-bg></div>
  <button id=tvbtn onclick="openTv()">📺</button>
  <div class="p" id=tl><button class=trig data-b=l>L</button><button class="trig" id=bz data-b=z>Z</button></div>
  <div class="p" id=tr><button class=trig data-b=r>R</button></div>
  <div class="p" id=mid><button id=tomenu>☰</button><button data-b=start>START</button><span id=pnum>P1</span><button data-b=select>SEL</button></div>
  <div id=dpad><div></div><button data-b=up>▲</button><div></div><button data-b=left>◀</button><div></div><button data-b=right>▶</button><div></div><button data-b=down>▼</button><div></div></div>
  <div class="p" id=face><div></div><button data-b=x>X</button><div></div><button data-b=y>Y</button><div></div><button data-b=a>A</button><div></div><button data-b=b>B</button><div></div></div>
  <div class="p" id=ls><div class=knob id=lk></div><span class=lbl>ANALÓGICO</span></div>
  <div class="p" id=rs><div class=knob id=rk></div><span class=lbl>C</span></div>

  <div id=mediactl>
    <button id=mc-back class=mc-corner onclick="showTab('games')">☰</button>
    <img id=mc-art alt="">
    <div id=mc-title>—</div>
    <div id=mc-time><span id=mc-cur>0:00</span><div id=mc-bar><div id=mc-fill></div></div><span id=mc-dur>0:00</span></div>
    <div id=mc-row>
      <button class=mc-track data-mpv=prev>⏮</button>
      <button data-mpv=back>-10s</button>
      <button id=mc-pp data-mpv=playpause>⏸</button>
      <button data-mpv=fwd>+10s</button>
      <button class=mc-track data-mpv=next>⏭</button>
    </div>
    <div id=mc-row2>
      <button data-mpv=voldown>🔉</button>
      <button data-mpv=audio>🔊 áudio</button>
      <button data-mpv=sub>💬 legenda</button>
      <button data-mpv=volup>🔊</button>
    </div>
    <div id=mc-sync class=mc-vid>
      <div class=mc-syncrow>
        <span class=lb>💬 legenda</span>
        <button data-mpv=subdelay->−</button>
        <span class=vv id=mc-subd onclick="mpvBtn('subdelay0')">0.0s</span>
        <button data-mpv=subdelay+>+</button>
      </div>
      <div class=mc-syncrow>
        <span class=lb>🔊 áudio</span>
        <button data-mpv=audiodelay->−</button>
        <span class=vv id=mc-audd onclick="mpvBtn('audiodelay0')">0.0s</span>
        <button data-mpv=audiodelay+>+</button>
      </div>
    </div>
  </div>
</div>
<div id=tvview onclick="closeTv()"><img id=tvimg alt="TV"><button id=tvclose>✕</button></div>

<div id=miniplayer onclick="showTab('pad')">
  <img id=mp-art alt="">
  <div id=mp-info><div id=mp-title>—</div><div id=mp-sub></div></div>
  <button id=mp-pp onclick="event.stopPropagation();mpvBtn('playpause')">⏸</button>
  <button id=mp-stop onclick="event.stopPropagation();stop()">✕</button>
</div>

<div id=tabs>
  <button data-tab=games class=on><span class=i>🕹</span>Jogos</button>
  <button data-tab=movies><span class=i>🎬</span>Filmes</button>
  <button data-tab=series><span class=i>📺</span>Séries</button>
  <button data-tab=music><span class=i>🎵</span>Música</button>
  <button data-tab=apps><span class=i>⚙️</span>Apps</button>
  <button data-tab=pad><span class=i>🎮</span>Controle</button>
</div>

<script>
// tema Yerba Mate: Tererê (6h-18h) / Cimarrão (18h-6h), igual ao site pessoal
(function(){var forced=new URLSearchParams(location.search).get('theme');
  function t(){if(forced){document.documentElement.dataset.theme=forced;return;}
    var h=new Date().getHours();
    document.documentElement.dataset.theme=(h>=6&&h<18)?'light':'dark';}
  t();setInterval(t,600000);})();
const P = new URLSearchParams(location.search).get('p') === '2' ? 2 : 1;
document.body.dataset.p = P;

// ---------- navegacao de abas ----------
const TABS=['games','movies','series','music','apps'];
const views={};
for(const t of TABS) views[t]=document.getElementById('v-'+t);
views.pad=document.getElementById('pad');
let loaded={};
function showTab(t){
  for(const b of document.querySelectorAll('#tabs button')) b.classList.toggle('on', b.dataset.tab===t);
  const pad = t==='pad';
  document.body.dataset.inpad = pad ? '1' : '';
  document.getElementById('app').style.display = pad ? 'none' : 'block';
  document.getElementById('tabs').style.display = pad ? 'none' : 'flex';  // controle = sem tab bar
  document.getElementById('app').style.bottom = pad ? '0' : '62px';
  for(const k of TABS) views[k].classList.toggle('on', k===t);
  views.pad.classList.toggle('on', pad);
  if(pad){ keepAwake(); refreshStatus(); }
  if(t==='movies' && !loaded.movies){ loaded.movies=1; loadMovies(); }
  if(t==='series' && !loaded.series){ loaded.series=1; loadSeries(); }
  if(t==='music'  && !loaded.music ){ loaded.music =1; loadMusic();  }
}
for(const b of document.querySelectorAll('#tabs button'))
  b.onclick=()=>showTab(b.dataset.tab);
document.getElementById('tomenu').onclick=()=>showTab('games');

// ---------- musica ----------
async function loadMusic(){
  skeletons(document.getElementById('music'),'post',8);
  const a=await fetch('/api/albums').then(r=>r.json()).catch(()=>[]);
  const el=document.getElementById('music'); el.innerHTML='';
  if(!a.length){el.innerHTML='<div style="padding:20px;opacity:.5">nenhum álbum</div>';return;}
  for(const al of a){
    const c=posterCard(al, ()=>play(al.path,'music',al.cover));
    c.querySelector('.pc').textContent = al.cover?'':'🎵';
    el.appendChild(c);
  }
}

// ---------- controle de midia (mpv) ----------
for(const b of document.querySelectorAll('#mediactl button[data-mpv]')){
  b.onclick=()=>{buzz();fetch('/api/mpv',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:b.dataset.mpv})}).then(()=>setTimeout(refreshStatus,300));};
}
function fmt(s){s=Math.max(0,Math.floor(s||0));const m=Math.floor(s/60);return m+':'+String(s%60).padStart(2,'0');}
function updateMedia(now){
  if(!now) return;
  document.getElementById('mc-title').textContent = now.title || 'reproduzindo';
  document.getElementById('mc-cur').textContent = fmt(now.pos);
  document.getElementById('mc-dur').textContent = fmt(now.duration);
  document.getElementById('mc-fill').style.width = now.duration? (100*now.pos/now.duration)+'%':'0';
  document.getElementById('mc-pp').textContent = now.paused ? '▶' : '⏸';
  const art=document.getElementById('mc-art');
  if(now.cover){ if(art.getAttribute('src')!==now.cover) art.src=now.cover; art.classList.add('on'); }
  else { art.classList.remove('on'); art.removeAttribute('src'); }
  const bg=document.getElementById('np-bg');
  if(now.cover){ const u=`url(${now.cover})`; if(bg.style.backgroundImage!==u) bg.style.backgroundImage=u; bg.classList.add('on'); }
  else bg.classList.remove('on');
  const sd=document.getElementById('mc-subd'), ad=document.getElementById('mc-audd');
  if(sd) sd.textContent=(now.subdelay>0?'+':'')+(now.subdelay||0).toFixed(1)+'s';
  if(ad) ad.textContent=(now.audiodelay>0?'+':'')+(now.audiodelay||0).toFixed(1)+'s';
}

// ---------- filmes / series ----------
function posterCard(item, onclick){
  const c=document.createElement('div'); c.className='poster';
  const cov=item.cover?`background-image:url(${item.cover})`:'';
  c.innerHTML=`<div class=pc style="${cov}">${item.cover?'':'🎬'}</div><div class=pn>${item.name}</div>`;
  c.onclick=onclick; return c;
}
async function loadMovies(){
  skeletons(document.getElementById('movies'),'post',10);
  loadResume();
  const m=await fetch('/api/movies').then(r=>r.json()).catch(()=>[]);
  const el=document.getElementById('movies'); el.innerHTML='';
  if(!m.length){el.innerHTML='<div style="padding:20px;opacity:.5">nenhum filme</div>';return;}
  for(const mv of m) el.appendChild(posterCard(mv, ()=>play(mv.path,'movie',mv.cover)));
}
async function loadResume(){
  const r=await fetch('/api/resume').then(x=>x.json()).catch(()=>[]);
  const wrap=document.getElementById('resume-wrap'), el=document.getElementById('resume');
  if(!r.length){wrap.style.display='none';return;}
  wrap.style.display='block'; el.innerHTML='';
  for(const it of r){
    const c=document.createElement('div'); c.className='rcard';
    const mins=Math.floor((it.pos||0)/60), badge=mins>0?`▶ ${mins}min`:'▶';
    const cov=it.cover?`background-image:url(${it.cover})`:'';
    c.innerHTML=`<div class=rc style="${cov}">${it.cover?'':'🎬'}</div><div class=rt>${badge}</div><div class=rn>${it.name}</div>`;
    c.onclick=()=>play(it.path,'movie',it.cover);
    el.appendChild(c);
  }
}

// ---------- toast ----------
let toastT=null;
function toast(msg){
  const t=document.getElementById('toast'); t.textContent=msg; t.classList.add('on');
  clearTimeout(toastT); toastT=setTimeout(()=>t.classList.remove('on'),3500);
}

// ---------- busca (filme=Radarr, serie=Sonarr), generica ----------
const SEARCH={
  movie:  {url:'/api/search',        grid:'movies', reload:()=>loadMovies(),
           req:r=>({ep:'/api/request',        body:{tmdbId:r.tmdbId}}), where:'Filmes'},
  series: {url:'/api/search-series',  grid:'series', reload:()=>loadSeries(),
           req:r=>({ep:'/api/request-series', body:{tvdbId:r.tvdbId}}), where:'Séries'},
};
let searchT=null;
for(const inp of document.querySelectorAll('.searchbar .si')){
  const kind=inp.dataset.kind, cfg=SEARCH[kind];
  const xb=inp.parentElement.querySelector('.sx');
  inp.addEventListener('input',()=>{
    xb.style.display=inp.value?'block':'none';
    clearTimeout(searchT);
    const q=inp.value.trim();
    if(!q){cfg.reload();return;}
    searchT=setTimeout(()=>doSearch(kind,q),500);
  });
  inp.addEventListener('search',()=>{const q=inp.value.trim();q?doSearch(kind,q):cfg.reload();});
  xb.onclick=()=>{inp.value='';xb.style.display='none';cfg.reload();inp.blur();};
}
async function doSearch(kind,q){
  const cfg=SEARCH[kind], el=document.getElementById(cfg.grid);
  el.innerHTML='<div style="padding:20px;opacity:.5">buscando…</div>';
  const res=await fetch(cfg.url+'?q='+encodeURIComponent(q)).then(r=>r.json()).catch(()=>[]);
  el.innerHTML='';
  if(!res.length){el.innerHTML='<div style="padding:20px;opacity:.5">nada encontrado</div>';return;}
  for(const r of res){
    const c=posterCard({name:`${r.title} (${r.year||'?'})`,cover:r.poster},
      ()=> r.have ? toast('já está na biblioteca') : reqItem(kind,r));
    const tag=document.createElement('div');
    if(r.have){tag.className='badge';tag.textContent='NA BIBLIOTECA';}
    else{tag.className='req';tag.textContent='＋ baixar';}
    c.appendChild(tag); el.appendChild(c);
  }
}
async function reqItem(kind,r){
  const cfg=SEARCH[kind], {ep,body}=cfg.req(r);
  toast('Solicitando '+r.title+'…');
  const res=await fetch(ep,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(body)}).then(x=>x.json()).catch(()=>({ok:false}));
  toast(res.ok ? '✓ '+r.title+' — baixando, aparece em '+cfg.where+' quando pronto' : 'erro ao solicitar');
  setTimeout(loadDownloads,2000);
}

// ---------- downloads ----------
async function loadDownloads(){
  const dl=await fetch('/api/downloads').then(r=>r.json()).catch(()=>[]);
  const btn=document.getElementById('dlbtn'), badge=document.getElementById('dlbadge');
  btn.classList.toggle('on', dl.length>0);
  badge.textContent=dl.length||'';
  const box=document.getElementById('dls');
  if(!dl.length){box.innerHTML='<div style="padding:20px;opacity:.5">nada baixando</div>';return;}
  box.innerHTML='';
  for(const d of dl){
    const el=document.createElement('div'); el.className='dl';
    el.innerHTML=`<div class=dh><span class=t>${d.title}</span><span class=p>${d.percent}%</span></div><div class=bar><i style="width:${d.percent}%"></i></div>`;
    box.appendChild(el);
  }
}
function openDl(){loadDownloads();document.getElementById('dllist').classList.add('on');}
function closeDl(){document.getElementById('dllist').classList.remove('on');}
async function loadSeries(){
  skeletons(document.getElementById('series'),'post',10);
  const s=await fetch('/api/series').then(r=>r.json()).catch(()=>[]);
  const el=document.getElementById('series'); el.innerHTML='';
  if(!s.length){el.innerHTML='<div style="padding:20px;opacity:.5">nenhuma série</div>';return;}
  for(const sr of s) el.appendChild(posterCard(sr, ()=>openEps(sr)));
}
async function openEps(series){
  document.getElementById('eptitle').textContent=series.name;
  const box=document.getElementById('eps'); box.innerHTML='carregando…';
  document.getElementById('eplist').classList.add('on');
  const eps=await fetch('/api/episodes?id='+series.id).then(r=>r.json()).catch(()=>[]);
  box.innerHTML='';
  if(!eps.length){box.innerHTML='<div style="padding:20px;opacity:.5">sem episódios</div>';return;}
  eps.forEach((ep,i)=>{
    const d=document.createElement('div'); d.className='ep'; d.textContent=ep.name;
    d.onclick=()=>{closeEps();play(eps.slice(i).map(e=>e.path),'series',series.cover);};
    box.appendChild(d);
  });
}
function closeEps(){document.getElementById('eplist').classList.remove('on');}
async function play(pathOrList, kind, cover){
  const body = Array.isArray(pathOrList) ? {paths:pathOrList,kind,cover} : {path:pathOrList,kind,cover};
  await fetch('/api/play',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  setTimeout(refreshStatus,1500);
  showTab('pad');
}

// ---------- jogos ----------
function skeletons(el,cls,n){
  el.innerHTML='';
  const w=document.createElement('div'); w.className='skwrap '+cls;
  for(let i=0;i<n;i++){const s=document.createElement('div');s.className='sk';w.appendChild(s);}
  el.appendChild(w);
}
async function loadGames(){
  const el0=document.getElementById('games'); skeletons(el0,'games',12);
  loadRecent();
  const g = await fetch('/api/games').then(r=>r.json()).catch(()=>[]);
  const el=document.getElementById('games'); el.innerHTML='';
  for(const game of g){
    const c=document.createElement('div'); c.className='card';
    const cov = game.cover ? `background-image:url(${game.cover})` : '';
    c.innerHTML=`<div class=cov style="${cov}">${game.cover?'':'🎮'}</div><div class=nm>${game.name}</div><div class=sys>${game.label}</div>`;
    c.onclick=()=>launch(game);
    el.appendChild(c);
  }
}
async function loadRecent(){
  const r=await fetch('/api/recent').then(x=>x.json()).catch(()=>[]);
  const wrap=document.getElementById('recent-wrap'), el=document.getElementById('recent');
  if(!r.length){wrap.style.display='none';return;}
  wrap.style.display='block'; el.innerHTML='';
  for(const it of r){
    const c=document.createElement('div'); c.className='rcard';
    const cov=it.cover?`background-image:url(${it.cover})`:'';
    const icon=it.type==='game'?'🎮':'🎬';
    const tag=it.type==='game'?(it.label||'JOGO'):'FILME';
    c.innerHTML=`<div class=rc style="${cov}">${it.cover?'':icon}</div><div class=rt>${tag}</div><div class=rn>${it.name}</div>`;
    c.onclick=()=> it.type==='game' ? launch(it) : play(it.path,'movie',it.cover);
    el.appendChild(c);
  }
}
async function launch(game){
  await fetch('/api/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({system:game.system,path:game.path})});
  setTimeout(refreshStatus, 1500);
  showTab('pad');   // lancou -> vira controle
}

// ---------- apps ----------
async function loadApps(){
  const a = await fetch('/api/apps').then(r=>r.json()).catch(()=>[]);
  const el=document.getElementById('apps'); el.innerHTML='';
  for(const app of a){
    const d=document.createElement('div'); d.className='app';
    d.innerHTML=`<span class=i>${app.icon}</span>${app.label}`;
    d.onclick=()=>fetch('/api/app',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:app.id})});
    el.appendChild(d);
  }
}

// ---------- status / mini-player ----------
async function refreshStatus(){
  const s = await fetch('/api/status').then(r=>r.json()).catch(()=>({running:false}));
  const mp=document.getElementById('miniplayer');
  document.body.dataset.mode = s.kind==='media' ? 'media' : 'game';
  if(!s.running){ mp.classList.remove('on'); return; }
  mp.classList.add('on');
  const art=document.getElementById('mp-art'), pp=document.getElementById('mp-pp');
  if(s.kind==='media'){
    const now=s.now||{};
    document.getElementById('mp-title').textContent = now.title || 'reproduzindo';
    document.getElementById('mp-sub').textContent = fmt(now.pos)+' / '+fmt(now.duration);
    if(now.cover){ if(art.getAttribute('src')!==now.cover)art.src=now.cover; art.style.display='block'; }
    else art.style.display='none';
    pp.style.display=''; pp.textContent = now.paused?'▶':'⏸';
    document.body.dataset.media = now.mkind||'';
    updateMedia(now);
  } else {
    document.getElementById('mp-title').textContent = 'Jogo rodando';
    document.getElementById('mp-sub').textContent = 'toque para abrir o controle';
    art.style.display='none'; pp.style.display='none';
  }
}
async function mpvBtn(action){
  await fetch('/api/mpv',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action})});
  setTimeout(refreshStatus,300);
}
async function stop(){ await fetch('/api/stop',{method:'POST'}); document.getElementById('miniplayer').classList.remove('on'); setTimeout(refreshStatus,800); }

// ---------- ver a TV (grim) ----------
let tvTimer=null;
function tvTick(){
  const img=document.getElementById('tvimg');
  const u='/api/tv?'+Date.now();
  const pre=new Image();
  pre.onload=()=>{img.src=u;};
  pre.src=u;
}
function openTv(){ document.getElementById('tvview').classList.add('on'); tvTick(); tvTimer=setInterval(tvTick,2500); }
function closeTv(){ document.getElementById('tvview').classList.remove('on'); clearInterval(tvTimer); tvTimer=null; }

// ---------- gamepad (controle) ----------
const post=o=>{o.p=P;return fetch('/p',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o),keepalive:true}).catch(()=>{});};
const buzz=()=>{try{navigator.vibrate&&navigator.vibrate(8)}catch(_){}};
for(const el of document.querySelectorAll('#pad button[data-b]')){
  const b=el.dataset.b;
  const d=ev=>{ev.preventDefault();el.classList.add('on');buzz();post({btn:b,state:1})};
  const u=ev=>{ev.preventDefault();el.classList.remove('on');post({btn:b,state:0})};
  el.addEventListener('touchstart',d,{passive:false});el.addEventListener('touchend',u,{passive:false});
  el.addEventListener('touchcancel',u,{passive:false});el.addEventListener('mousedown',d);el.addEventListener('mouseup',u);el.addEventListener('mouseleave',u);
}
function stick(pad,knob,which){
  let id=null,last=0,px=0,py=0;
  function move(t){const r=pad.getBoundingClientRect(),R=r.width/2;let dx=t.clientX-(r.left+R),dy=t.clientY-(r.top+R);const d=Math.hypot(dx,dy);if(d>R){dx*=R/d;dy*=R/d;}knob.style.transform=`translate(calc(-50% + ${dx}px),calc(-50% + ${dy}px))`;const x=Math.round(dx/R*32767),y=Math.round(dy/R*32767),now=Date.now();if(now-last>16&&(x!==px||y!==py)){last=now;px=x;py=y;post({axis:which,x,y});}}
  function reset(){knob.style.transform='translate(-50%,-50%)';px=py=0;post({axis:which,x:0,y:0});}
  pad.addEventListener('touchstart',ev=>{ev.preventDefault();if(id===null){id=ev.changedTouches[0].identifier;buzz();move(ev.changedTouches[0]);}},{passive:false});
  pad.addEventListener('touchmove',ev=>{ev.preventDefault();for(const t of ev.changedTouches)if(t.identifier===id)move(t);},{passive:false});
  const end=ev=>{ev.preventDefault();for(const t of ev.changedTouches)if(t.identifier===id){id=null;reset();}};
  pad.addEventListener('touchend',end,{passive:false});pad.addEventListener('touchcancel',end,{passive:false});
  pad.addEventListener('mousedown',ev=>{id='m';move(ev)});window.addEventListener('mousemove',ev=>{if(id==='m')move(ev)});window.addEventListener('mouseup',()=>{if(id==='m'){id=null;reset()}});
}
stick(document.getElementById('ls'),document.getElementById('lk'),1);
stick(document.getElementById('rs'),document.getElementById('rk'),2);

let lock=null;
async function keepAwake(){try{if('wakeLock' in navigator)lock=await navigator.wakeLock.request('screen');}catch(_){}}
document.addEventListener('gesturestart',e=>e.preventDefault());
document.addEventListener('dblclick',e=>e.preventDefault());

// tela cheia real (esconde a barra do navegador em HTTP, sem precisar de HTTPS/PWA).
// so pode ser acionada por gesto do usuario -> primeiro toque em qualquer lugar.
function goFullscreen(){
  const el=document.documentElement;
  const fn=el.requestFullscreen||el.webkitRequestFullscreen;
  if(fn && !document.fullscreenElement){ try{fn.call(el);}catch(_){} }
}
window.addEventListener('touchend', goFullscreen, {passive:true});
window.addEventListener('click', goFullscreen);

loadGames(); loadApps(); refreshStatus(); loadDownloads();
setInterval(refreshStatus, 2000);
setInterval(loadDownloads, 8000);
// abrir aba direto via ?tab= (util pra testar)
const _t=new URLSearchParams(location.search).get('tab');
if(_t && (TABS.includes(_t)||_t==='pad')) showTab(_t);
</script></body></html>"""


LOGIN_PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Oikos</title><style>
html,body{height:100%;margin:0;background:#0c0e13;color:#e7eaf0;
  font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center}
form{display:flex;flex-direction:column;gap:14px;width:min(320px,82vw);text-align:center}
h1{margin:0 0 6px;font-size:26px;letter-spacing:.5px}
input{padding:14px 16px;border-radius:12px;border:1px solid #ffffff1a;
  background:#161a22;color:#e7eaf0;font-size:16px}
button{padding:14px;border:0;border-radius:12px;background:#2f6df0;color:#fff;
  font-size:16px;font-weight:600}
.err{color:#ff7a7a;font-size:14px;min-height:18px}
</style></head><body>
<form method=post action=/login>
  <h1>Oikos</h1>
  <input type=password name=password placeholder=Senha autofocus autocomplete=current-password>
  <div class=err><!--err--></div>
  <button>Entrar</button>
</form></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authed(self):
        # Neither set -> open (trusted LAN). Otherwise accept ?t=<token>, or the
        # `oikos` cookie holding the token or the password hash. Cookies auto-attach
        # to same-origin fetches, so the phone stays logged in.
        if not TOKEN and not PASSWORD:
            return True
        if TOKEN and parse_qs(urlparse(self.path).query).get("t", [""])[0] == TOKEN:
            return True
        cookie = self.headers.get("Cookie", "")
        return any(v and f"oikos={v}" in cookie for v in (TOKEN, PWHASH))

    def _deny(self):
        self.send_response(401)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"unauthorized: append ?t=<token>")

    def _login_page(self, err=""):
        body = LOGIN_PAGE.replace("<!--err-->", err).encode()
        self.send_response(401 if err else 200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _login(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b""
        if "json" in self.headers.get("Content-Type", ""):
            try:
                pw = json.loads(raw or b"{}").get("password", "")
            except Exception:
                pw = ""
        else:
            pw = parse_qs(raw.decode("utf-8", "ignore")).get("password", [""])[0]
        if PASSWORD and hashlib.sha256(pw.encode()).hexdigest() == PWHASH:
            self.send_response(303)
            self.send_header("Set-Cookie",
                             f"oikos={PWHASH}; Path=/; Max-Age=31536000; SameSite=Lax")
            self.send_header("Location", "/")
            self.end_headers()
        else:
            self._login_page("Wrong password")

    def do_GET(self):
        path = urlparse(self.path).path
        if not self._authed():
            # login form only at the root; everything else gets a clean 401
            if PASSWORD and (path == "/" or path == ""):
                return self._login_page()
            return self._deny()
        if path == "/" or path == "":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            if TOKEN:   # persist the token so later requests carry it
                self.send_header("Set-Cookie",
                                 f"oikos={TOKEN}; Path=/; Max-Age=31536000; SameSite=Lax")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/manifest.json":
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json")
            self.send_header("Content-Length", str(len(MANIFEST)))
            self.end_headers()
            self.wfile.write(MANIFEST)
        elif path == "/icon.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "max-age=604800")
            self.send_header("Content-Length", str(len(ICON_PNG)))
            self.end_headers()
            self.wfile.write(ICON_PNG)
        elif path == "/api/games":
            self._json(list_games())
        elif path == "/api/apps":
            self._json(APPS)
        elif path == "/api/recent":
            self._json(list_recent())
        elif path == "/api/resume":
            self._json(list_resume())
        elif path == "/api/tv":
            data = tv_frame()
            if data:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(503); self.end_headers()
        elif path == "/api/movies":
            try:
                self._json(list_movies())
            except Exception:
                self._json([])
        elif path == "/api/series":
            try:
                self._json(list_series())
            except Exception:
                self._json([])
        elif path == "/api/albums":
            try:
                self._json(list_albums())
            except Exception:
                self._json([])
        elif path == "/api/search":
            qs = parse_qs(urlparse(self.path).query)
            term = qs.get("q", [""])[0]
            try:
                self._json(search_movies(term) if term else [])
            except Exception:
                self._json([])
        elif path == "/api/search-series":
            qs = parse_qs(urlparse(self.path).query)
            term = qs.get("q", [""])[0]
            try:
                self._json(search_series(term) if term else [])
            except Exception:
                self._json([])
        elif path == "/api/downloads":
            self._json(get_downloads())
        elif path == "/img":
            qs = parse_qs(urlparse(self.path).query)
            u = qs.get("u", [""])[0]
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "hub"})
                data = urllib.request.urlopen(req, timeout=15).read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_response(404); self.end_headers()
        elif path.startswith("/acover/"):
            apath = urllib.parse.unquote(path[len("/acover/"):])
            cov = next((os.path.join(apath, c) for c in
                        ("cover.jpg", "folder.jpg", "cover.png", "front.jpg")
                        if os.path.exists(os.path.join(apath, c))), None)
            if cov:
                data = open(cov, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers()
        elif path == "/api/episodes":
            qs = parse_qs(urlparse(self.path).query)
            sid = qs.get("id", [""])[0]
            try:
                self._json(list_episodes(sid))
            except Exception:
                self._json([])
        elif path.startswith("/jf/"):
            iid = path[4:]
            try:
                url = f"{JF}/Items/{iid}/Images/Primary?maxWidth=400&api_key={JF_KEY}"
                data = urllib.request.urlopen(url, timeout=15).read()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_response(404); self.end_headers()
        elif path == "/api/status":
            g = running_game()
            # kind: 'game' (gamepad) | 'media' (controle de video) | None
            if g == "mpv":
                now = mpv_now_playing() or {}
                now["cover"] = STATE["cover"]
                now["mkind"] = STATE["mkind"]
                self._json({"running": True, "kind": "media", "now": now})
            elif g:
                self._json({"running": True, "kind": "game", "current": g})
            else:
                self._json({"running": False, "kind": None})
        elif path.startswith("/cover/"):
            _, _, sysname, stem = path.split("/", 3)
            stem = urllib.parse.unquote(stem)
            f = os.path.join(COVERS, sysname, stem + ".png")
            if os.path.exists(f):
                data = open(f, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "max-age=86400")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/login":
            return self._login()
        if not self._authed():
            return self._deny()
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n) if n else b"{}"
        try:
            d = json.loads(raw) if raw.strip() else {}
        except Exception:
            d = {}

        if path == "/p":
            try:
                ui = PADS.get(2 if d.get("p") == 2 else 1)
                ax = d.get("axis")
                if ax:
                    c = lambda v: max(-AMAX, min(AMAX, int(v)))
                    xa, ya = (e.ABS_X, e.ABS_Y) if ax == 1 else (e.ABS_RX, e.ABS_RY)
                    ui.write(e.EV_ABS, xa, c(d.get("x", 0)))
                    ui.write(e.EV_ABS, ya, c(d.get("y", 0)))
                else:
                    ui.write(e.EV_KEY, BUTTONS[d["btn"]], 1 if d["state"] else 0)
                ui.syn()
                self.send_response(204); self.end_headers()
            except Exception:
                self.send_response(400); self.end_headers()

        elif path == "/api/launch":
            sysname = d.get("system"); rom = d.get("path")
            conf = SYSTEMS.get(sysname)
            if conf and rom and os.path.exists(rom):
                subprocess.run(["stop-game"])
                sway_exec(f"{conf['cmd']} '{rom}'")
                self._json({"ok": True})
            else:
                self._json({"ok": False}, 400)

        elif path == "/api/app":
            app = next((a for a in APPS if a["id"] == d.get("id")), None)
            if app:
                subprocess.run(["stop-game"])
                sway_exec(app["cmd"])
                self._json({"ok": True})
            else:
                self._json({"ok": False}, 400)

        elif path == "/api/play":
            # path (filme/musica single) ou paths (serie = temporada como playlist)
            items = d.get("paths") or ([d["path"]] if d.get("path") else [])
            items = [p for p in items if p and os.path.exists(p)]
            if items:
                subprocess.run(["stop-game"])
                STATE["cover"] = d.get("cover")
                STATE["mkind"] = d.get("kind")
                launcher = "play-audio" if d.get("kind") == "music" else "play-video"
                args = " ".join("'" + p.replace("'", "'\\''") + "'" for p in items)
                sway_exec(f"{launcher} {args}")
                self._json({"ok": True})
            else:
                self._json({"ok": False}, 400)

        elif path == "/api/mpv":
            cmd = MPV_ACTIONS.get(d.get("action"))
            if cmd:
                mpv_cmd(cmd)
                self._json({"ok": True})
            else:
                self._json({"ok": False}, 400)

        elif path == "/api/request":
            try:
                request_movie(int(d.get("tmdbId")))
                self._json({"ok": True})
            except Exception as ex:
                msg = str(ex)
                # ja existe = ok pro usuario
                self._json({"ok": "already" in msg.lower() or "exist" in msg.lower(),
                            "error": msg[:120]}, 200)

        elif path == "/api/request-series":
            try:
                request_series(int(d.get("tvdbId")))
                self._json({"ok": True})
            except Exception as ex:
                msg = str(ex)
                self._json({"ok": "already" in msg.lower() or "exist" in msg.lower(),
                            "error": msg[:120]}, 200)

        elif path == "/api/stop":
            subprocess.run(["stop-game"])
            STATE["cover"] = None
            STATE["mkind"] = None
            self._json({"ok": True})
        else:
            self.send_response(404); self.end_headers()


for n, pad in PADS.items():
    print(f"gamepad P{n}: {pad.device.path}")
print(f"console hub:  http://0.0.0.0:{PORT}")
ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
