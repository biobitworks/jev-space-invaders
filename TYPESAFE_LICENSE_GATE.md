# TypeSafe License Gate

State: ENFORCED_BEFORE_FIRST_JEV_EXECUTION

Sources:
- https://typesafe.ai/legal/mca
- https://docs.typesafe.ai/introduction/quickstart

## Hard gates

1. JEV Output is benchmark/evidence material only. It must not be used to distill, imitate, or train a competing/similar model.
2. JEV requests contain only the minimum game state required for the bounded decision. Do not send unrelated Vithia architecture, private prompts, or patent-sensitive design details.
3. Novel proprietary architecture must not be submitted as TypeSafe feedback without explicit review.
4. Do not assume permission to use TypeSafe names, logos, or brand assets beyond factual attribution required by the event or separately authorized materials.
5. Do not submit sensitive biomedical, patient, or regulated personal data through this competition integration.
6. Treat JEV Output as non-exclusive evidence. Do not represent it as TypeSafe-indemnified IP.

## Preflight

A JEV run may start only when all are true:
- API credential exists only in an ignored/runtime secret source.
- tracked files contain no secret value.
- outbound state schema has been reviewed for minimum disclosure.
- no training/distillation consumer reads JEV outputs.
- run logger preserves served model id, tokens, latency, retries/errors, confidence/probabilities, action, score, and fallback state when available.

Failure of any item => `LICENSE_GATE=FAIL`; do not call JEV.
