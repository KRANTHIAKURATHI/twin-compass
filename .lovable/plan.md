## Goal

Fix the remaining alignment problems visible in the four screenshots — uneven card heights, ragged action rows, floating status chips and inconsistent icon-button sizing.

## What's wrong today

1. **Document Center (`_shell.documents.tsx`)** — grid cards are not equal height, so the Preview / Versions / download row sits at a different vertical position in each card. The download button is a bare icon that doesn't match the height of the two adjacent small buttons, and the badge row wraps unpredictably.
2. **My Reports (patient portal)** — each row is `flex items-center gap-3` with the status chip in the natural text flow, so "Verified" / "Pending OCR" / "Needs review" land at different x positions from card to card, and the eye/download icons don't sit on a shared right-hand column.
3. **OCR Verification** — the two panels have different content heights and the stepper row items don't share a common baseline; the step connector line sits off-center against the numbered circles.
4. **Patient Notifications** — the bell avatar, title/body block and timestamp are not on a shared grid; unread cards get an extra border that shifts content by 1px versus read cards.

## Changes

**Document Center**
- Make grid cells stretch: card gets `flex h-full flex-col`, `CardContent` gets `flex flex-1 flex-col`, and the action row gets `mt-auto` so all action rows line up across a row.
- Give the badge row a fixed min-height so cards with two vs three chips stay aligned.
- Convert the download control to the same `size="sm"` button shape as its siblings (icon-only but matching height), and put the action row on one non-wrapping line with `items-center`.

**My Reports (patient)**
- Restructure each row into three fixed zones: icon, flexible title/meta block, then a right-aligned `ml-auto` cluster holding the status chip plus the two icon buttons.
- Chip gets a fixed min-width so chips align vertically down the column; icon buttons standardized to one size.

**OCR Verification**
- Equalize the two panels with `items-stretch` on the grid and `h-full` on both cards.
- Align the stepper: each step is a flex row with `items-center`, the connector line centered against the circle, and consistent gap so labels share a baseline.

**Patient Notifications**
- Same three-zone row: avatar, content, right-aligned timestamp.
- Replace the unread border swap with a same-width border (transparent when read) so content never shifts, matching the doctor-portal notifications pattern.

## Verification

Re-render each of the four pages at both desktop and the 650px viewport the user is on, and confirm equal card heights, aligned action rows and a straight right-hand column of chips/icons.
