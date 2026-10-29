# ssh alias of the box running the hub and the stack
homelab := env("OIKOS_HOST", "homelab")

# Build the UI and install the hub on the homelab (console-hub.service)
deploy:
    cd hub/ui && pnpm build
    rsync -a hub/console-hub.py {{homelab}}:/opt/console-hub/
    rsync -a --delete hub/scripts/ {{homelab}}:/opt/console-hub/scripts/
    rsync -a --delete hub/ui/dist/ {{homelab}}:/opt/console-hub/dist/
    ssh {{homelab}} systemctl restart console-hub
    ssh {{homelab}} systemctl is-active console-hub

# Fast-forward the homelab checkout (compose files) to this branch
sync:
    git push {{homelab}}:oikos HEAD:refs/heads/desktop
    ssh {{homelab}} 'cd ~/oikos && git merge --ff-only desktop'
