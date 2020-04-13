import subprocess
import re

def check_translation_format(git_path):
    errors_encounter = 0
    pattern = re.compile(r"_\(([\"']{,3})(?P<message>((?!\1).)*)\1(\s*,\s*context\s*=\s*([\"'])(?P<py_context>((?!\5).)*)\5)*(\s*,\s*(.)*?\s*(,\s*([\"'])(?P<js_context>((?!\11).)*)\11)*)*\)")
    temp = re.compile(r"_\(([\"']{,3})")
    subprocess.run('git fetch origin '+git_path+ ' :' +git_path+ ' -q', shell=True)
    files = subprocess.check_output('git diff --name-only '+git_path, shell=True)
    files = files.decode('utf-8')
    files = files.split()
    for file in files:
        with open(file, 'r') as f:
        for num, line in enumerate(f, 1):
            all_matches = temp.finditer(line)
            if all_matches:
            for match in all_matches:
                verify = pattern.search(line)
                if not verify:
                errors_encounter += 1
                print(num)
                print(line)
    if errors_encounter > 0 :
        assert 1+1 == 3
    