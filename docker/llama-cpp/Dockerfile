FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        ninja-build \
        git \
        libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

ENV CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS"
ENV FORCE_CMAKE=1

RUN pip install --no-cache-dir "llama-cpp-python[server]"
