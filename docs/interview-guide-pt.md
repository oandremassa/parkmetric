# Guia de estudo para entrevista — ParkMetric

## Como explicar o projeto em 30 segundos

O ParkMetric é uma aplicação Django com PostgreSQL para uma organização que administra vários estacionamentos. Eu separei operação em tempo real de análise histórica. O fluxo mais importante é entrada → permanência → cálculo → pagamento simulado → saída. Usei transações e restrições do PostgreSQL para evitar duas entradas pegarem a mesma vaga e para impedir duplicidade de operações.

## O que você precisa saber explicar

### Por que Django + PostgreSQL?

Django resolve autenticação, formulários, segurança, ORM, templates e API de forma organizada. PostgreSQL foi importante porque o projeto não é só CRUD: há concorrência real, `SELECT FOR UPDATE`, restrições parciais e transações atômicas. SQLite não representaria corretamente esses testes.

### O que é uma transação atômica?

É uma sequência de alterações que deve acontecer inteira ou não acontecer. Na saída, por exemplo, não posso registrar um pagamento e falhar antes de fechar a estadia/liberar a vaga. O bloco `transaction.atomic()` garante rollback se ocorrer um erro.

### Como evitei duas pessoas ocuparem a mesma vaga?

Na entrada automática, a consulta trava uma vaga livre usando `select_for_update(skip_locked=True)`. Em paralelo, o banco também tem uma restrição que permite no máximo uma estadia ativa por vaga. Assim há uma proteção na lógica e outra na integridade do banco.

### O que é idempotência?

É a propriedade de repetir a mesma requisição sem duplicar a operação. Uma chave de idempotência é associada ao usuário, unidade, tipo da operação e conteúdo da requisição. Se a mesma chamada for repetida, devolvo o resultado original. Se a chave for reutilizada com conteúdo diferente, rejeito.

### Como funciona a tarifa?

Existe tolerância, duração do intervalo, preço por intervalo e teto por cada janela de 24 horas. Se passar da tolerância, o tempo total passa a ser cobrado e cada intervalo iniciado arredonda para cima. Cada estadia guarda a versão da tarifa do momento da entrada.

### Por que `Decimal`?

`float` representa números binários e pode produzir erros de precisão em dinheiro. `Decimal` permite cálculo decimal previsível e arredondamento para centavos.

### Como tratei horário de verão?

O tempo decorrido é medido entre instantes UTC. Para exibição e filtros de calendário uso o fuso IANA da unidade, por exemplo `Europe/Berlin`. Assim uma mudança de horário de verão não altera artificialmente a duração real.

### Qual é a diferença entre autenticação e autorização?

Autenticação responde “quem é o usuário?”. Autorização responde “o que esse usuário pode fazer?”. Não basta esconder um botão. O backend restringe páginas, objetos, API, buscas e exportações conforme o perfil e as unidades atribuídas.

### O que é versionamento de tarifa?

Quando o preço muda eu crio uma nova linha/versão e encerro a anterior. Não edito a versão antiga usada por estadias existentes. Isso preserva a explicação de como um valor histórico foi calculado.

### Por que o pagamento é simulado?

Integração financeira real está fora do escopo. O simulador permite testar sucesso e falha sem fingir que existe uma adquirente/gateway. A lógica de preço é independente do simulador, e os recibos começam com `SIM-`.

## Perguntas que podem aparecer

**“O que você melhoraria para produção real?”**  
Eu validaria a infraestrutura concreta: secrets manager, TLS/proxy, observabilidade, alertas, alta disponibilidade do PostgreSQL, backups com restore drill, políticas de retenção/privacidade, testes de carga e integração com um provedor real de pagamento, se fosse necessário.

**“Por que não microserviços?”**  
O domínio atual cabe bem em um monólito modular e precisa de transações fortes. Microserviços aumentariam complexidade de rede, consistência e operação sem benefício proporcional.

**“Dashboard é dado fixo?”**  
Não. Os indicadores são consultas sobre entradas, saídas e pagamentos persistidos. O gerador de demonstração apenas cria dados sintéticos determinísticos.

**“Qual parte é mais sênior?”**  
Evite responder apenas “a interface”. Destaque integridade, concorrência, idempotência, autorização por unidade, histórico imutável, versionamento de tarifa, semântica de datas e evidência de validação.

## Limite que você deve assumir com transparência

Neste pacote, a validação executada no ambiente de geração ficou limitada porque não havia servidor PostgreSQL/Docker nem acesso funcional ao índice de pacotes para instalar Django. A suíte para PostgreSQL e o CI estão implementados, mas você só deve dizer que “todos os testes passaram” depois de executá-los no seu Mac/CI e conferir o resultado.
