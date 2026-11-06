# ANCHOR — production bible (read fully before touching anything)

A 90-second anime short, 24 fps, 1920x1080, no dialogue, no mascot. Look target: the reference frames
(archer, whales, wave, breach): saturated cobalt sky, white cumulus with
lavender shadows, cobalt-turquoise sea with drawn whitecaps, hard cel shading, ink lines, gouache backgrounds, dense detail,
weathered machines. High-key: drama comes from scale and light, never from murk.

## Story
A floating island-city, HIGH HARBOR, hovers 320-530 m above a bay, held by one colossal stud-link chain anchored to the seabed.
In the port below, in dry dock 3, an 80 m harbor mech, unit 07, has slept for decades: moss, vines, rust, a gull nesting on its head.
A storm rolls in from the west. Lightning strikes the chain, the discharge runs down to the anchor, the shackle pin shears,
the chain whips free and the city starts to drift toward a waterspout. The free chain end smashes the crane by dry dock 3;
lightning hits the mech's antenna; its visor lights. It rises, wades out, sprints along the breakwater past the lighthouse, leaps,
catches the last link, is dragged, winds the chain round the lighthouse like a bollard, and holds. The waterspout passes the
city by metres. The clouds tear open; the gull returns to its nest; the visor dims.
Setups -> payoffs: gull on the head -> gull returns; lighthouse in act 1 -> holds the city in act 6; the lightning that breaks
the chain -> the lightning that wakes the mech.

## World (metres, Blender Z up, sea level z = 0, north +Y, east +X)
- Sun: low morning sun from the EAST (azimuth ~95 deg, elevation 14-22 deg). Storm and waterspout in the WEST (-X).
  Screen direction: the city drifts and the mech runs toward the west, usually screen-left.
- City collar (bottom tip of the floating rock, where the chain hangs): (-100, 150, 320) at rest. City top surface ~z 530.
- Anchor shackle on the seabed: (-100, 150, -52). Harbour seabed -12 m by the quay, falling to a trench -60 m under the city.
- Shore and quay: along y = 400, quay top z = +4. Land rises north behind the port to ~180 m hills at y ~ 1200.
- DRY DOCK 3: basin x -510..-410, y 400..600, floor z = -14, caisson gate at y = 400. The mech sits inside against the north wall.
- CRANE A (the one the chain smashes): ship-to-shore gantry crane at (-370, 395), first of 4 cranes along the quay to the east.
- West breakwater: x = -700 from y = 400 (shore) to y = -150; LIGHTHOUSE at its tip (-700, -168). East breakwater (600,400)->(400,60).
- Fishing boats moor in the harbour near (100..300, 330..380).
- The city drifts from (-100,150) toward (-650,-350) during acts 3-5; the waterspout comes from (-3500,-2500) to ~(-1150,-900).

## Departments and file ownership (never edit another department's files; ask the lead in your final report instead)
| Dept | Owns | Builds |
|---|---|---|
| LEAD | `kit/*`, `BIBLE.md`, `shots/*`, `assets/chain.py`, `out/shots` | look, env, post, QA, chain, cameras, animation, render |
| MECH | `assets/mech.py`, `assets/preview_mech.py`, `out/preview/mech*` | unit 07, its rig and pose API |
| CITY | `assets/city.py`, `assets/preview_city.py`, `out/preview/city*` | High Harbor |
| PORT | `assets/port.py`, `assets/preview_port.py`, `out/preview/port*` | port, dry dock, cranes, containers, town, boats, breakwaters, lighthouse |
| UNDER | `assets/under.py`, `assets/preview_under.py`, `out/preview/under*` | seabed, anchor + shackle + pin, kelp, coral, fish |
| FX | `assets/fx.py`, `assets/preview_fx.py`, `out/preview/fx*` | lightning, storm wall, waterspout, splashes, foam, steam, sparks, debris, silt |

## How to work
- Blender: `blender` (5.2 LTS, Eevee). Run from the project root:
  `blender -b -P assets/preview_x.py -- 50 16` (res %, samples). Previews at 50 % are fine; look at every still you render.
- Put `sys.path.insert(0, <root>/kit)` and `sys.path.insert(0, <root>/assets)` at the top of scripts; `import look as LK, env as EV, preview as PV, qa as QA`.
- `PV.setup(preset, sun=(az, el))` gives the shared sky, sun, sea, clouds; build your asset; `PV.shoot(sc, 'name', views)` renders
  each view as one frame, runs the post (ink, haze, bloom, grade) and writes `out/preview/name/post/fNNNN.png` and `sheet.jpg`.
  Read the post-processed PNGs at full size with the Read tool and judge them against the reference frames.
- GPU: renders go through a lock (`EV.gpu_lock`, already inside `PV.shoot`). Never start a render outside it.
- Python 3.13 + numpy + opencv are available outside Blender (`python`). Do not pip install anything.
- Build speed: `build()` must finish in < 90 s of Python. Use linked duplicates (objects sharing one mesh) for repeats.

## Look rules (non-negotiable)
1. Every material comes from `kit/look.py`: `LK.cel(name, color_or_fn, ink, paint, spec, rim, vary, grime, scuff, chips, rust, algae,
   waterline, wscale)`, `LK.glowmat` for self-lit things, `LK.flat` for unlit cards. Custom colour logic goes in a callable
   `lambda nb: ...` using the `NB` helpers (noise, voronoi, wave, stripes, image, ramp, mixc, attr, objattr). Never a Principled BSDF.
2. `ink=1` for machines, buildings, props, characters (lines come from depth/normal/id edges in the post); `ink=0` for sky, clouds,
   water, mist, glow, FX; `paint=1` for terrain, rock, distant land, clouds (the gouache brush only paints those pixels).
3. NO coplanar overlapping faces, ever (z-fighting). Markings, stencils, numbers, windows, stripes, grime are drawn IN the shader
   (`nb.stripes`, `nb.image` with a texture you generate into `tex/` with PIL or cv2, procedural masks) on the same face, not as
   separate decal planes. Separate plates must stand >= 2 % of their thickness off the surface or be real closed solids.
4. NO interpenetrating separate objects except designed contacts (a house base sunk into terrain, a foot in the sea, a pile in the
   seabed). Every department runs `QA.overlaps(objs, allow=...)` on its own build and reports zero unexpected pairs.
5. Detail density: no empty flat surface bigger than ~1/6 of the frame in your previews. Panels, bolts, seams, pipes, vents,
   ladders, railings, windows, signage, wear. Bevel edges (Bevel modifier, segments 1-2) so the cel light catches them.
6. Palette anchors: safety yellow #f2b705, steel #3b4152 / #4b5163, rust #9a4f2a, terracotta #c8553d, lighthouse red #d23a2e,
   white walls #f1ead8, teal #2a8f8a, moss #6b8f3a, crystal cyan #5fe3ff, deep sea #1238b8, shallow #22c7d6, ink #2a2236.
7. Characters/machines animate on twos, FX on threes (the lead keys them; your API must allow it).

## Scene uniforms (scene custom props, keyable; materials read them with `nb.attr(name)`)
`sunD sunC skyC shadeC bounceC deepC flashC flash wet seaT seaCalm seaRough skyStorm cloudStorm`. Use `flash` (0..1 lightning)
and `wet` (0..1) in self-lit materials too when it makes sense. Object custom props are read with `nb.objattr(name)` (e.g. the
mech's `eyes`, the shackle's `heat`, a crystal's `power`); expose such props for anything the lead must animate.

## Deliverable of every department
- `assets/<dept>.py` with `build(parent_collection, **opts) -> dict` returning named objects/empties the lead animates, plus the
  documented API below. Pivots at real hinge points. Names prefixed by department (MECH_, CITY_, PORT_, LH_, UNDER_, FX_).
- `assets/preview_<dept>.py` rendering >= 6 views that show the asset like the shots will (see shot list), at 50 % res.
- A self-review: what you checked, QA.overlaps result, build time, triangle count, and the API summary, in your final message.

## Shot list (t in seconds; frame = round(t*24)+1). Departments: preview the views your asset plays in.
| # | t | Shot | Needs |
|---|---|---|---|
| 01 | 0.0-3.0 | EST: High Harbor above scattered cumulus at sunrise, camera arcs; waterfalls into the void; the chain going down | CITY, sky |
| 02 | 3.0-4.6 | CU street: windmill sails sweep past, laundry flapping, bell tower behind | CITY |
| 03 | 4.6-7.4 | The camera dives along the chain through clouds, links rushing past, the port appears below | chain, CITY, PORT |
| 04 | 7.4-9.6 | WIDE port at dawn: cranes, containers, dry dock 3 with the sleeping overgrown mech, the chain in the distance, lighthouse | PORT, MECH |
| 05 | 9.6-11.2 | MACRO: the mech's head, gull nest with a chick, moss, dark visor, "07" stencil | MECH |
| 06 | 11.2-14.0 | UNDERWATER: the coral-covered anchor, shackle and pin, fish schools, god rays, the chain rising | UNDER, chain |
| 07 | 14.0-16.4 | From the city rim: the storm wall on the western horizon, lightning inside; weather vanes swing | CITY, FX |
| 08 | 16.4-18.4 | Fishing boats race home past the lighthouse, waves rising, spray | PORT, FX |
| 09 | 18.4-20.0 | City: windmills spin wildly, the bell swings (alarm), laundry torn away | CITY |
| 10 | 20.0-22.0 | CU the iron collar under the city: chain goes taut, rivets pop, rust dust | CITY, chain, FX |
| 11 | 22.0-24.4 | WIDE: the waterspout forms from the storm base and touches the sea | FX |
| 12 | 24.4-25.8 | Lightning strikes the chain at the collar | FX, CITY, chain |
| 13 | 25.8-28.0 | The discharge runs down the chain link by link into the sea | chain, FX |
| 14 | 28.0-30.0 | UNDERWATER: the shackle glows red-hot, fish flee, water boils | UNDER, FX |
| 15 | 30.0-31.6 | MACRO: the shackle pin shears, silt explodes | UNDER, FX |
| 16 | 31.6-33.2 | Underwater: the chain whips up past the camera | chain, UNDER |
| 17 | 33.2-35.2 | The chain bursts out of the bay in a wall of spray | chain, FX, PORT |
| 18 | 35.2-37.4 | City lurches and tilts: houses shudder, roof tiles rain, a waterfall bends | CITY, FX |
| 19 | 37.4-39.0 | Under the city: the blue crystals flare | CITY |
| 20 | 39.0-42.0 | WIDE: the city drifts toward the waterspout, chain end dragging a spray trail, lighthouse in the foreground | CITY, chain, PORT, FX |
| 21 | 42.0-44.0 | The chain end smashes crane A, containers fly, a wave hits the dock | PORT, chain, FX |
| 22 | 44.0-45.6 | Water and debris crash over the sleeping mech; the gull flees the nest | MECH, FX |
| 23 | 45.6-47.4 | Lightning strikes the mech's antenna | MECH, FX |
| 24 | 47.4-49.0 | EXTREME CU: the visor eyes power on | MECH |
| 25 | 49.0-52.4 | It rises, tearing vines and rust, moss falling, gulls scatter (low angle) | MECH, PORT, FX |
| 26 | 52.4-55.0 | The first step into the sea, a huge splash; it looks up at the drifting city | MECH, FX, CITY |
| 27 | 55.0-57.4 | Tracking: it runs through the harbour shallows, spray | MECH, FX, PORT |
| 28 | 57.4-59.0 | Fishing boats pass between its legs the other way | MECH, PORT |
| 29 | 59.0-61.0 | The city near the waterspout, debris spirals, the chain end skips over the waves | CITY, FX, chain |
| 30 | 61.0-63.4 | It runs along the breakwater past the lighthouse (low angle from the gallery) | MECH, PORT |
| 31 | 63.4-65.4 | It leaps from the breakwater tip against lightning (silhouette) | MECH, FX |
| 32 | 65.4-67.2 | Lands waist-deep, ring wave | MECH, FX |
| 33 | 67.2-70.0 | The hand reaches, the last link skips away, the hand closes on it | MECH, chain |
| 34 | 70.0-72.0 | The chain snaps taut throwing off water; its feet plough the seabed | MECH, chain, FX |
| 35 | 72.0-73.6 | CU: armour cracks, steam from the joints, visor flickers | MECH, FX |
| 36 | 73.6-76.0 | From the mech looking up: the city like a stone sky, the waterspout beside it | CITY, FX, chain |
| 37 | 76.0-78.6 | It winds the chain round the lighthouse; the lighthouse bends and holds | MECH, PORT, chain |
| 38 | 78.6-80.6 | The waterspout passes the city by metres; windmill sails ripped off | CITY, FX |
| 39 | 80.6-82.0 | The chain shudders and slackens; the city stops | chain, CITY |
| 40 | 82.0-84.4 | Clouds tear open, sunbeams, the city levels, waterfalls straight again | CITY, sky |
| 41 | 84.4-86.4 | WIDE: the mech in calm golden water holding the chain round the lighthouse | MECH, PORT, chain |
| 42 | 86.4-88.2 | The gull returns to its nest on the head | MECH |
| 43 | 88.2-90.0 | The visor dims | MECH |

## Department briefs

### MECH — unit 07 (`assets/mech.py`)
80 m to the top of the head standing. Heavy industrial harbour labour mech: broad shoulders (~44 m across), barrel chest with a
recessed cockpit-like chest vent, small head with ONE wide visor band (dark glass; behind it two amber eye lights that turn on via
object prop `eyes` 0..1, plus scanlines), a lightning-rod antenna mast on the head (the bolt in shot 23 hits its tip: empty
`MECH_antenna_tip`). Long arms (fingertips reach mid-thigh), big hands (~11 m) with THREE fingers + an opposable thumb, claw-capped,
each finger 3 segments with pivots (curl API). Thick legs, knee guards with hazard stripes, wide flat feet (~18 m long) with toe plates.
Hydraulic pistons at elbows/knees (chrome rods), 2-3 exhaust stacks on the back (steam empties `MECH_steam_*`), shoulder beacons
(orange, prop `beacon`), stencils "07" on chest and shoulder, "DOCK 3" / "HARBOR AUTHORITY" on a leg, all in-shader. Weathering:
chipped yellow paint, rust runs, grime; overgrowth as SEPARATE objects (moss pads on the head/shoulders/arms, hanging vines, a
twig nest 4 m wide on the head with a gull chick and an adult gull as simple low-poly cel birds with wing pivots) so the lead can
tear vines off (they must be separate objects with origins at their attachment points) and fly the gull.
API: `M = build(coll)`; `M['root']` (empty at the pelvis floor projection), `M['parts'][name]`, `set_pose(M, pose)` with pose =
{'root': (x,y,z,yaw_deg), 'pelvis': (rx,ry,rz), 'spine', 'chest', 'neck', 'head', 'shoulderL/R', 'elbowL/R', 'wristL/R',
'fingersL/R': curl 0..1, 'thumbL/R': curl 0..1, 'hipL/R', 'kneeL/R', 'ankleL/R'} in degrees, plus `leg_ik(M, side, foot_pos,
foot_yaw)` and `arm_ik(M, side, hand_pos, pole)` that solve and set the joint angles (analytic two-bone IK), `key_pose(M, frame)`
that keyframes every part. Provide `POSES = {'sleep': ..., 'stand': ..., 'crouch': ..., 'reach': ..., 'pull': ...}` where
'sleep' is sitting slumped against a wall: back at the wall, legs forward with knees bent, arms resting, head bowed (the floor is
the root's z). Contact empties: `MECH_soleL/R`, `MECH_palmL/R`. Joints must not show gaps or poke through armour in any pose in
POSES (ball/cylinder joints hidden inside armour). Preview: front 3/4 standing, back 3/4, head macro with nest (shot 05), the
sleeping pose inside a 100 x 200 m box with 18 m walls (dock), a hand gripping an 8 m oval ring, a low-angle hero shot.

### CITY — High Harbor (`assets/city.py`)
Floating island: an irregular top ~340 x 280 m; a rock body hanging 210 m below it, tapering to a point at the bottom (the collar).
Rock: strata bands (ochre, sienna, violet-grey), cliff facets, overhangs, ledges with small trees, hanging roots/vines.
Top: gentle hills, a central hill with a bell tower (campanile ~45 m, bell `CITY_bell` with a pivot for swinging), a water tower,
6 windmills (~20 m, 4 lattice sails each `CITY_sails_i` rotating about their hub axis), ~300 houses (2-4 storeys, 8-12 m, white/cream
/pastel walls, terracotta and teal roofs, windows+shutters+doors in-shader, chimneys), stepped streets, little bridges, gardens and
round trees, laundry lines between houses (cloth pieces `CITY_cloth_*` able to flap: give them a Wave modifier or shape keys),
railings and balconies at the cliff edge, lamps. 3-4 waterfalls pouring off the rim (ribbons with a scrolling material driven by
`seaT`, falling ~300 m and fraying into mist). Underside: clusters of blue levitation crystals (hex prisms; glow with prop `power`
0..2). Bottom tip: the IRON COLLAR, an 18 m ring with bolts, rivets, rust streaks, and an eye/lug where the chain's top link hangs:
empty `CITY_chain_top` at the hanging point. API: `C = build(coll)`, `C['root']` empty at the collar point (-100,150,320) - moving
it moves the whole city (tilt/drift); lists `C['sails']`, `C['cloth']`, `C['tiles']` (20-40 loose roof tiles that can fall),
`C['falls']`, `C['crystals']`, `C['bell']`, `C['vanes']`. Preview: establishing from 600 m away slightly above (shot 01), a street
close-up at 2 m height (shot 02), the rim with the storm horizon (07), under the city looking up at the crystals and collar (19, 36).

### PORT — port, dock, cranes, town, boats, breakwaters, lighthouse (`assets/port.py`)
Quay along y = 400 (top z = +4): concrete quay wall with fenders, bollards, ladders, rails, lamps. Land rising behind: warehouses
with sawtooth roofs, silos, offices, a hillside town (white houses, terracotta roofs) climbing to the hills, trees, roads; far land
painted (`paint=1`). DRY DOCK 3 (see World) with stepped walls, keel blocks, puddles, a caisson gate, two rail cranes on its sides,
signage "3" in-shader. Container terminal east of the dock: 4 ship-to-shore cranes (~70 m legs+boom, red/white), CRANE A first at
(-370,395) built from separable parts with pivots (`PORT_craneA_boom`, `_cab`, `_legs`, `_trolley`) so the lead can break it;
hundreds of containers (12 m and 6 m, corrugated in-shader, saturated colours, logos/letters in-shader) in stacks (linked
duplicates), straddle carriers. 6-8 fishing boats (15-22 m trawlers, colourful hulls, cabins, masts, booms, nets, buoys), each a
separate root empty `PORT_boat_i` for the lead to move. West breakwater: rubble mound + concrete cap path (top z +5, 14 m wide)
with tetrapods (4-legged concrete units, instanced, not interpenetrating each other) on the seaward side; the LIGHTHOUSE at the tip:
red/white banded tower 32 m, gallery with railing, lantern room with a lamp (`LH_lamp`, prop `beam` and a rotating beam cone), a
small base house; built as `LH_base`, `LH_mid`, `LH_top` with pivots at the joints so it can bend, crack prop `crack` 0..1 drawn in
shader. East breakwater simpler. Preview: wide port at dawn from (-200, 50, 120) (shot 04), crane A close (21), boats passing the
lighthouse (08), the breakwater from low near the tip (30), the lighthouse close (37).

### UNDER — seabed, anchor, shackle (`assets/under.py`)
Seabed mesh: -12 m by the quay sloping to a trench -60 m under the city at (-100,150), rocks, sand ripples, kelp forests (tall
ribbons 10-25 m, sway driven by `seaT`), coral heads (colourful), sea grass, a sunken wooden boat. The ANCHOR: a giant stockless
ship anchor ~28 m tall lying on the seabed with flukes half buried, encrusted with coral, barnacles, sponges, algae; its shank
top carries a D-SHACKLE (`UNDER_shackle`, prop `heat` 0..1 = red-hot glow drawn in shader) closed by a PIN (`UNDER_pin` made of two
halves `UNDER_pin_a/b` with pivots so it can shear). The chain's first link passes through the shackle bow: empty `UNDER_chain_end`
at the bow centre (-100,150,-52) oriented along the chain. Fish: `fish_school(coll, center, radius, count, seed)` returning
instanced fish objects plus `animate_school(objs, f0, f1, ...)` for circling and fleeing. Marine snow, god-ray cards (drawn light
shafts, `ink=0`), caustics on the seabed in shader. Underwater look: the post supports `under` (fog toward a water colour by depth);
also give materials a cooler tint. Preview: the anchor wide with the chain rising (06), the shackle macro (15), kelp + fish.

### FX (`assets/fx.py`)
Drawn effects, on threes, cel/flat materials, ink 0 unless noted:
`bolt(name, p0, p1, seed, branches=4, width=1.0)` lightning (white core, violet-cyan glow, glow AOV) + `flicker(obj, frames)`;
`storm_wall(coll)` a cumulonimbus mass 6-12 km west (dark indigo underside, bright sunlit top edge, shelf cloud, rain curtains as
streak cards, inner flashes via prop); `waterspout(coll)` funnel from cloud base ~900 m to the sea (twisting striped translucent
material, base spray ring, debris spiralling), animatable position and `twist`; `splash_crown(...)`, `splash_wall(...)`,
`foam_ring(...)`, `spray_trail(path, ...)` (for the chain end skipping), `droplets(...)`, `steam(...)` puffs, `sparks(...)`,
`silt(...)` underwater, `bubbles(...)`, `debris(...)` (planks, roof tiles, container bits on ballistic paths with spin).
Every FX takes start frame / duration and keys itself on threes. Preview: a lightning bolt over the sea, the storm wall from the
port, the waterspout wide, a crown splash around a 8 m pillar standing in the sea, steam puffs, sparks.
