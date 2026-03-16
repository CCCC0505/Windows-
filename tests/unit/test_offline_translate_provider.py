from __future__ import annotations

import pytest

import app.providers.offline_translate_provider as offline_translate_provider


class _FakeTranslation:
    def __init__(self, source: str, target: str) -> None:
        self.source = source
        self.target = target

    def translate(self, text: str) -> str:
        return f"{self.source}->{self.target}:{text}"


class _FakeLanguage:
    def __init__(self, code: str, counter: dict[tuple[str, str], int]) -> None:
        self.code = code
        self._counter = counter

    def get_translation(self, target_lang: "_FakeLanguage") -> _FakeTranslation:
        key = (self.code, target_lang.code)
        self._counter[key] = self._counter.get(key, 0) + 1
        return _FakeTranslation(self.code, target_lang.code)


class _FakeTranslateModule:
    def __init__(self, counter: dict[tuple[str, str], int]) -> None:
        self._counter = counter
        self._langs = [
            _FakeLanguage("en", counter),
            _FakeLanguage("zh", counter),
            _FakeLanguage("ja", counter),
        ]

    def get_installed_languages(self):
        return self._langs


class _FakePackageModule:
    @staticmethod
    def install_from_path(_path: str) -> None:
        return


class _FakeArgos:
    def __init__(self, counter: dict[tuple[str, str], int]) -> None:
        self.translate = _FakeTranslateModule(counter)
        self.package = _FakePackageModule()


@pytest.mark.asyncio
async def test_offline_argos_translate_switches_target_language_at_runtime(monkeypatch) -> None:
    counter: dict[tuple[str, str], int] = {}
    monkeypatch.setattr(offline_translate_provider, "argostranslate", _FakeArgos(counter))

    provider = offline_translate_provider.OfflineArgosTranslateProvider(
        source_lang="en",
        target_lang="zh",
    )

    zh_text = await provider.translate("hello", source_lang="en", target_lang="zh")
    ja_text = await provider.translate("hello", source_lang="en", target_lang="ja")
    ja_again = await provider.translate("again", source_lang="en", target_lang="ja")

    assert zh_text == "en->zh:hello"
    assert ja_text == "en->ja:hello"
    assert ja_again == "en->ja:again"
    assert counter[("en", "zh")] == 1
    assert counter[("en", "ja")] == 1
