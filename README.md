# Chien_chatbot

Chatbot AI tra loi khi duoc mention trong nhom Zalo va Messenger, co RAG va memory.

## Tai lieu

| File | Noi dung |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | **Doc truoc.** Code nam o dau, ai duoc goi ai, schema DB, chi phi. |
| [docs/master-plan-chatbot.md](docs/master-plan-chatbot.md) | Lo trinh: lam gi, tuan nao. |
| [docs/dep-rules-verified.md](docs/dep-rules-verified.md) | Bang chung 7 luat kien truc thuc su bat duoc vi pham. |
| [docs/archive/](docs/archive/) | Ban ke hoach cu, giu de tra cuu. Da bi ARCHITECTURE.md thay the. |

## Chay lan dau

```bash
npm install                           # SDK da ghim, lockfile da commit
cp .env.example .env                  # dien OPENAI_API_KEY va DAILY_BUDGET_USD
docker compose -f ops/docker-compose.yml up -d postgres redis
npm run migrate
npm run dev:cli                       # chat voi bot qua terminal, chua can token Zalo/Meta
```

## Lenh

| Lenh | Lam gi |
|---|---|
| `npm run dev:cli` | REPL — adapter thu ba, dung de phat trien Phase 0 |
| `npm run dev:api` | Fastify: webhook Zalo + Meta |
| `npm run dev:worker` | BullMQ workers |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | unit + contract (khong can I/O) |
| `npm run test:int` | integration + security (can Docker) |
| `npm run guard:sql` | **Chan SQL cham `memory_fact` ngoai `memory/repository/`. Bat buoc trong CI.** |
| `npm run lint:deps` | **Cuong che 8 luat kien truc. Bat buoc trong CI.** |
| `npm run eval` | Bo 50 cau — chay moi khi doi prompt / chunking / model |

## Ba dieu de nham nhat

1. `src/agents/` khong duoc import `adapters/` `infra/` `llm/` `memory/` `knowledge/`.
   `npm run lint:deps` se bao do.
2. Moi truy van memory phai kem `ThreadScope`. Day la hang rao chong ro ri cross-group,
   khong phai toi uu hoa.
3. `SYSTEM_PROMPT` la hang so. Noi suy bien vao do lam hanh vi bot khong tai lap duoc
   va bo eval tuan 6 mat y nghia. Xem ARCHITECTURE.md section 7.1.
4. `gpt-5-mini` la model reasoning: dung `max_completion_tokens`, va token reasoning
   AN VAO cap do. Cap thap thi API tra ve content rong, khong nem loi nao.
