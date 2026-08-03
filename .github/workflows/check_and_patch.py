import os
import sys
import json
import subprocess
import requests
import argparse

GITHUB_TOKEN = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY", "")

def get_morphe_versions():
    print("[+] Getting morphe-compatible versions...")
    
    from utils.morphe import Morphe
    
    m = Morphe()
    cli_path = m.get_cli_path()
    patches_path = m.get_patches_path()
    mpp_version = os.path.basename(patches_path).replace("patches-", "").replace(".mpp", "")
    versions = m.list_versions(patches_path, cli_path)
    
    return versions, mpp_version

def get_released_files():
    print("[+] Checking existing releases...")
    
    url = f"https://api.github.com/repos/{REPO}/releases"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        releases = response.json()
    except Exception as e:
        print(f"[-] Could not fetch releases: {e}")
        return set()
    
    released = set()
    for release in releases:
        for asset in release.get("assets", []):
            released.add(asset["name"])
    
    print(f"[+] Found {len(released)} released files")
    return released

def find_versions_to_patch(versions, released, mpp_version, all_versions=False):
    to_patch = []

    # Fail loudly if no versions were detected at all, instead of treating it
    # as "all up to date". An empty version map almost always means the CLI
    # failed or the Java version is wrong (see list_versions raise).
    if not any(version_list for version_list in versions.values()):
        raise RuntimeError(
            "No compatible app versions were detected from morphe-cli. "
            "This usually means the CLI failed (check Java version / patches file), "
            "not that everything is already released."
        )

    for app, version_list in versions.items():
        if not version_list:
            continue
        versions_to_process = version_list if all_versions else [version_list[0]]
        for version in versions_to_process:
            filename = f"{app}-morphe-v{version}-mpp{mpp_version}.apk"

            if filename not in released:
                to_patch.append((app, version, filename))
                print(f"[+] Need to patch: {app} v{version}")
            else:
                print(f"[+] Already released: {filename}")

    return to_patch

def run_patcher(all_versions=False):
    print("[+] Running patcher...")
    cmd = [sys.executable, "app.py"]
    if all_versions:
        cmd.append("--all")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0

def upload_release(app, version, mpp_version, filename):
    patched_path = os.path.join("patched", filename)
    
    if not os.path.exists(patched_path):
        print(f"[-] File not found: {patched_path}")
        return False
    
    print(f"[+] Uploading {filename}...")
    
    url = f"https://api.github.com/repos/{REPO}/releases"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    
    tag_name = f"{app}-morphe-v{version}-mpp{mpp_version}"
    
    existing = requests.get(url, headers=headers)
    release_id = None
    
    if existing.ok:
        for r in existing.json():
            if r.get("tag_name") == tag_name:
                release_id = r["id"]
                break
    
    if not release_id:
        resp = requests.post(url, headers=headers, json={
            "tag_name": tag_name,
            "name": f"{app} v{version} (Morphe {mpp_version})",
            "body": f"Auto-patched {app} v{version} with Morphe {mpp_version}",
            "draft": False
        })
        if not resp.ok:
            print(f"[-] Failed to create release: {resp.text}")
            return False
        release_id = resp.json()["id"]
    
    upload_url = f"https://uploads.github.com/repos/{REPO}/releases/{release_id}/assets"
    
    with open(patched_path, "rb") as f:
        resp = requests.post(
            upload_url,
            headers={
                "Authorization": f"token {GITHUB_TOKEN}",
                "Content-Type": "application/octet-stream",
                "Accept": "application/vnd.github+json"
            },
            params={"name": filename},
            data=f
        )
    
    if resp.ok:
        print(f"[+] Uploaded: {filename}")
        return True
    else:
        print(f"[-] Upload failed: {resp.text}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Patch all compatible versions")
    args = parser.parse_args()

    versions, mpp_version = get_morphe_versions()
    released = get_released_files()
    to_patch = find_versions_to_patch(versions, released, mpp_version, args.all)
    
    if not to_patch:
        print("[+] All versions already released. Skipping.")
        return
    
    print(f"[+] Found {len(to_patch)} version(s) to patch")

    success = True
    if run_patcher(args.all):
        for app, version, filename in to_patch:
            if not upload_release(app, version, mpp_version, filename):
                success = False
                print(f"[-] Failed to upload {filename}")
        if not success:
            print("[-] Some uploads failed")
            sys.exit(1)
    else:
        print("[-] Patcher failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
