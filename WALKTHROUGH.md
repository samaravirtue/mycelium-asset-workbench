# Learn the current workbench

## 1. Run the checks
Open a terminal in this downloaded repository. On Windows:
```
py -3 -m unittest discover -s . -v
py -3 demo.py
```
Expected: 27 tests, 26 passing and one skipped when Windows cannot create symlinks. The tests check the organizer, not a game or world.

## 2. Look at the layers
Open layered_demo/layers.html from File Explorer. Each illustrative domain has six layers. These are fictional layout examples, not your private work or actual 3D models. Open layered_demo/gallery.html to search them. Search winter (six results), winter water (one), and clear the box (24). Reports are read-only snapshots.

## 3. Inspect a record
```
py -3 workbench.py --workspace layered_demo/catalog search winter
```
ID is a stable label. Domain and layer say where it belongs. Source records origin. SHA256 identifies the exact file contents. Reference/proposal are not completed meshes. A tested status requires a recorded claim but does not independently prove that claim.

## 4. Check that copies match
```
py -3 workbench.py --workspace layered_demo/catalog verify
```
Every result should say true. This checks stored bytes, not artistic quality, licensing or engine compatibility. Originals are not renamed or moved.

## 5. Understand planned links
Open layered_demo/scene_plan.json and project_index.json in a text editor. IDs connect proposed modules and fictional projects. A planned passage is not a working portal. Engine-ready is false. Cross-project indexing is not an exhaustive inventory of your real projects.

## 6. Safe first experiment
Use only a disposable fictional text or image file, never private art for this learning exercise. The default local_catalog workspace is separate from the synthetic demo. Use the intake example in README with your chosen fictional file. Then search and generate a report. Never upload local_catalog or your real assets to the public repository.

## 7. What to learn before the next milestone
Explain the difference between an original and a stored copy; a reference and a tested asset; a report and an editor. Read Catalog.ingest, Catalog.verify and Catalog.report in workbench.py. Record what you changed and tested yourself. AI wrote this implementation; learning it is not the same as claiming unaided authorship.

Manifest import, an editable GUI and Godot integration are not published features. Pause new milestones until you are comfortable with this version. No job application has been submitted.
