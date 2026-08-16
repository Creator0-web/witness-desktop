# WITNESS 3D asset contract

v7.56 ships a dependency-free procedural 3D prototype in `ui_qt/character_3d.py` so rotation,
zoom, idle motion, Core/Charge response and stage styling can be tested in the real Windows app
without introducing a fragile graphics dependency.

This mesh is intentionally not the final Character art. If the interaction proves worth keeping,
the production replacement should be one rigged, identity-consistent character asset with stage
outfit variants, ideally exported as GLB/glTF with:

- one humanoid skeleton and stable bone names across all forms,
- neutral idle pose + breathing idle animation,
- separate material slots for skin, hair, clothing, green continuity accent and Core emissive area,
- stage outfit variants rather than eight unrelated body meshes,
- no personal/user data embedded in assets,
- environments as separate assets so a Sovereign can revisit the original jungle.

Do not couple 3D state to scoring. `shared/character_engine.py` remains the data contract.
