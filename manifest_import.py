"""Validated copy-only manifest import. Preview by default; explicit --apply writes."""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile
from workbench import Catalog, LAYERS, STATES, slug, digest, now


def prepare(catalog, manifest, object_root):
    data=json.loads(Path(manifest).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("assets"),list):
        raise ValueError("Unsupported manifest schema")
    root=Path(object_root).resolve(strict=True)
    seen=set(); pending=[]
    existing={r["id"] for r in catalog.rows()}
    for record in data["assets"]:
        if not isinstance(record,dict): raise ValueError("Asset must be an object")
        row=dict(record);key=slug(row.get("id"));slug(row.get("domain"))
        if key in seen or key in existing: raise ValueError("Conflicting asset ID: "+key)
        seen.add(key)
        if row.get("layer") not in LAYERS or row.get("status") not in STATES:
            raise ValueError("Invalid layer or status")
        for field in ("name","source","note","filename"):
            if not isinstance(row.get(field),str):raise ValueError("Invalid "+field)
        if not row["name"].strip() or not row["source"].strip():raise ValueError("Missing provenance/name")
        if Path(row["filename"]).name != row["filename"] or "/" in row["filename"] or "\\" in row["filename"]:raise ValueError("Unsafe filename")
        tags=row.get("tags")
        if not isinstance(tags,list) or any(not isinstance(t,str) or len(t)>80 for t in tags):raise ValueError("Invalid tags")
        checksum=row.get("sha256","")
        if not isinstance(checksum,str) or not re.fullmatch(r"[0-9a-f]{64}",checksum):raise ValueError("Invalid hash")
        if row.get("object_path") != "objects/"+checksum:raise ValueError("Unsafe object path")
        path=root/"objects"/checksum
        if (root/"objects").is_symlink() or path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):raise ValueError("Unsafe/missing source object")
        if digest(path)!=checksum:raise ValueError("Source checksum mismatch")
        target=catalog.objects/checksum
        if target.is_symlink() or (target.exists() and digest(target)!=checksum):raise ValueError("Corrupt/unsafe destination object")
        row["imported_status"]=row["status"]
        # Never import a test assertion as local verification.
        if row["status"]=="tested":row["status"]="unverified"
        pending.append((row,path))
    return pending


def import_manifest(catalog, manifest, object_root, apply=False):
    pending=prepare(catalog,manifest,object_root)
    preview={"mode":"apply" if apply else "preview","count":len(pending),"assets":[{"id":r["id"],"status":r["status"],"source_status":r["imported_status"]} for r,p in pending]}
    if not apply:return preview
    # Recheck bytes during staging before any catalog row is committed.
    with tempfile.TemporaryDirectory(dir=catalog.root) as stage:
        for row,path in pending:
            staged=Path(stage)/row["sha256"];shutil.copyfile(path,staged)
            if digest(staged)!=row["sha256"]:raise ValueError("Source changed while staging")
        with catalog.db:
            for row,path in pending:
                target=catalog.objects/row["sha256"]
                if not target.exists():shutil.copyfile(Path(stage)/row["sha256"],target)
                if digest(target)!=row["sha256"]:raise ValueError("Destination verification failed")
                catalog.db.execute("INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?)",(row["id"],row["name"],row["domain"],row["layer"],row["status"],json.dumps(sorted(set(row["tags"]))),row["sha256"],row["filename"],row["source"],row["note"],now()))
                catalog.event(row["id"],"manifest_import",json.dumps({"source_status":row["imported_status"],"sha256":row["sha256"],"note":"Copied validated object; imported tested claims downgraded"}))
    return preview


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("manifest");p.add_argument("--objects-root",required=True);p.add_argument("--workspace",required=True);p.add_argument("--apply",action="store_true");a=p.parse_args()
    c=Catalog(a.workspace)
    try:print(json.dumps(import_manifest(c,a.manifest,a.objects_root,a.apply),indent=2))
    except (ValueError,OSError,KeyError,TypeError) as e:p.exit(2,str(e)+"\n")
    finally:c.close()
if __name__=="__main__":main()
