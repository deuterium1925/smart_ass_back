# How to start

### requirements

- docker or podman compose on your machine

### preparation

- create `.env` file from example:
  ```bash
  cp .env.example .env
  ```
- add your API key to `MWS_API_KEY` variable

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