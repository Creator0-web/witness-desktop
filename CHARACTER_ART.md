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

## V1 evolution forms

Character evolution is a presentation layer over the canonical rolling **Level Rating**. It
never awards XP or changes game levels. Forms are earned permanently from the person's peak
Level Rating. The first five thresholds align with current V1 game-level entry thresholds;
forms 6–8 extend the same rating curve beyond the current top game level so the visual journey
can continue without reopening scoring architecture.

| Form | Peak Rating | World | Visual meaning | Asset |
|---|---:|---|---|---|
| Wanderer | 0 | Wild Path | raw potential; barefoot, humble, mysterious beginning | `01_wanderer.png` |
| Seeker | 5,000 | Hidden Ruins | intention; dagger, wraps, first stronger Core | `02_seeker.png` |
| Apprentice | 12,800 | Training Ruins | discipline; stronger body, staff, deliberate training | `03_apprentice.png` |
| Builder | 24,100 | Frontier Outpost | self-creation; first boots, structured gear, built environment | `04_builder.png` |
| Disciplined Man | 39,200 | Old City | control; civilization, refined rugged clothing, quiet confidence | `05_disciplined_man.png` |
| Operator | 55,000 | City Rooftop | precision; tight agile tactical clothing, fast/powerful silhouette | `06_operator.png` |
| Elite | 75,000 | High-Rise Terrace | refinement; tailored high-status look, less visible equipment | `07_elite.png` |
| Sovereign | 100,000 | Sovereign Hall | authority; modern regal presence, minimal visible gear, command | `08_sovereign.png` |

## World progression

The V1 composite artwork intentionally tells one continuous environmental story:

**wild nature → hidden ruins → training ruins → built outpost → old civilization → modern
city → high-status city → command-level city**.

The current artwork is composited character + environment. Therefore V1 treats these as
**chapters/forms**, not independent swappable environments. Unlocked earlier chapters can be
revisited as memories. A later true-3D / layered-asset pass can separate avatar and environment
so a Sovereign can physically stand in the original jungle without showing the Wanderer body.
Do not fake that by displaying an old composite as if it were the current body.

## Core / Charge / Shield

- **Evolution form** = long-term peak Level Rating.
- **Current Charge** = today's canonical battle XP relative to the existing character charge
  target; it only changes the subtle live Core/aura presentation.
- **Protection Shield** = existing monitored clean-streak projection; first unlock at 14 clean
  monitored days, then 30/60/90 strengthening tiers.
- A future **Reserve / Inner Core timer** may be added as a separate user-defined behavioral
  state. It is deliberately not part of this V1 build yet.

## Motion direction

V1 remains 2.5D, not fake 3D:

- art stays dominant;
- drag pans/inspects the scene;
- wheel zooms slightly;
- early forms get subtle moving fireflies/particles;
- city forms get restrained rain;
- current Charge gives the Core a soft pulse;
- an earned Shield adds a restrained protective field;
- no effect may invent XP or game state.

A future true-3D model can replace the renderer while continuing to consume
`shared/character_engine.py`.
