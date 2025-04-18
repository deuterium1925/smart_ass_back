# yes, it's insecure, but it's a server for just 3 days - why not?
export NIX_SSHOPTS := "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ConnectTimeout=10"

deploy:
  @passh -c 3 \
    -C \
    -p "$(age -i "$HOME/.ssh/id_ed25519" -d user_password.age)" \
    -P '\[sudo\] password' \
    nixos-rebuild switch --fast --use-remote-sudo --flake . --target-host ahmed@82.97.248.178

ssh *args:
  @ssh {{NIX_SSHOPTS}} ahmed@82.97.248.178 {{args}}
