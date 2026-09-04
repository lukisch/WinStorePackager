import sys
import tkinter as tk
from tkinter import ttk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import WindowsStorePublisher_3 as _wsp


def _minimal_app() -> "_wsp.StorePackagerApp":
    app = _wsp.StorePackagerApp.__new__(_wsp.StorePackagerApp)
    tk.Tk.__init__(app)
    app.withdraw()

    app.language = tk.StringVar(value="de")
    app._translatable_items = []
    app._tooltips = []

    app.app_name = tk.StringVar(value="TestApp")
    app.publisher = tk.StringVar(value="CN=Test")
    app.publisher_display = tk.StringVar(value="Test Studio")
    app.identity_name = tk.StringVar(value="Test.TestApp")
    app.version = tk.StringVar(value="1.0.0.0")
    app.script_path = tk.StringVar()
    app.icon_path = tk.StringVar()
    app.source_path = tk.StringVar()
    app.installer_path = tk.StringVar()
    app.output_dir = tk.StringVar(value="store_package")
    app.exe_name = tk.StringVar(value="TestApp.exe")
    app.makeappx_path = tk.StringVar()
    app.signtool_path = tk.StringVar()
    app.appcert_path = tk.StringVar()
    app.pfx_path = tk.StringVar()
    app.pfx_password = tk.StringVar()
    app.timestamp_url = tk.StringVar(value="http://timestamp.example")
    app.msix_name = tk.StringVar(value="TestApp.msix")
    app.python_path = tk.StringVar()
    app.enable_i18n = tk.BooleanVar(value=False)
    app.privacy_url = tk.StringVar(value="https://example.test/privacy")
    app.support_url = tk.StringVar(value="https://example.test/support")
    app.capabilities = tk.StringVar(value="internetClient")
    app.category = tk.StringVar(value="Productivity")
    app.age_rating = tk.StringVar(value="3+")
    return app


def _button_texts(parent: tk.Misc) -> list[str]:
    texts: list[str] = []
    stack = [parent]
    while stack:
        widget = stack.pop()
        for child in widget.winfo_children():
            stack.append(child)
            try:
                if child.winfo_class() == "TButton":
                    texts.append(child.cget("text"))
            except tk.TclError:
                continue
    return texts


class TestProjectProfileDialogLocalization(unittest.TestCase):
    def setUp(self):
        self.translator = _wsp.get_translator()
        if self.translator is None:
            self.skipTest("Translation system is unavailable")
        self.translator.set_language("en")

    def tearDown(self):
        if self.translator is not None:
            self.translator.set_language("de")

    def test_profile_dialogs_follow_the_selected_language(self):
        export_app = SimpleNamespace(collect_project_profile_state=lambda: {"app_name": "Demo"})
        with (
            patch.object(_wsp.filedialog, "asksaveasfilename", return_value="demo.json") as save_dialog,
            patch.object(_wsp, "write_project_profile") as write_profile,
            patch.object(_wsp.messagebox, "showinfo") as show_info,
        ):
            _wsp.StorePackagerApp.export_project_profile(export_app)

        self.assertEqual(save_dialog.call_args.kwargs["title"], "Export Project Profile")
        self.assertEqual(
            save_dialog.call_args.kwargs["filetypes"],
            [("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        write_profile.assert_called_once_with("demo.json", {"app_name": "Demo"})
        show_info.assert_called_once_with(
            "Project Profile Exported",
            "Project profile was exported.\n\n"
            "Publisher ID, SDK paths, certificate paths, and passwords are not included.",
        )

        import_app = SimpleNamespace(apply_project_profile_state=Mock())
        with (
            patch.object(_wsp.filedialog, "askopenfilename", return_value="demo.json") as open_dialog,
            patch.object(_wsp, "read_project_profile", return_value={"app_name": "Demo"}),
            patch.object(_wsp.messagebox, "showinfo") as show_info,
        ):
            _wsp.StorePackagerApp.import_project_profile(import_app)

        self.assertEqual(open_dialog.call_args.kwargs["title"], "Import Project Profile")
        self.assertEqual(
            open_dialog.call_args.kwargs["filetypes"],
            [("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        import_app.apply_project_profile_state.assert_called_once_with({"app_name": "Demo"})
        show_info.assert_called_once_with(
            "Project Profile Imported",
            "Project profile was loaded.\n\n"
            "Please add Publisher ID, SDK paths, and certificate locally.",
        )


class TestBuildPackageDialogLocalization(unittest.TestCase):
    def setUp(self):
        self.translator = _wsp.get_translator()
        if self.translator is None:
            self.skipTest("Translation system is unavailable")
        self.translator.set_language("en")

    def tearDown(self):
        if self.translator is not None:
            self.translator.set_language("de")

    def test_build_package_missing_name_uses_selected_language(self):
        app = SimpleNamespace(app_name=SimpleNamespace(get=lambda: "  "))
        with patch.object(_wsp.messagebox, "showerror") as show_error:
            _wsp.StorePackagerApp.build_package(app)

        show_error.assert_called_once_with("Error", "Please enter an app name.")

    def test_existing_output_confirmation_uses_selected_language(self):
        app = SimpleNamespace(
            app_name=SimpleNamespace(get=lambda: "Demo"),
            package_dir=lambda: "C:/temporary/output",
        )
        with (
            patch.object(_wsp.os.path, "exists", return_value=True),
            patch.object(_wsp.messagebox, "askyesno", return_value=False) as ask_yes_no,
        ):
            _wsp.StorePackagerApp.build_package(app)

        ask_yes_no.assert_called_once_with(
            "Confirmation",
            "Output directory already exists:\nC:/temporary/output\n\nOverwrite?",
        )


class TestUiAccessibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.app = _minimal_app()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tkinter display is unavailable: {exc}") from exc

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_metadata_tab_uses_contextual_button_labels(self):
        parent = tk.Frame(self.app)
        self.app.build_metadata_tab(parent)
        texts = _button_texts(parent)

        for label in (
            "Skript wählen",
            "Icon wählen",
            "Quelle wählen",
            "Installer wählen",
            "README laden",
            "Beschreibung laden",
        ):
            self.assertIn(label, texts)

        self.assertNotIn("Wählen", texts)
        self.assertNotIn("Datei laden", texts)

    def test_build_tab_uses_contextual_button_labels(self):
        parent = tk.Frame(self.app)
        self.app.build_build_tab(parent)
        texts = _button_texts(parent)

        for label in (
            "Python wählen",
            "MakeAppx wählen",
            "SignTool wählen",
            "AppCert wählen",
            "Zertifikat wählen",
        ):
            self.assertIn(label, texts)

        self.assertNotIn("Wählen", texts)

    def test_store_tab_uses_real_german_umlaut_for_format_action(self):
        parent = tk.Frame(self.app)
        self.app.build_store_tab(parent)
        texts = _button_texts(parent)

        self.assertIn("Format für Store", texts)
        self.assertNotIn("Format fuer Store", texts)

    def test_tooltip_behavior_and_status_bar_updates(self):
        test_btn = ttk.Button(self.app, text="Test")
        tip = _wsp.ToolTip(
            test_btn,
            text="Hilfetext für Test",
            app=self.app,
            status_text="Statuszeile für Test"
        )
        self.assertEqual(tip.text, "Hilfetext für Test")
        self.assertEqual(tip.status_text, "Statuszeile für Test")

        # Test set_text
        tip.set_text("Neuer Text", "Neuer Status")
        self.assertEqual(tip.text, "Neuer Text")
        self.assertEqual(tip.status_text, "Neuer Status")

    def test_full_gui_structure_and_menubar(self):
        full_app = _minimal_app()
        try:
            full_app.build_gui()

            # Status bar exists
            self.assertIsNotNone(full_app.status_bar)
            self.assertIsNotNone(full_app.status_label)
            self.assertEqual(full_app.status_label.cget("text"), "Status: Bereit")

            # Notebook has 4 tabs
            self.assertEqual(full_app.notebook.index("end"), 4)

            # Tooltips registered
            self.assertGreater(len(full_app._tooltips), 15)

            # Menubar exists
            menu = full_app.cget("menu")
            self.assertTrue(menu != "" and menu is not None)

            # Keyboard shortcut helper
            self.assertTrue(hasattr(full_app, "show_shortcuts_help"))
            self.assertTrue(hasattr(full_app, "show_about_dialog"))
            self.assertTrue(hasattr(full_app, "select_tab"))
        finally:
            full_app.destroy()

    def test_dynamic_language_switch_updates_tooltips(self):
        try:
            full_app = _minimal_app()
        except tk.TclError as exc:
            self.skipTest(f"Tkinter display is unavailable for a second window: {exc}")
        try:
            full_app.build_gui()

            tr = _wsp.get_translator()
            if tr is not None:
                tr.set_language("en")
            full_app.language.set("en")
            full_app.refresh_ui_language()

            # Tabs are translated
            self.assertEqual(full_app.notebook.tab(0, "text"), "Metadata")
            self.assertEqual(full_app.notebook.tab(1, "text"), "Build Settings")
            self.assertEqual(full_app.notebook.tab(2, "text"), "Store Information")
            self.assertEqual(full_app.notebook.tab(3, "text"), "Actions")

            # Status bar is translated
            self.assertEqual(full_app.status_label.cget("text"), "Status: Ready")

            # Switch back to DE
            if tr is not None:
                tr.set_language("de")
            full_app.language.set("de")
            full_app.refresh_ui_language()
            self.assertEqual(full_app.notebook.tab(0, "text"), "Metadaten")
            self.assertEqual(full_app.status_label.cget("text"), "Status: Bereit")
        finally:
            tr = _wsp.get_translator()
            if tr is not None:
                tr.set_language("de")
            full_app.destroy()

    def test_german_end_user_texts_have_real_umlauts(self):
        tr = _wsp.get_translator()
        self.assertIsNotNone(tr)
        translations = tr.translations
        self.assertGreater(len(translations), 50)

        # Check that German translation catalog contains entries with proper umlauts
        self.assertIn("Tastaturkürzel & Barrierefreiheit", translations)
        self.assertIn("Über WinStorePackager", translations)
        self.assertIn("Format für Store", translations)

        # Check that values for 'de' contain proper umlauts
        de_text = translations["Tastaturkürzel & Barrierefreiheit"].get("de", "")
        self.assertIn("ü", de_text)

    def test_window_title_matches_current_release_version(self):
        source = Path(_wsp.__file__).read_text(encoding="utf-8")
        self.assertIn('self.title("Windows Store Packager v3.1.0 (Auto-Setup)")', source)

if __name__ == "__main__":
    unittest.main()
