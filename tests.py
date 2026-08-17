import json
import unittest
from pathlib import Path

from exporters import export_docx, export_html, export_json, export_pdf, export_txt
import licensing


DATA = {"fullName": "أمين بن يوسف", "headline": "مهندس", "email": "a@example.com", "experience": [{"role": "مطور", "company": "شركة", "details": "رفعت الأداء 20%"}]}
TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="


class ExportTests(unittest.TestCase):
    def test_exports_are_valid(self):
        self.assertTrue(export_pdf(DATA).startswith(b"%PDF"))
        self.assertTrue(export_docx(DATA).startswith(b"PK"))
        self.assertIn("أمين", export_html(DATA).decode())
        self.assertIn("أمين", export_txt(DATA).decode())
        self.assertEqual(json.loads(export_json(DATA))["fullName"], DATA["fullName"])

    def test_french_export_labels(self):
        french = {**DATA, "uiLanguage": "fr", "summary": "Profil de test"}
        self.assertIn("Profil professionnel", export_html(french).decode())

    def test_english_export_labels(self):
        english = {**DATA, "uiLanguage": "en", "summary": "Test profile"}
        self.assertIn("Professional Summary", export_txt(english).decode())

    def test_arabic_text_exports_use_unicode(self):
        arabic = {**DATA, "uiLanguage": "ar", "summary": "ملخص مهني عربي"}
        self.assertTrue(export_txt(arabic).startswith(b"\xef\xbb\xbf"))
        self.assertTrue(export_html(arabic).startswith(b"\xef\xbb\xbf"))
        self.assertTrue(export_json(arabic).startswith(b"\xef\xbb\xbf"))
        self.assertIn("ملخص مهني عربي", export_json(arabic).decode("utf-8"))

    def test_photo_is_optional_and_exportable(self):
        with_photo = {**DATA, "uiLanguage": "fr", "photoData": TINY_PNG}
        self.assertIn('class="photo"', export_html(with_photo).decode("utf-8"))
        self.assertTrue(export_docx(with_photo).startswith(b"PK"))
        self.assertTrue(export_pdf(with_photo).startswith(b"%PDF"))


class LicenseTests(unittest.TestCase):
    def setUp(self):
        self.db = Path("test-licenses.db")
        licensing.DB_PATH = self.db
        for suffix in ("", "-wal", "-shm"):
            Path(str(self.db) + suffix).unlink(missing_ok=True)

    def tearDown(self):
        for suffix in ("", "-wal", "-shm"):
            Path(str(self.db) + suffix).unlink(missing_ok=True)

    def test_activation_and_signed_token(self):
        key = licensing.create_license("client@example.com", "monthly")
        result = licensing.activate("client@example.com", key, "device-one", "Windows")
        status = licensing.verify_token(result["token"])
        self.assertTrue(status["active"])
        self.assertEqual(status["plan"], "monthly")


if __name__ == "__main__": unittest.main()
