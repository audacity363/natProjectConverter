# Purpose
This script converts an old plain fuser to an folder structure which can be imported into NaturalOne. Whereby GDAs/PDAs/LDAs, which were created using the old Natural editor, gets converted into source code.

# Quickstart
```
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 converter.py --help
```
1. Create new Natural project in NatOne
2. Right click on `Natural-Libraries` => Import 
3. Select General => File System
4. Select the output folder => select everything you want to import => Finish

# Disclamer
This is just a quickly hacked together script and has the motto "It works on my machine". There is no garantee that it will work with all combinations, which can get generated with the old Natural editor, nether that the output doesn't have any errors.