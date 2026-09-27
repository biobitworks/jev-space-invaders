# Security and submission secrecy

This repository is public because the UFA arena requires reproducibility. Public does not mean credentials or unrelated proprietary material may be committed.

Never commit API keys, access tokens, private registration payloads, `.env`, private prompts, patent-sensitive notes, or unrelated Vithia-family architecture.

Runtime credentials are loaded from environment variables or ignored local files only. Logs must never serialize authorization headers or raw secret values.

JEV receives the minimum bounded game state required for its decision. Public results contain measurements needed for judging and reproducibility, not private credentials or unrelated research state.
