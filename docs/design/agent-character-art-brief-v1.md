# Agent character concept and animation brief

Status: reference design; concept generation brief
Date: 2026-10-14
Owner: product and design
Related work: Issue 170 and [ADR 0004](../decisions/0004-conversation-workspace-interaction.md)

Create a small original character family for the conversation-first commerce
workspace. Use image generation to explore the art direction, then create an
editable master for the selected design before rigging it in Rive. The master
artwork, expressive parts and motion system are the durable assets; a flattened
generated image or video is a concept or render, not a reusable character rig.

## Recommended production route

1. Generate one concept board with three distinct characters. Use an existing
   image-model account rather than setting up API infrastructure for this pilot.
2. Choose a direction by testing the character in the actual conversation header,
   sidebar and profile at small sizes. Compare colour and monochrome silhouettes.
3. Use the selected image as the reference for a consistent model sheet and
   expression study. Correct identity drift before producing more views.
4. Develop a substantively original editable vector master, with deliberate
   human design decisions. Use a layered raster master only if the selected
   material cannot be represented satisfactorily as vectors. An automatic trace
   or wrapping a PNG in an SVG is not an equivalent asset or an ownership solution.
5. Build one pilot Rive rig, connect a few illustrative presentation states, and
   test it inside the existing prototype. Archive the editable source/backup
   separately from the runtime export and rendered previews.
6. Add other characters only after the first rig works at avatar size, with
   colour changes, reduced motion and a static fallback.

A flat vector character with subtle volume is the preferred first route. A
sculptural 3D concept can still guide that design. If actual camera turns or
three-dimensional acting become important, make a separate editable Blender
model and rig. A generated image does not contain a recoverable 3D mesh, and
Blender artwork does not automatically become a compatible editable Rive rig.

## Product placement and personality

The audience is adult commerce, merchandising and product operators. The
character should feel like a thoughtful, memorable companion in a precise work
environment. Personality comes from posture, silhouette and gestures. The
interface remains calm, readable and useful during consequential decisions.

At launch these are alternative presentations of the same commerce assistant,
not three new autonomous specialists. Character selection may change its accent
palette and conversational manner; it does not change authority, capabilities,
verified facts or the need for individual approvals.

Explore three unnamed archetypes:

| Archetype | Attitude | Palette | Shape and motion direction |
| --- | --- | --- | --- |
| Curious | Attentive, inquisitive, observant | Cobalt with pale blue | Asymmetric folded form; a small lean and an alert glance. |
| Thoughtful | Composed, warm, deliberate | Apricot with warm cream | A compact sculptural form; balanced posture and measured gestures. |
| Playful | Inventive, encouraging, expressive | Lilac with pale violet | A distinct hinged or layered form; a gentle wave and controlled spring. |

These are exploration directions, not final names or prescribed silhouettes.
Keep the characters recognisably related through materials and facial grammar,
while making their body construction and resting poses distinct.

Use one principal colour per character. Define dark and light accent variants
after testing contrast in the UI. Keep warning, error and success meanings
independent of character colour. Hand-drawn flourishes can appear in the welcome
or profile; do not make approval controls, tables or evidence boundaries wobble.

## References and originality

The supplied Roger Hargreaves reference boards illustrate immediate personality,
simple forms, economical expressions and strong colour. The desired result is
an original family with its own body construction, names, props and stories.
Do not recreate an existing Mr. Men or Little Miss character, alter one slightly,
or convert a recognisable character to 3D and present it as a new invention.

Start with the verbal brief below; attaching the copyrighted boards is optional,
not necessary to generate these qualities. Before uploading reference images to
a service, check that the intended input use is permitted by its terms and the
rights you have. The reference instruction below does not itself grant rights.

If reference boards are attached, append this instruction to the model prompt:

> The attached boards illustrate broad design principles: readable silhouettes,
> simple expressive faces, clear personality and a restrained palette. Develop
> a new visual vocabulary. Do not reproduce a depicted character, its defining
> silhouette, distinctive accessories, name, lettering or biography. Create
> characters that stand on their own without claiming an official connection.

## Prompt 1 Concept board

Copy this prompt into an image model. This stage asks for concept imagery, not
layered source files or a finished Rive rig.

```text
Create a concept board for THREE ORIGINAL companion characters for a clean,
conversation-first professional AI workspace. The users are adult commerce,
merchandising and product operators. The characters should have warmth, wit
and immediate recognisability, while feeling credible beside work decisions.

Art direction:
Create a new family of small, sculptural, deliberately designed creatures.
Explore folded, hinged or layered body construction, subtle asymmetry and
tactile matte materials. Give each an economical expressive face and a
distinct resting posture. Use gentle 2.5D volume, restrained shading and
clean contours that could later be reconstructed as editable vector parts.
Avoid generic glossy AI blobs, stock robots, emoji balls and toy packaging.

Show three personalities:
1. Curious: observant, inquisitive, cobalt blue with a pale-blue secondary tone.
2. Thoughtful: composed, warm, apricot with a cream secondary tone.
3. Playful: inventive, encouraging, lilac with a pale-violet secondary tone.

Make the body architecture and pose of each character genuinely different.
Changing only the colour of the same body is insufficient. They should share
a visual family through material, facial grammar and level of detail.
No names, lettering, logos, biographies or existing brand characters.

Composition:
One clean landscape board with three equal columns. Show one full-body,
front-facing neutral pose in each column at the same scale and baseline.
Use a plain warm-white background and generous space around every character.
No scene, furniture, interface, collage of additional views or heavy shadow.
Keep the whole silhouette visible, including limbs. Separate limbs enough
to make their joints understandable. Keep facial features simple and large
enough to read when the character is reduced to a 32-pixel avatar.

Animation considerations:
Design clearly separable eyes, brows if needed, mouth, limbs and body pieces.
Avoid fuzzy edges, dense texture, tiny accessories and limbs fused into the
body silhouette. A few expressive parts are better than complicated anatomy.
The expression should be attentive and relaxed, not constantly ecstatic.

Originality:
Use broad principles of economy, personality and strong silhouette. Do not
recreate, recolour, modernise or render a recognisable existing book character
in 3D. Invent your own body construction, proportions and facial arrangement.

Output a high-resolution concept board. If output-size selection is available,
choose a landscape format with a long edge around 2400 pixels or greater.
```

## Prompt 2 Selected character model sheet

Attach only the selected original concept as the identity reference. Generate
this sheet after selecting a character, not independently for every candidate.

```text
Use the attached SELECTED ORIGINAL CHARACTER as the identity reference.
Create a production reference sheet for the exact same character. Preserve
its proportions, face placement, body construction, limb lengths, palette and
material. Do not redesign it or introduce new accessories.

On a plain warm-white background, show four equally scaled full-body views:
front, three-quarter, side and back. Keep the lighting and baseline consistent.
Use neutral, animation-friendly poses with limbs slightly separated. No
foreshortened camera effects, props, labels, text, logos or scene.

These views are references for a human-created editable master and rig, not
claims that the generated image is already a 3D model. Make the back and side
construction coherent with the approved front view. Preserve recognisable
identity across all views and avoid invented hidden details that change it.
```

## Prompt 3 Expression and pose study

```text
Using the attached SELECTED ORIGINAL CHARACTER, create six consistent pose
studies on a plain background, with the same scale and body proportions:
neutral attentive, working, awaiting the user's decision, paused, result
available, and needs attention.

Convey state through restrained eye direction, posture and a simple gesture.
Awaiting a decision must feel patient, not pleading. Needs attention must feel
clear and composed, not panicked or blaming the user. Result available should
be quietly informative, not a confetti celebration or a claim of business
success. Paused should settle into a comfortable still pose.

Keep the character's geometry, palette, material and identity unchanged.
Do not add objects, text, status symbols or accessories. Leave room around
each pose. These are separate pose references, not an animation or a rig.
```

Generated model sheets can drift. Reject changed limb counts, facial spacing,
body volume and accessories instead of accepting them as alternate designs.
Once the master exists, reuse it for poses; do not keep regenerating the asset.

## Editable artwork and Rive handoff

The chosen character must be rebuilt with real, named editable parts. Do not
ask an image model to promise a layered PSD, SVG geometry or a Rive file unless
the actual product can produce that format and the exported file is inspected.

| Deliverable | Requirement |
| --- | --- |
| Master artwork | Editable vector paths and fills in a design source and plain SVG; no flattened image disguised as vectors. Alternatively, a layered raster source with complete separated parts. |
| Anatomy | Named body, head if separate, eyes, eyelids, mouth and each articulated limb. Reconstruct obscured portions so movement reveals no missing pixels or geometry. |
| Material | Palette, stroke/edge treatment, shading recipe and any owned/licensed textures. Separate shadows from body parts. |
| Identity sheet | Approved neutral front view, consistent other views, proportions and expression rules. |
| Recolouring | Separate palette tokens; usable light/dark variants, including a monochrome silhouette. |
| Rive project | Editable source/backup available from the selected editor/version, plus the runtime export and documented animation/state names. Verify account export access before commissioning the rig. |
| Fallbacks | Transparent still exports at useful sizes and a reduced-motion still/path. No checkerboard baked into an image presented as transparent. |
| Archive | Prompts, original generated concepts, human design revisions, source files, exports, tool/model versions and asset rights records. |

Pilot motion: a small glance/lean for working, a patient settled pose when a
decision is needed, a brief acknowledgement when a result becomes available,
and a composed needs-attention pose. Avoid endless bouncing. Keep reading and
approval interaction available before the animation loads. Motion reflects
actual application state and never authorises work; a cheerful gesture is not
proof of successful execution or commercial impact. Listening and speaking can
be added later when those product capabilities exist.

Rive supports vector artwork, raster images, layered PSD import and bones/meshes.
That supports this handoff, but importing a single PNG does not separate its
eyes, limbs or expressions. See [Rive features](https://rive.app/features) and
[reduced-motion authoring](https://rive.app/docs/editor/accessibility/reduced-motion).

## Ownership and provider choice

Keep three questions separate: permission to use an output commercially,
copyright protection for the authored design, and practical control of editable
source files. No provider choice alone guarantees all three or exclusivity.

- Google's Gemini API terms say Google does not claim ownership of generated
  content, while allowing similar outputs for others. These are API/AI Studio
  terms, not a substitute for checking the particular consumer app or reseller
  used to access an image model. [Google terms](https://ai.google.dev/gemini-api/terms).
- Runway states that it does not impose non-commercial restrictions on created
  content and that, between the user and Runway, the user retains their rights.
  This is provider permission, not proof of exclusive copyright or clearance of
  a borrowed character. [Runway commercial use](https://help.runwayml.com/hc/en-us/articles/21668707517587-Can-I-use-the-content-I-made-in-Runway-for-commercial-purposes).
- OpenRouter states that output ownership is governed by the selected model's
  terms. An OpenRouter key does not create stronger ownership rights. Use it
  when repeatable generation, model comparison or an API workflow becomes useful.
  [OpenRouter terms](https://openrouter.ai/terms).
- ByteDance identifies Seedream as its image family and Seedance as its video
  family. Use still-image generation for the concept stage; generated videos
  can be motion references, not the editable master. The terms of the actual
  service and account used still need checking. [Seed models](https://seed.bytedance.com/en/models).

Start in an existing image-model UI with a small pilot. Free access is adequate
for exploration if its terms and export quality suit the task; it does not
establish exclusivity. No API key or paid infrastructure is needed to use this
brief. No comparative model-quality benchmark is claimed here.

For stronger authorship provenance, develop an original design through
substantive human creative work and keep its source history. Merely tracing a
generated image is not a guarantee of copyright protection. U.S. guidance
distinguishes human-authored expression from prompt-only generation; rules
and outcomes differ by jurisdiction. [U.S. Copyright Office guidance](https://www.copyright.gov/newsnet/2025/1060.html).

If hiring an artist or animator, agree in writing on the rights to the original
artwork and animation, source-file delivery, modification, commercial use and
future media. Commissioning by itself does not necessarily transfer copyright.
Ask for a record of incorporated third-party assets and their licences.
[UK guidance on commissioned images](https://www.gov.uk/government/publications/copyright-notice-digital-images-photographs-and-the-internet/copyright-notice-digital-images-photographs-and-the-internet).

## Acceptance for the first character

- Distinct from the supplied book characters in its defining design.
- Readable at 32 and 48 pixels; expressive at 128 pixels without extra clutter.
- Coherent silhouette in monochrome and on both interface appearances.
- Palette can change without redrawing the face or losing useful contrast.
- Art remains editable and body parts remain complete through pose changes.
- One short Rive pilot has a neutral resting pose, controlled transitions and
  a tested reduced-motion/static fallback.
- Independent local copies of artwork, animation source, runtime exports and
  provenance records are available. The pilot does not depend on retaining an
  image-generation subscription to redraw or reanimate the chosen character.

This brief defines a proposed production route. It contains no generated final
artwork, tested Rive rig or verified editor connection, and does not change the
workspace implementation or accepted execution authority.
