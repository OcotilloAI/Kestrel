# Model Selection Guidance (GB10)

This note summarizes model/quant tradeoffs for GB10 and recommends a default.

## Targets
- **Primary**: Qwen3-Coder 30B/32B, Q4 quantization, llama.cpp backend.
- **Constraint**: GB10 memory budget (GPU VRAM + host RAM).

## A3B (MoE) vs Dense
- **A3B (MoE)**: Smaller *active* parameters per token, typically lower VRAM pressure and faster token processing when offloaded; good for GB10 headroom.
- **Dense 32B**: Higher active parameters per token; tends to be heavier on VRAM and slower at similar quant levels.

## Quantization Notes
- **Q4_K_M** is a strong quality/size balance for code models on constrained GPUs.
- Larger contexts (e.g., 128k/256k) significantly increase KV cache use; this can dominate memory.

## Recommendation
1) **Default**: Qwen3-Coder A3B Q4_K_M.
2) **Fallback**: If A3B is unavailable or unstable, use dense Q4_K_M with reduced context.
3) **When memory pressure occurs**: lower `n_ctx` first, then reduce GPU offload layers.

## Operational Checklist
- Verify model file size and GGUF compatibility.
- Start with moderate `n_ctx` (e.g., 32k–64k) and increase only if stable.
- If you see OOM or heavy paging, reduce `n_ctx` or offload layers.

