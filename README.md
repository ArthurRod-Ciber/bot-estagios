# vagas-estagio-bot

Bot que procura vagas de **estágio em cibersegurança, redes, infraestrutura e IA** de hora em hora e manda um resumo por e-mail **só quando aparece vaga nova**.

Roda de graça no **GitHub Actions**: não precisa de servidor nem deixar o PC ligado.

## O que ele faz

1. Consulta fontes públicas: **Gupy** (vagas brasileiras), **Greenhouse** e **Lever** (páginas oficiais de carreira das empresas) e **Remotive** (vagas remotas).
2. Filtra: precisa ser estágio, da área, e **remota** (que aceite o Brasil) ou **híbrida em Uberlândia**.
3. Descarta vagas com prazo de inscrição vencido.
4. Sinaliza o que não está claro: país não informado, exigência de visto/autorização de trabalho, período mínimo, requisitos não encontrados, link de agregador.
5. Guarda as vagas já enviadas em `data/seen.json` e só manda e-mail se houver novidade.

## Configuração (uns 10 minutos)

### 1. Senha de app do Gmail
A conta precisa ter verificação em duas etapas ativada.
Acesse https://myaccount.google.com/apppasswords, crie uma senha de app (ex.: "vagas-bot") e copie os 16 caracteres.

### 2. Suba o projeto no GitHub
Crie um repositório (ex.: `vagas-estagio-bot`) e envie esta pasta.

### 3. Cadastre os secrets
No repositório: **Settings → Secrets and variables → Actions → New repository secret**

| Nome | Valor |
|---|---|
| `SMTP_USER` | seu Gmail que envia |
| `SMTP_PASSWORD` | a senha de app (sem espaços) |
| `EMAIL_TO` | e-mail que recebe as vagas |

O e-mail fica nos secrets, então não aparece no código mesmo com repositório público.

### 4. Teste
Aba **Actions → Buscar vagas de estágio → Run workflow**. Depois disso roda sozinho de hora em hora.

Se o passo "Salvar vagas já vistas" falhar com erro de permissão: **Settings → Actions → General → Workflow permissions → Read and write permissions**.

## Rodar localmente
```bash
pip install -r requirements.txt
python -m bot.main --dry-run   # imprime no terminal, não envia nem salva
python -m pytest -q            # testes do filtro
```

## Personalizar
Tudo em `config.yaml`: palavras-chave, exclusões, cidades, termos de busca e empresas.
Para acompanhar uma empresa, descubra se a página de vagas dela é `boards.greenhouse.io/NOME` ou `jobs.lever.co/NOME` e adicione `NOME` na lista correspondente. Empresa com nome errado só gera um aviso no log.

## Observações
- As APIs de Gupy, Greenhouse, Lever e Remotive são públicas, mas não são garantidas; se alguma mudar, as outras continuam funcionando.
- O agendamento do GitHub pode atrasar alguns minutos em horários de pico.
- Em repositório público, o GitHub pode pausar workflows agendados após 60 dias sem atividade no repositório; se acontecer, é só reativar na aba Actions.
- Estágio ainda exige conferir o edital: o bot filtra e sinaliza, mas a decisão é sua.

## Estrutura
```
bot/fontes.py       coletores de cada site
bot/filtro.py       regras de área, local, prazo e alertas
bot/email_envio.py  monta e envia o e-mail (HTML + texto)
bot/main.py         orquestra e guarda o estado
config.yaml         suas preferências
.github/workflows/  agendamento de hora em hora
```
