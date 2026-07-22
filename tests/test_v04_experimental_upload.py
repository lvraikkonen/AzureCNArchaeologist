from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import upload_to_blob
from src.core.product_catalog import sha256_file


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_ROOT = ROOT / "output" / "experiments"


class ExperimentalUploadIsolationTests(unittest.TestCase):
    def _write_payload(
        self,
        root: Path,
        filename: str,
        payload: dict,
        *,
        validation: str = "passed",
    ) -> Path:
        payload_path = root / "payloads" / "zh-cn" / "pricing" / filename
        payload_path.parent.mkdir(parents=True, exist_ok=True)
        payload_path.write_text(
            json.dumps(payload, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        sidecar_path = (
            root
            / "diagnostics"
            / "zh-cn"
            / "pricing"
            / f"{payload_path.stem}.sidecar.json"
        )
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        sidecar_path.write_text(
            json.dumps(
                {
                    "product_key": "virtual-machines",
                    "status": {
                        "execution": "succeeded",
                        "validation": validation,
                    },
                    "payload": {"sha256": sha256_file(payload_path)},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return payload_path

    def _dry_run(self, output_dir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "cli.py"),
                "upload",
                "--output-dir",
                str(output_dir),
                "--dry-run",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_experiments_root_and_descendants_are_rejected(self):
        for output_dir in (
            EXPERIMENTS_ROOT,
            EXPERIMENTS_ROOT / "shared-id" / "zh-cn",
        ):
            with self.subTest(output_dir=output_dir):
                result = self._dry_run(output_dir)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("experimental_upload_root_forbidden", result.stdout)
                self.assertIn("Upload aborted", result.stdout)

    def test_unvalidated_filename_is_rejected_with_matching_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = self._write_payload(
                root,
                "virtual-machines.unvalidated.json",
                {"title": "VM experimental candidate"},
            )

            directory_result = self._dry_run(root / "payloads")
            self.assertEqual(
                directory_result.returncode,
                1,
                directory_result.stdout + directory_result.stderr,
            )
            self.assertIn("unvalidated_filename_forbidden", directory_result.stdout)
            self.assertNotIn("DRY-RUN ", directory_result.stdout)

            file_result = self._dry_run(candidate)
            self.assertEqual(file_result.returncode, 1, file_result.stdout + file_result.stderr)
            self.assertIn("unvalidated_filename_forbidden", file_result.stdout)

    def test_unvalidated_trust_status_defeats_forged_passed_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_payload(
                root,
                "virtual-machines.json",
                {
                    "title": "VM experimental candidate",
                    "trust_status": "unvalidated",
                },
            )

            result = self._dry_run(root / "payloads")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("unvalidated_trust_status_forbidden", result.stdout)
            self.assertIn("Upload aborted", result.stdout)
            self.assertNotIn("DRY-RUN ", result.stdout)

    def test_policy_rejection_aborts_mixed_batch_but_normal_payload_remains_eligible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_payload(root, "service-bus.json", {"title": "Service Bus"})

            normal_result = self._dry_run(root / "payloads")
            self.assertEqual(
                normal_result.returncode,
                0,
                normal_result.stdout + normal_result.stderr,
            )
            self.assertIn("DRY-RUN", normal_result.stdout)

            self._write_payload(
                root,
                "virtual-machines.json",
                {"title": "VM", "trust_status": "UNVALIDATED"},
            )
            mixed_result = self._dry_run(root / "payloads")
            self.assertEqual(
                mixed_result.returncode,
                1,
                mixed_result.stdout + mixed_result.stderr,
            )
            self.assertIn("unvalidated_trust_status_forbidden", mixed_result.stdout)
            self.assertNotIn("DRY-RUN ", mixed_result.stdout)

    def test_symlink_alias_cannot_hide_an_experimental_candidate_or_root(self):
        EXPERIMENTS_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=EXPERIMENTS_ROOT) as experiment_directory:
            experiment_root = Path(experiment_directory)
            candidate = experiment_root / "virtual-machines.unvalidated.json"
            candidate.write_text(
                json.dumps({"title": "VM experimental candidate"}) + "\n",
                encoding="utf-8",
            )
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                payload_alias = root / "payloads/zh-cn/pricing/service-bus.json"
                payload_alias.parent.mkdir(parents=True)
                payload_alias.symlink_to(candidate)
                sidecar = root / "diagnostics/zh-cn/pricing/service-bus.sidecar.json"
                sidecar.parent.mkdir(parents=True)
                sidecar.write_text(
                    json.dumps(
                        {
                            "product_key": "service-bus",
                            "status": {"execution": "succeeded", "validation": "passed"},
                            "payload": {"sha256": sha256_file(candidate)},
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

                payload_result = self._dry_run(root / "payloads")
                self.assertEqual(
                    payload_result.returncode,
                    1,
                    payload_result.stdout + payload_result.stderr,
                )
                self.assertIn("payload_symlink_forbidden", payload_result.stdout)
                self.assertNotIn("DRY-RUN ", payload_result.stdout)

                root_alias = root / "experiment-root-alias"
                root_alias.symlink_to(experiment_root, target_is_directory=True)
                root_result = self._dry_run(root_alias)
                self.assertEqual(
                    root_result.returncode,
                    1,
                    root_result.stdout + root_result.stderr,
                )
                self.assertIn("experimental_upload_root_forbidden", root_result.stdout)

    def test_non_dry_run_never_constructs_blob_manager_for_unvalidated_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_payload(
                root,
                "virtual-machines.json",
                {"title": "VM", "trust_status": "unvalidated"},
            )
            with mock.patch.object(upload_to_blob, "BlobStorageManager") as manager_class:
                results = upload_to_blob.upload_output_directory(
                    str(root / "payloads"),
                    dry_run=False,
                )
            self.assertEqual(results, [])
            manager_class.assert_not_called()

    def test_non_dry_run_normal_payload_still_uploads_and_updates_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = self._write_payload(root, "service-bus.json", {"title": "Service Bus"})
            sidecar = root / "diagnostics/zh-cn/pricing/service-bus.sidecar.json"
            with mock.patch.object(upload_to_blob, "BlobStorageManager") as manager_class:
                manager = manager_class.return_value
                manager.upload_json_file.return_value = "https://example.invalid/service-bus.json"
                results = upload_to_blob.upload_output_directory(
                    str(root / "payloads"),
                    dry_run=False,
                )
            self.assertEqual(len(results), 1)
            manager.upload_json_file.assert_called_once()
            self.assertEqual(results[0]["local_path"], str(payload.resolve()))
            self.assertEqual(
                json.loads(sidecar.read_text(encoding="utf-8"))["status"]["publication"],
                "published",
            )


if __name__ == "__main__":
    unittest.main()
