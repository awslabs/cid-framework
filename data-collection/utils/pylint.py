""" This script shows pylint for all Lambda Functions with ZipFile code in yaml

"""
import os
import glob
import subprocess

import cfn_tools # pip install cfn-flip


FOLDER_PATH = 'data-collection/deploy/'
TMP_DIR  = '.tmp'
PYLINT_DISABLE = [
    'C0301', # Line too long
    'C0103', # Invalid name of module
    'C0114', # Missing module docstring
    'C0116', # Missing function or method docstring
    'W1203', # Use lazy % formatting in logging functions (logging-fstring-interpolation)
    'W1201', # Use lazy % formatting in logging functions (logging-not-lazy)
]
BANDIT_SKIP = [
    'B101', # Assert
    'B108', # Hardcoded_tmp_directory
]

def pylint(filename):
    """ call pylint """
    try:
        res = subprocess.check_output(
            f'pylint {filename} --disable {",".join(PYLINT_DISABLE)}'.split(),
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        return res
    except subprocess.CalledProcessError as exc:
        return exc.stdout

def bandit(filename):
    """ call bandit """
    try:
        res = subprocess.check_output(
            f'bandit {filename} --skip {",".join(BANDIT_SKIP)}'.split(),
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if 'No issues identified.' in str(res):
            return 'Bandit: No issues identified.' # skip verbose
        return res
    except subprocess.CalledProcessError as exc:
        return exc.stdout

def tab(text, indent="\t"):
    """ returns text with a tab """
    return '\n'.join([indent + line for line in text.splitlines()])

def main():
    """ run pylint for all lambda functions """
    file_list = glob.glob(os.path.join(FOLDER_PATH, "*.yaml"))
    file_list.sort(key=os.path.getmtime, reverse=True)
    for filename in file_list:
        try:
            with open(filename, encoding='utf-8') as template_file:
                template = cfn_tools.load_yaml(template_file.read())
        except Exception:
            print(f'failed to load {filename}')
            continue
        for name, res in template['Resources'].items():
            if isinstance(res, dict) and res['Type'] == 'AWS::Lambda::Function':
                code = res.get('Properties', {}).get('Code', {}).get('ZipFile')
                if not code:
                    continue
                code_dir =  TMP_DIR + '/' + os.path.basename(filename).rsplit('.', 1)[0] + "/" + name + '/'
                os.makedirs(code_dir, exist_ok=True)

                py_fn = code_dir + '/code.py'
                with open(py_fn, 'w', encoding='utf-8') as py_f:
                    py_f.write(code)
                print(filename, name)
                print(tab(pylint(py_fn)))
                print(tab(bandit(py_fn)))


if __name__ == '__main__':
    main()
