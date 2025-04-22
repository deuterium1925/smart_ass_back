# How to start

### requirements

- docker or podman compose on your machine

### preparation

- create `.env` file from example:
  ```bash
  cp .env.example .env
  ```
- add your API key to `MWS_API_KEY` variable
<<<<<<< HEAD
- copy default nginx config from folder to /etc/nginx/sites-available/default
=======

### run compose

```bash
podman compose up -d
```

### misc

- Restart backend:

```bash
podman compose -f ~/mts_hackathon/docker-compose.yaml restart backend
```

- Restart backend with rebuild:

```bash
podman compose -f ~/mts_hackathon/docker-compose.yaml down backend && podman compose -f ~/mts_hackathon/docker-compose.yaml up backend -d --build --remove-orphans
```

- Restart backend with rebuild without stopping:

```bash
podman compose -f ~/mts_hackathon/docker-compose.yaml up -d --build --force-recreate
```

# Install NixOS with a single command

### requirements

- nix package manager on your machine with enabled `flakes` and `nix-commands`
- it is assumed that there is some linux already installed on the server

### preparation

- remove `nix/hw-config.nix` file, it will be generated during installation
- modify `disko` option in the `nix/configuration.nix` file according to the
  desired disk layout
- configure root ssh access on target

### install

```bash
nix develop -c nixos-anywhere \
    --generate-hardware-config nixos-generate-config nix/hw-config.nix \
    --flake .#nixos \
    --ssh-option "PasswordAuthentication=no" \
    --target-host "root@<ip>"
```
