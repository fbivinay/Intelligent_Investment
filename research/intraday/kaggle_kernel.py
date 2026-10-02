import hashlib, json, os, shutil, subprocess, sys
src = next(os.path.join(r, "") for r, d, f in os.walk("/kaggle/input") if "research" in d)
shutil.copytree(src, "/kaggle/working/proj", dirs_exist_ok=True)
os.chdir("/kaggle/working/proj")
print("cpus", os.cpu_count(), flush=True)
subprocess.run([sys.executable, "-m", "research.intraday.grid", str(os.cpu_count())], check=True)
out = "/kaggle/working/out"
os.makedirs(out, exist_ok=True)
shutil.copy("research/out/intraday/grid.csv", out)
h = hashlib.sha256(open(f"{out}/grid.csv", "rb").read()).hexdigest()
json.dump({"files": {"grid.csv": h}}, open(f"{out}/outputs.json", "w"))
shutil.rmtree("/kaggle/working/proj")
