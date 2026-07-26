#!/usr/bin/env bash
# Headless Jellyfin setup: runs the first-run wizard, adds Movies/Shows libraries,
# and creates an API key -> homelab/jf.key. Assumes Jellyfin from docker-compose.yml
# is already up on :8096. (stack-setup.py does this too, as part of the whole stack.)
set -euo pipefail
J=http://localhost:8096
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTH='MediaBrowser Client="oikos", Device="setup", DeviceId="oikos-setup", Version="1.0"'

echo -n "waiting for Jellyfin"
for _ in $(seq 1 60); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$J/System/Info/Public")" = "200" ] && break
  echo -n .; sleep 2
done; echo

if [ "$(curl -s "$J/System/Info/Public" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("StartupWizardCompleted"))')" != "True" ]; then
  echo "running setup wizard..."
  curl -s -X POST "$J/Startup/Configuration" -H 'Content-Type: application/json' \
    -d '{"UICulture":"en-US","MetadataCountryCode":"US","PreferredMetadataLanguage":"en"}' >/dev/null
  curl -s "$J/Startup/User" >/dev/null
  curl -s -X POST "$J/Startup/User" -H 'Content-Type: application/json' \
    -d '{"Name":"admin","Password":"devdev"}' >/dev/null
  curl -s -X POST "$J/Startup/RemoteAccess" -H 'Content-Type: application/json' \
    -d '{"EnableRemoteAccess":true,"EnableAutomaticPortMapping":false}' >/dev/null
  curl -s -X POST "$J/Startup/Complete" >/dev/null
fi

TOK=$(curl -s -X POST "$J/Users/AuthenticateByName" -H "X-Emby-Authorization: $AUTH" \
  -H 'Content-Type: application/json' -d '{"Username":"admin","Pw":"devdev"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["AccessToken"])')

for pair in "Movies:movies:/media/movies" "Shows:tvshows:/media/series"; do
  n=${pair%%:*}; rest=${pair#*:}; coll=${rest%%:*}; path=${rest#*:}
  curl -s -X POST "$J/Library/VirtualFolders?name=$n&collectionType=$coll&refreshLibrary=true" \
    -H "X-Emby-Token: $TOK" -H 'Content-Type: application/json' \
    -d "{\"LibraryOptions\":{\"PathInfos\":[{\"Path\":\"$path\"}]}}" >/dev/null || true
done

curl -s -X POST "$J/Auth/Keys?App=oikos" -H "X-Emby-Token: $TOK" >/dev/null || true
KEY=$(curl -s "$J/Auth/Keys" -H "X-Emby-Token: $TOK" \
  | python3 -c 'import sys,json;ks=json.load(sys.stdin)["Items"];print(next((k["AccessToken"] for k in ks if k.get("AppName")=="oikos"), ks[-1]["AccessToken"] if ks else ""))')
echo "$KEY" > "$HERE/jf.key"
echo "libraries + API key -> homelab/jf.key (${KEY:0:8}...)"
