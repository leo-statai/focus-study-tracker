# Guia Rápido de Instalação

Este app roda localmente em um servidor Ubuntu e pode ser acessado pela rede doméstica.

## Opção 1: Docker

Recomendado para manter o ambiente isolado.

### 1. Entrar na pasta do projeto

```bash
cd /home/leonardo/01_codigos/contador_estudos
```

### 2. Subir a aplicação

```bash
docker compose up -d --build
```

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

### 4. Parar a aplicação

```bash
docker compose down
```

## Opção 2: Python direto

Útil para desenvolvimento ou testes rápidos.

### 1. Entrar na pasta do projeto

```bash
cd /home/leonardo/01_codigos/contador_estudos
```

### 2. Rodar o servidor

```bash
python3 app.py
```

### 3. Acessar

```txt
http://localhost:8000
```

## Dados e Backup

O banco SQLite fica em:

```txt
data/estudos.sqlite
```

Para fazer backup, copie esse arquivo com a aplicação parada:

```bash
cp data/estudos.sqlite backups/estudos-$(date +%F).sqlite
```

Se a pasta `backups` ainda não existir:

```bash
mkdir -p backups
```

## Atualização

Após alterar arquivos do projeto, reinicie a aplicação.

Com Docker:

```bash
docker compose up -d --build
```

Com Python direto:

```bash
python3 app.py
```
