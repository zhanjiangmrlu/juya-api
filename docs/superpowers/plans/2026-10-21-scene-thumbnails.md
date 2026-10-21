# Scene thumbnails and on-demand originals

Approved specification: the 2026-10-21 plan in the current chat

## Task 1: Published thumbnail contract

Expose the existing current-publication thumbnail_id on PublishedDetail, export contracts and regenerate the miniapp types. Test that unpublished candidate images never replace that thumbnail and that its controlled URL is readable

## Task 2: Miniapp image separation

Use a common image selector (thumbnail by default, original explicitly). Render detail thumbnails directly, separate original download/cache/error state, and request originals only after opening the viewer. Test cold detail entry, thumbnail failure/retry, concurrent original opens, missing thumbnails, stale responses and preservation of the thumbnail after an original failure

## Task 3: Admin image selection

Use the common selector for list thumbnails and explicitly for the original viewer. Add lazy loading and image failure placeholders with retry. Keep version verification and existing zoom/scroll behavior

## Task 4: Verification

Run both frontend suites, checks and builds, the backend suite and lint, then review the complete diff and verify image requests in browser/WeChat where the available runtime permits. Do not deploy or claim real-device verification without evidence
