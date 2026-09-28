from src.deciders import AdapterLLMDecider


def test_ollama_uses_custom_openai_compatible_provider():
    dec = AdapterLLMDecider(
        "ollama",
        "qwen2.5:0.5b",
        base_url="http://127.0.0.1:11434/v1",
    )
    try:
        assert dec.provider == "ollama"
        assert dec.requested_model == "qwen2.5:0.5b"
        assert dec.base_url == "http://127.0.0.1:11434/v1"
        assert dec._provider_instance is not None
        assert dec._provider_instance.model_name == "qwen2.5:0.5b"
        assert dec._provider_instance.api == "chat_completions"
        assert dec.llm_answer_mode == "discrete"
        assert dec.client.structured_outputs is True
        assert dec.client.n_retry_malformed_structure == 2
    finally:
        dec.close()
