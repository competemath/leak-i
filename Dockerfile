FROM ubuntu:22.04

RUN useradd -m -u 1000 user
RUN apt-get update && apt-get install -y \
    curl git build-essential python3 python3-pip python3-venv zstd && \
    rm -rf /var/lib/apt/lists/*

USER user
ENV HOME=/home/user
ENV PATH="${HOME}/.local/bin:${HOME}/.elan/bin:${PATH}"
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
WORKDIR ${HOME}

# The environment loogle indexes is the Tengoku tree — one self-contained Lean 4
# library seeded from Mathlib and other open libraries, plus every verified
# addition. The image carries only the clone (scripts/pin.sh, the lakefile, the
# toolchain): the BUILT tree is pinned to its newest published build cache when
# the container starts (server.py _startup -> tengoku_sync), because the built tree
# no longer fits in an image the Space builder can push (2026-10-16: OOMKilled at
# "Pushing image", exit 137, with the tree pinned in a layer).
# Changing TENGOKU_REFRESH (the installer passes the time) re-clones on a
# rebuild instead of reusing a stale cached clone layer.
ARG TENGOKU_REFRESH=0
# Which tree this service follows, and whether it follows the per-merge top-ups (1) or only the
# nightly cache (0). Both are Space VARIABLES: Hugging Face passes them in as build args and as
# runtime env, so moving the service to another tree is a variable change plus a factory rebuild.
ARG TENGOKU_REPO=competemath/tengoku
ARG TENGOKU_TOPUPS=1
ENV TENGOKU_REPO=${TENGOKU_REPO}
ENV TENGOKU_TOPUPS=${TENGOKU_TOPUPS}
RUN echo "refresh ${TENGOKU_REFRESH}" >/dev/null && git clone --filter=blob:none https://github.com/${TENGOKU_REPO}.git tengoku
ENV TENGOKU_DIR=${HOME}/tengoku

# loogle, built against the tree instead of Mathlib. loogle-tengoku.patch swaps
# its one dependency for the tree (a path dependency, ../tengoku) and renames
# the five import lines (Mathlib -> Tengoku, Batteries.X -> Tengoku.Std.X).
RUN git clone https://github.com/nomeata/loogle.git && cd loogle && git checkout -q ceaefdb
COPY --chown=user loogle-tengoku.patch loogle_imports.py ${HOME}/loogle/
WORKDIR ${HOME}/loogle
# The patch names the tree's Batteries copy as Tengoku.Std.X (the tree before its seed move); loogle_imports.py sets the names from the cloned tree (Tengoku.Seed.Std.X now), the same
# step server.py runs before every build of loogle. loogle is built at run time, after the tree is pinned (it imports the tree's built files): not here.
RUN git apply loogle-tengoku.patch && python3 loogle_imports.py . ../tengoku && cp ../tengoku/lean-toolchain lean-toolchain && lake update

# Python app (the MCP server; torch/sentence-transformers serve moogle)
WORKDIR ${HOME}/app
COPY --chown=user . ${HOME}/app
RUN uv python install 3.11
RUN uv venv --python 3.11 ${HOME}/app/.venv
ENV PATH="${HOME}/app/.venv/bin:${PATH}"
RUN uv pip install torch --index-url https://download.pytorch.org/whl/cpu
RUN uv pip install fastmcp "mcp<2" asyncio nest_asyncio chromadb sentence-transformers

EXPOSE 7860
CMD ["python3", "server.py"]
