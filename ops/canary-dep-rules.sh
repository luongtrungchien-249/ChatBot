#!/usr/bin/env bash
# Canary: chung minh tung luat dependency-cruiser THUC SU bat duoc vi pham.
# Tao file vi pham -> chay depcruise -> luat phai xuat hien duoi dang error -> xoa file.
cd "c:/Users/PC ACER/OneDrive/Desktop/ChatBot" || exit 1

FILES=(
  src/agents/_canary1.ts
  src/config/_canary_secret.ts
  src/agents/_canary2.ts
  src/adapters/cli/_canary3.ts
  src/adapters/cli/_canary4.ts
  src/knowledge/_canary5.ts
  src/shared/_canary6a.ts
  src/shared/_canary6b.ts
)
cleanup() { rm -f "${FILES[@]}"; }
trap cleanup EXIT

# L1: agents -> infra
echo "import '../infra/logger.js'; export {};" > src/agents/_canary1.ts
# L7: agents -> config/<file khac index|schema|policy>
echo "export const secret = 1;" > src/config/_canary_secret.ts
echo "import { secret } from '../config/_canary_secret.js'; export const x = secret;" > src/agents/_canary2.ts
# L5a: adapter -> adapter khac
echo "import '../zalo-bot/send.js'; export {};" > src/adapters/cli/_canary3.ts
# L5b: adapter -> llm
echo "import '../../llm/models.js'; export {};" > src/adapters/cli/_canary4.ts
# L4: ngoai repository -> fact.repo
echo "import '../memory/repository/fact.repo.js'; export {};" > src/knowledge/_canary5.ts
# Vong tron
echo "import './_canary6b.js'; export const a = 1;" > src/shared/_canary6a.ts
echo "import './_canary6a.js'; export const b = 1;" > src/shared/_canary6b.ts

OUT=$(npx depcruise src --config .dependency-cruiser.cjs 2>&1)

echo "$OUT" | grep -E '^\s*(error|warn)' | sed 's/\x1b\[[0-9;]*m//g' | sort -u > /tmp/canary-hits.txt

for rule in agents-khong-biet-ha-tang agents-khong-doc-env adapter-khong-goi-adapter \
            adapter-khong-goi-llm memory-fact-chi-o-repository khong-phu-thuoc-vong khong-orphan; do
  if echo "$OUT" | sed 's/\x1b\[[0-9;]*m//g' | grep -q "$rule"; then
    echo "SONG   $rule"
  else
    echo "CHET   $rule   <-- luat nay khong bat duoc gi"
  fi
done

echo "--- tong ket depcruise ---"
echo "$OUT" | sed 's/\x1b\[[0-9;]*m//g' | grep -E 'dependency violations'
