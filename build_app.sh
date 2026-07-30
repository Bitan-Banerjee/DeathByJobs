#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# DeathByJobs macOS App Builder
# ═══════════════════════════════════════════════════════════════════════════════
# Builds a standalone .app bundle with bundled Python backend, then packages
# it into a .dmg for distribution.
#
# Prerequisites: swiftc, hdiutil (both ship with Xcode/macOS)
# Optional:      create-dmg (brew install create-dmg) for prettier DMGs
#
# Usage:
#   chmod +x build_app.sh
#   ./build_app.sh
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BUILD_DIR="$PROJECT_ROOT/build"
BUNDLE_DIR="$BUILD_DIR/bundle"
APP_DIR="$BUNDLE_DIR/DeathByJobs.app"
RES_DIR="$APP_DIR/Contents/Resources"
MACOS_DIR="$APP_DIR/Contents/MacOS"

# ── Version ───────────────────────────────────────────────────────────────────
VERSION="1.0.0"
DMG_NAME="DeathByJobs-${VERSION}.dmg"
DMG_PATH="$PROJECT_ROOT/$DMG_NAME"

echo "🔨  Building DeathByJobs v${VERSION}…"

# ── Prerequisites ─────────────────────────────────────────────────────────────
command -v swiftc >/dev/null 2>&1 || { echo "❌  swiftc not found. Install Xcode."; exit 1; }
command -v hdiutil >/dev/null 2>&1 || { echo "❌  hdiutil not found."; exit 1; }

# ── Clean & scaffold ──────────────────────────────────────────────────────────
echo "📦  Cleaning build directory…"
rm -rf "$BUNDLE_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR"

# ── Compile Swift frontend ────────────────────────────────────────────────────
echo "🛠️   Compiling Swift frontend…"
swiftc \
    -O \
    -o "$MACOS_DIR/DeathByJobs" \
    "$PROJECT_ROOT/mac/main.swift" \
    "$PROJECT_ROOT/mac/App.swift" \
    -framework SwiftUI \
    -framework AppKit \
    -framework Foundation \
    -framework UniformTypeIdentifiers

echo "✅  Swift binary → $MACOS_DIR/DeathByJobs"

# ── Bundle Python standalone ──────────────────────────────────────────────────
PYTHON_TARBALL="$BUILD_DIR/python-standalone.tar.gz"
PYTHON_DIR="$BUILD_DIR/python"

if [[ -f "$PYTHON_TARBALL" ]]; then
    echo "📦  Extracting bundled Python…"
    rm -rf "$PYTHON_DIR"
    mkdir -p "$PYTHON_DIR"
    tar -xzf "$PYTHON_TARBALL" -C "$PYTHON_DIR" --strip-components=1
elif [[ -d "$PYTHON_DIR" ]]; then
    echo "📦  Using existing Python directory…"
else
    echo "⚠️   No bundled Python found at $PYTHON_TARBALL or $PYTHON_DIR"
    echo "     The app will require system Python. Continuing anyway…"
fi

# Install Python dependencies into the extracted Python
if [[ -d "$PYTHON_DIR" && -f "$PROJECT_ROOT/requirements.txt" ]]; then
    echo "📦  Installing Python dependencies…"
    "$PYTHON_DIR/bin/pip3" install -r "$PROJECT_ROOT/requirements.txt" >/dev/null 2>&1 || \
        echo "⚠️   pip install failed (some packages may be missing)"
fi

if [[ -d "$PYTHON_DIR" ]]; then
    cp -R "$PYTHON_DIR" "$RES_DIR/python"
    echo "✅  Python bundled → $RES_DIR/python"
fi

# ── Copy backend source & data ──────────────────────────────────────────────
echo "📂  Copying backend resources…"

cp -R "$PROJECT_ROOT/src"         "$RES_DIR/src"
cp -R "$PROJECT_ROOT/config"      "$RES_DIR/config"
# Only copy schedule.json as default; user data files are generated at runtime
cp "$PROJECT_ROOT/data/schedule.json" "$RES_DIR/data/schedule.json" 2>/dev/null || true
cp -R "$PROJECT_ROOT/templates"   "$RES_DIR/templates"
cp -R "$PROJECT_ROOT/context"     "$RES_DIR/context"

cp "$PROJECT_ROOT/.env"             "$RES_DIR/.env"          2>/dev/null || true
cp "$PROJECT_ROOT/base_resume.md" "$RES_DIR/base_resume.md" 2>/dev/null || true
cp "$PROJECT_ROOT/resume.docx"   "$RES_DIR/resume.docx"   2>/dev/null || true
cp "$PROJECT_ROOT/logo.png"     "$RES_DIR/logo.png"
cp "$PROJECT_ROOT/mac/AppIcon.icns" "$RES_DIR/AppIcon.icns" 2>/dev/null || true

# Copy playwright browsers if available
if [[ -d "$PROJECT_ROOT/playwright-browsers" ]]; then
    cp -R "$PROJECT_ROOT/playwright-browsers" "$RES_DIR/playwright-browsers"
    echo "✅  Playwright browsers bundled"
elif [[ -d "$BUILD_DIR/playwright-browsers" ]]; then
    cp -R "$BUILD_DIR/playwright-browsers" "$RES_DIR/playwright-browsers"
    echo "✅  Playwright browsers bundled (from build dir)"
fi

# ── Create backend_launcher.py ────────────────────────────────────────────────
cat > "$MACOS_DIR/backend_launcher.py" <<'PYEOF'
#!/usr/bin/env python3
"""Launcher for the bundled DeathByJobs backend."""
import os
import sys
import shutil
import subprocess

RESOURCE_DIR = os.environ.get("DEATHBYJOBS_RESOURCE_DIR", "")
DATA_DIR = os.environ.get("DEATHBYJOBS_DATA_DIR", "")

if not RESOURCE_DIR or not DATA_DIR:
    print("FATAL: DEATHBYJOBS_RESOURCE_DIR and DEATHBYJOBS_DATA_DIR must be set.", file=sys.stderr)
    sys.exit(1)

for subdir in ["config", "data", "templates", "context", "outputs", "logs"]:
    os.makedirs(os.path.join(DATA_DIR, subdir), exist_ok=True)

def _copy_defaults(src, dst):
    if not os.path.exists(src):
        return
    if os.path.isfile(src):
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    elif os.path.isdir(src):
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            target_root = os.path.join(dst, rel)
            os.makedirs(target_root, exist_ok=True)
            for f in files:
                s = os.path.join(root, f)
                t = os.path.join(target_root, f)
                if not os.path.exists(t):
                    shutil.copy2(s, t)

_copy_defaults(os.path.join(RESOURCE_DIR, "config"), os.path.join(DATA_DIR, "config"))
_copy_defaults(os.path.join(RESOURCE_DIR, "data", "schedule.json"), os.path.join(DATA_DIR, "data", "schedule.json"))
_copy_defaults(os.path.join(RESOURCE_DIR, "templates"), os.path.join(DATA_DIR, "templates"))
_copy_defaults(os.path.join(RESOURCE_DIR, "context"), os.path.join(DATA_DIR, "context"))

for name in ["base_resume.md", "resume.docx", "AI_CONTEXT.md"]:
    s = os.path.join(RESOURCE_DIR, name)
    if os.path.exists(s):
        t = os.path.join(DATA_DIR, name)
        if not os.path.exists(t):
            shutil.copy2(s, t)

env_src = os.path.join(RESOURCE_DIR, ".env")
env_dst = os.path.join(DATA_DIR, ".env")
if os.path.exists(env_src) and not os.path.exists(env_dst):
    shutil.copy2(env_src, env_dst)

src_link = os.path.join(DATA_DIR, "src")
if os.path.islink(src_link):
    os.remove(src_link)
if not os.path.exists(src_link):
    os.symlink(os.path.join(RESOURCE_DIR, "src"), src_link)

os.environ["DEATHBYJOBS_BASE_DIR"] = DATA_DIR
os.environ["DEATHBYJOBS_RESOURCE_DIR"] = RESOURCE_DIR
os.environ["DEATHBYJOBS_DATA_DIR"] = DATA_DIR

python_root = os.environ.get("DEATHBYJOBS_PYTHON_ROOT", "")
if python_root:
    sp = os.path.join(python_root, "lib", "python3.12", "site-packages")
    if sp not in sys.path:
        sys.path.insert(0, sp)

src_dir = os.path.join(RESOURCE_DIR, "src")
sys.path.insert(0, RESOURCE_DIR)
sys.path.insert(0, src_dir)
automation_dir = os.path.join(src_dir, "automation")
if automation_dir not in sys.path:
    sys.path.insert(0, automation_dir)

try:
    import config_loader
    config_loader.BASE_DIR = DATA_DIR
    config_loader.CONFIG_DIR = os.path.join(DATA_DIR, "config")
    config_loader.PROFILE_PATH = os.path.join(config_loader.CONFIG_DIR, "profile.json")
    config_loader.PROVIDERS_PATH = os.path.join(config_loader.CONFIG_DIR, "providers.json")
except Exception:
    pass

api_main = os.path.join(RESOURCE_DIR, "src", "api", "main.py")
if not os.path.exists(api_main):
    print(f"FATAL: API entry point not found: {api_main}", file=sys.stderr)
    sys.exit(1)

# Use uvicorn module to serve the FastAPI app.
# main:app is the FastAPI instance in src/api/main.py
src_dir = os.path.join(RESOURCE_DIR, "src")
os.chdir(src_dir)
sys.path.insert(0, RESOURCE_DIR)
sys.path.insert(0, src_dir)
src_api_dir = os.path.join(src_dir, "api")
if src_api_dir not in sys.path:
    sys.path.insert(0, src_api_dir)

cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"]
cmd.extend(sys.argv[1:])
subprocess.run(cmd)
PYEOF
chmod +x "$MACOS_DIR/backend_launcher.py"
echo "✅  backend_launcher.py created"

# ── Create Info.plist ─────────────────────────────────────────────────────────
cat > "$APP_DIR/Contents/Info.plist" <<'PLISTEOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleExecutable</key>
    <string>DeathByJobs</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.example.DeathByJobs</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>DeathByJobs</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLISTEOF
echo "✅  Info.plist created"

# ── Patch paths (if patch_paths.py exists) ────────────────────────────────────
if [[ -f "$BUILD_DIR/patch_paths.py" ]]; then
    echo "🔧  Patching paths with patch_paths.py…"
    cd "$BUILD_DIR" && python3 patch_paths.py
    echo "✅  Paths patched"
fi

# ── Symlink to repo root for convenience ─────────────────────────────────────
echo "🔗  Linking bundle to repo root…"
rm -rf "$PROJECT_ROOT/DeathByJobs.app"
ln -s "$APP_DIR" "$PROJECT_ROOT/DeathByJobs.app"

# ── Build DMG ─────────────────────────────────────────────────────────────────
echo "💿  Building DMG…"
rm -f "$DMG_PATH"

# Create a temporary disk image
TMP_DMG="$BUILD_DIR/tmp.dmg"
TMP_MOUNT="$BUILD_DIR/mount"

mkdir -p "$TMP_MOUNT"

# Create DMG with hdiutil
hdiutil create -size 1024m -fs HFS+ -volname "DeathByJobs" -srcfolder "$APP_DIR" "$TMP_DMG"

# Convert to compressed read-only DMG
hdiutil convert "$TMP_DMG" -format UDZO -o "$DMG_PATH"

# Cleanup
rm -f "$TMP_DMG"
echo "✅  DMG created → $DMG_PATH"

# ── Final info ────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Build complete!"
echo "═══════════════════════════════════════════════════════════"
echo "  App:  $APP_DIR"
echo "  DMG:  $DMG_PATH"
echo "  Size: $(du -sh "$APP_DIR" | cut -f1) (app)"
echo "        $(du -sh "$DMG_PATH" 2>/dev/null | cut -f1) (dmg)"
echo ""
echo "  Next steps:"
echo "    1. Test the app: open $APP_DIR"
echo "    2. Upload the DMG to GitHub Releases"
echo "═══════════════════════════════════════════════════════════"
