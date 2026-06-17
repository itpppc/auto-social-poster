---
name: project-tiktok-approach
description: TikTok posting approach — Photo Mode blocked, switched to Video FILE_UPLOAD with slideshow
metadata:
  type: project
---

TikTok Photo Mode (PULL_FROM_URL) is blocked for unaudited apps — requires domain ownership verification. Switched to Video FILE_UPLOAD approach: download Pexels images, create MP4 slideshow using imageio + Pillow, upload as video file.

**Why:** TikTok's `url_ownership_unverified` error blocks PULL_FROM_URL for any domain not owned by the developer. `FILE_UPLOAD` has no such restriction.

**How to apply:** Always use `_upload_video_file()` via `post_photo_mode()` or `upload_video()` in `tiktok_poster.py`. Never use PULL_FROM_URL with Pexels or third-party URLs.

Also: unaudited sandbox app can only post to private TikTok accounts. @ton.ai.40 must remain PRIVATE until app passes TikTok review.
