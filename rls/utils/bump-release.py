import sys
import git
import json

repo = git.Repo('.')

print(repo.git.execute('git checkout main'.split()))
print(repo.git.execute('git pull'.split()))
module = 'rls'


old_ver = json.load(open(f"{module}/utils/version.json"))['version']

print(old_ver)
bump = 'patch'
if len(sys.argv) > 1:
    bump = sys.argv[1]

maj, minor, patch = map(int, old_ver.split('.'))

if bump == 'patch':
    new_ver = '.'.join(map(str, [maj, minor, patch + 1]))
elif bump == 'minor':
    new_ver = '.'.join(map(str, [maj, minor + 1, 0]))
else:
    raise NotImplementedError('only patch and minor are implemented')

print(repo.git.execute(f"git checkout -b release/{new_ver}".split()))


tx = open("{module}/utils/version.json").read()
with open("{module}/utils/version.json", "w") as f:
    f.write(tx.replace(old_ver, new_ver))


filenames = [
    f"{module}/deploy/deploy-{module}.yaml",
    f"{module}/utils/version.json",
]
for filename in filenames:
    tx = open(filename).read()
    with open(filename, "w") as f:
        f.write(tx.replace(f"v{old_ver}", f"v{new_ver}"))


print(repo.git.execute('git diff HEAD --unified=0'.split()))

print('to undo:\n git checkout HEAD -- cfn-templates/cid-cfn.yml cid/_version.py')
print(f"to continue:\n git commit -am 'release {new_ver}'; git push origin 'release/{new_ver}'")
