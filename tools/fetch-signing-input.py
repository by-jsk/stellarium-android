#!/usr/bin/env python3
"""Download the exact ARM64 artifact from a verified main-branch build."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


REPOSITORY = "by-jsk/stellarium-android"
BUILD_WORKFLOW = ".github/workflows/android.yml"
RELEASE_RUN_TITLE = "Stellar Touch release candidate"
APK_FILE = "StellarTouch-arm64-v8a-unsigned.apk"
APK_INPUTS = (
    ".gitattributes",
    "android",
    "mobile",
    "source.lock.json",
    "version.json",
    "tools/prepare.py",
    "tools/build-android.sh",
    "tools/prepare-gradle.py",
    "tools/package-notices.py",
    "LICENSE",
    "LICENSE-GPL-3.0.txt",
    "THIRD-PARTY.md",
    "licenses",
)


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", path]))


def successful_job(jobs, name, required_steps):
    matches = [job for job in jobs if job["name"] == name]
    require(len(matches) == 1, f"Expected exactly one job named {name}")
    job = matches[0]
    require(job["status"] == "completed" and job["conclusion"] == "success",
            f"{name} did not complete successfully")
    passed_steps = {step["name"] for step in job["steps"] if step["conclusion"] == "success"}
    require(set(required_steps) <= passed_steps, f"{name} is missing a required passing step")
    require({"Build Android APK with bundled PC data", "Verify the reused APK's native source identity"}
            & passed_steps, f"{name} did not build or verify native source identity")
    return job["id"]


def verified_artifact(artifacts, name, run_id, repository_id, sha):
    matches = [artifact for artifact in artifacts if artifact["name"] == name]
    require(len(matches) == 1, f"Expected one artifact named {name}")
    artifact = matches[0]
    run = artifact["workflow_run"]
    require(not artifact["expired"] and artifact["size_in_bytes"] > 0,
            f"{name} has expired or is empty")
    require(run["id"] == run_id and run["repository_id"] == repository_id
            and run["head_repository_id"] == repository_id
            and run["head_branch"] == "main" and run["head_sha"] == sha,
            f"{name} does not belong to the verified run and source")
    require(type(artifact["id"]) is int and artifact["id"] > 0
            and re.fullmatch(r"sha256:[0-9a-f]{64}", artifact.get("digest") or ""),
            f"{name} lacks an immutable artifact ID or SHA-256 digest")
    return {"id": artifact["id"], "digest": artifact["digest"], "size_in_bytes": artifact["size_in_bytes"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_run_id", type=int)
    parser.add_argument("expected_source_sha")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    require(args.build_run_id > 0, "Build run ID must be positive")
    require(not args.expected_source_sha or re.fullmatch(r"[0-9a-f]{40}", args.expected_source_sha),
            "Expected source SHA must contain 40 lowercase hexadecimal characters")
    require(os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REF") == "refs/heads/main",
            "Signing is restricted to the Stellar Touch main branch")

    repository_api = f"repos/{REPOSITORY}"
    run_api = f"{repository_api}/actions/runs/{args.build_run_id}"
    run = api(run_api)
    source_sha = run["head_sha"]
    require(run["id"] == args.build_run_id and run["path"] == BUILD_WORKFLOW
            and run["status"] == "completed" and run["conclusion"] == "success"
            and run["head_branch"] == "main" and run["event"] in {"push", "workflow_dispatch"}
            and run["repository"]["full_name"] == REPOSITORY
            and run["head_repository"]["id"] == run["repository"]["id"]
            and re.fullmatch(r"[0-9a-f]{40}", source_sha),
            "Choose a successful Stellar Touch build from this repository's main branch")
    require(not args.expected_source_sha or source_sha == args.expected_source_sha,
            "The build run does not match the expected source SHA")
    if os.environ.get("GITHUB_EVENT_NAME") == "workflow_run":
        owner = REPOSITORY.split("/", 1)[0]
        require(run["event"] == "workflow_dispatch" and run["display_title"] == RELEASE_RUN_TITLE
                and run["actor"]["login"] == owner and run["triggering_actor"]["login"] == owner,
                "Automatic signing requires an explicit release build requested by the repository owner")

    # Signing workflow/docs can land after the native build. All APK inputs must
    # still be identical in the reviewed checkout and the tested source commit.
    subprocess.run(["git", "fetch", "--no-tags", "--depth=1", "origin", source_sha], check=True)
    subprocess.run(["git", "diff", "--exit-code", source_sha, "HEAD", "--", *APK_INPUTS], check=True)

    jobs = api(f"{run_api}/attempts/{run['run_attempt']}/jobs?per_page=100")["jobs"]
    upload_step = "Upload unsigned APK before runtime tests"
    arm_job = successful_job(jobs, "android (android_arm64_v8a, arm64-v8a)", [upload_step])
    test_job = successful_job(jobs, "android (android_x86_64, x86_64)", [
        upload_step,
        "Run reactivecircus/android-emulator-runner@v2",
        "Verify on a 16-KiB page emulator",
        "Upload execution report and screen previews",
    ])
    artifact_names = ("apk-arm64-v8a", "apk-x86_64", "android-smoke-preview")
    artifacts = api(f"{run_api}/artifacts?per_page=100")["artifacts"]
    evidence = {
        name: verified_artifact(artifacts, name, args.build_run_id, run["repository"]["id"], source_sha)
        for name in artifact_names
    }
    arm = evidence["apk-arm64-v8a"]

    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    archive_path = args.output / "arm64-artifact.zip"
    with archive_path.open("wb") as archive:
        subprocess.run(["gh", "api", f"{repository_api}/actions/artifacts/{arm['id']}/zip"],
                       stdout=archive, check=True)
    with archive_path.open("rb") as archive:
        digest = hashlib.file_digest(archive, "sha256").hexdigest()
    require(archive_path.stat().st_size == arm["size_in_bytes"] and "sha256:" + digest == arm["digest"],
            "Downloaded ARM64 archive does not match GitHub's recorded size and digest")
    apk_path = args.output / APK_FILE
    with zipfile.ZipFile(archive_path) as archive:
        require(archive.namelist() == [APK_FILE], "Unexpected files in the ARM64 build artifact")
        require(0 < archive.getinfo(APK_FILE).file_size < 2 * 1024**3,
                "APK exceeds the GitHub release asset limit or is empty")
        with archive.open(APK_FILE) as source, apk_path.open("wb") as output:
            shutil.copyfileobj(source, output)
    archive_path.unlink()
    with apk_path.open("rb") as apk:
        unsigned_digest = hashlib.file_digest(apk, "sha256").hexdigest()
    report = {
        "build_run_id": args.build_run_id,
        "build_run_attempt": run["run_attempt"],
        "source_sha": source_sha,
        "signing_checkout_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "arm64_job_id": arm_job,
        "x86_64_test_job_id": test_job,
        "artifacts": evidence,
        "unsigned_apk_sha256": unsigned_digest,
    }
    (args.output / "build-provenance.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verified build {args.build_run_id} at {source_sha} and downloaded ARM64 artifact {arm['id']}")


if __name__ == "__main__":
    main()
