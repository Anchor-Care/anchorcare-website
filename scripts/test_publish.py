"""Prove PR publication cannot accidentally push the default branch."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class PublishTests(unittest.TestCase):
    def test_publish_branch_and_reject_stale_branch(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory).resolve()
            remote = root / "remote.git"
            checkout = root / "checkout"

            def git(*args, cwd=checkout):
                return subprocess.check_output(["git", *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()

            git("init", "--bare", str(remote), cwd=root)
            git("init", "-b", "main", str(checkout), cwd=root)
            git("config", "user.name", "Synthetic test")
            git("config", "user.email", "test@example.invalid")
            git("config", "core.hooksPath", "/dev/null")
            (checkout / "scripts").mkdir()
            shutil.copy2(Path(__file__).with_name("anchor-site.sh"), checkout / "scripts/anchor-site.sh")
            (checkout / "index.html").write_text("synthetic fixture")
            git("add", ".")
            git("commit", "-m", "test: initialize fixture")
            git("remote", "add", "origin", str(remote))
            git("push", "origin", "main")
            initial_main = git("rev-parse", "main")
            git("switch", "-c", "fix/synthetic-check")
            (checkout / "fixture.txt").write_text("synthetic change")
            result = subprocess.run(
                ["bash", "scripts/anchor-site.sh", "publish", "test: publish fixture"],
                cwd=checkout, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(git("rev-parse", "refs/heads/main", cwd=remote), initial_main)
            self.assertEqual(git("rev-parse", "refs/heads/fix/synthetic-check", cwd=remote), git("rev-parse", "HEAD"))
            self.assertIn("pushed PR branch", result.stdout)

            # Advance main independently; the PR branch must then refuse publication.
            git("switch", "main")
            (checkout / "other.txt").write_text("another synthetic change")
            git("add", ".")
            git("commit", "-m", "test: advance fixture main")
            git("push", "origin", "main")
            git("switch", "fix/synthetic-check")
            result = subprocess.run(
                ["bash", "scripts/anchor-site.sh", "publish", "test: refuse stale fixture"],
                cwd=checkout, text=True, capture_output=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing changes from origin/main", result.stdout)


if __name__ == "__main__":
    unittest.main()
