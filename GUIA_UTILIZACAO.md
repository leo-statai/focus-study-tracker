# Guia Rápido de Utilização

O Contador de Estudos registra o tempo total estudado e separa esse tempo por disciplina.

## Tela Principal

Na tela inicial você verá:

- velocímetro da meta diária
- tempo estudado hoje
- disciplina atual
- botão para iniciar ou pausar o timer
- resumo de horas por disciplina
- progresso da meta total do projeto
- gráficos por dia e por disciplina

## Primeiro Uso

1. Abra o app no navegador.
2. Clique no botão de configurações.
3. Defina o nome do projeto.
4. Informe a meta diária em horas.
5. Informe a meta total em horas.
6. Cadastre, edite ou exclua disciplinas.
7. Clique em **Salvar**.

## Iniciar um Estudo

1. Selecione a disciplina que será estudada.
2. Clique em **Iniciar**.
3. O tempo começará a contar para a meta diária e para a disciplina selecionada.

O timer só inicia se houver uma disciplina selecionada.

## Pausar

Clique em **Pausar**.

O app salva a sessão no banco de dados e atualiza os resumos.

## Trocar de Disciplina

Enquanto o timer estiver rodando:

1. Abra o seletor de disciplina.
2. Escolha outra disciplina.

O app encerra a sessão da disciplina anterior e inicia uma nova sessão para a disciplina escolhida.

## Ver Resumos

Use os botões de período na área de resumo:

- **Dia**
- **Semana**
- **Mês**
- **Total**

Os gráficos mostram:

- horas estudadas por dia
- distribuição por disciplina
- tabela com horas e participação percentual

## Configurações

Nas configurações você pode:

- alterar o nome do projeto
- alterar a meta diária
- alterar a meta total
- adicionar disciplinas
- editar nomes e cores das disciplinas
- ativar ou desativar disciplinas
- excluir disciplinas
- resetar todo o app

## Excluir Disciplina

Na tela de configurações, use o botão de exclusão da disciplina.

Atenção: ao excluir uma disciplina, as sessões registradas nela também são removidas.

## Resetar Tudo

Na tela de configurações, clique em **Resetar tudo**.

Isso apaga o banco atual e recria o app com o projeto e disciplinas iniciais.

Use essa opção somente se quiser começar do zero.

## Backup Recomendado

Antes de resetar ou fazer mudanças importantes, faça backup do arquivo:

```txt
data/estudos.sqlite
```
