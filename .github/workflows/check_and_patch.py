import os
import sys
import json
import subprocess
import requests

GITHUB_TOKEN = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY", "")

def get_morphe_versions():
    print("[+] Getting morphe-compatible versions...")
    
    from utils.morphe import Morphe
    
    m = Morphe()
    cli_path = m.get_cli_path()
    patches_path = m.get_patches_path()
    versions = m.list_versions(patches_path, cli_path)
    
    return versions

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

def find_versions_to_patch(versions, released):
    to_patch = []
    
    for app, version_list in versions.items():
        if not version_list:
            continue
        
        version = version_list[0]
        filename = f"{app}-morphe-{version}.apk"
        
        if filename not in released:
            to_patch.append((app, version, filename))
            print(f"[+] Need to patch: {app} v{version}")
        else:
            print(f"[+] Already released: {filename}")
    
    return to_patch

def run_patcher():
    print("[+] Running patcher...")
    result = subprocess.run([sys.executable, "app.py"], capture_output=True, text=True, cwd=os.getcwd())
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode == 0

def upload_release(app, version, filename):
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
    
    tag_name = f"v{version}"
    
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
            "name": f"{app} v{version} (Morphe patched)",
            "body": f"Auto-patched {app} v{version} with Morphe",
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
    versions = get_morphe_versions()
    released = get_released_files()
    to_patch = find_versions_to_patch(versions, released)
    
    if not to_patch:
        print("[+] All versions already released. Skipping.")
        return
    
    print(f"[+] Found {len(to_patch)} version(s) to patch")
    
    if run_patcher():
        for app, version, filename in to_patch:
            upload_release(app, version, filename)
    else:
        print("[-] Patcher failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
