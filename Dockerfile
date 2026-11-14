# syntax=docker/dockerfile:1

ARG LLAMA_CPP_COMMIT=61dbf49228c8a96b72e40c89d93cb7c003411f8c

FROM ubuntu:24.04 AS build

ARG LLAMA_CPP_COMMIT
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates cmake git \
    && git clone --filter=blob:none https://github.com/ggml-org/llama.cpp.git /src/llama.cpp \
    && git -C /src/llama.cpp checkout --detach "${LLAMA_CPP_COMMIT}" \
    && test "$(git -C /src/llama.cpp rev-parse HEAD)" = "${LLAMA_CPP_COMMIT}"

WORKDIR /src/llama.cpp

# Ivy Bridge baseline: AVX and F16C are available, while AVX2/FMA/BMI2 are not.
# The -mno-* flags are deliberately repeated at compiler level as a safety belt.
RUN cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_C_FLAGS_RELEASE="-O3 -DNDEBUG -march=ivybridge -mno-avx2 -mno-fma -mno-bmi -mno-bmi2" \
        -DCMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG -march=ivybridge -mno-avx2 -mno-fma -mno-bmi -mno-bmi2" \
        -DGGML_NATIVE=OFF \
        -DGGML_SSE42=ON \
        -DGGML_AVX=ON \
        -DGGML_F16C=ON \
        -DGGML_AVX_VNNI=OFF \
        -DGGML_AVX2=OFF \
        -DGGML_FMA=OFF \
        -DGGML_BMI2=OFF \
        -DGGML_AVX512=OFF \
        -DGGML_AVX512_VBMI=OFF \
        -DGGML_AVX512_VNNI=OFF \
        -DGGML_AVX512_BF16=OFF \
        -DGGML_AMX_TILE=OFF \
        -DGGML_AMX_INT8=OFF \
        -DGGML_AMX_BF16=OFF \
        -DGGML_CUDA=OFF \
        -DGGML_VULKAN=OFF \
        -DGGML_OPENCL=OFF \
        -DLLAMA_BUILD_TESTS=OFF \
        -DBUILD_SHARED_LIBS=OFF \
        -DLLAMA_BUILD_EXAMPLES=OFF \
        -DLLAMA_BUILD_SERVER=ON \
        -DLLAMA_BUILD_UI=ON \
    && cmake --build build --config Release --parallel 2 \
        --target llama-server \
    && mkdir -p /out/bin /out/lib /out/share \
    && cp build/bin/llama-server /out/bin/ \
    && find build -type f -name '*.so*' -exec cp -a {} /out/lib/ \; \
    && printf '%s\n' \
        "llama.cpp commit: ${LLAMA_CPP_COMMIT}" \
        'GGML_NATIVE=OFF GGML_SSE42=ON GGML_AVX=ON GGML_F16C=ON' \
        'GGML_AVX2=OFF GGML_FMA=OFF GGML_BMI2=OFF CPU-only' \
        'compiler baseline: -march=ivybridge -mno-avx2 -mno-fma -mno-bmi -mno-bmi2' \
        > /out/share/llama-build-info.txt

FROM ubuntu:24.04 AS runtime

ARG LLAMA_CPP_COMMIT
LABEL org.opencontainers.image.title="Argo Forge llama.cpp server for Ivy Bridge" \
      org.opencontainers.image.source="https://github.com/ggml-org/llama.cpp" \
      org.opencontainers.image.revision="${LLAMA_CPP_COMMIT}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libgomp1 \
    && apt-get clean \
    && find /var/lib/apt/lists -type f -delete

COPY --from=build /out/bin/ /usr/local/bin/
COPY --from=build /out/lib/ /usr/local/lib/
COPY --from=build /out/share/llama-build-info.txt /usr/local/share/llama-build-info.txt
RUN ldconfig

EXPOSE 8080
ENTRYPOINT ["llama-server"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
