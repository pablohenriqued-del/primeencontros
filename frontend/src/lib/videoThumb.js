// Extracts a JPEG frame from a video File or URL using HTMLVideoElement + canvas.
// Returns a Blob (JPEG) or null on failure.
export async function extractVideoThumb(source, { atSeconds = 1.0, maxWidth = 960, quality = 0.82 } = {}) {
  return new Promise((resolve) => {
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    video.crossOrigin = "anonymous";

    let objectUrl = null;
    if (source instanceof Blob) {
      objectUrl = URL.createObjectURL(source);
      video.src = objectUrl;
    } else if (typeof source === "string") {
      video.src = source;
    } else {
      resolve(null);
      return;
    }

    const cleanup = () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };

    const fail = () => { cleanup(); resolve(null); };

    video.addEventListener("error", fail, { once: true });

    video.addEventListener("loadedmetadata", () => {
      const target = Math.min(atSeconds, Math.max(0, (video.duration || 0) - 0.1));
      const seekTo = isFinite(target) && target > 0 ? target : 0.1;
      try {
        video.currentTime = seekTo;
      } catch {
        fail();
      }
    }, { once: true });

    video.addEventListener("seeked", () => {
      try {
        const w = video.videoWidth;
        const h = video.videoHeight;
        if (!w || !h) { fail(); return; }
        const scale = w > maxWidth ? maxWidth / w : 1;
        const cw = Math.round(w * scale);
        const ch = Math.round(h * scale);
        const canvas = document.createElement("canvas");
        canvas.width = cw;
        canvas.height = ch;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, cw, ch);
        canvas.toBlob((blob) => {
          cleanup();
          resolve(blob || null);
        }, "image/jpeg", quality);
      } catch {
        fail();
      }
    }, { once: true });

    // Safety timeout (10s)
    setTimeout(() => { if (!video.videoWidth) fail(); }, 10000);
  });
}
