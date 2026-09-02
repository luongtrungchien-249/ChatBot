/**
 * Cuong che 8 luat kien truc trong ARCHITECTURE.md section 1.
 * Chay: npm run lint:deps  (bat buoc trong CI)
 */
module.exports = {
  forbidden: [
    {
      name: 'agents-khong-biet-ha-tang',
      comment: 'L1: agents/ khong duoc import adapters, infra, llm, memory, knowledge.',
      severity: 'error',
      from: { path: '^src/agents' },
      to: { path: '^src/(adapters|infra|llm|memory|knowledge)' },
    },
    {
      name: 'agents-khong-doc-env',
      comment: 'L7: chi config/ duoc cham process.env.',
      severity: 'error',
      from: { path: '^src/(agents|adapters|memory|knowledge|llm|infra)' },
      to: { path: '^src/config/(?!index|schema|policy)' },
    },
    {
      name: 'adapter-khong-goi-adapter',
      comment: 'L5: moi adapter la mot hop kin.',
      severity: 'error',
      from: { path: '^src/adapters/([^/]+)/' },
      to: { path: '^src/adapters/(?!$1)([^/]+)/' },
    },
    {
      name: 'adapter-khong-goi-llm',
      comment: 'L5: adapter chi verify -> chuan hoa -> enqueue -> gui. Khong goi LLM, khong doc DB.',
      severity: 'error',
      from: { path: '^src/adapters' },
      to: { path: '^src/(llm|memory|knowledge)' },
    },
    {
      name: 'memory-fact-chi-o-repository',
      comment: 'L4: chi memory/repository/ duoc cham bang memory_fact.',
      severity: 'error',
      from: { pathNot: '^src/memory/repository' },
      to: { path: '^src/memory/repository/fact\.repo' },
    },
    {
      name: 'khong-phu-thuoc-vong',
      severity: 'error',
      from: {},
      to: { circular: true },
    },
    {
      name: 'khong-orphan',
      severity: 'warn',
      from: { orphan: true, pathNot: '^src/main/' },
      to: {},
    },
  ],
  options: {
    doNotFollow: { path: 'node_modules' },
    tsConfig: { fileName: 'tsconfig.json' },
    tsPreCompilationDeps: true,
  },
};
