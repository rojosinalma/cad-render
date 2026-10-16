# Python 3.12 (build123d/OCP) + Ruby (Roda) in one image; the Python env lives outside /app so a
# development mount of the project does not hide it.
FROM python:3.12.15-slim-trixie
ARG TARGETARCH

COPY --from=ghcr.io/astral-sh/uv:0.9.23 /uv /uvx /bin/

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ruby ruby-dev build-essential ca-certificates curl \
        libgl1 libglu1-mesa libxrender1 libxext6 libx11-6 libsm6 libice6 libxi6 libfontconfig1 && \
    rm -rf /var/lib/apt/lists/*

# Zoo CLI: turns the copilot's KCL into STEP/STL via Zoo's Engine API (pinned, checksum verified,
# one static musl binary per architecture).
ARG ZOO_CLI_VERSION=v0.2.202
ARG ZOO_CLI_SHA256_AMD64=fef7f6d82beabf6262faaf243668d5154667925b16c34af7c45a567e172b12e1
ARG ZOO_CLI_SHA256_ARM64=b1828d4f2c2b95ba6fe27ca59acf354155f54faac6a932686d94b623fc5fa424
RUN case "${TARGETARCH:-amd64}" in \
      amd64) triple=x86_64-unknown-linux-musl; sha="${ZOO_CLI_SHA256_AMD64}" ;; \
      arm64) triple=aarch64-unknown-linux-musl; sha="${ZOO_CLI_SHA256_ARM64}" ;; \
      *) echo "unsupported TARGETARCH ${TARGETARCH}" >&2; exit 1 ;; \
    esac && \
    curl -fsSL -o /usr/local/bin/zoo \
      "https://github.com/KittyCAD/cli/releases/download/${ZOO_CLI_VERSION}/zoo-${triple}" && \
    echo "${sha}  /usr/local/bin/zoo" | sha256sum -c - && \
    chmod +x /usr/local/bin/zoo

ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/opt/venv/bin:${PATH}"

COPY Gemfile Gemfile.lock ./
RUN gem install bundler --no-document && bundle install

COPY . .

LABEL org.opencontainers.image.source="https://github.com/rojosinalma/cad-render" \
      org.opencontainers.image.description="Headless B-rep CAD service: build123d scripts to STL/STEP/3MF/PNG, mesh convert/repair, Zoo text-to-CAD" \
      org.opencontainers.image.licenses="MIT"

RUN useradd -u 1000 -m -s /bin/sh cad
USER 1000
ENV LANG=C.UTF-8 HOME=/tmp
EXPOSE 9292
ENTRYPOINT ["/app/bin/entrypoint"]
