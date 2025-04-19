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
