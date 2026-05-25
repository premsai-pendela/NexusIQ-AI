import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


class Ec2PilotDeployContractTests(unittest.TestCase):
    def test_docker_context_never_bakes_local_pilot_evidence(self):
        dockerignore = (REPO_ROOT / ".dockerignore").read_text()

        self.assertIn("data/pdfs_staging", dockerignore)
        self.assertIn("data/chroma_staging", dockerignore)

    def test_ec2_deploy_provisions_and_mounts_isolated_pilot_volumes(self):
        script = (REPO_ROOT / "scripts" / "deploy_ec2.sh").read_text()

        self.assertIn('PILOT_PDF_VOLUME="${PILOT_PDF_VOLUME:-nexusiq-pilot-pdfs}"', script)
        self.assertIn('PILOT_CHROMA_VOLUME="${PILOT_CHROMA_VOLUME:-nexusiq-pilot-chroma}"', script)
        self.assertIn("provision_pilot_evidence", script)
        self.assertIn("GENERATE_PILOT_PDFS_FROM_STAGING_ONLY", script)
        self.assertIn("INGEST_PILOT_PDFS_TO_ISOLATED_STAGING_ONLY", script)
        self.assertIn("VALIDATE_PILOT_STAGING_INDEX_AGAINST_STAGING_SQL_ONLY", script)
        self.assertIn('src=${PILOT_PDF_VOLUME},dst=/app/data/pdfs_staging', script)
        self.assertIn('src=${PILOT_CHROMA_VOLUME},dst=/app/data/chroma_staging', script)
        self.assertLess(script.index("provision_pilot_evidence\n"), script.index('echo "Replacing container:'))

    def test_existing_partial_evidence_is_not_overwritten_automatically(self):
        script = (REPO_ROOT / "scripts" / "deploy_ec2.sh").read_text()

        self.assertIn("Pilot PDF volume exists without its validated index; refusing automatic overwrite", script)


if __name__ == "__main__":
    unittest.main()
