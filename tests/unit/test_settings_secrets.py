from research_agent.config.settings import Settings


def test_api_key_is_secret_and_not_plaintext_in_repr() -> None:
    settings = Settings(llm_api_key="test-secret")

    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)
