import os
import glob
import sys

with open('data_stats.txt', 'w', encoding='utf-8') as fs:
    data_dirs = ['data/original', 'data/standardized_256', 'data/standardized_384']
    for d in data_dirs:
        fs.write(f"\\nDirectory: {d}\\n")
        if not os.path.exists(d):
            fs.write("  Not found.\\n")
            continue
        
        classes = [c for c in os.listdir(d) if os.path.isdir(os.path.join(d, c))]
        for cls in classes:
            cls_dir = os.path.join(d, cls)
            files = os.listdir(cls_dir)
            count = len(files)
            size = sum(os.path.getsize(os.path.join(cls_dir, f)) for f in files)
            types = set(os.path.splitext(f)[1].lower() for f in files)
            
            # Check corrupt / 0-byte
            corrupt = sum(1 for f in files if os.path.getsize(os.path.join(cls_dir, f)) == 0)
            
            mb = size / (1024*1024)
            fs.write(f"  {cls}: {count} files, {mb:.2f} MB, types: {types}, 0-byte corrupt files: {corrupt}\\n")
