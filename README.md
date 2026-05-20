# Foco no Estudo

<p align="center">
  <img src="static/favicon.svg" alt="Foco no Estudo" width="92" height="92">
</p>

<h3 align="center">Contador local para acompanhar horas de estudo por projeto, disciplina e período.</h3>

<p align="center">
  <a href="#visão-geral">Visão geral</a> ·
  <a href="#recursos">Recursos</a> ·
  <a href="#instalação">Instalação</a> ·
  <a href="#backup">Backup</a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-local-003B57?style=for-the-badge&logo=sqlite&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?style=for-the-badge&logo=docker&logoColor=white">
</p>

---

## Visão Geral

O **Foco no Estudo** é uma aplicação web local para registrar tempo de estudo de forma simples, visual e persistente. Ela foi pensada para rodar em um servidor Ubuntu, notebook ou máquina doméstica, podendo ser acessada pelo navegador no próprio computador ou por outros dispositivos da rede local.

Com ela você acompanha:

- tempo estudado no dia;
- progresso da meta diária;
- progresso da meta total do projeto;
- distribuição de horas por disciplina;
- relatórios por dia, semana, mês e total;
- sessões salvas em banco SQLite local.

## Recursos

| Área | O que oferece |
| --- | --- |
| Timer | Início, pausa e troca de disciplina durante uma sessão |
| Disciplinas | Cadastro, edição, cores, ativação, desativação e exclusão |
| Metas | Meta diária em horas e meta total do projeto |
| Relatórios | Resumos por período, gráficos e participação por disciplina |
| Persistência | Banco SQLite salvo em `data/estudos.sqlite` |
| Deploy local | Execução direta com Python ou via Docker Compose |

## Preview da Experiência

```txt
Projeto
├── Meta diária
│   └── progresso do dia
├── Timer
│   ├── disciplina atual
│   └── iniciar / pausar
├── Relatórios
│   ├── dia
│   ├── semana
│   ├── mês
│   └── total
└── Configurações
    ├── projeto
    ├── metas
    └── disciplinas
```

## Tecnologias

- **Python 3.13** para o servidor HTTP e API local;
- **SQLite** para armazenamento das sessões;
- **HTML, CSS e JavaScript** no frontend;
- **Docker Compose** para execução isolada;
- sem dependências externas obrigatórias para rodar com Python direto.

## Estrutura do Projeto

```txt
.
├── app.py                 # Servidor, API e camada SQLite
├── static/
│   ├── index.html         # Interface principal
│   ├── styles.css         # Estilos da aplicação
│   ├── app.js             # Lógica do frontend
│   └── favicon.svg        # Ícone do projeto
├── data/                  # Banco local ignorado pelo Git
├── Dockerfile
├── docker-compose.yml
├── GUIA_INSTALACAO.md
├── GUIA_UTILIZACAO.md
└── README.md
```

## Instalação

### Opção 1: Docker Compose

Recomendado para deixar a aplicação rodando de forma isolada.

```bash
docker compose up -d --build
```

Acesse no navegador:

```txt
http://localhost:8000
```

Em outro dispositivo da mesma rede, use o IP da máquina onde o app está rodando:

```txt
http://IP_DO_SERVIDOR:8000
```

Para parar:

```bash
docker compose down
```

### Opção 2: Python Direto

Boa opção para desenvolvimento e testes rápidos.

```bash
python3 app.py
```

Acesse:

```txt
http://localhost:8000
```

## Como Usar

1. Abra o app no navegador.
2. Entre nas configurações.
3. Defina o nome do projeto.
4. Configure a meta diária e a meta total.
5. Cadastre as disciplinas.
6. Selecione uma disciplina.
7. Clique em iniciar e estude com o timer rodando.

Ao pausar, a sessão é salva no banco local e os relatórios são atualizados.

## Backup

Os dados ficam no arquivo:

```txt
data/estudos.sqlite
```

Antes de resetar o app ou mover a instalação para outra máquina, pare a aplicação e copie esse arquivo:

```bash
mkdir -p backups
cp data/estudos.sqlite backups/estudos-$(date +%F).sqlite
```

## Atualização

Depois de alterar arquivos do projeto, reinicie a aplicação.

Com Docker:

```bash
docker compose up -d --build
```

Com Python direto:

```bash
python3 app.py
```

## Observações

- O app foi projetado para uso local ou em rede doméstica.
- O banco SQLite não é enviado para o GitHub.
- A pasta `data/` fica ignorada para proteger os registros pessoais de estudo.
- Para detalhes de uso, veja [GUIA_UTILIZACAO.md](GUIA_UTILIZACAO.md).
- Para instalação passo a passo, veja [GUIA_INSTALACAO.md](GUIA_INSTALACAO.md).

---

<p align="center">
  Feito para transformar horas soltas de estudo em progresso visível.
</p>
