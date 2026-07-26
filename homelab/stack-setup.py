#!/usr/bin/env python3
"""Configure the media stack after `docker compose up` (deterministic, stdlib only).

Does the wiring the arr web UIs otherwise need by hand:
  - Jellyfin: headless setup wizard, Movies/Shows libraries, an API key -> jf.key
  - Transmission: download-dir = /media/downloads
  - Radarr/Sonarr/Lidarr: root folder, Transmission download client (right category,
    remove-completed on)
  - Prowlarr: registers the arrs as applications (so indexers sync to them)

What it does NOT do (your call / interactive):
  - add indexers in Prowlarr (pick your own; run with names as args to add public ones,
    e.g. `stack-setup.py thepiratebay`)
  - Bazarr languages/providers (needs your subtitle-provider account)
  - the 1080p cap is enforced by the hub (it requests the HD-1080p profile)

Run it on the host after the stack is up. Idempotent: re-running skips what exists.
"""
import json, os, subprocess, sys, time, urllib.request, urllib.error

HOST = "http://localhost"
# container-to-container addresses (compose service names on the default network)
SVC = {"radarr": "http://radarr:7878", "sonarr": "http://sonarr:8989",
       "lidarr": "http://lidarr:8686", "prowlarr": "http://prowlarr:9696"}
PORT = {"radarr": 7878, "sonarr": 8989, "lidarr": 8686, "prowlarr": 9696}
ROOT = {"radarr": "/media/movies", "sonarr": "/media/series", "lidarr": "/media/music"}
CAT = {"radarr": "movies", "sonarr": "series", "lidarr": "music"}
HERE = os.path.dirname(os.path.abspath(__file__))


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def api_key(container):
    xml = sh("docker", "exec", container, "cat", "/config/config.xml")
    return xml.split("<ApiKey>")[1].split("</ApiKey>")[0] if "<ApiKey>" in xml else ""


def req(url, key=None, method="GET", body=None, token=None):
    h = {"Content-Type": "application/json"}
    if key:
        h["X-Api-Key"] = key
    if token:
        h["X-Emby-Token"] = token
    r = urllib.request.Request(url, method=method, headers=h,
                               data=json.dumps(body).encode() if body is not None else None)
    b = urllib.request.urlopen(r, timeout=30).read()
    return json.loads(b) if b else None


def wait(url, code=(200,), secs=120):
    for _ in range(secs):
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status in code:
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


# ---------------- Jellyfin ----------------
def setup_jellyfin():
    J = f"{HOST}:8096"
    print("Jellyfin: waiting...")
    wait(f"{J}/System/Info/Public")
    auth = 'MediaBrowser Client="oikos", Device="setup", DeviceId="oikos-setup", Version="1.0"'
    info = req(f"{J}/System/Info/Public")
    if not info.get("StartupWizardCompleted"):
        print("Jellyfin: running setup wizard")
        req(f"{J}/Startup/Configuration", method="POST",
            body={"UICulture": "en-US", "MetadataCountryCode": "US", "PreferredMetadataLanguage": "en"})
        req(f"{J}/Startup/User")
        req(f"{J}/Startup/User", method="POST", body={"Name": "admin", "Password": "devdev"})
        req(f"{J}/Startup/RemoteAccess", method="POST",
            body={"EnableRemoteAccess": True, "EnableAutomaticPortMapping": False})
        req(f"{J}/Startup/Complete", method="POST")
    r = urllib.request.Request(f"{J}/Users/AuthenticateByName", method="POST",
                               headers={"X-Emby-Authorization": auth, "Content-Type": "application/json"},
                               data=json.dumps({"Username": "admin", "Pw": "devdev"}).encode())
    tok = json.loads(urllib.request.urlopen(r, timeout=20).read())["AccessToken"]
    for name, coll, path in (("Movies", "movies", "/media/movies"), ("Shows", "tvshows", "/media/series")):
        try:
            req(f"{J}/Library/VirtualFolders?name={name}&collectionType={coll}&refreshLibrary=true",
                method="POST", token=tok, body={"LibraryOptions": {"PathInfos": [{"Path": path}]}})
        except urllib.error.HTTPError:
            pass
    req(f"{J}/Auth/Keys?App=oikos", method="POST", token=tok)
    keys = req(f"{J}/Auth/Keys", token=tok)["Items"]
    key = next((k["AccessToken"] for k in keys if k.get("AppName") == "oikos"), keys[-1]["AccessToken"] if keys else "")
    open(os.path.join(HERE, "jf.key"), "w").write(key)
    print(f"Jellyfin: libraries + API key -> homelab/jf.key ({key[:8]}...)")


# ---------------- Transmission ----------------
def setup_transmission():
    base = f"{HOST}:9091/transmission/rpc"
    wait(base, code=(200, 409))
    sid = ""
    try:
        urllib.request.urlopen(base, timeout=5)
    except urllib.error.HTTPError as e:
        sid = e.headers.get("X-Transmission-Session-Id", "")
    r = urllib.request.Request(base, method="POST",
                               headers={"X-Transmission-Session-Id": sid, "Content-Type": "application/json"},
                               data=json.dumps({"method": "session-set", "arguments": {
                                   "download-dir": "/media/downloads",
                                   "incomplete-dir": "/media/downloads/incomplete",
                                   "incomplete-dir-enabled": True}}).encode())
    urllib.request.urlopen(r, timeout=10)
    print("Transmission: download-dir -> /media/downloads")


# ---------------- arrs (root folder + download client) ----------------
def setup_arr(name):
    key = api_key(name)
    if not key:
        print(f"{name}: no API key (container running?), skipping"); return
    base = f"{HOST}:{PORT[name]}/api/v3"
    if not wait(f"{base}/system/status".replace("/api/v3", "") + "?apikey=" + key, secs=1) and \
       not wait(f"{HOST}:{PORT[name]}/", secs=60):
        pass
    # root folder
    if not any(r["path"] == ROOT[name] for r in req(f"{base}/rootfolder", key)):
        req(f"{base}/rootfolder", key, "POST", {"path": ROOT[name]})
    # download client (Transmission), schema-driven, with category + remove-completed
    if not any(c["implementation"] == "Transmission" for c in req(f"{base}/downloadclient", key)):
        tr = next(s for s in req(f"{base}/downloadclient/schema", key)
                  if s["implementation"] == "Transmission")
        f = {fl["name"]: fl.get("value") for fl in tr["fields"]}
        f["host"] = "transmission"; f["port"] = 9091; f["useSsl"] = False; f["urlBase"] = "/transmission/"
        for ck in ("category", "movieCategory", "tvCategory", "musicCategory"):
            if ck in f:
                f[ck] = CAT[name]
        req(f"{base}/downloadclient", key, "POST", {
            "enable": True, "protocol": "torrent", "priority": 1, "name": "Transmission",
            "implementation": tr["implementation"], "implementationName": tr["implementationName"],
            "configContract": tr["configContract"], "removeCompletedDownloads": True,
            "fields": [{"name": k, "value": v} for k, v in f.items()]})
    print(f"{name}: root folder + Transmission client (category '{CAT[name]}', remove-completed)")
    return key


# ---------------- Prowlarr (register arrs; optional indexers) ----------------
def setup_prowlarr(indexers):
    key = api_key("prowlarr")
    if not key:
        print("prowlarr: no API key, skipping"); return
    P = f"{HOST}:9696/api/v1"
    appsch = req(f"{P}/applications/schema", key)
    have = {a["name"] for a in req(f"{P}/applications", key)}
    for impl in ("Radarr", "Sonarr", "Lidarr"):
        if impl in have:
            continue
        arr = impl.lower()
        arrkey = api_key(arr)
        if not arrkey:
            continue
        s = next(x for x in appsch if x["implementation"] == impl)
        f = {fl["name"]: fl.get("value") for fl in s["fields"]}
        f["prowlarrUrl"] = "http://prowlarr:9696"; f["baseUrl"] = SVC[arr]; f["apiKey"] = arrkey
        try:
            req(f"{P}/applications", key, "POST", {
                "syncLevel": "fullSync", "name": impl, "implementation": s["implementation"],
                "implementationName": s["implementationName"], "configContract": s["configContract"],
                "fields": [{"name": k, "value": v} for k, v in f.items() if v is not None]})
            print(f"prowlarr: registered {impl}")
        except urllib.error.HTTPError as e:
            print(f"prowlarr: {impl} -> {e.code}")
    for defn in indexers:
        sch = req(f"{P}/indexer/schema", key)
        d = next((x for x in sch if x.get("definitionName", "").lower() == defn.lower()), None)
        if not d:
            print(f"prowlarr: indexer '{defn}' not found in schema"); continue
        f = {fl["name"]: fl.get("value") for fl in d["fields"]}
        try:
            req(f"{P}/indexer", key, "POST", {
                "enable": True, "name": d.get("name", defn), "implementation": d["implementation"],
                "implementationName": d["implementationName"], "configContract": d["configContract"],
                "protocol": d["protocol"], "appProfileId": 1, "priority": 25,
                "fields": [{"name": k, "value": v} for k, v in f.items() if v is not None], "tags": []})
            print(f"prowlarr: added indexer {defn}")
        except urllib.error.HTTPError as e:
            print(f"prowlarr: indexer {defn} -> {e.code} {e.read()[:120]}")
    req(f"{P}/command", key, "POST", {"name": "ApplicationIndexerSync"})


def main():
    indexers = sys.argv[1:]      # optional indexer definitionNames to add (e.g. thepiratebay)
    setup_jellyfin()
    setup_transmission()
    for arr in ("radarr", "sonarr", "lidarr"):
        setup_arr(arr)
    setup_prowlarr(indexers)
    print("\nDone. Left to do by hand:")
    print("  - Prowlarr: add your indexers (or re-run with names: stack-setup.py thepiratebay)")
    print("  - Bazarr: enable a language + profile + a subtitle provider (your account)")
    print("  - point OIKOS_JF_KEY_FILE at homelab/jf.key when running the hub")


if __name__ == "__main__":
    main()
