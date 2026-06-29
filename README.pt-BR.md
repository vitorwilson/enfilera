# Enfilera

[English](README.md) · **Português (Brasil)**

**Vale a pena atravessar o campus pra fila do bandejão agora, ou é melhor
esperar?**

Enfilera é um bot de Telegram que coleta de forma colaborativa quanto tempo a
fila de um restaurante universitário (*bandejão*) realmente leva. Os
estudantes iniciam um cronômetro quando entram na fila e o param na catraca; o
bot transforma esses tempos de trajeto anônimos em uma única estimativa ao
vivo por fila — "~12 min" — para que a próxima pessoa saiba se vale ir agora
ou voltar mais tarde.

Estimativas separadas para cada fila (cartão / pix / …). Sem cadastro, sem
rastreamento, sem armazenar localização.

## Começando

```bash
uv sync                                              # instala as dependências
cp config/config.example.toml config/config.toml     # depois edite para o seu bandejão
export ENFILERA_BOT_TOKEN=...                         # token do bot, via @BotFather
uv run python -m enfilera                             # inicia o bot
```

O banco SQLite é criado na primeira execução (`enfilera.db` por padrão; mude
com `ENFILERA_DB`, e o caminho do config com `ENFILERA_CONFIG`). Rode os testes
com `uv run pytest`.

## Faça um fork para o seu bandejão

O Enfilera foi feito para ser forkado: aponte-o para o *seu* restaurante
editando um único arquivo de configuração — filas, períodos de funcionamento,
centro e raio da geofence — e faça o deploy com um comando que roda igual em um
Raspberry Pi, uma VPS ou no seu notebook:

```bash
cp config/config.example.toml config/config.toml     # edite para o seu bandejão
cp config/enfilera.env.example config/enfilera.env   # coloque o token do bot
bin/deploy                                           # docker compose up -d --build
```

Todo valor específico do bandejão fica em `config/config.toml`; nada é fixado
no código. Veja [`docs/DEPLOY.md`](docs/DEPLOY.md) para deploy remoto, operação
e backup/restauração do banco.

## Como funciona

O algoritmo de estimativa, o modelo anti-abuso e o roadmap completo estão em
[`docs/PLAN.md`](docs/PLAN.md).
