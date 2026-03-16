# Release Checklist

## 1) Environment

- [ ] Windows 10/11 machine prepared
- [ ] `.venv` exists and dependencies installed
- [ ] `config.toml` present

## 2) Quality Gate

- [ ] `.\.venv\Scripts\python -m pytest -q` passes
- [ ] `.\.venv\Scripts\python -m compileall app tests` passes
- [ ] Manual smoke run works (`python -m app.main`)

## 3) Runtime Validation

- [ ] Start/Stop button works
- [ ] System audio capture works (WASAPI loopback / Stereo Mix)
- [ ] Source model switching (`en` / `zh`) works
- [ ] Target language switching works
- [ ] Translation backend unavailable fallback shows passthrough transcript (STT still usable)
- [ ] TXT/SRT export works

## 4) Packaging

- [ ] `powershell -ExecutionPolicy Bypass -File .\build_release.ps1` succeeds
- [ ] Build output exists in `dist\`
- [ ] Packaged app launches and can start a session

## 5) Startup and Shortcut

- [ ] Desktop shortcut script works (`create_desktop_shortcut.ps1`)
- [ ] Startup shortcut script works (`create_startup_shortcut.ps1`)
- [ ] Startup disable flow works (`create_startup_shortcut.ps1 -Disable`)

## 6) Deliverables

- [ ] `README.md` is up to date
- [ ] `config.example.toml` matches runtime fields
- [ ] Release artifacts archived (`dist\` output + config template)
