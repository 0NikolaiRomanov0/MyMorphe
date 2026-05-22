# MyMorphe - Auto-Patched APKs

## Description
Automated daily builds of YouTube, YouTube Music, and Reddit APKs patched with Morphe.

## Tech Stack
- Python
- Morphe CLI/patches for patching
- APKEditor for XAPK conversion
- Uptodown as APK source

## Current Status
- Working: YouTube, YouTube Music, Reddit download and patch
- In Progress: Testing Reddit support

## Goals
- [ ] Verify Reddit patching works with Morphe
- [ ] Test full download-patch workflow for Reddit

## Recent Changes
- Added Reddit support (com.reddit.frontpage)
- Added Uptodown source: https://reddit-official-app.en.uptodown.com/android/apps/179119
- Made scraper URL generation dynamic per app