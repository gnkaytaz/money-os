# MLX experiments

Use this after enough feedback has accumulated.

Candidate progression:
- 100-200 decisions: retrieval of similar corrections.
- 500+ decisions: prompt/evaluation optimization.
- 1,000-3,000 high-quality labeled examples: consider LoRA/QLoRA.

Do not train on `approve/reject` alone. Prefer downstream labels such as `test`, `paid`, and `paid_again`.
