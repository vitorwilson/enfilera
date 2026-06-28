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
uv run pytest                                         # roda a suíte de testes
```

O ponto de entrada do bot chega na Feature 4; até lá, `uv run pytest` é a
forma de exercitar o projeto.

## Faça um fork para o seu bandejão

O Enfilera foi feito para ser forkado: aponte-o para o *seu* restaurante
editando um único arquivo de configuração — filas, períodos de funcionamento,
centro e raio da geofence — e faça o deploy. Todo valor específico do bandejão
fica em `config/config.toml`; nada é fixado no código. Veja [`docs/`](docs/)
para o guia de fork e deploy.

## Como funciona

O algoritmo de estimativa, o modelo anti-abuso e o roadmap completo estão em
[`docs/PLAN.md`](docs/PLAN.md).
