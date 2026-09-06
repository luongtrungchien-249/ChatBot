# Mot image, ba lenh chay (api / worker / zalo) — xem docker-compose.yml.
# Khong co buoc build: Python khong bien dich, va giao dien web gio la Jinja2 +
# JavaScript thuan nen cung khong can bundler.

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app
ENV NODE_ENV=production \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Cai phu thuoc TRUOC khi copy ma nguon: sua mot dong code khong lam mat cache lop
# nay, va cai lai ca cay phu thuoc la phan cham nhat cua build.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY db ./db
# Cai chinh du an (10 goi trong src/) sau cung.
RUN uv sync --frozen --no-dev

# Khong chay bang root: mot lo hong trong FastAPI khong duoc phep thanh quyen root
# trong container.
RUN useradd --create-home --uid 10001 bot && chown -R bot /app
USER bot

CMD ["uv", "run", "python", "-m", "main.api"]
