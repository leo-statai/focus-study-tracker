# Foco no Estudo

Web app local para controlar horas de estudo por projeto e disciplina.

## Rodar com Python

```bash
python3 app.py
```

Acesse:

```txt
http://localhost:8000
```

## Rodar em Docker

```bash
docker compose up -d --build
```

Em outro computador da rede doméstica, acesse pelo IP do servidor Ubuntu:

```txt
http://IP_DO_SERVIDOR:8000
```

## Dados

O banco SQLite fica em:

```txt
data/estudos.sqlite
```

Para backup, copie esse arquivo com o app pausado ou depois de interromper o container.
