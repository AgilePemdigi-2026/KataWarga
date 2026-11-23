"""
Test suite untuk Frontend UX contracts, template structure, dan static assets (P0.1, P1.1, P1.2, P2).
Kompatibel dengan pytest dan django.test.runner.DiscoverRunner.
"""

from pathlib import Path
from django.conf import settings
from django.test import SimpleTestCase


class FrontendUXContractsTestCase(SimpleTestCase):
    def test_pipeline_template_ux_contracts(self):
        """Memverifikasi template pipeline memiliki indeterminate progress dan atribut aksesibilitas."""
        template_path = Path(settings.BASE_DIR) / "templates" / "extraction" / "pipeline.html"
        self.assertTrue(template_path.exists(), "pipeline.html must exist")
        content = template_path.read_text(encoding="utf-8")

        self.assertTrue('id="pipeline-run-form"' in content or 'data-pipeline-form' in content)
        self.assertIn('id="pipeline-progress"', content)
        self.assertIn('role="status"', content)
        self.assertIn('aria-live="polite"', content)
        self.assertIn('kw-progress--indeterminate', content)
        self.assertIn("Pengambilan Review", content)
        self.assertIn("Filtering Review", content)
        self.assertIn("Ekstraksi AI &amp; Clustering", content)
        self.assertIn("Validasi Analyst", content)

    def test_compose_template_skeleton_separation(self):
        """
        Memverifikasi template compose memisahkan #story-results dari #story-loading
        sehingga skeleton DOM tidak tertimpa/hancur saat swap HTMX.
        """
        template_path = Path(settings.BASE_DIR) / "templates" / "stories" / "compose.html"
        self.assertTrue(template_path.exists(), "compose.html must exist")
        content = template_path.read_text(encoding="utf-8")

        self.assertIn('id="story-loading"', content)
        self.assertIn('id="story-results"', content)
        self.assertIn('hx-target="#story-results"', content)
        self.assertIn('hx-indicator="#story-loading"', content)

    def test_app_js_loading_lifecycle_contracts(self):
        """Memverifikasi app.js memiliki kontrak marker data-kw-loading dan lifecycle HTMX."""
        js_path = Path(settings.BASE_DIR) / "static" / "js" / "app.js"
        self.assertTrue(js_path.exists(), "app.js must exist")
        content = js_path.read_text(encoding="utf-8")

        self.assertTrue('submitter.dataset.kwLoading = "1"' in content or 'submitter.dataset.kwLoading' in content)
        self.assertIn('data-kw-loading', content)
        self.assertIn('data-kw-submitting', content)
        self.assertIn('[data-kw-loading="1"]', content)
        self.assertIn("htmx:afterRequest", content)
        self.assertIn("htmx:responseError", content)
        self.assertIn("htmx:sendError", content)
        self.assertIn("htmx:timeout", content)

    def test_app_css_reduced_motion_and_hover_contracts(self):
        """Memverifikasi CSS memiliki aturan prefers-reduced-motion dan transisi yang konsisten."""
        css_path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
        self.assertTrue(css_path.exists(), "app.css must exist")
        content = css_path.read_text(encoding="utf-8")

        self.assertIn("@media (prefers-reduced-motion: reduce)", content)
        self.assertIn("animation: none !important", content)
        self.assertIn("transition: none !important", content)
        self.assertIn(".kw-progress--indeterminate", content)
        self.assertIn(".kw-pipeline-progress", content)
