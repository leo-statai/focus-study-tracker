# Guia Rápido de Instalação

Este app roda localmente em um servidor (Ubuntu ou similar) e pode ser acessado pela rede doméstica. A forma recomendada de execução é via **Docker**.

## Opção 1: Docker (recomendado)

### 1. Entrar na pasta do projeto

```bash
cd focus-study-tracker
```

### 2. Subir a aplicação

```bash
docker compose up -d --build
```

O container reinicia sozinho em caso de queda ou reboot do servidor (`restart: unless-stopped`) e tem healthcheck — o `docker ps` mostra se o app está respondendo de verdade.

### 3. Acessar no navegador

No próprio servidor:

```txt
http://localhost:8000
```

Em outro dispositivo da rede:

```txt
http://IP_DO_SERVIDOR:8000
```

Exemplo:

```txt
http://192.168.1.50:8000
```

### 4. Ver os logs

```bash
docker logs -f contador-estudos
```

### 5. Parar a aplicação

```bash
docker compose down
```

## Opção 2: Python direto

Útil para desenvolvimento ou testes rápidos. Não há dependências para instalar.

```bash
cd focus-study-tracker
python3 app.py
```

Acesse `http://localhost:8000`.

## Dados e Backup

O banco SQLite fica em `data/estudos.sqlite` — o **mesmo arquivo** é usado rodando via Docker (montado em `/data` no container) ou via Python direto.

Para fazer backup, copie esse arquivo com a aplicação parada:

```bash
mkdir -p backups
cp data/estudos.sqlite backups/estudos-$(date +%F).sqlite
```

## Atualização

Após alterar arquivos do projeto:

```bash
docker compose up -d --build
```

Com Python direto, basta reiniciar o `python3 app.py`.
