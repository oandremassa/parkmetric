# Deploy do ParkMetric no Railway — guia rápido

Este repositório já está preparado para o Railway com Dockerfile, PostgreSQL obrigatório, migrações automáticas no startup, porta dinâmica e domínio Railway reconhecido automaticamente.

## No Railway

1. Crie um projeto novo.
2. Adicione **PostgreSQL**.
3. Adicione o repositório do ParkMetric como novo serviço.
4. No serviço da aplicação, abra **Variables** e use como base `.env.railway.example`.
5. Garanta que `DATABASE_URL` referencie o PostgreSQL do mesmo projeto:

   `DATABASE_URL=${{Postgres.DATABASE_URL}}`

6. Defina uma `SECRET_KEY` longa e única.
7. Para deixar a demonstração pronta no primeiro deploy, mantenha:

   - `DEMO_MODE=true`
   - `AUTO_SEED_DEMO=true`
   - `ALLOW_DEMO_RESET=false`
   - `DEMO_PASSWORD=<uma senha forte escolhida por você>`

8. Faça o deploy.
9. Em **Settings > Networking > Public Networking**, clique em **Generate Domain**.
10. Configure o Healthcheck Path como `/health/`.

## Login inicial

A senha é exatamente a definida em `DEMO_PASSWORD`.

- administrador: `demo_admin`
- gerente: `demo_manager`
- operador: `demo_operator`

## O que você não precisa configurar manualmente

- `PORT`: o Railway injeta automaticamente e o Gunicorn usa esse valor.
- domínio `*.railway.app`: o Django lê `RAILWAY_PUBLIC_DOMAIN` automaticamente.
- `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` para o domínio padrão do Railway.

Se depois você usar um domínio próprio, adicione `APP_PUBLIC_URL=https://seu-dominio`.
