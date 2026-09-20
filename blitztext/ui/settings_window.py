"""
Settings window — tabbed UI.
Tabs: API-Zugänge | Workflows | Hotkeys | Erweitert
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QFormLayout, QComboBox, QCheckBox,
    QTextEdit, QGroupBox, QScrollArea, QSizePolicy, QFrame,
    QSpinBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ..services.settings import (
    AppSettings, save_settings,
    STTProvider, LLMProvider, WorkflowModelConfig, LLM_MODEL_PRESETS,
    get_api_key, set_api_key, masked,
    KEY_OPENAI, KEY_GROQ, KEY_ANTHROPIC, KEY_ASSEMBLYAI, KEY_CUSTOM_STT, KEY_CUSTOM_LLM,
)


class SettingsWindow(QWidget):
    settings_saved = pyqtSignal(object)  # emits AppSettings

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._setup_ui()
        self.setWindowTitle("Blitztext – Einstellungen")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self.setMinimumWidth(620)
        self.setMinimumHeight(720)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QTabWidget()
        tabs.addTab(self._tab_api(),       "🔑  API-Zugänge")
        tabs.addTab(self._tab_workflows(), "⚙  Workflows")
        tabs.addTab(self._tab_hotkeys(),   "⌨  Hotkeys")
        tabs.addTab(self._tab_advanced(),  "🔧  Erweitert")
        layout.addWidget(tabs)

        # Save / Cancel
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(16, 8, 16, 16)
        btn_row.addStretch()

        cancel = QPushButton("Abbrechen")
        cancel.clicked.connect(self.close)
        btn_row.addWidget(cancel)

        save = QPushButton("Speichern")
        save.setDefault(True)
        save.setStyleSheet(
            "QPushButton { background: #4a90d9; color: white; border-radius: 6px; "
            "padding: 6px 20px; font-weight: bold; }"
            "QPushButton:hover { background: #357abd; }"
        )
        save.clicked.connect(self._save)
        btn_row.addWidget(save)

        layout.addLayout(btn_row)

    # ── Tab: API-Zugänge ─────────────────────────────────────────────────────

    def _tab_api(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        def _key_row(label: str, key_name: str, placeholder: str = "sk-…") -> QWidget:
            grp = QGroupBox(label)
            g = QVBoxLayout(grp)
            g.setSpacing(6)
            g.setContentsMargins(10, 14, 10, 10)

            current = get_api_key(key_name)
            display = QLabel(f"Gespeichert: {masked(current)}" if current else "Nicht gesetzt")
            display.setStyleSheet("color: #888; font-size: 11px;")
            g.addWidget(display)

            row = QHBoxLayout()
            row.setSpacing(6)

            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setObjectName(f"key_{key_name}")
            field.setMinimumHeight(30)
            row.addWidget(field, 1)

            show_btn = QPushButton("👁")
            show_btn.setFixedWidth(36)
            show_btn.setFixedHeight(30)
            show_btn.setCheckable(True)
            show_btn.setToolTip("Schlüssel anzeigen / verbergen")
            show_btn.toggled.connect(
                lambda on, f=field: f.setEchoMode(
                    QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
                )
            )
            row.addWidget(show_btn)

            paste_btn = QPushButton("Einfügen")
            paste_btn.setFixedHeight(30)
            paste_btn.setMinimumWidth(80)
            paste_btn.clicked.connect(lambda: self._paste_key(field))
            row.addWidget(paste_btn)

            clear_btn = QPushButton("Löschen")
            clear_btn.setFixedHeight(30)
            clear_btn.setMinimumWidth(80)
            clear_btn.clicked.connect(lambda: self._clear_key(key_name, display, field))
            row.addWidget(clear_btn)

            g.addLayout(row)
            return grp

        groq_hint = QLabel("👉 Kostenlos starten: https://console.groq.com  (STT + LLM gratis)")
        groq_hint.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
        layout.addWidget(groq_hint)

        layout.addWidget(_key_row("Groq API Key (kostenlos, Standard)", KEY_GROQ, "gsk_…"))
        layout.addWidget(_key_row("Claude API Key (Anthropic)", KEY_ANTHROPIC, "sk-ant-…"))
        layout.addWidget(_key_row("OpenAI API Key", KEY_OPENAI))
        layout.addWidget(_key_row("AssemblyAI API Key", KEY_ASSEMBLYAI, "…"))

        # Ollama URL
        ollama_grp = QGroupBox("Ollama (lokales LLM)")
        ol = QFormLayout(ollama_grp)
        self._ollama_url = QLineEdit(self.settings.ollama_base_url)
        self._ollama_url.setPlaceholderText("http://localhost:11434")
        self._ollama_model = QLineEdit(self.settings.ollama_llm_model)
        self._ollama_model.setPlaceholderText("llama3.2")
        ol.addRow("Basis-URL:", self._ollama_url)
        ol.addRow("Modell:", self._ollama_model)
        layout.addWidget(ollama_grp)

        # Custom endpoints
        custom_grp = QGroupBox("Eigene Endpunkte (OpenAI-kompatibel)")
        cu = QFormLayout(custom_grp)
        self._custom_stt_url = QLineEdit(self.settings.custom_stt_url)
        self._custom_stt_url.setPlaceholderText("https://…/v1/audio/transcriptions")
        self._custom_llm_url = QLineEdit(self.settings.custom_llm_url)
        self._custom_llm_url.setPlaceholderText("https://…/v1/chat/completions")
        cu.addRow("STT-Endpunkt:", self._custom_stt_url)
        cu.addRow("LLM-Endpunkt:", self._custom_llm_url)

        custom_stt_key = get_api_key(KEY_CUSTOM_STT)
        self._custom_stt_key = QLineEdit()
        self._custom_stt_key.setPlaceholderText(
            f"Gespeichert: {masked(custom_stt_key)}" if custom_stt_key else "Nicht gesetzt"
        )
        self._custom_stt_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._custom_stt_key.setObjectName(f"key_{KEY_CUSTOM_STT}")
        cu.addRow("STT-Key (optional):", self._custom_stt_key)

        custom_llm_key = get_api_key(KEY_CUSTOM_LLM)
        self._custom_llm_key = QLineEdit()
        self._custom_llm_key.setPlaceholderText(
            f"Gespeichert: {masked(custom_llm_key)}" if custom_llm_key else "Nicht gesetzt"
        )
        self._custom_llm_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._custom_llm_key.setObjectName(f"key_{KEY_CUSTOM_LLM}")
        cu.addRow("LLM-Key (optional):", self._custom_llm_key)

        layout.addWidget(custom_grp)

        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    def _paste_key(self, field: QLineEdit) -> None:
        from PyQt6.QtWidgets import QApplication
        text = QApplication.clipboard().text().strip()
        if text:
            field.setText(text)

    def _clear_key(self, key_name: str, display: QLabel, field: QLineEdit) -> None:
        from ..services.settings import delete_api_key
        delete_api_key(key_name)
        display.setText("Nicht gesetzt")
        field.clear()

    # ── Tab: Workflows ───────────────────────────────────────────────────────

    def _tab_workflows(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # ─ Transkription ─
        tr_grp = QGroupBox("🎙  Blitztext — Transkription")
        tr = QFormLayout(tr_grp)
        self._tr_stt_provider = self._stt_combo(self.settings.transcription_model.stt_provider)
        self._tr_stt_model    = QLineEdit(self.settings.transcription_model.stt_model)
        self._tr_language     = QLineEdit(self.settings.transcription_model.language)
        tr.addRow("STT-Anbieter:", self._tr_stt_provider)
        tr.addRow("STT-Modell:", self._tr_stt_model)
        tr.addRow("Sprache (BCP-47):", self._tr_language)
        layout.addWidget(tr_grp)

        # ─ Blitztext+ ─
        ti_grp = QGroupBox("✨  Blitztext+ — Text verbessern")
        ti = QFormLayout(ti_grp)
        self._ti_stt_provider = self._stt_combo(self.settings.text_improvement.model.stt_provider)
        self._ti_stt_model    = QLineEdit(self.settings.text_improvement.model.stt_model)
        self._ti_llm_provider = self._llm_combo(self.settings.text_improvement.model.llm_provider)
        self._ti_llm_model    = self._llm_model_combo(
            self._ti_llm_provider, self.settings.text_improvement.model.llm_model
        )
        self._ti_tone         = QComboBox()
        for val, lbl in [("formal","Formell"),("neutral","Neutral"),("casual","Locker")]:
            self._ti_tone.addItem(lbl, val)
        self._ti_tone.setCurrentIndex(
            ["formal","neutral","casual"].index(self.settings.text_improvement.tone)
        )
        self._ti_context = QLineEdit(self.settings.text_improvement.context)
        self._ti_prompt  = QTextEdit(self.settings.text_improvement.system_prompt)
        self._ti_prompt.setFixedHeight(80)
        self._ti_prompt.setPlaceholderText("Leer = automatischer Standardprompt")
        ti.addRow("STT-Anbieter:", self._ti_stt_provider)
        ti.addRow("STT-Modell:", self._ti_stt_model)
        ti.addRow("LLM-Anbieter:", self._ti_llm_provider)
        ti.addRow("LLM-Modell:", self._ti_llm_model)
        ti.addRow("Ton:", self._ti_tone)
        ti.addRow("Kontext:", self._ti_context)
        ti.addRow("Eigener Prompt:", self._ti_prompt)
        layout.addWidget(ti_grp)

        # ─ Dampf ablassen ─
        da_grp = QGroupBox("🔥  Blitztext $%&! — Frust umformulieren")
        da = QFormLayout(da_grp)
        self._da_stt_provider = self._stt_combo(self.settings.dampf_ablassen.model.stt_provider)
        self._da_stt_model    = QLineEdit(self.settings.dampf_ablassen.model.stt_model)
        self._da_llm_provider = self._llm_combo(self.settings.dampf_ablassen.model.llm_provider)
        self._da_llm_model    = self._llm_model_combo(
            self._da_llm_provider, self.settings.dampf_ablassen.model.llm_model
        )
        self._da_prompt       = QTextEdit(self.settings.dampf_ablassen.system_prompt)
        self._da_prompt.setFixedHeight(100)
        da.addRow("STT-Anbieter:", self._da_stt_provider)
        da.addRow("STT-Modell:", self._da_stt_model)
        da.addRow("LLM-Anbieter:", self._da_llm_provider)
        da.addRow("LLM-Modell:", self._da_llm_model)
        da.addRow("System-Prompt:", self._da_prompt)
        layout.addWidget(da_grp)

        # ─ Emoji ─
        em_grp = QGroupBox("😊  Blitztext :) — Emojis")
        em = QFormLayout(em_grp)
        self._em_stt_provider = self._stt_combo(self.settings.emoji.model.stt_provider)
        self._em_stt_model    = QLineEdit(self.settings.emoji.model.stt_model)
        self._em_llm_provider = self._llm_combo(self.settings.emoji.model.llm_provider)
        self._em_llm_model    = self._llm_model_combo(
            self._em_llm_provider, self.settings.emoji.model.llm_model
        )
        self._em_density      = QComboBox()
        for val, lbl in [("wenig","Wenig"),("mittel","Mittel"),("viel","Viel")]:
            self._em_density.addItem(lbl, val)
        self._em_density.setCurrentIndex(
            ["wenig","mittel","viel"].index(self.settings.emoji.density)
        )
        em.addRow("STT-Anbieter:", self._em_stt_provider)
        em.addRow("STT-Modell:", self._em_stt_model)
        em.addRow("LLM-Anbieter:", self._em_llm_provider)
        em.addRow("LLM-Modell:", self._em_llm_model)
        em.addRow("Emoji-Dichte:", self._em_density)
        layout.addWidget(em_grp)

        layout.addStretch()
        scroll.setWidget(w)
        return scroll

    def _stt_combo(self, current: str) -> QComboBox:
        cb = QComboBox()
        for val in STTProvider.ALL:
            cb.addItem(STTProvider.DISPLAY[val], val)
        idx = STTProvider.ALL.index(current) if current in STTProvider.ALL else 0
        cb.setCurrentIndex(idx)
        return cb

    def _llm_combo(self, current: str) -> QComboBox:
        cb = QComboBox()
        for val in LLMProvider.ALL:
            cb.addItem(LLMProvider.DISPLAY[val], val)
        idx = LLMProvider.ALL.index(current) if current in LLMProvider.ALL else 0
        cb.setCurrentIndex(idx)
        return cb

    def _llm_model_combo(self, provider_combo: QComboBox, current_model: str) -> QComboBox:
        """Editierbare Auswahlliste fuer das LLM-Modell, Vorschlaege richten sich
        nach dem aktuell gewaehlten LLM-Anbieter. Eigene Modellnamen bleiben
        weiterhin moeglich (Feld ist editierbar)."""
        cb = QComboBox()
        cb.setEditable(True)
        cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._fill_llm_models(cb, provider_combo.currentData(), current_model)
        provider_combo.currentIndexChanged.connect(
            lambda: self._fill_llm_models(cb, provider_combo.currentData(), cb.currentText())
        )
        return cb

    def _fill_llm_models(self, cb: QComboBox, provider: str, keep_text: str) -> None:
        cb.blockSignals(True)
        cb.clear()
        cb.addItems(LLM_MODEL_PRESETS.get(provider, []))
        cb.setEditText(keep_text)
        cb.blockSignals(False)

    # ── Tab: Hotkeys ─────────────────────────────────────────────────────────

    def _tab_hotkeys(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        note = QLabel(
            "Format: ctrl+shift+r  |  alt+f1  |  ctrl+alt+t\n"
            "Halten = Taste gedrückt halten, beim Loslassen wird übernommen.\n"
            "Umschalten = einmal drücken startet, nochmal drücken stoppt."
        )
        note.setStyleSheet("color: #888; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._hk_enabled = QCheckBox("Globale Hotkeys aktivieren")
        self._hk_enabled.setChecked(self.settings.hotkeys.enabled)
        layout.addWidget(self._hk_enabled)

        def _mode_combo(current: str) -> QComboBox:
            cb = QComboBox()
            cb.addItem("Halten", "hold")
            cb.addItem("Umschalten", "toggle")
            cb.setCurrentIndex(0 if current == "hold" else 1)
            return cb

        def _row(label: str, key_field: QLineEdit, mode_combo: QComboBox) -> QWidget:
            box = QGroupBox(label)
            form = QFormLayout(box)
            form.addRow("Tastenkürzel:", key_field)
            form.addRow("Modus:", mode_combo)
            return box

        self._hk_transcription    = QLineEdit(self.settings.hotkeys.transcription)
        self._hk_text_improvement = QLineEdit(self.settings.hotkeys.text_improvement)
        self._hk_dampf_ablassen   = QLineEdit(self.settings.hotkeys.dampf_ablassen)
        self._hk_emoji_text       = QLineEdit(self.settings.hotkeys.emoji_text)

        self._hk_transcription_mode    = _mode_combo(self.settings.hotkeys.transcription_mode)
        self._hk_text_improvement_mode = _mode_combo(self.settings.hotkeys.text_improvement_mode)
        self._hk_dampf_ablassen_mode   = _mode_combo(self.settings.hotkeys.dampf_ablassen_mode)
        self._hk_emoji_text_mode       = _mode_combo(self.settings.hotkeys.emoji_text_mode)

        layout.addWidget(_row("🎙  Blitztext — kurze Texte",
                              self._hk_transcription, self._hk_transcription_mode))
        layout.addWidget(_row("✨  Blitztext+ — lange Texte / freies Sprechen",
                              self._hk_text_improvement, self._hk_text_improvement_mode))
        layout.addWidget(_row("🔥  Blitztext $%&! — Frust umformulieren",
                              self._hk_dampf_ablassen, self._hk_dampf_ablassen_mode))
        layout.addWidget(_row("😊  Blitztext :) — mit Emojis",
                              self._hk_emoji_text, self._hk_emoji_text_mode))

        layout.addStretch()
        return w

    # ── Tab: Erweitert ───────────────────────────────────────────────────────

    def _tab_advanced(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._auto_paste = QCheckBox("Text automatisch in fokussiertes Fenster einfügen")
        self._auto_paste.setChecked(self.settings.auto_paste)
        layout.addWidget(self._auto_paste)

        note = QLabel(
            "Auto-Paste benötigt xdotool (Linux X11) oder ydotool (Wayland) "
            "bzw. pyautogui (Windows).\n"
            "Ohne Auto-Paste landet der Text nur in der Zwischenablage."
        )
        note.setStyleSheet("color: #888; font-size: 11px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # ─ Mikrofon-Auswahl ─
        mic_grp = QGroupBox("🎤  Mikrofon")
        mf = QFormLayout(mic_grp)
        self._mic_combo = QComboBox()
        self._mic_combo.addItem("System-Standard", None)

        try:
            from ..services.recorder import list_input_devices
            devices = list_input_devices()
            current = self.settings.audio_input_device
            selected_idx = 0
            for i, d in enumerate(devices):
                label = d["name"]
                if d.get("default"):
                    label += "  (Default)"
                self._mic_combo.addItem(label, d["index"])
                if current is not None and d["index"] == current:
                    selected_idx = i + 1
            self._mic_combo.setCurrentIndex(selected_idx)
        except Exception as e:
            self._mic_combo.addItem(f"Fehler: {e}", None)

        mf.addRow("Aufnahmegerät:", self._mic_combo)
        layout.addWidget(mic_grp)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        groq_grp = QGroupBox("Groq – Standardmodelle")
        gf = QFormLayout(groq_grp)
        self._groq_stt = QLineEdit(self.settings.groq_stt_model)
        self._groq_stt.setPlaceholderText("whisper-large-v3-turbo")
        self._groq_llm = QComboBox()
        self._groq_llm.setEditable(True)
        self._groq_llm.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._groq_llm.addItems(LLM_MODEL_PRESETS.get(LLMProvider.GROQ, []))
        self._groq_llm.setEditText(self.settings.groq_llm_model)
        gf.addRow("STT-Modell:", self._groq_stt)
        gf.addRow("LLM-Modell:", self._groq_llm)
        layout.addWidget(groq_grp)

        layout.addStretch()
        return w

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self) -> None:
        s = self.settings

        # Save API keys from fields
        for key_name in [KEY_OPENAI, KEY_GROQ, KEY_ANTHROPIC, KEY_ASSEMBLYAI, KEY_CUSTOM_STT, KEY_CUSTOM_LLM]:
            field = self.findChild(QLineEdit, f"key_{key_name}")
            if field:
                val = field.text().strip()
                if val:
                    set_api_key(key_name, val)

        # Ollama
        s.ollama_base_url  = self._ollama_url.text().strip()
        s.ollama_llm_model = self._ollama_model.text().strip()

        # Custom endpoints
        s.custom_stt_url = self._custom_stt_url.text().strip()
        s.custom_llm_url = self._custom_llm_url.text().strip()

        # Transcription
        s.transcription_model.stt_provider = self._tr_stt_provider.currentData()
        s.transcription_model.stt_model    = self._tr_stt_model.text().strip()
        s.transcription_model.language     = self._tr_language.text().strip()

        # Blitztext+
        s.text_improvement.model.stt_provider = self._ti_stt_provider.currentData()
        s.text_improvement.model.stt_model    = self._ti_stt_model.text().strip()
        s.text_improvement.model.llm_provider = self._ti_llm_provider.currentData()
        s.text_improvement.model.llm_model    = self._ti_llm_model.currentText().strip()
        s.text_improvement.tone               = self._ti_tone.currentData()
        s.text_improvement.context            = self._ti_context.text().strip()
        s.text_improvement.system_prompt      = self._ti_prompt.toPlainText().strip()

        # Dampf ablassen
        s.dampf_ablassen.model.stt_provider = self._da_stt_provider.currentData()
        s.dampf_ablassen.model.stt_model    = self._da_stt_model.text().strip()
        s.dampf_ablassen.model.llm_provider = self._da_llm_provider.currentData()
        s.dampf_ablassen.model.llm_model    = self._da_llm_model.currentText().strip()
        s.dampf_ablassen.system_prompt      = self._da_prompt.toPlainText().strip()

        # Emoji
        s.emoji.model.stt_provider = self._em_stt_provider.currentData()
        s.emoji.model.stt_model    = self._em_stt_model.text().strip()
        s.emoji.model.llm_provider = self._em_llm_provider.currentData()
        s.emoji.model.llm_model    = self._em_llm_model.currentText().strip()
        s.emoji.density            = self._em_density.currentData()

        # Hotkeys
        s.hotkeys.transcription    = self._hk_transcription.text().strip()
        s.hotkeys.text_improvement = self._hk_text_improvement.text().strip()
        s.hotkeys.dampf_ablassen   = self._hk_dampf_ablassen.text().strip()
        s.hotkeys.emoji_text       = self._hk_emoji_text.text().strip()
        s.hotkeys.transcription_mode    = self._hk_transcription_mode.currentData()
        s.hotkeys.text_improvement_mode = self._hk_text_improvement_mode.currentData()
        s.hotkeys.dampf_ablassen_mode   = self._hk_dampf_ablassen_mode.currentData()
        s.hotkeys.emoji_text_mode       = self._hk_emoji_text_mode.currentData()
        s.hotkeys.enabled               = self._hk_enabled.isChecked()

        # Advanced
        s.auto_paste              = self._auto_paste.isChecked()
        s.audio_input_device      = self._mic_combo.currentData()
        s.groq_stt_model          = self._groq_stt.text().strip()
        s.groq_llm_model          = self._groq_llm.currentText().strip()

        save_settings(s)
        self.settings_saved.emit(s)
        self.close()
