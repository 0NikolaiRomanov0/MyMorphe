# MyMorphe - Auto-Patched APKs

Automated daily builds of YouTube, YouTube Music, and Reddit APKs patched with Morphe.

## What is Morphe?

Morphe is a patcher that adds features to YouTube (ReVanced-like features) without needing root. It patches YouTube and YouTube Music to remove ads, enable background play, and more.

## How to Get the APKs

1. Go to the **[Releases](https://github.com/0NikolaiRomanov0/MyMorphe/releases)** page
2. Download the latest version of any of:
   - `youtube-morphe-v<ver>-mpp<mpp-ver>.apk` — YouTube
   - `youtube-music-morphe-v<ver>-mpp<mpp-ver>.apk` — YouTube Music
   - `reddit-morphe-v<ver>-mpp<mpp-ver>.apk` — Reddit
3. Install the APK on your Android device

*Filenames include both the app version and the Morphe patches version so updates to either trigger new builds.*

## IMPORTANT: Install MicroG-RE First

Before installing the patched YouTube, you **must** install MicroG-RE:

1. Go to: **https://github.com/MorpheApp/MicroG-RE/releases**
2. Download and install the latest MicroG-RE APK
3. Keep it updated! MicroG-RE is required for the patched YouTube to work.

Without MicroG-RE, the patched YouTube app will crash or won't sign in.

## FAQ

### Do I need root?
No! These APKs work on any Android device without root.

### How do I update?
**Option 1 - Manual:** Check the Releases page for new versions and download manually.

**Option 2 - Automatic (Recommended):** Use [Obtainium](https://github.com/ImranR98/Obtainium/releases) to auto-update:

1. Install Obtainium from the Play Store or GitHub
2. Tap **Add App** → Paste this URL in "App source URL": `https://github.com/0NikolaiRomanov0/MyMorphe`
3. Scroll down to **Filter APKs by regular expression** and type:
   - For YouTube: `youtube-morphe-v`
   - For YouTube Music: `youtube-music-morphe-v`
   - For Reddit: `reddit-morphe-v`
4. Enable "Follow GitHub releases" in the app settings
5. Obtainium will notify you when new versions are available

*Note: Add the repo multiple times if you want auto-updates for more than one app.*

### Are these safe?
Yes. The source code is available here. Morphe is a well-known open-source patcher.

## Support

- **Website:** [morphe.software](https://morphe.software/)
- **GitHub:** [MorpheApp](https://github.com/MorpheApp)
- **X/Twitter:** [@MorpheApp](https://x.com/MorpheApp)
- **Reddit:** [r/MorpheApp](https://www.reddit.com/r/MorpheApp/)
- **Crowdin:** [Translate Morphe](https://crowdin.com/project/morphe)
- **Report Issues:** [here](https://github.com/0NikolaiRomanov0/MyMorphe/issues)

## Auto-Build

This repository automatically checks daily for new versions of YouTube, YouTube Music, and Reddit, then builds and releases patched APKs when available.