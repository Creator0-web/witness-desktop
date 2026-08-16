# WITNESS — Character Art Bible (V1)

This file records the approved visual progression so future UI/art work does not drift.
The eight images in `ui_qt/assets/character/` are the **approved original concepts** selected
by the person on 2026-08-16. Later regenerated versions that made the character look thinner,
bonier, sweatier/wirier are **not** the canonical V1 art direction.

## Identity continuity

Across every form, he must still read as the same person:

- light-brown / tan lightskin complexion;
- dark curly hair;
- quiet, introspective, solitary energy;
- healthy, athletic progression — never gaunt, wirey or over-cut;
- calm seriousness rather than loud aggression;
- increasingly upright/composed posture as the forms progress;
- the inner Core exists beneath the clothing and should feel like energy coming from inside,
  not a pasted-on superhero logo;
- the original green sash/motif is obvious early, then becomes subtler as status rises.

## v7.56 interactive 3D prototype

The approved original images remain the **canonical visual art direction**. v7.56 adds a separate
`3D LAB` on the Character page to test whether true rotation/zoom/idle state feels worth pursuing.
The lab uses a lightweight procedural humanoid mesh and deliberately does not try to impersonate
the final face/art quality. Portrait remains the default.

The lab must preserve these stage cues: early forms barefoot and lightly equipped; Apprentice trains;
Builder gains boots/structure; Disciplined Man enters civilization; Operator is tight/agile rather than
bulky; Elite removes visible gear and becomes tailored; Sovereign stays athletic with a slim modern
commanding layer. The green continuity motif shrinks with progression. Core Reserve maps to the
chest-space glow and Daily Charge to a separate outer field.

If the interaction is approved, the next 3D-art step is **one** rigged identity-consistent character
with outfit variants, not eight unrelated people. See `ui_qt/assets/3d/README.md`.

## V1 evolution forms

Character evolution is now aligned **one-for-one with the canonical rolling Level ladder**.
It never awards XP. The active form follows the current canonical level, while the highest
historically earned form stays available in the Journey strip as an unlocked memory. The full
ladder is now eight levels, using the same thresholds the art progression was already designed
around.

| Level / Form | Rating threshold | World | Visual meaning | Asset |
|---|---:|---|---|---|
| 1 · Wanderer | 0 | Wild Path | raw potential; barefoot, humble, mysterious beginning | `01_wanderer.png` |
| 2 · Seeker | 5,000 | Hidden Ruins | intention; dagger, wraps, first stronger Core | `02_seeker.png` |
| 3 · Apprentice | 12,800 | Training Ruins | discipline; stronger body, staff, deliberate training | `03_apprentice.png` |
| 4 · Builder | 24,100 | Frontier Outpost | self-creation; first boots, structured gear, built environment | `04_builder.png` |
| 5 · Disciplined Man | 39,200 | Old City | control; civilization, refined rugged clothing, quiet confidence | `05_disciplined_man.png` |
| 6 · Operator | 55,000 | City Rooftop | precision; tight agile tactical clothing, fast/powerful silhouette | `06_operator.png` |
| 7 · Elite | 75,000 | High-Rise Terrace | refinement; tailored high-status look, less visible equipment | `07_elite.png` |
| 8 · Sovereign | 100,000 | Sovereign Hall | authority; modern regal presence, minimal visible gear, command | `08_sovereign.png` |

## World progression

The V1 composite artwork intentionally tells one continuous environmental story:

**wild nature → hidden ruins → training ruins → built outpost → old civilization → modern
city → high-status city → command-level city**.

The current artwork is composited character + environment. Therefore V1 treats these as
**chapters/forms**, not independent swappable environments. Unlocked earlier chapters can be
revisited as memories. A later true-3D / layered-asset pass can separate avatar and environment
so a Sovereign can physically stand in the original jungle without showing the Wanderer body.
Do not fake that by displaying an old composite as if it were the current body.

## Evolution / Charge / Core Reserve / Shield

- **Current evolution form** = current canonical rolling Level (1–8).
- **Unlocked memories** = historically earned peak level; a normal later demotion does not erase the chapter.
- **Daily Charge** = today's canonical battle XP relative to the existing character charge target.
  It drives a restrained **outer aura** only; it does not define the inner Core.
- **Core Reserve** = an explicit user-controlled 14-day personal timer stored in `game_state`.
  Start/Reset is intentional and independent of XP, Level, unlocked forms, Charge and Shield.
  It is a behavioral/visual metaphor, not a medical measurement. Reserve state progresses
  SPARK → AWAKE → BUILDING → STEADY → VIBRANT and drives the **inner chest glow**.
- **Protection Shield** = monitored clean-streak projection; first unlock at 14 clean monitored
  days, then 30/60/90 strengthening tiers. Missing telemetry never counts as a clean day.

## Motion direction

V1 remains 2.5D, not fake 3D:

- art stays dominant;
- pointer movement gives gentle parallax/depth and drag still pans the scene;
- wheel zooms slightly;
- the composite scene has a barely perceptible breathing/camera drift;
- early forms get drifting fog plus subtle fireflies/particles;
- city forms get restrained rain and low haze;
- Core Reserve gives the inner chest light a soft pulse;
- Daily Charge gives the character a separate restrained outer aura;
- an earned Shield adds a restrained protective field;
- form changes cross-fade rather than snapping; a real canonical evolution also gets a brief dark/reveal + gold-ring moment;
- no effect may invent XP or game state.

A future true-3D model can replace the renderer while continuing to consume
`shared/character_engine.py`.

## Undo / correction behavior (v7.54)

Manual Undo is treated as a correction to the immutable XP ledger, not as ordinary weak
performance. If an accidental/test Activity created a level-up, reversing those events
immediately reconciles current level and historical peak against the corrected ledger instead
of making the false level linger through the normal 48-hour demotion grace. Normal decay still
uses the existing demotion rules.
